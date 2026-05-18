"""Tests for ``csshx_latest.__main__.main`` argument parsing.

Author: Aditya Kapadia.

We don't actually run the master loop -- that needs a tty and forks
ssh. Instead we stub ``asyncio.run`` and assert on the args that
``run_master`` would have received.
"""
from __future__ import annotations

import pytest

from csshx_latest import __main__ as cli


@pytest.fixture
def captured_run(monkeypatch):
    """Stub ``asyncio.run`` and capture the coro's bound args."""
    captured: dict[str, object] = {}

    async def fake_coro(
        hosts,
        ssh_args,
        login,
        launcher,
        *,
        max_hosts=16,
        strict_preflight=False,
        reconnect=False,
        skip_preflight=False,
        command_key=b"\x14",
    ):
        captured["hosts"] = list(hosts)
        captured["ssh_args"] = list(ssh_args)
        captured["login"] = login
        captured["launcher"] = launcher
        captured["max_hosts"] = max_hosts
        captured["strict_preflight"] = strict_preflight
        captured["reconnect"] = reconnect
        captured["skip_preflight"] = skip_preflight
        captured["command_key"] = command_key
        return 0

    monkeypatch.setattr(cli, "run_master", fake_coro)

    def fake_asyncio_run(coro):
        import asyncio
        return asyncio.new_event_loop().run_until_complete(coro)

    monkeypatch.setattr(cli.asyncio, "run", fake_asyncio_run)
    return captured


@pytest.fixture(autouse=True)
def _no_clusters(monkeypatch):
    """Clusters should not be loaded from the user's real home dir in tests."""
    monkeypatch.setattr(cli, "load_clusters", lambda: {})


def test_version_flag_exits_zero(capsys):
    """``--version`` should print the package version and exit 0."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "csshx-latest" in out


def test_brace_expansion_happens_before_run_master(captured_run, monkeypatch):
    """``web0{1..3}`` must be expanded to three hosts before run_master sees them."""
    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    cli.main(["--launcher", "manual", "web0{1..3}"])
    assert captured_run["hosts"] == ["web01", "web02", "web03"]


def test_launcher_choices_include_all_registered_backends():
    """The ``--launcher`` choices must come from the registry (not hardcoded)."""
    from csshx_latest.launcher import available_launcher_names

    names = available_launcher_names()
    for expected in ("auto", "tmux", "iterm2", "terminal", "kitty", "waveterm", "wezterm", "manual"):
        assert expected in names, f"missing launcher choice: {expected}"


def test_debug_flag_does_not_raise(captured_run, monkeypatch):
    """``--debug`` is accepted and reconfigures logging without error."""
    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    rc = cli.main(["--debug", "--launcher", "manual", "host1"])
    assert rc == 0


def test_ssh_args_are_split_with_shlex(captured_run, monkeypatch):
    """``--ssh-args`` accepts a single quoted string; we shlex-split it."""
    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    cli.main(["--launcher", "manual", "--ssh-args", "-o StrictHostKeyChecking=no -p 2222", "h"])
    assert captured_run["ssh_args"] == ["-o", "StrictHostKeyChecking=no", "-p", "2222"]


def test_invalid_launcher_choice_exits_nonzero(capsys):
    """Argparse rejects unknown launcher names."""
    with pytest.raises(SystemExit):
        cli.main(["--launcher", "bogus-name", "host"])


def test_max_hosts_default_is_sixteen(captured_run, monkeypatch):
    """Default ``--max-hosts`` should match the orchestrator constant."""
    from csshx_latest.orchestrator import DEFAULT_MAX_HOSTS

    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    cli.main(["--launcher", "manual", "host"])
    assert captured_run["max_hosts"] == DEFAULT_MAX_HOSTS == 16


def test_strict_flag_propagates(captured_run, monkeypatch):
    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    cli.main(["--launcher", "manual", "--strict", "h"])
    assert captured_run["strict_preflight"] is True


def test_reconnect_flag_propagates(captured_run, monkeypatch):
    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    cli.main(["--launcher", "manual", "--reconnect", "h"])
    assert captured_run["reconnect"] is True


def test_no_preflight_flag_propagates(captured_run, monkeypatch):
    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    cli.main(["--launcher", "manual", "--no-preflight", "h"])
    assert captured_run["skip_preflight"] is True


def test_cluster_alias_expansion(captured_run, monkeypatch):
    """A ``cluster`` name on the CLI should expand to its host list."""
    monkeypatch.setattr(cli, "detect_launcher", lambda _name: object())
    monkeypatch.setattr(cli, "load_clusters", lambda: {"web": ["web01", "web02"]})
    cli.main(["--launcher", "manual", "web"])
    assert captured_run["hosts"] == ["web01", "web02"]
