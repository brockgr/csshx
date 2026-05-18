"""Cluster alias configuration.

Author: Aditya Kapadia.

Two config sources are supported, in priority order:

1. ``$XDG_CONFIG_HOME/csshx-latest/config.toml`` (or
   ``~/.config/csshx-latest/config.toml``), with a ``[clusters]``
   table mapping cluster name → list of hostnames.

2. ``~/.csshrc`` in the original csshX format:
   ``cluster <name> = host1 host2 host3`` lines, ``#`` for comments.

The first source that exists wins. Either format is fine; the TOML
flavor is preferred for new setups, the ``~/.csshrc`` path is kept so
users migrating from the Perl csshX don't have to rewrite their config.
"""
from __future__ import annotations

import logging
import os
import shlex
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

Clusters = dict[str, list[str]]


def _toml_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "csshx-latest", "config.toml")


def _csshrc_path() -> str:
    return os.path.expanduser("~/.csshrc")


def _load_toml(path: str) -> Clusters:
    if tomllib is None:
        log.debug("tomllib unavailable; skipping %s", path)
        return {}
    try:
        with open(path, "rb") as fh:
            doc = tomllib.load(fh)
    except (OSError, ValueError) as exc:
        log.warning("could not parse %s: %s", path, exc)
        return {}
    raw = doc.get("clusters", {})
    if not isinstance(raw, dict):
        log.warning("%s: [clusters] must be a table, got %r", path, type(raw).__name__)
        return {}
    out: Clusters = {}
    for name, hosts in raw.items():
        if isinstance(hosts, str):
            out[name] = shlex.split(hosts)
        elif isinstance(hosts, list):
            out[name] = [str(h) for h in hosts]
        else:
            log.warning("%s: cluster %r ignored (must be string or list)", path, name)
    return out


def _load_csshrc(path: str) -> Clusters:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        log.debug("could not read %s: %s", path, exc)
        return {}
    out: Clusters = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("cluster "):
            continue
        body = line[len("cluster "):].lstrip()
        if "=" not in body:
            continue
        name, _, rest = body.partition("=")
        name = name.strip()
        if not name:
            continue
        out[name] = shlex.split(rest)
    return out


def load_clusters(toml_path: Optional[str] = None, csshrc_path: Optional[str] = None) -> Clusters:
    """Return cluster aliases from the first source that exists.

    ``toml_path`` / ``csshrc_path`` override the default lookup; useful
    in tests. Missing files return an empty mapping, never raise.
    """
    tp = toml_path if toml_path is not None else _toml_path()
    rp = csshrc_path if csshrc_path is not None else _csshrc_path()
    if os.path.isfile(tp):
        return _load_toml(tp)
    if os.path.isfile(rp):
        return _load_csshrc(rp)
    return {}


def expand_clusters(tokens: list[str], clusters: Clusters) -> list[str]:
    """Replace any token that matches a cluster name with its host list.

    Cluster references are resolved recursively so a cluster can list
    another cluster's name. A cycle short-circuits at the first repeat
    so a misconfigured config doesn't hang the CLI.
    """
    out: list[str] = []
    for tok in tokens:
        out.extend(_resolve(tok, clusters, seen=set()))
    return out


def _resolve(name: str, clusters: Clusters, seen: set[str]) -> list[str]:
    if name not in clusters or name in seen:
        return [name]
    seen = seen | {name}
    out: list[str] = []
    for child in clusters[name]:
        out.extend(_resolve(child, clusters, seen))
    return out
