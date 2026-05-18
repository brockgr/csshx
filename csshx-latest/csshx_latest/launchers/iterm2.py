"""iTerm2 launcher via ``osascript`` and iTerm's AppleScript dictionary.

Author: Aditya Kapadia.

Every block (the first included) is a *split* of the master TUI's
current session, so master + slaves end up sharing one iTerm2 window
and iTerm2's auto-balanced split panes give all of them equal real
estate. Each open shifts the slaves smaller and the master smaller in
lockstep, exactly the visual rearrangement the original Perl csshX
provided on Terminal.app.

Every split passes the attach command as the new session's
``command``, so iTerm executes it directly via ``execvp`` and the
user's interactive login shell never runs. That sidesteps p10k /
oh-my-zsh swallowing the attach command's keystrokes.

Session ids returned by ``id of newSession`` are captured into
``BlockHandle.data`` so :meth:`close_block` can actually close the
pane on shutdown instead of leaving a dead socket sitting visible.
iTerm2 auto-balances split panes whenever a new one is added, so
:meth:`tile` itself stays a no-op.
"""
from __future__ import annotations

import logging
import shlex
import subprocess

from csshx_latest.launcher import BlockHandle, Color

log = logging.getLogger(__name__)

# iTerm2's session ``background color`` accepts a 16-bit RGB triple
# (0..65535). Same low-saturation palette as Apple Terminal so the
# visual cue feels consistent across backends and doesn't fatigue the
# eye after staring at a wall of slave panes for an hour:
#   ENABLED  → dim sage   (faint cool green wash)
#   DISABLED → dim slate  (barely-tinted neutral)
#   DEAD     → dim mauve  (faint warm red wash)
_SESSION_BG: dict[Color, tuple[int, int, int]] = {
    Color.ENABLED:  (12288, 17408, 14336),
    Color.DISABLED: (14336, 14336, 15360),
    Color.DEAD:     (18432, 13312, 14336),
}


def _osascript(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)


def _escape(s: str) -> str:
    """Escape backslashes and double-quotes for embedding in an AppleScript literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


class ITerm2Launcher:
    """Open each block as an iTerm2 split pane via AppleScript."""

    name = "iterm2"

    def start(self, total: int) -> None:
        """No-op: iTerm2 split panes balance automatically."""

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Split the master's current session and run ``attach_cmd`` inside it.

        Every block — including the first — is created with ``split
        vertically with default profile command ...``. That places the
        new slave alongside the master TUI in the same iTerm2 window,
        so iTerm2's automatic pane balancing rearranges master and
        slaves together on every spawn. (v1.0 created a brand-new
        window for the first block, which left the master orphaned
        in its own window — slaves were tiled, master wasn't.)
        """
        cmd_str = " ".join(shlex.quote(a) for a in attach_cmd)
        cmd_esc = _escape(cmd_str)
        title_esc = _escape(title)

        script = (
            'tell application "iTerm"\n'
            '  activate\n'
            '  tell current session of current window\n'
            '    set newSession to (split vertically with default profile '
            f'    command "{cmd_esc}")\n'
            '  end tell\n'
            '  tell newSession\n'
            f'    set name to "{title_esc}"\n'
            '  end tell\n'
            '  return (id of current window) & "|" & (id of newSession)\n'
            'end tell\n'
        )
        result = _osascript(script)
        window_id, session_id = _parse_ids(result.stdout)
        if result.returncode != 0:
            log.warning("iTerm2 open_block exited %d: %s", result.returncode, result.stderr.strip())
        return BlockHandle(
            backend=self.name,
            data={"title": title, "window_id": window_id, "session_id": session_id},
        )

    def close_block(self, handle: BlockHandle) -> None:
        """Close the captured session id. No-op if iTerm2 didn't return one."""
        session_id = handle.data.get("session_id")
        if not session_id:
            return
        sid_esc = _escape(session_id)
        _osascript(
            'tell application "iTerm"\n'
            '  repeat with w in windows\n'
            '    repeat with t in tabs of w\n'
            '      repeat with s in sessions of t\n'
            f'        if id of s is "{sid_esc}" then close s\n'
            '      end repeat\n'
            '    end repeat\n'
            '  end repeat\n'
            'end tell\n'
        )

    def tile(self, handles: list[BlockHandle]) -> None:
        """No-op: iTerm2 evenly balances split panes automatically."""

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """Rename the captured session if we got an id."""
        session_id = handle.data.get("session_id")
        title_esc = _escape(title)
        if not session_id:
            _osascript(
                'tell application "iTerm" to tell current session of current window '
                f'to set name to "{title_esc}"'
            )
            return
        sid_esc = _escape(session_id)
        _osascript(
            'tell application "iTerm"\n'
            '  repeat with w in windows\n'
            '    repeat with t in tabs of w\n'
            '      repeat with s in sessions of t\n'
            f'        if id of s is "{sid_esc}" then set name of s to "{title_esc}"\n'
            '      end repeat\n'
            '    end repeat\n'
            '  end repeat\n'
            'end tell\n'
        )


    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """Tint the slave session so broadcast state is visible.

        Writes ``background color`` of the matched session via
        AppleScript using a 16-bit RGB triple from :data:`_SESSION_BG`.
        Silently no-ops if we never captured a session id (open_block
        fell back). Errors are swallowed inside an AppleScript ``try``
        block so a stale id during shutdown can't break callers.
        """
        session_id = handle.data.get("session_id")
        rgb = _SESSION_BG.get(color)
        if not session_id or not rgb:
            return
        r, g, b = rgb
        sid_esc = _escape(session_id)
        _osascript(
            'tell application "iTerm"\n'
            '  repeat with w in windows\n'
            '    repeat with t in tabs of w\n'
            '      repeat with s in sessions of t\n'
            f'        if id of s is "{sid_esc}" then\n'
            f'          try\n'
            f'            set background color of s to {{{r}, {g}, {b}}}\n'
            f'          end try\n'
            f'        end if\n'
            '      end repeat\n'
            '    end repeat\n'
            '  end repeat\n'
            'end tell\n'
        )


def _parse_ids(stdout: str) -> tuple[str, str]:
    """Parse ``"window_id|session_id"`` from osascript output."""
    if not stdout:
        return ("", "")
    line = stdout.strip().splitlines()[-1] if stdout.strip() else ""
    if "|" not in line:
        return ("", "")
    win, _, sess = line.partition("|")
    return (win.strip(), sess.strip())
