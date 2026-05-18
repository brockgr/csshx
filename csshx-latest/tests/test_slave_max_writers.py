"""Tests for the ``Slave.max_writers`` fan-out cap on the data socket.

A leaked AUTH token would otherwise let an attacker attach an
unbounded number of writers to the same slave socket. ``max_writers``
caps the simultaneously-attached count *after* the AUTH handshake (so
the check itself isn't a probe oracle).
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

pytest.importorskip("fcntl", reason="max-writers tests need Unix pipes/sockets")
if sys.platform == "win32":  # pragma: no cover
    pytest.skip("AF_UNIX not available", allow_module_level=True)

from csshx_latest.slave import (
    DEFAULT_MAX_WRITERS,
    Slave,
    run_slave_bridge,
    shutdown_slave,
)


def _make_slave(sock_path: str, ctl_path: str, pty_fd: int, pid: int, *, max_writers: int) -> Slave:
    return Slave(
        index=1,
        host="h",
        sock_path=sock_path,
        ctl_sock_path=ctl_path,
        token="TOK",
        pty_master=pty_fd,
        pid=pid,
        max_writers=max_writers,
    )


async def _attach(sock_path: str, token: str) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Open the data socket and complete the ``AUTH <token>\\n`` handshake."""
    reader, writer = await asyncio.open_unix_connection(sock_path)
    writer.write(f"AUTH {token}\n".encode("ascii"))
    await writer.drain()
    return reader, writer


def test_default_max_writers_constant_is_reasonable():
    """A regression guard: DEFAULT_MAX_WRITERS must be small but > 1."""
    assert 1 < DEFAULT_MAX_WRITERS <= 16


def test_max_writers_caps_concurrent_attachments(short_socket_dir, harmless_pid):
    """Above the cap, additional attachments are closed by the server."""
    import pty

    pty_master, pty_slave = pty.openpty()
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    ctl_path = os.path.join(short_socket_dir, "slave.ctl")
    slave = _make_slave(sock_path, ctl_path, pty_master, harmless_pid, max_writers=2)

    async def go() -> None:
        await run_slave_bridge(slave)
        # First two attaches must succeed and register.
        _, w1 = await _attach(sock_path, slave.token)
        _, w2 = await _attach(sock_path, slave.token)
        # Give the server a tick to process AUTH + register.
        for _ in range(10):
            await asyncio.sleep(0.02)
            if len(slave.connected_writers) >= 2:
                break
        assert len(slave.connected_writers) == 2

        # Third attach passes AUTH but the server rejects + closes it.
        _, w3 = await _attach(sock_path, slave.token)
        try:
            await asyncio.wait_for(w3.wait_closed(), timeout=1.5)
        except Exception:
            pass
        # After rejection, the cap is still 2.
        assert len(slave.connected_writers) == 2

        for w in (w1, w2):
            w.close()
            try:
                await w.wait_closed()
            except Exception:
                pass

    try:
        asyncio.run(go())
    finally:
        os.close(pty_slave)
        shutdown_slave(slave)


def test_unauthenticated_attach_does_not_count_against_cap(short_socket_dir, harmless_pid):
    """A bad token never makes it past AUTH, so it never consumes a slot."""
    import pty

    pty_master, pty_slave = pty.openpty()
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    ctl_path = os.path.join(short_socket_dir, "slave.ctl")
    slave = _make_slave(sock_path, ctl_path, pty_master, harmless_pid, max_writers=1)

    async def go() -> None:
        await run_slave_bridge(slave)
        # Bad AUTH: server should close immediately.
        reader, writer = await asyncio.open_unix_connection(sock_path)
        writer.write(b"AUTH not-the-real-token\n")
        await writer.drain()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
        except Exception:
            pass
        assert slave.connected_writers == []

        # Now a legitimate attach should still succeed — the bad attempt
        # never consumed the one allowed slot.
        _, w2 = await _attach(sock_path, slave.token)
        for _ in range(10):
            await asyncio.sleep(0.02)
            if len(slave.connected_writers) >= 1:
                break
        assert len(slave.connected_writers) == 1
        w2.close()
        try:
            await w2.wait_closed()
        except Exception:
            pass

    try:
        asyncio.run(go())
    finally:
        os.close(pty_slave)
        shutdown_slave(slave)
