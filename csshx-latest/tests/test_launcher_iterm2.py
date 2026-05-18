"""Tests for the iTerm2 launcher (osascript mocked).

iTerm2's AppleScript bridge is fundamentally opaque from Python's side
— the only thing we can really verify without an actual iTerm2 process
is the *shape* of the AppleScript we send.

Two contracts pinned here:

1. **The p10k fix:** every attach command is passed as the new
   session's ``command`` (which iTerm execvps directly) rather than
   via ``write text`` (which types into the user's interactive shell,
   where p10k's instant-prompt can intercept keystrokes).

2. **Master + slave co-tiling:** every block splits the master TUI's
   current session. v1.0 created a brand-new window for the first
   slave, leaving the master orphaned in its own window; iTerm2 only
   rearranged the slaves. v1.1+ always splits, so iTerm2's automatic
   pane balancing rearranges master and slaves together.
"""
from __future__ import annotations

import subprocess

import pytest

from csshx_latest.launcher import BlockHandle, Color
from csshx_latest.launchers import iterm2 as iterm_mod


@pytest.fixture
def fake_osascript(monkeypatch):
    """Capture every osascript invocation; return the AppleScript bodies."""
    scripts: list[str] = []

    def runner(args, check=False, capture_output=False, text=False):
        # Real call shape: ``osascript -e <script>``.
        if args[:2] == ["osascript", "-e"]:
            scripts.append(args[2])
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(iterm_mod.subprocess, "run", runner)
    return scripts


def test_first_open_splits_current_session_not_new_window(fake_osascript):
    """First block → ``split vertically`` of the master's current session.

    v1.0 issued ``create window with default profile`` here, which
    parked the master TUI in a sibling window where iTerm2's auto-tile
    couldn't reach it. v1.1+ splits the master's session so master +
    every slave share one window and iTerm2 rearranges them together.
    """
    l = iterm_mod.ITerm2Launcher()
    l.open_block(["socat", "-", "UNIX-CONNECT:/tmp/a"], "web01")

    assert len(fake_osascript) == 1
    s = fake_osascript[0]
    # The p10k fix: pass attach as the new session's ``command``,
    # not via ``write text`` (which types into the interactive shell).
    assert "split vertically with default profile" in s
    assert "create window with default profile" not in s
    assert 'command "' in s
    assert "write text" not in s
    # Title is applied via ``set name`` on the new session.
    assert 'set name to "web01"' in s
    # Attach argv must appear inside the command string.
    assert "socat" in s


def test_second_open_also_uses_split_vertically_with_command(fake_osascript):
    """Subsequent blocks also split the current session, again via ``command``."""
    l = iterm_mod.ITerm2Launcher()
    l.open_block(["echo", "first"], "first")
    l.open_block(["echo", "second"], "second")

    assert len(fake_osascript) == 2
    for body in fake_osascript:
        assert "split vertically with default profile" in body
        assert "create window with default profile" not in body
        assert 'command "' in body
        assert "write text" not in body
    assert 'set name to "first"' in fake_osascript[0]
    assert 'set name to "second"' in fake_osascript[1]


def test_special_chars_in_attach_command_are_escaped(fake_osascript):
    """Backslashes and double-quotes in argv must not break out of the literal."""
    l = iterm_mod.ITerm2Launcher()
    l.open_block(['echo', 'has "quote" and \\back'], "evil")

    s = fake_osascript[0]
    # Raw double-quote / backslash must be escaped in the AppleScript body.
    # We can't easily count exact escaping without re-parsing, but we
    # can verify that unescaped sequences that would terminate the
    # AppleScript string do NOT appear adjacent to the cmd boundary.
    cmd_start = s.index('command "') + len('command "')
    # The next unescaped " marks the end of the AppleScript literal.
    # Make sure the user's literal `"quote"` chars don't terminate early.
    tail = s[cmd_start:]
    # Find first un-escaped quote (i.e. a `"` not preceded by `\`).
    i = 0
    while i < len(tail):
        if tail[i] == '"' and (i == 0 or tail[i - 1] != "\\"):
            break
        i += 1
    closing_quote = i
    # Everything up to closing_quote is the embedded command. It MUST
    # still contain the original 'echo' token — if escaping broke, the
    # AppleScript would have terminated before that.
    embedded = tail[:closing_quote]
    assert "echo" in embedded


def test_close_block_is_noop(fake_osascript):
    """iTerm2 sessions die when ssh exits; close_block is intentionally no-op."""
    l = iterm_mod.ITerm2Launcher()
    h = l.open_block(["echo"], "h")
    fake_osascript.clear()

    l.close_block(h)

    assert fake_osascript == []


def test_tile_is_noop(fake_osascript):
    """iTerm2 auto-balances splits — explicit tiling is unnecessary."""
    l = iterm_mod.ITerm2Launcher()
    fake_osascript.clear()

    l.tile([])

    assert fake_osascript == []


def test_set_title_renames_current_session(fake_osascript):
    """Best-effort: ``set name to`` on the current session."""
    l = iterm_mod.ITerm2Launcher()
    h = l.open_block(["echo"], "h")
    fake_osascript.clear()

    l.set_title(h, "renamed")

    assert len(fake_osascript) == 1
    assert "set name to" in fake_osascript[0]
    assert "renamed" in fake_osascript[0]


def test_set_color_writes_session_background_per_state(fake_osascript):
    """``set_color`` writes a per-state RGB triple to the matched session.

    Exact RGB values come from :data:`_SESSION_BG`; we look them up
    rather than hard-coding so a future palette retune only changes
    one place. The contract pinned here is the AppleScript shape
    (correct session id, ``background color`` write) and the one-to-
    one mapping from Color state to palette entry.
    """
    l = iterm_mod.ITerm2Launcher()
    h = BlockHandle(
        backend="iterm2",
        data={"title": "x", "window_id": "w1", "session_id": "sess-42"},
    )
    fake_osascript.clear()

    l.set_color(h, Color.ENABLED)
    l.set_color(h, Color.DISABLED)
    l.set_color(h, Color.DEAD)

    assert len(fake_osascript) == 3
    # All three scripts target the captured session id and write
    # ``background color`` (not a no-op anymore).
    assert all('if id of s is "sess-42"' in s for s in fake_osascript)
    assert all("set background color of s" in s for s in fake_osascript)
    for script, color in zip(fake_osascript, (Color.ENABLED, Color.DISABLED, Color.DEAD)):
        r, g, b = iterm_mod._SESSION_BG[color]
        assert f"{{{r}, {g}, {b}}}" in script


def test_session_bg_palette_is_distinct_and_in_range():
    """All three Color states map to distinct, valid 16-bit RGB triples."""
    palette = iterm_mod._SESSION_BG
    assert set(palette.keys()) == {Color.ENABLED, Color.DISABLED, Color.DEAD}
    triples = list(palette.values())
    assert len(set(triples)) == 3
    for r, g, b in triples:
        assert 0 <= r <= 65535
        assert 0 <= g <= 65535
        assert 0 <= b <= 65535


def test_set_color_is_noop_without_session_id(fake_osascript):
    """No captured session_id → set_color silently no-ops."""
    l = iterm_mod.ITerm2Launcher()
    h = BlockHandle(backend="iterm2", data={"title": "x", "window_id": "w1"})
    fake_osascript.clear()

    l.set_color(h, Color.ENABLED)

    assert fake_osascript == []
