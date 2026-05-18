"""Project-wide logging configuration.

Logging is opt-in (``--debug`` on the CLI). When enabled, every module
that does ``log = logging.getLogger(__name__)`` writes structured lines
to stderr with timestamps and module names so it's clear where a
message originates. The default is WARNING — quiet enough to keep the
TUI clean, loud enough to surface real problems.
"""
from __future__ import annotations

import logging
import sys


def configure_logging(debug: bool = False) -> None:
    """Install a stderr handler with a sensible format.

    Safe to call more than once; the root handler is replaced rather
    than appended so repeated calls during tests don't multiply output.
    """
    level = logging.DEBUG if debug else logging.WARNING
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
