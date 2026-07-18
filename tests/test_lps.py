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

from engine_alpha.structure.metrics import (
    _vol_trend_from_contractions,
    measure_bar_compression,
    measure_contractions,
    measure_dwell_balance,
    measure_equilibrium,
)
from engine_alpha.structure.box_gates import _validate_base_quality
from engine_alpha.structure.box_primitives import select_phase_b_candidate
from engine_alpha.structure.inner_box import (
    _detect_inner_phase_b_start,
    detect_inner_root_swing,
)
from engine_alpha.structure.lps import (
    detect_lps,
    detect_lps_candidates,
    detect_lps_tests,
    select_active_lps_candidate,
)
import engine_alpha.structure.lps as lps_module


_VCP_LEVELS = [
    10, 12, 14, 16, 30, 22, 18, 14, 6, 12, 16, 20,
    26, 18, 14, 9, 13, 17, 22, 16, 13, 11, 12, 13,
]


def test_vol_trend_from_contractions_scores_drying_up():
    # Lighter each contraction, quietest at the final coil -> full credit.
    assert _vol_trend_from_contractions([1000, 800, 500]) == 1.0
    # Heaviest at the final contraction -> zero.
    assert _vol_trend_from_contractions([500, 800, 1000]) == 0.0
    # A trend needs two points; non-finite values are dropped before scoring.
    assert _vol_trend_from_contractions([1000]) is None
    assert _vol_trend_from_contractions([]) is None
    assert _vol_trend_from_contractions([float("nan"), 900, 700, 500]) == 1.0
    # Flat volume -> every step non-rising (1.0), final-lightest neutral (0.5).
    assert _vol_trend_from_contractions([800, 800, 800]) == 0.75


def test_measure_contractions_volume_does_not_touch_quality(_contraction_frame):
    n = len(_VCP_LEVELS)
    drying = _contraction_frame(_VCP_LEVELS, [2000 - 60 * i for i in range(n)])
    rising = _contraction_frame(_VCP_LEVELS, [620 + 60 * i for i in range(n)])

    rd = measure_contractions(drying, order=2)
    rr = measure_contractions(rising, order=2)

    # Identical price -> identical contractions and IDENTICAL quality: volume is
    # measured but never folded into the score (the measure-first invariant).
    assert rd["n_contractions"] >= 2
    assert rd["quality"] == rr["quality"]
    # ...but the volume read separates them: drying up ranks far above rising in.
    assert rd["vol_trend"] is not None and rr["vol_trend"] is not None
    assert rd["vol_trend"] > rr["vol_trend"]


def test_measure_contractions_vol_trend_none_without_contractions(_contraction_frame):
    flat = _contraction_frame([10, 10, 10, 10, 10], [500, 500, 500, 500, 500])
    assert measure_contractions(flat, order=2)["vol_trend"] is None


def test_detect_inner_phase_b_start_finds_recent_climax(_contraction_frame):
    # 12 bars rising to a clear peak (118), a ~17% drop over 5 bars to the inner
    # AR (~98), then 21 tight bars — a textbook inner climax → reaction → inner range.
    levels = (
        [90, 93, 96, 99, 102, 105, 108, 111, 114, 116, 117, 118]
        + [112, 108, 104, 100, 98]
        + [100, 99, 101, 100, 102, 99, 100, 101, 99, 100, 102,
           100, 99, 101, 100, 99, 100, 101, 99, 100, 101]
    )
    frame = _contraction_frame(levels, [1000] * len(levels))
    off = _detect_inner_phase_b_start(frame)
    assert off is not None
    # Lands after the peak, leaves >= INNER_MIN_DAYS room, and is a real reaction.
    assert 11 < off <= len(frame) - 15
    assert frame['Low'].iloc[off] <= 0.95 * frame['High'].iloc[:off].max()


def test_detect_inner_root_swing_reports_reaction_measurements(_contraction_frame):
    levels = (
        [90, 93, 96, 99, 102, 105, 108, 111, 114, 116, 117, 118]
        + [112, 108, 104, 100, 98]
        + [100, 99, 101, 100, 102, 99, 100, 101, 99, 100, 102,
           100, 99, 101, 100, 99, 100, 101, 99, 100, 101]
    )
    frame = _contraction_frame(levels, [1000] * len(levels))

    root = detect_inner_root_swing(frame)

    assert root is not None
    assert root["bc_bar"] < root["ar_bar"]
    assert root["ar_bar"] == _detect_inner_phase_b_start(frame)
    assert root["reaction_bars"] == root["ar_bar"] - root["bc_bar"]
    assert root["reaction_pct"] >= settings.AR_MIN_DROP_PCT


