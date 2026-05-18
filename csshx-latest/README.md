# csshx-latest

A modern, terminal-agnostic cluster-SSH tool — a spiritual successor to
[csshX](https://github.com/brockgr/csshx) built on real PTYs and a
pluggable launcher layer instead of the old TIOCSTI keystroke-injection
hack.

Author: Aditya Kapadia.

## What it is

- **N terminal blocks** — one per SSH host. Click a block and type to
  send keystrokes to just that host.
- **1 master TUI** — runs in your current terminal. Every keystroke is
  broadcast to every enabled slave at once.
- **Master + slaves are tiled together** on backends that can address
  the master window (Terminal.app, iTerm2, tmux ≤ 4 hosts, WezTerm) —
  every spawn rearranges all of them in lockstep, just like the
  original Perl csshX did.
- **PTY end-to-end** — no TIOCSTI, works on modern macOS/Linux.
- **Pluggable backends** — WaveTerm, tmux, iTerm2, Terminal.app, Kitty,
  WezTerm, plus a `manual` fallback that works in any terminal by
  printing attach commands for you to paste.
- **Auto-detect** which terminal you're in. Falls back to manual if it
  doesn't recognize the environment.
- **One-shot action mode** — `--action 'uname -a' host1 host2 …` fans
  the command out concurrently, prints a per-host summary, exits.
  No TUI, no launcher; equivalent to the original csshX's
  `--remote_command`.
- **Stdlib-only Python 3.9+** — zero hard runtime dependencies.

## Install

```bash
cd csshx-latest/
uv venv && uv pip install -e '.[test]'
```

Python 3.9 is the floor (`asyncio.to_thread` is required). Tested on
3.9 – 3.13.

## Usage

```bash
csshx-latest web01 web02 web03
csshx-latest --launcher tmux web0{1..5}
csshx-latest --login deploy --ssh-args "-i ~/.ssh/cluster_key" host1 host2
csshx-latest --launcher manual host1 host2          # prints attach commands
csshx-latest --reconnect --strict web0{1..10}       # safer mode
csshx-latest production-cluster                     # uses ~/.csshrc alias
csshx-latest --action 'uptime' web0{1..3}           # one-shot fan-out
```

### CLI flags

| Flag | Default | What it does |
| --- | --- | --- |
| `--launcher` | `auto` | Pick a backend: `auto`, `waveterm`, `tmux`, `iterm2`, `terminal`, `kitty`, `wezterm`, `manual`. |
| `--login` | (ssh default) | Username, forwarded as `-l`. |
| `--ssh-args` | `""` | Extra arguments forwarded to ssh (single quoted string). |
| `--max-hosts` | `16` | Refuse to start above this many hosts. Saves you from typo fork-bombs. |
| `--strict` | off | Abort if any host fails the tcp/22 preflight (default: warn and skip). |
| `--no-preflight` | off | Skip the tcp/22 reachability check entirely. |
| `--reconnect` | off | Re-spawn ssh with exponential backoff (1s, 2s, 4s, 8s, 16s) on slave death. |
| `--action CMD` | (interactive) | One-shot mode: run `CMD` via ssh on every host concurrently, print a per-host summary, exit. |
| `--action-timeout` | `60.0` | Per-host ssh timeout in `--action` mode. |
| `--command-key` | `^T` | Master TUI command-mode prefix. Accepts `^X`, `0x14`, or a single literal byte. |
| `--debug` | off | Verbose logging to stderr. |
| `--version` | — | Print version and exit. |

## Host expansion

Three layers, applied in this order to each CLI argument:

1. **Cluster alias** — replaced with the alias's host list (recursive,
   cycle-safe).
2. **Brace expansion** — bash-style:
   - numeric: `web0{1..5}` → `web01 web02 web03 web04 web05`
     (width preserved from the lower bound)
   - alphabetic: `host-{a..c}` → `host-a host-b host-c`
   - alternation: `api-{a,b,c}` → `api-a api-b api-c`
   - nested / combined: `{prod,stage}-web{1..2}` → 4 hosts
