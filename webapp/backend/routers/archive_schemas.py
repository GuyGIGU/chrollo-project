"""Pydantic schemas for archive API responses and requests."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SetupOut(BaseModel):
    id: int
    ticker: str
    scan_date: str
    setup_type: str
    tier: str
    score: float
    current_price: Optional[float] = None
    r_level: Optional[float] = None
    s_level: Optional[float] = None
    trigger_price: Optional[float] = None
    base_length: Optional[int] = None
    box_width: Optional[float] = None
    touches: Optional[int] = None
    r_touches: Optional[int] = None
    s_touches: Optional[int] = None
    r_anchor: Optional[int] = None
    s_anchor: Optional[int] = None
    atr_ratio: Optional[float] = None
    lps_length: Optional[int] = None
    breach_days: Optional[int] = None
    vol_contraction: Optional[float] = None
    tightness_ratio: Optional[float] = None
    # Sub-scores
    score_box_tightness: Optional[float] = None
    score_touch_density: Optional[float] = None
    score_atr_squeeze: Optional[float] = None
    score_lps_tightness: Optional[float] = None
    score_vol_contraction: Optional[float] = None
    score_base_age: Optional[float] = None
    score_uptrend_bonus: Optional[float] = None
    # Forward returns
    triggered: Optional[int] = None
    trigger_date: Optional[str] = None
    fwd_return_1d: Optional[float] = None
    fwd_return_5d: Optional[float] = None
    fwd_return_10d: Optional[float] = None
    fwd_return_20d: Optional[float] = None
    fwd_return_60d: Optional[float] = None
    mfe_20d: Optional[float] = None
    mae_20d: Optional[float] = None
    mfe_60d: Optional[float] = None
    mae_60d: Optional[float] = None
    mfe_20d_date: Optional[str] = None
    mae_20d_date: Optional[str] = None
    r_multiple_20d: Optional[float] = None
    r_multiple_60d: Optional[float] = None
    trigger_volume_ratio: Optional[float] = None
    days_to_trigger: Optional[int] = None
    days_to_2_5r: Optional[int] = None
    days_to_15pct: Optional[int] = None
    days_to_stop: Optional[int] = None
    barrier_label: Optional[str] = None
    win_barrier: Optional[str] = None
    # Market context
    spy_trend: Optional[str] = None
    vix_level: Optional[float] = None
    sector_etf: Optional[str] = None
    sector_trend: Optional[str] = None
    rs_vs_sector_pct: Optional[float] = None
    dist_52w_high_pct: Optional[float] = None
    regime_state: Optional[str] = None
    regime_breadth_50_pct: Optional[float] = None
    regime_breadth_200_pct: Optional[float] = None
    regime_distribution_days: Optional[int] = None
    regime_spy_above_50: Optional[int] = None
    regime_spy_above_200: Optional[int] = None
    regime_spy_50d_slope_pct: Optional[float] = None
    regime_qqq_above_50: Optional[int] = None
    regime_qqq_above_200: Optional[int] = None
    regime_qqq_50d_slope_pct: Optional[float] = None
    # Phase A structural detail
    phase_d_inner: Optional[int] = None
    lps_in_inner: Optional[int] = None
    inner_source: Optional[str] = None
    inner_search_start_bar: Optional[int] = None
    inner_climax_bar: Optional[int] = None
    inner_reaction_bar: Optional[int] = None
    inner_reaction_pct: Optional[float] = None
    inner_reaction_bars: Optional[int] = None
    # HTF (higher-timeframe) context — same Trend+Box engine on weekly/monthly bars
    htf_w_stage2: Optional[int] = None
    htf_w_trend_state: Optional[str] = None
    htf_w_in_consol: Optional[int] = None
    htf_w_phase: Optional[str] = None
    htf_w_box_r: Optional[float] = None
    htf_w_box_s: Optional[float] = None
    htf_w_box_width: Optional[float] = None
    htf_w_reaccum: Optional[int] = None
    htf_w_daily_nested: Optional[int] = None
    htf_m_stage2: Optional[int] = None
    htf_m_trend_state: Optional[str] = None
    htf_m_in_consol: Optional[int] = None
    htf_m_phase: Optional[str] = None
    htf_m_box_r: Optional[float] = None
    htf_m_box_s: Optional[float] = None
    htf_m_box_width: Optional[float] = None
    htf_m_reaccum: Optional[int] = None
    htf_m_daily_nested: Optional[int] = None
    # Volume-around-touches signature
    r_touch_vol_z: Optional[float] = None
    s_touch_vol_z: Optional[float] = None
    # LPS shape & zone detail
    lps_descent_frac: Optional[float] = None
    lps_zone_type: Optional[str] = None
    # New sub-scores
    score_high_proximity: Optional[float] = None
    score_breadth_bonus: Optional[float] = None
    score_rs_bonus: Optional[float] = None
    # VCP contraction footprint
    contraction_count: Optional[int] = None
    contraction_quality: Optional[float] = None
    final_contraction_depth: Optional[float] = None
    contraction_vol_trend: Optional[float] = None
    score_contraction: Optional[float] = None
    # Base bar-compression texture
    base_median_spread_atr: Optional[float] = None
    base_p80_spread_atr: Optional[float] = None
    base_median_spread_pct_box: Optional[float] = None
    base_tight_bar_pct: Optional[float] = None
    # Ascending support / higher-lows footprint
    support_slope_atr: Optional[float] = None
    ascending_support_quality: Optional[float] = None
    score_ascending_support: Optional[float] = None
    # Worked-equilibrium occupancy footprint
    eq_r_touches: Optional[int] = None
    eq_s_touches: Optional[int] = None
    eq_r_touch_thirds: Optional[int] = None
    eq_s_touch_thirds: Optional[int] = None
    eq_lower_dwell: Optional[float] = None
    eq_mid_dwell: Optional[float] = None
    eq_upper_dwell: Optional[float] = None
    eq_coverage: Optional[float] = None
    # Region/bin features
    bin_a_bars: Optional[int] = None
    bin_a_range_pct: Optional[float] = None
    bin_a_volume_ratio: Optional[float] = None
    bin_b_bars: Optional[int] = None
    bin_b_range_pct: Optional[float] = None
    bin_b_volume_ratio: Optional[float] = None
    bin_b_cog_end: Optional[float] = None
    bin_b_cog_crossings: Optional[int] = None
    bin_b_cog_rng: Optional[float] = None
    bin_b_cog_corr: Optional[float] = None
    bin_c_present: Optional[int] = None
    bin_c_type: Optional[str] = None
    bin_c_event_date: Optional[str] = None
    bin_c_event_bar: Optional[int] = None
    bin_c_undercut_atr: Optional[float] = None
    bin_c_recovery_bars: Optional[int] = None
    bin_c_recovery_bar: Optional[int] = None
    bin_c_time_loc: Optional[float] = None
    bin_c_spring_vol_z: Optional[float] = None
    bin_d_bars: Optional[int] = None
    bin_d_start_bar: Optional[int] = None
    bin_d_range_pct: Optional[float] = None
    bin_d_volume_ratio: Optional[float] = None
    bin_d_support_slope_atr: Optional[float] = None
    bin_d_higher_low_frac: Optional[float] = None
    bin_d_ascending_support_quality: Optional[float] = None
    bin_d_boundary_source: Optional[str] = None
    phase_d_evidence_json: Optional[str] = None
    bin_lps_bars: Optional[int] = None
    lps_position_in_box: Optional[float] = None
    bin_d_vs_b_range_ratio: Optional[float] = None
    bin_d_vs_b_volume_ratio: Optional[float] = None
    bin_d_vs_b_support_quality_delta: Optional[float] = None
    lps_stretch_atr: Optional[float] = None
    lps_stretch_box: Optional[float] = None
    # ADR% absolute-volatility character
    adr_pct: Optional[float] = None
    score_adr: Optional[float] = None
    # Curation
    quality_label: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None

    model_config = {"from_attributes": True}


class EpisodeOut(SetupOut):
    """A setup collapsed to one row per *episode*: the first-seen (canonical)
    row plus how long the base persisted across daily re-flags."""

    episode_key: str     # stable logical setup key: ticker|setup_type|first_seen
    scan_count: int       # number of daily scans that flagged this base
    first_seen: str       # == canonical scan_date (the entry anchor)
    last_seen: str        # latest scan that still flagged the same base
    passed: bool = False  # operator reviewed this setup and skipped it
    review_note: Optional[str] = None


class LabelUpdate(BaseModel):
    quality_label: Optional[str] = None
    notes: Optional[str] = None


class ManualSetupIn(BaseModel):
    ticker: str
    scan_date: Optional[str] = None    # YYYY-MM-DD; defaults to today
    quality_label: Optional[str] = None
    notes: Optional[str] = None


class ReviewToggleIn(BaseModel):
    ticker: str
    # Explicit for an archive-table row (the episode first-seen date); omitted
    # by the live screener, where it's resolved to the ticker's current episode.
    scan_date: Optional[str] = None


class ReviewMarkIn(ReviewToggleIn):
    note: Optional[str] = None
