"""Passive market regime and sector health measurements.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

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
# MARKET & SECTOR HEALTH BOARD (position-in-cycle read)
# ============================================================
# An always-on, PASSIVE structural read of every member of the two non-equity
# universes (Sectors + Market, Commodities + ETFs) — including SPY/QQQ — that
# classifies each into one position-in-cycle STATE, so the ETF tabs (which fire
# ZERO tradeable setups by design) become a useful "where is this in its cycle"
# board. It is a SEPARATE, additive read path over the PUBLIC engine_alpha.structure box
# detector + trend/drawdown measures; it never touches the byte-parity-locked
# us_equities firing chain, assigns no score/tier/trigger, and writes nothing to
# the archive. Read LAZILY inside functions (never at module import) to respect
# the backend config-vs-cwd shadowing trap. See core/pipeline/context/health_board.py,
# docs/archive/specs/market-sector-health-board.md, docs/health_board_state_audit.md.
#
# Flipped live per operator request (commit "flip HEALTH_BOARD_ENABLED live"); the
# board still only materializes once an ETF-universe scan regenerates its artifact with
# the health_board section. Flag-off is byte-identical to today (the read path is never
# entered); even flag-ON the read runs ONLY on the non-equities universes
# (universe_type != DEFAULT_UNIVERSE_TYPE), so the byte-parity-locked us_equities chain
# is untouched in both states.
HEALTH_BOARD_ENABLED = True

# A member sitting this far (or more) below its trailing 52-week high reads as a
# DEEP CORRECTION — "fallen well below its base" — and is classified FIRST, before
# any box read (this also absorbs the below-SMA200 cohort the box substrate
# refuses). Negative fraction: -0.30 = 30% below the 52-week high. Deep enough not
# to steal a normal near-highs base (Minervini bases sit within ~25% of highs).
# Starting value for the operator's eyeball flip; tune against the live boards.
HEALTH_DEEP_CORRECTION_DRAWDOWN = -0.30

# The health classifier needs a full trend-template read (>= 200 bars) evaluated
# on the SAME as-of bar the box detector uses (df[:-STRUCTURE_EDGE_SKIP_BARS]), so
# a member is only classifiable when its as-of frame clears this floor. Members
# below it read as "can't read yet" (short history) rather than being mislabeled.
HEALTH_MIN_BARS = 200

# The near-rail zones reuse the calibrated traversal zones (TRAVERSAL_LOW_ZONE /
# TRAVERSAL_HIGH_ZONE) and the touch band (TOUCH_TOLERANCE_ATR) — no new
# geometry knobs — so "near a rail" is expressed in the same scale-invariant
# fraction-of-box / ATR units the firing engine already uses.