3. **TCP/22 preflight** (unless `--no-preflight`) — unreachable hosts
   are warned & dropped (or abort the run with `--strict`).

## Cluster aliases

Two config sources, first-match wins:

1. `~/.config/csshx-latest/config.toml` (preferred; respects
   `$XDG_CONFIG_HOME`):

   ```toml
   [clusters]
   web        = ["web01", "web02", "web03"]
   db         = "db1 db2"
   production = ["web", "db"]   # clusters can reference clusters
   ```

2. `~/.csshrc` (original csshX format):

   ```
   cluster web        = web01 web02 web03
   cluster db         = db1 db2
   cluster production = web db
   ```

Any token on the command line that matches a cluster name is expanded
recursively before brace expansion runs.

## Master TUI keys

The command-mode prefix is `Ctrl-T` by default and can be changed with
`--command-key` (e.g. `--command-key ^A`).

| Key | Action |
| --- | --- |
| (any byte) | Broadcast to every enabled slave |
| `Ctrl-Q` | Quit |
| `Ctrl-T` then `b` | Toggle broadcast for ALL alive slaves |
| `Ctrl-T` then `1..9` | Toggle broadcast for that specific slave |
| `Ctrl-T` then `i`, digits, Enter | Toggle slave by index (for 10+ hosts) |
| `Ctrl-T` then `l` | List slaves and their state |
| `Ctrl-T` then `q` | Quit |
| `Ctrl-T` then `?` | Help |
| `Ctrl-T` then `Ctrl-T` | Send a literal `Ctrl-T` to slaves |
| `Ctrl-T` then any unbound printable | Cancel command mode AND broadcast that letter (so a typo never silently vanishes) |
| `Ctrl-T` then any unbound control byte (Esc, Ctrl-C, …) | Cancel command mode silently |

SIGINT / SIGTERM / SIGHUP also shut down cleanly. SIGWINCH on the
master propagates the new window size to every slave PTY via
TIOCSWINSZ; each individual terminal block also reports its own
resizes back through its dedicated control socket.

A one-line status footer is printed to stderr and updated on every
toggle:

```
[csshx-latest] hosts: 4  enabled: 3  dead: 1  (Ctrl-Q quit, Ctrl-T menu)
```

When stderr is a TTY the `enabled` / `dead` counters are colorized
(green / red / dim) so a broken host is visible at a glance.

## Architecture

```
   master process
   ----------------------------------------------------------------
   raw stdin --> Broadcaster --> Slave[1] PTY --> ssh host1
                                Slave[2] PTY --> ssh host2
                                Slave[N] PTY --> ssh hostN

   per slave:
       PTY master fd
       data socket   (0600, AUTH-gated)  -- bidirectional bytes
       control socket(0600, AUTH-gated)  -- WINSZ <rows> <cols> ...
       per-fd write_lock                  -- escape sequences stay whole
       per-slave scrollback (64 KiB)      -- replayed to new attach clients
       on_dead callback                   -- drives --reconnect / repaint

   per launcher:
       BlockHandle (backend, data{...})
       start(total) / open_block / close_block / tile / set_title /
       set_color
```

Output flows one way (PTY → data socket → terminal block). Input
arrives from two writers: the master broadcaster *and* whichever
terminal block is focused. A per-slave `asyncio.Lock` (`write_lock`)
serializes PTY writes so an escape sequence can never get torn between
them. A separate `state_lock` keeps the PTY reader's
extend-scrollback-then-fan-out cycle atomic against a new attach
client joining the writer list.

Each socket is gated by a 32-byte hex token; clients have 2 seconds
to send `AUTH <token>\n` or they're dropped. Sockets live in
`$XDG_RUNTIME_DIR/csshx-<pid>/` (or `/tmp/csshx-<pid>/` on macOS),
with the directory at mode `0700` and each socket at `0600`. Tokens
are read from `0600` files inside the run dir — never embedded in
argv, so `ps` listings can't leak them.

### Two sockets per slave

Each slave exposes two AUTH-gated UNIX sockets:

- `slave-N.sock` (data): bidirectional bytes. PTY output fans out;
  client keystrokes flow in. Per-slave scrollback (64 KiB) is
  replayed to each new client after AUTH succeeds.
- `slave-N.ctl` (control): line-oriented ASCII. Supported verbs:
  - `WINSZ <rows> <cols> [<xpixel> <ypixel>]` — sent on every local
    SIGWINCH so the individual block can resize the remote PTY
    independently of the master.
  - `BYE` — sent by the attach client when its visible terminal block
    is destroyed (SIGHUP from the terminal emulator, or stdin EOF from
    a pane kill). The master flips `slave.user_closed`, sends
    `SIGTERM` to that slave's ssh pid, and the existing PTY-EOF path
    repaints the block DEAD and updates the status footer.
    `--reconnect` honors `user_closed` and does NOT respawn — a slave
    the user explicitly closed stays closed.

  Unknown verbs are silently ignored so older attach clients don't
  break newer slaves.

The bundled stdlib attach client (`python3 -m csshx_latest.attach`)
multiplexes both sockets. socat-based attach is no longer supported
because it can't handle the dual-socket protocol.

### Reconnect

`--reconnect` schedules an exponential-backoff retry (1, 2, 4, 8, 16
seconds; max 5 attempts) whenever a slave's ssh exits. The block's
title is retitled `<host> [reconnecting]` and painted with the DEAD
color during retries; on success the block keeps its socket
connection and the title/color are restored — the slave's terminal
block never noticed the underlying ssh died.

## Safety defaults

- **TCP-22 preflight**: every host gets a 1-second TCP probe before
  ssh forks. Unreachable hosts are warned & skipped (or aborted with
  `--strict`). No more screens full of timed-out panes when your VPN
  is down. Probes run concurrently. Disable with `--no-preflight`.
- **`StrictHostKeyChecking=accept-new`** is injected unless your
  `--ssh-args` already specifies a value. First-connect prompts no
  longer fan out across every broadcast slave.
- **`--max-hosts 16`** hard cap. Raise explicitly if you really need
  more.
- **Bounded reap**: on shutdown we send SIGTERM, poll-wait up to 2s,
  then SIGKILL. The master can never hang on a stuck ssh.
- **`max_writers` per slave** caps simultaneous authenticated data
  clients (default 4). A leaked token can't be used to attach
  indefinitely.

## Backend support matrix

