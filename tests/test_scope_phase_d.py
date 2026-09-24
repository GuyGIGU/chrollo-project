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

from engine_alpha.structure.context.scope import _resolve_phase_d_start, scope_consolidation


def test_support_test_evidence_reads_the_raw_staircase():
    # The raw staircase feeds Phase-D boundary evidence unfiltered — up-swing
    # footprints legitimately count toward rising-support runs. (The DRAWN
    # staircase this once contrasted against was retired 2026-08-09 — operator
    # ruling: one drawn LPS per setup — but the evidence read is unchanged.)
    from engine_alpha.structure.phases.phase_d import support_test_evidence_starts

    raw_tests = [
        {"start_index": 20, "end_index": 21, "low": 100.0, "descent_frac": 0.20, "zone_type": "INSIDE"},
        {"start_index": 23, "end_index": 24, "low": 101.0, "descent_frac": 0.20, "zone_type": "OVERSHOOT_R"},
    ]

    assert support_test_evidence_starts(raw_tests, box_start=0, base_len=20) == {
        "support_tests": 20,
        "sos_reclaim": 23,
        "rising_support": 20,
    }


def test_resolve_phase_d_start_matches_scope_rule():
    # Corrected model: the LPS is the GATE / fallback. A spring RECOVERY ends
    # Phase C and only FLOORS the search; Phase D opens at the EARLIEST credible
    # right-side evidence AFTER that floor.
    common = dict(box_start=60, base_len=60, last=119, is_inner_box=False,
                  has_lps_window=True, b=30)
    # No richer evidence -> LPS fallback.
    assert _resolve_phase_d_start(lps_start=115, **common) == 115
    # A spring recovery is NOT itself the Phase-D start: with nothing after it,
    # Phase D still falls back to the LPS (it does not anchor at the reclaim).
    assert _resolve_phase_d_start(lps_start=115, phase_c_recovery_bar=96, **common) == 115
    # Earliest right-side evidence wins regardless of type (v_tip @88 < inner @90
    # < support @92).
    assert _resolve_phase_d_start(lps_start=115, phase_d_start_bar=90,
                                  support_test_start_bar=92, v_tip_bar=88, **common) == 88
    assert _resolve_phase_d_start(lps_start=115, support_test_start_bar=92,
                                  v_tip_bar=88, **common) == 88
    assert _resolve_phase_d_start(lps_start=115, support_test_start_bar=92, **common) == 92
    # The spring reclaim floors it: evidence BEFORE the reclaim is ignored; the
    # earliest evidence AFTER it wins.
    assert _resolve_phase_d_start(lps_start=115, phase_c_recovery_bar=91,
                                  v_tip_bar=88, support_test_start_bar=95,
                                  **common) == 95
    assert _resolve_phase_d_start(lps_start=115, phase_c_recovery_bar=91,
                                  phase_d_start_bar=93, support_test_start_bar=95,
                                  **common) == 93
    # Shakeout case: the LPS pullback can predate the reclaim, but Phase D never
    # opens before it — the LPS fallback clamps UP to the recovery floor, so D
    # lands right at "the recovery after a mean shakeout".
    assert _resolve_phase_d_start(lps_start=90, phase_c_recovery_bar=96, **common) == 96
    # Active inner box implies its box start.
    assert _resolve_phase_d_start(box_start=60, base_len=60, last=119,
                                  is_inner_box=True, has_lps_window=True,
                                  lps_start=115, b=30) == 60
    # Clamp: never cross the body start b.
    assert _resolve_phase_d_start(lps_start=20, **common) == 30
    # No LPS window -> None.
    assert _resolve_phase_d_start(box_start=60, base_len=60, last=119,
                                  is_inner_box=False, has_lps_window=False,
                                  lps_start=0, b=30) is None


