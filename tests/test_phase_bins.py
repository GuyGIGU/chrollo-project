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

from config import settings

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from engine_alpha.structure.phases.phase_features import measure_phases


def test_measure_phases_slices_named_regions_at_lps(_flat_ohlc):
    df = _flat_ohlc(120)
    # LPS = last 5 bars, low pinned at 100 (inside the 99..101 box).
    for i in range(115, 120):
        df.loc[i, "Low"] = 100.0
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )
    assert bins["bin_a_bars"] == 20          # 30 - 10
    assert bins["bin_b_bars"] == 60          # base_len
    assert bins["bin_lps_bars"] == 5
    assert bins["bin_d_bars"] == 5           # Phase D anchored at the LPS: 120 - 115
    assert bins["bin_d_boundary_source"] == "lps"
    evidence = json.loads(bins["phase_d_evidence_json"])
    assert evidence["selected"]["source"] == "lps"
    assert evidence["selected"]["meta"]["fallback"] is True
    assert abs(bins["lps_position_in_box"] - 0.5) < 1e-9   # (100-99)/(101-99)
    assert bins["bin_b_volume_ratio"] == 1.0               # uniform volume
    # LPS foot sits below the ceiling -> no Last-Supper stretch (< 0).
    assert bins["lps_stretch_box"] < 0
    assert bins["lps_stretch_atr"] == -1.0                 # (100-101)/1


def test_measure_phases_phase_a_can_end_at_root_reaction(_flat_ohlc):
    df = _flat_ohlc(120)
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, phase_a_end_bar=16,
        base_len=60, is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_a_bars"] == 6


def test_measure_phases_inner_box_sets_boundary_source_and_region(_flat_ohlc):
    df = _flat_ohlc(120)
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=True, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )
    assert bins["bin_d_boundary_source"] == "inner_box"
    assert bins["bin_d_bars"] == 60          # Phase D = the inner box (box_start..end)


def test_measure_phases_parent_with_inner_phase_d_keeps_parent_base(_flat_ohlc):
    df = _flat_ohlc(120)
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0, phase_d_start_bar=90,
    )
    assert bins["bin_b_bars"] == 60          # parent remains the base of record
    assert bins["bin_d_boundary_source"] == "inner_box"
    assert bins["bin_d_bars"] == 30          # Phase D spans the nested range


def test_measure_phases_evidence_json_records_selected_source(_flat_ohlc):
    df = _flat_ohlc(120)
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
        support_test_start_bar=88,
        sos_reclaim_start_bar=82,
        rising_support_start_bar=84,
        v_tip_bar=86,
    )
    evidence = json.loads(bins["phase_d_evidence_json"])

    assert bins["bin_d_boundary_source"] == "sos_reclaim"
    assert evidence["selected"]["source"] == "sos_reclaim"
    assert {s["source"] for s in evidence["signals"]} >= {"support_tests", "sos_reclaim", "rising_support", "v_tip", "lps"}


def test_measure_phases_v_tip_anchors_phase_d_before_support_cluster(_flat_ohlc):
    df = _flat_ohlc(120)
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
        support_test_start_bar=92, v_tip_bar=88,
    )
    assert bins["bin_d_boundary_source"] == "v_tip"
    assert bins["bin_d_bars"] == 32


def test_measure_phases_last_supper_positive_when_lps_above_ceiling(_flat_ohlc):
    df = _flat_ohlc(120)
    df.loc[113, "Low"] = 102.0
    df.loc[113, "Close"] = 102.5
    df.loc[113, "High"] = 103.0
    for i in range(115, 120):
        df.loc[i, "Low"] = 103.0
        df.loc[i, "Close"] = 103.5
        df.loc[i, "High"] = 104.0
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )
    # LPS formed 2 points above R=101 -> stretched (the Last-Supper risk axis).
    assert bins["lps_stretch_box"] > 0
    assert bins["lps_stretch_atr"] == 2.0     # (103-101)/1
    assert bins["lps_position_in_box"] > 1.0  # above the box ceiling
    assert bins["last_supper_pullback_from_extension_pct"] == 0.0096
    assert bins["last_supper_source_box_age"] == 2
    assert bins["last_supper_reclaim_quality"] == 0.75


