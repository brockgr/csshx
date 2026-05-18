"""Top-level orchestration: spawn slaves, open blocks, run TUI, tear down.

Author: Aditya Kapadia.

Lives in its own module (instead of being stuffed into ``master.py``)
so the broadcaster, the TUI, and the orchestration glue can each be
tested in isolation. ``master.py`` is a thin shim that re-exports the
same names for backward compatibility.

Async launcher dispatch
-----------------------

Concrete launchers are synchronous -- they ``subprocess.run`` an
``osascript`` / ``wsh`` / ``tmux`` command and block until it returns.
Calling them straight from the event loop freezes the TUI for the
duration of every block-open (e.g. ~200ms per host on macOS osascript
calls). ``_open_block`` / ``_close_block`` / ``_tile`` run these
through ``asyncio.to_thread`` so the loop stays responsive.

Preflight
---------

Before forking any ssh subprocess we open a 1s TCP connection to
``<host>:22`` for each host concurrently. Hosts that refuse or time
out are dropped (warn) or abort the run (``--strict``). Saves the user
from a screen full of dead panes when their VPN is down.

Reconnect
---------

With ``--reconnect``, a slave whose ssh exits gets re-spawned with
exponential backoff (1s, 2s, 4s, ..., capped at 30s; max 5 attempts).
The block stays put; we just rebind the PTY behind it.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import sys
import tempfile
import time
from typing import Optional

from csshx_latest.auth import make_token, write_token_file
from csshx_latest.broadcaster import Broadcaster
from csshx_latest.launcher import BlockHandle, Color, Launcher
from csshx_latest.slave import (
    Slave,
    run_slave_bridge,
    shutdown_slave,
    spawn_slave,
)
from csshx_latest.terminal import get_winsize
from csshx_latest.tui import KEY_COMMAND_PREFIX, render_status, tui_loop

log = logging.getLogger(__name__)

#: Hard ceiling on hosts per run. Above this the orchestrator refuses
#: unless ``--max-hosts`` was raised. 16 keeps the most extreme accidents
#: (``web{1..1000}`` typos) from forking until fd exhaustion.
DEFAULT_MAX_HOSTS = 16

#: TCP connect timeout for the preflight check (seconds).
PREFLIGHT_TIMEOUT = 1.0

#: ssh-options injected when the user didn't override -o StrictHostKeyChecking.
#: ``accept-new`` auto-trusts unknown hosts but still rejects mismatches,
#: so first-connect prompts don't fan out across every broadcast slave.
_DEFAULT_SSH_OPTS = ("-o", "StrictHostKeyChecking=accept-new")

#: Reconnect schedule (seconds between attempts). After the last entry we stop.
_RECONNECT_BACKOFF = (1.0, 2.0, 4.0, 8.0, 16.0)


def make_socket_dir() -> str:
    """Create a 0700 directory for slave sockets + token files."""
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    base = xdg if xdg and os.path.isdir(xdg) else tempfile.gettempdir()
    path = os.path.join(base, f"csshx-{os.getpid()}")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def attach_command(sock_path: str, token_path: str) -> list[str]:
    """Build the attach command for a terminal block.

    Always uses the bundled stdlib attach client. It handles the dual
    data + control socket protocol (SIGWINCH per-block resize lives on
    the control channel) which a single ``socat`` invocation cannot.
    The token is read from ``token_path`` at runtime so the literal
    token never appears in any process's argv.
    """
    return [sys.executable, "-m", "csshx_latest.attach", sock_path, token_path]


def maybe_inject_strict_host_key_opts(ssh_args: list[str]) -> list[str]:
    """Prepend ``-o StrictHostKeyChecking=accept-new`` if the user didn't set it.

    Detecting "user set it" means: any token after ``-o`` mentions
    ``StrictHostKeyChecking``. We don't try to parse arbitrary ssh-arg
    grammars; we just look for the substring.
    """
    if any("StrictHostKeyChecking" in a for a in ssh_args):
        return list(ssh_args)
    return [*_DEFAULT_SSH_OPTS, *ssh_args]


async def _open_block(launcher: Launcher, attach_cmd: list[str], title: str) -> BlockHandle:
    return await asyncio.to_thread(launcher.open_block, attach_cmd, title)


async def _close_block(launcher: Launcher, handle: BlockHandle) -> None:
    try:
        await asyncio.to_thread(launcher.close_block, handle)
    except Exception:
        log.exception("close_block failed for %s", handle)


async def _tile(launcher: Launcher, handles: list[BlockHandle]) -> None:
    if not handles:
        return
    try:
        await asyncio.to_thread(launcher.tile, handles)
    except Exception as exc:
        log.warning("tile() failed: %s", exc)


async def _start_launcher(launcher: Launcher, total: int) -> None:
    try:
        await asyncio.to_thread(launcher.start, total)
    except Exception as exc:
        log.warning("launcher.start failed: %s", exc)


def _color_for(slave: Slave) -> Color:
    """Map slave state to its visual color (mirrors original csshX)."""
    if slave.dead:
        return Color.DEAD
    if slave.enabled:
        return Color.ENABLED
    return Color.DISABLED


def _should_reconnect(slave: Slave, reconnect_enabled: bool) -> bool:
    """Return True iff a dead slave should be auto-respawned.

    Two conditions both have to hold:

    * the user passed ``--reconnect`` on the CLI, AND
    * the slave was NOT killed by the user closing its visible terminal
      block. A ``BYE`` on the control socket flips ``user_closed`` and
      we honor that: the user explicitly ended this session, so resurrecting
      it would be surprising.
    """
    return reconnect_enabled and not slave.user_closed


async def _set_color(launcher: Launcher, slave: Slave) -> None:
    """Push the slave's current state color to its block (best-effort)."""
    if slave.handle is None:
        return
    try:
        await asyncio.to_thread(launcher.set_color, slave.handle, _color_for(slave))
    except Exception as exc:
        log.debug("set_color slave %d failed: %s", slave.index, exc)


