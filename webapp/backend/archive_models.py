"""
Setup Archive model — persistent memory for every screener signal.

Each row captures the full structural fingerprint of a detected setup,
its scoring decomposition, market context, and (once computed) the actual
forward returns / MFE / MAE.  This is the ground-truth table that the
calibration engine uses to validate and refine the screener's parameters.
"""
from sqlalchemy import CheckConstraint, Column, Float, Index, Integer, String, Text, UniqueConstraint

from database import Base


class SetupArchive(Base):
    __tablename__ = "setup_archive"

    id = Column(Integer, primary_key=True, index=True)

    # ── Identity ─────────────────────────────────────────────────
    ticker = Column(String, nullable=False, index=True)
    scan_date = Column(String, nullable=False, index=True)   # YYYY-MM-DD
    setup_type = Column(String, nullable=False)               # LPS / REBOUND / BREAKOUT

    # ── Screener scoring snapshot ────────────────────────────────
    tier = Column(String, nullable=False)
    score = Column(Float, nullable=False)

    # ── Structural DNA ───────────────────────────────────────────
    current_price = Column(Float)
    r_level = Column(Float)           # Resistance
    s_level = Column(Float)           # Support
    trigger_price = Column(Float)     # Entry trigger
    base_length = Column(Integer)
    box_width = Column(Float)
    touches = Column(Integer)         # r_touches + s_touches
    r_touches = Column(Integer)
    s_touches = Column(Integer)
    atr_ratio = Column(Float)
    lps_length = Column(Integer)
    breach_days = Column(Integer)
    r_anchor = Column(Integer, nullable=True)
    s_anchor = Column(Integer, nullable=True)
    vol_contraction = Column(Float)
    tightness_ratio = Column(Float)

    # ── Sub-scores (decomposed for regression) ───────────────────
    score_box_tightness = Column(Float, nullable=True)
    score_touch_density = Column(Float, nullable=True)
    score_traversal_quality = Column(Float, nullable=True)  # rail-to-rail two-sidedness reward
    score_atr_squeeze = Column(Float, nullable=True)
    score_lps_tightness = Column(Float, nullable=True)
    score_vol_contraction = Column(Float, nullable=True)
    score_base_age = Column(Float, nullable=True)
    score_uptrend_bonus = Column(Float, nullable=True)
    score_rs_bonus = Column(Float, nullable=True)

    # ── Forward returns (populated by updater) ───────────────────
    triggered = Column(Integer, nullable=True)        # 0/1: did price reach trigger?
    trigger_date = Column(String, nullable=True)      # YYYY-MM-DD
    fwd_return_1d = Column(Float, nullable=True)
    fwd_return_5d = Column(Float, nullable=True)
    fwd_return_10d = Column(Float, nullable=True)
    fwd_return_20d = Column(Float, nullable=True)
    fwd_return_60d = Column(Float, nullable=True)
    mfe_20d = Column(Float, nullable=True)            # Max favorable excursion (20d)
    mae_20d = Column(Float, nullable=True)            # Max adverse excursion (20d)
    mfe_60d = Column(Float, nullable=True)            # Max favorable excursion (60d)
    mae_60d = Column(Float, nullable=True)            # Max adverse excursion (60d)
    mfe_20d_date = Column(String, nullable=True)      # YYYY-MM-DD when MFE 20d high was hit
    mae_20d_date = Column(String, nullable=True)      # YYYY-MM-DD when MAE 20d low was hit
    r_multiple_20d = Column(Float, nullable=True)     # MFE_20d / risk_pct — true reward/risk
    r_multiple_60d = Column(Float, nullable=True)
    trigger_volume_ratio = Column(Float, nullable=True)  # vol_on_trigger_day / Vol_50_at_scan

    # ── Elapsed-window outcome (window-agnostic edge metric) ─────
    # Measured over min(bars_elapsed, 60) forward bars, recomputed every run as
    # the window grows — NOT gated on a full 20/60. Lets the backtest harness read
    # an unbiased edge TODAY instead of "no mature data; wait months". Computed by
    # the single source of truth core/archive/outcomes.py.
    mfe_to_date = Column(Float, nullable=True)          # max favorable excursion so far (frac of scan close)
    mae_to_date = Column(Float, nullable=True)          # max adverse  excursion so far (frac of scan close)
    ret_to_date = Column(Float, nullable=True)          # close-to-close return at the last available bar
    bars_to_date = Column(Integer, nullable=True)       # forward bars used (1..60)
    abnormal_ret_to_date = Column(Float, nullable=True) # ret_to_date minus SPY's same-window return (bias control)

    # ── Triple-barrier outcome label (path events + derived win/loss/timeout) ──
    # Anchored to the scan close. Stop = s_level*0.97; targets = entry+2.5*risk
    # and entry*1.15. Raw event timings stored so the label can be re-cut later.
    days_to_trigger = Column(Integer, nullable=True)  # bars from scan to trigger touch (1-based)
    days_to_2_5r = Column(Integer, nullable=True)     # bars to 2.5R profit target (None = never)
    days_to_15pct = Column(Integer, nullable=True)    # bars to +15% profit target (None = never)
    days_to_stop = Column(Integer, nullable=True)     # bars to stop (low <= s_level*0.97; None = never)
    barrier_label = Column(String, nullable=True)     # win / loss / timeout (target-before-stop race)
    win_barrier = Column(String, nullable=True)       # 2.5R / 15pct — which target fired first on a win

    # ── Market context at time of signal ─────────────────────────
    spy_trend = Column(String, nullable=True)         # BULLISH / BEARISH / NEUTRAL
    vix_level = Column(Float, nullable=True)
    sector_etf = Column(String, nullable=True)        # XLK, XLF, XLE, etc.
    sector_trend = Column(String, nullable=True)      # BULLISH / BEARISH / NEUTRAL
    rs_vs_sector_pct = Column(Float, nullable=True)   # stock_return_during_base − sector_return_during_base
    dist_52w_high_pct = Column(Float, nullable=True)  # (current − max_high_252d) / max_high_252d (negative)
    excess_return_6m = Column(Float, nullable=True)   # stock 6m return − SPY 6m return at scan_date
    yearly_return = Column(Float, nullable=True)      # raw YoY return at scan_date (the demoted uptrend-bonus ramp input; model-only column)
    breadth_pct = Column(Float, nullable=True)        # % of universe with Close > SMA_50 on scan_date
    regime_state = Column(String, nullable=True)      # UPTREND / NEUTRAL / UNDER_PRESSURE / CORRECTION
    regime_breadth_50_pct = Column(Float, nullable=True)
    regime_breadth_200_pct = Column(Float, nullable=True)
    regime_distribution_days = Column(Integer, nullable=True)
    regime_spy_above_50 = Column(Integer, nullable=True)
    regime_spy_above_200 = Column(Integer, nullable=True)
    regime_spy_50d_slope_pct = Column(Float, nullable=True)
    regime_qqq_above_50 = Column(Integer, nullable=True)
    regime_qqq_above_200 = Column(Integer, nullable=True)
    regime_qqq_50d_slope_pct = Column(Float, nullable=True)

    # ── Phase A structural detail ────────────────────────────────
    bars_since_bc = Column(Integer, nullable=True)    # Bars from BC (or SC) to scan_date
    descent_length = Column(Integer, nullable=True)   # Bars from BC to AR low (or SC to bounce high)
    phase_d_inner = Column(Integer, nullable=True)    # 1 if a nested (inner) Phase D range exists, else 0
    lps_in_inner = Column(Integer, nullable=True)     # 1 if the scored LPS is rooted in that inner range, else 0
    inner_source = Column(String, nullable=True)       # midpoint | inner_climax: which inner-search origin won
    inner_search_start_bar = Column(Integer, nullable=True)  # df bar where the selected inner search began
    inner_climax_bar = Column(Integer, nullable=True)  # df bar of selected inner climax, when source=inner_climax
    inner_reaction_bar = Column(Integer, nullable=True)  # df bar of selected inner reaction low / mini-AR
    inner_reaction_pct = Column(Float, nullable=True)  # selected inner reaction depth from climax high to AR low
    inner_reaction_bars = Column(Integer, nullable=True)  # bars from selected inner climax to reaction low

    # ── Volume-around-touches signature (Wyckoff no-supply / spring test) ──
    r_touch_vol_z = Column(Float, nullable=True)      # z-score of avg volume at R-touches vs base volume distribution. Negative = no supply, positive = distribution warning.
    s_touch_vol_z = Column(Float, nullable=True)      # z-score of avg volume at S-touches. Positive = spring strength (heavy hands defending), negative = weak support.

    # ── LPS shape & zone detail ──────────────────────────────────
    lps_descent_frac = Column(Float, nullable=True)   # Pair-wise descent fraction across LPS lows (0=rally, 0.5=sideways, 1=clean descent)
    lps_zone_type = Column(String, nullable=True)     # INSIDE / OVERSHOOT_R / UNDERCUT_S — splits LPS quality by structural role
    score_high_proximity = Column(Float, nullable=True)  # 52w-high proximity sub-score (raw points)
    score_breadth_bonus = Column(Float, nullable=True)   # Market-breadth bonus sub-score (raw points)

    # ── VCP progressive-contraction footprint ────────────────────
    contraction_count = Column(Integer, nullable=True)       # number of peak->valley contractions in the base
    contraction_quality = Column(Float, nullable=True)       # [0,1] composite: count + progressive tightening + final tightness
    final_contraction_depth = Column(Float, nullable=True)   # depth of the last (rightmost) contraction, fractional
    contraction_vol_trend = Column(Float, nullable=True)     # [0,1] volume drying up across contractions, lightest at final coil
    score_contraction = Column(Float, nullable=True)         # contraction-quality sub-score (raw points)
    base_median_spread_atr = Column(Float, nullable=True)     # median base spread / ATR snapshot
    base_p80_spread_atr = Column(Float, nullable=True)        # 80th percentile base spread / ATR snapshot
    base_median_spread_pct_box = Column(Float, nullable=True) # median base spread / box height
    base_tight_bar_pct = Column(Float, nullable=True)         # share of base bars with spread <= ATR snapshot

    # ── Ascending support / higher-lows footprint ────────────────
    support_slope_atr = Column(Float, nullable=True)         # ATR-normalized slope of zigzag valley lows (positive = rising support)
    ascending_support_quality = Column(Float, nullable=True) # [0,1] composite: slope ramp + higher-low consistency
    score_ascending_support = Column(Float, nullable=True)   # ascending-support sub-score (raw points)

    # Worked-equilibrium occupancy footprint (raw, no scoring)
    eq_r_touches = Column(Integer, nullable=True)             # R rail touches measured by measure_equilibrium
    eq_s_touches = Column(Integer, nullable=True)             # S rail touches measured by measure_equilibrium
    eq_r_touch_thirds = Column(Integer, nullable=True)        # time-thirds containing an R touch
    eq_s_touch_thirds = Column(Integer, nullable=True)        # time-thirds containing an S touch
    eq_lower_dwell = Column(Float, nullable=True)             # share of closes in lower third of box
    eq_mid_dwell = Column(Float, nullable=True)               # share of closes in middle third of box
    eq_upper_dwell = Column(Float, nullable=True)             # share of closes in upper third of box
    eq_coverage = Column(Float, nullable=True)                # share of occupied vertical box bins

    # ── Gate-margin telemetry (raw, measure-first; plan task 2) ──
    # The elected box against the ACTUAL election gates: the respect band
    # fraction and the dead-space gate's own close-residence dwells (the
    # eq_*_dwell trio above is range-occupancy, a different statistic).
    eq_respect_frac = Column(Float, nullable=True)            # share of bars inside the buffered band
    # Move 1 dark measures (gap-breach Task 3; never-gated, NULL = engine
    # version predates the measure): engagement-basis respect (bounded
    # close-back-inside excursions read as hangs) + deepest excursion in ATR.
    eq_engagement_respect_frac = Column(Float, nullable=True) # respect share on the engagement basis
    eq_max_excursion_atr = Column(Float, nullable=True)       # deepest single-bar excursion beyond the buffered rails (ATR)
    eq_close_lower_dwell = Column(Float, nullable=True)       # gate's close residence, lower third
    eq_close_mid_dwell = Column(Float, nullable=True)         # gate's close residence, middle third
    eq_close_upper_dwell = Column(Float, nullable=True)       # gate's close residence, upper third

    # ── Limb-traversal read (raw, no scoring; v1 measure-first) ──
    # Do the swing limbs travel rail-to-rail, or hang off a rail (dead space)?
    # measure_equilibrium (formerly measure_traversal) — the swing-structural complement to eq_* occupancy.
    trav_n_full_traversals = Column(Integer, nullable=True)   # rail-to-rail swings (round-trip S->R->S = 2)
    trav_n_swings = Column(Integer, nullable=True)            # significant swings after amplitude filtering
    trav_top_dead_space = Column(Float, nullable=True)        # 1 - 75th-pct peak position (dead space below R)
    trav_bottom_dead_space = Column(Float, nullable=True)     # 25th-pct valley position (dead space above S)
    trav_rail_reaches_high = Column(Integer, nullable=True)   # swing peaks reaching the high zone
    trav_rail_reaches_low = Column(Integer, nullable=True)    # swing valleys reaching the low zone
    trav_max_swing_frac = Column(Float, nullable=True)        # largest single limb as a fraction of box height
    trav_last_support_frac = Column(Float, nullable=True)     # time-pos (0..1) of last support touch; low = S abandoned early (descent tail)
    trav_coil_floor_pos = Column(Float, nullable=True)        # box-pos of lowest Low after last S-touch; high = dead band under the late coil

    # ── ADR% absolute-volatility character ──────────────────────
    adr_pct = Column(Float, nullable=True)                    # Average Daily Range % over 20 bars (plain percent)
    score_adr = Column(Float, nullable=True)                  # ADR sub-score (raw points)

    # ── Phase-D scoping layer (descriptive right-most-region bands) ──
    # Read-only measurement: where each region begins + the LPS support band.
    # Dates align with the chart OHLC; archived raw for the fidelity harness.
    scope_phase_a_date = Column(String, nullable=True)  # Phase A (climax/lead-in) start
    scope_phase_b_date = Column(String, nullable=True)  # Phase B (equilibrium body) start
    scope_phase_d_date = Column(String, nullable=True)  # Phase D right-most-region start
    scope_phase_c_date = Column(String, nullable=True)  # Phase C spring marker (UNDERCUT_S only)
    scope_has_mini = Column(Integer, nullable=True)     # 1 if Phase D is an inner mini-consolidation
    scope_confidence = Column(Float, nullable=True)     # [0,1] fraction of regions confidently placed

    # ── Region (bin) features (measure-only: "where am I in the base?") ──
    # Per-region size / price-range / volume character, the D-vs-B comparison,
    # and the Last-Supper stretch of the LPS from the box that birthed it.
    bin_a_bars = Column(Integer, nullable=True)            # climax event (BC/SC -> AR) length in bars
    bin_a_range_pct = Column(Float, nullable=True)         # (maxHigh-minLow)/minLow over Bin A
    bin_a_volume_ratio = Column(Float, nullable=True)      # Bin A mean volume / trailing-50 mean
    bin_b_bars = Column(Integer, nullable=True)            # working base length (= base_length)
    bin_b_range_pct = Column(Float, nullable=True)         # base price range fraction
    bin_b_volume_ratio = Column(Float, nullable=True)      # base mean volume / trailing-50 mean
    # Bin B interior trajectory ("eyes inside the base") — Close-residence CoG over time
    bin_b_cog_end = Column(Float, nullable=True)           # recent CoG (0=floor..1=ceiling): where price sits now
    bin_b_cog_crossings = Column(Integer, nullable=True)   # CoG mid-line crossings (>=2 = two-sided/oscillating range)
    bin_b_cog_rng = Column(Float, nullable=True)           # CoG sweep (max-min): how much box height the center covered
    bin_b_cog_corr = Column(Float, nullable=True)          # corr(position, time): + climbing to R, - sagging to S
    bin_c_present = Column(Integer, nullable=True)          # 1 when a late spring was measured
    bin_c_type = Column(String, nullable=True)              # SPRING
    bin_c_event_date = Column(String, nullable=True)        # low bar date
    bin_c_event_bar = Column(Integer, nullable=True)        # df-positional low/tip bar
    bin_c_undercut_atr = Column(Float, nullable=True)       # Low undercut depth below S, in ATR
    bin_c_recovery_bars = Column(Integer, nullable=True)    # bars until Close recovered back above S
    bin_c_recovery_bar = Column(Integer, nullable=True)     # df-positional Close reclaim bar
    bin_c_time_loc = Column(Float, nullable=True)           # event location inside Bin B (0=start, 1=end)
    bin_c_spring_vol_z = Column(Float, nullable=True)       # event volume z-score vs Bin B volume distribution
    bin_d_bars = Column(Integer, nullable=True)            # Phase D length in bars
    bin_d_start_bar = Column(Integer, nullable=True)        # df-positional Phase D start
    bin_d_range_pct = Column(Float, nullable=True)         # Phase D price range fraction
    bin_d_volume_ratio = Column(Float, nullable=True)      # Phase D mean volume / trailing-50 mean
    bin_d_support_slope_atr = Column(Float, nullable=True) # Phase D swing-low slope, ATR-normalized
    bin_d_higher_low_frac = Column(Float, nullable=True)   # Phase D consecutive valley pairs that step up
    bin_d_ascending_support_quality = Column(Float, nullable=True) # Phase D rising-support quality
    bin_d_boundary_source = Column(String, nullable=True)  # support_tests | inner_box | v_tip | lps
    phase_d_evidence_json = Column(Text, nullable=True)    # JSON detail for Phase-D boundary evidence
    bin_lps_bars = Column(Integer, nullable=True)          # LPS window length in bars
    lps_position_in_box = Column(Float, nullable=True)     # (lps_low - S)/(R - S): 0=floor, 1=ceiling
    bin_d_vs_b_range_ratio = Column(Float, nullable=True)  # Bin D range / Bin B range (<1 = tighter Phase D)
    bin_d_vs_b_volume_ratio = Column(Float, nullable=True) # Bin D vol / Bin B vol (<1 = quieter Phase D)
    bin_d_vs_b_support_quality_delta = Column(Float, nullable=True) # Phase D support quality - full-base support quality
    lps_stretch_atr = Column(Float, nullable=True)         # (lps_low - R)/ATR: how far the LPS sits above the box ceiling
    lps_stretch_box = Column(Float, nullable=True)         # (lps_low - R)/(R - S): same, in box-heights (Last-Supper risk)
    lps_swing_type = Column(String, nullable=True)         # terminal_valley / shelf / clean downswing / undercut rebound
    lps_anchor_bar = Column(Integer, nullable=True)        # df-positional anchor high for the elected LPS swing
    lps_anchor_date = Column(String, nullable=True)
    lps_low_bar = Column(Integer, nullable=True)           # df-positional elected LPS valley
    lps_low_date = Column(String, nullable=True)
    lps_swing_depth_pct = Column(Float, nullable=True)     # (anchor_high - lps_low) / anchor_high
    lps_swing_depth_atr = Column(Float, nullable=True)     # same swing depth in ATR units
    lps_swing_depth_box = Column(Float, nullable=True)     # same swing depth in active box-heights
    last_supper_pullback_from_extension_pct = Column(Float, nullable=True) # anchor-high to LPS-low pullback fraction
    last_supper_source_box_age = Column(Integer, nullable=True)            # bars since price first left the source box
    last_supper_reclaim_quality = Column(Float, nullable=True)             # [0,1] cleanup/reclaim quality after the LPS low
    # Pivot-anchored over-extension (2026-07-26): siblings of the three above,
    # anchored on the run-up's terminal PIVOT rather than the LPS window's first
    # bar. Measure-only; added alongside so the existing columns stay comparable.
    last_supper_pivot_stretch_atr = Column(Float, nullable=True)           # (run-up pivot high - R) / ATR
    last_supper_pivot_stretch_box = Column(Float, nullable=True)           # (run-up pivot high - R) / box height
    last_supper_pullback_from_pivot_pct = Column(Float, nullable=True)     # pivot-high to LPS-low pullback fraction
    last_supper_pivot_bars_back = Column(Integer, nullable=True)           # bars from the run-up pivot to the LPS low

    # ── Minervini Stage-2 trend template (raw context, no scoring) ──
    stage2_ma_stack_pass = Column(Integer, nullable=True)       # 1 if price > SMA50 > SMA150 > SMA200
    stage2_ma200_slope_1m_pct = Column(Float, nullable=True)    # SMA200 % change over ~21 bars
    stage2_52w_low_pct = Column(Float, nullable=True)           # fraction above the 52-week low
    stage2_trend_pass_count = Column(Integer, nullable=True)    # how many of the 7 trend-template criteria pass
    stage2_trend_pass = Column(Integer, nullable=True)          # 1 if all 7 pass

    # ── HTF (higher-timeframe) context — same Trend+Box engine, weekly/monthly ──
    htf_w_stage2 = Column(Integer, nullable=True)        # weekly price > rising 30-wk MA (Stage-2)
    htf_w_trend_state = Column(String, nullable=True)    # up / neutral / down / unknown
    htf_w_in_consol = Column(Integer, nullable=True)     # a worked weekly box exists now
    htf_w_phase = Column(String, nullable=True)          # B / C / D
    htf_w_box_r = Column(Float, nullable=True)
    htf_w_box_s = Column(Float, nullable=True)
    htf_w_box_width = Column(Float, nullable=True)
    htf_w_reaccum = Column(Integer, nullable=True)       # Stage-2 uptrend AND consolidating (re-accumulation)
    htf_w_daily_nested = Column(Integer, nullable=True)  # daily box sits inside the weekly box
    htf_m_stage2 = Column(Integer, nullable=True)
    htf_m_trend_state = Column(String, nullable=True)
    htf_m_in_consol = Column(Integer, nullable=True)
    htf_m_phase = Column(String, nullable=True)
    htf_m_box_r = Column(Float, nullable=True)
    htf_m_box_s = Column(Float, nullable=True)
    htf_m_box_width = Column(Float, nullable=True)
    htf_m_reaccum = Column(Integer, nullable=True)
    htf_m_daily_nested = Column(Integer, nullable=True)

    # ── Event Map tape summary — measure-only, flag-gated (EVENT_MAP_ENABLED) ──
    # Owning declaration (names / SQL types / row extraction) lives in
    # engine_alpha/structure/event_map.py (EVENT_MAP_COLUMN_SQL); a test keeps this model
    # in sync. MODEL-ONLY adds (the engine_config_version precedent): deliberately
    # NOT in the writer's _NEW_COLUMNS or startup._MIGRATIONS — the Track B
    # model-diff auto-migration and the writer's model-derived pass ADD them.
    # NULL means "not measured" (flag off / pre-Event-Map rows), never zero.
    event_map_n_swings = Column(Integer, nullable=True)       # committed + in-progress swings, whole frame
    event_map_pre_box_trend = Column(String, nullable=True)   # pre-box view trend_state
    event_map_n_labels = Column(Integer, nullable=True)       # role labels over the elected bricks
    event_map_n_committed = Column(Integer, nullable=True)    # labels knowable at scan close
    # Rail-episode substrate (Event Map program Task 10): typed scalars the
    # TA-score session may grade + the ONE compact audit tape. Explicit zeros
    # are evidence (the junk separator IS zero); NULL only = never measured.
    event_map_completed_s = Column(Integer, nullable=True)      # completed support tests (as-of)
    event_map_completed_r = Column(Integer, nullable=True)      # completed resistance rejections
    event_map_alternations = Column(Integer, nullable=True)     # completed-episode rail changes
    event_map_terminal_posture = Column(Integer, nullable=True)  # 0/1 pre-breakout R engagement
    event_map_terminal_drift = Column(Integer, nullable=True)    # 0/1 open S drift at the edge
    event_map_story_admitted = Column(Integer, nullable=True)    # 0/1 ruled form (2026-07-25)
    event_map_episode_nan_bars = Column(Integer, nullable=True)  # readability companion
    event_map_zone_coverage = Column(Float, nullable=True)       # geometry companion: 2*tol/(R-S) (2026-08-10)
    event_map_episode_profile = Column(String, nullable=True)    # the sentence "S+ S+ S+ R^"
    event_map_episodes = Column(String, nullable=True)           # compact JSON tape (dates)

    # ── Technical Analysis Grade v2 family — flag-gated (TA_SCORE_V2) ────────
    # Owning declaration in engine_alpha/scoring/scoring.py (TA_GRADE_COLUMN_SQL
    # + ta_grade_archive_values — the ONE extraction both writers splat).
    # MODEL-ONLY schema adds (AP-7): the Track B auto-migration and the
    # writer's model-derived pass ADD them; never hand-list in _NEW_COLUMNS /
    # _MIGRATIONS. NULL = flag-off / pre-flip rows FOREVER (no backfill, ever);
    # both floats are FULL precision — rounding is display-only.
    ta_grade = Column(Float, nullable=True)       # the 0-100 (post-warnings)
    ta_grade_raw = Column(Float, nullable=True)   # the raw affine sum
    # The three setup grades — closing the setup_quality scored-but-invisible
    # breach (on the wire since 2026-07-18, never archived). Populated on every
    # fire whose narrative produced a read; NULL = the narrative abstained.
    # setup_chronology is a closed set {intact, partial, absent}: refused at
    # write in ta_grade_archive_values (the live DB's operative constraint) +
    # the fresh-DB CHECK below.
    setup_completeness = Column(Integer, nullable=True)       # 0..4 canonical pieces
    setup_chronology = Column(String, nullable=True)          # intact | partial | absent
    setup_upthrust_terminal = Column(Integer, nullable=True)  # 0/1 terminal upthrust
    # Per-term points (registry column = score_ + key, the house convention).
    # score_setup_quality is a v1 term scored on EVERY row (NULL = pre-add
    # history only); the five below are flag-gated (NULL = flag-off/pre-flip;
    # caps start 0 shape-only, so flag-on values are 0.0 until the A/B).
    score_setup_quality = Column(Float, nullable=True)
    score_spring = Column(Float, nullable=True)
    score_story_s_tests = Column(Float, nullable=True)
    score_story_r_rejections = Column(Float, nullable=True)
    score_story_alternations = Column(Float, nullable=True)
    score_story_terminal_posture = Column(Float, nullable=True)
    # Wave-1 charter measurements (task 7) — RAW measure-first columns,
    # fires-only inside TA_SCORE_V2. NULL = absent (below the minimum-step
    # floor / insufficient window / all-absent ingredients) — never zero.
    # lps_window_classification is a closed set {rising_march, turned,
    # clean_dip, mixed}: refused at write in ta_grade_archive_values + the
    # fresh-DB CHECK below.
    lps_shrink_frac = Column(Float, nullable=True)           # [0,1] tests shrink test-over-test
    lps_window_classification = Column(String, nullable=True)  # the elected window's descent read
    story_richness_rate = Column(Float, nullable=True)       # [0,1] story events per bar, bounded
    # Wave-2 (task 8): the bounded box-walk pair. count NULL = labelling
    # refused (the elected base itself counts as 1, never 0); ratio NULL =
    # no predecessor base in the covering up-segment (never 1, never inf).
    trend_base_count = Column(Integer, nullable=True)        # Minervini base # in the current up-segment, capped
    inter_base_width_ratio = Column(Float, nullable=True)    # elected width / most-recent predecessor width
    # Fired tags (task 10): the resolved chip verdicts, compact JSON array of
    # {id, detail} — ids are a closed set (taxonomy.TAG_IDS) refused at write
    # in ta_grade_archive_values. NULL = flag-off/pre-flip; '[]' = resolved,
    # nothing fired (absent vs empty are DIFFERENT states).
    fired_tags = Column(String, nullable=True)

    # ── Election-trace evidence — flag-gated (ELECTION_TRACE_EXPORT_ENABLED) ──
    # Owning declaration in engine_alpha/structure/trace_export.py (ELECTION_TRACE_COLUMN_SQL);
    # same MODEL-ONLY convention as the event_map family above. The compact
    # date-anchored export the operator was shown, as JSON text — NULL means
    # never captured, and pre-flip NULLs are never backfilled (a trace
    # re-derived under a rotated engine is not the evidence he graded).
    election_trace = Column(String, nullable=True)

    # ── Strategy read — flag-gated (STRATEGY_READ_ENABLED), measure-first ──
    # Owning declaration in engine_alpha/structure/strategy_read.py; raw campaign
    # context, never gated, never scored; NULL = never measured.
    strategy_correction_depth_pct = Column(Float, nullable=True)
    strategy_floor_above_ar = Column(Integer, nullable=True)

    # ── Power-Play species family — flag-gated (dark), measure-first ──
    # Owning declaration in engine_alpha/structure/power_play.py
    # (POWER_PLAY_COLUMN_SQL); MODEL-ONLY adds (AP-7). NULL = never evaluated;
    # "watched but refused" is the closed-set pp_state (fresh-DB CHECK below;
    # the live DB's operative constraint is the write-time refusal in
    # power_play_archive_values). Anchor-family from birth: the pp_* numerics
    # join the PHASE_A_ANCHOR_FEATURES epoch partition in core/archive/analyze.
    pp_state = Column(String, nullable=True)
    pp_clock = Column(Integer, nullable=True)
    pp_climax_date = Column(String, nullable=True)
    pp_ar_date = Column(String, nullable=True)
    pp_pole_gain = Column(Float, nullable=True)
    pp_shelf_start_date = Column(String, nullable=True)
    pp_shelf_end_date = Column(String, nullable=True)
    pp_shelf_bars = Column(Integer, nullable=True)
    pp_lower_third_bars = Column(Integer, nullable=True)
    pp_zone_coverage = Column(Float, nullable=True)
    pp_zone_collided = Column(Integer, nullable=True)

    # ── Advisory metadata (Lane E) — GRADED context, NOT a veto, NOT scored ──
    # Flag-gated (FUNDAMENTALS_ENABLED / RS_LINE_ENABLED / SECTOR_RANKING_ENABLED),
    # all default OFF -> these stay NULL and the engine output is byte-identical.
    # Surfaced only as advisory tag chips; geometry remains the only veto, missing
    # data -> no chip (never a penalty). Fundamentals are point-in-time (filing-lag
    # gated, see core/fundamentals/metrics.py) so no future quarter leaks.
    fund_eps_growth_yoy = Column(Float, nullable=True)      # latest-available qtr EPS YoY (signed fraction)
    fund_sales_growth_yoy = Column(Float, nullable=True)    # latest-available qtr revenue YoY (signed fraction)
    fund_eps_growth_accel = Column(Float, nullable=True)    # EPS-growth acceleration (latest YoY - prior YoY)
    fund_earnings_surprise = Column(Float, nullable=True)   # most-recent-available earnings surprise (signed fraction)
    days_to_earnings = Column(Integer, nullable=True)       # calendar days to next earnings (forward warning chip)
    rs_rating = Column(Float, nullable=True)                # in-house RS rating: universe percentile (0..100) of trailing return
    rs_line_latest = Column(Float, nullable=True)           # latest stock/SPY RS-line ratio
    rs_line_new_high = Column(Integer, nullable=True)       # 1 if the RS line is at a trailing new high (leadership tell)
    sector_rank_pct = Column(Float, nullable=True)          # setup's SPDR-sector composite RS percentile (scan-wide)
    sector_rank_pos = Column(Integer, nullable=True)        # setup's sector rank position (1 = strongest sector this scan)

    # ── Engine provenance (frozen-config reproducibility) ────────
    # sha256 of the frozen engine-config manifest (engine_alpha/freeze/manifest.py) that
    # produced this row. Lets a freeze + backtest trace any signal to the exact
    # config version and detect silent drift. Nullable: pre-existing rows have
    # no stamp. Pure provenance — never a computed engine field.
    engine_config_version = Column(String, nullable=True)
    # The electing pool's closed-set provenance (strict / rescued / band /
    # story) — Event Map program Task 11. Stamped on every fire by BOTH
    # writers; NULL only on pre-provenance rows. The rescued cohort's own
    # forward returns are how the operator later judges whether a rescue
    # tier earns its keep. Pure provenance — never a computed engine field.
    elected_pool = Column(String, nullable=True)
    # A story election's admitting sentence (the pool's own evidence at the
    # consultation basis; NULL for ordinary elections). The event_map_*
    # substrate reads the ELECTED geometry — a different basis that may
    # legally disagree; this column is what the rescue was judged on.
    story_admission_profile = Column(String, nullable=True)

    # ── Manual curation (human-in-the-loop) ──────────────────────
    quality_label = Column(String, nullable=True)     # perfect / good / noise / miss
    notes = Column(Text, nullable=True)
    source = Column(String, default="screener")       # screener / seed / manual
    # Which universe this setup belongs to: us_equities (US stocks) / us_sectors /
    # commodities_etf. Part of the identity key so the same symbol can be archived
    # independently per universe on one date. NOT NULL + server default keeps every
    # pre-existing row valid (they backfill to us_equities); the CHECK keeps the set
    # closed so a typo can't fork the identity space.
    universe_type = Column(String, nullable=False, server_default="us_equities")

    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", "universe_type", name="uq_ticker_scan_date_universe"),
        CheckConstraint(
            "universe_type IN ('us_equities', 'us_sectors', 'commodities_etf')",
            name="ck_setup_archive_universe_type",
        ),
        # The universe_type precedent applied to the electing-pool provenance:
        # the closed set is enforced on every FRESH create_all database (SQLite
        # cannot retrofit a table-level CHECK via the ADD COLUMN migration
        # path, so the existing live DB is guarded by the write-time assertion
        # at the single stamping point — bricks._pool_label).
        CheckConstraint(
            "elected_pool IS NULL OR "
            "elected_pool IN ('strict', 'rescued', 'band', 'story')",
            name="ck_setup_archive_elected_pool",
        ),
        # Same precedent for the setup chronology grade: fresh-DB defence
        # only (the ADD COLUMN path strips CHECKs); the live DB's operative
        # constraint is the write-time refusal in ta_grade_archive_values.
        CheckConstraint(
            "setup_chronology IS NULL OR "
            "setup_chronology IN ('intact', 'partial', 'absent')",
            name="ck_setup_archive_setup_chronology",
        ),
        CheckConstraint(
            "lps_window_classification IS NULL OR "
            "lps_window_classification IN "
            "('rising_march', 'turned', 'clean_dip', 'mixed')",
            name="ck_setup_archive_lps_window_classification",
        ),
        # Power-Play species state (program Task 7): fresh-DB defence only
        # (the ADD COLUMN path strips CHECKs); the live DB's operative
        # constraint is the write-time refusal in power_play_archive_values.
        CheckConstraint(
            "pp_state IS NULL OR "
            "pp_state IN ('refused_clock', 'refused_occupancy', "
            "'refused_story', 'admitted_dark')",
            name="ck_setup_archive_pp_state",
        ),
        Index("ix_setup_archive_universe_type", "universe_type"),
    )


