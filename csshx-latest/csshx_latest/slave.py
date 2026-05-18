"""One SSH slave: PTY + ssh subprocess + UNIX-socket bridge.

Author: Aditya Kapadia.

The master forks ``ssh <host>`` attached to a fresh PTY and exposes
that PTY through two UNIX domain sockets, both gated by the same AUTH
token:

* ``slave-N.sock`` -- the data socket. PTY bytes flow out, keystrokes
  flow in. Bytes that arrive *before* the terminal block has connected
  are kept in a per-slave scrollback buffer and replayed to each new
  client immediately after AUTH succeeds.

* ``slave-N.ctl`` -- the control socket. After AUTH it accepts
  line-oriented ASCII commands, one per line. Supported commands::

      WINSZ <rows> <cols> [<xpixel> <ypixel>]
      BYE

  ``WINSZ`` applies ``TIOCSWINSZ`` to the PTY master so the remote
  ssh side learns the new size when the *individual* terminal block
  (not just the master) is resized.

  ``BYE`` signals "the user closed this block." The slave is marked
  ``user_closed`` and the ssh pid is sent ``SIGTERM`` so the remote
  session ends. The natural PTY-EOF path then fires ``on_dead`` so
  the status footer's alive/dead counters update and (with
  ``--reconnect``) the retry schedule is suppressed because the
  termination was user-initiated.

  The grammar is intentionally forward-compatible: ``_apply_control_line``
  silently ignores any unknown command verb so an older attach client
  never breaks when newer slaves grow new ones. Reserved future verbs
  include ``BELL``, ``FOCUS``, ``RESIZE`` (a structured rename of
  ``WINSZ``) — when adding a new verb, follow the WINSZ shape:
  ``VERB <arg1> [<arg2> ...]\\n``, ASCII only, no quoting.

Input direction (data socket -> PTY) accepts bytes from the focused
terminal block AND from the master's broadcaster, both serialized
through a per-slave ``write_lock`` so individual escape sequences are
never torn apart by interleaving writes.

This module also handles:

* a TOCTOU-safe ``start_unix_server`` (sockets created under ``umask
  0o077`` so they're mode 0600 from the moment they exist);
* dead-slave detection -- when the PTY reader sees EOF (ssh exited),
  the slave is marked ``dead`` and an optional ``on_dead`` callback is
  invoked;
* clean child reaping -- ``shutdown_slave`` calls ``waitpid`` after
  ``SIGTERM`` so the parent doesn't accumulate ``<defunct>`` zombies.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

from csshx_latest.auth import authenticate
from csshx_latest.terminal import set_winsize

log = logging.getLogger(__name__)

#: Per-slave cap on simultaneous authenticated data-socket clients.
#: A legitimate run has one (the spawned terminal block). Allowing a
#: handful supports re-attach + a side-channel for tooling; rejecting
#: beyond that contains the blast radius of a leaked token.
DEFAULT_MAX_WRITERS = 4


@dataclass
class Slave:
    """State for one SSH connection."""

    index: int
    host: str
    sock_path: str
    token: str
    pty_master: int
    pid: int
    token_path: str = ""
    ctl_sock_path: str = ""
    enabled: bool = True
    dead: bool = False
    #: Set to True when the visible terminal block is destroyed and its
    #: attach client sent ``BYE``. Used by the orchestrator to suppress
    #: ``--reconnect`` for slaves the user explicitly killed.
    user_closed: bool = False
    max_writers: int = DEFAULT_MAX_WRITERS
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    server: Optional[asyncio.AbstractServer] = field(default=None, repr=False)
    ctl_server: Optional[asyncio.AbstractServer] = field(default=None, repr=False)
    pty_reader_task: Optional[asyncio.Task] = field(default=None, repr=False)
    connected_writers: list[asyncio.StreamWriter] = field(default_factory=list, repr=False)
    scrollback: bytearray = field(default_factory=bytearray, repr=False)
    scrollback_max: int = 65536
    state_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    on_dead: Optional[Callable[["Slave"], None]] = field(default=None, repr=False)
    #: Opaque ``BlockHandle`` returned by ``launcher.open_block``. Stored
    #: here so dead-slave / reconnect / state-change paths can repaint
    #: the block without the orchestrator threading the mapping
    #: separately. ``Any`` (not ``BlockHandle``) to avoid an import cycle.
    handle: Optional[Any] = field(default=None, repr=False)


@contextmanager
def _temporary_umask(mask: int) -> Iterator[None]:
    """Set process umask to ``mask`` for the duration of the block.

    Process-global; not thread-safe. The assertion enforces the
    invariant the rest of the orchestrator relies on (single-threaded
    slave setup on the event loop). If a future change starts running
    socket creation through ``asyncio.to_thread`` the assertion will
    fire and force introduction of a real lock rather than producing a
    silent race.
    """
    assert threading.current_thread() is threading.main_thread(), (
        "_temporary_umask is process-global; must be called on the main thread"
    )
    prev = os.umask(mask)
    try:
        yield
    finally:
        os.umask(prev)


def _trim_scrollback(buf: bytearray, max_size: int) -> None:
    """Trim ``buf`` so ``len(buf) <= max_size`` without splitting on an escape."""
    excess = len(buf) - max_size
    if excess <= 0:
        return
    nl = buf.find(b"\n", excess)
    if nl == -1:
        cut = excess
    else:
        cut = nl + 1
    del buf[:cut]


async def spawn_slave(
    index: int,
    host: str,
    sock_dir: str,
    ssh_args: list[str],
    login: Optional[str],
    token: str,
    initial_winsize: Optional[tuple[int, int, int, int]] = None,
) -> Slave:
    """Fork ``ssh <host>`` attached to a new PTY and return its :class:`Slave`."""
    import pty
    pty_master, pty_slave = pty.openpty()
    if initial_winsize is None:
        initial_winsize = (24, 80, 0, 0)
    rows, cols, xp, yp = initial_winsize
    set_winsize(pty_master, rows, cols, xp, yp)

    cmd = ["ssh", *ssh_args]
    if login:
        cmd += ["-l", login]
    cmd.append(host)

    pid = os.fork()
    if pid == 0:  # pragma: no cover - child path
        try:
            os.setsid()
            os.close(pty_master)
            os.dup2(pty_slave, 0)
            os.dup2(pty_slave, 1)
            os.dup2(pty_slave, 2)
            if pty_slave > 2:
                os.close(pty_slave)
            os.execvp(cmd[0], cmd)
        except Exception as exc:
            os.write(2, f"slave spawn failed: {exc}\n".encode())
            os._exit(127)
    os.close(pty_slave)

    sock_path = os.path.join(sock_dir, f"slave-{index}.sock")
    ctl_path = os.path.join(sock_dir, f"slave-{index}.ctl")
    token_path = os.path.join(sock_dir, f"slave-{index}.token")
    return Slave(
        index=index,
        host=host,
        sock_path=sock_path,
        ctl_sock_path=ctl_path,
        token=token,
        token_path=token_path,
        pty_master=pty_master,
        pid=pid,
    )


async def run_slave_bridge(slave: Slave) -> None:
    """Start the data + control sockets and the PTY-fanout task for ``slave``."""
    loop = asyncio.get_running_loop()

    async def handle_data_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if not await authenticate(reader, slave.token):
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return
        async with slave.state_lock:
            # Bound the writer fan-out so a leaked token can't be
            # used to attach indefinitely. Reject *after* AUTH so the
            # check itself isn't a probe oracle.
            if len(slave.connected_writers) >= slave.max_writers:
                log.warning(
                    "slave %d (%s): rejecting attach -- max_writers=%d reached",
                    slave.index, slave.host, slave.max_writers,
                )
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                return
            if slave.scrollback:
                writer.write(bytes(slave.scrollback))
            slave.connected_writers.append(writer)
        try:
            await writer.drain()
        except Exception:
            pass
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                if slave.dead:
                    break
                async with slave.write_lock:
                    _write_all(slave.pty_master, data)
        finally:
            try:
                slave.connected_writers.remove(writer)
            except ValueError:
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def handle_ctl_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if not await authenticate(reader, slave.token):
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                _apply_control_line(slave, line)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    with _temporary_umask(0o077):
        server = await asyncio.start_unix_server(handle_data_client, path=slave.sock_path)
        if not slave.ctl_sock_path:
            slave.ctl_sock_path = _derive_ctl_path(slave.sock_path)
        ctl_server = await asyncio.start_unix_server(handle_ctl_client, path=slave.ctl_sock_path)
    for path in (slave.sock_path, slave.ctl_sock_path):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    slave.server = server
    slave.ctl_server = ctl_server

    async def pty_to_sockets() -> None:
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        pipe = os.fdopen(slave.pty_master, "rb", buffering=0, closefd=False)
        transport, _ = await loop.connect_read_pipe(lambda: protocol, pipe)
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                async with slave.state_lock:
                    slave.scrollback.extend(data)
                    _trim_scrollback(slave.scrollback, slave.scrollback_max)
                    writers = list(slave.connected_writers)
                    for w in writers:
                        try:
                            w.write(data)
                        except Exception:
                            try:
                                slave.connected_writers.remove(w)
                            except ValueError:
                                pass
                for w in writers:
                    try:
                        await w.drain()
                    except Exception:
                        try:
                            slave.connected_writers.remove(w)
                        except ValueError:
                            pass
        finally:
            transport.close()
            slave.dead = True
            log.debug("slave %s (%s) PTY reached EOF -- marking dead", slave.index, slave.host)
            if slave.on_dead is not None:
                try:
                    slave.on_dead(slave)
                except Exception:  # pragma: no cover - defensive
                    log.exception("on_dead callback for slave %s raised", slave.index)

    slave.pty_reader_task = asyncio.create_task(pty_to_sockets())


def _derive_ctl_path(data_path: str) -> str:
    """Derive the control socket path from the data socket path."""
    if data_path.endswith(".sock"):
        return data_path[: -len(".sock")] + ".ctl"
    return data_path + ".ctl"


def _apply_control_line(slave: Slave, line: bytes) -> None:
    """Parse and apply a single control-socket line.

    Supported grammar::

        WINSZ <rows> <cols> [<xpixel> <ypixel>]
        BYE

    Anything else is ignored (with a debug log) so the protocol can grow
    without breaking older attach clients.
    """
    try:
        text = line.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError:
        return
    if not text:
        return
    parts = text.split()
    if parts[0] == "BYE" and len(parts) == 1:
        _handle_bye(slave)
        return
    if parts[0] != "WINSZ" or len(parts) not in (3, 5):
        log.debug("slave %s: unknown control line %r", slave.index, text)
        return
    try:
        rows = int(parts[1])
        cols = int(parts[2])
        xp = int(parts[3]) if len(parts) == 5 else 0
        yp = int(parts[4]) if len(parts) == 5 else 0
    except ValueError:
        log.debug("slave %s: malformed WINSZ %r", slave.index, text)
        return
    if rows <= 0 or cols <= 0:
        return
    set_winsize(slave.pty_master, rows, cols, xp, yp)


def _handle_bye(slave: Slave) -> None:
    """Treat ``BYE`` as user-initiated shutdown of this slave's session.

    Marks ``user_closed`` (so ``--reconnect`` skips retries) and sends
    ``SIGTERM`` to the remote ssh pid. The natural PTY-EOF chain in
    :func:`run_slave_bridge` then fires ``on_dead`` exactly once, so
    the status footer repaints and the launcher's set_color hook
    flips the block to DEAD without any extra plumbing.

    Idempotent: a second BYE on an already-dead slave is a no-op.
    """
    if slave.user_closed:
        return
    slave.user_closed = True
    log.debug("slave %s (%s) BYE received -- terminating ssh pid %d",
              slave.index, slave.host, slave.pid)
    if slave.pid > 0 and not slave.dead:
        try:
            os.kill(slave.pid, signal.SIGTERM)
        except OSError as exc:
            log.debug("slave %s SIGTERM failed: %s", slave.index, exc)


async def write_to_slave(slave: Slave, data: bytes) -> None:
    """Write ``data`` to ``slave``'s PTY iff the slave is alive and enabled."""
    if not slave.enabled or slave.dead:
        return
    async with slave.write_lock:
        try:
            _write_all(slave.pty_master, data)
        except OSError as exc:
            slave.dead = True
            log.debug("write to slave %s failed (%s) -- marking dead", slave.index, exc)


def _write_all(fd: int, data: bytes) -> None:
    """``os.write`` until every byte has been delivered (handles short writes)."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n == 0:
            break
        view = view[n:]


def shutdown_slave(slave: Slave) -> None:
    """Tear down a slave: stop servers, kill ssh, reap, close fds, unlink files."""
    if slave.server is not None:
        slave.server.close()
    if slave.ctl_server is not None:
        slave.ctl_server.close()
    if slave.pty_reader_task is not None and not slave.pty_reader_task.done():
        slave.pty_reader_task.cancel()
    if slave.pid > 0:
        try:
            os.kill(slave.pid, signal.SIGTERM)
        except OSError:
            pass
        try:
            os.waitpid(slave.pid, os.WNOHANG)
        except (ChildProcessError, OSError):
            pass
    try:
        os.close(slave.pty_master)
    except OSError:
        pass
    for path in (slave.sock_path, slave.ctl_sock_path, slave.token_path):
        if not path:
            continue
        try:
            os.unlink(path)
        except OSError:
            pass