async def _set_title(launcher: Launcher, slave: Slave, title: str) -> None:
    """Push a per-block title rename (best-effort)."""
    if slave.handle is None:
        return
    try:
        await asyncio.to_thread(launcher.set_title, slave.handle, title)
    except Exception as exc:
        log.debug("set_title slave %d failed: %s", slave.index, exc)


def _master_winsize() -> tuple[int, int, int, int]:
    """Best-effort: read the controlling tty's current size for slave init."""
    fd: Optional[int] = None
    try:
        if sys.stdin.isatty():
            fd = sys.stdin.fileno()
    except (AttributeError, ValueError, OSError):
        fd = None
    if fd is None:
        return (24, 80, 0, 0)
    return get_winsize(fd)


async def _probe_host(host: str, port: int = 22, timeout: float = PREFLIGHT_TIMEOUT) -> bool:
    """Return True if a TCP connection to ``host:port`` opens within ``timeout``.

    The host token may include a ``user@`` prefix; strip it for the
    connect. Hostnames that don't resolve count as unreachable.
    """
    target = host.split("@", 1)[1] if "@" in host else host
    try:
        coro = asyncio.open_connection(target, port)
        reader, writer = await asyncio.wait_for(coro, timeout=timeout)
    except (OSError, asyncio.TimeoutError, socket.gaierror):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    return True


async def preflight_hosts(hosts: list[str], strict: bool) -> list[str]:
    """Drop unreachable hosts (warn) or abort the run (``strict``).

    Probes every host concurrently. With ``strict=True`` an unreachable
    host raises ``RuntimeError`` so the master never starts. With
    ``strict=False`` the unreachable hosts are skipped and the rest
    proceed.
    """
    if not hosts:
        return hosts
    results = await asyncio.gather(*(_probe_host(h) for h in hosts))
    ok = [h for h, alive in zip(hosts, results) if alive]
    dead = [h for h, alive in zip(hosts, results) if not alive]
    for h in dead:
        log.warning("preflight: %s is unreachable on tcp/22", h)
        sys.stderr.write(f"warning: {h} unreachable on tcp/22 -- skipping\n")
    if dead and strict:
        raise RuntimeError(f"--strict: refusing to start, unreachable: {' '.join(dead)}")
    return ok


def _kill_and_reap(pid: int, grace: float = 2.0) -> None:
    """Poll-reap a child after SIGTERM; SIGKILL if the grace window expires.

    Replaces the unbounded ``waitpid(pid, 0)`` that could hang forever
    if ssh refused to exit.
    """
    if pid <= 0:
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        except OSError:
            return
        if done != 0:
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return
    try:
        os.waitpid(pid, 0)
    except (ChildProcessError, OSError):
        pass


async def _attempt_reconnect(
    slave: Slave,
    ssh_args: list[str],
    login: Optional[str],
    winsize: tuple[int, int, int, int],
    launcher: Optional[Launcher] = None,
) -> None:
    """Re-spawn ssh for a dead slave with exponential backoff.

    When ``launcher`` is passed, the block's title is updated to
    ``<host> [reconnecting]`` during retry attempts and restored to
    ``<host>`` on success — same visual feedback the original csshX
    provided via its master-status line.
    """
    if launcher is not None:
        await _set_title(launcher, slave, f"{slave.host} [reconnecting]")
        await _set_color(launcher, slave)  # DEAD because slave.dead is True
    for attempt, delay in enumerate(_RECONNECT_BACKOFF, start=1):
        log.info("reconnect %s: attempt %d in %.1fs", slave.host, attempt, delay)
        await asyncio.sleep(delay)
        if not await _probe_host(slave.host):
            log.info("reconnect %s: still unreachable", slave.host)
            continue
        try:
            fresh = await spawn_slave(
                index=slave.index,
                host=slave.host,
                sock_dir=os.path.dirname(slave.sock_path),
                ssh_args=ssh_args,
                login=login,
                token=slave.token,
                initial_winsize=winsize,
            )
        except Exception as exc:
            log.warning("reconnect %s: spawn failed: %s", slave.host, exc)
            continue
        slave.pty_master = fresh.pty_master
        slave.pid = fresh.pid
        slave.dead = False
        write_token_file(slave.token_path, slave.token)
        try:
            await run_slave_bridge(slave)
        except Exception as exc:
            log.warning("reconnect %s: bridge failed: %s", slave.host, exc)
            continue
        if launcher is not None:
            await _set_title(launcher, slave, slave.host)
            await _set_color(launcher, slave)
        sys.stderr.write(f"\r[csshx-latest] {slave.host} reconnected\r\n")
        sys.stderr.flush()
        return
    log.info("reconnect %s: giving up after %d attempts", slave.host, len(_RECONNECT_BACKOFF))


