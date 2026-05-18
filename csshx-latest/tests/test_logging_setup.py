"""Tests for :mod:`csshx_latest.logging_setup`.

We verify that :func:`configure_logging` installs a stderr handler at
the requested level and is idempotent (repeated calls don't double the
output, which would be a footgun during tests that import the module
multiple times).
"""
from __future__ import annotations

import logging
import sys

from csshx_latest.logging_setup import configure_logging


def test_default_level_is_warning():
    configure_logging(debug=False)
    assert logging.getLogger().level == logging.WARNING


def test_debug_flag_sets_debug_level():
    configure_logging(debug=True)
    assert logging.getLogger().level == logging.DEBUG


def test_repeated_calls_do_not_accumulate_handlers():
    """Calling configure_logging twice must replace, not append, handlers."""
    configure_logging(debug=False)
    first_count = len(logging.getLogger().handlers)
    configure_logging(debug=True)
    second_count = len(logging.getLogger().handlers)
    assert first_count == second_count


def test_handler_writes_to_stderr():
    """The single root handler is a StreamHandler on sys.stderr."""
    configure_logging(debug=False)
    handlers = logging.getLogger().handlers
    assert any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
        for h in handlers
    )


def test_debug_logs_actually_render(capsys):
    """A getLogger(...) call after configure_logging emits to stderr at DEBUG.

    ``configure_logging`` replaces every root handler — including
    pytest's ``caplog`` plumbing — so we have to assert on the real
    stderr stream rather than via the caplog fixture. That's also the
    surface the user actually sees, so this is the right thing to pin.
    """
    configure_logging(debug=True)
    log = logging.getLogger("csshx_latest.test_marker")
    log.debug("hello-from-test")
    # Logging handlers are line-buffered; flush before reading.
    for h in logging.getLogger().handlers:
        h.flush()
    err = capsys.readouterr().err
    assert "hello-from-test" in err
    # Format check: includes level + logger name so users can grep.
    assert "DEBUG" in err
    assert "csshx_latest.test_marker" in err
