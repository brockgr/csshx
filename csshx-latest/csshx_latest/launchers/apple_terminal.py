"""Apple Terminal.app launcher via ``osascript``.

Author: Aditya Kapadia.

Terminal.app's only AppleScript hook for launching commands is
``do script``, which feeds the typed text into the new tab's login
shell. With Powerlevel10k as the user's default shell, the long
.zshrc + instant-prompt initialization can swallow / reorder the
attach command's keystrokes. To avoid that, we prefix the attach
command with ``exec /bin/sh -c '...'`` -- zsh's first parsed line
exec-replaces itself with ``/bin/sh`` running our command, so the
prompt never gets a chance to render and no shell init code runs.

Each block opens in its OWN Terminal window (not a tab in a shared
window) so :meth:`tile` can position blocks independently by setting
``bounds`` on each window. The window id is captured into
:attr:`BlockHandle.data["window_id"]` at open time so subsequent
tile / close / set_title calls don't have to scan all windows.

Master window
-------------

The TUI runs in the Terminal window the user invoked ``csshx-latest``
from. :meth:`start` captures its id (``id of front window``) before
any slave window opens, so :meth:`tile` can include it as the first
cell of the grid. The result: master + slaves all get rearranged
together every time a slave block is added, matching the original
Perl csshX behavior. If the capture fails (Finder denied, AppleScript
returns garbage), the master is silently excluded and slaves are
tiled as before -- no regression.

Tiling mirrors the original Perl csshX layout: compute the usable
desktop area (Finder's ``bounds of window of desktop`` minus the
Dock and a small edge margin) and divide it into a near-square grid
of ``rows × cols`` cells, packing windows left-to-right, top-to-
bottom, with the master always at cell 0 (top-left). Each cell is
shrunk by :data:`WINDOW_GAP` pixels on its right and bottom so
adjacent windows aren't flush against each other. The math is in
:func:`_grid_for` / :func:`_get_usable_bounds`.

Color hook
----------

Terminal.app does NOT expose a per-tab "color" attribute in
AppleScript, but it does expose ``background color`` on tabs
(16-bit RGB). :meth:`set_color` writes that property so the user
gets a visible cue when broadcast is toggled. The palette is
deliberately low-saturation (see :data:`_TAB_BG`) so a wall of
slave windows isn't fatiguing to look at: ENABLED → dim sage,
DISABLED → dim slate, DEAD → dim mauve. The change is per-tab and
does not persist into the user's saved profile.
"""
from __future__ import annotations

import logging
import math
import shlex
import subprocess

from csshx_latest.launcher import BlockHandle, Color

log = logging.getLogger(__name__)

# Pixels reserved at the bottom of the screen for the Dock. Finder's
# ``bounds of window of desktop`` returns the full screen rectangle and
# does NOT subtract the Dock, so windows tiled to that rectangle slide
# under the Dock. 90px covers the default Dock size + a small buffer.
# Querying the actual Dock size requires Accessibility permission and
# can prompt the user, so we use a conservative fixed reserve instead.
DOCK_RESERVE = 90

# Small inset on every screen edge so windows don't sit flush against
# the menu bar or screen borders.
EDGE_MARGIN = 8

# Pixels of space between adjacent tiled windows. Each cell is shrunk
# by this amount on its right and bottom edges so neighbours don't
# touch each other.
WINDOW_GAP = 6

# Terminal.app's ``background color`` of a tab is 16-bit RGB (0..65535).
# Subtle low-saturation tints rather than full-strength primaries — the
# eye picks up the hue difference at a glance without the slab of green
# / red being uncomfortable to look at for hours. All three live in the
# same lightness band (~12k-19k of 65535) so foreground text contrast
# stays roughly the same on every state.
#
# - ENABLED  → dim sage  (#303E37-ish) — faint cool green wash
# - DISABLED → dim slate (#38383C-ish) — barely-tinted neutral
# - DEAD     → dim mauve (#483438-ish) — faint warm red wash
_TAB_BG: dict[Color, tuple[int, int, int]] = {
    Color.ENABLED:  (12288, 17408, 14336),
    Color.DISABLED: (14336, 14336, 15360),
    Color.DEAD:     (18432, 13312, 14336),
}


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _osascript(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)


