"""Build step 4 of the final method (Sun 13/09/2026): the ONE turn line, DARK, behind two flags.

Flag off, every path is byte-identical — the fleet, junk, marks and reader-pin guards prove that at scale, and
`tests/engine/test_event_map.py` / `tests/engine/test_market_structure.py` keep proving the order-1 walk unmoved. These tests
pin the line's own mechanics and each flag's bite on fakes, so a branch that silently stopped biting goes red.

His ruling (docs/final_method_2026-09.md, points 1 and 2): ONE line over the whole chart, one floor of 0.75
daily ranges, wick to wick; the first bar and the right edge are turns by their shape; a bar whose own range
covers the floor may carry both a peak and a valley; no retracement ratio. The box election is NOT a site: it
stays on today's skeleton until build step 10.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure.events.event_map import read_swing_map
from engine_alpha.structure.events.market_structure import read_market_structure
from engine_alpha.structure.metrics.pivots import (
    _build_zigzag,
    _find_pivots,
    turn_line,
    turn_line_floors,
    turn_line_views,
)

STEP4_FLAGS = ("TURN_LINE_ENABLED", "TURN_LINE_TREND_ENABLED")


@dataclass
class _Box:
    start_bar: int
    R: float
    S: float
    base_len: int = 40


def _frame(highs, lows, atr=None):
    df = pd.DataFrame({"High": list(highs), "Low": list(lows),
                       "Close": list(lows), "Open": list(lows)})
    if atr is not None:
        df["ATR_10"] = float(atr) if np.isscalar(atr) else list(atr)
    return df


def test_every_step4_flag_is_dark_and_rides_the_manifest():
    for name in STEP4_FLAGS:
        assert getattr(settings, name) is False, name
        assert name in ENGINE_SETTINGS_KEYS, name
    assert settings.TURN_LINE_FLOOR_ATR == 0.75
    assert "TURN_LINE_FLOOR_ATR" in ENGINE_SETTINGS_KEYS


# ── the line itself ──────────────────────────────────────────────────────────

def test_a_turn_commits_when_price_backs_off_the_floor_and_not_before():
    # Rises to 20 at bar 2, then gives back 0.9 (bar 3) and 2.0 (bar 4). Floor 1.0: bar 3 is not enough.
    highs = [10, 15, 20, 19.5, 18.5, 19, 20.5]
    lows = [9, 14, 19, 19.1, 18.0, 18.5, 20]
    line = turn_line(highs, lows, 1.0)
    peak = [t for t in line if t[1] == "peak" and t[0] == 2]
    assert peak, "the peak at bar 2 is on the line"
    assert peak[0][2] == 20 and peak[0][3] == 4, "it commits on bar 4, the bar that backs off a full floor"
    assert turn_line(highs, lows, 3.0) == [(0, "valley", 9.0, 0), (6, "peak", 20.5, None)], \
        "a floor of 3 sees one rise and no committed turn inside it"


def test_the_first_bar_is_a_turn_by_its_shape_and_the_right_edge_is_forming():
    up = turn_line([10, 12, 14, 12.5], [9, 11, 13, 11.5], 1.0)
    assert up[0] == (0, "valley", 9.0, 0), "the line rose first, so bar 0 is a valley"
    assert up[-1][3] is None and up[-1][1] == "valley", "the running extreme at the edge is forming"
    down = turn_line([14, 12, 10, 11.5], [13, 11, 9, 10.5], 1.0)
    assert down[0] == (0, "peak", 14.0, 0), "the line fell first, so bar 0 is a peak"


def test_a_bar_whose_own_range_covers_the_floor_carries_both_a_peak_and_a_valley():
    # Bar 2 makes the high of the up-leg AND falls a full floor within its own range.
    line = turn_line([10.2, 11.2, 16.0, 13.2, 15.0], [10.0, 11.0, 12.0, 13.0, 14.8], 1.0)
    at_two = [t for t in line if t[0] == 2]
    assert {t[1] for t in at_two} == {"peak", "valley"}, "one bar, both turns"
    assert [t[2] for t in at_two if t[1] == "peak"] == [16.0]
    assert [t[2] for t in at_two if t[1] == "valley"] == [12.0]


def test_the_line_has_no_edge_mask_where_the_order_one_walk_does():
    # A clean rise whose top is the LAST bar: the order-1 walk masks the right edge and can never pivot there.
    highs = [10.2, 11.2, 12.2, 13.2, 14.2, 15.2, 16.2]
    lows = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
    peaks, valleys = _find_pivots(np.array(highs, dtype=float), np.array(lows, dtype=float), 1)
    assert peaks == [] and valleys == [], "the order-1 walk sees no turn at all on this frame"
    line = turn_line(highs, lows, 1.0)
    assert line[0] == (0, "valley", 10.0, 0), "bar 0 is a turn by its shape"
    assert line[-1] == (6, "peak", 16.2, None), "the top on the last bar rides as a forming turn"


def test_the_line_alternates_and_its_pivot_view_round_trips():
    rng = np.random.default_rng(11)
    mid = np.cumsum(rng.normal(0.0, 1.0, 200)) + 60.0
    highs, lows = mid + rng.uniform(0.2, 1.0, 200), mid - rng.uniform(0.2, 1.0, 200)
    line = turn_line(highs, lows, 1.5)
    assert len(line) > 5
    kinds = [k for (_, k, _, _) in line]
    assert all(a != b for a, b in zip(kinds, kinds[1:])), "strictly alternating"
    assert [b for (b, _, _, _) in line] == sorted(b for (b, _, _, _) in line), "oldest first"
    pre, box, commits = turn_line_views(line, 0)
    assert len(pre) + len(box) == len(line), "the seam split keeps every turn"
    assert all(highs[b] == p for (b, k, p, _) in line if k == "peak")
    assert all(lows[b] == p for (b, k, p, _) in line if k == "valley")
    assert commits[(line[-1][0], line[-1][1])] is None, "only the edge turn is uncommitted"


def test_the_line_is_never_rebuilt_through_the_shared_zigzag():
    """The shared zigzag concatenates every peak before every valley and stable-sorts by bar, so rebuilding
    the line through it INVERTS a bar that carries both turns and the same-type merge then eats its
    neighbours. The views hand the line on as a finished list instead."""
    highs = np.array([10, 9, 8, 10.5, 10, 11.5, 12], dtype=float)
    lows = np.array([9.5, 8.5, 7.5, 6, 9, 10.5, 11], dtype=float)
    line = turn_line(highs, lows, 1.0)
    assert [(b, k) for (b, k, _, _) in line][1:3] == [(3, "valley"), (3, "peak")], "bar 3 carries both"
    rebuilt = _build_zigzag([b for (b, k, _, _) in line if k == "peak"],
                            [b for (b, k, _, _) in line if k == "valley"], highs, lows)
    assert len(rebuilt) < len(line), "the rebuild is lossy — this is why the views exist"
    pre, box, _ = turn_line_views(line, 2)
    assert len(pre) + len(box) == len(line), "the views lose nothing"
    assert [k for (_, k, _) in box][:2] == ["valley", "peak"], "and keep the same-bar pair in its own order"


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


# ── the event map's swing layer ──────────────────────────────────────────────

def _wave_frame():
    """A frame whose daily range is about 1, with waves of 4 to 6 — every wave clears a 0.75 floor."""
    path = np.interp(np.arange(60), [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 59],
                     [20.0, 14.0, 19.0, 12.0, 16.0, 11.0, 15.5, 11.5, 15.0, 11.0, 14.0])
    df = _frame(path + 0.5, path - 0.5, atr=1.0)
    return df, _Box(start_bar=20, R=15.5, S=11.0)


def test_the_swing_map_reads_the_line_only_under_the_flag(monkeypatch):
    df, box = _wave_frame()
    off = read_swing_map(df, box, 1.0)
    monkeypatch.setattr(settings, "TURN_LINE_ENABLED", True)
    on = read_swing_map(df, box, 1.0)
    assert off["n_swings"] != on["n_swings"] or [s["bar"] for s in off["swings"]] != [s["bar"] for s in on["swings"]], \
        "the line is a different substrate from the order-1 walk plus the box-height collapse"
    line = turn_line(df["High"].values.astype(float), df["Low"].values.astype(float),
                     turn_line_floors(df, 1.0))
    on_bars = {(s["bar"], s["kind"]) for s in on["swings"]}
    assert on_bars <= {(b, k) for (b, k, _, _) in line}, "every swing on the tape is a turn on the line"


def test_the_swing_map_stamps_the_line_s_own_commit_bar(monkeypatch):
    df, box = _wave_frame()
    monkeypatch.setattr(settings, "TURN_LINE_ENABLED", True)
    on = read_swing_map(df, box, 1.0)
    line = turn_line(df["High"].values.astype(float), df["Low"].values.astype(float),
                     turn_line_floors(df, 1.0))
    commits = turn_line_views(line, box.start_bar)[2]
    assert on["swings"], "the tape is not empty"
    for s in on["swings"]:
        assert s["knowable_bar"] == commits[(s["bar"], s["kind"])], s["bar"]
        assert s["in_progress"] is (s["knowable_bar"] is None)
    assert any(s["in_progress"] for s in on["swings"]), "the forming turn rides as in progress"


def test_the_line_does_not_collapse_twice(monkeypatch):
    """The line has applied its floor once; the shared staircase must be asked to collapse at zero, or the
    box-height amplitude filter would read the line's own turns as noise."""
    df, box = _wave_frame()
    monkeypatch.setattr(settings, "TURN_LINE_ENABLED", True)
    wide = read_swing_map(df, box, 1.0)
    monkeypatch.setattr(settings, "TRAVERSAL_NOISE_FRAC", 0.99)
    assert read_swing_map(df, box, 1.0)["n_swings"] == wide["n_swings"], \
        "the box-height collapse knob may not touch the line"


