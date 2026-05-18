# csshx

This repository contains two related cluster-SSH tools:

| | path | language | platform |
|-|-|-|-|
| **Original csshX** (Gavin Brock's 2011 release) | [`csshX`](csshX) | Perl 5 | macOS only |
| **csshx-latest** — modern rewrite | [`csshx-latest/`](csshx-latest/) | Python 3.10+ (stdlib only) | macOS / Linux |

If you want the classic, terminal-coupled, Perl version of csshX, run
[`./csshX --man`](csshX). The historical install/usage notes live in
[`README.txt`](README.txt).

The rest of this file is a quick-start for the new
[`csshx-latest/`](csshx-latest/) rewrite. For the full architecture
diagram, backend support matrix, and design notes, see
[`csshx-latest/README.md`](csshx-latest/README.md).

---

## csshx-latest — quick start

A modern, terminal-agnostic cluster-SSH tool. PTY end-to-end (no
TIOCSTI), with pluggable backends for WaveTerm, tmux, iTerm2,
Terminal.app, Kitty, WezTerm, and a Manual fallback that prints attach
commands you can paste into any terminal.

### Install

```bash
cd csshx-latest/
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
```

Or with `uv`:

```bash
cd csshx-latest/
uv venv && uv pip install -e '.[test]'
```

### Run

```bash
csshx-latest web01 web02 web03
csshx-latest --launcher tmux web0{1..5}
csshx-latest --login deploy --ssh-args "-i ~/.ssh/cluster_key" host1 host2
csshx-latest --launcher manual host1 host2   # prints attach commands
```

Type in the master TUI to broadcast to every host at once. Click any
host's terminal block to type to just that host. Press **Ctrl-Q** to
exit.

`--launcher` choices: `auto` (default), `waveterm`, `tmux`, `iterm2`,
`terminal`, `kitty`, `wezterm`, `manual`. With `auto`, csshx-latest
auto-detects via `$TERM_PROGRAM`, `$KITTY_PID`, `$TMUX`, etc., and
falls back to `manual` if it doesn't recognize the environment (no
surprise tmux sessions).

### Tests

```bash
cd csshx-latest/
pytest -q
```

The package itself is Unix-only (uses `pty`, `termios`, `tty`,
`fcntl`); tests assume a Unix-like host.

### License

The original Perl csshX is released under the same terms as Perl
itself (Artistic + GPL — see [`README.txt`](README.txt)). The
`csshx-latest/` rewrite is MIT.
