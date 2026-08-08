"""Pydantic schemas for archive API responses and requests."""
from __future__ import annotations

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator

_serve_log = logging.getLogger("chrollo.archive_serve")


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
    # (was missing until the task-9 drift-tripwire's first run — the archive
    # API silently never served it; the tripwire exists to catch exactly this)
    score_traversal_quality: Optional[float] = None
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
    # Elapsed-window outcome (window-agnostic edge metric)
    mfe_to_date: Optional[float] = None
    mae_to_date: Optional[float] = None
    ret_to_date: Optional[float] = None
    bars_to_date: Optional[int] = None
    abnormal_ret_to_date: Optional[float] = None
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
    lps_swing_type: Optional[str] = None
    lps_anchor_bar: Optional[int] = None
    lps_anchor_date: Optional[str] = None
    lps_low_bar: Optional[int] = None
    lps_low_date: Optional[str] = None
    lps_swing_depth_pct: Optional[float] = None
    lps_swing_depth_atr: Optional[float] = None
    lps_swing_depth_box: Optional[float] = None
    last_supper_pullback_from_extension_pct: Optional[float] = None
    last_supper_source_box_age: Optional[int] = None
    last_supper_reclaim_quality: Optional[float] = None
    # ADR% absolute-volatility character
    adr_pct: Optional[float] = None
    score_adr: Optional[float] = None
    # Curation
    quality_label: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    # Archive identity + evidence provenance — the read-verdict loop binds to
    # the (ticker, scan_date, universe_type) triple and stamps the version the
    # operator saw, so archive rows must serve both (council review 2026-08-05,
    # findings 4 + 6).
    universe_type: Optional[str] = None
    engine_config_version: Optional[str] = None
    # ── The narrative fact block (Surface the Read) ──
    # The event_map family + electing-pool provenance + the election trace,
    # served so the grading loop sees the story the archive recorded. NULL =
    # not measured (pre-flip rows / flag off) — never defaulted here (EC-26);
    # the operator must be able to tell "not measured" from "nothing happened"
    # (explicit zeros). The two JSON TEXT cells are parsed ONCE at this
    # boundary so the wire carries structure; an unparseable cell serves None
    # for that setup (honest degrade — one corrupt row never 500s the list).
    # Pool vocabulary is enforced three ways at WRITE time (CHECK + stamping
    # assertion + producing tests); the serve side stays a plain string so one
    # historic anomaly cannot blank the whole surface.
    elected_pool: Optional[str] = None
    story_admission_profile: Optional[str] = None
    event_map_n_swings: Optional[int] = None
    event_map_pre_box_trend: Optional[str] = None
    event_map_n_labels: Optional[int] = None
    event_map_n_committed: Optional[int] = None
    event_map_completed_s: Optional[int] = None
    event_map_completed_r: Optional[int] = None
    event_map_alternations: Optional[int] = None
    event_map_terminal_posture: Optional[int] = None
    event_map_terminal_drift: Optional[int] = None
    event_map_story_admitted: Optional[int] = None
    event_map_episode_nan_bars: Optional[int] = None
    event_map_episode_profile: Optional[str] = None
    event_map_episodes: Optional[list] = None
    election_trace: Optional[dict] = None
    # ── Technical Analysis Grade v2 family (task 9) — NULL on every pre-flip
    # row FOREVER (no backfill). The drift-tripwire in tests/test_dashboard_wire
    # pins that every registry term column + family column stays covered here.
    ta_grade: Optional[float] = None
    ta_grade_raw: Optional[float] = None
    puzzle_completeness: Optional[int] = None
    puzzle_chronology: Optional[str] = None
    puzzle_upthrust_terminal: Optional[int] = None
    score_puzzle_quality: Optional[float] = None
    score_spring: Optional[float] = None
    score_story_s_tests: Optional[float] = None
    score_story_r_rejections: Optional[float] = None
    score_story_alternations: Optional[float] = None
    score_story_terminal_posture: Optional[float] = None
    lps_shrink_frac: Optional[float] = None
    lps_window_classification: Optional[str] = None
    story_richness_rate: Optional[float] = None
    trend_base_count: Optional[int] = None
    inter_base_width_ratio: Optional[float] = None
    fired_tags: Optional[list] = None

    # The two deep JSON cells degrade PER ROW — parse failure AND wrong
    # container shape both land None (council review 2026-08-05, finding 8:
    # a cell holding valid JSON of the wrong container would otherwise pass
    # this validator and 500 the whole list at response-model time). Every
    # degrade logs, so corruption is visible without breaking the serve —
    # never confusable with the legitimate tape-unreadable state, which is
    # NULL in the cell itself.
    @field_validator("event_map_episodes", "election_trace", "fired_tags",
                     mode="before")
    @classmethod
    def _parse_json_cell(cls, value, info: ValidationInfo):
        if value is None:
            return None
        expected = dict if info.field_name == "election_trace" else list
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, RecursionError):
                _serve_log.warning(
                    "archive %s cell unparseable — row degraded to None",
                    info.field_name)
                return None
        if not isinstance(value, expected):
            _serve_log.warning(
                "archive %s cell parsed to %s, expected %s — row degraded to None",
                info.field_name, type(value).__name__, expected.__name__)
            return None
        return value

    model_config = {"from_attributes": True}


class EpisodeOut(SetupOut):
    """A setup collapsed to one row per *episode*: the first-seen (canonical)
    row plus how long the base persisted across daily re-flags."""

    episode_key: str     # stable logical setup key: ticker|setup_type|first_seen
    scan_count: int       # number of daily scans that flagged this base
    first_seen: str       # == canonical scan_date (the entry anchor)
    last_seen: str        # latest scan that still flagged the same base
    # The episode's CURRENT grade — the LATEST member's ta_grade (the value
    # min_ta_grade floors on; the inherited ta_grade above is the canonical
    # first-seen row's, NULL forever on flip-straddling episodes).
    latest_ta_grade: Optional[float] = None
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


class ReadVerdictIn(BaseModel):
    """The concordance verdict on the engine's READ. ``scan_date`` is REQUIRED
    and verbatim (the payload's scan_identity / the archive row's own date) —
    the read changes across scans, so this never resolves to an episode.
    ``verdict`` None clears the mark; an EMPTY STRING is a 422, never a clear.
    The write contract mirrors (and is at least as strict as) the GET twin's
    Query constraints — a persisted row the read path refuses to serve is a
    write-boundary defect (council review 2026-08-05, finding 7)."""
    ticker: str = Field(min_length=1, max_length=12)
    scan_date: str = Field(min_length=10, max_length=10,
                           pattern=r"^\d{4}-\d{2}-\d{2}$")
    # Scan-level half of the archive identity triple; None resolves to the
    # equities-default scope server-side (EC-1 one source).
    universe_type: Optional[str] = Field(default=None, max_length=32)
    # Evidence provenance from the payload's scan_identity (manifest hash).
    engine_config_version: Optional[str] = Field(default=None, max_length=64)
    verdict: Optional[str] = None   # 'agree' | 'disagree' | None (clear)
    # The GRADE channel (task 14): 'read right, grade wrong' separable from a
    # reading error. None = not judged (and clears any prior grade verdict).
    grade_verdict: Optional[str] = None  # 'agree' | 'too_high' | 'too_low' | None
    note: Optional[str] = Field(default=None, max_length=500)