def test_measure_phases_lps_stretch_can_use_active_inner_box(_flat_ohlc):
    df = _flat_ohlc(120, high=110.0, low=100.0, close=105.0)
    for i in range(115, 120):
        df.loc[i, "Low"] = 103.0
        df.loc[i, "Close"] = 103.5
        df.loc[i, "High"] = 104.0
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=110.0, S=100.0, atr_val=1.0, lps_R=104.0, lps_S=102.0,
    )
    assert bins["bin_b_bars"] == 60           # parent remains the base of record
    assert bins["lps_position_in_box"] == 0.5 # active inner box: (103-102)/(104-102)
    assert bins["lps_stretch_box"] == -0.5    # active inner R, not parent R
    assert bins["lps_stretch_atr"] == -1.0


def test_cog_interior_nan_closes_route_to_excluded():
    """A NaN close leaked raw into cog_end/cog_rng and its sign comparisons
    counted phantom mid-line crossings (2026-08-25 sweep). NaN routes to
    excluded; the emissions stay JSON-safe."""
    from engine_alpha.structure.phases.phase_features import _cog_interior

    closes = [101, 103, 105, 107, 109, 107, 105, 103] * 3
    seg = pd.DataFrame({"Close": [float(c) for c in closes]})
    clean = _cog_interior(seg, 110.0, 100.0)
    poisoned = seg.copy()
    poisoned.loc[4, "Close"] = np.nan
    out = _cog_interior(poisoned, 110.0, 100.0)
    for key, value in out.items():
        assert value is None or math.isfinite(value), key
    assert out["bin_b_cog_crossings"] <= clean["bin_b_cog_crossings"] + 1
    # all-NaN closes: the whole read refuses (all None), never fabricates
    all_nan = seg.copy()
    all_nan["Close"] = np.nan
    assert all(v is None for v in _cog_interior(all_nan, 110.0, 100.0).values())


def test_last_supper_reclaim_refuses_an_unreadable_final_close():
    """The old fallback pinned an unreadable final close to lps_low (a
    fabricated zero reclaim), and a NaN close sailed through the clamp into
    a fabricated FULL reclaim. Both now refuse: quality stays None while the
    pullback depth (which never read the close) still emits."""
    from engine_alpha.structure.phases.phase_features import _last_supper_measurements

    closes = [100.0, 104.0, 108.0, 112.0, 106.0, 103.0, 104.0, 105.0]
    df = pd.DataFrame({"High": [c + 1 for c in closes],
                       "Low": [c - 1 for c in closes],
                       "Close": closes})
    kwargs = dict(anchor_bar=3, low_bar=5, lps_end=8, box_start=0,
                  active_R=98.0)
    baseline = _last_supper_measurements(df, **kwargs)
    assert baseline["last_supper_reclaim_quality"] is not None
    poisoned = df.copy()
    poisoned.loc[7, "Close"] = np.nan
    out = _last_supper_measurements(poisoned, **kwargs)
    assert out["last_supper_reclaim_quality"] is None
    assert out["last_supper_pullback_from_extension_pct"] == \
        baseline["last_supper_pullback_from_extension_pct"]


def test_measure_phases_no_lps_window_degrades_gracefully(_flat_ohlc):
    df = _flat_ohlc(120)
    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=200, lps_length=5,   # window falls off the frame
        R=101.0, S=99.0, atr_val=1.0,
    )
    assert bins["bin_lps_bars"] is None
    assert bins["lps_stretch_atr"] is None
    assert bins["bin_d_bars"] is None         # heuristic Phase D keys off the LPS start
    assert bins["bin_b_bars"] == 60           # the base region is still measured


def test_measure_phases_phase_d_support_delta_blank_when_unmeasured(_ramp_frame):
    # The support-test boundary creates a Phase D slice that is too short to fit
    # swing lows. Its standalone quality is neutral, but the D-vs-B comparison
    # should stay blank instead of pretending "no measurement" is weaker support.
    lead = _ramp_frame([104, 108, 103, 107, 102, 106, 101, 105, 100, 104])
    lead["Volume"] = 1000.0
    d = _ramp_frame([104, 105])
    d["Volume"] = 1000.0
    df = pd.concat([lead, d], ignore_index=True)
    d_start = len(lead)

    bins = measure_phases(
        df, bc_anchor_bar=0, phase_b_start_bar=1, base_len=len(df),
        is_inner_box=False, lps_offset=0, lps_length=2,
        R=108.0, S=100.0, atr_val=1.0, support_test_start_bar=d_start,
    )

    assert bins["bin_d_support_slope_atr"] is None
    assert bins["bin_d_ascending_support_quality"] == 0.0
    assert bins["bin_d_boundary_source"] == "support_tests"
    assert bins["bin_d_vs_b_support_quality_delta"] is None


