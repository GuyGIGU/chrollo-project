"""The displacement seam's battery (story-chain program Task 5).

The seam owns the resolution arithmetic both chains and the species wall
consume. These tests pin the contract laws the module docstring states: the
yardstick excludes the crossing bar's own volatility, NaN fails closed,
unresolved is None (never a fabricated index), and running extremes keep the
earliest tie. The species lane's byte-identity through the delegation is
pinned by its own battery (test_power_play_*), which runs in the same suite.
"""
import numpy as np
import pytest

from engine_alpha.structure.displacement import (
    atr10_before,
    first_close_beyond,
    first_close_below,
    running_argmax,
    running_argmin,
)


def _flat_bars(n, close=100.0, tr=1.0):
    closes = np.full(n, close)
    highs = closes + tr / 2
    lows = closes - tr / 2
    return highs, lows, closes


def test_atr10_before_excludes_the_crossing_bars_own_range():
    highs, lows, closes = _flat_bars(12)
    highs[11] = 130.0                      # an explosive bar at the end
    lows[11] = 100.0
    out = atr10_before(highs, lows, closes)
    # Bar 11's yardstick is the ten bars BEFORE it — the explosion cannot
    # raise its own wall.
    assert out[11] == pytest.approx(1.0)
    # The frame head has no ten-bar history: NaN, which downstream compares
    # False (fails closed).
    assert np.isnan(out[:10]).all()


def test_first_close_beyond_and_below_basics():
    closes = np.array([100.0, 101.0, 99.0, 103.0, 105.0])
    assert first_close_beyond(closes, 102.0, 0) == 3
    assert first_close_beyond(closes, 102.0, 4) == 4
    assert first_close_beyond(closes, 110.0, 0) is None      # unresolved
    assert first_close_beyond(closes, 102.0, 9) is None      # start past end
    assert first_close_below(closes, 100.0, 0) == 2
    assert first_close_below(closes, 90.0, 0) is None


def test_lift_raises_the_wall_and_nan_lift_fails_closed():
    closes = np.array([100.0, 103.0, 104.0, 108.0])
    lift = np.array([2.0, 2.0, 2.0, 2.0])
    # bare level: bar 1 already crosses 102; with the lift the wall is 104
    assert first_close_beyond(closes, 102.0, 0) == 1
    assert first_close_beyond(closes, 102.0, 0, lift=lift) == 3
    nan_lift = np.array([np.nan] * 4)
    assert first_close_beyond(closes, 102.0, 0, lift=nan_lift) is None
    assert first_close_below(closes, 104.0, 0, lift=nan_lift) is None


def test_running_extremes_keep_the_earliest_tie():
    lows = np.array([5.0, 3.0, 4.0, 3.0, 6.0])
    assert list(running_argmin(lows)) == [0, 1, 1, 1, 1]     # the later equal
    highs = np.array([1.0, 4.0, 2.0, 4.0, 3.0])              # low never moves it
    assert list(running_argmax(highs)) == [0, 1, 1, 1, 1]


def test_running_extremes_are_prefix_true_never_hindsight():
    lows = np.array([10.0, 8.0, 9.0, 5.0, 7.0])
    out = running_argmin(lows)
    # Standing at bar 2 the walk sees bar 1 as the low — bar 3's deeper low
    # does not exist yet (the running-vs-final AR lesson, 2026-08-17/20).
    assert out[2] == 1
    assert out[4] == 3
