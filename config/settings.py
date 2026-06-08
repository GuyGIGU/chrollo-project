"""
Centralized configuration for the Wyckoff VCP/LPS Screener.
All tunable parameters in one place for easy adjustment.
"""

# ============================================================
# PHASE 1 — UNIVERSE BASELINE FILTERS
# ============================================================
MIN_PRICE = 3.0
MIN_VOLUME_50D = 50_000          # 50-day average daily volume floor
MIN_YEARLY_RETURN = -0.20        # Allows modest drawdowns (v1 used +0.30)

# ============================================================
# PHASE 2 — CONSOLIDATION BASE PARAMETERS
# ============================================================
MIN_BASE_DAYS = 20               # Minimum consolidation length (reject < 20 day chop)
MAX_BOX_WIDTH = 0.18             # (R - S) / S ceiling. A range wider than this is
                                 # not a tradeable tight equilibrium — it's the
                                 # BC->AR extremes, not a worked Phase B box.
                                 # (was 0.25; tightened with the worked-equilibrium
                                 #  rewrite. Doubles as the box-tightness scoring scale.)
CRASH_FILTER_MULT = 0.70         # Floor cap for the box-width-scaled crash filter
EXTENSION_FILTER_MULT = 1.15     # Price above R * this = too extended

# Pivot detection
PIVOT_ORDER_SHORT = 1            # Used when equity window < 40 bars
PIVOT_ORDER_LONG = 2             # Used when equity window >= 40 bars
PIVOT_ORDER_THRESHOLD = 40       # Bar count threshold for switching ORDER

# Dynamic Recursive S/R Scanning (Phase B)
BOUNDARY_ATR_BUFFER = 0.50       # ATR multiplier for boundary respect zone
MAX_CONSECUTIVE_OUTSIDE_DAYS = 10 # Max consecutive bars whose full range pierces the buffered boundary (high>R+buf or low<S-buf). (was 30 — absurdly lenient; tightened with the worked-equilibrium rewrite.)
MIN_BOUNDARY_RESPECT_PCT = 0.80  # At least 80% of bars must keep their full range inside [S-buffer, R+buffer]
TOUCH_TOLERANCE_ATR = 0.5        # ATR multiplier for S/R touch zone (price-level agnostic)
MIDLINE_ATR_BUFFER = 0.3         # Price must move this × ATR from midline before a new cross counts (retained for legacy oscillation scoring; the midline-cross VALIDITY gate is retired in favor of the equilibrium dwell/coverage rule below)

# Worked-equilibrium validity (Phase B) — a candidate Resistance/Support-anchor
# pair is only a real trading range if price RESPECTS, TOUCHES, and ZIGZAGS
# THROUGH both rails CONSTANTLY, with no dead space. These gates replace the old
# "2 touches per side + N midline crosses" rule, which let the widest BC->AR box
# win (dead space below a one-time AR low, or mid-box churn). Measured by
# core.structure.metrics.measure_equilibrium. Starting points — CALIBRATED
# against seed-recall, not hard-coded blind.
EQ_MIN_TOUCHES_PER_RAIL = 3      # >= this many touches within TOUCH_TOLERANCE_ATR of EACH rail
EQ_MIN_TOUCH_THIRDS = 2          # each rail touched in >= this many of 3 time-thirds (constant, not clustered)
EQ_MIN_HALF_DWELL = 0.15         # >= this fraction of closes in BOTH the lower and the upper box third (both halves worked -> no dead space)
EQ_MAX_MID_DWELL = 0.45          # <= this fraction of closes in the middle box third (reject mid-box churn that never works the rails)
EQ_MIN_COVERAGE = 0.80           # >= this fraction of box-height bins must hold real dwell (starved-band / dead-space detector)
EQ_COVERAGE_BINS = 6             # number of equal box-height bins for the coverage measure
EQ_COVERAGE_MIN_FRAC = 0.03      # a bin counts as "filled" if it holds >= this fraction of closes

