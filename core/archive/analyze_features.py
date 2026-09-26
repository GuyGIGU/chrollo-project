"""What the archive report card reads: its feature lists and the engine-epoch seam.

``python -m core.archive.analyze`` tabulates, correlates and tests the archive
columns named here. Every list names columns the archive already stores; none
of them is new data.

The Phase-A anchor family lives here too, with the three functions that decide
whether it may be pooled: across an engine seam those columns are two
different measurements under one name.
"""
from __future__ import annotations

import pandas as pd

from engine_alpha.scoring import taxonomy

# Structural features (the "picture" - produced by the Visual Structure Engine).
STRUCTURAL_FEATURES = [
    "box_width", "base_length", "touches", "r_touches", "s_touches",
    "atr_ratio", "lps_length", "breach_days", "vol_contraction",
    "tightness_ratio", "lps_descent_frac", "r_touch_vol_z", "s_touch_vol_z",
    "dist_52w_high_pct", "excess_return_6m", "rs_vs_sector_pct", "breadth_pct",
    "bars_since_bc", "descent_length",
    "inner_reaction_pct", "inner_reaction_bars",
    "contraction_count", "contraction_quality", "final_contraction_depth",
    "contraction_vol_trend",
    "base_median_spread_atr", "base_p80_spread_atr",
    "base_median_spread_pct_box", "base_tight_bar_pct",
    "support_slope_atr", "ascending_support_quality",
    "eq_r_touches", "eq_s_touches",
    "eq_r_touch_thirds", "eq_s_touch_thirds",
    "eq_lower_dwell", "eq_mid_dwell", "eq_upper_dwell", "eq_coverage",
    "trav_n_full_traversals", "trav_n_swings",
    "trav_top_dead_space", "trav_bottom_dead_space",
    "trav_rail_reaches_high", "trav_rail_reaches_low", "trav_max_swing_frac",
    "trav_last_support_frac", "trav_coil_floor_pos",
    "adr_pct",
    # Region (bin) features (Stage 2A — "where am I in the base?")
    "bin_a_bars", "bin_a_range_pct", "bin_a_volume_ratio",
    "bin_b_range_pct", "bin_b_volume_ratio",
    "bin_b_cog_end", "bin_b_cog_crossings", "bin_b_cog_rng", "bin_b_cog_corr",
    "bin_c_present", "bin_c_undercut_atr", "bin_c_recovery_bars",
    "bin_c_time_loc", "bin_c_spring_vol_z",
    "bin_d_bars", "bin_d_range_pct", "bin_d_volume_ratio",
    "bin_d_support_slope_atr", "bin_d_higher_low_frac",
    "bin_d_ascending_support_quality",
    "bin_lps_bars", "lps_position_in_box",
    "bin_d_vs_b_range_ratio", "bin_d_vs_b_volume_ratio",
    "bin_d_vs_b_support_quality_delta",
    "lps_stretch_atr", "lps_stretch_box",
    "lps_anchor_bar", "lps_low_bar",
    "lps_swing_depth_pct", "lps_swing_depth_atr", "lps_swing_depth_box",
    "last_supper_pullback_from_extension_pct",
    "last_supper_source_box_age", "last_supper_reclaim_quality",
    # Minervini Stage-2 trend template (raw context)
    "stage2_ma_stack_pass", "stage2_ma200_slope_1m_pct",
    "stage2_52w_low_pct", "stage2_trend_pass_count", "stage2_trend_pass",
    # HTF (higher-timeframe) re-accumulation context — does HTF alignment predict outcome?
    "htf_w_stage2", "htf_w_in_consol", "htf_w_reaccum", "htf_w_daily_nested", "htf_w_box_width",
    "htf_m_stage2", "htf_m_in_consol", "htf_m_reaccum", "htf_m_daily_nested", "htf_m_box_width",
]

# The two-axis read — mirrors engine_alpha.structure.Structure.horizontal / .vertical.
# A daily chart is read along two axes; splitting the fingerprint by axis lets the
# edge analysis ask WHICH ONE separates winners from losers (the validation
# question). Every column here is already archived (core/archive/writer.py) — these
# are groupings of the existing fingerprint, not new data.
#   HORIZONTAL = structure along the TIME axis: how long the base runs, how often
#     each rail is tested, and whether the swings travel the range rail-to-rail.
HORIZONTAL_FEATURES = [
    "base_length", "r_touches", "s_touches",
    "eq_r_touches", "eq_s_touches", "eq_r_touch_thirds", "eq_s_touch_thirds",
    "breach_days", "lps_length", "bin_lps_bars", "lps_position_in_box",
    "lps_anchor_bar", "lps_low_bar", "last_supper_source_box_age",
    "trav_n_full_traversals", "trav_n_swings",
    "trav_rail_reaches_high", "trav_rail_reaches_low", "trav_last_support_frac",
    "bin_c_time_loc", "bin_d_bars",
]
#   VERTICAL = magnitudes along the PRICE axis: rail levels / range height, the
#     Phase-C undercut depth, and the right-side breakout thrust.
VERTICAL_FEATURES = [
    "box_width", "tightness_ratio", "atr_ratio",
    "lps_descent_frac", "bin_c_undercut_atr",
    "lps_stretch_atr", "lps_stretch_box",
    "lps_swing_depth_pct", "lps_swing_depth_atr", "lps_swing_depth_box",
    "last_supper_pullback_from_extension_pct", "last_supper_reclaim_quality",
    "trav_top_dead_space", "trav_bottom_dead_space", "trav_max_swing_frac",
    "trav_coil_floor_pos",
    "final_contraction_depth", "bin_d_vs_b_range_ratio",
]

