"""WezTerm launcher via ``wezterm cli spawn``."""
from __future__ import annotations

import subprocess

from csshx_latest.launcher import BlockHandle, Color


class WezTermLauncher:
    """Open each block as a new WezTerm pane via ``wezterm cli``."""

    name = "wezterm"

    @staticmethod
    def _run(args: list[str], capture: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(args, check=False, capture_output=capture, text=True)

    def start(self, total: int) -> None:
        """No-op: WezTerm balances panes automatically."""

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Spawn a new pane and stamp the tab title with ``host``."""
        out = self._run(["wezterm", "cli", "spawn", "--", *attach_cmd], capture=True)
        pane_id = (out.stdout or "").strip()
        if title and pane_id:
            self._run(["wezterm", "cli", "set-tab-title", "--pane-id", pane_id, title])
        return BlockHandle(backend=self.name, data={"pane_id": pane_id, "title": title})

    def close_block(self, handle: BlockHandle) -> None:
        """Kill the pane via ``wezterm cli kill-pane``."""
        pane_id = handle.data.get("pane_id")
        if not pane_id:
            return
        self._run(["wezterm", "cli", "kill-pane", "--pane-id", pane_id])

    def tile(self, handles: list[BlockHandle]) -> None:
        """No-op: WezTerm tiles split panes evenly when they are created."""

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """Rename the tab containing this pane."""
        pane_id = handle.data.get("pane_id")
        if not pane_id:
            return
        self._run(["wezterm", "cli", "set-tab-title", "--pane-id", pane_id, title])

    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """WezTerm has no CLI hook for per-pane background tint."""
