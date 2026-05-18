"""Tests for the per-slave focus toggle (Ctrl-T <digit>) in tui.py."""
from __future__ import annotations

import asyncio

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.slave import Slave
from csshx_latest.tui import _handle_command_byte


def _make_slave(index: int, *, enabled: bool = True, dead: bool = False) -> Slave:
    return Slave(
        index=index,
        host=f"h{index}",
        sock_path=f"/tmp/s{index}",
        token="t",
        pty_master=-1,
        pid=0,
        enabled=enabled,
        dead=dead,
    )


def _bcast_with(*slaves: Slave) -> Broadcaster:
    b = Broadcaster()
    for s in slaves:
        b.add(s)
    return b


def test_digit_toggles_only_that_slave():
    s1 = _make_slave(1, enabled=True)
    s2 = _make_slave(2, enabled=True)
    s3 = _make_slave(3, enabled=True)
    b = _bcast_with(s1, s2, s3)

    asyncio.run(_handle_command_byte(b, ord("2"), asyncio.Event()))

    assert s1.enabled is True
    assert s2.enabled is False
    assert s3.enabled is True


def test_digit_for_missing_index_is_no_op():
    s1 = _make_slave(1, enabled=True)
    b = _bcast_with(s1)

    extra = asyncio.run(_handle_command_byte(b, ord("9"), asyncio.Event()))

    assert extra == b""
    assert s1.enabled is True


def test_digit_toggles_back_on_second_press():
    s1 = _make_slave(1, enabled=True)
    b = _bcast_with(s1)

    asyncio.run(_handle_command_byte(b, ord("1"), asyncio.Event()))
    assert s1.enabled is False
    asyncio.run(_handle_command_byte(b, ord("1"), asyncio.Event()))
    assert s1.enabled is True


def test_broadcaster_toggle_returns_new_state():
    s1 = _make_slave(1, enabled=True)
    b = _bcast_with(s1)
    assert b.toggle(1) is False
    assert b.toggle(1) is True
