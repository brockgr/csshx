"""Tests for ``--command-key`` parsing + the doubled-prefix echo path.

The parser accepts three forms (``^X``, ``0xNN``, single char); we
exercise each plus error cases. We also confirm that when the user
chooses a non-default prefix, the dispatch still recognizes a doubled
press of *that* prefix as a literal-send (so the orchestrated UX
matches the documented behavior).
"""
from __future__ import annotations

import asyncio

import pytest

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.slave import Slave
from csshx_latest.tui import _handle_command_byte, parse_command_key


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("^T", b"\x14"),
        ("^a", b"\x01"),  # case-insensitive
        ("0x14", b"\x14"),
        ("0X1B", b"\x1b"),
        ("a", b"a"),
        ("/", b"/"),
    ],
)
def test_parse_command_key_accepts_all_documented_forms(spec, expected):
    assert parse_command_key(spec) == expected


@pytest.mark.parametrize(
    "spec",
    [
        "",
        "^1",       # not a letter
        "^!",       # not a letter
        "0xZZ",     # invalid hex
        "0x100",    # outside byte range
        "abc",      # too long
    ],
)
def test_parse_command_key_rejects_invalid(spec):
    with pytest.raises(ValueError):
        parse_command_key(spec)


def _slave(idx: int) -> Slave:
    return Slave(
        index=idx, host=f"h{idx}", sock_path=f"/tmp/s{idx}",
        token="t", pty_master=-1, pid=0,
    )


def test_doubled_custom_prefix_echoes_that_prefix_byte():
    """When the user picks Ctrl-A, two Ctrl-A presses must echo a Ctrl-A."""
    bcast = Broadcaster()
    bcast.add(_slave(1))
    custom = b"\x01"  # Ctrl-A

    extra = asyncio.run(
        _handle_command_byte(bcast, custom[0], asyncio.Event(), command_key=custom)
    )

    assert extra == custom


def test_doubled_default_prefix_still_echoes_ctrl_t():
    """With no override the default Ctrl-T behavior is preserved."""
    bcast = Broadcaster()
    bcast.add(_slave(1))

    extra = asyncio.run(
        _handle_command_byte(bcast, 0x14, asyncio.Event())
    )

    assert extra == b"\x14"


def test_unknown_printable_echoes_back_through_dispatch():
    """``Ctrl-T x`` cancels command mode and broadcasts the ``x``.

    This is the original csshX behavior: a stray letter never gets
    silently swallowed.
    """
    bcast = Broadcaster()
    bcast.add(_slave(1))

    extra = asyncio.run(_handle_command_byte(bcast, ord("x"), asyncio.Event()))

    assert extra == b"x"


def test_unknown_control_byte_cancels_without_echo():
    """Esc / Ctrl-C inside command mode cancel silently."""
    bcast = Broadcaster()
    bcast.add(_slave(1))

    extra = asyncio.run(_handle_command_byte(bcast, 0x03, asyncio.Event()))

    assert extra == b""