class NearMissArchive(Base):
    """The near-miss lane's cohort table (near-miss lane Task 9) — one row
    per RULED one-leg-narrow refusal EPISODE (operator ruling 2026-07-26,
    docs/near_miss_lane_2026-07.md §5: R-EPISODE recurrence — one row per
    framing identity, re-observations bump the counters, never the record).

    A DEDICATED table by design: setup_archive is the FIRE population (NOT
    NULL tier/score, every consumer treats it as picks) — one forgotten
    filter on a shared table would poison the edge record forever. A
    near-miss NEVER scores, never fires, never enters the picks.

    NULL discipline: margins are NOT NULL for every leg the completion
    measured (all fourteen on a completed vector); ``nm_window`` is NULL
    when the floor was never consulted (the outer seam pre-gates it).
    Outcome columns are NULL until the Task-10 maturation pass fills them;
    ``would_be_score``/``would_be_tier`` ship NULL-until-measured (a refused
    framing has no election context to score — the ledger records this
    fallback). A re-ruling PARTITIONS by (engine_config_version,
    lane_ruleset); it never reinterprets old rows.
    """
    __tablename__ = "near_miss_archive"

    id = Column(Integer, primary_key=True, index=True)

    # ── Identity (the Task-2 date-anchored framing key + universe) ──
    ticker = Column(String, nullable=False, index=True)
    universe_type = Column(String, nullable=False, server_default="us_equities")
    r_level = Column(Float, nullable=False)            # 4dp rail convention
    s_level = Column(Float, nullable=False)
    r_anchor_date = Column(String, nullable=False)     # YYYY-MM-DD
    s_anchor_date = Column(String, nullable=False)

    # ── R-EPISODE recurrence (first refusal anchors the forward clock) ──
    first_seen = Column(String, nullable=False, index=True)   # YYYY-MM-DD
    last_seen = Column(String, nullable=False)
    nights_seen = Column(Integer, nullable=False, server_default="1")
    fired_first_night = Column(Integer, nullable=False)       # 0/1
    fired_any_night = Column(Integer, nullable=False)         # 0/1, OR-updated

    # ── Ruling + provenance stamps ──
    pool = Column(String, nullable=False)              # strict / rescued / band
    kill_stage = Column(String, nullable=False)        # the cascade's kill leg
    failing_leg = Column(String, nullable=False)       # THE ruled coarse leg
    lane_ruleset = Column(String, nullable=False)      # e.g. 2026-07-26.A
    engine_config_version = Column(String, nullable=False)

    # ── The margin vector at FIRST refusal (native quanta, signed) ──
    judged_n = Column(Integer, nullable=False)
    window_start_date = Column(String, nullable=False)
    window_end_date = Column(String, nullable=False)
    nm_width = Column(Float, nullable=False)
    nm_window = Column(Integer, nullable=True)         # NULL = never consulted
    nm_respect_share = Column(Integer, nullable=False)
    nm_respect_run = Column(Integer, nullable=False)
    nm_crash = Column(Float, nullable=False)
    nm_r_touches = Column(Integer, nullable=False)
    nm_s_touches = Column(Integer, nullable=False)
    nm_r_touch_thirds = Column(Integer, nullable=False)
    nm_s_touch_thirds = Column(Integer, nullable=False)
    nm_lower_dwell = Column(Integer, nullable=False)
    nm_upper_dwell = Column(Integer, nullable=False)
    nm_mid_dwell = Column(Integer, nullable=False)
    nm_coverage = Column(Integer, nullable=False)
    nm_traversal_count = Column(Integer, nullable=False)
    nm_traversal_density = Column(Float, nullable=False)

    # ── Episode evidence + outcome substrate at refusal time ──
    episode_profile = Column(String, nullable=True)    # the rail sentence
    would_be_trigger = Column(Float, nullable=False)   # breakout over the box's R
    scan_close = Column(Float, nullable=False)         # scan-time price scale
    would_be_score = Column(Float, nullable=True)      # NULL-until-measured
    would_be_tier = Column(String, nullable=True)      # NULL-until-measured

    # ── Forward outcomes (Task-10 maturation pass; core/archive/outcomes.py) ──
    triggered = Column(Integer, nullable=True)
    trigger_date = Column(String, nullable=True)
    mfe_to_date = Column(Float, nullable=True)
    mae_to_date = Column(Float, nullable=True)
    ret_to_date = Column(Float, nullable=True)
    bars_to_date = Column(Integer, nullable=True)
    abnormal_ret_to_date = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticker", "universe_type", "r_level", "s_level",
                         "r_anchor_date", "s_anchor_date",
                         name="uq_near_miss_framing_identity"),
        # EC-19: closed-set label columns get the universe_type treatment —
        # fresh-DB CHECK here, the write-time assertion at the single
        # stamping point (near_miss_writer._failing_leg_label), and the
        # archive-layer test. Vocabulary = the RULED T-COARSE-8 taxonomy
        # (box_gates.GATE_LEGS stages + the occupancy family collapse).
        CheckConstraint(
            "failing_leg IN ('width', 'window', 'respect_share', "
            "'respect_run', 'crash', 'occupancy', 'traversal_count', "
            "'traversal_density')",
            name="ck_near_miss_failing_leg",
        ),
        CheckConstraint(
            "pool IN ('strict', 'rescued', 'band')",
            name="ck_near_miss_pool",
        ),
        Index("ix_near_miss_identity", "ticker", "first_seen"),
    )