# Sub-scores (the Scoring Engine decomposition) — sourced from the ONE registry
# (engine_alpha/scoring/taxonomy.py) so a new/renamed/dropped sub-score can't silently
# drift out of the correlation + signal-edge analysis. Same 14 columns, same order.
SUB_SCORES = taxonomy.archive_columns()

# Outcome targets (filled by update_forward_returns).
OUTCOME_TARGETS = ["fwd_return_20d", "fwd_return_60d", "r_multiple_20d"]

# Tightness features specifically - the prime directive.
TIGHTNESS_FEATURES = ["box_width", "atr_ratio", "tightness_ratio",
                      "lps_descent_frac", "contraction_quality",
                      "base_median_spread_atr", "base_tight_bar_pct",
                      "bin_d_vs_b_range_ratio",
                      "bin_d_ascending_support_quality",
                      "trav_n_full_traversals", "trav_top_dead_space"]

# ── The Phase-A anchor family — measurements that move with the READER ───────
# These describe the climax->AR span, so their value is a function of where the
# engine puts the automatic reaction, not only of what the chart did. Two
# mechanisms move that anchor with no chart changing: the always-on
# climax-terminality repair (a "climax" price out-ran re-anchors to the box's own
# run-up extreme) and the dark AR_FIRST_REACTION_ENABLED tighten, whose entire
# flip IS a re-anchor — 101 of 335 firing overlays, re-measured 2026-08-31
# against the re-keyed climax (was 100 of 291 on 2026-08-13).
#
# strategy_alpha.md states the consequence — "the engine_config_version rotation
# partitions the bin_a_*/bars_since_bc/descent_length archive seam" — and
# flag_ledger.md names taking that partition HERE as the AR flip's blocking
# precondition. Nothing was taking it: the family sat in STRUCTURAL_FEATURES and
# was pooled over every epoch in the archive, so the blend read as a measurement
# rather than as an artifact of when each row was written.
#
# Within one epoch they are a variable. Across two they are an average of two
# different questions. So across a seam they are withheld from the pooled tables
# and reported on the CURRENT epoch alone, named.
PHASE_A_ANCHOR_FEATURES = ("bin_a_bars", "bin_a_range_pct", "bin_a_volume_ratio",
                           "bars_since_bc", "descent_length",
                           # Power-Play species numerics (program Task 7):
                           # anchor-family FROM BIRTH — the clock and the pole
                           # measurement are anchor-identity-derived, so they
                           # join the epoch partition in the same change that
                           # created the columns, never retroactively.
                           "pp_clock", "pp_pole_gain")


def engine_epochs(df: pd.DataFrame) -> list:
    """The distinct engine epochs present. Unversioned rows (the pre-versioning
    archive) count as their own epoch "?" — they were written by an engine too,
    just one that did not stamp itself, and folding them into a versioned pool
    is the same blend by a quieter route. Mirrors section_composition's fillna."""
    if "engine_config_version" not in df.columns:
        return []
    return sorted(df["engine_config_version"].fillna("?").astype(str).unique())


def current_epoch(df: pd.DataFrame):
    """The epoch that produced the MOST RECENT rows — the one whose numbers
    describe today's reader. Config hashes carry no ordering, so recency comes
    from the data: the epoch holding the latest scan_date. Deliberately NOT the
    largest epoch, which on this archive is an old pre-versioning one."""
    if "engine_config_version" not in df.columns or "scan_date" not in df.columns:
        return None
    known = df[df["engine_config_version"].notna()]
    if known.empty:
        return None
    latest = known.groupby("engine_config_version")["scan_date"].max()
    return None if latest.empty else str(latest.idxmax())


def anchor_seam(df: pd.DataFrame) -> bool:
    """True when the population spans an engine seam, so the Phase-A anchor
    family may not be pooled."""
    return len(engine_epochs(df)) > 1
