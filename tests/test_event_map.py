"""Event Map mechanical layer — Task 4 guards.

Pins the three load-bearing properties of ``core.structure.event_map``:

1. **The in-box slice IS the staircase** — the tape's ``region == "box"`` swings,
   re-based and stripped of tape-only fields, equal ``read_box_staircase`` over
   ``df.iloc[box.start_bar:]`` byte-for-byte (the plan's widen-don't-fork rule).
2. **One walk, provably** — full-frame order-1 pivots filtered to a window equal
   the windowed walk's own pivots (the equality the slicing rests on).
3. **Causality stamps** — ``knowable_bar`` marks real commitment (truncating the
   frame at/after it reproduces the swing identically; before it, the swing is
   absent or provisional), the right-edge swing is ``in_progress``, and NaN bars
   are counted and fail closed.

Synthetic frames only — deterministic, instant. The corpus/panel-scale proof is
the Task-4 capture battery (staircase pre/post diff + tape projection), run as a
build step, not here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from core.structure.box_events import read_box_staircase
from core.structure.event_map import read_swing_map
from core.structure.pivots import _find_pivots

pytestmark = pytest.mark.regression

_TAPE_ONLY = ("region", "describes_bar", "knowable_bar", "in_progress",
              "edge_uncertain")


@dataclass
class _Box:
    start_bar: int
    R: float
    S: float


def _frame_from_path(path):
    """Bars whose High/Low straddle a piecewise path — pivots land exactly on
    the path's local extremes, so the expected skeleton is readable by eye."""
    path = np.asarray(path, dtype=float)
    return pd.DataFrame({"High": path + 0.5, "Low": path - 0.5})


def _zigzag_path(waypoints, n):
    """Piecewise-linear path through (bar, price) waypoints, length n."""
    bars = [b for b, _ in waypoints]
    prices = [p for _, p in waypoints]
    return np.interp(np.arange(n), bars, prices)


def _project_box_swings(tape, start):
    out = []
    for s in tape["swings"]:
        if s["region"] != "box":
            continue
        s = {k: v for k, v in s.items() if k not in _TAPE_ONLY}
        s["bar"] = int(s["bar"]) - start
        out.append(s)
    return out


def _demo_frame():
    """Downtrend into a 4-traversal box, breakout tail past the rail."""
    n = 72
    path = _zigzag_path(
        [(0, 30.0), (4, 24.0), (7, 27.0), (11, 20.0),           # pre-box downtrend
         (14, 23.0), (18, 11.5),
         (20, 11.0), (25, 14.0), (30, 10.5), (35, 13.8),        # box S~10.5 R~14
         (40, 10.6), (46, 13.9), (52, 10.4), (58, 13.7),
         (63, 11.0), (68, 15.5), (71, 16.5)],                   # right of the rail
        n)
    return _frame_from_path(path), _Box(start_bar=18, R=14.0, S=10.0)


def test_in_box_slice_is_byte_identical_to_staircase():
    df, box = _demo_frame()
    atr = 1.0
    tape = read_swing_map(df, box, atr)
    stair = read_box_staircase(df.iloc[box.start_bar:], box.R, box.S, atr)

    assert _project_box_swings(tape, box.start_bar) == stair["swings"]
    assert tape["box"] == {
        "n_swings": stair["n_swings"], "trend_state": stair["trend_state"],
        "counts": stair["counts"], "rail_to_rail": stair["rail_to_rail"],
        "is_zigzag": stair["is_zigzag"],
    }
    # The widening is additive: the pre-box trend is now readable too.
    assert tape["pre_box"]["n_swings"] >= 2
    assert all(s["bar"] <= box.start_bar for s in tape["swings"]
               if s["region"] == "pre_box")


def test_box_at_frame_start_has_empty_pre_view():
    df, _ = _demo_frame()
    box = _Box(start_bar=0, R=14.0, S=10.0)
    tape = read_swing_map(df, box, 1.0)
    stair = read_box_staircase(df, box.R, box.S, 1.0)
    assert tape["pre_box"]["n_swings"] == 0
    assert _project_box_swings(tape, 0) == stair["swings"]


def test_one_walk_pivot_window_equality():
    """The slicing hinge: full-frame order-1 pivots restricted to bars > start
    (and re-based) are EXACTLY the windowed walk's pivots."""
    rng = np.random.default_rng(7)
    for _ in range(25):
        mid = np.cumsum(rng.normal(0.0, 1.0, 140)) + 50.0
        spread = rng.uniform(0.2, 1.0, 140)
        highs, lows = mid + spread, mid - spread
        peaks, valleys = _find_pivots(highs, lows, 1)
        for start in (0, 4, 23, 61):
            wp, wv = _find_pivots(highs[start:], lows[start:], 1)
            assert [p - start for p in peaks if p >= start + 1] == wp
            assert [v - start for v in valleys if v >= start + 1] == wv


def test_knowable_bar_marks_real_commitment_and_edge_is_in_progress():
    df, box = _demo_frame()
    tape = read_swing_map(df, box, 1.0)
    swings = tape["swings"]
    assert swings, "demo frame must produce swings"

    committed = [s for s in swings if not s["in_progress"]]
    assert committed, "demo frame must commit swings"
    for s in committed:
        assert s["knowable_bar"] > s["describes_bar"] == s["bar"]
    # The frame's last swing has no committing reversal printed -> provisional.
    assert swings[-1]["in_progress"] and swings[-1]["knowable_bar"] is None
    # Left-edge rule: the frame's first swing is boundary-uncertain.
    assert swings[0].get("edge_uncertain") is True


def test_truncation_reproduces_committed_swings():
    """Contract §7 at the mechanical level: relabeling a truncated frame yields
    exactly the full frame's swings that were knowable inside the cut. (At view
    birth — fewer than 3 raw pivots in a window — the staircase guards emit
    nothing, so cuts start past the demo box's first traversal.)"""
    df, box = _demo_frame()
    full = read_swing_map(df, box, 1.0)

    def _sig(swings):
        return [(s["bar"], s["kind"], s["price"], s["label"], s["region"],
                 s["knowable_bar"]) for s in swings]

    for cut in range(34, len(df) + 1):
        trunc = read_swing_map(df.iloc[:cut], box, 1.0)
        got = _sig(s for s in trunc["swings"] if not s["in_progress"])
        want = _sig(s for s in full["swings"]
                    if s["knowable_bar"] is not None
                    and s["knowable_bar"] <= cut - 1)
        assert got == want, f"cut={cut}"


def test_nan_bars_are_counted_and_fail_closed():
    df, box = _demo_frame()
    df = df.copy()
    df.loc[df.index[40:43], ["High", "Low"]] = np.nan
    tape = read_swing_map(df, box, 1.0)
    assert tape["nan_bars"] == 3
    assert all(s["bar"] not in (40, 41, 42) for s in tape["swings"])


def test_degenerate_inputs_return_empty_shape():
    df, box = _demo_frame()
    empty_keys = {"swings", "n_swings", "pre_box", "box", "start_bar",
                  "n_bars", "nan_bars"}
    for bad_df, bad_box, bad_atr in (
        (None, box, 1.0),
        (df.iloc[:0], box, 1.0),
        (df, None, 1.0),
        (df, _Box(start_bar=18, R=10.0, S=14.0), 1.0),   # inverted rails
        (df, box, 0.0),
        (df, box, float("nan")),
        (df, _Box(start_bar=len(df), R=14.0, S=10.0), 1.0),
    ):
        tape = read_swing_map(bad_df, bad_box, bad_atr)
        assert set(tape) == empty_keys and tape["swings"] == []
