"""Tests for ``render_status`` — the one-line stderr footer.

pytest's ``capsys`` captures the real stderr write, so we lean on that
for assertions. To flip the "is stderr a tty?" branch in
``render_status`` we monkeypatch the function the TUI actually calls
(the bound ``sys.stderr.isatty`` method on the live stderr object).
"""
from __future__ import annotations

import sys

import pytest

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.slave import Slave
from csshx_latest.tui import render_status


def _bcast() -> Broadcaster:
    b = Broadcaster()
    b.add(Slave(index=1, host="h1", sock_path="/tmp/s1", token="t", pty_master=-1, pid=0, enabled=True))
    b.add(Slave(index=2, host="h2", sock_path="/tmp/s2", token="t", pty_master=-1, pid=0, enabled=False))
    b.add(Slave(index=3, host="h3", sock_path="/tmp/s3", token="t", pty_master=-1, pid=0, enabled=False, dead=True))
    return b


def _patch_isatty(monkeypatch, value: bool) -> None:
    """Force ``sys.stderr.isatty()`` to return ``value`` for the duration."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: value, raising=False)


def test_status_footer_includes_counts(capsys, monkeypatch):
    """Total / enabled / dead counts must all appear in the footer."""
    _patch_isatty(monkeypatch, False)
    render_status(_bcast())
    err = capsys.readouterr().err
    assert "hosts: 3" in err
    assert "enabled: 1" in err
    assert "dead: 1" in err


def test_status_footer_uses_ansi_when_stderr_is_tty(capsys, monkeypatch):
    """A tty stderr gets ANSI colors on the enabled / dead counters."""
    _patch_isatty(monkeypatch, True)
    render_status(_bcast())
    err = capsys.readouterr().err
    # Green ENABLED + red DEAD when both are non-zero.
    assert "\x1b[32m" in err  # green
    assert "\x1b[31m" in err  # red
    assert "\x1b[0m" in err   # reset


def test_status_footer_skips_ansi_when_not_a_tty(capsys, monkeypatch):
    """Plain pipe / log capture must never see ANSI escape codes."""
    _patch_isatty(monkeypatch, False)
    render_status(_bcast())
    err = capsys.readouterr().err
    assert "\x1b[" not in err


def test_status_footer_dims_zero_counters(capsys, monkeypatch):
    """Zero values render dim on a tty so the eye lands on non-zero state."""
    b = Broadcaster()
    b.add(Slave(index=1, host="h1", sock_path="/tmp/s1", token="t", pty_master=-1, pid=0, enabled=False))
    _patch_isatty(monkeypatch, True)
    render_status(b)
    err = capsys.readouterr().err
    assert "\x1b[2m" in err   # dim escape


def test_status_footer_renders_command_key_label(capsys, monkeypatch):
    """Non-default ``command_key`` should appear in the footer's menu hint."""
    _patch_isatty(monkeypatch, False)
    render_status(_bcast(), command_key=b"\x01")  # Ctrl-A
    err = capsys.readouterr().err
    assert "Ctrl-A" in err
