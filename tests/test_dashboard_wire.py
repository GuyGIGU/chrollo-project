"""Flag-off tripwires + key-set snapshot at the WIRE boundary (TA-grade build
task 2).

The scorer tripwire (tests/test_scoring.py::test_ta_score_v2_flag_off_leaks_no_v2_keys)
guards score_setup's result dict; this file guards the second leak point — the
serialized per-ticker dashboard payload (output/dashboard._extract_chart_data),
which previously had no flag-off snapshot at all. It drives the REAL payload
builder on a synthetic frame (the established house pattern from
tests/test_fetch_repair.py) — never a booted server. The sector-ETF lookup is
the one monkeypatched boundary (external lookup + a disk cache write).

The key-set snapshot is deliberately exact: adding or removing a wire key with
TA_SCORE_V2 off must be a conscious edit here, never silent drift — that is
EC-8's byte-identical promise expressed at the boundary the frontend consumes.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.scoring import taxonomy
from output import dashboard as dashboard_module


def _flag_off_payload(monkeypatch):
    """The per-ticker payload exactly as a flag-off scan would serialize it."""
    dates = pd.date_range("2026-01-01", periods=10, freq="B", name="Date")
    data = pd.DataFrame({
        "Open": np.linspace(10, 11, len(dates)),
        "High": np.linspace(10.5, 11.5, len(dates)),
        "Low": np.linspace(9.5, 10.5, len(dates)),
        "Close": np.linspace(10.2, 11.2, len(dates)),
        "Volume": np.linspace(1000, 1100, len(dates)),
    }, index=dates)
    sub_scores = {
        "box_tightness": 10.0, "touch_density": 12.0, "traversal_quality": 4.0,
        "atr_squeeze": 3.0, "lps_tightness": 11.0, "vol_contraction": 9.0,
        "base_age": 8.0, "uptrend_bonus": 0.0, "rs_bonus": 0.0,
        "high_proximity": 4.0, "breadth_bonus": 5.0, "contraction": 6.0,
        "ascending_support": 3.0, "adr": 4.0, "puzzle_quality": 5.0,
    }
    results = pd.DataFrame([{
        "Ticker": "AAA",
        "Tier": "A",
        "Score": 100,
        "Setup": "LPS",
        "Current Price": 11.2,
        "_trigger_price": 11.6,
        "_R": 11.5,
        "_S": 9.5,
        "_base_len": 8,
        "_lps_len": 2,
        "_lps_offset": 0,
        "_r_anchor_bar": 2,
        "_s_anchor_bar": 3,
        "_sub_scores": sub_scores,
    }])
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker",
                        lambda *_args: None)
    monkeypatch.setattr(settings, "TA_SCORE_V2", False)
    return dashboard_module._extract_chart_data(data, results, ["AAA"])["AAA"]


def test_wire_flag_off_leaks_no_v2_keys(monkeypatch):
    """No reserved v2 key may reach the wire — top level or sub_scores — while
    TA_SCORE_V2 is off. Derives from the ONE settled vocabulary (task 1)."""
    chart = _flag_off_payload(monkeypatch)
    for k in taxonomy.V2_RESULT_KEYS:
        assert k not in chart, (
            f"v2 key {k!r} leaked onto the flag-off wire payload")
        assert k not in chart["sub_scores"], (
            f"v2 key {k!r} leaked into flag-off sub_scores")


def test_wire_sub_scores_are_exactly_the_registry_emission(monkeypatch):
    """The served sub_scores key set equals the taxonomy's emitted keys — the
    wire cannot silently drop a registered term or invent an unregistered one."""
    chart = _flag_off_payload(monkeypatch)
    assert set(chart["sub_scores"]) == set(taxonomy.emitted_keys())


# The exact flag-off per-ticker key set (149 keys, captured 2026-08-08 at the
# task-2 baseline). Sorted. Changing the wire contract flag-off means editing
# this tuple deliberately in the same change — never drifting past it.
FLAG_OFF_WIRE_KEYS = (
    "R", "S",
    "_has_mini_consolidation",
    "_lps_zone_end_date", "_lps_zone_high", "_lps_zone_low",
    "_lps_zone_start_date",
    "_phase_a_end_date", "_phase_a_start_date", "_phase_b_start_date",
    "_phase_c_event_date", "_phase_d_start_date",
    "_scope_confidence",
    "adr_pct", "ascending_support_quality", "base_len",
    "bin_b_cog_corr", "bin_b_cog_crossings", "bin_b_cog_end", "bin_b_cog_rng",
    "bin_c_event_bar", "bin_c_event_date", "bin_c_present",
    "bin_c_recovery_bar", "bin_c_recovery_bars", "bin_c_spring_vol_z",
    "bin_c_time_loc", "bin_c_type", "bin_c_undercut_atr",
    "bin_d_ascending_support_quality", "bin_d_boundary_source",
    "bin_d_higher_low_frac", "bin_d_start_bar", "bin_d_support_slope_atr",
    "bin_d_vs_b_support_quality_delta",
    "candles",
    "contraction_count", "contraction_quality", "contraction_vol_trend",
    "days_to_earnings",
    "elected_pool", "election_trace",
    "event_map_alternations", "event_map_completed_r", "event_map_completed_s",
    "event_map_episode_nan_bars", "event_map_episode_profile",
    "event_map_episodes", "event_map_n_committed", "event_map_n_labels",
    "event_map_n_swings", "event_map_pre_box_trend",
    "event_map_story_admitted", "event_map_terminal_drift",
    "event_map_terminal_posture",
    "final_contraction_depth",
    "fund_earnings_surprise", "fund_eps_growth_accel", "fund_eps_growth_yoy",
    "fund_sales_growth_yoy",
    "higher_low_frac",
    "htf_m_box_r", "htf_m_box_s", "htf_m_box_width", "htf_m_daily_nested",
    "htf_m_in_consol", "htf_m_phase", "htf_m_reaccum", "htf_m_stage2",
    "htf_m_trend_state",
    "htf_w_box_r", "htf_w_box_s", "htf_w_box_width", "htf_w_daily_nested",
    "htf_w_in_consol", "htf_w_phase", "htf_w_reaccum", "htf_w_stage2",
    "htf_w_trend_state",
    "inner_R", "inner_S", "inner_box_width", "inner_climax_bar",
    "inner_end_bar", "inner_reaction_bar", "inner_reaction_bars",
    "inner_reaction_pct", "inner_search_start_bar", "inner_source",
    "inner_start_bar",
    "last_supper_pullback_from_extension_pct", "last_supper_reclaim_quality",
    "last_supper_source_box_age",
    "lps_anchor_bar", "lps_anchor_date", "lps_descent_frac", "lps_first_high",
    "lps_high_descent_frac", "lps_high_extension_atr",
    "lps_high_extension_box", "lps_in_inner", "lps_last_low", "lps_len",
    "lps_low_bar", "lps_low_date", "lps_offset", "lps_profile_unit",
    "lps_profile_unit_pct", "lps_pullback_profile",
    "lps_spread_expansion_profile", "lps_stretch_atr", "lps_stretch_box",
    "lps_swing_depth_atr", "lps_swing_depth_box", "lps_swing_depth_pct",
    "lps_swing_type", "lps_terminal_low_tolerance", "lps_tests",
    "lps_window_high", "lps_window_low", "lps_window_range_pct_box",
    "lps_zone_type",
    "monthly_box", "monthly_candles", "monthly_volumes",
    "phase_d_evidence_json", "phase_d_inner",
    "price",
    "r_anchor", "r_touch_vol_z",
    "rs_line_latest", "rs_line_new_high", "rs_rating",
    "s_anchor", "s_touch_vol_z",
    "score", "sector_etf", "sector_name", "setup",
    "story_admission_profile", "sub_scores", "support_slope_atr",
    "tier", "traversal_density", "trigger",
    "volumes",
    "weekly_box", "weekly_candles", "weekly_volumes",
)


def test_wire_flag_off_key_set_snapshot(monkeypatch):
    """The exact flag-off wire key set — the boundary snapshot EC-8's
    byte-identical promise was missing. Any add/remove/rename fails here until
    the snapshot is updated deliberately in the same change."""
    chart = _flag_off_payload(monkeypatch)
    assert tuple(sorted(chart.keys())) == tuple(sorted(FLAG_OFF_WIRE_KEYS))
