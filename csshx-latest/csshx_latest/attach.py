"""Stdlib attach client used by every spawned terminal block.

Author: Aditya Kapadia.

Connects to a slave's two UNIX sockets (data + control), performs the
AUTH handshake on each, then shuttles bytes between the user's TTY
and the data socket. SIGWINCH on the local TTY pushes
``WINSZ rows cols xpixel ypixel`` lines onto the control socket so
the slave can resize its PTY and the remote ssh side learns the new
geometry.

Run as a module so spawned terminal blocks can launch it without any
extra dependency::

    python3 -m csshx_latest.attach <socket_path> <token_path>

The control socket path is derived from the data socket by replacing
the trailing ``.sock`` with ``.ctl``. The master always creates the
two together so this is reliable.

The token is read at runtime from ``<token_path>`` rather than passed
on the command line so that ``ps`` listings can't be used by another
local user to harvest the AUTH token. The token file is created by
the master at mode ``0600`` inside a ``0700`` directory.

Closing the visible terminal block
----------------------------------

When the user closes the spawned terminal window/pane/tab, this
process either receives ``SIGHUP``/``SIGTERM``/``SIGINT`` from the
terminal emulator (Apple Terminal, iTerm2) or reads ``EOF`` on its
controlling TTY (tmux pane kill, Kitty tab close). In every case we
send a best-effort ``BYE\\n`` line on the control socket before
exiting so the master can mark the slave dead and update its status
footer. Without this, ssh keeps running attached to the master's PTY
and the user sees a stale "alive" count for a host they thought they
closed.
"""
from __future__ import annotations

import errno
import io
import os
import select
import signal
import socket
import struct
import sys
from typing import Optional

BUFSIZE = 4096


def _read_token(token_path: str) -> str:
    """Read the token from disk and strip surrounding whitespace."""
    with open(token_path, "r", encoding="ascii") as fh:
        return fh.read().strip()


def _ctl_path_for(data_path: str) -> str:
    """Derive the control socket path from the data socket path."""
    if data_path.endswith(".sock"):
        return data_path[: -len(".sock")] + ".ctl"
    return data_path + ".ctl"


def _resolve_io_fds() -> tuple[int, int, bool]:
    """Return ``(in_fd, out_fd, owns_fds)`` for shuttling bytes."""
    def _stdin_fd() -> int:
        try:
            return sys.stdin.fileno()
        except (AttributeError, io.UnsupportedOperation, OSError, ValueError):
            raise

    def _stdout_fd() -> int:
        try:
            return sys.stdout.fileno()
        except (AttributeError, io.UnsupportedOperation, OSError, ValueError):
            raise

    try:
        return _stdin_fd(), _stdout_fd(), False
    except Exception:
        pass

    try:
        in_fd = os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY)
        out_fd = os.open("/dev/tty", os.O_WRONLY | os.O_NOCTTY)
        return in_fd, out_fd, True
    except OSError:
        pass

    in_fd = os.open(os.devnull, os.O_RDONLY)
    out_fd = os.open(os.devnull, os.O_WRONLY)
    return in_fd, out_fd, True


