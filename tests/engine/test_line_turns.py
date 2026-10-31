"""The swing line copy's own pure tests: COPIED from tests/test_final_method_step4.py, test_final_method_step8.py and test_market_structure.py (two-eyes-reader task 7), re-pointed at the
new reader's copy. Verbatim but for the imports. None of them reads a number the copy takes from `method_numbers`;
those values are pinned in tests/engine/test_two_eyes_copies_equal_originals.py. The originals' tests stay where
they are, frozen with the old engine; these move with the copy and change when it changes.

Copied: the line's own tests (the rail count's and the labeller's went with those functions, Sat 31/10/2026). Left with the originals (they test the old engine, not the piece): the flag and seam tests, and three that contrast the line with the old order-one pivot walk the copy does not carry. One is copied in part: the line's invariants, without its pivot view (`turn_line_views`, which was not copied).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine_alpha.line import turn_line, turn_line_floors


# ---- from tests/test_final_method_step4.py --------------------------------------
def _frame(highs, lows, atr=None):
    df = pd.DataFrame({"High": list(highs), "Low": list(lows),
                       "Close": list(lows), "Open": list(lows)})
    if atr is not None:
        df["ATR_10"] = float(atr) if np.isscalar(atr) else list(atr)
    return df


def test_a_turn_commits_when_price_backs_off_the_floor_and_not_before():
    # Rises to 20 at bar 2, then gives back 0.9 (bar 3) and 2.0 (bar 4). Floor 1.0: bar 3 is not enough.
    highs = [10, 15, 20, 19.5, 18.5, 19, 20.5]
    lows = [9, 14, 19, 19.1, 18.0, 18.5, 20]
    line = turn_line(highs, lows, 1.0)
    peak = [t for t in line if t[1] == "peak" and t[0] == 2]
    assert peak, "the peak at bar 2 is on the line"
    assert peak[0][2] == 20 and peak[0][3] == 4, "it commits on bar 4, the bar that backs off a full floor"
    assert turn_line(highs, lows, 3.0) == [(0, "valley", 9.0, 1), (6, "peak", 20.5, None)], \
        "a floor of 3 sees one rise and no committed turn inside it"


def test_the_first_bar_is_a_turn_by_its_shape_and_the_right_edge_is_forming():
    up = turn_line([10, 12, 14, 12.5], [9, 11, 13, 11.5], 1.0)
    assert up[0] == (0, "valley", 9.0, 1), \
        "the line rose first, so bar 0 is a valley — known on bar 1, when the first leg covered its floor (task 8)"
    assert up[-1][3] is None and up[-1][1] == "valley", "the running extreme at the edge is forming"
    down = turn_line([14, 12, 10, 11.5], [13, 11, 9, 10.5], 1.0)
    assert down[0] == (0, "peak", 14.0, 1), "the line fell first, so bar 0 is a peak"


def test_a_bar_whose_own_range_covers_the_floor_carries_both_a_peak_and_a_valley():
    # Bar 2 makes the high of the up-leg AND falls a full floor within its own range.
    line = turn_line([10.2, 11.2, 16.0, 13.2, 15.0], [10.0, 11.0, 12.0, 13.0, 14.8], 1.0)
    at_two = [t for t in line if t[0] == 2]
    assert {t[1] for t in at_two} == {"peak", "valley"}, "one bar, both turns"
    assert [t[2] for t in at_two if t[1] == "peak"] == [16.0]
    assert [t[2] for t in at_two if t[1] == "valley"] == [12.0]


def test_a_bar_whose_floor_is_unreadable_still_moves_the_running_extreme():
    """Only the COMMIT test needs a readable floor. A frame whose range column is still warming up would
    otherwise open its line off a stale first-bar extreme and miss every turn in the warm-up."""
    df = _frame([10, 14, 13, 12, 11], [9, 13, 12, 11, 10], atr=[np.nan, np.nan, 1.0, 1.0, 1.0])
    line = turn_line(df["High"].values.astype(float), df["Low"].values.astype(float),
                     turn_line_floors(df, None))
    assert any(t[0] == 1 and t[1] == "peak" and t[2] == 14.0 for t in line),         "the top printed on an unreadable-floor bar is still the extreme the next turn measures from"


def test_the_floor_is_each_bar_s_own_range_with_the_scalar_as_the_fallback():
    df = _frame([10] * 4, [9] * 4, atr=[2.0, np.nan, 4.0, 0.0])
    got = turn_line_floors(df, 3.0)
    assert list(got) == [1.5, 2.25, 3.0, 2.25], "0.75 of each bar's range; a broken range falls back to 3.0"
    bare = _frame([10] * 3, [9] * 3)
    assert list(turn_line_floors(bare, 2.0)) == [1.5, 1.5, 1.5], "no range column: the caller's one range"
    assert all(not np.isfinite(f) for f in turn_line_floors(bare, None)), "no unit anywhere: no floor"
    assert turn_line([10, 11, 12], [9, 10, 11], turn_line_floors(bare, None)) == [], \
        "and with no floor the line refuses rather than guessing one"


def test_the_line_opens_on_the_older_running_extreme_not_on_bar_0():
    """Price dips 0.4 under bar 0 before its first leg covers the floor: the opening valley is that lower low,
    known on the bar where the leg covered its floor."""
    line = turn_line([9.2, 8.9, 9.9, 9.4], [9.0, 8.6, 9.7, 9.1], 1.0)
    assert line == [(1, "valley", 8.6, 2), (2, "peak", 9.9, None)]


def test_a_legs_turn_is_the_most_extreme_price_since_the_turn_before():
    """Changed with the copy at task 8. Bar 3 prints the lowest low after the peak on bar 2 but its own range is
    huge (a floor of 7.5), so nothing commits there; bar 4 confirms the peak with a small floor. The valley is
    bar 3's 17.6, not bar 4's 18.0: the original restarted the new leg at the confirming bar and lost it."""
    highs = [9.5, 14.5, 20.0, 19.0, 18.9, 19.5, 21.0]
    lows = [9.0, 14.0, 19.5, 17.6, 18.0, 18.6, 20.0]
    floors = [0.75, 0.75, 0.75, 7.5, 0.75, 0.75, 0.75]
    line = turn_line(highs, lows, floors)
    assert line == [(0, "valley", 9.0, 1), (2, "peak", 20.0, 4), (3, "valley", 17.6, 5), (6, "peak", 21.0, 6),
                    (6, "valley", 20.0, None)], \
        "the valley is the lowest low since the peak (bar 3), not the confirming bar's low (bar 4)"


def test_the_turn_bars_own_other_end_belongs_to_the_new_leg_when_read_after_the_turn():
    """The line came into bar 2 rising, so bar 2's low was read after its high. The high is the peak (confirmed
    on bar 3, whose floor is small); the lowest low since it is bar 2's own 17.7, read after the peak, and
    the rise on bar 4 confirms that valley. Both turns sit on bar 2, in that order."""
    highs = [9.5, 14.5, 20.0, 19.2, 19.5, 21.0]
    lows = [9.0, 14.0, 17.7, 18.5, 18.6, 20.0]
    floors = [0.75, 0.75, 7.5, 0.75, 0.75, 0.75]
    line = turn_line(highs, lows, floors)
    assert line == [(0, "valley", 9.0, 1), (2, "peak", 20.0, 3), (2, "valley", 17.7, 4), (5, "peak", 21.0, 5),
                    (5, "valley", 20.0, None)], line


def test_a_wide_first_bar_is_read_once():
    """Changed with the copy at task 8. The first bar with a readable floor (bar 1; bar 0 has no previous close)
    covers the floor on its own, so it opens the line upward — its valley, then its peak; the original then
    read that bar again and carried the same valley a second time (six of the 88 fixture frames)."""
    line = turn_line([10.2, 12.0, 11.0, 11.8], [10.0, 9.0, 10.5, 11.2], [np.nan, 1.0, 1.0, 1.0])
    keys = [(b, k) for b, k, _, _ in line]
    assert len(set(keys)) == len(keys), f"a turn is carried twice: {line}"
    assert line == [(1, "valley", 9.0, 1), (1, "peak", 12.0, 2), (2, "valley", 10.5, 3), (3, "peak", 11.8, None)]


def test_a_rise_that_tops_on_a_bar_with_no_readable_floor_still_opens_the_line_upward():
    """Changed with the copy at task 8: the line came into bar 1 rising, so bar 1's low (10.1) was read after
    its 11.0 top and is the lowest low since that peak — the valley is 10.1 on bar 1, not bar 2's 10.2, and
    bar 3's 10.9 rise covers the floor from it. The original leaves the valley on bar 2 and never commits it."""
    line = turn_line([10, 11, 10.3, 10.9], [9.8, 10.1, 10.2, 10.5], [np.nan, np.nan, 0.75, 0.75])
    assert line == [(0, "valley", 9.8, 2), (1, "peak", 11.0, 2), (1, "valley", 10.1, 3), (3, "peak", 10.9, None)], \
        "the 11.0 top on the unreadable bar is the extreme the first fall is measured from"


