import math
import json
from datetime import datetime, timezone
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from engine_alpha.structure.metrics import (
    _vol_trend_from_contractions,
    measure_bar_compression,
    measure_contractions,
    measure_dwell_balance,
    measure_equilibrium,
)
from engine_alpha.structure.box_gates import _dwell_bar_basis, _validate_base_quality
from engine_alpha.structure.box_primitives import select_phase_b_candidate
from engine_alpha.structure.inner_box import (
    _detect_inner_phase_b_start,
    detect_inner_root_swing,
)
from engine_alpha.structure.segmentation import segment_swings


def test_segment_swings_finds_root_bridge(_ramp_frame, monkeypatch):
    # This is a unit test of the ORDER-N root-bridge detection — the live
    # abstention fallback of the (now unconditional) macro read. Pin the macro
    # read to ABSTAIN so segment_swings exercises the order-N zigzag asserted
    # below through the real fallback seam; the macro STORY path (a different,
    # valid skeleton) is exercised in test_phase_a.
    from engine_alpha.structure import phase_a
    monkeypatch.setattr(phase_a, "macro_bridge_zigzag", lambda *a, **k: [])
    # Up-trend (with small pullbacks) into a climax at 60, then a big counter-
    # burst down to 53 (the AR), then a tight range. The root swing is the
    # 60 -> 53 leg: it terminates the trend and births the range.
    df = _ramp_frame([50, 53, 51.5, 56, 54, 60, 53, 56, 53.5, 56, 53.5])

    res = segment_swings(df, atr_val=1.0)

    assert res["dominant_direction"] == 1
    assert res["n_swings"] == 8

    root = res["root_swing"]
    assert root is not None
    assert root["bc_bar"] == 30           # climax pivot (price 60)
    assert root["ar_bar"] == 36           # first counter-burst valley (price 53)
    assert root["counter_disp_atr"] == 7.0
    # The AR (7 ATR) dwarfs the trend's pullbacks (median 1.75 ATR) -> ~4x burst.
    assert root["counter_burst_ratio"] == 4.0

    # Efficiency is a real ratio in [0, 1]; the AR is the single largest swing.
    assert 0.0 <= res["efficiency"] <= 1.0
    assert max(s["abs_disp_atr"] for s in res["swings"]) == 7.0


def test_phase_b_select_best_takes_global_best(_cand):
    # A later, tighter (higher-combined) pair vs an earlier, looser one.
    early_loose = _cand(combined=0.50, cand_start=10)
    late_tight = _cand(combined=0.80, cand_start=40)
    chosen = select_phase_b_candidate([early_loose, late_tight], "best")
    assert chosen is late_tight  # best == highest combined, regardless of start


def test_phase_b_select_earliest_prefers_earlier_start(_cand):
    # Every candidate has already passed worked-equilibrium validity, so
    # "earliest" takes the earliest start (longest cause) even when a later
    # framing scores higher combined. There is no reach-quality floor anymore:
    # a sparse / dead-space framing can no longer be a valid candidate, so the
    # old "is the early framing good enough?" question is moot.
    early = _cand(combined=0.60, cand_start=10)
    late_tight = _cand(combined=0.80, cand_start=40)
    chosen = select_phase_b_candidate([late_tight, early], "earliest")
    assert chosen is early


def test_phase_b_select_earliest_breaks_ties_by_quality(_cand):
    # When two valid framings start on the same bar, the higher-combined one
    # wins the tie (the -x[0] secondary key).
    start_lo = _cand(combined=0.50, cand_start=10)
    start_hi = _cand(combined=0.80, cand_start=10)
    chosen = select_phase_b_candidate([start_lo, start_hi], "earliest")
    assert chosen is start_hi


def test_phase_b_select_earliest_never_empties_pool(_cand):
    # A single candidate is always returned (it is, by construction, valid).
    only = _cand(combined=0.30, cand_start=5)
    assert select_phase_b_candidate([only], "earliest") is only