def test_detect_inner_phase_b_start_none_when_no_reaction(_contraction_frame):
    # 40 near-flat bars (~3% wiggle) — no >= 5% reaction, so no inner climax.
    levels = [100 + (1.5 if i % 2 else -1.5) for i in range(40)]
    assert _detect_inner_phase_b_start(_contraction_frame(levels, [1000] * 40)) is None


def test_detect_inner_phase_b_start_none_when_too_short(_contraction_frame):
    levels = [100, 102, 98, 101, 99, 100, 103, 97, 100, 101]
    assert _detect_inner_phase_b_start(_contraction_frame(levels, [1000] * 10)) is None


def test_lps_trigger_uses_last_lps_bar_high():
    df = pd.DataFrame([
        {"High": 118, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 117, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 110, "Low": 106, "Close": 107, "Spread": 2, "Volume": 500, "Vol_50": 1000},
        {"High": 107, "Low": 103, "Close": 106, "Spread": 1, "Volume": 500, "Vol_50": 1000},
    ])

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=2,
    )

    assert result["trigger_price"] == 107


def test_lps_candidate_detector_and_selector_match_wrapper():
    df = pd.DataFrame([
        {"High": 118, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 117, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 110, "Low": 106, "Close": 107, "Spread": 2, "Volume": 500, "Vol_50": 1000},
        {"High": 107, "Low": 103, "Close": 106, "Spread": 1, "Volume": 500, "Vol_50": 1000},
    ])
    kwargs = dict(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=2,
    )

    wrapper, wrapper_rejects = detect_lps(diagnose=True, **kwargs)
    candidates, candidate_rejects = detect_lps_candidates(diagnose=True, **kwargs)
    elected = select_active_lps_candidate(candidates, df.iloc[-1])

    assert elected is not None
    assert wrapper_rejects == candidate_rejects
    for key in ("start_index", "end_index", "low_index", "trigger_price", "zone_type"):
        assert wrapper[key] == elected[key]
    assert "_quality" in elected
    assert "_quality" not in wrapper