# ── the trend labels ─────────────────────────────────────────────────────────

def test_the_trend_labels_read_the_line_only_under_their_own_flag(monkeypatch):
    df, _ = _wave_frame()
    off = read_market_structure(df)
    monkeypatch.setattr(settings, "TURN_LINE_ENABLED", True)
    assert read_market_structure(df) == off, "the event map's flag does not move the trend labels"
    monkeypatch.setattr(settings, "TURN_LINE_TREND_ENABLED", True)
    on = read_market_structure(df)
    assert on["n_points"] != off["n_points"] or on["points"] != off["points"]
    line = turn_line(df["High"].values.astype(float), df["Low"].values.astype(float),
                     turn_line_floors(df, None))
    assert [(p["bar"], p["kind"]) for p in on["points"]] == [(b, k) for (b, k, _, _) in line]


def test_the_trend_labels_fall_back_when_the_frame_carries_no_daily_range(monkeypatch):
    bare = _frame(np.arange(40) % 7 + 10.5, np.arange(40) % 7 + 9.5)      # no ATR_10 column
    off = read_market_structure(bare)
    monkeypatch.setattr(settings, "TURN_LINE_TREND_ENABLED", True)
    assert read_market_structure(bare) == off, "no unit: today's skeleton, never a guessed floor"
    df, _ = _wave_frame()
    pinned = read_market_structure(df, order=2)
    monkeypatch.setattr(settings, "TURN_LINE_TREND_ENABLED", False)
    assert read_market_structure(df, order=2) == pinned, "a caller pinning an order keeps its own walk"