| Backend | Open | Close | Tile | Title | Color | Master tiled with slaves? | Platform |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WaveTerm | yes (`wsh run`) | yes (`wsh deleteblock`) | yes (probes `setlayout` / `layout` / `tile`) | yes (`wsh settitle`) | yes (`wsh setbg`, lazy-probed) | yes (`wsh setlayout tiled` rearranges the whole tab) | mac / linux / win |
| tmux | yes (`split-window`) | yes (`kill-pane`) | yes (`select-layout tiled`) | yes (`select-pane -T`) | yes (`select-pane -P bg=…`) | yes when hosts ≤ `PANE_THRESHOLD=4` (master is part of the same window); no when > 4 (master stays in original window, slaves get a dedicated `csshx` window so they aren't squeezed into ribbons) | anywhere with tmux |
| iTerm2 | yes (split current session) | yes (by session id) | auto-balanced | yes (by session id) | yes (`set background color of session`, 16-bit RGB) | yes — every block splits the master's session so iTerm2 auto-balances master + slaves on every spawn | macOS |
| Terminal.app | yes (per-block window) | yes (by window id) | grid via `set bounds`, inside a usable area that excludes the Dock + screen edges with a small gap between cells | yes (by tty id) | yes (`set background color of tab 1`, 16-bit RGB) | yes — `start()` captures the front window id and `tile()` includes it as cell 0 of the grid | macOS |
| Kitty | yes (`@ launch --type=tab`) | yes (`@ close-window` by id) | yes (`@ goto-layout grid`) | yes (`@ set-window-title`) | yes (`@ set-tab-color`, kitty ≥ 0.20) | no — slaves get their own tabs; the master TUI's tab is independent | mac / linux |
| WezTerm | yes (`cli spawn`) | yes (`cli kill-pane`) | auto-balanced | yes (`cli set-tab-title`) | no | yes — splits from the master's pane so WezTerm balances them together | mac / linux / win |
| Manual | print only | n/a | n/a | n/a | n/a | n/a | anywhere |

Notes:

- **Kitty** requires `allow_remote_control yes` in `kitty.conf`. The
  launcher raises on construction if the `kitty` CLI isn't on PATH.
- **WaveTerm** widgets configured with `controller: cmd` only get a
  `WAVETERM_SWAPTOKEN` in their env — the launcher swaps it to
  `WAVETERM_JWT` via `wsh token` so `wsh run` / `wsh layout` / `wsh
  deleteblock` / `wsh settitle` actually authenticate. The token-swap
  output is parsed with `shlex.split` so future quoting changes don't
  silently break the swap. The launcher also resolves `wsh` from
  WaveTerm's known install locations if it isn't on PATH.
- **WaveTerm** tiling tries `wsh setlayout tiled`, then `wsh layout
  tiled`, then `wsh tile` — the first one that exits 0 is cached so
  the launcher degrades quietly if the wsh CLI grammar drifts.
- **Color hooks** (`set_color`) push ENABLED → dim sage, DISABLED →
  dim slate, DEAD → dim mauve on every toggle. Backends without a
  native paint API silently no-op. On Terminal.app and iTerm2 the tint
  is written to the tab/session's ``background color`` (16-bit RGB)
  and stays scoped to that block — it does not modify the user's
  saved profile. The palette is intentionally low-saturation so a wall
  of slave windows isn't fatiguing to look at; retune by editing
  ``_TAB_BG`` (`launchers/apple_terminal.py`) or ``_SESSION_BG`
  (`launchers/iterm2.py`).
- **Terminal.app tiling** reserves space for the Dock and inserts a
  small gap between cells (`DOCK_RESERVE`, `EDGE_MARGIN`, `WINDOW_GAP`
  in `csshx_latest/launchers/apple_terminal.py`) so windows never
  slide under the Dock or sit flush against neighbours / screen edges.
- The orchestrator calls `launcher.tile()` after every spawn so panes
  stay balanced as blocks are added — not just once at the end.

## What's different from the original csshX

| | csshX (Perl) | csshx-latest |
| --- | --- | --- |
| Keystroke delivery | TIOCSTI (deprecated / removed on modern systems) | Real PTYs |
| Terminal coupling | Hard-coded Terminal.app + iTerm | Pluggable Launcher protocol |
| Detection | macOS-only | macOS, Linux, WSL |
| Auth | None | 32-byte token per socket, constant-time compare, file-based (token never in argv) |
| Per-slave typing | Hidden window per slave | Authenticated, bidirectional UNIX socket |
| Per-slave focus toggle | Action menu | `Ctrl-T <digit>` (or `Ctrl-T i` for 10+) |
| Connectivity preflight | Optional ping | Built-in concurrent tcp/22 probe |
| Reconnect | none | `--reconnect` with exponential backoff |
| Per-block SIGWINCH | n/a | Dedicated control socket per slave |
| Config | `~/.csshrc` only | TOML preferred, `~/.csshrc` fallback |
| One-shot fan-out | `--remote_command` | `--action` (same semantics, with per-host timeout) |

## Run the tests

```bash
uv run pytest -q
```

280+ tests cover the broadcaster, the AUTH handshake + token-file
round-trip, the launcher auto-detect matrix, every concrete launcher
(subprocess mocked), launcher conformance against the Protocol
(structural shape, signature arity, every `Color` state), the TUI
command mode (including per-slave focus toggle, configurable command
key, status footer), the orchestrator's preflight / kill-and-reap /
max-hosts cap, the slave control socket's `WINSZ` grammar with a real
PTY pair, action-mode fan-out + summary rendering, and an end-to-end
real-PTY integration test that uses `cat` as a fake ssh.

The package itself can't run on Windows — `pty`, `termios`, `tty`,
and `fcntl` are Unix-only. Windows users should use WSL.