# ─────────────────────────────────────────────────────────────────
# Sector ETF mapping (ticker → SPDR sector ETF)
# ─────────────────────────────────────────────────────────────────
# Uses Yahoo Finance sector data to map to the SPDR sector ETF family.

_SECTOR_TO_ETF = {
    "Technology":           "XLK",
    "Healthcare":           "XLV",
    "Financial Services":   "XLF",
    "Financials":           "XLF",
    "Consumer Cyclical":    "XLY",
    "Consumer Defensive":   "XLP",
    "Communication Services": "XLC",
    "Industrials":          "XLI",
    "Energy":               "XLE",
    "Utilities":            "XLU",
    "Real Estate":          "XLRE",
    "Basic Materials":      "XLB",
}


_SECTOR_INFO_TIMEOUT_S = 12  # hard wall-clock bound for the (untimed) .info scrape


def get_sector_etf(ticker: str) -> str | None:
    """Resolve a ticker to its SPDR sector ETF using yfinance.

    Returns the ETF symbol (e.g. 'XLK') or None on failure OR an unmapped
    sector — callers that must tell those apart (the writer's persistent
    cache) use resolve_sector_etf instead.
    """
    _ok, etf = resolve_sector_etf(ticker)
    return etf or None


def resolve_sector_etf(ticker: str) -> tuple[bool, str]:
    """Failure-distinguishing sector-ETF lookup: (ok, etf).

    ok=False on exception/timeout (transient — retry later, never cache);
    ok=True with etf == "" means the lookup COMPLETED and the sector simply
    has no SPDR mapping (safe to cache forever).

    Hard-bounded with a daemon thread: yfinance's ``.info`` makes an untimed
    page scrape that routinely hangs for tens of seconds or wedges entirely.
    The archive writer also caches the result to disk so this is only hit for
    tickers it has never resolved before.
    """
    import threading

    holder: dict = {}

    def _run():
        holder["r"] = _sector_etf_impl(ticker)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_SECTOR_INFO_TIMEOUT_S)
    r = holder.get("r")  # missing key = timeout
    if r is None:
        return False, ""
    return True, r