def test_lps_accepts_compact_reaction_behavior(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 4)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 4)
    df = _lps_behavior_frame(
        highs=[108, 107, 106, 105],
        lows=[106, 104, 102, 101],
        closes=[107, 105, 103, 104],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["window_range_pct_box"] == 0.7
    assert result["high_descent_frac"] == 1.0


def test_lps_accepts_shallow_pullback_on_tight_clean_coil(monkeypatch, _lps_behavior_frame):
    # A tight, clean-descent coil (lows AND highs strictly descending) whose
    # first-high -> last-low pullback is only 0.5 profile units. The old 0.65
    # floor rejected these tight VCP pivots purely on pullback magnitude (the
    # BP / NVMI seed misses, both descent_frac 1.0); the shipped 0.40 floor
    # accepts them while the descent / vol / spread / zone gates still apply.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 4)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 4)
    df = _lps_behavior_frame(
        highs=[108, 107, 106, 105],
        lows=[107, 106, 105, 104],
        closes=[107, 106, 105, 104],
    )
    kw = dict(
        latest=df.iloc[-1], sup_avg=100, res_avg=110, atr_val=2,
        base_range_threshold=8, base_len=20, swing_complete_idx=-1,
    )

    # Accepted at the shipped 0.40 floor, with a genuinely shallow (<0.65) pullback.
    monkeypatch.setattr(settings, "LPS_PULLBACK_PROFILE_MIN", 0.40)
    accepted = detect_lps(df=df, **kw)
    assert accepted is not None
    assert 0.40 <= accepted["pullback_profile"] < 0.65
    assert accepted["descent_frac"] == 1.0  # the coil is a clean descent, not chop
    assert accepted["swing_type"] == "clean_downswing"

    # The retired 0.65 floor rejected exactly this coil on pullback magnitude alone.
    monkeypatch.setattr(settings, "LPS_PULLBACK_PROFILE_MIN", 0.65)
    rejected, rejects = detect_lps(df=df, diagnose=True, **kw)
    assert rejected is None
    assert any(str(k).startswith("pullback_profile") for k in rejects)


def test_lps_rejects_window_that_spans_most_of_box(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[110, 114, 113, 112, 106],
        lows=[105, 104, 103, 102, 101],
        closes=[106, 105, 104, 103, 102],
    )

    result, rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=10,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert result is None
    assert rejects["window_box_range"] == 1


def test_lps_accepts_clean_downswing_even_when_window_spans_box(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[112, 110, 107],
        lows=[108, 105, 102],
        closes=[109, 106, 103],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["window_range_pct_box"] > settings.LPS_MAX_WINDOW_BOX_RANGE
    assert result["descent_frac"] == 1.0
    assert result["high_descent_frac"] == 1.0
    assert result["swing_type"] == "clean_downswing"
    assert result["lps_anchor_bar"] == 0
    assert result["lps_low_bar"] == 2
    assert result["lps_swing_depth_box"] == pytest.approx((112 - 102) / (110 - 100))


def test_lps_rising_edge_is_graded_not_hard_rejected(monkeypatch, _lps_behavior_frame):
    # Reframed 2026-06-19: a rising upper edge is NOT a hard reject. A rising
    # coil ties into ASCENDING SUPPORT (gradual rising buyer pressure), which the
    # engine already rewards via SCORE_ASCENDING_SUPPORT — so the old high_up_march
    # reject double-counted it as a defect. The descent floors are retired to 0;
    # descent_frac / high_descent_frac stay GRADED quality inputs (clean descents
    # still outrank), but no longer gate. This frame (lows cleanly testing the
    # terminal support low, rising upper edge) now elects an LPS.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[104, 105, 106, 107, 108],
        lows=[104, 103, 102, 101, 100],
        closes=[104, 103, 102, 101, 101],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=10,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    # The rising upper edge is recorded as a graded signal (low high_descent_frac),
    # not a rejection; the lows still register a clean descent into support.
    assert result["high_descent_frac"] == 0.0
    assert result["descent_frac"] == 1.0


def test_lps_spread_widening_discounts_quality_not_gate(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[110.0, 109.0, 108.0, 107.0, 106.0],
        lows=[108.8, 107.6, 106.3, 105.6, 104.2],
        closes=[109.0, 108.0, 107.0, 106.0, 105.0],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=2.0,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["spread_decline_quality"] < 1.0


def test_lps_scans_last_seven_active_bars(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[116, 115, 110, 108, 109, 110, 111, 112, 113, 114],
        lows=[114, 113, 105, 102, 103, 104, 105, 106, 107, 108],
        closes=[115, 114, 106, 103, 104, 105, 106, 107, 108, 107],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=115,
        atr_val=2,
        base_range_threshold=8,
        base_len=30,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["offset"] == 6
    assert result["start_index"] == 2


def test_lps_rejects_stale_candidate_when_later_lower_low(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[110, 108, 107, 106, 107, 108],
        lows=[105, 102, 101, 100, 101, 102],
        closes=[106, 103, 102, 101, 102, 103],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=99,
        res_avg=112,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_index"] == 2
    assert result["end_index"] == 4


def test_lps_prefers_full_pullback_into_latest_low(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 7)
    df = _lps_behavior_frame(
        highs=[72.89, 72.83, 72.76, 72.29, 72.28, 72.98],
        lows=[71.68, 71.39, 71.04, 70.83, 70.51, 71.41],
        closes=[72.08, 71.41, 71.40, 71.68, 70.91, 72.20],
    )
    df.index = pd.to_datetime([
        "2026-06-02", "2026-06-03", "2026-06-04",
        "2026-06-05", "2026-06-08", "2026-06-09",
    ])
    df["Volume"] = [117000, 105800, 77700, 152700, 76500, 126200]
    df["Vol_50"] = [151010, 148000, 146088, 146834, 144268, 146428]

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=65.05789189179512,
        res_avg=74.15060505040422,
        atr_val=2.182,
        base_range_threshold=2.62,
        base_len=73,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_date"] == "2026-06-02"
    assert result["end_date"] == "2026-06-08"
    assert result["low_index"] == 4


def test_lps_profile_uses_first_high_not_window_high(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[106, 112, 105],
        lows=[104, 108, 101],
        closes=[105, 109, 104],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=120,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["first_high"] == 106
    assert result["window_high"] == 112
    assert result["pullback_profile"] == pytest.approx((106 - 101) / 4)


def test_lps_terminal_low_guard_rejects_earlier_lower_low(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[108, 107, 106],
        lows=[105, 100, 102],
        closes=[106, 101, 105],
    )

    result, rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=99,
        res_avg=112,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert result is None
    assert rejects["terminal_low"] == 1


def test_lps_accepts_compact_rising_support_shelf(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[106.0, 105.0, 105.2, 105.4, 105.6],
        lows=[104.0, 101.0, 102.0, 102.5, 103.0],
        closes=[105.0, 102.0, 103.0, 103.5, 104.5],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["low_index"] == 1
    assert result["low"] == 101.0
    assert result["last_low"] == 103.0
    assert result["swing_type"] == "rising_support_shelf"


def test_lps_swing_dates_follow_anchor_and_elected_valley(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[106.0, 105.0, 105.2, 105.4, 105.6],
        lows=[104.0, 101.0, 102.0, 102.5, 103.0],
        closes=[105.0, 102.0, 103.0, 103.5, 104.5],
    )
    df.index = pd.date_range("2026-01-05", periods=len(df), freq="B")

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["lps_anchor_date"] == "2026-01-05"
    assert result["lps_low_date"] == "2026-01-06"
    assert result["lps_swing_depth_pct"] == pytest.approx((106 - 101) / 106)
    assert result["lps_swing_depth_atr"] == pytest.approx((106 - 101) / 2)


def test_lps_accepts_shallow_buec_shelf_above_resistance(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[113.0, 112.2, 111.8, 111.6, 111.3],
        lows=[110.7, 110.4, 110.5, 110.6, 110.5],
        closes=[111.2, 110.8, 110.9, 111.0, 110.8],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["zone_type"] == "OVERSHOOT_R"
    assert result["swing_type"] == "buec_shelf"
    assert settings.LPS_PULLBACK_PROFILE_MIN <= result["pullback_profile"] < settings.LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R


# ── OVERSHOOT_R window rescope (dark, LPS_OVERSHOOT_WINDOW_ATR_ENABLED —
# solve-the-engine task 10). Geometry transcribed from CTOS: his marked shelf
# spans 1.06 box-heights but only 1.42 ATR — above a NARROW box, box height is
# the wrong localization yardstick. Same proven shelf as the test above, box
# shrunk so the window gate becomes the sole discriminator. ─────────────────

def _narrow_box_buec_frame(_lps_behavior_frame):
    # Final close 110.65 keeps the shelf's box-position extension within the
    # BUEC exception's 0.35 cap on the 2.0-point box (0.325), mirroring
    # CTOS's shelf resting ON the rail rather than lifted away from it.
    return _lps_behavior_frame(
        highs=[113.0, 112.2, 111.8, 111.6, 111.3],
        lows=[110.7, 110.4, 110.5, 110.6, 110.5],
        closes=[111.2, 110.8, 110.9, 111.0, 110.65],
    )


def _detect_on_narrow_box(df, sup_avg, res_avg, base_len=20):
    return detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=sup_avg,
        res_avg=res_avg,
        atr_val=2,
        base_range_threshold=4,
        base_len=base_len,
        swing_complete_idx=-1,
    )


def test_overshoot_window_rescope_is_inert_flag_off(monkeypatch, _lps_behavior_frame):
    # Flag-off (the pre-2026-07-16 default, preserved as the OFF contract): the
    # 2.6-point shelf over a 2.0-point box measures 1.3 box-heights and the
    # window gate rejects it exactly as the frozen engine always has. This
    # value is independently reasoned and MUST NOT be changed — if it fails,
    # fix the implementation.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    monkeypatch.setattr(settings, "LPS_OVERSHOOT_WINDOW_ATR_ENABLED", False)
    df = _narrow_box_buec_frame(_lps_behavior_frame)
    assert _detect_on_narrow_box(df, sup_avg=108, res_avg=110) is None


def test_overshoot_window_rescope_admits_the_ctos_class_flag_on(monkeypatch, _lps_behavior_frame):
    # Flag-on, MATURED cause (real CTOS: 50-bar base, 10 traversals): the
    # OVERSHOOT_R denominator becomes max(box_height, 2*ATR) = 4.0, so the
    # 2.6-point shelf measures 0.65 <= 0.85 and completes as the BUEC shelf
    # it visually is.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    monkeypatch.setattr(settings, "LPS_OVERSHOOT_WINDOW_ATR_ENABLED", True)
    df = _narrow_box_buec_frame(_lps_behavior_frame)
    result = _detect_on_narrow_box(df, sup_avg=108, res_avg=110, base_len=50)
    assert result is not None
    assert result["zone_type"] == "OVERSHOOT_R"
    assert result["swing_type"] == "buec_shelf"


def test_overshoot_rescope_refuses_immature_cause(monkeypatch, _lps_behavior_frame):
    # The BBVA pin (operator-ruled "just incomplete" 2026-07-17): a throwback
    # above R claims the cause below is complete, so the rescoped ATR
    # denominator only engages on a matured cause (>= 2x MIN_BASE_DAYS, the
    # same floor a terminal shakeout needs in rail_qualification). The IDENTICAL
    # shelf geometry on a bare-minimum 20-bar base falls back to the raw
    # window gate — the pre-flip path — and refuses.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    monkeypatch.setattr(settings, "LPS_OVERSHOOT_WINDOW_ATR_ENABLED", True)
    df = _narrow_box_buec_frame(_lps_behavior_frame)
    assert _detect_on_narrow_box(df, sup_avg=108, res_avg=110, base_len=20) is None


def test_overshoot_window_rescope_never_touches_inside_windows(monkeypatch, _lps_behavior_frame):
    # Provably invisible outside its scope: the SAME oversized window sitting
    # INSIDE the box still rejects with the flag on — the rescope reads the
    # zone, not the flag alone.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    monkeypatch.setattr(settings, "LPS_OVERSHOOT_WINDOW_ATR_ENABLED", True)
    df = _narrow_box_buec_frame(_lps_behavior_frame)
    assert _detect_on_narrow_box(df, sup_avg=110, res_avg=111.5) is None


# ── The holding-shelf completion form (Event Map Task 8, flag-gated dark) ────

_SHELF_KW = dict(sup_avg=100, res_avg=110, atr_val=2, base_range_threshold=4,
                 base_len=20, swing_complete_idx=-1)


def _hot_high_shelf(_lps_behavior_frame):
    """PBT-analog: a monotone, upper-half INSIDE shelf whose only pullback-form
    failure is the volume dry-up (avg 1400 vs Vol_50 1000)."""
    df = _lps_behavior_frame(
        highs=[108.5, 107.8, 107.5],
        lows=[106.5, 106.2, 106.0],
        closes=[107.5, 107.0, 106.8],
    )
    df["Volume"] = 1400
    return df


def test_holding_shelf_flag_off_is_inert_and_never_consulted(monkeypatch, _lps_behavior_frame):
    # EC-8 unit inert test: flag-off must never even CALL the shelf judgment.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", False)
    monkeypatch.setattr(lps_module, "_holding_shelf_verdict",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError(
                            "flag-off consulted the shelf form")))
    df = _hot_high_shelf(_lps_behavior_frame)

    result, rejects = detect_lps(df=df, latest=df.iloc[-1], diagnose=True, **_SHELF_KW)

    assert result is None
    assert rejects["vol_contraction"] >= 1  # the pullback form's own reject stands
    assert "holding_shelf_refused" not in rejects  # flag-off counters unchanged


def test_holding_shelf_accepts_hot_volume_high_shelf_flag_on(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    df = _hot_high_shelf(_lps_behavior_frame)

    result = detect_lps(df=df, latest=df.iloc[-1], **_SHELF_KW)

    assert result is not None
    assert result["swing_type"] == "holding_shelf"
    assert result["zone_type"] == "INSIDE"
    assert result["descent_frac"] == 1.0            # monotone non-rising lows
    assert result["vol_contraction"] < 0            # measured truthfully, not gated
    assert result["trigger_price"] == 107.5


def test_holding_shelf_rejects_low_in_box_flag_on(monkeypatch, _lps_behavior_frame):
    # The canon failure geometry: flat + LOW + hot volume. The position gate
    # (shelf low at/above the box midpoint) keeps it dead.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    df = _lps_behavior_frame(
        highs=[103.5, 102.8, 102.5],
        lows=[101.5, 101.2, 101.0],
        closes=[102.5, 102.0, 101.8],
    )
    df["Volume"] = 1400

    result, rejects = detect_lps(df=df, latest=df.iloc[-1], diagnose=True, **_SHELF_KW)

    assert result is None
    assert rejects["vol_contraction"] >= 1
    # Form-tagged counters (Task 10): flag-on, the shelf was consulted and
    # ALSO refused this window — both forms' refusals are visible.
    assert rejects["holding_shelf_refused"] >= 1


def test_holding_shelf_rejects_rising_lows_wedge_flag_on(monkeypatch, _lps_behavior_frame):
    # A wedge whose last low still rests inside the terminal tolerance but whose
    # middle low rose: monotone-non-rising lows (the wedging guard) reject it.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    df = _lps_behavior_frame(
        highs=[108.5, 107.8, 107.5],
        lows=[106.0, 106.45, 106.3],
        closes=[107.5, 107.0, 106.8],
    )
    df["Volume"] = 1400

    result = detect_lps(df=df, latest=df.iloc[-1], **_SHELF_KW)

    assert result is None


def test_holding_shelf_converts_short_overshoot_shelf_above_creek(monkeypatch, _lps_behavior_frame):
    # WTS-analog: a 3-bar back-up shelf perched just above broken R (inside the
    # zone ceiling). Too short for the buec exception (length >= 5) and too
    # shallow for the OVERSHOOT_R depth floor — the shelf form owns it.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[113.4, 112.5, 112.2],
        lows=[110.9, 110.7, 110.5],
        closes=[112.5, 112.0, 111.8],
    )

    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", False)
    off, off_rejects = detect_lps(df=df, latest=df.iloc[-1], diagnose=True, **_SHELF_KW)
    assert off is None
    assert any(str(k).startswith("pullback_profile") for k in off_rejects)

    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    on = detect_lps(df=df, latest=df.iloc[-1], **_SHELF_KW)
    assert on is not None
    assert on["swing_type"] == "holding_shelf"
    assert on["zone_type"] == "OVERSHOOT_R"
    assert on["pullback_profile"] < settings.LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R


def test_holding_shelf_never_steals_a_passing_pullback_window(monkeypatch, _lps_behavior_frame):
    # A window the pullback form fully accepts also satisfies the shelf shape;
    # flag-on it must stay pullback-attributed and byte-identical to flag-off.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[108.5, 107.8, 107.5],
        lows=[106.5, 106.2, 106.0],
        closes=[107.5, 107.0, 106.8],
    )  # dry fixture volume: 500 vs Vol_50 1000

    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", False)
    off = detect_lps(df=df, latest=df.iloc[-1], **_SHELF_KW)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    on = detect_lps(df=df, latest=df.iloc[-1], **_SHELF_KW)

    assert off is not None
    assert on == off
    assert on["swing_type"] != "holding_shelf"


def test_holding_shelf_both_forms_qualify_frame_pins_precedence(monkeypatch, _lps_behavior_frame):
    # Detection-level precedence pin (Task 9): ONE frame where the scan yields
    # BOTH forms with the same terminal low and end — a len-3 pullback window
    # (dry tail volume) and a len-4 shelf-saved window (the extra bar drags in
    # a volume spike). The pullback must win the election, and the flag-on
    # result must equal the flag-off result exactly.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 4)
    df = _lps_behavior_frame(
        highs=[111.0, 108.5, 107.8, 107.5],
        lows=[107.0, 106.5, 106.2, 106.0],
        closes=[108.0, 107.5, 107.0, 106.8],
    )
    df.loc[0, "Volume"] = 5000  # len-4 window mean vol 1625 >= 850 -> shelf-saved
    kw = dict(latest=df.iloc[-1], sup_avg=100, res_avg=110, atr_val=2,
              base_range_threshold=4, base_len=20, swing_complete_idx=-1)

    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    candidates, _ = detect_lps_candidates(df=df, **kw)
    # The electable group: windows ending at the last bar (offset 0).
    at_end = {c["length"]: c["swing_type"] for c in candidates
              if c["end_index"] == len(df)}
    assert at_end.get(4) == "holding_shelf"         # both forms really present
    assert at_end.get(3) is not None and at_end[3] != "holding_shelf"

    on = detect_lps(df=df, **kw)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", False)
    off = detect_lps(df=df, **kw)

    assert on == off                                 # election unchanged flag-on
    assert on["length"] == 3
    assert on["swing_type"] != "holding_shelf"


def test_holding_shelf_election_pullback_outranks_shelf_on_integer_tie():
    latest = pd.Series({"Close": 100.0})
    base = dict(low_index=9, end_index=10, trigger_price=105.0,
                descent_frac=0.9, high_descent_frac=0.9)
    pullback = dict(base, length=3, swing_type="terminal_valley", _quality=0.05)
    shelf = dict(base, length=5, swing_type="holding_shelf", _quality=0.90)

    # Full integer tie on (end, low): the pullback form wins regardless of
    # length or float quality — quality never compares across forms.
    best = select_active_lps_candidate([pullback, shelf], latest)
    assert best["swing_type"] == "terminal_valley"

    # But a LATER shelf still beats an earlier pullback: latest-actionable
    # election is preserved across forms.
    later_shelf = dict(shelf, end_index=11, low_index=10)
    best = select_active_lps_candidate([pullback, later_shelf], latest)
    assert best["swing_type"] == "holding_shelf"


def test_lps_swing_type_labels_undercut_rebound(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[108, 106, 104],
        lows=[103, 100, 98],
        closes=[104, 101, 100],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=4,
        base_range_threshold=5,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["setup_type"] == "REBOUND"
    assert result["zone_type"] == "UNDERCUT_S"
    assert result["swing_type"] == "undercut_rebound"


def test_lps_rejects_extended_shallow_overshoot_shelf(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[114.5, 114.2, 114.1, 114.0, 114.2],
        lows=[110.7, 110.4, 110.5, 110.6, 110.5],
        closes=[113.8, 113.9, 113.8, 113.9, 113.8],
    )

    result, rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert result is None
    assert any(str(k).startswith("pullback_profile") for k in rejects)


def test_lps_wide_profile_gets_more_spread_room_than_tight_profile(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[108, 106],
        lows=[105, 102],
        closes=[106, 104],
    )

    tight, tight_rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=2.4,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )
    wide = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4.0,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert tight is None
    assert tight_rejects["spread_profile"] == 1
    assert wide is not None
    assert wide["profile_unit"] == 4.0


def test_lps_spread_can_expand_slightly_but_not_a_lot(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    small = _lps_behavior_frame(
        highs=[108, 106],
        lows=[106, 103],
        closes=[107, 104],
    )
    large = _lps_behavior_frame(
        highs=[108, 106],
        lows=[107, 102.5],
        closes=[107, 104],
    )

    ok = detect_lps(
        df=small,
        latest=small.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4.0,
        base_len=20,
        swing_complete_idx=-1,
    )
    bad, rejects = detect_lps(
        df=large,
        latest=large.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4.0,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert ok is not None
    assert ok["spread_expansion_profile"] == pytest.approx(0.25)
    assert bad is None
    assert rejects["spread_expansion"] == 1


def test_lps_selector_latest_actionable_beats_older_quality(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[112, 110, 108, 106],
        lows=[106, 102, 105, 102],
        closes=[107, 103, 106, 104],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=7,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_index"] == 2
    assert result["end_index"] == 4


def test_lps_selector_skips_non_actionable_latest(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[112, 110, 109, 107],
        lows=[105, 102, 105, 102],
        closes=[106, 103, 106, 107],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=7,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_index"] == 0
    assert result["end_index"] == 2


def test_detect_lps_tests_returns_non_overlapping_support_tests(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[118, 117, 108, 106, 116, 115, 107, 105],
        lows=[116, 115, 102, 100, 114, 113, 101, 100],
        closes=[117, 116, 104, 103, 115, 114, 103, 103],
    )
    df.index = pd.date_range("2026-01-01", periods=len(df), freq="D")

    tests = detect_lps_tests(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert len(tests) >= 2
    assert all("start_date" in test and "end_date" in test for test in tests)
    spans = {(test["start_index"], test["end_index"]) for test in tests}
    assert len(spans) == len(tests)


def test_measure_bar_compression_reports_base_spread_texture():
    base_df = pd.DataFrame([
        {"High": 102.0, "Low": 100.0, "Spread": 2.0},
        {"High": 103.0, "Low": 102.0, "Spread": 1.0},
        {"High": 104.0, "Low": 101.0, "Spread": 3.0},
        {"High": 105.0, "Low": 103.0, "Spread": 2.0},
        {"High": 106.0, "Low": 105.0, "Spread": 1.0},
    ])

    result = measure_bar_compression(base_df, box_height=10.0, atr_val=2.0)

    assert result["median_spread_atr"] == 1.0
    assert result["p80_spread_atr"] == 1.1
    assert result["median_spread_pct_box"] == 0.2
    assert result["tight_bar_pct"] == 0.8


# ── Threshold-move companions (solve-the-engine flip checklist #5/#6,
#    operator grant 2026-07-16/17) ────────────────────────────────────────────


def test_vol50_non_finite_refuses_both_forms(monkeypatch, _lps_behavior_frame):
    # A NaN Vol_50 makes both ratio comparisons silently False — the dry-up
    # gate would "pass" on missing data. The refusal guard must dominate even
    # a geometry the shelf form would otherwise save.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    df = _lps_behavior_frame(
        highs=[108.5, 107.8, 107.5],
        lows=[106.5, 106.2, 106.0],
        closes=[107.5, 107.0, 106.8],
    )
    df["Vol_50"] = float("nan")

    result, rejects = detect_lps(df=df, latest=df.iloc[-1], diagnose=True, **_SHELF_KW)

    assert result is None
    assert rejects["vol50_nonpos"] >= 1


def test_vol_ratio_088_still_rejected_at_the_new_floor(monkeypatch, _lps_behavior_frame):
    # Companion pin for the 0.85 -> 0.87 move: a window whose ONLY pullback
    # failure is volume at ratio 0.88 stays rejected (the shelf also refuses —
    # low in the box — so the volume verdict is decisive for the pullback form).
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    monkeypatch.setattr(settings, "LPS_VOL_CONTRACTION_MAX", 0.87)
    df = _lps_behavior_frame(
        highs=[103.5, 102.8, 102.5],
        lows=[101.5, 101.2, 101.0],
        closes=[102.5, 102.0, 101.8],
    )
    df["Volume"] = 880  # ratio 0.88 vs Vol_50 1000

    result, rejects = detect_lps(df=df, latest=df.iloc[-1], diagnose=True, **_SHELF_KW)

    assert result is None
    assert rejects["vol_contraction"] >= 1


def test_two_bar_shelf_floor_admits_shelves_not_noise(monkeypatch, _lps_behavior_frame):
    # Companion pins for the shelf-length 3 -> 2 move. At n=2 the monotone
    # axis is one comparison (near-vacuous) — the position and profile gates
    # must carry the discrimination.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    monkeypatch.setattr(settings, "LPS_SHELF_LENGTH_MIN", 2)

    # A 2-bar hot-volume HIGH shelf (the VCTR class): shelf-saved.
    high_shelf = _lps_behavior_frame(
        highs=[108.5, 107.5], lows=[106.5, 106.0], closes=[107.5, 106.8])
    high_shelf["Volume"] = 1400
    accepted = detect_lps(df=high_shelf, latest=high_shelf.iloc[-1], **_SHELF_KW)
    assert accepted is not None
    assert accepted["swing_type"] == "holding_shelf"

    # The canon failure geometry at 2 bars — flat + LOW + hot volume: dead.
    low_flat = _lps_behavior_frame(
        highs=[103.5, 102.5], lows=[101.5, 101.0], closes=[102.5, 101.8])
    low_flat["Volume"] = 1400
    result, rejects = detect_lps(df=low_flat, latest=low_flat.iloc[-1],
                                 diagnose=True, **_SHELF_KW)
    assert result is None
    assert rejects["holding_shelf_refused"] >= 1

    # A 2-bar rising-low wedge + hot volume: the monotone axis still bites.
    wedge = _lps_behavior_frame(
        highs=[108.5, 107.5], lows=[106.0, 106.45], closes=[107.5, 107.0])
    wedge["Volume"] = 1400
    assert detect_lps(df=wedge, latest=wedge.iloc[-1], **_SHELF_KW) is None
