"""Brace-expansion and cluster-alias resolution for host arguments.

Author: Aditya Kapadia.

Brace expansion mirrors bash so the CLI behaves the same regardless of
the user's shell. Cluster aliases come from :mod:`csshx_latest.config`
and are expanded *before* brace expansion so a cluster can list
brace-pattern hosts.

Supported brace forms:

* numeric range: ``web0{1..5}`` → ``web01 web02 web03 web04 web05``
  (width is preserved from the lower bound's literal text);
* alphabetic range: ``host-{a..c}`` → ``host-a host-b host-c``;
* alternation: ``api-{a,b,c}`` → ``api-a api-b api-c``.

Patterns can be nested and combined: ``{prod,stage}-web{1..2}`` yields
4 hosts. Inputs without braces are returned unchanged.
"""
from __future__ import annotations

import re
from typing import Optional

from csshx_latest.config import Clusters, expand_clusters

_BRACE_RE = re.compile(r"\{([^{}]+)\}")


def expand_hosts(args: list[str], clusters: Optional[Clusters] = None) -> list[str]:
    """Resolve cluster aliases, then brace-expand, then return the flat list.

    Inputs with no braces are returned unchanged. Empty alternation
    elements are kept (so ``foo{,bar}`` yields ``foo`` and ``foobar``,
    matching bash's behavior). ``clusters`` defaults to no aliases.
    """
    tokens = expand_clusters(args, clusters) if clusters else list(args)
    out: list[str] = []
    for a in tokens:
        out.extend(_expand_one(a))
    return out


def _expand_one(s: str) -> list[str]:
    """Expand a single token; recurses for nested braces."""
    m = _BRACE_RE.search(s)
    if not m:
        return [s]
    prefix, suffix = s[: m.start()], s[m.end() :]
    inner = m.group(1)
    pieces = _expand_inner(inner)
    out: list[str] = []
    for piece in pieces:
        # Recurse: ``suffix`` (and any later prefix) may have more braces.
        for tail in _expand_one(suffix):
            out.append(f"{prefix}{piece}{tail}")
    return out


def _expand_inner(inner: str) -> list[str]:
    """Expand the contents of one ``{...}`` group.

    Handles numeric ranges (``N..M``) first because they're the more
    constrained form; anything else is treated as comma-separated
    alternation.
    """
    range_match = re.fullmatch(r"(-?\d+)\.\.(-?\d+)", inner)
    if range_match:
        lo_s, hi_s = range_match.group(1), range_match.group(2)
        lo, hi = int(lo_s), int(hi_s)
        # Preserve zero-padding width from the lower bound's literal text.
        width = 0
        if lo_s.startswith("0") or lo_s.startswith("-0"):
            width = len(lo_s.lstrip("-"))
        step = 1 if hi >= lo else -1
        items: list[str] = []
        for n in range(lo, hi + step, step):
            if width:
                sign = "-" if n < 0 else ""
                items.append(f"{sign}{abs(n):0{width}d}")
            else:
                items.append(str(n))
        return items
    alpha_match = re.fullmatch(r"([A-Za-z])\.\.([A-Za-z])", inner)
    if alpha_match:
        lo_c, hi_c = alpha_match.group(1), alpha_match.group(2)
        step = 1 if ord(hi_c) >= ord(lo_c) else -1
        return [chr(c) for c in range(ord(lo_c), ord(hi_c) + step, step)]
    # Comma alternation. Split on every comma (no nested brace splitting —
    # outer recursion in _expand_one handles nesting after the outer brace
    # is consumed).
    return inner.split(",")
