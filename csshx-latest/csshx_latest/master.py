"""Backward-compatibility shim.

Author: Aditya Kapadia.

The master module used to bundle the broadcaster, the TUI loop, the
attach-command builder, and the top-level orchestration in one file.
Those have since been split across :mod:`csshx_latest.broadcaster`,
:mod:`csshx_latest.tui`, and :mod:`csshx_latest.orchestrator` so each
piece can be unit-tested in isolation. Anything that used to import
from ``csshx_latest.master`` keeps working -- every public name is
re-exported here.
"""
from __future__ import annotations

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.orchestrator import (
    attach_command,
    make_socket_dir,
    run_master,
)
from csshx_latest.tui import render_status, tui_loop

__all__ = [
    "Broadcaster",
    "attach_command",
    "make_socket_dir",
    "render_status",
    "run_master",
    "tui_loop",
]
