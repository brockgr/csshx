"""Shared pytest fixtures.

* ``short_socket_dir`` — pytest's ``tmp_path`` lives under
  ``/private/var/folders/.../pytest-of-USER/pytest-N/test_name0/``,
  whose path length routinely blows past macOS's 104-byte ``sun_path``
  limit and crashes ``bind()`` on AF_UNIX sockets.
  ``tempfile.mkdtemp(prefix="csshx-")`` gives us a path under ``/tmp``
  (or wherever ``$TMPDIR`` points) that's short enough to leave room
  for a filename below it.

* ``harmless_pid`` — ``shutdown_slave`` calls ``os.kill(pid, SIGTERM)``,
  and ``os.kill(0, ...)`` on POSIX signals every process in the
  caller's process group — i.e. pytest itself. Bridge tests must never
  pass ``pid=0`` to a Slave. This fixture spawns a short-lived
  ``time.sleep`` subprocess so the test gets a real, isolated PID, and
  reaps it on teardown.

* ``stdio_devnull`` — ``attach.main()`` calls ``sys.stdin.fileno()`` and
  ``sys.stdout.fileno()`` to drive its ``select()`` loop. pytest's
  default ``capsys`` capture replaces those with StringIO mocks that
  don't expose real fds, so calls to ``.fileno()`` raise. This fixture
  swaps in real file objects opened on ``os.devnull`` before the test
  body runs and closes them on teardown. ``sys.stderr`` is left alone
  so ``capsys.readouterr().err`` keeps working for assertions.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

import pytest


@pytest.fixture
def short_socket_dir():
    """Yield a tempdir whose paths fit in macOS's 104-byte ``sun_path``."""
    d = tempfile.mkdtemp(prefix="csshx-")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def harmless_pid():
    """Yield the PID of a short-lived sleep subprocess; reap on teardown."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield proc.pid
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:  # pragma: no cover
            pass


@pytest.fixture
def stdio_devnull(monkeypatch, capsys):
    """Replace ``sys.stdin``/``sys.stdout`` with real fds on ``os.devnull``.

    Required by tests that call ``attach.main()`` because pytest's
    ``capsys`` capture leaves ``sys.stdin``/``sys.stdout`` without a usable
    ``.fileno()``. ``sys.stderr`` is left untouched so ``capsys`` still
    captures the error messages we assert on.

    The ``capsys`` dependency forces pytest to set up its capture wrappers
    *before* this fixture monkey-patches sys.stdin/sys.stdout — otherwise
    capsys overrides our devnull file objects and ``.fileno()`` blows up.
    """
    fin = open(os.devnull, "rb")
    fout = open(os.devnull, "wb")
    monkeypatch.setattr("sys.stdin", fin)
    monkeypatch.setattr("sys.stdout", fout)
    try:
        yield
    finally:
        fin.close()
        fout.close()