def test_measure_phases_phase_c_spring_requires_recovery(_flat_ohlc):
    df = _flat_ohlc(120, low=100.0, close=100.2)
    # A clean-V spring: a visible undercut of S (0.8 ATR) that reclaims S by
    # Close on the next bar and holds.
    df.loc[95, "Low"] = 98.2
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Low"] = 99.1
    df.loc[96, "Close"] = 99.2

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is True
    assert bins["bin_c_type"] == "SPRING"
    assert bins["bin_c_undercut_atr"] == 0.8
    assert bins["bin_c_recovery_bars"] == 1
    assert bins["bin_c_event_bar"] == 95
    assert bins["bin_c_recovery_bar"] == 96
    # The spring reclaim (96) FLOORS Phase D but does not anchor it; with no
    # richer right-side evidence after it, D opens at the LPS (the gate).
    assert bins["bin_d_start_bar"] == 115
    assert bins["bin_d_boundary_source"] == "lps"
    assert bins["bin_c_time_loc"] == pytest.approx((95 - 60) / 59, abs=0.0001)


def test_measure_phases_phase_c_spring_floors_out_earlier_v_tip(_flat_ohlc):
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.2
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Close"] = 99.2

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0, v_tip_bar=88,
    )

    assert bins["bin_c_type"] == "SPRING"
    # The V-tip at 88 sits BEFORE the spring reclaim (96), so it is floored out
    # (it belonged to Phase C); Phase D falls back to the LPS.
    assert bins["bin_d_start_bar"] == 115
    assert bins["bin_d_boundary_source"] == "lps"


def test_measure_phases_inner_after_spring_recovery_opens_phase_d(_flat_ohlc):
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.2
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Close"] = 99.2

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0, phase_d_start_bar=100,
    )

    assert bins["bin_c_type"] == "SPRING"
    # An inner mini-consolidation at 100 is AFTER the reclaim (96): it is the
    # earliest credible right-side evidence and opens Phase D, ahead of the LPS.
    assert bins["bin_d_start_bar"] == 100
    assert bins["bin_d_boundary_source"] == "inner_box"


def test_measure_phases_phase_c_rejects_shallow_undercut(_flat_ohlc):
    # A barely-below-support poke (0.2 ATR) is a "test at support", not a spring
    # — the undercut floor rejects it even though it reclaims by Close.
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.8
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Close"] = 99.2

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None
    assert bins["bin_c_event_bar"] is None
    assert bins["bin_c_recovery_bar"] is None


def test_measure_phases_phase_c_accepts_linger_spring(_flat_ohlc):
    # A choppy multi-bar sojourn below S (not a clean V) that reclaims and holds
    # is a valid spring — the "linger below support then recover" variation.
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, ["Low", "Close"]] = [98.5, 98.7]
    df.loc[96, ["Low", "Close"]] = [98.2, 98.6]   # trough
    df.loc[97, ["Low", "Close"]] = [98.3, 98.4]
    df.loc[98, ["Low", "Close"]] = [98.4, 98.8]
    df.loc[99, ["Low", "Close"]] = [98.9, 99.3]   # reclaim; bars 100+ hold above S

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is True
    assert bins["bin_c_type"] == "SPRING"
    assert bins["bin_c_event_bar"] == 96      # the trough, not the first penetration
    assert bins["bin_c_recovery_bar"] == 99
    assert bins["bin_c_recovery_bars"] == 3
    assert bins["bin_c_undercut_atr"] == 0.8


