"""Archive-feed completeness gate (Purity Pass Task 2 — Leach P4).

The archive writer fills the operator-locked columns by silent string lookup
(``column=r.get("_key")`` in core/archive/writer.py): if an engine rename moves
an emission key and the writer string lags, the column goes NULL in every new
archive row with no error anywhere. This gate makes that failure RED instead
of silent, from both sides of the seam:

  1. static  — every floor key still appears as a writer ``.get`` source
               (the writer side of the mapping is intact);
  2. dynamic — a fired shadow-fixture ticker's eval result carries every floor
               key non-null (the engine emission side is intact).

The floor is the 83 writer-source keys that were non-null for ALL 32 fired
fixture tickers at capture (2026-07-17). A sanctioned coordinated rename must
update this list in the SAME commit — that visibility is the point.
"""
import re
from pathlib import Path

import pytest

from engine_alpha.evaluation import EVAL_ERROR
from core.pipeline.screener import _evaluate_ticker
from tools.shadow_diff import _load_fixture

_WRITER = Path(__file__).resolve().parent.parent / "core" / "archive" / "writer.py"

# Writer-source keys non-null on every fired fixture ticker (frozen 2026-07-17).
FEED_FLOOR = (
    "Setup", "Tier",
    "_adr_pct", "_ascending_support_quality", "_bars_since_BC",
    "_base_median_spread_atr", "_base_median_spread_pct_box",
    "_base_p80_spread_atr", "_base_tight_bar_pct",
    "_bin_a_bars", "_bin_a_range_pct", "_bin_a_volume_ratio",
    "_bin_b_bars", "_bin_b_cog_corr", "_bin_b_cog_crossings",
    "_bin_b_cog_end", "_bin_b_cog_rng", "_bin_b_range_pct",
    "_bin_b_volume_ratio",
    "_bin_d_ascending_support_quality", "_bin_d_bars",
    "_bin_d_boundary_source", "_bin_d_higher_low_frac", "_bin_d_range_pct",
    "_bin_d_start_bar", "_bin_d_volume_ratio", "_bin_d_vs_b_range_ratio",
    "_bin_d_vs_b_volume_ratio", "_bin_lps_bars",
    "_breadth_pct", "_contraction_count", "_contraction_quality",
    "_contraction_vol_trend", "_descent_length", "_dist_52w_high_pct",
    "_eq_close_lower_dwell", "_eq_close_mid_dwell", "_eq_close_upper_dwell",
    "_eq_coverage", "_eq_lower_dwell", "_eq_mid_dwell",
    "_eq_engagement_respect_frac", "_eq_max_excursion_atr",
    "_eq_r_touch_thirds", "_eq_r_touches", "_eq_respect_frac",
    "_eq_s_touch_thirds", "_eq_s_touches", "_eq_upper_dwell",
    "_excess_return_6m", "_final_contraction_depth",
    "_last_supper_pullback_from_extension_pct", "_last_supper_reclaim_quality",
    "_lps_anchor_bar", "_lps_anchor_date", "_lps_descent_frac",
    "_lps_low_bar", "_lps_low_date", "_lps_position_in_box",
    "_lps_stretch_atr", "_lps_stretch_box", "_lps_swing_depth_atr",
    "_lps_swing_depth_box", "_lps_swing_depth_pct", "_lps_swing_type",
    "_lps_zone_type",
    "_phase_a_start_date", "_phase_b_start_date", "_phase_d_evidence_json",
    "_phase_d_start_date",
    "_r_touch_vol_z", "_s_touch_vol_z", "_scope_confidence",
    "_stage2_52w_low_pct", "_stage2_ma200_slope_1m_pct",
    "_stage2_trend_pass_count", "_support_slope_atr",
    "_trav_bottom_dead_space", "_trav_last_support_frac",
    "_trav_max_swing_frac", "_trav_n_full_traversals", "_trav_n_swings",
    "_trav_rail_reaches_high", "_trav_rail_reaches_low",
    "_trav_top_dead_space",
)


def test_writer_still_maps_every_floor_key():
    src = _WRITER.read_text(encoding="utf-8")
    sources = {m.group(2) for m in re.finditer(r'(\w+)=(?:r|row)\.get\("([^"]+)"', src)}
    missing = [k for k in FEED_FLOOR if k not in sources]
    assert not missing, (
        f"writer no longer .get()s these engine keys: {missing} — a rename "
        "moved an emission key without the writer (silent-NULL archive columns)"
    )


@pytest.mark.slow
def test_fired_fixture_result_feeds_every_floor_key():
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None
    result = None
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        r = _evaluate_ticker(ticker, df, spy_6m, breadth)
        if r is not None and r is not EVAL_ERROR:
            result = r
            break
    assert result is not None, "no fixture ticker fires — fixture or engine broken"
    bad = [k for k in FEED_FLOOR
           if result.get(k) is None
           or (isinstance(result.get(k), float) and result[k] != result[k])]
    assert not bad, (
        f"fired result no longer emits these writer-mapped keys non-null: {bad} "
        "— the archive columns they feed would go silently NULL"
    )
