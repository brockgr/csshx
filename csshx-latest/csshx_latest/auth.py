"""Token generation, persistence, and authentication handshake.

Each slave socket created by the master is gated by a 32-byte hex
token. Connecting clients must send ``AUTH <token>\\n`` as the first
line within :data:`HANDSHAKE_TIMEOUT` seconds; otherwise their
connection is dropped. This prevents other local users from injecting
keystrokes into your SSH sessions.

The token itself is persisted to a file at mode ``0600`` inside the
master's ``0700`` socket directory. Spawned terminal blocks pass the
token's *file path* (never the token itself) on their command line —
``ps`` listings only reveal the file path, and the file mode keeps the
contents off-limits to other UIDs.
"""
from __future__ import annotations

import asyncio
import os
import secrets

TOKEN_BYTES = 32
HANDSHAKE_TIMEOUT = 2.0


def make_token() -> str:
    """Return a fresh 64-character hex token (32 bytes of entropy)."""
    return secrets.token_hex(TOKEN_BYTES)


def write_token_file(path: str, token: str) -> None:
    """Persist ``token`` to ``path`` with mode ``0600``.

    Uses ``os.open`` with ``O_CREAT | O_WRONLY | O_TRUNC`` and an
    explicit mode so the file is never world-readable, even briefly.
    """
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token.encode("ascii"))
    finally:
        os.close(fd)
    # Belt-and-suspenders: an existing file with looser permissions
    # won't have its mode reset by O_CREAT (mode arg is ignored on
    # already-existing files), so re-chmod explicitly.
    os.chmod(path, 0o600)


async def authenticate(reader: asyncio.StreamReader, expected: str) -> bool:
    """Read the first line and validate the AUTH handshake.

    Returns True iff the client sent ``AUTH <expected>\\n`` (``\\r`` is
    tolerated) within :data:`HANDSHAKE_TIMEOUT` seconds. Uses a
    constant-time comparison for the token.
    """
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=HANDSHAKE_TIMEOUT)
    except asyncio.TimeoutError:
        return False
    if not line:
        return False
    try:
        text = line.decode("ascii", errors="strict").rstrip("\r\n")
    except UnicodeDecodeError:
        return False
    if not text.startswith("AUTH "):
        return False
    return secrets.compare_digest(text[5:], expected)