def _sector_etf_impl(ticker: str) -> str | None:
    # "" = completed lookup, sector unmapped; None = exception (retryable).
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "")
        return _SECTOR_TO_ETF.get(sector, "")
    except Exception:
        return None


_MARKET_CONTEXT_TIMEOUT_S = 45  # hard wall-clock bound for the SPY+VIX fetch


def get_market_context(scan_date: str) -> dict:
    """Fetch SPY trend and VIX level for a given date.

    Hard-bounded with a daemon thread: yfinance's per-request ``timeout`` is
    unreliable, and a hung SPY/VIX download here would block the whole screener
    subprocess from finishing — which is what gatekeeps the webapp's scan from
    ever surfacing results. On timeout we return an empty context and move on;
    market context is non-critical archive metadata, never worth a hang.
    """
    import threading

    holder: dict = {}

    def _run():
        holder["r"] = _market_context_impl(scan_date)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_MARKET_CONTEXT_TIMEOUT_S)
    return holder.get("r", {"spy_trend": None, "vix_level": None})


def _history_window(symbol: str, start, end):
    """One ``Ticker.history`` fetch over ``[start, end)``.

    NOT ``yf.download``: its results round-trip through module-level globals
    (``yfinance.shared._DFS``) that collide when two FastAPI threadpool requests
    fetch at once, returning one symbol's frame under another's label. These
    readers are reachable from the manual-add route, so they take the same
    per-instance surface ``providers.daily_candles`` was migrated to. The twin
    in ``core/pipeline/providers.py`` mirrors this helper; the pair is pinned by
    tests/test_provider_capabilities.py. ``auto_adjust=True`` preserves
    ``download``'s adjusted-close default the SMA readers were calibrated
    against, and the tz-aware index ``history`` returns is stripped so the
    tz-naive ``scan_date`` masks below keep working.
    """
    import pandas as pd
    import yfinance as yf

    frame = yf.Ticker(symbol).history(
        start=pd.Timestamp(start).strftime("%Y-%m-%d"),
        end=pd.Timestamp(end).strftime("%Y-%m-%d"),
        interval="1d", auto_adjust=True, actions=False,
    )
    if frame is None:
        return pd.DataFrame()
    if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
        frame.columns = frame.columns.get_level_values(-1)
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_localize(None)
    return frame