# ── the step-10 sites keep today's skeleton (review finding RF-4, Mon 14/09/2026) ──

def test_the_live_cause_veto_reads_today_s_walk_whatever_the_line_flag_says(monkeypatch):
    """Operand B of the LIVE cause-before-effect veto reads the swing map's trend states. The line is the event
    map's site; the veto folds into a graded trend fact at build step 10, so it keeps today's walk until then."""
    import engine_alpha.structure.events.event_map as em
    import engine_alpha.structure.phases.phase_a as pa
    from engine_alpha.structure.narrative.bricks import cause_maturity

    df, box = _wave_frame()
    monkeypatch.setattr(pa, "macro_bridge_zigzag", lambda *a, **k: [])      # the bridge abstains: Operand B runs
    real, seen = em.read_swing_map, []
    monkeypatch.setattr(em, "read_swing_map", lambda *a, **k: seen.append(k.get("line")) or real(*a, **k))
    off = cause_maturity(df, box, 1.0)
    monkeypatch.setattr(settings, "TURN_LINE_ENABLED", True)
    on = cause_maturity(df, box, 1.0)
    assert seen == [False, False], "Operand B pins today's walk"
    assert (on.pre_box_trend, on.box_trend) == (off.pre_box_trend, off.box_trend)


def test_the_phase_a_climax_repair_reads_today_s_skeleton_whatever_the_trend_flag_says(monkeypatch):
    from engine_alpha.structure.events.market_structure import segment_trends, trend_terminal_floor

    df, _ = _wave_frame()
    off = trend_terminal_floor(df)
    monkeypatch.setattr(settings, "TURN_LINE_TREND_ENABLED", True)
    unpinned = trend_terminal_floor(df, segments=segment_trends(read_market_structure(df)["points"]))
    assert not all(np.array_equal(a, b, equal_nan=True) for a, b in zip(off, unpinned)), \
        "on this frame the line's trend segments differ from the skeleton's"
    on = trend_terminal_floor(df)
    assert all(np.array_equal(a, b, equal_nan=True) for a, b in zip(off, on)), \
        "the painter's trend floor keeps today's skeleton until build step 10"


