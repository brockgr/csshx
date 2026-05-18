"""Conformance tests every registered launcher must pass.

Author: Aditya Kapadia.

The Launcher Protocol is structural — Python won't catch a typo'd
``open_block`` signature at import time. These tests instantiate every
backend from the registry and assert that:

* it satisfies the runtime-checkable :class:`Launcher` protocol,
* it exposes the required attributes (``name``),
* every required method is callable with the documented signature
  (smoke-only, no side effects).

If you add a new launcher, register it in
``csshx_latest.launcher._LAUNCHERS`` and these checks will exercise it
automatically — no per-backend boilerplate.
"""
from __future__ import annotations

import inspect

import pytest

from csshx_latest.launcher import (
    BlockHandle,
    Color,
    Launcher,
    _LAUNCHERS,
    _by_name,
)


@pytest.fixture(params=sorted(_LAUNCHERS))
def launcher_name(request):
    """Yield every registered launcher name in turn."""
    return request.param


def _instantiate_or_skip(name: str):
    """Build a launcher; skip the test if the backend's binary isn't installed.

    A backend whose ``__init__`` raises ``RuntimeError`` (e.g. kitty
    without ``kitty`` on PATH) can't be tested in this environment but
    its conformance is checked on developer/CI machines that do have it.
    """
    try:
        return _by_name(name)
    except RuntimeError as exc:
        pytest.skip(f"{name} backend not installed on this host: {exc}")


def test_launcher_satisfies_protocol(launcher_name):
    """Every registered backend must structurally implement Launcher."""
    inst = _instantiate_or_skip(launcher_name)
    assert isinstance(inst, Launcher), (
        f"{launcher_name} doesn't implement the Launcher protocol"
    )


def test_launcher_has_name_attribute(launcher_name):
    """``name`` is used in logs + telemetry — must be a non-empty str."""
    inst = _instantiate_or_skip(launcher_name)
    assert isinstance(inst.name, str) and inst.name, (
        f"{launcher_name} has invalid .name attribute: {inst.name!r}"
    )


@pytest.mark.parametrize(
    "method,sig_args",
    [
        ("start", ["total"]),
        ("open_block", ["attach_cmd", "title"]),
        ("close_block", ["handle"]),
        ("tile", ["handles"]),
        ("set_title", ["handle", "title"]),
        ("set_color", ["handle", "color"]),
    ],
)
def test_launcher_method_signature(launcher_name, method, sig_args):
    """Every method documented in the Protocol must exist with matching args.

    We don't require exact param names (some backends use clearer
    domain terms), but the *positional arity* has to match so the
    orchestrator's call sites work.
    """
    inst = _instantiate_or_skip(launcher_name)
    fn = getattr(inst, method, None)
    assert callable(fn), f"{launcher_name}.{method} missing or not callable"
    sig = inspect.signature(fn)
    positional = [
        p
        for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    assert len(positional) == len(sig_args), (
        f"{launcher_name}.{method} expected {len(sig_args)} args "
        f"({sig_args}), got {len(positional)} ({[p.name for p in positional]})"
    )


def test_launcher_set_color_accepts_every_state(launcher_name):
    """A backend may no-op set_color, but it must accept every Color value.

    We pass a dummy BlockHandle so a crash means the backend tried to
    dereference handle.data — those backends should guard against an
    unknown / handle-less call instead. Errors are tolerated only if
    they are KeyError/AttributeError from the dummy handle; any other
    exception type signals a broken signature.
    """
    inst = _instantiate_or_skip(launcher_name)
    handle = BlockHandle(backend=launcher_name, data={})
    for color in Color:
        try:
            inst.set_color(handle, color)
        except (KeyError, AttributeError, RuntimeError, FileNotFoundError):
            # Expected: the dummy handle lacks real backend identifiers,
            # or the external binary (tmux, kitty, ...) isn't installed.
            pass
        except TypeError as exc:  # pragma: no cover - regression guard
            pytest.fail(
                f"{launcher_name}.set_color rejected Color.{color.name}: {exc}"
            )
