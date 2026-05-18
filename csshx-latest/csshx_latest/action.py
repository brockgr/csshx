"""One-shot action mode: broadcast a command, collect per-host output, exit.

Author: Aditya Kapadia.

Equivalent to the original Perl csshX's ``--remote_command`` option,
adapted for scripted use:

    csshx-latest --action 'uname -a' web0{1..3}

prints a per-host summary table on stdout and exits. There is no TUI,
no PTY, no Launcher — each host gets its own ``ssh <host> <command>``
subprocess, all run concurrently. The exit code is the maximum
per-host return code (so a single non-zero remote command surfaces).

Unlike interactive mode, we do *not* allocate a PTY; remote programs
that need one (vim, ncurses tools) won't behave correctly here. That's
intentional: action mode is for non-interactive ops scripts.
"""
from __future__ import annotations

import asyncio
import logging
import shlex
import sys
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

#: Per-host hard timeout. Avoids one stuck host stalling the whole run.
DEFAULT_TIMEOUT = 60.0


@dataclass
class ActionResult:
    """Per-host outcome of an action invocation."""

    host: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


async def _run_one(
    host: str,
    ssh_args: list[str],
    login: Optional[str],
    command: str,
    timeout: float,
) -> ActionResult:
    """Run ``ssh <host> <command>``; capture stdout/stderr/returncode."""
    argv = ["ssh", *ssh_args]
    if login:
        argv += ["-l", login]
    # ``-o BatchMode=yes`` so a host that would otherwise prompt for a
    # password fails fast instead of stalling the whole action run.
    if not any("BatchMode" in a for a in ssh_args):
        argv += ["-o", "BatchMode=yes"]
    argv += [host, command]

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        return ActionResult(host=host, returncode=-1, stdout="", stderr=f"spawn failed: {exc}")

    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:  # pragma: no cover - defensive
            pass
        return ActionResult(host=host, returncode=-1, stdout="", stderr="timeout", timed_out=True)

    return ActionResult(
        host=host,
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
    )


async def run_action(
    hosts: list[str],
    ssh_args: list[str],
    login: Optional[str],
    command: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> int:
    """Broadcast ``command`` over ssh to every host concurrently.

    Returns the max per-host return code (0 iff every host succeeded).
    Prints a header + per-host block + a final summary table to stdout.
    """
    if not hosts:
        sys.stderr.write("no hosts\n")
        return 2
    if not command.strip():
        sys.stderr.write("empty --action command\n")
        return 2

    results = await asyncio.gather(
        *(_run_one(h, ssh_args, login, command, timeout) for h in hosts)
    )
    _print_report(command, results)
    worst = max((r.returncode for r in results), default=0)
    # asyncio sometimes returns negative codes; clamp to 1 so the
    # process-exit value stays a meaningful shell-style number.
    return 0 if worst == 0 else (worst if worst > 0 else 1)


def _print_report(command: str, results: list[ActionResult]) -> None:
    """Render the per-host body + a compact final summary."""
    sys.stdout.write(f"# csshx-latest --action {shlex.quote(command)}\n")
    sys.stdout.write(f"# {len(results)} host(s)\n\n")
    for r in results:
        sys.stdout.write(f"--- {r.host} (rc={r.returncode}{' TIMEOUT' if r.timed_out else ''})\n")
        if r.stdout:
            sys.stdout.write(r.stdout if r.stdout.endswith("\n") else r.stdout + "\n")
        if r.stderr:
            for line in r.stderr.splitlines():
                sys.stdout.write(f"  [stderr] {line}\n")
        sys.stdout.write("\n")
    ok = sum(1 for r in results if r.returncode == 0)
    failed = len(results) - ok
    sys.stdout.write(f"# summary: {ok} ok, {failed} failed\n")
    sys.stdout.flush()


__all__ = ["ActionResult", "DEFAULT_TIMEOUT", "run_action"]
