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
    score_oscillation: Optional[float] = None
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
    # Market context
    spy_trend: Optional[str] = None
    vix_level: Optional[float] = None
    sector_etf: Optional[str] = None
    sector_trend: Optional[str] = None
    rs_vs_sector_pct: Optional[float] = None
    dist_52w_high_pct: Optional[float] = None
    # Phase A structural detail
    phase_d_inner: Optional[int] = None
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
