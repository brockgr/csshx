"""Master TUI: raw-mode stdin, status line, and command-mode dispatch.

Author: Aditya Kapadia.

Command mode (configurable prefix, default ``Ctrl-T``, then one key):

* ``b`` -- toggle broadcast for ALL alive slaves
* ``1`` ... ``9`` -- toggle broadcast for that single slave
* ``i`` -- prompt for a slave index (for clusters with 10+ hosts)
* ``l`` -- list slaves with their state
* ``q`` -- quit
* ``?`` -- show command-mode help
* ``<prefix>`` (typed twice) -- send a literal prefix byte to slaves
* printable letter not in the dispatch -- cancel command mode AND
  broadcast that letter (so typo doesn't silently vanish)
* control byte (Esc, Ctrl-C, ...) -- cancel command mode silently
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.terminal import get_winsize, raw_mode, set_winsize

log = logging.getLogger(__name__)

KEY_QUIT = b"\x11"               # Ctrl-Q
KEY_COMMAND_PREFIX = b"\x14"     # Ctrl-T (default prefix)
KEY_INDEX_PROMPT = b"i"

#: ANSI escape codes for the colored status footer. Skipped when the
#: footer destination (stderr) isn't a TTY.
_ANSI_GREEN = "\x1b[32m"
_ANSI_RED = "\x1b[31m"
_ANSI_DIM = "\x1b[2m"
_ANSI_RESET = "\x1b[0m"


def parse_command_key(spec: str) -> bytes:
    """Parse a ``--command-key`` spec into a single byte.

    Accepts:

    * ``^X`` / ``^x`` (Ctrl-X), where X is an ASCII letter
    * ``0x14`` hex literal
    * a single literal printable character

    Raises ``ValueError`` on anything else.
    """
    if not spec:
        raise ValueError("empty")
    s = spec.strip()
    if len(s) == 2 and s[0] == "^":
        ch = s[1].upper()
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"^X requires A-Z, got {s!r}")
        return bytes([ord(ch) - 0x40])
    if s.lower().startswith("0x"):
        try:
            v = int(s, 16)
        except ValueError:
            raise ValueError(f"bad hex: {s!r}")
        if not 0 <= v <= 0xFF:
            raise ValueError(f"hex out of byte range: {s!r}")
        return bytes([v])
    if len(s) == 1:
        return s.encode("ascii", errors="strict")
    raise ValueError(f"unrecognized command-key spec: {s!r}")


def _key_label(prefix: bytes) -> str:
    """Render ``b"\\x14"`` as ``Ctrl-T`` for the help / status lines."""
    if not prefix or len(prefix) != 1:
        return repr(prefix)
    b = prefix[0]
    if 1 <= b <= 26:
        return f"Ctrl-{chr(b + 0x40)}"
    return repr(prefix)


def render_status(bcast: Broadcaster, command_key: bytes = KEY_COMMAND_PREFIX) -> None:
    """Write a one-line status footer to stderr.

    Colorizes the ``enabled`` / ``dead`` counters when stderr is a tty
    so the eye can spot a broken host in a wall of text.
    """
    total = len(bcast.slaves)
    enabled = len(bcast.enabled_indices())
    dead = sum(1 for s in bcast.slaves if s.dead)
    tty = sys.stderr.isatty()
    if tty:
        en_s = f"{_ANSI_GREEN}{enabled}{_ANSI_RESET}" if enabled else f"{_ANSI_DIM}0{_ANSI_RESET}"
        dead_s = f"{_ANSI_RED}{dead}{_ANSI_RESET}" if dead else f"{_ANSI_DIM}0{_ANSI_RESET}"
    else:
        en_s = str(enabled)
        dead_s = str(dead)
    sys.stderr.write(
        f"\r[csshx-latest] hosts: {total}  enabled: {en_s}  "
        f"dead: {dead_s}  (Ctrl-Q quit, {_key_label(command_key)} menu)\r\n"
    )
    sys.stderr.flush()


def _write_msg(msg: str) -> None:
    sys.stderr.write("\r" + msg + "\r\n")
    sys.stderr.flush()


def _render_help(command_key: bytes = KEY_COMMAND_PREFIX) -> None:
    label = _key_label(command_key)
    _write_msg("--- csshx-latest command mode ---")
    _write_msg("  b        toggle broadcast for ALL alive slaves")
    _write_msg("  1..9     toggle broadcast for that single slave")
    _write_msg("  i        prompt for a slave index (for 10+ hosts)")
    _write_msg("  l        list slaves and their state")
    _write_msg("  q        quit")
    _write_msg("  ?        show this help")
    _write_msg(f"  {label:<7}  send a literal {label}")
    _write_msg("  (other)  cancel command mode (printable echoes)")


def _render_list(bcast: Broadcaster) -> None:
    _write_msg(f"--- {len(bcast.slaves)} slaves ---")
    for s in bcast.slaves:
        state = "DEAD" if s.dead else ("ON" if s.enabled else "off")
        _write_msg(f"  [{s.index:>3}] {s.host:<30} {state}")


def _toggle_slave(bcast: Broadcaster, index: int) -> None:
    try:
        new_state = bcast.toggle(index)
    except KeyError:
        _write_msg(f"no slave with index {index}")
        return
    _write_msg(f"slave [{index}] -> {'ON' if new_state else 'off'}")


class _CommandState:
    """State machine for command mode: prefix -> dispatch / index-prompt."""

    def __init__(self) -> None:
        self.in_command = False
        self.in_index_prompt = False
        self.index_buffer = bytearray()

    def reset(self) -> None:
        self.in_command = False
        self.in_index_prompt = False
        self.index_buffer.clear()


async def _handle_command_byte(
    bcast: Broadcaster,
    byte: int,
    quit_event: asyncio.Event,
    command_key: bytes = KEY_COMMAND_PREFIX,
) -> bytes:
    """Apply one command-mode keystroke.

    Returns any bytes that should still be broadcast. Two cases push
    bytes back into the broadcast stream:

    * the user typed the prefix twice -> send a literal prefix byte
    * the user typed a printable letter that isn't bound -> cancel
      command mode AND broadcast that letter (so a typo never silently
      vanishes, matching the original csshX behavior)
    """
    ch = bytes([byte])
    if ch == command_key:
        return command_key
    if ch == b"b":
        any_enabled = any(s.enabled for s in bcast.slaves if not s.dead)
        bcast.set_all_enabled(not any_enabled)
        _write_msg(f"broadcast -> {'OFF' if any_enabled else 'ON'} for all alive slaves")
        render_status(bcast, command_key)
        return b""
    if ch in (b"1", b"2", b"3", b"4", b"5", b"6", b"7", b"8", b"9"):
        _toggle_slave(bcast, int(ch))
        render_status(bcast, command_key)
        return b""
    if ch == b"l":
        _render_list(bcast)
        render_status(bcast, command_key)
        return b""
    if ch == b"q":
        _write_msg("quitting...")
        quit_event.set()
        return b""
    if ch == b"?":
        _render_help(command_key)
        render_status(bcast, command_key)
        return b""
    # Printable ASCII that wasn't bound: cancel command mode and let the
    # byte through so the user's typo lands in the broadcast stream
    # instead of silently disappearing. Control bytes (Esc, Ctrl-C, etc.)
    # cancel silently.
    if 0x20 <= byte <= 0x7E:
        _write_msg(f"(command-mode cancelled; broadcasting {ch!r})")
        render_status(bcast, command_key)
        return ch
    _write_msg("(command-mode cancelled)")
    render_status(bcast, command_key)
    return b""


async def tui_loop(
    bcast: Broadcaster, command_key: bytes = KEY_COMMAND_PREFIX
) -> None:
    """Read stdin in raw mode and broadcast keystrokes; render a status line."""
    if not sys.stdin.isatty():
        await asyncio.Event().wait()
        return

    loop = asyncio.get_running_loop()
    quit_event = asyncio.Event()

    def on_sigwinch() -> None:
        rows, cols, xp, yp = get_winsize(sys.stdin.fileno())
        for s in bcast.slaves:
            set_winsize(s.pty_master, rows, cols, xp, yp)

    def on_quit_signal() -> None:
        quit_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        try:
            loop.add_signal_handler(sig, on_quit_signal)
        except (NotImplementedError, RuntimeError):
            pass
    try:
        loop.add_signal_handler(signal.SIGWINCH, on_sigwinch)
    except (NotImplementedError, RuntimeError, AttributeError):
        pass

    on_sigwinch()
    # One-line startup hint so first-time users discover the menu prefix
    # without reading docs. Skipped if stderr isn't a TTY (logs, pipes).
    if sys.stderr.isatty():
        _write_msg(
            f"[csshx-latest] press {_key_label(command_key)} for the command menu, "
            "Ctrl-Q to quit."
        )
    render_status(bcast, command_key)

    with raw_mode():
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        pipe = os.fdopen(sys.stdin.fileno(), "rb", buffering=0, closefd=False)
        transport, _ = await loop.connect_read_pipe(lambda: protocol, pipe)

        state = _CommandState()

        async def reader_task() -> None:
            while True:
                data = await reader.read(64)
                if not data:
                    quit_event.set()
                    return
                if KEY_QUIT in data:
                    quit_event.set()
                    return
                if (
                    not state.in_command
                    and not state.in_index_prompt
                    and command_key not in data
                ):
                    await bcast.broadcast(data)
                    continue
                await _drain_with_command_handling(
                    data, bcast, state, quit_event, command_key
                )

        task = asyncio.create_task(reader_task())
        try:
            await quit_event.wait()
        finally:
            task.cancel()
            transport.close()


async def _drain_with_command_handling(
    data: bytes,
    bcast: Broadcaster,
    state: _CommandState,
    quit_event: asyncio.Event,
    command_key: bytes = KEY_COMMAND_PREFIX,
) -> None:
    """Walk a chunk byte-by-byte when command / index-prompt mode is live."""
    buf = bytearray()
    for b in data:
        if state.in_index_prompt:
            if buf:
                await bcast.broadcast(bytes(buf))
                buf.clear()
            _consume_index_prompt_byte(b, bcast, state, command_key)
            continue
        if state.in_command:
            if buf:
                await bcast.broadcast(bytes(buf))
                buf.clear()
            if bytes([b]) == KEY_INDEX_PROMPT:
                state.in_command = False
                state.in_index_prompt = True
                state.index_buffer.clear()
                _write_msg("index: (type digits, Enter to apply, Esc to cancel)")
                continue
            extra = await _handle_command_byte(bcast, b, quit_event, command_key)
            state.in_command = False
            if extra:
                buf.extend(extra)
            continue
        if bytes([b]) == command_key:
            if buf:
                await bcast.broadcast(bytes(buf))
                buf.clear()
            state.in_command = True
            _write_msg("command mode (press ? for help)")
            continue
        buf.append(b)
    if buf:
        await bcast.broadcast(bytes(buf))


def _consume_index_prompt_byte(
    b: int,
    bcast: Broadcaster,
    state: _CommandState,
    command_key: bytes = KEY_COMMAND_PREFIX,
) -> None:
    """Process one byte while we're collecting digits for the index prompt."""
    if b in (0x1B, 0x03):
        _write_msg("(index prompt cancelled)")
        state.reset()
        render_status(bcast, command_key)
        return
    if b in (ord("\r"), ord("\n")):
        if not state.index_buffer:
            _write_msg("(no index given)")
        else:
            try:
                idx = int(state.index_buffer.decode("ascii"))
            except ValueError:
                _write_msg("(not a number)")
            else:
                _toggle_slave(bcast, idx)
        state.reset()
        render_status(bcast, command_key)
        return
    if b in (0x7F, 0x08):
        if state.index_buffer:
            state.index_buffer.pop()
        return
    if 0x30 <= b <= 0x39:
        state.index_buffer.append(b)
