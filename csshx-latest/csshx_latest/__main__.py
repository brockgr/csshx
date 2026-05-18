"""Command-line entry point for ``csshx-latest``.

Author: Aditya Kapadia.

Argument-parsing only -- the real work happens in
:func:`csshx_latest.orchestrator.run_master`.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from importlib import metadata
from typing import Optional

from csshx_latest.action import DEFAULT_TIMEOUT as ACTION_TIMEOUT, run_action
from csshx_latest.config import load_clusters
from csshx_latest.hosts import expand_hosts
from csshx_latest.launcher import available_launcher_names, detect_launcher
from csshx_latest.logging_setup import configure_logging
from csshx_latest.orchestrator import DEFAULT_MAX_HOSTS, run_master
from csshx_latest.tui import parse_command_key


def _version() -> str:
    """Look up the installed package version; ``unknown`` if not installed."""
    try:
        return metadata.version("csshx-latest")
    except metadata.PackageNotFoundError:
        return "unknown"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csshx-latest",
        description="Modern, terminal-agnostic cluster-SSH (csshX rewrite).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    parser.add_argument(
        "hosts",
        nargs="+",
        help=(
            "Hosts to ssh to. Supports brace expansion: 'web0{1..5}', "
            "'host-{a..c}', and 'api-{a,b,c}'. Cluster names from "
            "~/.config/csshx-latest/config.toml or ~/.csshrc are expanded too."
        ),
    )
    parser.add_argument(
        "--ssh-args",
        default="",
        help="Extra arguments forwarded to ssh, as a single quoted string.",
    )
    parser.add_argument("--login", default=None, help="Username (passed to ssh -l).")
    parser.add_argument(
        "--launcher",
        default="auto",
        choices=available_launcher_names(),
        help="Terminal backend (default: auto-detect).",
    )
    parser.add_argument(
        "--max-hosts",
        type=int,
        default=DEFAULT_MAX_HOSTS,
        help=f"Refuse to start above this many hosts (default: {DEFAULT_MAX_HOSTS}).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Abort if any host fails the tcp/22 preflight (default: skip them).",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip the tcp/22 reachability check entirely.",
    )
    parser.add_argument(
        "--reconnect",
        action="store_true",
        help="Re-spawn ssh with exponential backoff when a slave's connection drops.",
    )
    parser.add_argument(
        "--action",
        default=None,
        help=(
            "One-shot mode: run the given command via ssh on every host "
            "concurrently, print a per-host summary, and exit (no TUI). "
            "Equivalent to csshX's --remote_command."
        ),
    )
    parser.add_argument(
        "--action-timeout",
        type=float,
        default=ACTION_TIMEOUT,
        help=f"Per-host ssh timeout in --action mode (default: {ACTION_TIMEOUT}s).",
    )
    parser.add_argument(
        "--command-key",
        default="^T",
        help=(
            "Master command-mode prefix. Accepts ^X (Ctrl-X), ^A, ... "
            "or a raw byte like 0x14. Default: ^T."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Verbose logging to stderr.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Parse args and run the master event loop. Returns the exit code."""
    import shlex as _shlex

    parser = _build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.debug)

    clusters = load_clusters()
    expanded = expand_hosts(args.hosts, clusters=clusters)
    if not expanded:
        parser.error("no hosts after brace / cluster expansion")

    ssh_extra = _shlex.split(args.ssh_args) if args.ssh_args else []

    if args.action:
        # One-shot mode bypasses the TUI / launcher entirely.
        try:
            return asyncio.run(
                run_action(
                    expanded,
                    ssh_extra,
                    args.login,
                    args.action,
                    timeout=args.action_timeout,
                )
            )
        except KeyboardInterrupt:
            return 130

    try:
        command_key = parse_command_key(args.command_key)
    except ValueError as exc:
        parser.error(f"invalid --command-key: {exc}")

    launcher = detect_launcher(args.launcher)

    try:
        return asyncio.run(
            run_master(
                expanded,
                ssh_extra,
                args.login,
                launcher,
                max_hosts=args.max_hosts,
                strict_preflight=args.strict,
                reconnect=args.reconnect,
                skip_preflight=args.no_preflight,
                command_key=command_key,
            )
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
