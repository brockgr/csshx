"""End-to-end test: real PTY + a cat child standing in for ssh.

This is the integration coverage the unit tests can't give us. We
spawn a real PTY with ``cat`` as the child, wire it up to a real
``Slave`` via ``run_slave_bridge``, connect through the attach client,
and assert that bytes written to the data socket reach cat and are
echoed back.
"""
from __future__ import annotations

import asyncio
import os
import pty
import sys

import pytest

pytest.importorskip("fcntl", reason="PTY integration needs Unix")
if sys.platform == "win32":  # pragma: no cover
    pytest.skip("PTY is Unix-only", allow_module_level=True)

from csshx_latest.auth import write_token_file
from csshx_latest.slave import Slave, run_slave_bridge, shutdown_slave


def test_pty_bytes_round_trip_through_socket(short_socket_dir):
    """Write 'ping\\n' to the data socket -> cat echoes 'ping\\n' back."""
    sock_path = os.path.join(short_socket_dir, "slave.sock")
    ctl_path = os.path.join(short_socket_dir, "slave.ctl")
    token_path = os.path.join(short_socket_dir, "slave.token")
    write_token_file(token_path, "TOK")

    pty_master, pty_slave = pty.openpty()
    pid = os.fork()
    if pid == 0:
        try:
            os.setsid()
            os.close(pty_master)
            os.dup2(pty_slave, 0)
            os.dup2(pty_slave, 1)
            os.dup2(pty_slave, 2)
            if pty_slave > 2:
                os.close(pty_slave)
            os.execvp("cat", ["cat"])
        except Exception:
            os._exit(127)
    os.close(pty_slave)

    slave = Slave(
        index=1,
        host="localhost",
        sock_path=sock_path,
        ctl_sock_path=ctl_path,
        token="TOK",
        token_path=token_path,
        pty_master=pty_master,
        pid=pid,
    )

    async def go() -> bytes:
        await run_slave_bridge(slave)
        reader, writer = await asyncio.open_unix_connection(sock_path)
        writer.write(b"AUTH TOK\n")
        writer.write(b"ping\n")
        await writer.drain()
        # cat will echo "ping\n" back; read until we see it.
        collected = bytearray()
        for _ in range(50):
            try:
                chunk = await asyncio.wait_for(reader.read(64), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if not chunk:
                break
            collected.extend(chunk)
            if b"ping" in collected:
                break
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return bytes(collected)

    try:
        out = asyncio.run(go())
    finally:
        shutdown_slave(slave)
        try:
            os.waitpid(pid, 0)
        except (ChildProcessError, OSError):
            pass

    assert b"ping" in out


def test_alpha_brace_expansion():
    """``host-{a..c}`` expands to host-a host-b host-c."""
    from csshx_latest.hosts import expand_hosts

    assert expand_hosts(["host-{a..c}"]) == ["host-a", "host-b", "host-c"]