def test_collapse_swings_absorbs_never_deletes_a_committed_swing():
    """EC-48 correction (2026-08-25 sweep): a committed swing followed by a
    sub-threshold counter-pivot is ABSORBED (the committed extreme stays),
    never deleted — the old pop form erased it, permanently at the tail."""
    from engine_alpha.structure.pivots import _collapse_swings

    v0, p5, v8 = (0, "valley", 100.0), (5, "peak", 110.0), (8, "valley", 108.5)
    # The tail case: the small pullback must not erase the committed peak.
    assert _collapse_swings([v0, p5, v8], min_amp=5.0) == [v0, p5]
    # Mid-sequence: absorb, then the running extreme extends through the
    # same-type merge, and a genuine reversal commits off the extended peak.
    p12, v20 = (12, "peak", 112.0), (20, "valley", 101.0)
    out = _collapse_swings([v0, p5, v8, p12, v20], min_amp=5.0)
    assert out == [v0, p12, v20]
    kinds = [k for _b, k, _p in out]
    assert kinds == ["valley", "peak", "valley"]     # alternation preserved


_WORKED = [101, 103, 105, 107, 109, 107, 105, 103] * 3


_DEAD_SPACE = [100, 102] + [106, 109, 107, 108, 106, 109, 107, 108] * 2 + [106, 109, 107, 108, 106, 109]


def test_measure_dwell_balance_worked_range_is_filled_and_two_sided(_osc_frame):
    eq = measure_dwell_balance(_osc_frame(_WORKED), R=110.0, S=100.0, atr_val=1.0)
    assert eq["r_touches"] >= 3 and eq["s_touches"] >= 3
    assert eq["r_touch_thirds"] >= 2 and eq["s_touch_thirds"] >= 2
    assert eq["lower_dwell"] >= 0.15 and eq["upper_dwell"] >= 0.15
    assert eq["mid_dwell"] <= 0.85
    assert eq["coverage"] >= 0.80


def test_measure_dwell_balance_dead_space_starves_the_lower_half(_osc_frame):
    eq = measure_dwell_balance(_osc_frame(_DEAD_SPACE), R=110.0, S=100.0, atr_val=1.0)
    # Price lives up top after a one-time dip: the lower half is dead (dwell
    # collapses there) while the upper half hogs the action.
    assert eq["lower_dwell"] < 0.15
    assert eq["upper_dwell"] > 0.45


def test_measure_dwell_balance_nan_bar_occupies_nothing(_osc_frame):
    """One NaN bar used to wrap through the int cast and stamp occupancy on
    EVERY coverage bin (2026-08-25 sweep). NaN routes to EXCLUDED instead,
    matching the dwell legs' own False comparisons."""
    clean = measure_dwell_balance(_osc_frame(_DEAD_SPACE),
                                  R=110.0, S=100.0, atr_val=1.0)
    df = _osc_frame(_DEAD_SPACE)
    df.iloc[3, df.columns.get_loc("Low")] = np.nan
    eq = measure_dwell_balance(df, R=110.0, S=100.0, atr_val=1.0)
    assert eq["coverage"] <= clean["coverage"]      # never fabricated upward
    assert eq["lower_dwell"] < 0.15                 # the starved half stays starved


def test_measure_dwell_balance_range_occupancy_uses_high_low_not_close():
    frame = pd.DataFrame([
        {"High": 110.0, "Low": 100.0, "Close": 105.0},
        {"High": 110.0, "Low": 100.0, "Close": 105.0},
        {"High": 110.0, "Low": 100.0, "Close": 105.0},
    ])

    eq = measure_dwell_balance(frame, R=110.0, S=100.0, atr_val=1.0)

    assert eq["r_touches"] == 3
    assert eq["s_touches"] == 3
    assert eq["lower_dwell"] == 1.0
    assert eq["mid_dwell"] == 1.0
    assert eq["upper_dwell"] == 1.0
    assert eq["coverage"] == 1.0


def test_measure_gate_margins_reports_the_gates_own_statistics():
    # Three flat bars fully inside [S-buffer, R+buffer], closes mid-box: the
    # respect fraction is 1.0 and the close-residence dwell is all-mid — the
    # GATE's statistic, not the range-occupancy twin (which reads 1.0 in every
    # third for these bars). Hand-specified, not read off the code.
    from engine_alpha.structure.metrics import measure_gate_margins
    frame = pd.DataFrame([
        {"High": 106.0, "Low": 104.0, "Close": 105.0},
        {"High": 106.0, "Low": 104.0, "Close": 105.0},
        {"High": 106.0, "Low": 104.0, "Close": 105.0},
    ])
    gm = measure_gate_margins(frame, 110.0, 100.0, 1.0)
    assert gm["respect_frac"] == 1.0
    assert gm["close_lower_dwell"] == 0.0
    assert gm["close_mid_dwell"] == 1.0
    assert gm["close_upper_dwell"] == 0.0
    # Move 1 dark measures: fully-inside bars — engagement basis agrees with
    # the wick basis, and the deepest excursion is a real measured 0.0.
    assert gm["engagement_respect_frac"] == 1.0
    assert gm["max_excursion_atr"] == 0.0


