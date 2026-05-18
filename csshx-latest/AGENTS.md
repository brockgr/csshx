# AGENTS.md

Guide for any contributor (human or AI agent) picking up `csshx-latest`.

Author: Aditya Kapadia.

---

## Project at a glance

A modern, terminal-agnostic cluster-SSH tool — a rewrite of the Perl
[csshX](https://github.com/brockgr/csshx). Async Python 3.9+, stdlib
only (no runtime deps), real PTYs, pluggable terminal launchers, token-
authenticated UNIX sockets, with master + slaves tiled together on
every backend that can address the master window.

**Status:** v0.2.0 Beta. 266 tests passing in ~3.8s. Safe for daily
use on trusted networks with up to 16 hosts (raise `--max-hosts` for
more).

```
csshx_latest/
├── __main__.py        CLI entry, argparse (also: --action, --command-key)
├── orchestrator.py    Top-level run loop, preflight, reap, reconnect
├── master.py          Back-compat shim re-exporting orchestrator names
├── slave.py           One ssh subprocess + PTY + data/control sockets
├── broadcaster.py     Routes master keystrokes to enabled slaves
├── tui.py             Raw-mode stdin reader + Ctrl-T command mode
├── auth.py            32-byte hex token + AUTH handshake + token file
├── attach.py          Stdlib attach client (run by spawned blocks)
├── terminal.py        raw-mode CM, winsize ioctls, xterm.js mode resets
├── hosts.py           Brace expansion + cluster alias resolution
├── config.py          ~/.config/csshx-latest/config.toml or ~/.csshrc
├── launcher.py        Launcher Protocol + auto-detect + Color enum
├── logging_setup.py   stderr formatter
├── action.py          One-shot --action mode (fan-out ssh exec)
└── launchers/         One file per backend
    ├── waveterm.py
    ├── tmux.py
    ├── iterm2.py
    ├── apple_terminal.py
    ├── kitty.py
    ├── wezterm.py
    └── manual.py
```

---

## Conventions

- **Authorship:** every module starts with `Author: Aditya Kapadia.` in
  the docstring. New modules follow the same pattern.
- **No AI / process narration** in comments. Comments explain *why*,
  not *what changed*.
- **Files stay under 600 LOC.** Current largest is `orchestrator.py`
  at ~430. Split before crossing 600.
- **Zen of Python.** Flat over nested; explicit over implicit; one
  obvious way to do it.
- **Stdlib only at runtime.** Tests may use pytest; nothing else.
- **All sync subprocess calls run through `asyncio.to_thread`** when
  invoked from the event loop (osascript, tmux, wsh can block 100ms+).
- **Launcher subprocesses use `capture=True` by default** so probes
  for legacy / removed CLI subcommands don't leak stderr into the
  user's terminal.

### Test layout

- `tests/test_<unit>.py` — pure unit tests with mocked subprocess.
- `tests/test_slave_bridge.py` — pipe-pair smoke tests of the bridge.
- `tests/test_slave_control_socket.py` — real PTY + control socket.
- `tests/test_integration_pty.py` — real PTY + fork + cat as fake ssh.
- `tests/test_launcher_conformance.py` — Protocol shape + signature
  arity + every `Color` state, parametrized over `_LAUNCHERS`.
- `tests/conftest.py` — shared fixtures (`short_socket_dir`,
  `harmless_pid`, `stdio_devnull`).

Run: `uv run pytest -q`. Target: < 4 seconds wall-clock.

---

## DONE in v0.2.0

### Critical fixes (production safety)

| ID | What | Where |
| --- | --- | --- |
| C1 | Bounded reap with SIGKILL fallback (no more hang on shutdown) | `orchestrator._kill_and_reap` |
| C2 | `StrictHostKeyChecking=accept-new` injected unless user overrode | `orchestrator.maybe_inject_strict_host_key_opts` |
| C3 | `--max-hosts 16` cap to prevent fork-bomb typos | `orchestrator.run_master` + `__main__` |
| C4 | Broadcaster logs per-slave write failures (no more silent drops) | `broadcaster.broadcast` |
| C5 | WaveTerm export parser uses `shlex.split` (all quote forms safe) | `launchers.waveterm._parse_bash_exports` |

### Must-have features

| ID | What | Where |
| --- | --- | --- |
| M1 | Per-slave focus toggle: `Ctrl-T 1..9` direct, `Ctrl-T i <num>` prompt | `tui._handle_command_byte`, `tui._consume_index_prompt_byte` |
| M2 | iTerm2 + Terminal.app actually close panes on shutdown (track ids) | `launchers.iterm2`, `launchers.apple_terminal` |
| M3 | `Launcher.start(total)` lifecycle hook replaces env smuggle | `launcher.Launcher`, every concrete launcher |
| M4 | TOML or `~/.csshrc` cluster aliases (recursive, cycle-safe) | `config.py` + `hosts.expand_hosts` |
| M5 | Concurrent tcp/22 preflight, `--strict` and `--no-preflight` flags | `orchestrator.preflight_hosts` |
| M6 | Per-block SIGWINCH via dedicated control socket (`WINSZ rows cols`) | `slave._apply_control_line`, `attach._push_winsize` |
| M7 | Real-PTY integration test with cat as fake ssh | `tests/test_integration_pty.py` |
| M8 | `--reconnect` with exponential backoff (1, 2, 4, 8, 16 s) | `orchestrator._attempt_reconnect` |

### Extras delivered along the way

- Alphabetic brace expansion: `host-{a..c}`.
- Tile-after-every-spawn so panes stay balanced as blocks are added.
- Stdlib attach client is now the default (socat couldn't handle the
  dual data + control socket protocol).
- Always-on per-master SIGWINCH propagation joined by per-block
  SIGWINCH via the control socket.
- `pyproject.toml` bumped to `0.2.0`, status `4 - Beta`, author Aditya.
- README rewritten with the new flag table, cluster examples, and key
  bindings.

### Polish landed in v0.2.0 (priority items 1–15)

| # | Where |
| --- | --- |
| 1. `set_color` hook wired to ENABLED/DISABLED/DEAD per block | `launcher.Color`, every launcher's `set_color`, `orchestrator._color_for` |
| 2. `--action 'uptime' h1 h2` one-shot fan-out + summary | `action.py`, `__main__.main` |
| 3. Backend conformance harness (skip when binary not on PATH) | `tests/test_launcher_conformance.py` |
| 4. `Slave.max_writers` cap on the data socket | `slave.handle_data_client` |
| 5. Python floor widened to 3.9 (`asyncio.to_thread` is the floor) | `pyproject.toml` |
| 6. Startup help hint: "press Ctrl-T for the command menu" | `tui.tui_loop` |
| 7. ANSI-colored status footer (green/red/dim, tty-only) | `tui.render_status` |
| 8. `--command-key ^T / 0x14 / single-char` configurable prefix | `tui.parse_command_key`, `__main__`, `tui._handle_command_byte` |
| 9. Cancel-on-printable echoes the byte back into broadcast | `tui._handle_command_byte` |
| 10. `master.py` shim trimmed to a plain re-export header | `master.py` |
| 11. `[project.urls]` filled in | `pyproject.toml` |
| 12. `_temporary_umask` now asserts main-thread instead of "trust me" | `slave._temporary_umask` |
| 13. WaveTerm `wsh token` still bash-parsed; tracked for JSON later | `launchers/waveterm.py` (no change) |
| 14. `--reconnect` retitles block "[reconnecting]" + paints DEAD | `orchestrator._attempt_reconnect` |
| 15. `slave.py` docstring documents WINSZ + reserved future verbs | `slave.py` |

### Polish landed post-v0.2.0

| # | What | Where |
| --- | --- | --- |
| 16. **Master + slaves are tiled together** on Terminal.app and iTerm2 — previously only slaves were rearranged | `launchers.apple_terminal.AppleTerminalLauncher.{start,tile}`, `launchers.iterm2.ITerm2Launcher.open_block` |
| 17. **Terminal.app windows no longer slide under the Dock** — tiling now happens inside a "usable area" rectangle (desktop minus Dock + edge inset) and each cell has a small gap so neighbours aren't flush | `launchers.apple_terminal.{DOCK_RESERVE, EDGE_MARGIN, WINDOW_GAP, _get_usable_bounds, tile}` |
| 18. **Visible broadcast-state color** on Apple Terminal and iTerm2 — `set_color` now writes the tab/session's `background color` (16-bit RGB) on every toggle. Previously both backends were silent no-ops, so the user couldn't see ENABLED/DISABLED/DEAD changes | `launchers.apple_terminal.{_TAB_BG, set_color}`, `launchers.iterm2.{_SESSION_BG, set_color}` |
| 19. **Closing a slave's terminal block now actually ends the session** — attach client emits a new `BYE` control verb on SIGHUP/SIGTERM/SIGINT and on stdin EOF. The master flips `slave.user_closed`, SIGTERMs the ssh pid, the PTY-EOF chain fires `on_dead` exactly once, the status footer updates, the block repaints DEAD, and `--reconnect` honors the close (no respawn) | `slave.{Slave.user_closed, _handle_bye, _apply_control_line}`, `attach.{_send_bye, on_terminating_signal, main}`, `orchestrator._should_reconnect` |

#### Master co-tiling — implementation notes

- **Terminal.app** (`AppleTerminalLauncher`): each block opens in its
  own Terminal window, so the master TUI's window was previously
  excluded from `tile()`'s grid. Fix: `start(total)` runs
  `tell application "Terminal" to return id of front window` and
  stores the result in `self._master_window_id`. `tile()` prepends
  that id to the cells list before computing the grid, so the master
  ends up at cell 0 (top-left). If the capture fails (Finder denied,
  AppleScript returns non-digit output), the master id is left empty
  and `tile()` falls back to the v0.2.0 slaves-only layout. The
  capture has to run in `start()`, not the constructor — by the time
  the first `open_block` `activate`s Terminal, the front window has
  shifted to the new slave.
- **iTerm2** (`ITerm2Launcher`): v0.2.0 created a new window for the
  first block (`create window with default profile command "…"`),
  parking the master TUI in a sibling window iTerm2's auto-tile
  couldn't reach. Fix: every block — including the first — now uses
  `split vertically with default profile command "…"` of
  `current session of current window` (the master's session). iTerm2
  rebalances all panes on every split, so master + slaves shrink in
  lockstep. The `_first` flag is gone.
- **tmux** ≤ `PANE_THRESHOLD` (4) hosts: master is one of the panes
  in the active window; `select-layout tiled` already includes it.
  No change needed.
- **tmux** > `PANE_THRESHOLD` hosts: master stays in its original
  window; slaves get a dedicated `csshx` window so they don't get
  squeezed into vertical ribbons. This is by design — adding the
  master back into the slave window would defeat the threshold.
- **WezTerm**: every block is `wezterm cli spawn` from the active
  pane (the master); WezTerm balances them automatically. No change
  needed.
- **WaveTerm**: `wsh setlayout tiled` rearranges the whole tab
  (master + every block opened with `wsh run`). No change needed.
- **Kitty**: slaves are tabs (`@ launch --type=tab`), the master is
  in its own tab. Tabs are visually separate by design. No co-tiling.
- **Manual**: prints attach commands; the user arranges them in
  whatever terminal they like.

#### Terminal.app sizing — Dock reservation + per-cell gap

`_get_desktop_bounds()` returns Finder's `bounds of window of desktop`,
which is the FULL screen rectangle — Finder does NOT subtract the
Dock. Tiling to that rectangle slides the bottom row of windows under
the Dock. Fix: `_get_usable_bounds()` shrinks the rectangle by:

- `EDGE_MARGIN = 8` on every side (small inset so windows don't sit
  flush against the menu bar or screen borders).
- `DOCK_RESERVE = 90` on the bottom (covers the default Dock size +
  buffer). We don't query the actual Dock size because that requires
  Accessibility permission via System Events and can prompt the user
  the first time.

`tile()` then divides the usable rectangle into a near-square
`rows × cols` grid and shrinks each cell by `WINDOW_GAP = 6` on the
right and bottom so adjacent windows have visible breathing room. The
math is in `csshx_latest/launchers/apple_terminal.py:_get_usable_bounds`
and `:tile`. The constants are deliberately module-level so a future
"too cramped on a 4K display" tweak is a one-line change.

#### User-closed slave — the `BYE` control verb

ssh runs in the master's PTY, NOT inside the visible terminal block.
That decoupling is what lets attach clients reconnect, but it has a
nasty corollary: closing a slave's Terminal.app window / iTerm2 pane
/ tmux pane just kills the attach client; ssh keeps running until
something else ends it. The user sees the visible block disappear but
the status footer keeps reporting the slave as "alive" — stale and
confusing.

Fix (post-v0.2.0): a new `BYE` control verb. The wiring lives in
three files:

- `csshx_latest/attach.py:_send_bye` writes `BYE\n` on the control
  socket. It's invoked from (a) signal handlers for `SIGHUP` /
  `SIGTERM` / `SIGINT` (Terminal.app, iTerm2, systemd / launchctl,
  Ctrl-C), (b) the stdin-EOF branch (tmux `kill-pane`, Kitty tab
  close), and (c) the `KeyboardInterrupt` fall-through. A `bye_sent`
  flag keeps it idempotent so the master never sees more than one
  `BYE` from a single client. `_send_bye` swallows `OSError` so it's
  safe to call from a signal handler even if the control socket is
  half-closed.

- `csshx_latest/slave.py:_handle_bye` is the master side. It sets
  `slave.user_closed = True` and sends `SIGTERM` to `slave.pid`. We
  deliberately do NOT call `on_dead` directly — instead we let ssh
  exit, the PTY return EOF, and the existing `pty_to_sockets` finally
  block fire `on_dead` exactly once. That keeps a single path for
  every kind of slave death (natural ssh exit, network drop, BYE).
  Idempotent: a second BYE is a no-op.

- `csshx_latest/orchestrator.py:_should_reconnect` is the new gate.
  Both conditions have to hold: `--reconnect` is on AND `user_closed
  is False`. Without this guard, BYE would mark the slave dead, the
  existing reconnect path would re-spawn ssh one backoff cycle later,
  and the slave the user just closed would silently resurrect.

Closing the master TUI's own window is unaffected — that's the
process running the TUI itself, not an attach client, so no `BYE` is
ever sent.

#### Apple Terminal / iTerm2 color — `background color` of tab/session

Apple Terminal does NOT expose a `color` attribute on tabs, but it
DOES expose `background color` (a 16-bit RGB triple). Same for
iTerm2 sessions. We write that property on every `set_color` call.

The palette is deliberately low-saturation — earlier iterations used
full-strength `(0, 24576, 0)` green / `(24576, 0, 0)` red which were
visually fatiguing after a few minutes. Current values:

- ENABLED  → dim sage   `(12288, 17408, 14336)` — faint cool green
- DISABLED → dim slate  `(14336, 14336, 15360)` — barely-tinted neutral
- DEAD     → dim mauve  `(18432, 13312, 14336)` — faint warm red

All three live in roughly the same lightness band so foreground text
contrast stays consistent across states. The palette lives at module
scope (`_TAB_BG` / `_SESSION_BG`) so retuning is a one-line change.
Tests pin the *contract* (distinct entries, valid 16-bit range,
present for every Color state) without pinning the specific hex values. The write is per-
tab/per-session and does NOT modify the user's saved profile. Both
implementations no-op silently when the captured id is missing
(degraded handle) and wrap the actual write in an AppleScript `try`
block so a stale id during shutdown can't break callers.

### Test coverage delta

| | Pre-v0.2.0 | v0.2.0 | Post-co-tiling | Post-sizing+color | Post-BYE | Post-palette |
| --- | --- | --- | --- | --- | --- | --- |
| Test files | 16 | 26 | 26 | 26 | 26 | 26 |
| Tests | 111 | 244 | 266 | 270 | 280 | 282 |
| Wall clock | 0.45s | ~3.7s | ~3.8s | ~3.8s | ~3.8s | ~3.8s |

New test modules in v0.2.0: `test_config.py`, `test_orchestrator.py`,
`test_tui_focus_toggle.py`, `test_slave_control_socket.py`,
`test_integration_pty.py`, `test_waveterm_export_parser.py`,
`test_action.py`, `test_command_key.py`, `test_color_state.py`,
`test_status_footer.py`, `test_slave_max_writers.py`,
`test_launcher_conformance.py`.

Post-co-tiling additions: 4 new tests in `test_launcher_apple_terminal.py`
covering `start()` capture, non-digit rejection, master placed at cell 0,
slaves-only fallback when capture fails, and single-master-fills-desktop
edge case.

Post-sizing+color additions: existing Apple Terminal bounds-assertion
tests were updated to the new usable-rectangle math (cells now sit
inside `(EDGE_MARGIN, EDGE_MARGIN, screen_w - EDGE_MARGIN, screen_h -
DOCK_RESERVE - EDGE_MARGIN)` with a `WINDOW_GAP` shrink per cell). The
old "set_color is a silent no-op for every state" test was replaced
with `test_set_color_emits_background_color_per_state` (verifies the
matched window id and the per-state RGB triple appear in the
AppleScript body) plus `test_set_color_is_noop_without_window_id`
(verifies the safety fallback). A new `test_usable_bounds_subtracts_
dock_and_edge_margins` pins the helper directly. iTerm2 gained
`test_set_color_writes_session_background_per_state` and
`test_set_color_is_noop_without_session_id` for the parallel change.

---

## PENDING

All v0.2.0 priority items 1–15 above are now DONE, plus the post-v0.2.0
master co-tiling, Dock-aware sizing, per-tab/session color hooks, and
user-closed-block → BYE → graceful slave shutdown. Nothing blocking
daily use. Next pass ideas:

- **Adopt 3.11+ `TaskGroup`** behind a version check to parallelize
  the ~50ms-per-host launcher round-trips during startup.
- **Switch WaveTerm `wsh token` parsing to a JSON variant** if/when
  WaveTerm exposes one, retiring the `shlex.split` of bash output.
- **Persist the broadcast-toggle state across runs** so a habitual
  "Ctrl-T b once" user starts with everyone OFF.
- **Per-block scrollback divider** on reconnect so users can see where
  the new ssh session began.
- **Optional dedicated master strip** for Terminal.app — instead of
  giving the master one cell of the grid, reserve a bottom strip for
  it (matching the original Perl csshX layout). Today the master gets
  equal real estate at cell 0.

---

## Architecture notes (for future spelunkers)

### Two sockets per slave

Each slave exposes two AUTH-gated UNIX sockets:

- `slave-N.sock` (data): bidirectional bytes. PTY output fans out;
  client keystrokes flow in. Per-slave scrollback (64 KiB cap, trimmed
  on newline boundaries) replays to every newly authenticated client.
- `slave-N.ctl` (control): line-oriented. Today only `WINSZ rows cols
  [xpixel ypixel]`. Future: `BELL`, `FOCUS`, etc. Unknown verbs are
  silently dropped so older attach clients survive newer slaves.

The stdlib attach client (`csshx_latest.attach`) opens both;
socat-based attach is no longer supported because it can't multiplex
two sockets cleanly.

### Tokens never appear in argv

`make_token()` returns a fresh 32-byte hex string per slave per run.
`write_token_file` creates the file under `O_CREAT | O_WRONLY | O_TRUNC`
with mode `0600`, then re-chmods (in case the file pre-existed). The
spawned attach process gets the token's *file path* on argv, never the
token itself, so `ps` listings from other UIDs can't harvest it.
`authenticate()` uses `secrets.compare_digest` for the comparison and
caps the handshake at `HANDSHAKE_TIMEOUT = 2.0` seconds.

### Why an `asyncio.Lock` per slave

The master broadcaster AND the focused block can both write into the
same PTY simultaneously. Without a per-slave `write_lock`, an ANSI
escape sequence from the broadcaster could interleave with a keystroke
from the block, producing garbage on the remote shell. The lock makes
each write atomic at the PTY level.

### Why a `state_lock` separately

The PTY reader task does *three* things every iteration: extend
scrollback, snapshot the current writers, and queue the chunk to each.
The `state_lock` makes those atomic with respect to a new client
authenticating and joining the writer list, so we can never duplicate
or drop a chunk. It also guards the `max_writers` cap on the data
socket so a leaked token can't accumulate attaches faster than the
reader notices.

### Reconnect path

`on_dead` callback fires from inside the PTY reader task when ssh
exits. With `--reconnect`, it schedules `_attempt_reconnect` on the
loop via `run_coroutine_threadsafe`. That coroutine:

1. Retitles the block `<host> [reconnecting]` and repaints DEAD.
2. Sleeps for the next backoff value.
3. Re-probes tcp/22.
4. Re-spawns `ssh` with the SAME token and socket paths.
5. Rebinds `slave.pty_master` and `slave.pid`, clears `dead`.
6. Re-runs the bridge.
7. On success: restores the original title and paints ENABLED /
   DISABLED according to `_color_for(slave)`.

The visible block keeps its socket connection — it never noticed the
underlying ssh died. The token file is re-written to the same path
(in case the file unlink was racy).

### Tile after every spawn

The orchestrator calls `launcher.tile(handles)` after every
`open_block`, not just once at the end. Without this, tmux's
default split halves the most-recent pane, producing visibly lopsided
layouts during launch. Backends with auto-tiling (iTerm2, WezTerm)
expose `tile` as a no-op; the orchestrator still calls it for the
same reason a no-op is cheap and the contract stays uniform.

### Terminal-mode resets

`terminal.reset_terminal_modes` emits a soft DECSTR (`\e[!p`) plus
explicit per-mode disables (bracketed paste, application keypad,
mouse tracking, focus reporting, modifyOtherKeys, …) before
`raw_mode` engages and again on exit. This is *essential* on
xterm.js-based terminals (WaveTerm, VSCode) where p10k's instant
prompt otherwise leaves modifyOtherKeys enabled and every keystroke
becomes `\e[27;<mod>;<key>~` — broadcast as-is, the remote shell
sees garbage. Apple Terminal is more permissive, which is why the
breakage was WaveTerm-specific.

### Async launcher dispatch

Concrete launchers are synchronous — they `subprocess.run` an
`osascript` / `wsh` / `tmux` / `kitty @` / `wezterm cli` and block
until it returns. Calling them straight from the event loop freezes
the TUI for the duration of every block-open (e.g. ~200 ms per host
on macOS osascript calls). `_open_block` / `_close_block` / `_tile`
/ `_set_color` / `_set_title` all run their target through
`asyncio.to_thread` so the loop stays responsive.

### Color taxonomy

`launcher.Color` is the three-state enum (`ENABLED`, `DISABLED`,
`DEAD`) every launcher's `set_color` paints. The orchestrator's
`_color_for(slave)` is the single source of truth for the
slave-state → color mapping; broadcaster `on_state_change` and
`on_dead` both push the result through `launcher.set_color` so toggle
feedback is instant. Launchers without a native paint API (Apple
Terminal, WezTerm) silently no-op.

---

## Common tasks

### Add a new terminal backend

1. New file under `csshx_latest/launchers/your_backend.py`.
2. Implement: `name`, `start(total)`, `open_block(cmd, title)`,
   `close_block(handle)`, `tile(handles)`, `set_title(handle, title)`,
   `set_color(handle, color)`. A no-op `set_color` is fine if the
   backend has no native paint API.
3. Register in `launcher._LAUNCHERS`. The CLI choice list updates
   automatically.
4. Add auto-detect rule in `launcher.detect_launcher` if your backend
   sets a recognizable env var.
5. **Decide how the master tiles with slaves** (see "Master co-tiling
   — implementation notes" above). If the backend uses split panes
   from the current pane, you get co-tiling for free. If it uses
   separate windows, capture the master window/pane id in `start()`
   and include it in `tile()`.
6. Tests: copy any existing `tests/test_launcher_*.py` and adapt.
   The conformance harness will exercise your backend automatically.

### Add a new control-socket command

1. Extend the grammar comment in `slave._apply_control_line`.
2. Parse the new command in that function; ignore unknown commands
   silently so older attach clients don't break newer slaves.
3. If the command needs to flow from the attach client, add a tiny
   sender in `attach.py` (see `_push_winsize` for a template).

### Add a new TUI command-mode key

1. Add the dispatch in `tui._handle_command_byte`.
2. If your new command needs follow-up input (like the `i` index
   prompt), extend `_CommandState` and add a per-byte handler.
3. Update the help in `_render_help`.
4. Add a test in `tests/test_tui_focus_toggle.py` (or a sibling file).

### Make `--command-key` accept a new syntax

`tui.parse_command_key` is the only parser. Accepted forms today:

- `^X` / `^x` for Ctrl-X (A–Z only)
- `0x14` hex byte (0–255)
- a single printable character

Add the new form there, then extend `tests/test_command_key.py`.

---

## What this project will NEVER do

- **Run on Windows.** `pty`, `termios`, `tty`, `fcntl` are Unix-only.
  Windows users use WSL.
- **Re-introduce TIOCSTI.** It's deprecated, removed in newer kernels,
  and a known privilege-escalation vector.
- **Auto-spawn a multiplexer.** `detect_launcher` falls back to
  `manual` (which just prints attach commands) rather than starting
  tmux/screen behind your back.
- **Embed the AUTH token in argv.** Always read from a `0600` file
  inside a `0700` directory so `ps` can't leak it.
- **Cache or persist credentials.** Tokens are per-run, generated
  fresh, never written outside the run's socket dir.
- **Block on a stuck ssh during shutdown.** SIGTERM → 2 s poll →
  SIGKILL is the bounded path; `os.waitpid(pid, 0)` is forbidden.