def _grid_for(n: int) -> tuple[int, int]:
    """Return ``(rows, cols)`` for a near-square grid holding ``n`` blocks."""
    if n <= 0:
        return (0, 0)
    cols = max(1, int(math.ceil(math.sqrt(n))))
    rows = max(1, int(math.ceil(n / cols)))
    return (rows, cols)


def _get_desktop_bounds() -> tuple[int, int, int, int]:
    """Return the usable desktop rectangle ``(left, top, right, bottom)``.

    Uses Finder's ``bounds of window of desktop``, which excludes the
    menu bar but includes the Dock area on macOS. Falls back to a
    sane default if the AppleScript call fails (e.g. Finder denied,
    headless test).
    """
    result = _osascript(
        'tell application "Finder" to get bounds of window of desktop'
    )
    text = (result.stdout or "").strip()
    try:
        parts = [int(p.strip()) for p in text.split(",")]
        if len(parts) == 4:
            return (parts[0], parts[1], parts[2], parts[3])
    except ValueError:
        pass
    log.debug("Finder desktop bounds unavailable; falling back to 1920x1080")
    return (0, 0, 1920, 1080)


def _get_usable_bounds() -> tuple[int, int, int, int]:
    """Return the desktop rectangle minus Dock and edge insets.

    Subtracts :data:`DOCK_RESERVE` from the bottom so windows don't
    slide under the Dock, and :data:`EDGE_MARGIN` from every side so
    windows don't sit flush against the menu bar or screen borders.
    """
    left, top, right, bottom = _get_desktop_bounds()
    return (
        left + EDGE_MARGIN,
        top + EDGE_MARGIN,
        right - EDGE_MARGIN,
        bottom - DOCK_RESERVE - EDGE_MARGIN,
    )