def test_measure_gate_margins_counts_wick_breaches_and_degrades_to_none():
    from engine_alpha.structure.metrics import measure_gate_margins
    # One of four bars wicks above R + 0.5*ATR buffer -> respect 0.75.
    frame = pd.DataFrame([
        {"High": 106.0, "Low": 104.0, "Close": 105.0},
        {"High": 111.0, "Low": 104.0, "Close": 105.0},  # wick past 110.5
        {"High": 106.0, "Low": 104.0, "Close": 105.0},
        {"High": 106.0, "Low": 104.0, "Close": 105.0},
    ])
    gm = measure_gate_margins(frame, 110.0, 100.0, 1.0)
    assert gm["respect_frac"] == 0.75
    # Move 1 dark measures discriminate: the 0.5-ATR poke past R+buffer that
    # CLOSED back inside hangs on the engagement basis (respect 1.0 vs the
    # wick basis 0.75), and the excursion depth is the measured 0.5 ATR.
    # Hand-specified: High 111.0 vs ceiling 110.5 with ATR 1.0.
    assert gm["engagement_respect_frac"] == 1.0
    assert gm["max_excursion_atr"] == 0.5
    # Degenerate inputs return the all-None dict, never a crash.
    empty = measure_gate_margins(frame.iloc[:0], 110.0, 100.0, 1.0)
    assert empty == {"respect_frac": None, "close_lower_dwell": None,
                     "close_mid_dwell": None, "close_upper_dwell": None,
                     "engagement_respect_frac": None, "max_excursion_atr": None}
    assert measure_gate_margins(frame, 100.0, 110.0, 1.0)["respect_frac"] is None


def test_validate_base_quality_accepts_worked_rejects_dead_space(_osc_frame):
    # A genuinely worked range validates; a dead-space range does not.
    _rt, _st, _eq, ok_worked = _validate_base_quality(
        _osc_frame(_WORKED), 110.0, 100.0, 1.0)
    _rt2, _st2, _eq2, ok_dead = _validate_base_quality(
        _osc_frame(_DEAD_SPACE), 110.0, 100.0, 1.0)
    assert ok_worked is True
    assert ok_dead is False


_EGBN_SHAPE = pd.DataFrame([
    # The EGBN twin (bar_dwell_protocol §3): closes hug the top of the box, so
    # close-residence starves the lower third (2/20 = 0.10 < 0.15) — but the
    # bar LOWS probe it (5/20 = 0.25): support IS tested, by bars whose closes
    # recover. Everything else passes on both bases (touches both rails across
    # thirds, close coverage 6/6 bins, close mid 7/20, zero resident-mid bars).
    {"High": 110.0, "Low": 106.0, "Close": 109.0},
    {"High": 110.0, "Low": 106.0, "Close": 108.0},
    {"High": 109.0, "Low": 100.0, "Close": 101.0},
    {"High": 110.0, "Low": 105.0, "Close": 108.0},
    {"High": 108.0, "Low": 104.0, "Close": 106.0},
    {"High": 109.0, "Low": 103.0, "Close": 105.0},
    {"High": 110.0, "Low": 106.0, "Close": 109.0},
    {"High": 109.0, "Low": 100.0, "Close": 102.8},
    {"High": 108.0, "Low": 104.0, "Close": 107.0},
    {"High": 110.0, "Low": 105.0, "Close": 108.0},
    {"High": 109.0, "Low": 104.0, "Close": 106.0},
    {"High": 108.0, "Low": 104.0, "Close": 105.0},
    {"High": 110.0, "Low": 106.0, "Close": 109.0},
    {"High": 109.0, "Low": 100.0, "Close": 104.5},
    {"High": 108.0, "Low": 104.0, "Close": 107.0},
    {"High": 110.0, "Low": 105.0, "Close": 108.0},
    {"High": 109.0, "Low": 104.0, "Close": 106.0},
    {"High": 110.0, "Low": 106.0, "Close": 109.0},
    {"High": 108.0, "Low": 103.0, "Close": 105.0},
    {"High": 110.0, "Low": 106.0, "Close": 109.5},
])


