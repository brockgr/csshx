"""Integration-ish tests for the PTY <-> socket bridge.

These exercise the bug fix where late-connecting terminal blocks would
miss the SSH banner / login prompt because the PTY reader had no
clients to forward to. With the scrollback buffer, connecting *after*
the PTY has emitted bytes should still deliver every byte to the new
client right after AUTH succeeds.

Two macOS-specific gotchas the fixtures handle:

* ``short_socket_dir`` keeps the AF_UNIX path under macOS's 104-byte
  ``sun_path`` limit (pytest's ``tmp_path`` does not).
* ``harmless_pid`` ensures the Slave has a real PID — ``shutdown_slave``
  calls ``os.kill(pid, SIGTERM)`` and ``os.kill(0, ...)`` would signal
  the entire process group (i.e. pytest itself).
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

pytest.importorskip("fcntl", reason="bridge tests need Unix pipes/sockets")
if sys.platform == "win32":  # pragma: no cover - skip path
    pytest.skip("asyncio.start_unix_server is not available on Windows", allow_module_level=True)
if not hasattr(asyncio, "start_unix_server"):  # pragma: no cover
    pytest.skip("Unix-domain asyncio server not available", allow_module_level=True)

from csshx_latest.slave import Slave, run_slave_bridge, shutdown_slave


def _make_slave(sock_path: str, pty_read_fd: int, pid: int, *, token: str = "TOK") -> Slave:
    return Slave(
        index=1,
        host="h",
        sock_path=sock_path,
        token=token,
        pty_master=pty_read_fd,
        pid=pid,
    )


def test_late_client_receives_scrollback(short_socket_dir, harmless_pid):
    """Bytes emitted before any client connected must be replayed on AUTH."""
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    pty_r, pty_w = os.pipe()
    slave = _make_slave(sock_path, pty_r, harmless_pid)

    async def go() -> bytes:
        # Bridge sets up server + pty_reader_task. After this returns, the
        # reader task is running and will pick up bytes from pty_r.
        await run_slave_bridge(slave)
        # Emit "banner" bytes before any client has connected. These must
        # land in the scrollback buffer.
        os.write(pty_w, b"SSH banner\nlogin: ")
        # Yield enough times for the reader task to drain the pipe into
        # scrollback.
        for _ in range(10):
            await asyncio.sleep(0.01)
        # Now connect a client, AUTH, and read the replay.
        reader, writer = await asyncio.open_unix_connection(sock_path)
        writer.write(f"AUTH {slave.token}\n".encode())
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), timeout=1.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return data

    try:
        received = asyncio.run(go())
    finally:
        os.close(pty_w)
        shutdown_slave(slave)

    assert b"SSH banner" in received
    assert b"login: " in received


def test_scrollback_is_capped(short_socket_dir, harmless_pid):
    """A flood of pre-connect output must not unbounded-grow the buffer."""
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    pty_r, pty_w = os.pipe()
    slave = _make_slave(sock_path, pty_r, harmless_pid)
    slave.scrollback_max = 1024  # tighten the cap for the test

    async def go() -> int:
        await run_slave_bridge(slave)
        os.write(pty_w, b"x" * 4096)
        for _ in range(20):
            await asyncio.sleep(0.01)
            if len(slave.scrollback) >= slave.scrollback_max:
                break
        return len(slave.scrollback)

    try:
        size = asyncio.run(go())
    finally:
        os.close(pty_w)
        shutdown_slave(slave)

    assert size <= slave.scrollback_max
    assert size > 0


def test_wrong_token_is_rejected_and_does_not_get_scrollback(short_socket_dir, harmless_pid):
    """Failed AUTH must drop the connection without leaking scrollback."""
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    pty_r, pty_w = os.pipe()
    slave = _make_slave(sock_path, pty_r, harmless_pid, token="REAL_TOKEN")

    async def go() -> bytes:
        await run_slave_bridge(slave)
        os.write(pty_w, b"super secret prompt")
        for _ in range(10):
            await asyncio.sleep(0.01)
        reader, writer = await asyncio.open_unix_connection(sock_path)
        writer.write(b"AUTH wrong-token\n")
        await writer.drain()
        # Server should close the connection without sending anything.
        data = await asyncio.wait_for(reader.read(4096), timeout=1.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return data

    try:
        received = asyncio.run(go())
    finally:
        os.close(pty_w)
        shutdown_slave(slave)

    assert received == b""