# Markup-leg qualification (Phase A in find_outer_box)
TREND_MIN_GAIN_PCT = 0.15        # Markup leg must gain >= 15% start->end
TREND_SMA_LOOKBACK = 20          # SMA50 must rise over this lookback to count
TREND_BULLISH_GAP_MAX = 5        # Tolerated consecutive non-bullish bars in a run
TREND_MIN_MOVE_BARS = 20         # Markup leg must span at least this many bars
TREND_PRIOR_LOOKBACK = 100       # Search this far back for prior trough/peak
LOCAL_PEAK_BARS = 30             # Anchor must be the local extremum over this window

# Phase-B ATR window (median over recent N base bars; used when no override is given)
PHASE_B_ATR_WINDOW = 30

# Automatic Reaction validation (required)
AR_MIN_DROP_PCT = 0.05           # Price must drop >= 5% from BC high (or rise from SC low)
AR_MAX_BARS = 15                 # ...within this many bars of the climax

# ============================================================
# PHASE 3 — LPS & BREAKOUT DETECTION
# ============================================================
LPS_DROP_MIN = 0.02              # Minimum pullback depth (2%) — INSIDE / UNDERCUT_S zones
LPS_DROP_MIN_OVERSHOOT_R = 0.04  # Stricter floor for OVERSHOOT_R: require a real backtest, not a shallow drift above R
LPS_DROP_MAX = 0.10              # Maximum pullback depth (10%, staleness cap)
# Graded shape gate: descent_frac is the fraction of pair-wise (i<j) low
# comparisons where the later bar's low is <= the earlier bar's low (perfect
# descent = 1.0, perfect rally = 0.0, ~0.5 for random/sideways). Replaces
# the prior binary argmax-high > argmin-low reject. Setups below this floor
# are still rejected; setups above multiply LPS quality by descent_frac so
# cleaner descents outrank sloppy ones.
LPS_MIN_DESCENT_FRAC = 0.50
LPS_MIN_HIGH_DESCENT_FRAC = 0.45  # Reject obvious rising / higher-high drift inside the LPS window
LPS_MAX_WINDOW_BOX_RANGE = 0.85   # LPS should be a support test, not span most/all of the box
LPS_INSIDE_HIGH_EXTENSION_BOX_MAX = 0.35  # INSIDE LPS cannot launch far above R before testing support
LPS_INSIDE_HIGH_EXTENSION_ATR_MAX = 0.75
LPS_SCAN_OFFSET_MAX = 4         # Today + up to 3 days back (offsets 0..3) — only surface active LPS
LPS_LENGTH_MIN = 2               # Shortest LPS formation (days)
LPS_LENGTH_MAX = 7               # Longest LPS formation (days)
LPS_HOLD_TOLERANCE = 0.97        # Price can't crash > 3% below LPS low

# Zone gate — LPS low must sit in one of 3 zones relative to the box:
#   INSIDE        : S <= low <= R
#   OVERSHOOT_R   : R < low <= R + k*ATR       (backtest of breakout)
#   UNDERCUT_S    : S - k*ATR <= low < S       (spring)
LPS_ZONE_ATR_MULT = 0.5

# Phase-C bin measurement (archive/UI only, never a gate): a spring is a
# meaningful Low undercut of Bin-B support that recovers by Close back inside.
BIN_C_UNDERCUT_ATR_MIN = 0.10
BIN_C_RECOVERY_BARS_MAX = 3
BIN_C_LATE_BOX_FRACTION = 0.50
BIN_C_HELD_TEST_ATR_MAX = 0.50

# Spread rules (core quality signal):
# Final LPS bar range must be < P-percentile of bar ranges across the base.
# 0.5 = median ("less than most bars in consolidation"); 0.33 stricter.
LPS_RANGE_PERCENTILE = 0.5
LPS_SPREAD_MUST_DECLINE = True    # Final bar range <= prior bar range