def _connect_auth(path: str, token: str) -> socket.socket:
    """Open a UNIX socket, send AUTH, return the connected socket."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(path)
    sock.sendall(f"AUTH {token}\n".encode("ascii"))
    return sock


def _get_winsize(fd: int) -> tuple[int, int, int, int]:
    """Read TIOCGWINSZ from ``fd``; fall back to (24, 80, 0, 0)."""
    try:
        import fcntl
        import termios
    except ImportError:  # pragma: no cover - non-unix
        return (24, 80, 0, 0)
    try:
        packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 8)
        return struct.unpack("HHHH", packed)
    except OSError:
        return (24, 80, 0, 0)


def _push_winsize(ctl_sock: socket.socket, in_fd: int) -> None:
    """Send a WINSZ line for the current ``in_fd`` geometry."""
    rows, cols, xp, yp = _get_winsize(in_fd)
    if rows <= 0 or cols <= 0:
        return
    try:
        ctl_sock.sendall(f"WINSZ {rows} {cols} {xp} {yp}\n".encode("ascii"))
    except OSError:
        pass


def _send_bye(ctl_sock: Optional[socket.socket]) -> None:
    """Best-effort ``BYE`` on the control socket.

    Safe to call from a signal handler: ``sendall`` of a ~4 byte line
    on a UNIX domain socket is far below ``PIPE_BUF``, atomic, and
    non-blocking enough to never re-enter the runtime. Idempotent at
    the master side (``_handle_bye`` no-ops the second time).
    """
    if ctl_sock is None:
        return
    try:
        ctl_sock.sendall(b"BYE\n")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    """Entry point. Returns the process exit code."""
    if len(argv) != 3:
        sys.stderr.write(
            "usage: python3 -m csshx_latest.attach <socket_path> <token_path>\n"
        )
        return 2
    path, token_path = argv[1], argv[2]

    try:
        token = _read_token(token_path)
    except OSError as exc:
        sys.stderr.write(f"read token {token_path}: {exc}\n")
        return 1

    try:
        data_sock = _connect_auth(path, token)
    except OSError as exc:
        sys.stderr.write(f"connect {path}: {exc}\n")
        return 1

    ctl_sock: Optional[socket.socket] = None
    try:
        ctl_sock = _connect_auth(_ctl_path_for(path), token)
    except OSError:
        ctl_sock = None

    in_fd, out_fd, owns_fds = _resolve_io_fds()

    saved = None
    if os.isatty(in_fd):
        import termios
        import tty
        saved = termios.tcgetattr(in_fd)
        tty.setraw(in_fd)

    resize_pending = {"flag": False}

    def on_sigwinch(_signo, _frame) -> None:
        resize_pending["flag"] = True

    if ctl_sock is not None and hasattr(signal, "SIGWINCH"):
        try:
            signal.signal(signal.SIGWINCH, on_sigwinch)
        except (OSError, ValueError):
            pass
        _push_winsize(ctl_sock, in_fd)

    # Terminal emulators send SIGHUP when the user closes the visible
    # block (Terminal.app, iTerm2). systemd / launchctl can deliver
    # SIGTERM. Ctrl-C inside a pre-raw-mode interrupt window arrives
    # as SIGINT. In every case the master needs to know this slave's
    # session is over — push BYE then re-raise the default action so
    # we still exit promptly. The handler is intentionally tiny and
    # signal-safe (no allocation beyond sendall's own buffers).
    bye_sent = {"flag": False}

    def on_terminating_signal(signo, _frame) -> None:
        if not bye_sent["flag"]:
            bye_sent["flag"] = True
            _send_bye(ctl_sock)
        # Restore default disposition and re-raise so the OS does the
        # right thing (default SIGHUP/SIGTERM/SIGINT all terminate).
        try:
            signal.signal(signo, signal.SIG_DFL)
            os.kill(os.getpid(), signo)
        except OSError:
            pass

    for _signo_name in ("SIGHUP", "SIGTERM", "SIGINT"):
        sig = getattr(signal, _signo_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, on_terminating_signal)
        except (OSError, ValueError):
            pass

    watch_in = True
    received_any = False
    try:
        while True:
            if resize_pending["flag"] and ctl_sock is not None:
                resize_pending["flag"] = False
                _push_winsize(ctl_sock, in_fd)

            watches = [data_sock]
            if watch_in:
                watches.append(in_fd)
            try:
                r, _, _ = select.select(watches, [], [], 0.5)
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise
            if data_sock in r:
                data = data_sock.recv(BUFSIZE)
                if not data:
                    if not received_any:
                        sys.stderr.write(
                            "csshx-latest: AUTH rejected -- the master closed the "
                            "socket before sending any data. Check that the token "
                            "embedded in the attach command matches the one the "
                            "master generated for this slave.\n"
                        )
                        return 1
                    return 0
                received_any = True
                os.write(out_fd, data)
            if watch_in and in_fd in r:
                try:
                    data = os.read(in_fd, BUFSIZE)
                except OSError:
                    data = b""
                if not data:
                    # Stdin EOF means the terminal block went away
                    # without giving us a signal (e.g. tmux ``kill-pane``,
                    # Kitty tab close). Mirror the signal-handler path
                    # so the master always learns about the closure.
                    if not bye_sent["flag"]:
                        bye_sent["flag"] = True
                        _send_bye(ctl_sock)
                    watch_in = False
                    try:
                        data_sock.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                else:
                    data_sock.sendall(data)
    except KeyboardInterrupt:
        if not bye_sent["flag"]:
            bye_sent["flag"] = True
            _send_bye(ctl_sock)
        return 130
    finally:
        if saved is not None:
            import termios
            termios.tcsetattr(in_fd, termios.TCSADRAIN, saved)
        if owns_fds:
            for fd in (in_fd, out_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass
        data_sock.close()
        if ctl_sock is not None:
            try:
                ctl_sock.close()
            except OSError:
                pass


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
