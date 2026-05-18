"""Terminal helpers: raw-mode context manager and PTY winsize ioctls.

These are tiny wrappers around termios / fcntl that hide the boilerplate
and degrade to no-ops on platforms without those modules (e.g. Windows),
so the package can at least be imported there.
"""
from __future__ import annotations

import os
import struct
import sys
from contextlib import contextmanager
from typing import Iterator, Optional

try:
    import fcntl
    import termios
    import tty
    _UNIX = True
except ImportError:  # pragma: no cover - non-unix
    _UNIX = False


def get_winsize(fd: int) -> tuple[int, int, int, int]:
    """Return ``(rows, cols, xpixel, ypixel)`` for ``fd``.

    Falls back to ``(24, 80, 0, 0)`` if the ioctl fails or the platform
    doesn't support TIOCGWINSZ.
    """
    if not _UNIX:
        return (24, 80, 0, 0)
    try:
        packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 8)
        return struct.unpack("HHHH", packed)
    except OSError:
        return (24, 80, 0, 0)


def set_winsize(fd: int, rows: int, cols: int, xpixel: int = 0, ypixel: int = 0) -> None:
    """Set the window size on a PTY master ``fd`` via TIOCSWINSZ."""
    if not _UNIX:
        return
    packed = struct.pack("HHHH", rows, cols, xpixel, ypixel)
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)
    except OSError:
        pass


# ANSI sequences to disable terminal modes that prompt frameworks like
# Powerlevel10k commonly leave enabled. xterm.js (WaveTerm, VSCode) honors
# these strictly; Apple Terminal is more permissive, which is why the
# breakage was WaveTerm-specific.
#
# Leading ``\e[!p`` is a DECSTR ("soft terminal reset") — clears most
# DEC private modes in one shot WITHOUT clearing the screen. The
# specific disables below are belt-and-suspenders for terminals that
# don't implement DECSTR (or implement it partially):
#
#   \e[?2004l   bracketed paste mode (otherwise input is wrapped in 200~/201~)
#   \e>         normal keypad (otherwise digits/Enter send SS3 sequences)
#   \e[?1l      normal cursor keys (otherwise arrows send SS3 not CSI)
#   \e[?1000l   X11 mouse: button events
#   \e[?1002l   X11 mouse: button-event tracking
#   \e[?1003l   X11 mouse: any-event tracking
#   \e[?1004l   focus reporting (otherwise focus in/out emits CSI I / CSI O)
#   \e[?1006l   SGR mouse encoding
#   \e[?1015l   urxvt mouse encoding
#   \e[>4;0m    disable xterm modifyOtherKeys (THIS was the WaveTerm killer:
#               with this on, plain letter keys are encoded as
#               ``\e[27;<mod>;<key>~`` extended sequences — broadcast to
#               ssh, the remote shell sees garbage)
#   \e[>1;0m    disable modifyCursorKeys
#   \e[>2;0m    disable modifyFunctionKeys
#   \e[?25h     ensure cursor is visible (some prompts hide it)
_TERM_MODE_RESET = (
    b"\x1b[!p"
    b"\x1b[?2004l"
    b"\x1b>"
    b"\x1b[?1l"
    b"\x1b[?1000l"
    b"\x1b[?1002l"
    b"\x1b[?1003l"
    b"\x1b[?1004l"
    b"\x1b[?1006l"
    b"\x1b[?1015l"
    b"\x1b[>4;0m"
    b"\x1b[>1;0m"
    b"\x1b[>2;0m"
    b"\x1b[?25h"
)


def reset_terminal_modes(fd: Optional[int] = None) -> None:
    """Emit ANSI sequences that undo the modes prompt frameworks set.

    Safe to call on a non-tty (writes are silent or fail-closed). The
    sequences are no-ops on terminals that don't implement them, so
    there's no harm sending them everywhere — and they're essential on
    xterm.js-based terminals (WaveTerm, VSCode) where p10k's bracketed
    paste / application-keypad state otherwise garbles every keystroke
    csshx-latest's TUI sees.
    """
    if not _UNIX:
        return
    if fd is None:
        try:
            fd = sys.stdout.fileno()
        except (AttributeError, ValueError, OSError):
            return
    if not os.isatty(fd):
        return
    try:
        os.write(fd, _TERM_MODE_RESET)
    except OSError:
        pass


@contextmanager
def raw_mode(fd: Optional[int] = None) -> Iterator[None]:
    """Put ``fd`` (default stdin) into termios raw mode; restore on exit.

    Also flushes any lingering terminal-mode state (bracketed paste,
    application keypad, etc.) before going raw, so a prompt framework
    like Powerlevel10k that left modes enabled in the parent shell
    doesn't garble the bytes the TUI is about to read. No-ops on
    non-Unix or when the fd is not a TTY.
    """
    if not _UNIX:
        yield
        return
    if fd is None:
        fd = sys.stdin.fileno()
    if not os.isatty(fd):
        yield
        return
    saved = termios.tcgetattr(fd)
    # Flush whatever the previous shell left buffered in the input queue
    # (e.g. p10k's instant-prompt feedback the user couldn't see) before
    # we go raw — otherwise the first broadcast cycle would replay it.
    try:
        termios.tcflush(fd, termios.TCIFLUSH)
    except termios.error:
        pass
    reset_terminal_modes()
    try:
        tty.setraw(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        # Re-emit the resets on exit so the user's next prompt isn't
        # left in a half-raw state if csshx-latest crashed mid-loop.
        reset_terminal_modes()