def test_resolve_phase_d_boundary_lps_fallback_respects_search_start_floor():
    from engine_alpha.structure.phases.phase_d import resolve_phase_d_boundary
    # The LPS fallback must not open Phase D before the declared search-start
    # floor (the floor includes search_start_bar, not only the spring reclaim).
    pb = resolve_phase_d_boundary(last=119, has_lps_window=True, lps_start=90,
                                  b=30, search_start_bar=100)
    assert pb.start_bar == 100 and pb.source == "lps"
    # ...but a later LPS still wins on its own bar.
    pb2 = resolve_phase_d_boundary(last=119, has_lps_window=True, lps_start=110,
                                   b=30, search_start_bar=100)
    assert pb2.start_bar == 110 and pb2.source == "lps"


def test_resolve_phase_d_boundary_earliest_evidence_after_floor_wins():
    from engine_alpha.structure.phases.phase_d import resolve_phase_d_boundary

    pb = resolve_phase_d_boundary(
        last=119,
        has_lps_window=True,
        lps_start=110,
        b=30,
        phase_c_recovery_bar=80,
        support_test_start_bar=78,
        sos_reclaim_start_bar=92,
        rising_support_start_bar=88,
        phase_d_start_bar=90,
        v_tip_bar=86,
    )

    assert pb.start_bar == 86
    assert pb.source == "v_tip"
    assert pb.evidence["floor"] == 80
    assert pb.evidence["selected"]["source"] == "v_tip"


def test_phase_d_boundary_evidence_carries_full_vocabulary():
    from engine_alpha.structure.phases.phase_d import PHASE_D_EVIDENCE_SOURCES, resolve_phase_d_boundary

    pb = resolve_phase_d_boundary(
        last=119,
        has_lps_window=True,
        lps_start=110,
        b=30,
        support_test_start_bar=88,
        sos_reclaim_start_bar=90,
        rising_support_start_bar=92,
        phase_d_start_bar=94,
        v_tip_bar=96,
    )

    signal_sources = {signal["source"] for signal in pb.evidence["signals"]}
    assert signal_sources == set(PHASE_D_EVIDENCE_SOURCES)
    assert pb.evidence["selected"]["source"] == "support_tests"


def test_support_test_evidence_starts_classifies_cluster_sos_and_rising_support():
    from engine_alpha.structure.phases.phase_d import support_test_evidence_starts

    starts = support_test_evidence_starts([
        {"start_index": 20, "end_index": 22, "low": 101.0, "zone_type": "INSIDE"},
        {"start_index": 25, "end_index": 27, "low": 102.0, "zone_type": "OVERSHOOT_R"},
        {"start_index": 29, "end_index": 31, "low": 103.0, "zone_type": "INSIDE"},
    ], box_start=0, base_len=40)

    assert starts == {
        "support_tests": 20,
        "sos_reclaim": 25,
        "rising_support": 20,
    }


def test_scope_outer_box_orders_a_b_d_bands(_scope_df):
    df = _scope_df(30)
    df.iloc[26, df.columns.get_loc("Low")] = 95.0  # min of the LPS window [25:29]
    df.iloc[26, df.columns.get_loc("High")] = 96.0
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # Outer box: A=climax, B=body start, D=right-most region (>= body start,
    # within the frame — its exact bar is anchored on the swing-high logic).
    assert out["phase_a_start_date"] == str(df.index[2])[:10]
    assert out["phase_b_start_date"] == str(df.index[5])[:10]
    assert out["phase_d_start_bar"] is not None
    assert 5 <= out["phase_d_start_bar"] <= 29
    assert out["phase_c_event_date"] is None
    assert out["has_mini_consolidation"] is False
    # All three regions placed → full confidence (D weighted 0.5).
    assert out["scope_confidence"] == 1.0
    # LPS zone = bounding box of the candidate bars [25:29): low = the dip at
    # bar 26 (95.0), high = the max High across those bars (101.0 default).
    assert out["lps_zone_low"] == 95.0
    assert out["lps_zone_high"] == 101.0
    # Tight in time too: the box spans the exact candidate bars.
    assert out["lps_zone_start_date"] == str(df.index[25])[:10]
    assert out["lps_zone_end_date"] == str(df.index[28])[:10]


