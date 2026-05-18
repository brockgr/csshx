"""Tmux launcher -- spawn each block as a pane in the active session.

Author: Aditya Kapadia.

Detects the ambient ``$TMUX`` session via ``detect_launcher``; the
launcher itself just shells out to ``tmux``.

Window vs. pane policy
----------------------

With more than :data:`PANE_THRESHOLD` hosts, splitting the current
pane over and over leaves each ssh session squeezed into a vertical
ribbon that's unusable. Above the threshold, the first block instead
opens a fresh ``tmux new-window`` (still attached to the same session),
and subsequent blocks split inside that dedicated window. This keeps
the user's original window untouched, gives every host enough columns
to matter, and survives the eventual ``select-layout tiled``.

The host count comes from :meth:`start`, called by the orchestrator
before any block opens.
"""
from __future__ import annotations

import shlex
import subprocess
from typing import Optional

from csshx_latest.launcher import BlockHandle, Color

#: Above this many hosts, open a dedicated tmux window rather than
#: splitting the current pane. 4 is the largest count where a 2x2 split
#: stays readable on a typical 1080p / 1440p display.
PANE_THRESHOLD = 4

#: 256-color codes for per-pane border / background paint.
#: Mirrors the original csshX's "subtle dark tint" palette: dark green
#: for enabled, neutral grey for disabled, dark red for dead. These
#: stay readable against any reasonable terminal theme.
_COLOR_BG: dict[Color, str] = {
    Color.ENABLED: "colour22",   # dark green
    Color.DISABLED: "colour237", # dark grey
    Color.DEAD: "colour52",      # dark red
}


class TmuxLauncher:
    """Open each block as a tmux pane; isolate large clusters in a new window."""

    name = "tmux"

    def __init__(self, target: Optional[str] = None, pane_threshold: int = PANE_THRESHOLD) -> None:
        self._target = target
        self._pane_threshold = pane_threshold
        self._window_target: Optional[str] = None
        self._opened = 0
        self._total = 0

    @staticmethod
    def _run(args: list[str], capture: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(args, check=False, capture_output=capture, text=True)

    def start(self, total: int) -> None:
        """Record the total host count so :meth:`open_block` can route the first split."""
        self._total = total

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Run ``tmux split-window`` (or ``new-window`` for the first of many)."""
        cmd_str = " ".join(shlex.quote(a) for a in attach_cmd)

        if (
            self._opened == 0
            and self._total > self._pane_threshold
            and not self._target
        ):
            new_cmd = ["tmux", "new-window", "-P", "-F", "#{pane_id}", "-n", "csshx"]
            new_cmd.append(cmd_str)
            out = self._run(new_cmd, capture=True)
            pane_id = (out.stdout or "").strip()
            self._window_target = pane_id or None
        else:
            split_cmd = ["tmux", "split-window", "-P", "-F", "#{pane_id}"]
            anchor = self._target or self._window_target
            if anchor:
                split_cmd += ["-t", anchor]
            split_cmd.append(cmd_str)
            out = self._run(split_cmd, capture=True)
            pane_id = (out.stdout or "").strip()

        if title and pane_id:
            self._run(["tmux", "select-pane", "-t", pane_id, "-T", title])

        if pane_id:
            self._run(["tmux", "select-layout", "-t", pane_id, "tiled"])

        self._opened += 1
        return BlockHandle(backend=self.name, data={"pane_id": pane_id, "title": title})

    def close_block(self, handle: BlockHandle) -> None:
        """Kill the pane opened for this block. Silent if already gone."""
        pane_id = handle.data.get("pane_id")
        if not pane_id:
            return
        self._run(["tmux", "kill-pane", "-t", pane_id])

    def tile(self, handles: list[BlockHandle]) -> None:
        """Apply ``tiled`` layout to whichever window holds the panes."""
        if not handles:
            return
        first = handles[0].data.get("pane_id")
        if not first:
            return
        self._run(["tmux", "select-layout", "-t", first, "tiled"])

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """Rename a pane via ``tmux select-pane -T``."""
        pane_id = handle.data.get("pane_id")
        if not pane_id:
            return
        self._run(["tmux", "select-pane", "-t", pane_id, "-T", title])

    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """Tint the pane border + status to reflect broadcast state.

        Uses ``tmux select-pane -P bg=<colour>``, which paints the pane
        body's "padding" / border tint without touching the remote
        shell's ANSI state. The original csshX painted the AppKit
        window title bar; we do the closest tmux equivalent.
        """
        pane_id = handle.data.get("pane_id")
        if not pane_id:
            return
        bg = _COLOR_BG.get(color)
        if not bg:
            return
        self._run(["tmux", "select-pane", "-t", pane_id, "-P", f"bg={bg}"])
