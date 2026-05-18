"""WaveTerm launcher — opens and tiles blocks via the ``wsh`` CLI.

The ``wsh`` subcommand grammar has churned across WaveTerm releases —
``setlayout`` was renamed, ``tile`` came and went, etc. :meth:`tile`
tries the known incantations in order and caches the first one that
exits 0 for the rest of the run, so we don't pay the cost of probing
(or risk the user seeing stderr from a stale grammar) on every tile.
"""
from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from typing import Optional

from csshx_latest.launcher import BlockHandle, Color

log = logging.getLogger(__name__)

#: Ordered list of ``wsh`` subcommands that have meant "tile the current
#: tab" across WaveTerm versions. Probed left-to-right on first call.
_TILE_VARIANTS: tuple[tuple[str, ...], ...] = (
    ("setlayout", "tiled"),
    ("layout", "tiled"),
    ("tile",),
)

#: Hex backgrounds per state. WaveTerm's ``wsh setbg`` accepts a CSS
#: color; we use the same palette family as tmux/kitty so the visual
#: cue stays consistent across backends.
_BG_HEX: dict[Color, str] = {
    Color.ENABLED: "#0e3d0e",
    Color.DISABLED: "#3a3a3a",
    Color.DEAD: "#4d1414",
}

#: Fallback locations to search for the ``wsh`` binary when it isn't on PATH
#: (e.g. when csshx-latest is launched directly via a WaveTerm widget's
#: ``controller: cmd``, which execvp's without a login shell so PATH is the
#: bare system default).
_WSH_FALLBACK_PATHS: tuple[str, ...] = (
    os.path.expanduser("~/Library/Application Support/waveterm/bin/wsh"),
    "/Applications/Wave.app/Contents/Resources/app/bin/wsh",
)


def _resolve_wsh() -> str:
    """Locate ``wsh``, preferring PATH then known WaveTerm install locations.

    Returns the resolved absolute path or the literal string ``"wsh"`` as a
    last-resort so callers still get a meaningful FileNotFoundError if the
    binary genuinely isn't installed.
    """
    found = shutil.which("wsh")
    if found:
        return found
    for candidate in _WSH_FALLBACK_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "wsh"


