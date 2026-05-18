"""Tests for dead-slave detection and the broadcaster's exclusion of dead slaves.

Covers the behavior added in v1.1:

* a slave with ``dead=True`` is not in ``enabled_indices``;
* ``write_to_slave`` is a silent no-op on a dead slave (so a stale fd
  doesn't raise EBADF and crash the broadcast);
* ``set_all_enabled`` skips dead slaves (their ``enabled`` flag is
  meaningless after their ssh has exited).
"""
from __future__ import annotations

import asyncio
import os

import pytest

pytest.importorskip("fcntl", reason="dead-slave tests require Unix pipe semantics")

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.slave import Slave, write_to_slave


def _slave(index: int, *, enabled: bool = True, dead: bool = False) -> tuple[Slave, int]:
    r, w = os.pipe()
    s = Slave(
        index=index,
        host=f"h{index}",
        sock_path=f"/tmp/s{index}",
        token="t",
        pty_master=w,
        pid=0,
        enabled=enabled,
        dead=dead,
    )
    return s, r


def test_dead_slave_excluded_from_enabled_indices():
    b = Broadcaster()
    s1, _ = _slave(1, enabled=True, dead=False)
    s2, _ = _slave(2, enabled=True, dead=True)
    b.add(s1)
    b.add(s2)
    assert b.enabled_indices() == [1]


def test_dead_slave_excluded_from_alive_indices():
    b = Broadcaster()
    s1, _ = _slave(1, dead=False)
    s2, _ = _slave(2, dead=True)
    b.add(s1)
    b.add(s2)
    assert b.alive_indices() == [1]


def test_write_to_slave_is_noop_for_dead_slave():
    """A dead slave's pipe should never be written to, even if enabled."""
    s, r = _slave(1, enabled=True, dead=True)

    asyncio.run(write_to_slave(s, b"should-not-arrive"))

    import fcntl
    flags = fcntl.fcntl(r, fcntl.F_GETFL)
    fcntl.fcntl(r, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    try:
        got = os.read(r, 1024)
    except BlockingIOError:
        got = b""
    assert got == b""


def test_set_all_enabled_skips_dead_slaves():
    """``b`` (toggle all) must leave dead slaves' enabled flag alone."""
    b = Broadcaster()
    s_alive, _ = _slave(1, enabled=False, dead=False)
    s_dead, _ = _slave(2, enabled=True, dead=True)
    b.add(s_alive)
    b.add(s_dead)

    b.set_all_enabled(True)

    assert s_alive.enabled is True
    # Dead slave's flag is irrelevant after ssh exited; we don't pretend
    # to bring it back to life by flipping it.
    assert s_dead.enabled is True

    b.set_all_enabled(False)
    assert s_alive.enabled is False
    # Same idea — set_all_enabled(False) must not "mark dead" or change
    # state on the already-dead slave; it just no-ops.
    assert s_dead.dead is True
