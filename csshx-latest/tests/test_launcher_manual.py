"""Tests for the Manual fallback launcher."""
from __future__ import annotations

from csshx_latest.launchers.manual import ManualLauncher


def test_manual_prints_numbered_attach_commands(capsys):
    l = ManualLauncher()
    h1 = l.open_block(["socat", "-", "UNIX-CONNECT:/tmp/a.sock"], "web01")
    h2 = l.open_block(["socat", "-", "UNIX-CONNECT:/tmp/b.sock"], "web02")
    out = capsys.readouterr().out

    assert "[1]" in out
    assert "[2]" in out
    assert "/tmp/a.sock" in out and "web01" in out
    assert "/tmp/b.sock" in out and "web02" in out
    assert h1.backend == "manual"
    assert h2.data["index"] == 2


def test_manual_quotes_paths_with_spaces(capsys):
    l = ManualLauncher()
    l.open_block(["socat", "-", "UNIX-CONNECT:/tmp/with space.sock"], "h")
    out = capsys.readouterr().out
    # shlex.quote either single-quotes or escapes the space.
    assert "'" in out or "\\ " in out


def test_manual_ops_are_noops_and_do_not_raise():
    l = ManualLauncher()
    h = l.open_block(["echo", "hi"], "h")
    l.tile([h])
    l.set_title(h, "renamed")
    l.close_block(h)
