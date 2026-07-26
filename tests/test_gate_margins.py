"""Margin measurement core (near-miss lane Task 3) — sign-locked native quanta.

The properties that must hold regardless of calibration: the count math's
integer forms are exact translations of the gate's fraction thresholds
(hand-derived pins), the respect stats are ONE pass (the legacy verdict tuple
derives from the extended one), close-residence counts are the ground truth
the judged fractions derive from, and the full-vector completion's pass
verdicts reproduce the real gates' verdicts on the same window — the
self-check contract, proven against the gate itself rather than asserted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.structure.box_gates import (
    _is_boundary_respected,
    _measure_close_residence,
    _respect_stats,
    _validate_base_quality,
)
from engine_alpha.structure.gate_margins import (
    complete_leg_vector,
    count_allowed,
    count_needed,
    outside_allowed,
)

pytestmark = pytest.mark.regression


def _frame(closes, lo_off=0.4, hi_off=0.4):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "High": closes + hi_off,
        "Low": closes - lo_off,
        "Close": closes,
    })


def _boxy_closes(n=40, lo=100.0, hi=110.0):
    out = []
    for i in range(n):
        cyc = i % 8
        out.append(lo + (hi - lo) * (cyc / 4 if cyc <= 4 else (8 - cyc) / 4))
    return out


def test_count_math_is_the_exact_integer_form_of_the_fraction_thresholds():
    # Hand-derived: 4/27 = 0.1481 < 0.15 but 5/27 = 0.1852 >= 0.15.
    assert count_needed(0.15, 20) == 3
    assert count_needed(0.15, 27) == 5
    # 9/20 = 0.45 passes the cap; 10/21 = 0.476 breaks it, 9/21 = 0.4286 holds.
    assert count_allowed(0.45, 20) == 9
    assert count_allowed(0.45, 21) == 9
    # 1 - 4/20 = 0.80 passes; 1 - 5/27 = 0.8148 passes, 6/27 outside fails.
    assert outside_allowed(0.80, 20) == 4
    assert outside_allowed(0.80, 27) == 5
    # Exactness at a representable boundary: no epsilon drift on n*frac int.
    assert count_needed(0.5, 10) == 5
    assert count_allowed(0.5, 10) == 5


def test_respect_stats_is_one_pass_and_the_legacy_tuple_derives():
    closes = _boxy_closes(60) + [125.0] * 12
    df = _frame(closes)
    highs, lows = df["High"].values, df["Low"].values
    stats = _respect_stats(highs, lows, 110.4, 99.6, 1.0)
    assert _is_boundary_respected(highs, lows, 110.4, 99.6, 1.0) == stats[:5]
    # The surfaced run maximum is the hand-built 12-bar breakout shelf.
    assert stats[5] == 12
    assert stats[6] == 12 and stats[7] == 0     # all above R, none below S


def test_close_residence_counts_are_the_ground_truth():
    df = _frame(_boxy_closes())
    eq = _measure_close_residence(df, 110.4, 99.6, 1.0)
    n = eq["n"]
    assert n == len(df)
    assert eq["lower_dwell"] == round(eq["lower_count"] / n, 4)
    assert eq["mid_dwell"] == round(eq["mid_count"] / n, 4)
    assert eq["upper_dwell"] == round(eq["upper_count"] / n, 4)
    assert eq["coverage"] == round(eq["coverage_occupied"] / eq["coverage_bins"], 4)
    assert eq["lower_count"] + eq["mid_count"] + eq["upper_count"] == n


def test_completion_vector_reproduces_the_real_gate_verdicts():
    for closes in (_boxy_closes(),                       # worked range
                   _boxy_closes(16) + [105.0] * 24,      # occupancy-starved
                   _boxy_closes(60) + [125.0] * 12):     # run-cap breaker
        df = _frame(closes)
        R, S, atr = 110.4, 99.6, 1.0
        rows = complete_leg_vector(df, R, S, atr)
        assert rows is not None
        assert "window" not in rows              # floor not consulted here
        assert len(rows) == 14
        # The vector's respect verdicts recompose the gate's own verdict.
        respected, *_ = _is_boundary_respected(
            df["High"].values, df["Low"].values, R, S, atr)
        assert respected == (rows["respect_share"]["passed"]
                             and rows["respect_run"]["passed"])
        # The occupancy-family verdicts recompose _validate_base_quality.
        _rt, _st, eq, is_valid = _validate_base_quality(df, R, S, atr)
        family = ("r_touches", "s_touches", "r_touch_thirds", "s_touch_thirds",
                  "lower_dwell", "upper_dwell", "mid_dwell", "coverage")
        if eq is not None:
            assert is_valid == all(rows[leg]["passed"] for leg in family)
            assert rows["crash"]["passed"]
        # Sign-lock holds on every row (construction raises on mismatch, so
        # reaching here IS the proof; assert the invariant explicitly anyway).
        for row in rows.values():
            assert (row["margin"] >= 0) == row["passed"]


def test_per_leg_margins_match_the_hand_derivation():
    """Task-12 per-leg battery: ONE eye-readable 20-bar frame, every native
    margin derived BY HAND against the live calibration (heterogeneous units
    are exactly where pasted-output tautologies hide — these numbers were
    written on paper first, then asserted).

    Frame: box R=110/S=100, ATR=1. Six floor bars (close 100.2; lows touch
    S), four mid bars (105), ten ceiling bars (109.8; highs touch R). Hand
    counts: s_touches 6 (first third only -> 1 third), r_touches 10 (thirds
    2+3), dwell counts 6/4/10 of n=20, zero outside bars, min low 99.8,
    width 0.10, three occupied coverage bins, zero rail-to-rail traversals.
    """
    closes = [100.2] * 6 + [105.0] * 4 + [109.8] * 10
    df = _frame(closes)
    rows = complete_leg_vector(df, 110.0, 100.0, 1.0)
    assert rows is not None

    got = {leg: r["margin"] for leg, r in rows.items()}
    assert got["width"] == pytest.approx(settings.MAX_BOX_WIDTH - 0.10)
    assert got["respect_share"] == outside_allowed(
        settings.MIN_BOUNDARY_RESPECT_PCT, 20) - 0          # zero outside
    assert got["respect_run"] == settings.MAX_CONSECUTIVE_OUTSIDE_DAYS - 0
    assert got["crash"] == pytest.approx(99.8 / 100.0 - settings.CRASH_FILTER_MULT)
    assert got["r_touches"] == 10 - settings.EQ_MIN_TOUCHES_PER_RAIL
    assert got["s_touches"] == 6 - settings.EQ_MIN_TOUCHES_PER_RAIL
    assert got["r_touch_thirds"] == 2 - settings.EQ_MIN_TOUCH_THIRDS
    assert got["s_touch_thirds"] == 1 - settings.EQ_MIN_TOUCH_THIRDS
    assert got["lower_dwell"] == 6 - count_needed(settings.EQ_MIN_HALF_DWELL, 20)
    assert got["upper_dwell"] == 10 - count_needed(settings.EQ_MIN_HALF_DWELL, 20)
    assert got["mid_dwell"] == count_allowed(settings.EQ_MAX_MID_DWELL, 20) - 4
    assert got["coverage"] == 3 - count_needed(settings.EQ_MIN_COVERAGE,
                                               settings.EQ_COVERAGE_BINS)
    assert got["traversal_count"] == 0 - settings.TRAVERSAL_MIN
    assert got["traversal_density"] == pytest.approx(
        -settings.TRAVERSAL_MIN_DENSITY)
    # At the LIVE calibration the hand numbers read: width +0.08,
    # respect +4/+10, crash +0.298, touches +7/+3, thirds 0/-1,
    # dwell +3/+7, mid +5, coverage -2 (3 of 6 bins occupied, 5 needed;
    # the first paper pass assumed 10 bins — corrected against
    # EQ_COVERAGE_BINS=6), traversal -2/-0.080.
    assert got["s_touch_thirds"] == -1 and got["coverage"] == -2


def test_completion_vector_window_leg_and_degenerate_refusals():
    df = _frame(_boxy_closes())
    rows = complete_leg_vector(df, 110.4, 99.6, 1.0, min_candidate_days=25)
    assert rows["window"]["measured"] == len(df)
    assert rows["window"]["margin"] == len(df) - 25
    assert rows["window"]["passed"]

    assert complete_leg_vector(df.iloc[:0], 110.4, 99.6, 1.0) is None
    assert complete_leg_vector(df, 99.6, 110.4, 1.0) is None      # inverted
    assert complete_leg_vector(df, 110.4, 99.6, float("nan")) is None
    assert complete_leg_vector(None, 110.4, 99.6, 1.0) is None
