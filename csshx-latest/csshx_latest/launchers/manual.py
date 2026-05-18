"""Universal fallback launcher: prints attach commands for the user to paste.

Used when no specific terminal backend was recognized. Prints a
numbered list of attach commands to stdout — the user copies each one
into a tab/pane/window of any terminal they like.
"""
from __future__ import annotations

import shlex
import sys

from csshx_latest.launcher import BlockHandle, Color


class ManualLauncher:
    """Print attach commands; tile/title/close are no-ops."""

    name = "manual"

    def __init__(self) -> None:
        self._counter = 0

    def start(self, total: int) -> None:
        """No-op: the manual launcher doesn't need a host-count hint."""

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Print ``[N] <quoted attach command>   # <title>`` to stdout."""
        self._counter += 1
        n = self._counter
        cmd_str = " ".join(shlex.quote(a) for a in attach_cmd)
        sys.stdout.write(f"[{n}] {cmd_str}   # {title}\n")
        sys.stdout.flush()
        return BlockHandle(backend=self.name, data={"index": n, "title": title})

    def close_block(self, handle: BlockHandle) -> None:
        """No-op: the user runs the attach command themselves."""

    def tile(self, handles: list[BlockHandle]) -> None:
        """No-op: nothing to tile when blocks are user-driven."""

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """No-op: titles are whatever the user's terminal already shows."""

    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """No-op: the manual launcher has no UI surface to paint."""