def _market_context_impl(scan_date: str) -> dict:
    """Actual SPY-trend + VIX fetch. Returns {'spy_trend', 'vix_level'}."""
    import pandas as pd

    result = {"spy_trend": None, "vix_level": None}
    try:
        end = pd.Timestamp(scan_date) + pd.Timedelta(days=5)
        # SMA-200 below needs >=200 trading bars; 250 calendar days is only
        # ~172 trading days, so the rolling(200) was all-NaN and spy_trend
        # silently stayed None. 400 calendar days (~275 trading bars) clears it.
        start = pd.Timestamp(scan_date) - pd.Timedelta(days=400)

        spy = _history_window("SPY", start, end)
        if not spy.empty:
            spy_close = spy["Close"]
            if hasattr(spy_close, "columns"):
                spy_close = spy_close.iloc[:, 0]
            sma200 = spy_close.rolling(200).mean()
            # Use the bar on or just before scan_date
            mask = spy.index <= pd.Timestamp(scan_date)
            if mask.any():
                idx = spy.index[mask][-1]
                price = float(spy_close.loc[idx])
                ma = float(sma200.loc[idx]) if not pd.isna(sma200.loc[idx]) else None
                if ma is not None:
                    if price > ma * 1.02:
                        result["spy_trend"] = "BULLISH"
                    elif price < ma * 0.98:
                        result["spy_trend"] = "BEARISH"
                    else:
                        result["spy_trend"] = "NEUTRAL"

        vix = _history_window("^VIX", pd.Timestamp(scan_date) - pd.Timedelta(days=5), end)
        if not vix.empty:
            vix_close = vix["Close"]
            if hasattr(vix_close, "columns"):
                vix_close = vix_close.iloc[:, 0]
            mask = vix.index <= pd.Timestamp(scan_date)
            if mask.any():
                result["vix_level"] = round(float(vix_close.loc[vix.index[mask][-1]]), 2)
    except Exception:
        pass

    return result


def get_sector_trend(sector_etf: str, scan_date: str) -> str | None:
    """Determine if a sector ETF is in a bullish/bearish/neutral trend on scan_date."""
    import pandas as pd

    try:
        end = pd.Timestamp(scan_date) + pd.Timedelta(days=5)
        start = pd.Timestamp(scan_date) - pd.Timedelta(days=120)

        data = _history_window(sector_etf, start, end)
        if data.empty:
            return None

        close = data["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        sma50 = close.rolling(50).mean()
        mask = data.index <= pd.Timestamp(scan_date)
        if not mask.any():
            return None
        idx = data.index[mask][-1]
        price = float(close.loc[idx])
        ma = float(sma50.loc[idx]) if not pd.isna(sma50.loc[idx]) else None
        if ma is None:
            return None
        if price > ma * 1.01:
            return "BULLISH"
        elif price < ma * 0.99:
            return "BEARISH"
        return "NEUTRAL"
    except Exception:
        return None