BREAKOUT_VOLUME_MULT = 1.5       # Volume must exceed 50d avg * this
LPS_VOL_CONTRACTION_MAX = 0.85   # LPS avg volume must be <= 85% of 50d avg

# ============================================================
# PHASE 4 — SCORING & RANKING
# ============================================================
# Tier thresholds — calibrated against the live archive distribution
# (avg ~95, max ~126 under prior weights). With the 52w-high proximity
# bonus added, S sits at roughly the top quartile rather than catching
# 75% of all setups.
TIER_S = 110
TIER_A = 95
TIER_B = 75
TIER_C = 55
# Below TIER_C = Tier D

# S-tier width cap — a wide base, however long or well-touched, is NOT an elite
# setup. Additive scoring can't enforce this (a wide range compensates with
# length/touches), so cap S by box width directly: only a genuinely tight,
# worked range can be S; wider (but still valid) ranges fall to A. This is the
# user's rule — "wide ... getting an S, this is bad." Main calibration knob.
# (Validity already caps box width at MAX_BOX_WIDTH = 0.18.)
S_MAX_BOX_WIDTH = 0.15

# Scoring component maximum points (Total ~ 122 pts)
# Rebalanced with the worked-equilibrium rewrite: base age no longer dominates
# (it used to reward the widest/oldest BC->AR framing — the very bug we fixed),
# and box tightness bites harder so a wide-but-worked range (now drawn correctly)
# lands a tier below an equally-clean tight coil.
SCORE_BASE_AGE = 22             # Wyckoff "cause" (was 35 — trimmed; the box is now a genuinely worked range, so length is a cleaner but less dominant signal)
BASE_AGE_CAP_DAYS = 120         # Saturation point for base-age reward (sqrt-scaled)
SCORE_TOUCH_DENSITY = 25        # 15 base + 10 bonus (was 20)
SCORE_VOL_CONTRACTION = 20      # Volume dry-up (was 10)
SCORE_LPS_TIGHTNESS = 20        # Final candle tightness (was 35)
SCORE_BOX_TIGHTNESS = 22        # Tightness now bites (was 15) — separates a tight coil from a wide-but-clean range
SCORE_ATR_SQUEEZE = 8           # Volatility contraction (was 10)
SCORE_OSCILLATION = 5           # Rail-working quality (closes spend time AT the rails, not clustered mid-box)

# Strong-uptrend bonus — linear ramp from MIN to MAX yearly return.
# Re-accumulation setups inside an established uptrend break out more reliably
# than the same structure on a flat YoY chart, so we elevate them.
MIN_STRONG_YEARLY_RETURN = 0.30
MAX_STRONG_YEARLY_RETURN = 0.60   # Saturation point for the ramp
SCORE_UPTREND_BONUS = 15

# Soft Relative Strength bonus — additive points for stocks outperforming SPY
# over a 6-month lookback. Not a filter; just rewards leadership.
SCORE_RS_BONUS = 15
RS_LOOKBACK_BARS = 126            # ~6 months of trading days
RS_MAX_EXCESS_RETURN = 0.30       # Stock 6m − SPY 6m saturation

# 52-week high proximity bonus — Wyckoff bases that consolidate near recent
# highs break out more reliably than those rebuilding from deep drawdowns.
# Linear ramp from HIGH_PROXIMITY_ZERO_PCT (0 pts) to HIGH_PROXIMITY_FULL_PCT
# (full points). dist_52w_high_pct is negative: e.g. -0.07 = 7% below 52w high.
SCORE_52W_HIGH_PROXIMITY = 8
HIGH_PROXIMITY_FULL_PCT = -0.05   # within 5% of 52w high → full points
HIGH_PROXIMITY_ZERO_PCT = -0.20   # 20%+ below → zero points