async def run_master(
    hosts: list[str],
    ssh_args: list[str],
    login: Optional[str],
    launcher: Launcher,
    *,
    max_hosts: int = DEFAULT_MAX_HOSTS,
    strict_preflight: bool = False,
    reconnect: bool = False,
    skip_preflight: bool = False,
    command_key: bytes = KEY_COMMAND_PREFIX,
) -> int:
    """Top-level entry: spawn slaves, run the TUI, tear down on exit."""
    if len(hosts) > max_hosts:
        sys.stderr.write(
            f"refusing to start: {len(hosts)} hosts exceeds --max-hosts={max_hosts}. "
            "Raise the cap explicitly or trim the host list.\n"
        )
        return 2

    if not skip_preflight:
        try:
            hosts = await preflight_hosts(hosts, strict_preflight)
        except RuntimeError as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
        if not hosts:
            sys.stderr.write("no reachable hosts after preflight\n")
            return 2

    ssh_args = maybe_inject_strict_host_key_opts(ssh_args)

    sock_dir = make_socket_dir()
    bcast = Broadcaster()
    handles: list[BlockHandle] = []
    winsize = _master_winsize()
    loop = asyncio.get_running_loop()

    # Live re-paint on every toggle (Ctrl-T 1..9 / Ctrl-T b). The
    # callback is fired from the TUI's event-loop thread, so a
    # bare ``create_task`` is enough — no thread bridge needed.
    def _on_state_change(s: Slave) -> None:
        try:
            loop.create_task(_set_color(launcher, s))
        except RuntimeError:  # pragma: no cover - loop closed
            pass

    bcast.on_state_change = _on_state_change

    def on_slave_dead(s: Slave) -> None:
        if s.user_closed:
            log.info("slave %d (%s) exited (user closed block)", s.index, s.host)
        else:
            log.info("slave %d (%s) exited", s.index, s.host)
        try:
            render_status(bcast)
        except Exception:  # pragma: no cover - defensive
            pass
        # PTY reader runs on the loop thread, so this fires on the loop;
        # schedule the repaint without threadsafe bridging.
        try:
            loop.create_task(_set_color(launcher, s))
        except RuntimeError:  # pragma: no cover - loop closed
            pass
        # User-initiated close (via ``BYE`` on the control socket) must
        # NOT trigger a reconnect — the user just told us this session
        # is done. Without this guard, --reconnect would silently
        # re-spawn ssh and the slave the user just closed would resurrect.
        if _should_reconnect(s, reconnect):
            asyncio.run_coroutine_threadsafe(
                _attempt_reconnect(s, ssh_args, login, winsize, launcher), loop
            )

    await _start_launcher(launcher, len(hosts))

    try:
        for i, host in enumerate(hosts, start=1):
            token = make_token()
            slave = await spawn_slave(
                index=i,
                host=host,
                sock_dir=sock_dir,
                ssh_args=ssh_args,
                login=login,
                token=token,
                initial_winsize=winsize,
            )
            slave.on_dead = on_slave_dead
            write_token_file(slave.token_path, token)
            await run_slave_bridge(slave)
            bcast.add(slave)
            attach = attach_command(slave.sock_path, slave.token_path)
            handle = await _open_block(launcher, attach, host)
            slave.handle = handle
            handles.append(handle)
            await _tile(launcher, handles)
            # Paint the initial ENABLED color now that we have a handle.
            await _set_color(launcher, slave)

        await _tile(launcher, handles)
        await tui_loop(bcast)
    finally:
        await asyncio.gather(
            *(_close_block(launcher, h) for h in handles),
            return_exceptions=True,
        )
        for s in bcast.slaves:
            shutdown_slave(s)
        for s in bcast.slaves:
            _kill_and_reap(s.pid)
        try:
            os.rmdir(sock_dir)
        except OSError as exc:
            log.debug("rmdir %s skipped: %s", sock_dir, exc)
    return 0


__all__ = [
    "Broadcaster",
    "DEFAULT_MAX_HOSTS",
    "attach_command",
    "make_socket_dir",
    "maybe_inject_strict_host_key_opts",
    "preflight_hosts",
    "render_status",
    "run_master",
    "tui_loop",
]


_signal = signal