def test_measure_phases_phase_c_rejects_never_reclaimed(_flat_ohlc):
    # A sojourn below S that never closes back above it is a breakdown, not a spring.
    df = _flat_ohlc(120, low=100.0, close=100.2)
    for idx in range(95, 120):
        df.loc[idx, ["Low", "Close"]] = [98.0, 98.3]

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_phases_phase_c_rejects_poke_and_fail(_flat_ohlc):
    # Penetrate + reclaim for ONE bar, then break back below S and stay there:
    # the hold check rejects it (a real spring's reclaim sticks = supply absorbed).
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, ["Low", "Close"]] = [98.5, 98.7]   # penetrate
    df.loc[96, ["Low", "Close"]] = [98.9, 99.3]   # one-bar reclaim
    for idx in range(97, 120):
        df.loc[idx, ["Low", "Close"]] = [98.0, 98.3]  # fails back below S, sustained

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_phases_phase_c_does_not_label_held_test_from_above(_flat_ohlc):
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[110, "Low"] = 99.2
    df.loc[110, "Close"] = 99.4

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_phases_phase_c_held_test_stays_near_support(_flat_ohlc):
    df = _flat_ohlc(120, high=104.0, low=102.0, close=102.2)

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=104.0, S=100.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_phases_phase_c_rejects_too_deep_undercut(_flat_ohlc):
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 97.4
    df.loc[95, "Close"] = 99.2

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_phases_phase_c_requires_atr_frame(_flat_ohlc):
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.8
    df.loc[95, "Close"] = 99.2

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=None,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


# ── Pivot-anchored over-extension (the run-up's terminal pivot) ──────────────
# The elected LPS window's own first bar is at most `lps_length` bars old, so it
# under-reports the give-back whenever the run-up peaked before the window
# opened. These pin the pivot anchor's reach and its refusals.

def test_run_up_pivot_anchor_reaches_past_the_lps_window(_flat_ohlc):
    """A run-up peaking well before the LPS window is found by the pivot anchor
    and reported deeper than the window-edge anchor."""
    df = _flat_ohlc(120, low=100.0, close=100.2)
    # Run-up pivot at bar 108, ~12 bars before the LPS low at 119.
    df.loc[108, "High"] = 112.0
    df.loc[108, "Close"] = 111.0
    for b in range(109, 120):
        df.loc[b, "High"] = 104.0 - (b - 109) * 0.2
    df.loc[119, "Low"] = 100.0

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=3,
        R=101.0, S=99.0, atr_val=1.0,
        lps_anchor_bar=117, lps_low_bar=119,
    )

    back = bins["last_supper_pivot_bars_back"]
    assert back is not None and back > 3, "anchor must reach past the LPS window"
    old = bins["last_supper_pullback_from_extension_pct"]
    new = bins["last_supper_pullback_from_pivot_pct"]
    assert new > old, "the pivot anchor must see the deeper give-back"
    # Stretch is measured against the box ceiling R, in ATR and box-heights.
    assert bins["last_supper_pivot_stretch_atr"] == pytest.approx(11.0, abs=0.5)
    assert bins["last_supper_pivot_stretch_box"] == pytest.approx(5.5, abs=0.5)


def test_run_up_pivot_anchor_refuses_a_nan_window(_flat_ohlc):
    """A NaN inside the search window distorts the pivot masks, so the anchor
    refuses rather than reporting a moved pivot."""
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[110, "High"] = np.nan

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=3,
        R=101.0, S=99.0, atr_val=1.0,
        lps_anchor_bar=117, lps_low_bar=119,
    )

    assert bins["last_supper_pivot_bars_back"] is None
    assert bins["last_supper_pullback_from_pivot_pct"] is None
    assert bins["last_supper_pivot_stretch_atr"] is None


def test_run_up_pivot_stretch_is_negative_when_the_lps_never_left_the_box(_flat_ohlc):
    """No over-extension: a run-up pivot below R reports a negative stretch
    rather than None, so 'measured and flat' stays distinguishable from 'unmeasured'."""
    # Whole frame sits under R = 101, so the only peak is a sub-R one.
    df = _flat_ohlc(120, high=100.0, low=99.0, close=100.0)
    df.loc[108, "High"] = 100.8          # a real pivot, still under R

    bins = measure_phases(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=3,
        R=101.0, S=99.0, atr_val=1.0,
        lps_anchor_bar=117, lps_low_bar=119,
    )

    stretch = bins["last_supper_pivot_stretch_atr"]
    assert stretch is not None and stretch < 0
