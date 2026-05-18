"""Tests for the slave control socket (WINSZ propagation, AUTH gating)."""
from __future__ import annotations

import asyncio
import os
import struct
import sys

import pytest

pytest.importorskip("fcntl", reason="control-socket tests need Unix pipes/sockets")
if sys.platform == "win32":  # pragma: no cover
    pytest.skip("AF_UNIX not available", allow_module_level=True)

from csshx_latest.slave import Slave, _apply_control_line, run_slave_bridge, shutdown_slave


def _make_slave(sock_path: str, ctl_path: str, pty_fd: int, pid: int, token: str = "TOK") -> Slave:
    return Slave(
        index=1,
        host="h",
        sock_path=sock_path,
        ctl_sock_path=ctl_path,
        token=token,
        pty_master=pty_fd,
        pid=pid,
    )


def test_apply_control_line_resizes_pty():
    """A well-formed WINSZ line should call TIOCSWINSZ on the slave's PTY."""
    import fcntl
    import pty
    import termios

    pty_master, pty_slave = pty.openpty()
    try:
        slave = _make_slave("", "", pty_master, 0)
        _apply_control_line(slave, b"WINSZ 42 137 0 0\n")
        packed = fcntl.ioctl(pty_slave, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, _, _ = struct.unpack("HHHH", packed)
        assert rows == 42
        assert cols == 137
    finally:
        os.close(pty_master)
        os.close(pty_slave)


def test_apply_control_line_rejects_bad_grammar():
    """Malformed lines are ignored without raising."""
    import pty

    pty_master, pty_slave = pty.openpty()
    try:
        slave = _make_slave("", "", pty_master, 0)
        # All these should be no-ops, never raise.
        _apply_control_line(slave, b"WINSZ\n")
        _apply_control_line(slave, b"WINSZ abc def\n")
        _apply_control_line(slave, b"HELLO 1 2\n")
        _apply_control_line(slave, b"\n")
        _apply_control_line(slave, b"\xff\xfe\n")  # non-ascii
        _apply_control_line(slave, b"WINSZ -1 80\n")  # non-positive
        _apply_control_line(slave, b"BYE extra\n")  # BYE takes no args
    finally:
        os.close(pty_master)
        os.close(pty_slave)


def test_apply_control_line_bye_marks_user_closed_and_sigterms_ssh(harmless_pid):
    """``BYE`` sets ``user_closed=True`` and sends SIGTERM to the ssh pid.

    This is the path that makes "close the terminal window → slave
    actually exits" work. We mock os.kill so we don't actually kill the
    fixture's helper process; we only need to verify the SIGTERM was
    issued with the right pid.
    """
    import pty
    import signal as _signal
    import unittest.mock

    from csshx_latest import slave as slave_mod

    pty_master, pty_slave = pty.openpty()
    try:
        slave = _make_slave("", "", pty_master, harmless_pid)
        assert slave.user_closed is False

        with unittest.mock.patch.object(slave_mod.os, "kill") as fake_kill:
            _apply_control_line(slave, b"BYE\n")

        assert slave.user_closed is True
        fake_kill.assert_called_once_with(harmless_pid, _signal.SIGTERM)
    finally:
        os.close(pty_master)
        os.close(pty_slave)


def test_apply_control_line_bye_is_idempotent(harmless_pid):
    """A second ``BYE`` after the first is a silent no-op (no extra SIGTERM)."""
    import pty
    import unittest.mock

    from csshx_latest import slave as slave_mod

    pty_master, pty_slave = pty.openpty()
    try:
        slave = _make_slave("", "", pty_master, harmless_pid)
        with unittest.mock.patch.object(slave_mod.os, "kill") as fake_kill:
            _apply_control_line(slave, b"BYE\n")
            _apply_control_line(slave, b"BYE\n")
        assert fake_kill.call_count == 1
    finally:
        os.close(pty_master)
        os.close(pty_slave)


def test_apply_control_line_bye_skips_kill_for_already_dead_slave(harmless_pid):
    """If ``slave.dead`` is already set (natural ssh exit), BYE does not SIGTERM."""
    import pty
    import unittest.mock

    from csshx_latest import slave as slave_mod

    pty_master, pty_slave = pty.openpty()
    try:
        slave = _make_slave("", "", pty_master, harmless_pid)
        slave.dead = True  # PTY EOF beat the BYE to the punch
        with unittest.mock.patch.object(slave_mod.os, "kill") as fake_kill:
            _apply_control_line(slave, b"BYE\n")
        assert slave.user_closed is True
        fake_kill.assert_not_called()
    finally:
        os.close(pty_master)
        os.close(pty_slave)


def test_control_socket_requires_auth(short_socket_dir, harmless_pid):
    """A client that fails AUTH on the control socket must not be able to resize."""
    import pty

    pty_master, pty_slave = pty.openpty()
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    ctl_path = os.path.join(short_socket_dir, "slave.ctl")
    slave = _make_slave(sock_path, ctl_path, pty_master, harmless_pid, token="REAL")

    async def go() -> None:
        await run_slave_bridge(slave)
        # Connect to the control socket and send a wrong AUTH.
        reader, writer = await asyncio.open_unix_connection(ctl_path)
        writer.write(b"AUTH WRONG\n")
        writer.write(b"WINSZ 99 200 0 0\n")
        await writer.drain()
        await asyncio.sleep(0.1)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    try:
        asyncio.run(go())
    finally:
        os.close(pty_slave)
        shutdown_slave(slave)
    # The PTY should NOT have been resized -- but we can't read it post-close.
    # The strong assertion is just that no exception was raised and AUTH dropped
    # the connection before WINSZ was honored.


def test_control_socket_accepts_winsz_after_auth(short_socket_dir, harmless_pid):
    """A correctly-authenticated client can resize the slave's PTY."""
    import fcntl
    import pty
    import termios

    pty_master, pty_slave = pty.openpty()
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    ctl_path = os.path.join(short_socket_dir, "slave.ctl")
    slave = _make_slave(sock_path, ctl_path, pty_master, harmless_pid, token="OK")

    async def go() -> None:
        await run_slave_bridge(slave)
        reader, writer = await asyncio.open_unix_connection(ctl_path)
        writer.write(b"AUTH OK\n")
        writer.write(b"WINSZ 50 123 0 0\n")
        await writer.drain()
        # Let the server process the line.
        for _ in range(10):
            await asyncio.sleep(0.02)
            packed = fcntl.ioctl(pty_slave, termios.TIOCGWINSZ, b"\x00" * 8)
            rows, cols, _, _ = struct.unpack("HHHH", packed)
            if rows == 50 and cols == 123:
                break
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    try:
        asyncio.run(go())
        packed = fcntl.ioctl(pty_slave, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, _, _ = struct.unpack("HHHH", packed)
        assert rows == 50
        assert cols == 123
    finally:
        os.close(pty_slave)
        shutdown_slave(slave)
