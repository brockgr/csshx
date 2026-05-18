"""Tests for the broadcast routing logic.

Uses a real ``os.pipe`` as a stand-in for a PTY master fd so we can
verify which slaves received what bytes without forking ssh.
"""
from __future__ import annotations

import asyncio
import os

import pytest

pytest.importorskip("fcntl", reason="broadcaster tests require Unix pipe semantics")

from csshx_latest.master import Broadcaster
from csshx_latest.slave import Slave


def _slave(index: int, *, enabled: bool = True) -> tuple[Slave, int]:
    """Return a Slave whose pty_master is the write end of a fresh pipe."""
    r, w = os.pipe()
    s = Slave(
        index=index,
        host=f"host{index}",
        sock_path=f"/tmp/fake-{index}",
        token="t",
        pty_master=w,
        pid=0,
        enabled=enabled,
    )
    return s, r


def _drain(fd: int) -> bytes:
    import fcntl
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    try:
        return os.read(fd, 1024)
    except BlockingIOError:
        return b""


def test_enabled_indices_filters():
    b = Broadcaster()
    s1, _ = _slave(1, enabled=True)
    s2, _ = _slave(2, enabled=False)
    s3, _ = _slave(3, enabled=True)
    for s in (s1, s2, s3):
        b.add(s)
    assert b.enabled_indices() == [1, 3]


def test_toggle_flips_enabled():
    b = Broadcaster()
    s1, _ = _slave(1, enabled=True)
    b.add(s1)
    b.toggle(1)
    assert s1.enabled is False
    b.toggle(1)
    assert s1.enabled is True


def test_toggle_unknown_index_raises():
    b = Broadcaster()
    with pytest.raises(KeyError):
        b.toggle(999)


def test_broadcast_writes_only_to_enabled_slaves():
    b = Broadcaster()
    s1, r1 = _slave(1, enabled=True)
    s2, r2 = _slave(2, enabled=False)
    s3, r3 = _slave(3, enabled=True)
    for s in (s1, s2, s3):
        b.add(s)

    asyncio.run(b.broadcast(b"hello"))

    assert _drain(r1) == b"hello"
    assert _drain(r2) == b""
    assert _drain(r3) == b"hello"


def test_broadcast_with_no_slaves_does_not_raise():
    b = Broadcaster()
    asyncio.run(b.broadcast(b"anything"))
