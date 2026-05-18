"""Tests for the WaveTerm launcher's robust export parser."""
from __future__ import annotations

from csshx_latest.launchers.waveterm import _parse_bash_exports


def test_unquoted_export_is_parsed():
    out = _parse_bash_exports("export WAVETERM_JWT=abc.def.ghi\n")
    assert out == {"WAVETERM_JWT": "abc.def.ghi"}


def test_double_quoted_export_is_parsed():
    out = _parse_bash_exports('export WAVETERM_JWT="abc.def.ghi"\n')
    assert out == {"WAVETERM_JWT": "abc.def.ghi"}


def test_single_quoted_export_is_parsed():
    out = _parse_bash_exports("export WAVETERM_JWT='abc.def.ghi'\n")
    assert out == {"WAVETERM_JWT": "abc.def.ghi"}


def test_multiple_exports_are_collected():
    out = _parse_bash_exports(
        'export WAVETERM_JWT="abc"\n'
        'export WAVETERM_BLOCKID="b1"\n'
        "non-export line\n"
        "# a comment\n"
    )
    assert out == {"WAVETERM_JWT": "abc", "WAVETERM_BLOCKID": "b1"}


def test_malformed_lines_are_skipped_not_raised():
    """An unterminated quote must not raise -- skip the line, move on."""
    out = _parse_bash_exports(
        'export BROKEN="no end quote\n'
        'export GOOD="x.y"\n'
    )
    assert "GOOD" in out
    assert out["GOOD"] == "x.y"


def test_invalid_identifier_is_rejected():
    out = _parse_bash_exports('export 1BAD="value"\n')
    assert out == {}


def test_empty_input_returns_empty_dict():
    assert _parse_bash_exports("") == {}
