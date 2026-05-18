"""Tests for the slave-state → ``Color`` mapping and broadcaster repaint hook.

The orchestrator's ``_color_for`` function is the single source of
truth for "what color should this block be right now?". A regression
here would mean a dead host paints green or an enabled host paints
red — both visually confusing.

The broadcaster fires ``on_state_change`` whenever a slave's enabled
flag is flipped via :meth:`toggle` or :meth:`set_all_enabled`. The
orchestrator wires this to schedule a ``set_color`` repaint, so we
test the callback contract directly.
"""
from __future__ import annotations

import pytest

from csshx_latest.broadcaster import Broadcaster
from csshx_latest.launcher import Color
from csshx_latest.orchestrator import _color_for
from csshx_latest.slave import Slave


def _slave(idx: int, *, enabled: bool = True, dead: bool = False) -> Slave:
    return Slave(
        index=idx, host=f"h{idx}", sock_path=f"/tmp/s{idx}",
        token="t", pty_master=-1, pid=0, enabled=enabled, dead=dead,
    )


@pytest.mark.parametrize(
    "enabled,dead,expected",
    [
        (True, False, Color.ENABLED),
        (False, False, Color.DISABLED),
        (True, True, Color.DEAD),
        (False, True, Color.DEAD),
    ],
)
def test_color_for_maps_state_to_color(enabled, dead, expected):
    """Dead always wins over enabled; otherwise enabled → green, off → grey."""
    assert _color_for(_slave(1, enabled=enabled, dead=dead)) is expected


def test_toggle_fires_on_state_change_for_that_slave_only():
    """Toggling slave 2 must invoke the callback once, with slave 2."""
    s1, s2 = _slave(1, enabled=False), _slave(2, enabled=False)
    b = Broadcaster()
    b.add(s1)
    b.add(s2)
    fired: list[int] = []
    b.on_state_change = lambda s: fired.append(s.index)

    b.toggle(2)

    assert fired == [2]
    assert s2.enabled is True
    assert s1.enabled is False


def test_set_all_enabled_only_fires_for_actual_changes():
    """Slaves already in the target state shouldn't trigger a repaint."""
    s1 = _slave(1, enabled=True)   # already on
    s2 = _slave(2, enabled=False)  # will flip on
    s3 = _slave(3, enabled=False, dead=True)  # dead — excluded
    b = Broadcaster()
    for s in (s1, s2, s3):
        b.add(s)
    fired: list[int] = []
    b.on_state_change = lambda s: fired.append(s.index)

    b.set_all_enabled(True)

    assert fired == [2]
    assert s1.enabled is True
    assert s2.enabled is True
    assert s3.enabled is False


def test_on_state_change_callback_exception_is_swallowed():
    """A buggy callback must not break ``toggle`` semantics."""
    s1 = _slave(1, enabled=False)
    b = Broadcaster()
    b.add(s1)
    b.on_state_change = lambda _s: (_ for _ in ()).throw(RuntimeError("boom"))

    # Should not raise; the toggle still completes.
    new_state = b.toggle(1)

    assert new_state is True
    assert s1.enabled is True