# ---- NEW with the copy (task 7): the tie the fixtures cannot see -------------------------------------------
def test_a_back_off_of_exactly_the_floor_commits_the_turn():
    """The commit is `>=` the floor. Swapped for `>`, not one of the 88 fixture lines moves, and every copied
    test still passes — so the tie is pinned here, on a line built to sit on it: the peak at bar 2 commits on
    bar 3, where price backs off exactly one floor; under `>` it would wait for bar 4."""
    line = turn_line([10.0, 11.0, 12.0, 12.0, 11.5], [9.5, 10.5, 11.5, 11.0, 10.0], 1.0)
    assert line[1] == (2, "peak", 12.0, 3)


# ---- from tests/test_final_method_step4.py, in part -------------------------------
def test_the_line_alternates_and_its_turns_sit_on_the_bars_own_extremes():
    """test_the_line_alternates_and_its_pivot_view_round_trips, without its last half: the pivot view
    (`turn_line_views`) belongs to the old engine and was not copied."""
    rng = np.random.default_rng(11)
    mid = np.cumsum(rng.normal(0.0, 1.0, 200)) + 60.0
    highs, lows = mid + rng.uniform(0.2, 1.0, 200), mid - rng.uniform(0.2, 1.0, 200)
    line = turn_line(highs, lows, 1.5)
    assert len(line) > 5
    kinds = [k for (_, k, _, _) in line]
    assert all(a != b for a, b in zip(kinds, kinds[1:])), "strictly alternating"
    assert [b for (b, _, _, _) in line] == sorted(b for (b, _, _, _) in line), "oldest first"
    assert all(highs[b] == p for (b, k, p, _) in line if k == "peak")
    assert all(lows[b] == p for (b, k, p, _) in line if k == "valley")
    assert [c is None for (_, _, _, c) in line] == [False] * (len(line) - 1) + [True], \
        "only the edge turn is uncommitted"