# Market-breadth bonus — % of the screened universe with Close > SMA_50 on
# scan_date. Broadcast as a per-run scalar; same value for every setup in a
# run, but rewards setups that form in a tape where the average stock is
# participating (breakouts hold more reliably in broad markets than in
# narrow / mega-cap-only rallies).
SCORE_BREADTH_BONUS = 8
BREADTH_FULL_PCT = 0.60           # 60%+ universe above SMA_50 → full points
BREADTH_ZERO_PCT = 0.35           # below 35% → zero points

# VCP progressive-contraction footprint (the defining Minervini pattern):
# 2-6 pullbacks each tighter than the last (18%→12%→6%), tight final
# contraction. Measured by core.structure.metrics.measure_contractions over the
# base window; scored as a sub-component. Measure-first — scored, not gated.
SCORE_CONTRACTION = 12            # cap for the contraction-quality sub-score
CONTRACTION_IDEAL_MIN = 2         # Minervini: 2-6 contractions, 3-4 typical
CONTRACTION_IDEAL_MAX = 6
CONTRACTION_FINAL_TIGHT_PCT = 0.03  # final contraction ≤ 3% drawdown → full final-tightness
CONTRACTION_FINAL_LOOSE_PCT = 0.12  # final contraction ≥ 12% → zero
CONTRACTION_QUALITY_TAG = 0.70    # quality ≥ this fires the "VCP Coil" tag chip

# Ascending support / higher lows (Minervini "tennis-ball action", Qullamaggie
# "higher lows surfing the rising EMA"): are the swing-low valleys stair-stepping
# UP across the base? Measured by core.structure.metrics.measure_support_slope
# (ATR-normalized least-squares slope through the zigzag valley lows). Bonus-only,
# measure-first — a flat or sagging floor simply earns zero, never penalized.
SCORE_ASCENDING_SUPPORT = 8          # cap for the ascending-support sub-score
ASCENDING_SUPPORT_FULL_SLOPE = 0.10  # valley lows rising ≥ 0.10 ATR/bar → full slope credit
ASCENDING_SUPPORT_TAG = 0.70         # quality ≥ this fires the "Ascending Support" tag chip

# ADR% absolute volatility (Qullamaggie "mover" character): does the stock
# travel enough each day to be worth trading? Bonus-only, measure-first.
ADR_WINDOW = 20        # bars used for the Average Daily Range %
SCORE_ADR = 8          # cap for the ADR sub-score
ADR_FULL_PCT = 5.0     # ADR% >= 5.0 earns full credit (~5% mover threshold)
ADR_TAG = 0.80         # sub-score >= this*cap fires the "High ADR" tag chip

# Volume signature at R/S touches — z-score of touch-bar volume vs the base's
# own volume distribution. Drives the no-supply / spring-strength /
# heavy-resistance tags. Negative z at R = no supply (textbook); positive z at
# S = spring strength; positive z at R = distribution-flavored resistance.
TOUCH_VOL_Z_NO_SUPPLY = -0.30     # r_touch_vol_z below this → "No Supply" tag
TOUCH_VOL_Z_SPRING = 0.30         # s_touch_vol_z above this → "Spring Strength" tag
TOUCH_VOL_Z_HEAVY_R = 0.50        # r_touch_vol_z above this → "Heavy Resistance" warning

# Touch density bonus trigger
TOUCH_BONUS_INDIVIDUAL = 3       # Need >= 3 touches on EACH side
TOUCH_BONUS_TOTAL = 6            # OR >= 6 total touches
TOUCH_BONUS_POINTS = 10          # Bonus awarded (part of the 25 pts max)

# Breakout default scores (when not an LPS)
BREAKOUT_DEFAULT_VOL_CONTRACTION = 0.5
BREAKOUT_DEFAULT_TIGHTNESS = 0.7