def test_a_caller_may_pin_either_reader_s_walk(monkeypatch):
    df, box = _wave_frame()
    walk_map, walk_labels = read_swing_map(df, box, 1.0), read_market_structure(df)
    line_map, line_labels = read_swing_map(df, box, 1.0, line=True), read_market_structure(df, line=True)
    assert walk_map != line_map and walk_labels != line_labels, "the two substrates differ on this frame"
    monkeypatch.setattr(settings, "TURN_LINE_ENABLED", True)
    monkeypatch.setattr(settings, "TURN_LINE_TREND_ENABLED", True)
    assert read_swing_map(df, box, 1.0) == line_map and read_market_structure(df) == line_labels
    assert read_swing_map(df, box, 1.0, line=False) == walk_map, "line=False keeps today's walk under the flag"
    assert read_market_structure(df, line=False) == walk_labels, "line=False keeps today's skeleton under the flag"


# ── the opening turn (review findings F3 and TG-8, Mon 14/09/2026) ──

def test_the_line_opens_on_the_older_running_extreme_not_on_bar_0():
    """Price dips 0.4 under bar 0 before its first leg covers the floor: the opening valley is that lower low,
    known on the bar where the leg covered its floor."""
    line = turn_line([9.2, 8.9, 9.9, 9.4], [9.0, 8.6, 9.7, 9.1], 1.0)
    assert line == [(1, "valley", 8.6, 2), (2, "peak", 9.9, None)]


def test_a_rise_that_tops_on_a_bar_with_no_readable_floor_still_opens_the_line_upward():
    line = turn_line([10, 11, 10.3, 10.9], [9.8, 10.1, 10.2, 10.5], [np.nan, np.nan, 0.75, 0.75])
    assert line == [(0, "valley", 9.8, 0), (1, "peak", 11.0, 2), (2, "valley", 10.2, None)], \
        "the 11.0 top on the unreadable bar is the extreme the first fall is measured from"
