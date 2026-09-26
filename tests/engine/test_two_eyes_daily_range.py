"""The daily range copy's own pure tests — NEW: the original never had any.

Task 7 of the two-eyes-reader build. The daily range is the unit every number in the method is placed in
("rail area is about half a daily range"), and in the old engine not one test pinned how it is computed: the
only uses under tests/ are as a helper. These pin the copy's behaviour exactly as it arrived, so a change to
it is a decision and never a drift — the plan already names one (the unit built on the long frame before the
two-year cut), and its task changes these tests on purpose.

What it is: the true range (the bar's high to low, stretched to the previous close when the market gapped),
smoothed by Wilder's rule — each day carries 1/period of its own range and the rest of yesterday's average —
with no warm-up average: the first day has no previous close and so no range, and the second day's range
seeds the average.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine_alpha.two_eyes.daily_range import calculate_atr


def _frame(highs, lows, closes):
    return pd.DataFrame({"High": highs, "Low": lows, "Close": closes},
                        index=pd.bdate_range("2026-01-05", periods=len(highs)))


def _true_ranges(df):
    prev = df["Close"].shift(1)
    return np.maximum(df["High"] - df["Low"],
                      np.maximum((df["High"] - prev).abs(), (df["Low"] - prev).abs())).to_numpy()


def test_the_first_day_has_no_range_and_the_second_seeds_the_average():
    df = _frame([11.0, 12.0, 13.0], [9.0, 10.0, 11.5], [10.0, 11.0, 12.0])
    atr = calculate_atr(df, 10).to_numpy()
    assert np.isnan(atr[0]), "no previous close, so no true range, so no average"
    assert atr[1] == _true_ranges(df)[1], "no warm-up average: day two's own range seeds it"


def test_each_later_day_carries_one_period_th_of_its_own_range():
    rng = np.random.default_rng(3)
    close = 50 + np.cumsum(rng.normal(0, 1, 40))
    df = _frame(close + rng.uniform(0.2, 2.0, 40), close - rng.uniform(0.2, 2.0, 40), close)
    tr, atr = _true_ranges(df), calculate_atr(df, 10).to_numpy()
    for k in range(2, 40):
        assert atr[k] == pytest.approx(0.1 * tr[k] + 0.9 * atr[k - 1], rel=1e-12), k


def test_the_period_is_the_smoothing():
    df = _frame([11.0, 12.0, 16.0], [9.0, 10.0, 11.0], [10.0, 11.0, 15.0])
    tr = _true_ranges(df)
    assert calculate_atr(df, 10).to_numpy()[2] == pytest.approx(0.1 * tr[2] + 0.9 * tr[1])
    assert calculate_atr(df, 50).to_numpy()[2] == pytest.approx(0.02 * tr[2] + 0.98 * tr[1])


def test_the_range_counts_the_overnight_gap():
    """Not his bar's high to low: a gap stretches the range to the previous close (an open question the
    census records; this pins what the copy does today)."""
    df = _frame([10.0, 21.0], [9.0, 20.0], [9.5, 20.5])
    assert calculate_atr(df, 10).to_numpy()[1] == pytest.approx(21.0 - 9.5)


def test_a_missing_close_is_unreadable_on_the_next_day_only():
    """A hole in the MIDDLE of a chart costs the day that has no previous close, and no other. The
    original was fixed this way on 2026-09-07 (one bad price cell used to delete the read from that day to
    the right edge); the copy carries the same fix since the port of Sat 26/09/2026. The frame contract
    still refuses a bar with a missing number before a read, so this edge is a guard, not a path."""
    df = _frame([11.0, 12.0, 13.0, 14.0, 15.0], [9.0, 10.0, 11.0, 12.0, 13.0],
                [10.0, 11.0, np.nan, 13.0, 14.0])
    atr = calculate_atr(df, 10).to_numpy()
    assert np.isfinite(atr[1]) and np.isfinite(atr[2]), "the day with the hole still has a high and a low"
    assert np.isnan(atr[3]), "the day after it has no previous close, so no range"
    assert np.isfinite(atr[4]), "the read resumes on the next readable day; it never dies to the right edge"


def test_a_one_day_frame_has_no_range_and_an_empty_one_is_not_a_frame():
    assert np.isnan(calculate_atr(_frame([11.0], [9.0], [10.0]), 10).to_numpy()).all()
    with pytest.raises(IndexError):
        calculate_atr(_frame([], [], []), 10)
