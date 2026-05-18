"""Tests for env-var based launcher auto-detection."""
from __future__ import annotations

import shutil

import pytest

from csshx_latest import launcher as launcher_mod
from csshx_latest.launcher import detect_launcher


@pytest.fixture
def clean_env(monkeypatch):
    """Strip any host env vars that might bias detection."""
    for k in ("TERM_PROGRAM", "KITTY_PID", "TMUX"):
        monkeypatch.delenv(k, raising=False)


def _which(found: dict[str, str]):
    return lambda c: found.get(c)


def test_explicit_choice_overrides_env(monkeypatch, clean_env):
    monkeypatch.setenv("TMUX", "/tmp/t,1,1")
    monkeypatch.setattr(shutil, "which", _which({"tmux": "/usr/bin/tmux"}))
    l = detect_launcher("manual")
    assert l.name == "manual"


def test_waveterm_when_term_program_and_wsh(monkeypatch, clean_env):
    monkeypatch.setenv("TERM_PROGRAM", "waveterm")
    monkeypatch.setattr(shutil, "which", _which({"wsh": "/usr/bin/wsh"}))
    assert detect_launcher().name == "waveterm"


def test_waveterm_skipped_when_wsh_missing(monkeypatch, clean_env):
    monkeypatch.setenv("TERM_PROGRAM", "waveterm")
    monkeypatch.setattr(shutil, "which", _which({}))
    assert detect_launcher().name == "manual"


def test_iterm2_term_program(monkeypatch, clean_env):
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.setattr(shutil, "which", _which({}))
    assert detect_launcher().name == "iterm2"


def test_apple_terminal_term_program(monkeypatch, clean_env):
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setattr(shutil, "which", _which({}))
    assert detect_launcher().name == "terminal"


def test_kitty_when_pid_set_and_kitty_on_path(monkeypatch, clean_env):
    monkeypatch.setenv("KITTY_PID", "123")
    monkeypatch.setattr(shutil, "which", _which({"kitty": "/usr/bin/kitty"}))
    assert detect_launcher().name == "kitty"


def test_wezterm_when_term_program_and_wezterm_on_path(monkeypatch, clean_env):
    monkeypatch.setenv("TERM_PROGRAM", "WezTerm")
    monkeypatch.setattr(shutil, "which", _which({"wezterm": "/usr/bin/wezterm"}))
    assert detect_launcher().name == "wezterm"


def test_tmux_only_when_tmux_env_set(monkeypatch, clean_env):
    monkeypatch.setenv("TMUX", "/tmp/tmux,123,4")
    monkeypatch.setattr(shutil, "which", _which({"tmux": "/usr/bin/tmux"}))
    assert detect_launcher().name == "tmux"


def test_falls_back_to_manual_when_nothing_recognized(monkeypatch, clean_env):
    monkeypatch.setattr(shutil, "which", _which({}))
    assert detect_launcher().name == "manual"


def test_does_not_pick_tmux_silently_without_tmux_env(monkeypatch, clean_env):
    """Even with tmux on PATH, $TMUX must be set — no surprise sessions."""
    monkeypatch.setattr(shutil, "which", _which({"tmux": "/usr/bin/tmux"}))
    assert detect_launcher().name == "manual"


def test_unknown_explicit_name_raises(monkeypatch, clean_env):
    with pytest.raises(ValueError):
        detect_launcher("nope")
