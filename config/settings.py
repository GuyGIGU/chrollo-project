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
MAX_BOX_WIDTH = 0.25             # (R - S) / S ceiling
CRASH_FILTER_MULT = 0.70         # Floor cap for the box-width-scaled crash filter
EXTENSION_FILTER_MULT = 1.15     # Price above R * this = too extended

# Pivot detection
PIVOT_ORDER_SHORT = 1            # Used when equity window < 40 bars
PIVOT_ORDER_LONG = 2             # Used when equity window >= 40 bars
PIVOT_ORDER_THRESHOLD = 40       # Bar count threshold for switching ORDER

# Dynamic Recursive S/R Scanning (Phase B)
BOUNDARY_ATR_BUFFER = 0.50       # ATR multiplier for boundary respect zone
MAX_CONSECUTIVE_OUTSIDE_DAYS = 30 # Max consecutive bars whose full range pierces the buffered boundary (high>R+buf or low<S-buf)
MIN_BOUNDARY_RESPECT_PCT = 0.80  # At least 80% of bars must keep their full range inside [S-buffer, R+buffer]
TOUCH_TOLERANCE_ATR = 0.5        # ATR multiplier for S/R touch zone (price-level agnostic)
MIN_MIDLINE_CROSSES = 3          # Minimum midline oscillations required
MIDLINE_ATR_BUFFER = 0.3         # Price must move this × ATR from midline before a new cross counts

# Markup-leg qualification (Phase A in find_outer_box)
TREND_MIN_GAIN_PCT = 0.15        # Markup leg must gain >= 15% start->end
TREND_SMA_LOOKBACK = 20          # SMA50 must rise over this lookback to count
TREND_BULLISH_GAP_MAX = 5        # Tolerated consecutive non-bullish bars in a run
TREND_MIN_MOVE_BARS = 20         # Markup leg must span at least this many bars
TREND_PRIOR_LOOKBACK = 100       # Search this far back for prior trough/peak
LOCAL_PEAK_BARS = 30             # Anchor must be the local extremum over this window

# Phase-B ATR window (median over recent N base bars; used when no override is given)
PHASE_B_ATR_WINDOW = 30

# Phase-B candidate selection (outer box). When the engine roots the
# consolidation at the EARLIEST valid range start (select="earliest"), it must
# not reach back into a *materially looser* framing just because it begins
# earlier. Among the valid pivot pairs it keeps only those whose combined
# structural quality (tightness + touch density + midline) is at least this
# fraction of the best available pair, then picks the earliest of THOSE. So a
# longer truer base is preferred, but a sparse, ballooning framing that merely
# starts earlier is rejected. 1.0 == strict "best only"; lower == more willing
# to trade a little quality for an earlier (longer) start.
PHASE_B_REACH_QUALITY_FLOOR = 0.75

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
LPS_SCAN_OFFSET_MAX = 4         # Today + up to 3 days back (offsets 0..3) — only surface active LPS
LPS_LENGTH_MIN = 2               # Shortest LPS formation (days)
LPS_LENGTH_MAX = 7               # Longest LPS formation (days)
LPS_HOLD_TOLERANCE = 0.97        # Price can't crash > 3% below LPS low

# Zone gate — LPS low must sit in one of 3 zones relative to the box:
#   INSIDE        : S <= low <= R
#   OVERSHOOT_R   : R < low <= R + k*ATR       (backtest of breakout)
#   UNDERCUT_S    : S - k*ATR <= low < S       (spring)
LPS_ZONE_ATR_MULT = 0.5

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

# Scoring component maximum points (Total ~ 128 pts)
SCORE_BASE_AGE = 35             # Wyckoff "cause" heavily rewarded (was 8)
BASE_AGE_CAP_DAYS = 120         # Saturation point for base-age reward (sqrt-scaled)
SCORE_TOUCH_DENSITY = 25        # 15 base + 10 bonus (was 20)
SCORE_VOL_CONTRACTION = 20      # Volume dry-up (was 10)
SCORE_LPS_TIGHTNESS = 20        # Final candle tightness (was 35)
SCORE_BOX_TIGHTNESS = 15        # Reduced penalty for wide boxes (was 35)
SCORE_ATR_SQUEEZE = 8           # Volatility contraction (was 10)
SCORE_OSCILLATION = 5           # Midline chop quality (was 10)

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
# contraction. Measured by core.structure.consolidation.measure_contractions over the
# base window; scored as a sub-component. Measure-first — scored, not gated.
SCORE_CONTRACTION = 12            # cap for the contraction-quality sub-score
CONTRACTION_IDEAL_MIN = 2         # Minervini: 2-6 contractions, 3-4 typical
CONTRACTION_IDEAL_MAX = 6
CONTRACTION_FINAL_TIGHT_PCT = 0.03  # final contraction ≤ 3% drawdown → full final-tightness
CONTRACTION_FINAL_LOOSE_PCT = 0.12  # final contraction ≥ 12% → zero
CONTRACTION_QUALITY_TAG = 0.70    # quality ≥ this fires the "VCP Coil" tag chip

# Ascending support / higher lows (Minervini "tennis-ball action", Qullamaggie
# "higher lows surfing the rising EMA"): are the swing-low valleys stair-stepping
# UP across the base? Measured by core.structure.consolidation.measure_support_slope
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
MARKET_CONTEXT_TTL_HOURS_MARKET = 1
MARKET_CONTEXT_TTL_HOURS_OFFHOURS = 12

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