# ============================================================
# DATA & CACHING
# ============================================================
# Live archiving — when True, every daily screener run upserts its full output
# (winners AND the setups that later fizzle) into setup_archive with
# source="screener". This is the fuel the calibration/analysis tools need:
# without live non-winners, every outcome metric is biased by the seed gallery.
# Idempotent per (ticker, scan_date); re-running the same day updates in place.
ARCHIVE_LIVE_SCANS = True

CACHE_FILENAME = "market_data_cache_2y.parquet"
CACHE_META_FILENAME = "cache_meta.json"
MARKET_CONTEXT_FILENAME = "market_context.json"
PARQUET_ENGINE = "pyarrow"
PARQUET_COMPRESSION = "zstd"
CACHE_MAX_AGE_HOURS = 12          # Legacy fallback TTL (used only if meta sidecar missing)
DOWNLOAD_PERIOD = "2y"
TICKER_CACHE_MAX_AGE_DAYS = 1     # Refresh the ticker universe CSV daily

# Incremental fetch tuning
TTL_FRESH_HOURS_MARKET = 1        # Re-fetch latest bars if cache is older than this during market hours
TTL_FRESH_HOURS_OFFHOURS = 12     # ...or this outside market hours
FULL_REFRESH_INTERVAL_DAYS = 7    # Force a cold 2y refetch at least weekly
INCREMENTAL_OVERLAP_BDAYS = 5     # Re-download this many business days before last_cached_date for split-probe overlap
INCREMENTAL_MAX_GAP_BDAYS = 10    # Above this gap, fall back to full refetch instead of incremental

# Split-detection probe (defends against yfinance's auto_adjust=True silently rescaling history)
SPLIT_PROBE_SAMPLE_SIZE = 30                 # Number of cached tickers (+ SPY) to probe for split-induced drift
SPLIT_PROBE_DRIFT_THRESHOLD = 0.005          # Ticker-level: ratio (fresh/cached) deviating by > 0.5% on overlap = split
SPLIT_PROBE_UNIVERSE_DRIFT_PCT = 0.02        # If > 2% of probed tickers drift → cold refetch
SPLIT_PROBE_REFERENCE_SYMBOL = "SPY"         # Always included in the probe sample if present in cache

# Market context cache
SPY_SYMBOL = "SPY"                # Stored in the parquet alongside the universe (not screened)
INDEX_SYMBOLS = ["SPY", "QQQ"]    # Market-regime indexes stored with the universe
MARKET_CONTEXT_TTL_HOURS_MARKET = 1
MARKET_CONTEXT_TTL_HOURS_OFFHOURS = 12

# Market-regime state (observability only; not a score/gate)
REGIME_MA_PERIODS = [10, 20, 50, 200]
REGIME_SLOPE_MA_PERIOD = 50
REGIME_SLOPE_LOOKBACK = 10
REGIME_DISTRIBUTION_DAY_DROP = 0.002
REGIME_DISTRIBUTION_DAY_LOOKBACK = 25
REGIME_DISTRIBUTION_DAY_PRESSURE = 5
REGIME_BREADTH_50_HEALTHY = 0.60
REGIME_BREADTH_50_WEAK = 0.40
REGIME_BREADTH_200_HEALTHY = 0.50
REGIME_BREADTH_200_WEAK = 0.35

# ============================================================
# DASHBOARD
# ============================================================
DASHBOARD_CHART_TIERS = ['S', 'A', 'B', 'C', 'D']   # Default: generate chart data for all setups
DASHBOARD_CHART_DAYS = 300           # Max candles shown per chart

# ============================================================
# SCHEDULED WEBAPP SCANS
# ============================================================
# The backend scheduler runs in America/New_York time, after the regular US
# close so yfinance has time to publish the completed daily bar.
SCAN_SCHEDULE_HOUR_ET = 18
SCAN_SCHEDULE_MINUTE_ET = 0
FORWARD_RETURNS_MIN_AGE_DAYS = 5
ALERT_WEBHOOK_URL_ENV = "ALERT_WEBHOOK_URL"
ALERT_ON_ZERO_RESULTS = True
