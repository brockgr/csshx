"""Tests for ``csshx_latest.action.run_action`` (one-shot broadcast).

Action mode replaces the TUI with a fan-out ssh-exec: every host runs
the same command concurrently and we print a per-host summary. The
external ``ssh`` binary is stubbed via ``asyncio.create_subprocess_exec``
so the tests are hermetic.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from csshx_latest.action import ActionResult, run_action


class _FakeProc:
    """Subset of ``asyncio.subprocess.Process`` used by ``run_action``."""

    def __init__(self, rc: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = rc
        self._stdout = stdout
        self._stderr = stderr
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr

    def kill(self) -> None:  # pragma: no cover - timeout-only path
        self.killed = True

    async def wait(self) -> int:  # pragma: no cover - timeout-only path
        return self.returncode


def _patch_subprocess(monkeypatch, recipe: dict[str, _FakeProc]) -> list[list[str]]:
    """Patch ``asyncio.create_subprocess_exec`` to return canned procs by host.

    Returns the captured argv list so tests can assert on the ssh args.
    """
    captured: list[list[str]] = []

    async def fake_create(*args: Any, **_kwargs: Any) -> _FakeProc:
        argv = list(args)
        captured.append(argv)
        # The host is the second-to-last argv element (last is the
        # remote command), and the recipe is keyed by host.
        host = argv[-2]
        if host not in recipe:
            raise AssertionError(f"unexpected host in argv: {host} ({argv})")
        return recipe[host]

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    return captured


def test_action_zero_hosts_returns_two(capsys):
    """No hosts at all → exit 2 with a stderr message."""
    rc = asyncio.run(run_action([], [], None, "uname -a"))
    assert rc == 2
    assert "no hosts" in capsys.readouterr().err


def test_action_empty_command_returns_two(capsys):
    """Whitespace-only command is rejected; exit 2."""
    rc = asyncio.run(run_action(["h1"], [], None, "   "))
    assert rc == 2
    assert "empty --action command" in capsys.readouterr().err


def test_action_all_hosts_succeed_returns_zero(monkeypatch, capsys):
    """Every host rc=0 → run_action returns 0 and the report mentions success."""
    _patch_subprocess(
        monkeypatch,
        {
            "h1": _FakeProc(0, stdout=b"ok1\n"),
            "h2": _FakeProc(0, stdout=b"ok2\n"),
        },
    )
    rc = asyncio.run(run_action(["h1", "h2"], [], None, "uname -a"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "ok1" in out and "ok2" in out
    assert "2 ok, 0 failed" in out


def test_action_one_host_fails_propagates_worst_rc(monkeypatch):
    """A single non-zero remote rc surfaces as the master's exit code."""
    _patch_subprocess(
        monkeypatch,
        {
            "ok": _FakeProc(0),
            "bad": _FakeProc(7, stderr=b"boom\n"),
        },
    )
    rc = asyncio.run(run_action(["ok", "bad"], [], None, "true"))
    assert rc == 7


def test_action_injects_batchmode_when_user_did_not(monkeypatch):
    """Action mode auto-adds BatchMode=yes so a host that would prompt fails fast."""
    captured = _patch_subprocess(monkeypatch, {"h": _FakeProc(0)})
    asyncio.run(run_action(["h"], [], None, "true"))
    flat = " ".join(captured[0])
    assert "BatchMode=yes" in flat


def test_action_respects_user_provided_batchmode(monkeypatch):
    """If the user already passed -o BatchMode=no, we don't double-set it."""
    captured = _patch_subprocess(monkeypatch, {"h": _FakeProc(0)})
    asyncio.run(
        run_action(
            ["h"],
            ["-o", "BatchMode=no"],
            None,
            "true",
        )
    )
    # The injected BatchMode=yes must NOT appear (only the user's no).
    bm_tokens = [a for a in captured[0] if "BatchMode" in a]
    assert bm_tokens == ["BatchMode=no"]


def test_action_passes_login_as_dash_l(monkeypatch):
    """``--login alice`` should become ``ssh -l alice <host> <cmd>``."""
    captured = _patch_subprocess(monkeypatch, {"h": _FakeProc(0)})
    asyncio.run(run_action(["h"], [], "alice", "id"))
    argv = captured[0]
    li = argv.index("-l")
    assert argv[li + 1] == "alice"


def test_action_result_dataclass_defaults():
    """ActionResult.timed_out defaults to False."""
    r = ActionResult(host="h", returncode=0, stdout="", stderr="")
    assert r.timed_out is False
