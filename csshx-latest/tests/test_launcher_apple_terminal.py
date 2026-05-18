"""Tests for the Apple Terminal launcher (osascript mocked).

Three contracts pinned here:

1. The p10k fix: every ``do script`` body must start with
   ``exec /bin/sh -c '...'`` so the user's interactive shell never
   gets a chance to swallow the attach command. Without this, zsh +
   Powerlevel10k's instant-prompt corrupts the first keystrokes.

2. Per-block window tiling: each block opens in its own Terminal
   window (not a tab), and :meth:`tile` lays the windows out in a
   near-square grid via AppleScript ``set bounds`` — the same scheme
   the original Perl csshX used.

3. **Master + slave co-tiling:** :meth:`start` captures the front
   Terminal window id (the master TUI), and :meth:`tile` includes
   that window as cell 0 of the grid so master and slaves are
   rearranged together. If the capture fails, slaves are tiled and
   the master is left alone (no regression vs. v0.2.0).
"""
from __future__ import annotations

import subprocess

import pytest

from csshx_latest.launcher import BlockHandle, Color
from csshx_latest.launchers import apple_terminal as term_mod


@pytest.fixture
def fake_osascript(monkeypatch):
    """Capture every osascript invocation; canned-respond for known queries."""
    scripts: list[str] = []
    # The launcher reads two kinds of values from osascript stdout:
    #   * Finder desktop bounds (left,top,right,bottom) — for tile()
    #   * open_block: "<window_id>\n<tty>"
    # The fixture supplies these via a side-channel mutated per-test.
    canned = {"desktop": "0, 0, 1600, 1000", "open_block": "1234\n/dev/ttys001"}

    def runner(args, check=False, capture_output=False, text=False):
        if args[:2] != ["osascript", "-e"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        script = args[2]
        scripts.append(script)
        if "bounds of window of desktop" in script:
            return subprocess.CompletedProcess(args, 0, stdout=canned["desktop"], stderr="")
        if "do script" in script:
            return subprocess.CompletedProcess(args, 0, stdout=canned["open_block"], stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(term_mod.subprocess, "run", runner)
    return scripts, canned


def test_open_block_wraps_attach_in_exec_sh(fake_osascript):
    """The do-script body must start with ``exec /bin/sh -c`` (p10k fix)."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    l.open_block(["socat", "-", "UNIX-CONNECT:/tmp/a"], "web01")

    assert len(scripts) == 1
    s = scripts[0]
    assert "exec /bin/sh -c" in s
    assert 'set custom title of newTab to "web01"' in s
    assert "do script" in s


def test_open_block_captures_window_id_and_tty(fake_osascript):
    """``BlockHandle.data`` must record window_id (for tile) and tty (for title)."""
    scripts, canned = fake_osascript
    canned["open_block"] = "55501\n/dev/ttys017"
    l = term_mod.AppleTerminalLauncher()

    h = l.open_block(["echo", "hi"], "host-x")

    assert h.backend == "terminal"
    assert h.data["title"] == "host-x"
    assert h.data["window_id"] == "55501"
    assert h.data["tty"] == "/dev/ttys017"


def test_close_block_targets_captured_window_id(fake_osascript):
    """Close should address the captured window by id, not scan all tabs."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    h = l.open_block(["echo"], "h")
    scripts.clear()

    l.close_block(h)

    assert len(scripts) == 1
    assert "every window whose id is" in scripts[0]


def test_close_block_falls_back_to_tty_when_no_window_id():
    """If open_block didn't capture window_id, close_block scans tabs by tty."""
    sent: list[str] = []

    def runner(args, check=False, capture_output=False, text=False):
        if args[:2] == ["osascript", "-e"]:
            sent.append(args[2])
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    import builtins
    import unittest.mock

    with unittest.mock.patch.object(term_mod.subprocess, "run", runner):
        l = term_mod.AppleTerminalLauncher()
        h = BlockHandle(backend="terminal", data={"tty": "/dev/ttys009"})
        l.close_block(h)

    assert len(sent) == 1
    assert "/dev/ttys009" in sent[0]
    assert "every window whose id" not in sent[0]


def test_close_block_with_no_identifiers_is_noop(fake_osascript):
    """A handle with neither window_id nor tty silently no-ops."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    h = BlockHandle(backend="terminal", data={})
    scripts.clear()

    l.close_block(h)

    assert scripts == []


def test_tile_with_no_handles_is_noop(fake_osascript):
    """No handles ⇒ no osascript call (don't even ask Finder)."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    scripts.clear()

    l.tile([])

    assert scripts == []


def test_tile_skips_handles_without_window_id(fake_osascript):
    """Degraded handles (open_block failed) must not crash tile."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    h = BlockHandle(backend="terminal", data={"tty": "/dev/ttys001"})
    scripts.clear()

    l.tile([h])

    # No window_id → tile filters everything out → no osascript at all.
    assert scripts == []


def test_tile_two_blocks_lays_side_by_side(fake_osascript):
    """2 blocks on a 1600×1000 desktop tile into two columns inside usable bounds.

    Usable area = desktop minus EDGE_MARGIN (8) on every side and
    DOCK_RESERVE (90) on the bottom: (8, 8, 1592, 902). 2 cols of
    width 792 each, then each cell shrinks by WINDOW_GAP (6) on the
    right/bottom for breathing room.
    """
    scripts, canned = fake_osascript
    canned["desktop"] = "0, 0, 1600, 1000"
    l = term_mod.AppleTerminalLauncher()
    h1 = BlockHandle(backend="terminal", data={"window_id": "100", "tty": ""})
    h2 = BlockHandle(backend="terminal", data={"window_id": "200", "tty": ""})
    scripts.clear()

    l.tile([h1, h2])

    # The tile call batches: one Finder probe + one tell-Terminal block.
    bounds_script = [s for s in scripts if "set bounds of" in s]
    assert len(bounds_script) == 1, scripts
    body = bounds_script[0]
    # Left column 8..794, right column 800..1586; top 8, bottom 896.
    assert "{8, 8, 794, 896}" in body
    assert "{800, 8, 1586, 896}" in body
    assert 'first window whose id is 100' in body
    assert 'first window whose id is 200' in body


def test_tile_four_blocks_makes_two_by_two_grid(fake_osascript):
    """4 blocks on a 1600×1000 desktop tile into a 2×2 grid inside usable bounds."""
    scripts, canned = fake_osascript
    canned["desktop"] = "0, 0, 1600, 1000"
    l = term_mod.AppleTerminalLauncher()
    handles = [
        BlockHandle(backend="terminal", data={"window_id": str(i), "tty": ""})
        for i in range(4)
    ]
    scripts.clear()

    l.tile(handles)

    bounds_script = [s for s in scripts if "set bounds of" in s]
    body = bounds_script[0]
    # Usable (8, 8, 1592, 902); 2×2 cells of 792×447 each, then -6 gap.
    assert "{8, 8, 794, 449}" in body
    assert "{800, 8, 1586, 449}" in body
    assert "{8, 455, 794, 896}" in body
    assert "{800, 455, 1586, 896}" in body


def test_grid_for_returns_near_square_shapes():
    """The grid math should pick a near-square layout for any block count."""
    assert term_mod._grid_for(1) == (1, 1)
    assert term_mod._grid_for(2) == (1, 2)
    assert term_mod._grid_for(3) == (2, 2)
    assert term_mod._grid_for(4) == (2, 2)
    assert term_mod._grid_for(5) == (2, 3)
    assert term_mod._grid_for(9) == (3, 3)
    assert term_mod._grid_for(10) == (3, 4)
    # Empty edge case: 0 blocks → 0 grid (no division-by-zero downstream).
    assert term_mod._grid_for(0) == (0, 0)


def test_set_title_uses_captured_tty(fake_osascript):
    """``set_title`` finds the tab via the captured tty id."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    h = l.open_block(["echo"], "h")
    scripts.clear()

    l.set_title(h, "new-title")

    assert len(scripts) == 1
    assert "set custom title of t" in scripts[0]
    assert 'new-title' in scripts[0]


def test_special_chars_in_title_are_escaped(fake_osascript):
    """A title containing a double-quote must not break the AppleScript string."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    l.open_block(["echo"], 'evil"title')

    assert 'evil\\"title' in scripts[0]


def test_tile_one_block_fills_whole_desktop(fake_osascript):
    """A single block on a 1600×1000 desktop fills the usable rectangle."""
    scripts, canned = fake_osascript
    canned["desktop"] = "0, 0, 1600, 1000"
    l = term_mod.AppleTerminalLauncher()
    h = BlockHandle(backend="terminal", data={"window_id": "42", "tty": ""})
    scripts.clear()

    l.tile([h])

    bounds_script = [s for s in scripts if "set bounds of" in s]
    assert len(bounds_script) == 1
    # Usable (8, 8, 1592, 902) minus 6px gap on right/bottom → (8, 8, 1586, 896).
    assert "{8, 8, 1586, 896}" in bounds_script[0]
    assert "first window whose id is 42" in bounds_script[0]


def test_tile_three_blocks_uses_two_by_two_grid_with_gap(fake_osascript):
    """3 blocks → 2×2 grid (4th cell empty); first three cells filled."""
    scripts, canned = fake_osascript
    canned["desktop"] = "0, 0, 1600, 1000"
    l = term_mod.AppleTerminalLauncher()
    handles = [
        BlockHandle(backend="terminal", data={"window_id": str(i), "tty": ""})
        for i in range(3)
    ]
    scripts.clear()

    l.tile(handles)

    body = [s for s in scripts if "set bounds of" in s][0]
    # Top-left, top-right, bottom-left filled (same cells as the 4-block grid).
    assert "{8, 8, 794, 449}" in body
    assert "{800, 8, 1586, 449}" in body
    assert "{8, 455, 794, 896}" in body
    # Only three windows referenced.
    assert body.count("first window whose id is") == 3


def test_tile_nine_blocks_uses_three_by_three_grid(fake_osascript):
    """9 blocks on a 1500×900 desktop tile into a 3×3 grid inside usable bounds."""
    scripts, canned = fake_osascript
    canned["desktop"] = "0, 0, 1500, 900"
    l = term_mod.AppleTerminalLauncher()
    handles = [
        BlockHandle(backend="terminal", data={"window_id": str(i), "tty": ""})
        for i in range(9)
    ]
    scripts.clear()

    l.tile(handles)

    body = [s for s in scripts if "set bounds of" in s][0]
    # Usable (8, 8, 1492, 802); 3×3 cells of 494×264 each, minus 6px gaps.
    # Spot-check the four corners + the center cell.
    assert "{8, 8, 496, 266}" in body          # top-left
    assert "{996, 8, 1484, 266}" in body       # top-right
    assert "{502, 272, 990, 530}" in body      # center
    assert "{8, 536, 496, 794}" in body        # bottom-left
    assert "{996, 536, 1484, 794}" in body     # bottom-right


def test_set_color_emits_background_color_per_state(fake_osascript):
    """``set_color`` writes a per-state RGB triple to the tab's background color.

    The exact RGB values come from :data:`_TAB_BG` in
    ``apple_terminal.py``; we read them out of the module rather than
    duplicating the magic numbers so a future palette retune only has
    to touch one place. The contract this test pins is the *shape* of
    the AppleScript and the *one-to-one mapping* between Color states
    and palette entries — not the specific hex values.
    """
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    h = BlockHandle(backend="terminal", data={"window_id": "77", "tty": "/dev/ttys001"})
    scripts.clear()

    l.set_color(h, Color.ENABLED)
    l.set_color(h, Color.DISABLED)
    l.set_color(h, Color.DEAD)

    assert len(scripts) == 3
    # All three scripts target the same captured window via id.
    assert all("first window whose id is 77" in s for s in scripts)
    assert all("set background color of tab 1" in s for s in scripts)
    # Each script must carry exactly the RGB the palette declares for
    # its state — three different triples, one per state.
    for script, color in zip(scripts, (Color.ENABLED, Color.DISABLED, Color.DEAD)):
        r, g, b = term_mod._TAB_BG[color]
        assert f"{{{r}, {g}, {b}}}" in script


def test_tab_bg_palette_is_distinct_and_in_range():
    """All three Color states map to distinct, valid 16-bit RGB triples.

    Pins the *contract* (distinguishability + valid hardware range) so
    the user can tell ENABLED / DISABLED / DEAD apart at a glance.
    Does NOT pin the specific hex values — palette tuning stays free.
    """
    palette = term_mod._TAB_BG
    assert set(palette.keys()) == {Color.ENABLED, Color.DISABLED, Color.DEAD}
    triples = list(palette.values())
    # Distinct: the user must be able to tell the three states apart.
    assert len(set(triples)) == 3
    # Valid 16-bit RGB: AppleScript silently clamps out-of-range and
    # negative values would crash the call.
    for r, g, b in triples:
        assert 0 <= r <= 65535
        assert 0 <= g <= 65535
        assert 0 <= b <= 65535


def test_set_color_is_noop_without_window_id(fake_osascript):
    """No captured window_id → set_color silently no-ops (degraded handle)."""
    scripts, _ = fake_osascript
    l = term_mod.AppleTerminalLauncher()
    h = BlockHandle(backend="terminal", data={"tty": "/dev/ttys001"})
    scripts.clear()

    l.set_color(h, Color.ENABLED)

    assert scripts == []


def test_usable_bounds_subtracts_dock_and_edge_margins(monkeypatch):
    """Usable area drops EDGE_MARGIN on every side and DOCK_RESERVE on the bottom."""
    def runner(args, check=False, capture_output=False, text=False):
        return subprocess.CompletedProcess(args, 0, stdout="0, 0, 1600, 1000", stderr="")

    monkeypatch.setattr(term_mod.subprocess, "run", runner)
    left, top, right, bottom = term_mod._get_usable_bounds()
    assert left == term_mod.EDGE_MARGIN
    assert top == term_mod.EDGE_MARGIN
    assert right == 1600 - term_mod.EDGE_MARGIN
    assert bottom == 1000 - term_mod.DOCK_RESERVE - term_mod.EDGE_MARGIN


def test_desktop_bounds_falls_back_when_finder_fails(monkeypatch):
    """If Finder returns garbage, we fall back to a 1920×1080 default."""

    def runner(args, check=False, capture_output=False, text=False):
        return subprocess.CompletedProcess(args, 0, stdout="oops not numbers", stderr="")

    monkeypatch.setattr(term_mod.subprocess, "run", runner)
    assert term_mod._get_desktop_bounds() == (0, 0, 1920, 1080)


# -----------------------------------------------------------------
# Master-window co-tiling tests.
#
# These verify the fix for "slaves get rearranged, master doesn't":
# start() captures the front window id (the master TUI's window) and
# tile() includes it in the grid.
# -----------------------------------------------------------------


@pytest.fixture
def fake_osascript_with_master(monkeypatch):
    """Like ``fake_osascript`` but also canned-responds to the master capture."""
    scripts: list[str] = []
    canned = {
        "desktop": "0, 0, 1600, 1000",
        "open_block": "1234\n/dev/ttys001",
        "master_window_id": "9001",
    }

    def runner(args, check=False, capture_output=False, text=False):
        if args[:2] != ["osascript", "-e"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        script = args[2]
        scripts.append(script)
        if "bounds of window of desktop" in script:
            return subprocess.CompletedProcess(args, 0, stdout=canned["desktop"], stderr="")
        if "do script" in script:
            return subprocess.CompletedProcess(args, 0, stdout=canned["open_block"], stderr="")
        if "id of front window" in script:
            return subprocess.CompletedProcess(
                args, 0, stdout=canned["master_window_id"], stderr=""
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(term_mod.subprocess, "run", runner)
    return scripts, canned


def test_start_captures_front_window_id(fake_osascript_with_master):
    """``start()`` must query and remember the master Terminal window's id."""
    scripts, _ = fake_osascript_with_master
    l = term_mod.AppleTerminalLauncher()

    l.start(total=3)

    capture_scripts = [s for s in scripts if "id of front window" in s]
    assert len(capture_scripts) == 1
    assert l._master_window_id == "9001"


def test_start_ignores_non_numeric_capture(fake_osascript_with_master):
    """Non-digit stdout from osascript must not poison the master id."""
    scripts, canned = fake_osascript_with_master
    canned["master_window_id"] = "missing value"
    l = term_mod.AppleTerminalLauncher()

    l.start(total=1)

    # Capture attempted, but the result was rejected.
    assert any("id of front window" in s for s in scripts)
    assert l._master_window_id == ""


def test_tile_includes_master_at_top_left(fake_osascript_with_master):
    """When start() captured the master, tile() puts it at cell 0 of the grid."""
    scripts, canned = fake_osascript_with_master
    canned["desktop"] = "0, 0, 1600, 1000"
    canned["master_window_id"] = "9001"
    l = term_mod.AppleTerminalLauncher()
    l.start(total=3)  # 1 master + 2 slaves coming
    h1 = BlockHandle(backend="terminal", data={"window_id": "100", "tty": ""})
    h2 = BlockHandle(backend="terminal", data={"window_id": "200", "tty": ""})
    scripts.clear()

    l.tile([h1, h2])

    body = [s for s in scripts if "set bounds of" in s][0]
    # 3 cells (master + 2 slaves) → 2×2 grid of 792×447 inside usable bounds.
    # Master at cell 0 (top-left), slave-100 at cell 1 (top-right),
    # slave-200 at cell 2 (bottom-left).
    assert "first window whose id is 9001" in body  # master included
    assert body.index("first window whose id is 9001") < body.index(
        "first window whose id is 100"
    )
    assert "{8, 8, 794, 449}" in body            # master cell
    assert "{800, 8, 1586, 449}" in body         # first slave cell
    assert "{8, 455, 794, 896}" in body          # second slave cell
    # All three windows are addressed exactly once.
    assert body.count("first window whose id is") == 3


def test_tile_falls_back_to_slaves_only_when_master_capture_failed(
    fake_osascript_with_master,
):
    """If start() couldn't capture the master, tile() keeps the v0.2.0 behavior."""
    scripts, canned = fake_osascript_with_master
    canned["master_window_id"] = ""  # simulate Finder-denied / failed capture
    canned["desktop"] = "0, 0, 1600, 1000"
    l = term_mod.AppleTerminalLauncher()
    l.start(total=2)  # capture is attempted but yields nothing
    assert l._master_window_id == ""
    h1 = BlockHandle(backend="terminal", data={"window_id": "100", "tty": ""})
    h2 = BlockHandle(backend="terminal", data={"window_id": "200", "tty": ""})
    scripts.clear()

    l.tile([h1, h2])

    body = [s for s in scripts if "set bounds of" in s][0]
    # 2 cells (slaves only) → 1×2 columns inside usable bounds.
    assert "{8, 8, 794, 896}" in body
    assert "{800, 8, 1586, 896}" in body
    assert body.count("first window whose id is") == 2
    assert "9001" not in body  # master not present


def test_tile_with_only_master_uses_full_desktop(fake_osascript_with_master):
    """Edge case: tile([]) but master captured → master gets the whole desktop."""
    scripts, canned = fake_osascript_with_master
    canned["master_window_id"] = "9001"
    canned["desktop"] = "0, 0, 1600, 1000"
    l = term_mod.AppleTerminalLauncher()
    l.start(total=0)
    scripts.clear()

    l.tile([])

    body = [s for s in scripts if "set bounds of" in s][0]
    assert "first window whose id is 9001" in body
    # Master gets the whole usable area: (8, 8, 1592, 902) minus 6px gap.
    assert "{8, 8, 1586, 896}" in body
