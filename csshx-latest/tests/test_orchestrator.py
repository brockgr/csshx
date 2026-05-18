"""Tests for orchestrator helpers: preflight, kill-reap, ssh-arg injection."""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time

import pytest

from csshx_latest import orchestrator


def test_inject_strict_host_key_when_user_did_not_set_it():
    out = orchestrator.maybe_inject_strict_host_key_opts([])
    assert out == ["-o", "StrictHostKeyChecking=accept-new"]


def test_inject_strict_host_key_skips_when_user_set_no():
    """If the user passes any -o ... StrictHostKeyChecking value, leave it alone."""
    user = ["-o", "StrictHostKeyChecking=no", "-p", "2222"]
    out = orchestrator.maybe_inject_strict_host_key_opts(user)
    assert out == user


def test_inject_strict_host_key_skips_when_user_set_yes():
    user = ["-oStrictHostKeyChecking=yes"]
    out = orchestrator.maybe_inject_strict_host_key_opts(user)
    assert out == user


def test_preflight_keeps_reachable_drops_unreachable(monkeypatch):
    async def fake_probe(host, port=22, timeout=1.0):
        return host in {"alive1", "alive2"}

    monkeypatch.setattr(orchestrator, "_probe_host", fake_probe)
    out = asyncio.new_event_loop().run_until_complete(
        orchestrator.preflight_hosts(["alive1", "dead", "alive2"], strict=False)
    )
    assert out == ["alive1", "alive2"]


def test_preflight_strict_raises_on_any_dead(monkeypatch):
    async def fake_probe(host, port=22, timeout=1.0):
        return host != "dead"

    monkeypatch.setattr(orchestrator, "_probe_host", fake_probe)
    with pytest.raises(RuntimeError) as exc:
        asyncio.new_event_loop().run_until_complete(
            orchestrator.preflight_hosts(["alive", "dead"], strict=True)
        )
    assert "dead" in str(exc.value)


def test_preflight_handles_user_at_host(monkeypatch):
    """``user@host`` should be stripped down to ``host`` before the TCP probe."""
    seen: list[str] = []

    async def fake_probe(host, port=22, timeout=1.0):
        seen.append(host)
        return True

    monkeypatch.setattr(orchestrator, "_probe_host", fake_probe)
    asyncio.new_event_loop().run_until_complete(
        orchestrator.preflight_hosts(["deploy@web01"], strict=False)
    )
    assert seen == ["deploy@web01"]


def test_kill_and_reap_returns_for_already_exited_child():
    """If the child has already exited, _kill_and_reap returns promptly."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc.wait()  # already exited
    start = time.monotonic()
    orchestrator._kill_and_reap(proc.pid, grace=2.0)
    assert time.monotonic() - start < 0.5


def test_kill_and_reap_kills_with_sigkill_on_grace_expiry():
    """If SIGTERM is ignored, SIGKILL closes the child within grace + epsilon."""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, time;"
            " signal.signal(signal.SIGTERM, signal.SIG_IGN);"
            " time.sleep(30)",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.1)  # let the child install the handler
    try:
        os.kill(proc.pid, signal.SIGTERM)
        start = time.monotonic()
        orchestrator._kill_and_reap(proc.pid, grace=0.3)
        # Should return within grace + a small headroom.
        assert time.monotonic() - start < 1.5
        # And the child must actually be gone.
        assert proc.poll() is not None or _is_zombie_or_dead(proc.pid)
    finally:
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def _is_zombie_or_dead(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return False
    except OSError:
        return True


def _bare_slave(**overrides):
    """Build a minimal Slave for decision-helper tests (no PTY / sockets)."""
    from csshx_latest.slave import Slave

    defaults = dict(
        index=1,
        host="h",
        sock_path="/tmp/x",
        token="t",
        pty_master=-1,
        pid=0,
    )
    defaults.update(overrides)
    return Slave(**defaults)


def test_should_reconnect_true_when_flag_on_and_not_user_closed():
    """Normal ssh death with ``--reconnect`` → respawn."""
    s = _bare_slave(dead=True, user_closed=False)
    assert orchestrator._should_reconnect(s, reconnect_enabled=True) is True


def test_should_reconnect_false_when_flag_off():
    """Without ``--reconnect``, no respawn even for an unexpected death."""
    s = _bare_slave(dead=True, user_closed=False)
    assert orchestrator._should_reconnect(s, reconnect_enabled=False) is False


def test_should_reconnect_false_when_user_closed_block():
    """User closed the terminal block → BYE → must NOT respawn even with --reconnect.

    This is the guard that prevents a closed slave from silently
    coming back to life one backoff cycle later.
    """
    s = _bare_slave(dead=True, user_closed=True)
    assert orchestrator._should_reconnect(s, reconnect_enabled=True) is False


def test_run_master_refuses_above_max_hosts(monkeypatch, capsys):
    """The hard cap rejects oversize host lists before touching launchers."""
    class FakeLauncher:
        name = "fake"
        def start(self, total): pass
        def open_block(self, c, t): raise AssertionError("must not be called")
        def close_block(self, h): pass
        def tile(self, h): pass
        def set_title(self, h, t): pass

    rc = asyncio.new_event_loop().run_until_complete(
        orchestrator.run_master(
            ["h"] * 50,
            ssh_args=[],
            login=None,
            launcher=FakeLauncher(),
            max_hosts=16,
            skip_preflight=True,
        )
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "max-hosts" in err