def test_egbn_shape_close_gate_rejects_bar_measure_documents():
    # The gate (close residence — the LIVE basis; the bar-basis GATE variant
    # was tested and REJECTED 2026-07-25, see _dwell_bar_basis): the sole
    # failing leg is close lower dwell.
    _rt, _st, eq, ok = _validate_base_quality(_EGBN_SHAPE, 110.0, 100.0, 1.0)
    assert ok is False
    assert eq["lower_dwell"] == 0.10
    assert eq["upper_dwell"] >= 0.15 and eq["mid_dwell"] <= 0.45

    # The measure-only bar-unit read documents WHY the operator disagrees:
    # the same window's bar-lows DID work the lower third.
    lower, mid, _upper = _dwell_bar_basis(_EGBN_SHAPE, 110.0, 100.0)
    assert lower == 0.25                         # 5/20 bar-lows reach the lower third
    assert mid == 0.0                            # no bar lives entirely interior


def test_dwell_bar_basis_residency_and_nan_routes():
    # Interior-resident bars are mid churn; bars reaching an end zone are not;
    # a NaN-extreme bar lands in NO bucket (denominator still counts it).
    frame = pd.DataFrame([
        {"High": 106.0, "Low": 104.0, "Close": 105.0},   # resident interior
        {"High": 106.0, "Low": 104.0, "Close": 105.0},   # resident interior
        {"High": 110.0, "Low": 104.0, "Close": 108.0},   # reaches upper -> not mid
        {"High": 106.0, "Low": 100.0, "Close": 104.0},   # reaches lower -> not mid
        {"High": float("nan"), "Low": float("nan"), "Close": 105.0},  # no bucket
    ])
    lower, mid, upper = _dwell_bar_basis(frame, 110.0, 100.0)
    assert lower == 0.2 and upper == 0.2 and mid == 0.4


def test_engagement_measure_hangs_are_bounded_and_close_confirmed():
    """Move 1 (gap-breach Task 3, MEASURE-ONLY — the election-variant form
    was tested and rejected 2026-07-24): the archived engagement read must
    discriminate in BOTH directions. Hand-specified (R 110, S 100, ATR 1 ->
    ceiling 110.5; bound 1.5 ATR): a 1.0-ATR poke that closes back inside
    hangs; a close-out bar and a deep 2.5-ATR poke NEVER hang."""
    from engine_alpha.structure.metrics import measure_gate_margins

    def _frame(high_last, close_last):
        rows = [{"High": 106.0, "Low": 104.0, "Close": 105.0}] * 3
        rows.append({"High": high_last, "Low": 104.0, "Close": close_last})
        return pd.DataFrame(rows)

    # Bounded poke (1.0 ATR past the ceiling), closed back inside -> hangs.
    gm = measure_gate_margins(_frame(111.5, 110.0), 110.0, 100.0, 1.0)
    assert gm["respect_frac"] == 0.75
    assert gm["engagement_respect_frac"] == 1.0
    assert gm["max_excursion_atr"] == 1.0
    # Close-out beyond the ceiling: never a hang (upthrust defense).
    gm = measure_gate_margins(_frame(111.5, 111.0), 110.0, 100.0, 1.0)
    assert gm["engagement_respect_frac"] == 0.75
    # Deep 2.5-ATR excursion: never a hang even closing back inside.
    gm = measure_gate_margins(_frame(113.0, 110.0), 110.0, 100.0, 1.0)
    assert gm["engagement_respect_frac"] == 0.75
    assert gm["max_excursion_atr"] == 2.5
    # Declared NaN route (conservative by contract, not by accident): an
    # outside bar whose Close is NaN must NOT hang — it stays a full outside
    # day. Pinned at the helper (live frames are finite; only the masks own
    # this route): a refactor flipping the comparison direction would quietly
    # inflate every archived engagement_respect_frac with the battery green.
    from engine_alpha.structure.box_gates import (
        _engagement_hang_masks,
        _rail_outside_masks,
    )

    nan_frame = _frame(111.5, float("nan"))
    highs = nan_frame["High"].to_numpy(float)
    lows = nan_frame["Low"].to_numpy(float)
    closes = nan_frame["Close"].to_numpy(float)
    above_r, below_s, r_ceiling, s_floor = _rail_outside_masks(
        highs, lows, 110.0, 100.0, 1.0)
    assert bool(above_r[-1])                       # it IS an outside bar
    hang_r, hang_s = _engagement_hang_masks(
        above_r, below_s, highs, lows, closes, r_ceiling, s_floor, 1.0)
    assert not hang_r.any() and not hang_s.any()   # NaN close never hangs


