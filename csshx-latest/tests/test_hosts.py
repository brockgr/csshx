"""Tests for ``csshx_latest.hosts.expand_hosts``.

These tests pin the exact bash-compatible behaviors the CLI promises:
numeric ranges with width preservation, alternation, nesting, and
graceful pass-through of inputs that don't use braces.
"""
from __future__ import annotations

from csshx_latest.hosts import expand_hosts


def test_no_braces_returns_input_unchanged():
    assert expand_hosts(["a", "b.example.com"]) == ["a", "b.example.com"]


def test_numeric_range_basic():
    assert expand_hosts(["web{1..3}"]) == ["web1", "web2", "web3"]


def test_numeric_range_preserves_zero_padding():
    """A literal ``01`` in the lower bound forces 2-digit zero-padded output."""
    assert expand_hosts(["web{01..05}"]) == [
        "web01",
        "web02",
        "web03",
        "web04",
        "web05",
    ]


def test_numeric_range_descending():
    assert expand_hosts(["h{3..1}"]) == ["h3", "h2", "h1"]


def test_alternation_basic():
    assert expand_hosts(["api-{a,b,c}"]) == ["api-a", "api-b", "api-c"]


def test_alternation_keeps_empty_elements():
    """``foo{,bar}`` matches bash: yields ``foo`` then ``foobar``."""
    assert expand_hosts(["foo{,bar}"]) == ["foo", "foobar"]


def test_nested_alternation_and_range():
    """``{prod,stage}-web{1..2}`` should produce the full 2x2 cartesian product."""
    result = expand_hosts(["{prod,stage}-web{1..2}"])
    assert result == [
        "prod-web1",
        "prod-web2",
        "stage-web1",
        "stage-web2",
    ]


def test_multiple_args_flatten():
    """Each arg is expanded independently; results are concatenated in order."""
    assert expand_hosts(["a{1..2}", "b{x,y}"]) == ["a1", "a2", "bx", "by"]


def test_empty_arg_list():
    assert expand_hosts([]) == []