class AppleTerminalLauncher:
    """Open each block as its own Terminal.app window and tile them."""

    name = "terminal"

    def __init__(self) -> None:
        # Captured at start() so tile() can include the TUI's own window in
        # the grid alongside slave windows. Empty string means "no capture
        # yet" or "capture failed" -- tile() falls back to slaves-only.
        self._master_window_id: str = ""

    def start(self, total: int) -> None:
        """Capture the front window id (the master TUI) before any slave opens.

        Done here -- not at construction -- so the orchestrator's
        single ``launcher.start(total)`` call lands while the TUI's
        Terminal window is still the frontmost. After the first
        :meth:`open_block` runs, ``activate`` will have shifted focus
        to a freshly-spawned slave window and ``front window`` would
        no longer point at the master.
        """
        result = _osascript(
            'tell application "Terminal" to return id of front window as text'
        )
        text = (result.stdout or "").strip()
        if result.returncode != 0 or not text or not text.isdigit():
            log.debug(
                "could not capture master Terminal window id (rc=%d, stdout=%r): "
                "tile() will arrange slave windows only",
                result.returncode,
                text,
            )
            return
        self._master_window_id = text

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Open a fresh Terminal window running ``attach_cmd``.

        AppleScript's ``do script`` without a target opens in the
        frontmost window's last tab (or a brand-new window if none
        exists). To guarantee a separate window per block we create
        the window explicitly with ``make new window``, then run the
        command in its single tab. The window's ``id`` is captured so
        tiling can address it directly without scanning.
        """
        cmd_str = " ".join(shlex.quote(a) for a in attach_cmd)
        wrapped = f"exec /bin/sh -c {shlex.quote(cmd_str)}"
        cmd_esc = _escape(wrapped)
        title_esc = _escape(title)
        script = (
            'tell application "Terminal"\n'
            '  activate\n'
            f'  set newTab to do script "{cmd_esc}"\n'
            '  set newWin to window 1\n'
            f'  set custom title of newTab to "{title_esc}"\n'
            '  return (id of newWin as text) & "\\n" & (tty of newTab)\n'
            'end tell\n'
        )
        result = _osascript(script)
        out_lines = [
            ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()
        ]
        window_id = out_lines[0] if len(out_lines) >= 1 else ""
        tty_id = out_lines[1] if len(out_lines) >= 2 else ""
        if result.returncode != 0:
            log.warning(
                "Terminal.app open_block exited %d: %s",
                result.returncode,
                result.stderr.strip(),
            )
        return BlockHandle(
            backend=self.name,
            data={"title": title, "tty": tty_id, "window_id": window_id},
        )

    def close_block(self, handle: BlockHandle) -> None:
        """Close the window matching the captured id; fall back to tty match."""
        window_id = handle.data.get("window_id")
        if window_id:
            wid_esc = _escape(str(window_id))
            _osascript(
                'tell application "Terminal"\n'
                f'  try\n'
                f'    close (every window whose id is {wid_esc})\n'
                f'  end try\n'
                'end tell\n'
            )
            return
        tty_id = handle.data.get("tty")
        if not tty_id:
            return
        tty_esc = _escape(tty_id)
        _osascript(
            'tell application "Terminal"\n'
            '  repeat with w in windows\n'
            '    repeat with t in tabs of w\n'
            f'      if tty of t is "{tty_esc}" then close t\n'
            '    end repeat\n'
            '  end repeat\n'
            'end tell\n'
        )

    def tile(self, handles: list[BlockHandle]) -> None:
        """Lay out the master + captured slave windows in a near-square grid.

        Windows pack left-to-right, top-to-bottom: with 4 blocks (1
        master + 3 slaves) you get 2×2; with 2 blocks you get 1×2
        (side-by-side); with 3 you get 2 rows where the bottom row is
        half-empty. Slave windows without a captured ``window_id``
        (open_block fell back) are skipped silently so a partial
        failure doesn't break the rest.

        When ``start()`` successfully captured the master window's id,
        it's placed at cell 0 (top-left) so the user keeps clear focus
        on where they're typing. When the master capture failed, only
        slave windows are tiled — the original behavior.
        """
        windowed = [h for h in handles if h.data.get("window_id")]
        cells: list[str] = []
        if self._master_window_id:
            cells.append(self._master_window_id)
        cells.extend(str(h.data["window_id"]) for h in windowed)
        if not cells:
            return
        left, top, right, bottom = _get_usable_bounds()
        width = max(0, right - left)
        height = max(0, bottom - top)
        rows, cols = _grid_for(len(cells))
        if rows == 0 or cols == 0 or width == 0 or height == 0:
            return
        cell_w = width // cols
        cell_h = height // rows
        lines = ['tell application "Terminal"']
        for i, wid in enumerate(cells):
            r = i // cols
            c = i % cols
            x1 = left + c * cell_w
            y1 = top + r * cell_h
            # Shrink each cell by WINDOW_GAP on right/bottom so adjacent
            # windows have visible breathing room.
            x2 = x1 + cell_w - WINDOW_GAP
            y2 = y1 + cell_h - WINDOW_GAP
            wid_esc = _escape(wid)
            lines.append(
                f'  try\n'
                f'    set bounds of (first window whose id is {wid_esc}) '
                f'to {{{x1}, {y1}, {x2}, {y2}}}\n'
                f'  end try'
            )
        lines.append('end tell')
        result = _osascript("\n".join(lines))
        if result.returncode != 0:
            log.warning(
                "Terminal.app tile exited %d: %s",
                result.returncode,
                result.stderr.strip(),
            )

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """Rename the tab matched by tty id."""
        tty_id = handle.data.get("tty")
        if not tty_id:
            return
        tty_esc = _escape(tty_id)
        title_esc = _escape(title)
        _osascript(
            'tell application "Terminal"\n'
            '  repeat with w in windows\n'
            '    repeat with t in tabs of w\n'
            f'      if tty of t is "{tty_esc}" then set custom title of t to "{title_esc}"\n'
            '    end repeat\n'
            '  end repeat\n'
            'end tell\n'
        )

    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """Tint the slave's tab so broadcast state is visible.

        Writes ``background color`` of the window's first tab via
        AppleScript. The value is a 16-bit RGB triple from
        :data:`_TAB_BG`. Silently no-ops if we never captured a window
        id (open_block fell back) or if the color isn't in the palette.
        Errors are swallowed inside an AppleScript ``try`` block so a
        stale window id during shutdown can't break callers.
        """
        wid = handle.data.get("window_id")
        rgb = _TAB_BG.get(color)
        if not wid or not rgb:
            return
        r, g, b = rgb
        wid_esc = _escape(str(wid))
        _osascript(
            'tell application "Terminal"\n'
            f'  try\n'
            f'    set background color of tab 1 of '
            f'(first window whose id is {wid_esc}) to {{{r}, {g}, {b}}}\n'
            f'  end try\n'
            'end tell\n'
        )
