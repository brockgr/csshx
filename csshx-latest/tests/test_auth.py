"""Tests for the AUTH handshake on slave sockets."""
from __future__ import annotations

import asyncio

import pytest

from csshx_latest import auth


def _run_handshake(payload: bytes, expected: str) -> bool:
    """Feed ``payload`` into a StreamReader and run the AUTH handshake."""
    async def go() -> bool:
        r = asyncio.StreamReader()
        r.feed_data(payload)
        r.feed_eof()
        return await auth.authenticate(r, expected)

    return asyncio.run(go())


def test_make_token_uniqueness_and_shape():
    a = auth.make_token()
    b = auth.make_token()
    assert a != b
    assert len(a) == 64
    assert all(c in "0123456789abcdef" for c in a)


def test_authenticate_correct_token():
    token = "abc123"
    assert _run_handshake(f"AUTH {token}\n".encode(), token) is True


def test_authenticate_tolerates_crlf():
    token = "deadbeef"
    assert _run_handshake(f"AUTH {token}\r\n".encode(), token) is True


def test_authenticate_wrong_token():
    assert _run_handshake(b"AUTH nope\n", "abc") is False


def test_authenticate_malformed_no_prefix():
    assert _run_handshake(b"hello world\n", "abc") is False


def test_authenticate_empty_input():
    assert _run_handshake(b"", "abc") is False


def test_authenticate_non_ascii_input():
    assert _run_handshake(b"AUTH \xff\xfe\n", "abc") is False


def test_authenticate_times_out_on_silent_client(monkeypatch):
    monkeypatch.setattr(auth, "HANDSHAKE_TIMEOUT", 0.05)

    async def go() -> bool:
        r = asyncio.StreamReader()
        return await auth.authenticate(r, "abc")

    assert asyncio.run(go()) is False
