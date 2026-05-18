"""Launcher Protocol and environment-based auto-detection.

Author: Aditya Kapadia.

A Launcher knows how to ask one specific terminal application (Wave,
iTerm2, tmux, ...) to open a new visible block running an arbitrary
command, and optionally to tile/title the resulting blocks.

Concrete launchers live under :mod:`csshx_latest.launchers`. They are
imported lazily in :func:`_by_name` so that selecting one backend
doesn't pay the import cost of the others.

Lifecycle
---------

The orchestrator calls launcher methods in this order::

    start(total)              # once, before any blocks open
    open_block(...)           # once per host
    tile(handles)             # after every open_block AND on resize
    close_block(handle)       # once per host, on shutdown

``start`` lets a launcher know up-front how many blocks it will be
asked to open; that's how the tmux launcher decides between
splitting the current pane and carving out a new window. The default
implementation is a no-op.
"""
from __future__ import annotations

import enum
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


class Color(enum.Enum):
    """Per-block state colors — mirrors the original csshX color taxonomy.

    The Perl csshX used four states (``selected``, ``disabled``,
    ``master``, ``setbounds``); for a TUI without a separate master
    window we only need three:

    * :attr:`ENABLED`  — broadcast is on (csshX ``selected``).
    * :attr:`DISABLED` — broadcast is off but the host is alive
      (csshX ``disabled``).
    * :attr:`DEAD`     — ssh has exited.

    Concrete launchers translate these into their native paint
    primitives (tmux ``select-pane -P``, wsh ``setbg``, kitty
    ``set-tab-color``, etc.). Launchers without a paint API treat
    every value as a no-op.
    """

    ENABLED = "enabled"
    DISABLED = "disabled"
    DEAD = "dead"


@dataclass
class BlockHandle:
    """Opaque handle returned by :meth:`Launcher.open_block`.

    ``data`` is a per-backend bag of identifiers (pane id, window id,
    block id, ...) that the same backend uses to later close, retitle,
    or tile the block.
    """

    backend: str
    data: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Launcher(Protocol):
    """Pluggable terminal-backend interface."""

    name: str

    def start(self, total: int) -> None:
        """Notify the launcher how many blocks will be opened in total."""
        ...

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Open a visible block and run ``attach_cmd`` inside it."""
        ...

    def close_block(self, handle: BlockHandle) -> None:
        """Close a block previously returned by :meth:`open_block`."""
        ...

    def tile(self, handles: list[BlockHandle]) -> None:
        """Arrange the given blocks in a tiled layout. May be a no-op."""
        ...

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """Rename a block. May be a no-op."""
        ...

    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """Paint a block to reflect its broadcast state. May be a no-op."""
        ...


# (module, class) pairs keyed by the public launcher name. The keys of
# this dict are the single source of truth for ``--launcher`` choices --
# ``__main__.py`` reads them so the CLI never drifts out of sync with
# what's actually available.
_LAUNCHERS: dict[str, tuple[str, str]] = {
    "waveterm": ("csshx_latest.launchers.waveterm", "WaveTermLauncher"),
    "tmux": ("csshx_latest.launchers.tmux", "TmuxLauncher"),
    "iterm2": ("csshx_latest.launchers.iterm2", "ITerm2Launcher"),
    "terminal": ("csshx_latest.launchers.apple_terminal", "AppleTerminalLauncher"),
    "kitty": ("csshx_latest.launchers.kitty", "KittyLauncher"),
    "wezterm": ("csshx_latest.launchers.wezterm", "WezTermLauncher"),
    "manual": ("csshx_latest.launchers.manual", "ManualLauncher"),
}


def available_launcher_names() -> list[str]:
    """Return the sorted list of valid ``--launcher`` choices, plus ``auto``."""
    return ["auto", *sorted(_LAUNCHERS)]


def _by_name(name: str) -> Launcher:
    """Instantiate the launcher class registered under ``name``."""
    if name not in _LAUNCHERS:
        raise ValueError(f"unknown launcher: {name!r}")
    mod_name, cls_name = _LAUNCHERS[name]
    import importlib
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)()


def detect_launcher(name: Optional[str] = None) -> Launcher:
    """Return a Launcher instance.

    If ``name`` is given (and not ``"auto"``), use that launcher
    explicitly. Otherwise inspect environment variables in priority
    order:

    1. ``$TMUX`` -- tmux is checked *first* because a tmux session
       running inside iTerm or Kitty leaves both ``TMUX`` *and*
       ``TERM_PROGRAM``/``KITTY_PID`` set; the user's foreground
       multiplexer is tmux, which is what should host the panes.
    2. WaveTerm (``TERM_PROGRAM=waveterm`` + ``wsh`` on PATH).
    3. iTerm2 (``TERM_PROGRAM=iTerm.app``).
    4. Apple Terminal.app (``TERM_PROGRAM=Apple_Terminal``).
    5. Kitty (``KITTY_PID`` set + ``kitty`` on PATH).
    6. WezTerm (``TERM_PROGRAM=WezTerm`` + ``wezterm`` on PATH).

    Falls back to the Manual launcher if nothing is recognized -- never
    silently picks tmux without ``$TMUX``, never auto-spawns a new
    multiplexer.
    """
    if name and name != "auto":
        return _by_name(name)

    if os.environ.get("TMUX") and shutil.which("tmux"):
        return _by_name("tmux")

    term_program = os.environ.get("TERM_PROGRAM", "")

    if term_program == "waveterm" and shutil.which("wsh"):
        return _by_name("waveterm")
    if term_program == "iTerm.app":
        return _by_name("iterm2")
    if term_program == "Apple_Terminal":
        return _by_name("terminal")
    if os.environ.get("KITTY_PID") and shutil.which("kitty"):
        return _by_name("kitty")
    if term_program == "WezTerm" and shutil.which("wezterm"):
        return _by_name("wezterm")
    return _by_name("manual")
