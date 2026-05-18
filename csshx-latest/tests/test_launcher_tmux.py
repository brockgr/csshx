"""Tests for the Tmux launcher (subprocess.run mocked)."""
from __future__ import annotations

import subprocess

import pytest

from csshx_latest.launchers import tmux as tmux_mod


@pytest.fixture
def fake_run(monkeypatch):
    """Replace ``subprocess.run`` with a recorder that mimics tmux output."""
    calls: list[list[str]] = []

    def runner(args, check=False, capture_output=False, text=False):
        calls.append(list(args))
        if "split-window" in args or "new-window" in args:
            return subprocess.CompletedProcess(args, 0, stdout="%42\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux_mod.subprocess, "run", runner)
    return calls


@pytest.fixture(autouse=True)
def _clear_host_count(monkeypatch):
    """The launcher no longer reads CSSHX_HOST_COUNT; ensure it's unset."""
    monkeypatch.delenv("CSSHX_HOST_COUNT", raising=False)


def test_open_block_runs_split_window_and_titles(fake_run):
    l = tmux_mod.TmuxLauncher()
    h = l.open_block(["socat", "-", "UNIX-CONNECT:/tmp/a"], "web01")
    assert h.backend == "tmux"
    assert h.data["pane_id"] == "%42"

    assert fake_run[0][:2] == ["tmux", "split-window"]
    assert "-P" in fake_run[0]
    title_call = next(c for c in fake_run if "select-pane" in c)
    assert "web01" in title_call


def test_tile_calls_select_layout_tiled(fake_run):
    l = tmux_mod.TmuxLauncher()
    h = l.open_block(["echo"], "h")
    fake_run.clear()
    l.tile([h])
    assert any("select-layout" in c and "tiled" in c for c in fake_run)


def test_close_block_kills_pane(fake_run):
    l = tmux_mod.TmuxLauncher()
    h = l.open_block(["echo"], "h")
    fake_run.clear()
    l.close_block(h)
    assert any("kill-pane" in c for c in fake_run)


def test_tile_with_no_handles_is_silent(fake_run):
    l = tmux_mod.TmuxLauncher()
    fake_run.clear()
    l.tile([])
    assert fake_run == []


def test_set_title_runs_select_pane_T(fake_run):
    l = tmux_mod.TmuxLauncher()
    h = l.open_block(["echo"], "h")
    fake_run.clear()
    l.set_title(h, "renamed")
    assert any("select-pane" in c and "renamed" in c for c in fake_run)


def test_first_open_uses_new_window_when_many_hosts(monkeypatch, fake_run):
    """With >PANE_THRESHOLD hosts, the first block carves out a new window."""
    l = tmux_mod.TmuxLauncher()
    l.start(8)
    l.open_block(["echo", "first"], "h1")

    # First tmux call must be ``new-window`` (not ``split-window``).
    assert fake_run[0][:2] == ["tmux", "new-window"]
    # And it must capture the pane id so subsequent splits anchor to it.
    assert "-P" in fake_run[0]
    assert any(a.startswith("-n") or a == "-n" for a in fake_run[0])


def test_second_open_anchors_split_to_new_window(monkeypatch, fake_run):
    """After new-window, subsequent splits must target the new window's pane id."""
    l = tmux_mod.TmuxLauncher()
    l.start(8)
    l.open_block(["echo", "first"], "h1")
    fake_run.clear()
    l.open_block(["echo", "second"], "h2")

    split_calls = [c for c in fake_run if "split-window" in c]
    assert split_calls, "second open should split inside the new window"
    # The split must be anchored to the new window's pane id (%42 from fake).
    split = split_calls[0]
    assert "-t" in split
    t_idx = split.index("-t")
    assert split[t_idx + 1] == "%42"


def test_small_cluster_uses_split_from_the_start(monkeypatch, fake_run):
    """At or below PANE_THRESHOLD, never call new-window."""
    l = tmux_mod.TmuxLauncher()
    l.start(3)
    l.open_block(["echo"], "h1")
    l.open_block(["echo"], "h2")

    assert all("new-window" not in c for c in fake_run), (
        "small clusters should never create a dedicated window"
    )
    assert any("split-window" in c for c in fake_run)


def test_explicit_target_disables_new_window_heuristic(monkeypatch, fake_run):
    """If the caller passed an explicit ``target``, never auto-new-window."""
    l = tmux_mod.TmuxLauncher(target="my-session:0")
    l.start(8)
    l.open_block(["echo"], "h1")

    assert all("new-window" not in c for c in fake_run)
    assert fake_run[0][:2] == ["tmux", "split-window"]
    # And the explicit target must be honored.
    assert "-t" in fake_run[0]
    t_idx = fake_run[0].index("-t")
    assert fake_run[0][t_idx + 1] == "my-session:0"