def test_scope_rising_shelf_zone_draw_trims_to_down_sideways_suffix(_scope_df):
    # A rising-shelf LPS window [24:29): lows climb 90 -> 96 -> 100, then sit
    # sideways (99, 100). The election keeps such ascending-support pivots on
    # purpose, but the DRAWN gold box should show the reaction, not the climb.
    df = _scope_df(30)
    for bar, low in ((24, 90.0), (25, 96.0), (26, 100.0), (27, 99.0), (28, 100.0)):
        df.iloc[bar, df.columns.get_loc("Low")] = low
    common = dict(
        bc_anchor_bar=2, phase_b_start_bar=5, base_len=25, is_inner_box=False,
        lps_offset=1, lps_length=5, lps_zone_type="INSIDE", atr_val=1.0,
    )

    # Default (threshold off) — zone wraps the full window, climb included.
    full = scope_consolidation(df, **common)
    assert full["lps_zone_start_date"] == str(df.index[24])[:10]
    assert full["lps_zone_low"] == 90.0

    # Threshold on — the drawn start advances to the longest down/sideways suffix
    # (bar 26: [100, 99, 100] is non-rising), keeping >= 3 bars; the low/high
    # re-tighten to that suffix and the window END is unchanged.
    trimmed = scope_consolidation(df, lps_zone_draw_min_descent=0.40, **common)
    assert trimmed["lps_zone_start_date"] == str(df.index[26])[:10]
    assert trimmed["lps_zone_end_date"] == str(df.index[28])[:10]
    assert trimmed["lps_zone_low"] == 99.0
    assert trimmed["lps_zone_high"] == 101.0


def test_scope_zone_draw_keeps_min_three_bars(_scope_df):
    # A window whose ONLY down/sideways suffix is the last 2 bars ([100, 99]).
    # The drawn trim must NOT shave to a 2-bar stub — it keeps >= 3 bars, so here
    # it makes no trim at all rather than collapse to [100, 99] (operator: "one
    # or two more bars could still fill the LPS definition").
    df = _scope_df(30)
    for bar, low in ((25, 90.0), (26, 95.0), (27, 100.0), (28, 99.0)):
        df.iloc[bar, df.columns.get_loc("Low")] = low
    trimmed = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25, is_inner_box=False,
        lps_offset=1, lps_length=4, lps_zone_type="INSIDE", atr_val=1.0,
        lps_zone_draw_min_descent=0.40,
    )
    assert trimmed["lps_zone_start_date"] == str(df.index[25])[:10]  # no 2-bar stub
    assert trimmed["lps_zone_low"] == 90.0


def test_scope_clean_reaction_zone_draw_not_trimmed(_scope_df):
    # A clean reaction into support (lows fall 100 -> 95) already reads as a
    # down move, so the trim must be a no-op even with the threshold on.
    df = _scope_df(30)
    df.iloc[26, df.columns.get_loc("Low")] = 95.0
    df.iloc[27, df.columns.get_loc("Low")] = 95.0
    df.iloc[28, df.columns.get_loc("Low")] = 95.0
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25, is_inner_box=False,
        lps_offset=1, lps_length=4, lps_zone_type="INSIDE", atr_val=1.0,
        lps_zone_draw_min_descent=0.40,
    )
    assert out["lps_zone_start_date"] == str(df.index[25])[:10]


def test_scope_phase_a_can_end_before_phase_b_body(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_a_end_bar=6, phase_b_start_bar=12,
        base_len=18, is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )

    assert out["phase_a_start_date"] == str(df.index[2])[:10]
    assert out["phase_a_end_date"] == str(df.index[6])[:10]
    assert out["phase_a_end_bar"] == 6
    assert out["phase_b_start_date"] == str(df.index[12])[:10]


