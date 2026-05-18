"""Tests for the Kitty launcher (subprocess.run and shutil.which mocked).

Kitty calls go through ``kitty @ launch / @ close-window / @
goto-layout / @ set-window-title``. We verify the argv shape rather
than ``kitty``'s actual behavior — the launcher's contract is "emit
the right command line", and kitty's remote-control protocol is
covered by its own test suite upstream.
"""
from __future__ import annotations

import subprocess

import pytest

from csshx_latest.launchers import kitty as kitty_mod


@pytest.fixture
def fake_kitty(monkeypatch):
    """Pretend ``kitty`` is on PATH; record every subprocess.run argv."""
    monkeypatch.setattr(kitty_mod.shutil, "which", lambda _name: "/usr/local/bin/kitty")
    calls: list[list[str]] = []

    def runner(args, check=False, capture_output=False, text=False):
        calls.append(list(args))
        # ``kitty @ launch`` prints the new window id on stdout.
        if args[:3] == ["kitty", "@", "launch"]:
            return subprocess.CompletedProcess(args, 0, stdout="17\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(kitty_mod.subprocess, "run", runner)
    return calls


def test_constructor_raises_if_kitty_missing(monkeypatch):
    """Operator-visible failure when ``kitty`` isn't on PATH."""
    monkeypatch.setattr(kitty_mod.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="kitty CLI not found"):
        kitty_mod.KittyLauncher()


def test_open_block_uses_type_tab_and_captures_window_id(fake_kitty):
    """v1.1 default is ``--type=tab`` (NOT ``--type=window``)."""
    l = kitty_mod.KittyLauncher()
    h = l.open_block(["socat", "-", "UNIX-CONNECT:/tmp/a"], "web01")

    launch = fake_kitty[0]
    assert launch[:3] == ["kitty", "@", "launch"]
    assert "--type=tab" in launch
    # ``--type=window`` would open a new OS window per host, which
    # was the v1.0 footgun we fixed — pin it explicitly.
    assert "--type=window" not in launch
    # ``--keep-focus`` keeps the master TUI focused so the user can keep typing.
    assert "--keep-focus" in launch
    # Both ``--tab-title`` and ``--title`` carry the title so kitty
    # tabbar AND window list show the host.
    assert "--tab-title" in launch and "web01" in launch
    assert h.data["window_id"] == "17"
    assert h.data["title"] == "web01"


def test_open_block_raises_when_kitty_returncode_nonzero(monkeypatch):
    """A failed ``kitty @ launch`` surfaces a clear remote-control error."""
    monkeypatch.setattr(kitty_mod.shutil, "which", lambda _name: "/usr/local/bin/kitty")

    def runner(args, check=False, capture_output=False, text=False):
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="kitty: not allowed\n"
        )

    monkeypatch.setattr(kitty_mod.subprocess, "run", runner)
    l = kitty_mod.KittyLauncher()
    with pytest.raises(RuntimeError, match="allow_remote_control"):
        l.open_block(["echo"], "h")


def test_tile_invokes_goto_layout_grid(fake_kitty):
    l = kitty_mod.KittyLauncher()
    h = l.open_block(["echo"], "h")
    fake_kitty.clear()

    l.tile([h])

    assert fake_kitty == [["kitty", "@", "goto-layout", "grid"]]


def test_close_block_matches_by_window_id(fake_kitty):
    """We match by window id, not title — IDs survive renames."""
    l = kitty_mod.KittyLauncher()
    h = l.open_block(["echo"], "h")
    fake_kitty.clear()

    l.close_block(h)

    assert fake_kitty[0][:3] == ["kitty", "@", "close-window"]
    assert "--match" in fake_kitty[0]
    assert "id:17" in fake_kitty[0]


def test_close_block_noop_when_window_id_missing(monkeypatch, fake_kitty):
    """If ``open_block`` couldn't capture a window id, close silently no-ops."""
    l = kitty_mod.KittyLauncher()
    from csshx_latest.launcher import BlockHandle
    bogus = BlockHandle(backend="kitty", data={"window_id": "", "title": "x"})
    fake_kitty.clear()

    l.close_block(bogus)

    assert fake_kitty == []


def test_set_title_uses_set_window_title(fake_kitty):
    l = kitty_mod.KittyLauncher()
    h = l.open_block(["echo"], "h")
    fake_kitty.clear()

    l.set_title(h, "renamed")

    assert fake_kitty[0][:3] == ["kitty", "@", "set-window-title"]
    assert "id:17" in fake_kitty[0]
    assert "renamed" in fake_kitty[0]
