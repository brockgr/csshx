"""Tests for the Ctrl-T command-mode dispatch in :mod:`csshx_latest.tui`.

We poke ``_handle_command_byte`` directly rather than wiring up a full
``tui_loop`` because the loop needs a real tty for raw mode. The
dispatch function is the interesting piece — the byte → effect mapping
is the contract we want to lock down.
"""
from __future__ import annotations

import asyncio

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.slave import Slave
from csshx_latest.tui import KEY_COMMAND_PREFIX, _handle_command_byte


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


def test_b_toggles_all_alive_slaves_off_when_any_enabled():
    """``b`` with mixed state turns every alive slave OFF."""
    s1 = _make_slave(1, enabled=True)
    s2 = _make_slave(2, enabled=False)
    s3 = _make_slave(3, enabled=True, dead=True)
    b = _bcast_with(s1, s2, s3)
    quit_ev = asyncio.Event()

    extra = asyncio.run(_handle_command_byte(b, ord("b"), quit_ev))

    assert extra == b""
    assert s1.enabled is False
    assert s2.enabled is False
    # Dead slaves are excluded from set_all_enabled — their flag is
    # meaningless and changing it would mask the dead-count UI.
    assert s3.enabled is True


def test_b_toggles_all_on_when_none_enabled():
    """``b`` from all-off → every alive slave ends ON."""
    s1 = _make_slave(1, enabled=False)
    s2 = _make_slave(2, enabled=False)
    b = _bcast_with(s1, s2)

    asyncio.run(_handle_command_byte(b, ord("b"), asyncio.Event()))

    assert s1.enabled is True
    assert s2.enabled is True


def test_q_sets_quit_event():
    b = _bcast_with(_make_slave(1))
    quit_ev = asyncio.Event()

    asyncio.run(_handle_command_byte(b, ord("q"), quit_ev))

    assert quit_ev.is_set()


def test_doubled_prefix_returns_literal_prefix_byte():
    """Ctrl-T then Ctrl-T → broadcast a single literal Ctrl-T."""
    b = _bcast_with(_make_slave(1))
    quit_ev = asyncio.Event()

    extra = asyncio.run(
        _handle_command_byte(b, KEY_COMMAND_PREFIX[0], quit_ev)
    )

    assert extra == KEY_COMMAND_PREFIX
    assert not quit_ev.is_set()


def test_unknown_printable_byte_cancels_and_echoes():
    """Unmapped *printable* byte cancels command mode and echoes the byte.

    Matches the original csshX behavior: a typo'd letter after Ctrl-T
    isn't silently swallowed — command mode unwinds and the letter is
    broadcast to the slaves.
    """
    s1 = _make_slave(1, enabled=True)
    b = _bcast_with(s1)
    quit_ev = asyncio.Event()

    extra = asyncio.run(_handle_command_byte(b, ord("z"), quit_ev))

    assert extra == b"z"
    assert s1.enabled is True
    assert not quit_ev.is_set()


def test_unknown_control_byte_cancels_silently():
    """A non-printable byte (Esc, Ctrl-C) cancels with no echo."""
    s1 = _make_slave(1, enabled=True)
    b = _bcast_with(s1)
    quit_ev = asyncio.Event()

    extra = asyncio.run(_handle_command_byte(b, 0x1B, quit_ev))  # Esc

    assert extra == b""
    assert s1.enabled is True
    assert not quit_ev.is_set()


def test_help_byte_does_not_modify_state():
    """``?`` should print help but leave slaves and quit_event untouched."""
    s1 = _make_slave(1, enabled=True)
    b = _bcast_with(s1)
    quit_ev = asyncio.Event()

    asyncio.run(_handle_command_byte(b, ord("?"), quit_ev))

    assert s1.enabled is True
    assert not quit_ev.is_set()


def test_l_byte_does_not_modify_state():
    """``l`` lists slaves — must not toggle enabled/dead/quit."""
    s1 = _make_slave(1, enabled=True)
    s2 = _make_slave(2, enabled=False, dead=True)
    b = _bcast_with(s1, s2)
    quit_ev = asyncio.Event()

    asyncio.run(_handle_command_byte(b, ord("l"), quit_ev))

    assert s1.enabled is True
    assert s2.enabled is False
    assert s2.dead is True
    assert not quit_ev.is_set()