def test_worked_window_end_trims_only_a_held_late_breakout():
    # The SOS -> BUEC rescue: a worked range whose right side has broken out above
    # R and HELD above support is validated over its cause, not the breakout tail.
    from engine_alpha.structure.box_primitives import _worked_window_end
    R, S, atr = 110.0, 100.0, 1.0          # buffer = BOUNDARY_ATR_BUFFER * atr
    base_h, base_l = [105.0] * 20, [104.0] * 20
    # A sustained breakout above R that holds above S -> trim exactly the tail.
    assert _worked_window_end(base_h + [118.0] * 6, base_l + [115.0] * 6,
                              R, S, atr) == 20
    # An all-in-range window has no breakout tail -> no-op (full length).
    assert _worked_window_end([105.0] * 26, [104.0] * 26, R, S, atr) == 26
    # A 2-bar poke is below SOS_TRIM_MIN_RUN -> not a breakout -> no trim.
    assert _worked_window_end(base_h + [118.0] * 2 + [105.0] * 4,
                              base_l + [115.0] * 2 + [104.0] * 4, R, S, atr) == 26
    # A breakout that loses support afterwards is a breakdown, not SOS -> no trim.
    assert _worked_window_end(base_h + [118.0] * 4 + [105.0] * 2,
                              base_l + [115.0] * 4 + [90.0] * 2, R, S, atr) == 26


def test_measure_equilibrium_counts_rail_to_rail_swings(_osc_frame):
    # The worked triangle wave runs the full box repeatedly: many genuine
    # rail-to-rail traversals and no dead space at either rail.
    t = measure_equilibrium(_osc_frame(_WORKED), R=110.0, S=100.0, atr_val=1.0)
    assert t["n_full_traversals"] >= 2
    assert t["top_dead_space"] is not None and t["top_dead_space"] < 0.15
    assert t["bottom_dead_space"] is not None and t["bottom_dead_space"] < 0.15


def test_measure_equilibrium_flags_dead_space_hanging_from_a_rail(_osc_frame):
    # Price hangs in the top after one initial dip: only that single trip reaches
    # S, so rail-to-rail traversals collapse and the lower half reads as dead.
    t = measure_equilibrium(_osc_frame(_DEAD_SPACE), R=110.0, S=100.0, atr_val=1.0)
    assert t["n_full_traversals"] < 2
    assert t["bottom_dead_space"] > 0.30


def test_measure_equilibrium_absorbs_subthreshold_reversal(_flat_frame):
    # A 1.2-wide pullback inside an up-leg of an 11-wide box (min_amp = 0.15*11 =
    # 1.65) must be absorbed: the swing list stays V->P->V (3, via soft endpoints),
    # not split into 5 by the noise pivot, and the leg reads as 2 traversals.
    frame = _flat_frame([100, 110, 108.8, 111, 100])
    t = measure_equilibrium(frame, R=111.0, S=100.0, atr_val=1.0)
    assert t["n_swings"] == 3
    assert t["n_full_traversals"] == 2


def test_measure_equilibrium_guards_bad_inputs(_flat_frame, _osc_frame):
    frame = _osc_frame(_WORKED)
    # Non-positive / NaN ATR and a non-positive box collapse to the empty read.
    assert (measure_equilibrium(frame, 110.0, 100.0, 0.0)
            == measure_equilibrium(frame, 110.0, 100.0, -1.0))
    assert measure_equilibrium(frame, 100.0, 100.0, 1.0)["n_full_traversals"] == 0
    assert measure_equilibrium(frame, 110.0, 100.0, float("nan"))["n_swings"] == 0
    # Too few bars to form a pivot structure.
    assert measure_equilibrium(_flat_frame([1, 2]), 2.0, 1.0, 1.0)["n_swings"] == 0


def test_segment_swings_guards_bad_inputs(_ramp_frame):
    df = _ramp_frame([50, 53, 51.5, 56, 54, 60, 53, 56, 53.5, 56, 53.5])
    # Non-positive / NaN ATR must never divide a displacement.
    assert segment_swings(df, atr_val=0.0) == segment_swings(df, atr_val=-1.0)
    assert segment_swings(df, atr_val=0.0)["root_swing"] is None
    assert segment_swings(df, atr_val=float("nan"))["n_swings"] == 0
    # Too few bars to form a swing structure.
    tiny = pd.DataFrame({"High": [1, 2, 3], "Low": [1, 2, 3],
                         "Close": [1, 2, 3], "Open": [1, 2, 3]})
    assert segment_swings(tiny, atr_val=1.0)["n_swings"] == 0