def _swap_waveterm_token(wsh_path: str) -> bool:
    """Exchange ``WAVETERM_SWAPTOKEN`` for ``WAVETERM_JWT`` via ``wsh token``.

    WaveTerm widgets configured with ``controller: cmd`` (i.e. csshx-latest
    is the block's direct exec, no shell init) get only ``WAVETERM_SWAPTOKEN``
    in their env — never the post-swap ``WAVETERM_JWT`` that ``wsh run`` /
    ``wsh layout`` / ``wsh deleteblock`` / ``wsh settitle`` need to authenticate
    against the Wave daemon. Shell controllers swap it themselves via the
    ``wave-init`` script; under ``cmd`` we have to do it.

    ``wsh token <swaptoken> bash`` emits a bash init script of the form
    ``export WAVETERM_JWT="..." \n export WAVETERM_BLOCKID="..." \n …``.
    We parse those exports and merge them into ``os.environ`` so the
    subsequent ``wsh`` subprocesses inherit a fully authenticated env.

    Returns ``True`` iff we successfully extracted *and exported* at least
    ``WAVETERM_JWT``. No-ops (returning ``True``) when the env already has
    ``WAVETERM_JWT`` set (i.e. running under ``controller: shell`` or from
    an interactive WaveTerm prompt that already swapped).
    """
    if os.environ.get("WAVETERM_JWT"):
        return True  # already swapped — nothing to do
    swap = os.environ.get("WAVETERM_SWAPTOKEN")
    if not swap:
        return False
    try:
        proc = subprocess.run(
            [wsh_path, "token", swap, "bash"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("wsh token swap failed to invoke: %s", exc)
        return False
    if proc.returncode != 0:
        log.warning("wsh token swap exited %d: %s", proc.returncode, proc.stderr.strip())
        return False
    exported = _parse_bash_exports(proc.stdout)
    if "WAVETERM_JWT" not in exported:
        log.warning("wsh token output missing WAVETERM_JWT; got keys=%s", sorted(exported))
        return False
    os.environ.update(exported)
    return True


def _parse_bash_exports(script: str) -> dict[str, str]:
    """Pull ``export KEY=VALUE`` lines out of a bash init script.

    Uses :func:`shlex.split` (POSIX mode) to handle quoting so future
    JWT formats with escapes don't silently break the swap. Any line
    that doesn't parse as a single ``KEY=VALUE`` token after the
    ``export`` keyword is skipped.
    """
    out: dict[str, str] = {}
    for raw in script.splitlines():
        line = raw.strip()
        if not line.startswith("export "):
            continue
        body = line[len("export "):].lstrip()
        try:
            tokens = shlex.split(body, posix=True, comments=True)
        except ValueError:
            continue
        if not tokens:
            continue
        first = tokens[0]
        if "=" not in first:
            continue
        key, _, val = first.partition("=")
        if not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not key.replace("_", "").isalnum():
            continue
        out[key] = val
    return out


class WaveTermLauncher:
    """Open each block via ``wsh run`` and tile via the closest available subcommand."""

    name = "waveterm"

    def __init__(self) -> None:
        self._counter = 0
        self._tile_cmd: Optional[tuple[str, ...]] = None
        self._tile_probed = False
        # ``setbg`` was added in a recent ``wsh`` release. We probe once
        # (lazy on first :meth:`set_color` call) and cache the result so
        # older WaveTerm installs aren't spammed with unknown-command
        # errors. ``None`` = not probed; ``False`` = unsupported here;
        # ``True`` = supported, keep calling.
        self._setbg_supported: Optional[bool] = None
        self._wsh = _resolve_wsh()
        _swap_waveterm_token(self._wsh)

    def start(self, total: int) -> None:
        """No-op: WaveTerm tile decisions are made per call, not up-front."""

    @staticmethod
    def _run(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
        # capture=True by default so legacy wsh probes (setlayout/layout/tile,
        # deleteblock, settitle) don't spam the user's terminal on modern wsh
        # builds where those subcommands have been renamed or removed.
        return subprocess.run(args, check=False, capture_output=capture, text=True)

    def open_block(self, attach_cmd: list[str], title: str) -> BlockHandle:
        """Spawn a new Wave block running ``attach_cmd``.

        Logs ``wsh`` failures at WARNING — the original behavior silently
        swallowed stderr, which made it impossible to diagnose missing
        ``WAVETERM_*`` env vars or auth failures from a widget that runs
        csshx-latest under ``controller: cmd``.
        """
        self._counter += 1
        out = self._run([self._wsh, "run", "--", *attach_cmd], capture=True)
        if out.returncode != 0:
            log.warning(
                "wsh run for %s exited %d; stderr=%r stdout=%r",
                title, out.returncode, out.stderr, out.stdout,
            )
        block_id = ""
        if out.stdout:
            tail = out.stdout.strip().splitlines()
            if tail:
                block_id = tail[-1]
        return BlockHandle(
            backend=self.name,
            data={"block_id": block_id, "title": title, "index": self._counter},
        )

    def close_block(self, handle: BlockHandle) -> None:
        """Delete the block (no-op if we never captured an id)."""
        block_id = handle.data.get("block_id")
        if not block_id:
            return
        self._run([self._wsh, "deleteblock", "-b", block_id])

    def tile(self, handles: list[BlockHandle]) -> None:
        """Run the cached ``wsh`` tile subcommand; probe + cache on first call."""
        if not self._tile_probed:
            for attempt in _TILE_VARIANTS:
                r = self._run([self._wsh, *attempt])
                if r.returncode == 0:
                    self._tile_cmd = attempt
                    break
            self._tile_probed = True
            return  # The successful probe already tiled — don't double-run.

        if self._tile_cmd:
            self._run([self._wsh, *self._tile_cmd])

    def set_title(self, handle: BlockHandle, title: str) -> None:
        """Rename a block via ``wsh settitle``."""
        block_id = handle.data.get("block_id")
        if not block_id:
            return
        self._run([self._wsh, "settitle", "-b", block_id, title])

    def set_color(self, handle: BlockHandle, color: Color) -> None:
        """Tint the block background via ``wsh setbg`` (best-effort).

        Lazily probes once: if the local ``wsh`` doesn't ship ``setbg``,
        we cache that and silently no-op every subsequent call so we
        never burn a subprocess on a known-unsupported command.
        """
        block_id = handle.data.get("block_id")
        if not block_id:
            return
        if self._setbg_supported is False:
            return
        hex_bg = _BG_HEX.get(color)
        if not hex_bg:
            return
        out = self._run([self._wsh, "setbg", "-b", block_id, hex_bg])
        if out.returncode != 0:
            if self._setbg_supported is None:
                log.debug(
                    "wsh setbg unsupported (exit=%d, stderr=%r); disabling for this run",
                    out.returncode, (out.stderr or "").strip(),
                )
                self._setbg_supported = False
            return
        self._setbg_supported = True
