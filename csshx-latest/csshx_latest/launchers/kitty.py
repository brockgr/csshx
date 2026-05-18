"""Kitty launcher — uses ``kitty @`` remote control.

Requires ``allow_remote_control yes`` in ``kitty.conf`` (or the
equivalent ``--listen-on`` flag). The constructor surfaces a clear
error if the kitty CLI isn't on PATH; runtime failures from
``kitty @ launch`` are reported with kitty's own stderr included so
config issues are easy to diagnose.

v1.0 used ``--type=window``, which opened a fresh OS window per host.
With ten ssh targets that meant ten OS-level windows — useless. v1.1
defaults to ``--type=tab`` so all blocks live as tabs of the user's
current kitty OS window, exactly like every other launcher.
``--keep-focus`` keeps the master TUI focused so the user can keep
typing without juggling windows.
"""
from __future__ import annotations

import shutil
import subprocess

from csshx_latest.launcher import BlockHandle, Color

#: Hex backgrounds for the per-tab color tint. Same palette family
#: as the tmux launcher to keep the visual language consistent across
#: backends.
_TAB_BG: dict[Color, str] = {
    Color.ENABLED: "#0e3d0e",   # dark green
    Color.DISABLED: "#3a3a3a",  # neutral grey
    Color.DEAD: "#4d1414",      # dark red
}


class KittyLauncher:
    """Open each block as a new kitty tab. Tile via ``goto-layout grid``."""

    name = "kitty"

    def __init__(self) -> None:
        if not shutil.which("kitty"):
            raise RuntimeError(
                "kitty CLI not found on PATH. Install kitty and ensure "
                "'allow_remote_control yes' is set in kitty.conf."
            )

    @staticmethod
    def _run(args: list[str], capture: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(args, check=False, capture_output=capture, text=True)

    def start(self, total: int) -> None:
        """No-op: kitty's grid layout adapts as tabs are added."""

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Spawn a new kitty tab via ``kitty @ launch --type=tab``."""
        out = self._run(
            [
                "kitty",
                "@",
                "launch",
                "--type=tab",
                "--keep-focus",
                "--tab-title",
                title,
                "--title",
                title,
                *attach_cmd,
            ],
            capture=True,
        )
        if out.returncode != 0:
            raise RuntimeError(
                "kitty @ launch failed — make sure 'allow_remote_control yes' "
                f"is set in kitty.conf. stderr: {(out.stderr or '').strip()}"
            )
        # kitty prints the window id of the new tab's first window. We use
        # that for close-window; matching by id is more reliable than by
        # title (title can be customized after the fact).
        window_id = (out.stdout or "").strip()
        return BlockHandle(backend=self.name, data={"window_id": window_id, "title": title})

    def close_block(self, handle: BlockHandle) -> None:
        """Close the window via ``kitty @ close-window --match id:<wid>``."""
        wid = handle.data.get("window_id")
        if not wid:
            return
        self._run(["kitty", "@", "close-window", "--match", f"id:{wid}"])

    def tile(self, handles: list[BlockHandle]) -> None:
        """Switch the active tab to kitty's ``grid`` layout."""
        self._run(["kitty", "@", "goto-layout", "grid"])

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """Rename the window via ``kitty @ set-window-title``."""
        wid = handle.data.get("window_id")
        if not wid:
            return
        self._run(["kitty", "@", "set-window-title", "--match", f"id:{wid}", title])

    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """Tint the containing tab via ``kitty @ set-tab-color``.

        Requires kitty >= 0.20. A non-zero exit (e.g. older kitty)
        is silently ignored — the rest of the broadcast still works,
        the user just doesn't get the visual hint.
        """
        wid = handle.data.get("window_id")
        if not wid:
            return
        hex_bg = _TAB_BG.get(color)
        if not hex_bg:
            return
        self._run([
            "kitty", "@", "set-tab-color",
            "--match", f"window_id:{wid}",
            f"active_bg={hex_bg}",
            f"inactive_bg={hex_bg}",
        ])