def test_scope_phase_d_anchors_at_lps(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # No spring -> Phase D anchors at the LPS: lps_start = 30 - 1 - 4 = 25.
    assert out["phase_d_start_bar"] == 25
    assert out["phase_d_start_date"] == str(df.index[25])[:10]


def test_scope_phase_d_can_use_support_test_cluster_hint(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0, support_test_start_bar=18,
    )
    assert out["has_mini_consolidation"] is False
    assert out["phase_d_start_bar"] == 18
    assert out["phase_d_start_date"] == str(df.index[18])[:10]


def test_scope_phase_d_can_use_v_tip_boundary(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
        support_test_start_bar=18, v_tip_bar=16,
    )
    assert out["has_mini_consolidation"] is False
    assert out["phase_d_start_bar"] == 16
    assert out["phase_d_start_date"] == str(df.index[16])[:10]


def test_scope_phase_c_recovery_floors_phase_d_search(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
        phase_c_recovery_bar=17, v_tip_bar=16, support_test_start_bar=20,
    )
    # Recovery (17) ends Phase C and FLOORS the search: the V-tip at 16 is before
    # the reclaim (ignored); the support test at 20 is after it and opens Phase D.
    assert out["has_mini_consolidation"] is False
    assert out["phase_d_start_bar"] == 20
    assert out["phase_d_start_date"] == str(df.index[20])[:10]


def test_scope_inner_after_recovery_opens_phase_d(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
        phase_d_start_bar=20, phase_c_recovery_bar=17,
    )
    # An inner mini-consolidation AFTER the reclaim is the right-side contraction
    # that opens Phase D (the LPS stays the gate underneath it).
    assert out["has_mini_consolidation"] is True
    assert out["phase_d_start_bar"] == 20
    assert out["phase_d_start_date"] == str(df.index[20])[:10]


def test_scope_inner_box_marks_mini_consolidation_and_d_start(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=10,
        is_inner_box=True, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # Active inner box: Phase D is the mini-consolidation itself -> box start.
    assert out["has_mini_consolidation"] is True
    assert out["phase_d_start_date"] == str(df.index[20])[:10]
    assert out["phase_d_start_bar"] == 20


def test_scope_parent_with_inner_phase_d_uses_explicit_start(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0, phase_d_start_bar=18,
    )
    assert out["has_mini_consolidation"] is True
    assert out["phase_d_start_bar"] == 18
    assert out["phase_d_start_date"] == str(df.index[18])[:10]
    assert out["phase_b_start_date"] == str(df.index[5])[:10]


def test_scope_spring_emits_phase_c_marker_at_lps_low(_scope_df):
    df = _scope_df(30)
    df.iloc[27, df.columns.get_loc("Low")] = 90.0  # the spring low inside [25:29]
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="UNDERCUT_S", atr_val=2.0,
    )
    assert out["phase_c_event_date"] == str(df.index[27])[:10]
    # Bounding box: low = the spring dip (90.0), high = max High over [25:29).
    assert out["lps_zone_low"] == 90.0
    assert out["lps_zone_high"] == 101.0


def test_scope_degenerate_order_drops_lead_in_keeps_phase_d(_scope_df):
    df = _scope_df(30)
    # Climax AFTER body start is degenerate → drop A/B rather than invert.
    out = scope_consolidation(
        df, bc_anchor_bar=10, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    assert out["phase_a_start_date"] is None
    assert out["phase_b_start_date"] is None
    assert out["phase_d_start_date"] is not None  # Phase D still placed
    assert out["scope_confidence"] == 0.5         # only D (weighted 0.5)


def test_scope_degrades_when_no_lps_window(_scope_df):
    df = _scope_df(30)
    # offset past the frame → no usable LPS window; outer box → no Phase D.
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=40, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    assert out["phase_d_start_date"] is None
    assert out["lps_zone_low"] is None
    assert out["phase_a_start_date"] == str(df.index[2])[:10]
    assert out["scope_confidence"] == 0.5  # A + B placed, D missing


def test_scope_empty_on_no_base(_scope_df):
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=0,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    assert out["phase_a_start_date"] is None
    assert out["phase_d_start_date"] is None
    assert out["scope_confidence"] == 0.0
