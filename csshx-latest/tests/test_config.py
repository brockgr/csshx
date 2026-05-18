"""Tests for ``csshx_latest.config`` (cluster alias loading)."""
from __future__ import annotations

import os

import pytest

from csshx_latest.config import expand_clusters, load_clusters


def test_toml_clusters_preferred_over_csshrc(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[clusters]\nweb = ["web01", "web02"]\n')
    csshrc = tmp_path / ".csshrc"
    csshrc.write_text("cluster web = ignored\n")

    clusters = load_clusters(toml_path=str(toml), csshrc_path=str(csshrc))
    assert clusters == {"web": ["web01", "web02"]}


def test_csshrc_fallback_when_toml_missing(tmp_path):
    csshrc = tmp_path / ".csshrc"
    csshrc.write_text(
        "# comment line\n"
        "cluster web = web01 web02 web03\n"
        "cluster db  = db1 db2\n"
        "\n"
        "ignored line\n"
    )
    clusters = load_clusters(
        toml_path=str(tmp_path / "nonexistent.toml"),
        csshrc_path=str(csshrc),
    )
    assert clusters == {"web": ["web01", "web02", "web03"], "db": ["db1", "db2"]}


def test_missing_both_files_returns_empty(tmp_path):
    assert load_clusters(
        toml_path=str(tmp_path / "no.toml"),
        csshrc_path=str(tmp_path / "no.rc"),
    ) == {}


def test_toml_accepts_string_value(tmp_path):
    """``hosts = "h1 h2 h3"`` is split on whitespace via shlex."""
    toml = tmp_path / "config.toml"
    toml.write_text('[clusters]\nweb = "web01 web02 web03"\n')
    clusters = load_clusters(toml_path=str(toml), csshrc_path=str(tmp_path / "nope"))
    assert clusters == {"web": ["web01", "web02", "web03"]}


def test_expand_clusters_resolves_nested_alias():
    clusters = {
        "all": ["web", "db"],
        "web": ["web01", "web02"],
        "db": ["db1"],
    }
    assert expand_clusters(["all"], clusters) == ["web01", "web02", "db1"]


def test_expand_clusters_short_circuits_cycle():
    clusters = {"a": ["b"], "b": ["a"]}
    # Should not hang. Resolves a -> b -> (sees a in seen) -> emits literal "a".
    out = expand_clusters(["a"], clusters)
    assert out == ["a"]


def test_expand_clusters_passes_unknown_through():
    assert expand_clusters(["host1"], {"web": ["web01"]}) == ["host1"]


def test_expand_clusters_no_clusters_arg_returns_input():
    """An empty / None clusters dict means no expansion happens."""
    from csshx_latest.hosts import expand_hosts

    assert expand_hosts(["h1", "h2"]) == ["h1", "h2"]


def test_xdg_config_home_is_respected(monkeypatch, tmp_path, capsys):
    """``$XDG_CONFIG_HOME`` overrides the default ``~/.config`` lookup."""
    cfg_dir = tmp_path / "cfg" / "csshx-latest"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.toml").write_text('[clusters]\nweb = ["x"]\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("HOME", str(tmp_path))
    # Use real default-resolution path so we exercise _toml_path.
    assert load_clusters() == {"web": ["x"]}
