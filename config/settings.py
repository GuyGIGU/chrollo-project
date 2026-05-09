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

# Automatic Reaction validation (required)
AR_MIN_DROP_PCT = 0.05           # Price must drop >= 5% from BC high (or rise from SC low)
AR_MAX_BARS = 15                 # ...within this many bars of the climax

# ============================================================
# PHASE 3 — LPS & BREAKOUT DETECTION
# ============================================================
LPS_DROP_MIN = 0.02              # Minimum pullback depth (2%)
LPS_DROP_MAX = 0.10              # Maximum pullback depth (10%, staleness cap)
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
CACHE_FILENAME = "market_data_cache_2y.parquet"
PARQUET_ENGINE = "pyarrow"
CACHE_MAX_AGE_HOURS = 12
DOWNLOAD_PERIOD = "2y"
TICKER_CACHE_MAX_AGE_DAYS = 1     # Refresh the ticker universe CSV daily

# ============================================================
# DASHBOARD
# ============================================================
DASHBOARD_CHART_TIERS = ['S', 'A', 'B', 'C', 'D']   # Default: generate chart data for all setups
DASHBOARD_CHART_DAYS = 300           # Max candles shown per chart
