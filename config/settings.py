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

# PIP (Perceptually Important Points) swing skeleton — Phase-2 measure-first wire
# (see core/structure/pip.py, docs/segmentation_research.md). When enabled,
# segment_swings sources its zigzag from the multi-resolution PIP substrate
# instead of fixed-order pivots. segment_swings feeds ONLY the Phase-A OVERLAY
# (resolve_phase_a) in the live path — never R/S/score/tier — so this is
# shadow-canonical-safe (flag-ON shadow stays byte-identical). Default OFF until
# the eyeball + seed-recall gate clears. dist_min = fraction of the window price
# range that counts as a salient turn (scale-free, adapts across lookbacks).
PIP_PIVOTS_ENABLED = False
PIP_PIVOTS_DIST_MIN = 0.03

# Coarse->fine MACRO Phase-A read (pip.macro_bridge_zigzag). The flat wire above
# was eyeball-gated OFF as a wash (fixes some inverted climax->AR overlays,
# creates others — GBTG/PLSE/CGNX, commit d43e7fd); this is the multi-resolution
# retry: source segment_swings' zigzag from the SMALLEST top-K importance prefix
# holding a confirmed climax->AR bridge (interior AR), so late range retests /
# noise dips are not in the skeleton to steal the climax or AR. Independent of
# PIP_PIVOTS_ENABLED (checked FIRST when both are on) and deliberately NOT
# applied to read_market_structure — event labels want the fine skeleton, the
# Phase-A bridge wants the coarse one. Same safe surface as the flat wire:
# feeds ONLY the Phase-A overlay via resolve_phase_a, never R/S/score/tier.
# Default OFF until the eyeball gate clears (tools/phase_a_pip_diff.py).
PIP_MACRO_PHASE_A_ENABLED = False
PIP_MACRO_K_MAX = 24             # refinement cap: finest skeleton size tried
# "True Phase-A root swing" rule (operator, 2026-07-02): a candidate trend-end
# bridge qualifies ONLY if it leads to an actual equilibrium. The read stays
# linear (find where the trend ends first), but the claim is validated by what
# follows. No validated bridge => the macro read ABSTAINS and the calibrated
# order-N read speaks — the merge contract.
# Climax terminality: post-AR highs may poke above the climax by at most this
# fraction of the bridge height (honest range pokes BYD +0.20x / GOOD +0.13x
# pass; pullback-in-trend ATI +0.93x / AXTA +1.79x fails).
PIP_MACRO_MAX_POST_EXCESS = 0.25
PIP_MACRO_MIN_BASE_BARS = MIN_BASE_DAYS  # an "actual equilibrium" needs at least
                                 # what the engine itself calls a minimum base
PIP_MACRO_EQ_FLOOR_FRAC = 0.5    # max breakdown below the AR (spring-tolerant)
PIP_MACRO_EQ_OSC_FRAC = 0.3      # min two-sided traversal (x bridge height)

# Dynamic Recursive S/R Scanning (Phase B)
BOUNDARY_ATR_BUFFER = 0.50       # ATR multiplier for boundary respect zone
MAX_CONSECUTIVE_OUTSIDE_DAYS = 10 # Max consecutive bars whose full range pierces the buffered boundary (high>R+buf or low<S-buf). (was 30 — absurdly lenient; tightened with the worked-equilibrium rewrite.)
MIN_BOUNDARY_RESPECT_PCT = 0.80  # At least 80% of bars must keep their full range inside [S-buffer, R+buffer]
TOUCH_TOLERANCE_ATR = 0.5        # ATR multiplier for S/R touch zone (price-level agnostic)

# Worked-equilibrium validity (Phase B) — a candidate Resistance/Support-anchor
# pair is only a real trading range if price RESPECTS, TOUCHES, and ZIGZAGS
# THROUGH both rails CONSTANTLY, with no dead space. These gates replace the old
# "2 touches per side + N midline crosses" rule, which let the widest BC->AR box
# win (dead space below a one-time AR low, or mid-box churn). Candidate selection
# uses close-residence dwell/coverage; public measure_equilibrium also reports
# High/Low range occupancy for analysis. Starting points are calibrated against
# seed-recall, not hard-coded blind.
EQ_MIN_TOUCHES_PER_RAIL = 3      # >= this many touches within TOUCH_TOLERANCE_ATR of EACH rail
EQ_MIN_TOUCH_THIRDS = 2          # each rail touched in >= this many of 3 time-thirds (constant, not clustered)
EQ_MIN_HALF_DWELL = 0.15         # >= this fraction of closes in BOTH the lower and the upper box third (both halves worked -> no dead space)
EQ_MAX_MID_DWELL = 0.45          # <= this fraction of closes in the middle box third for box-of-record selection
EQ_MIN_COVERAGE = 0.80           # >= this fraction of box-height bins must hold real close dwell (starved-band / dead-space detector)
EQ_COVERAGE_BINS = 6             # number of equal box-height bins for the coverage measure
EQ_COVERAGE_MIN_FRAC = 0.03      # a bin counts as "filled" if it holds >= this fraction of closes

# Limb-traversal read (Phase B) — the swing-structural complement to the
# occupancy gate above. The occupancy gate asks where price resides; this asks
# whether the up/down swing LIMBS of the chop actually travel rail-to-rail
# (S<->R), or hang off one rail and leave dead space (the tell that R/S were
# marked too wide). Swing size is judged as a FRACTION OF BOX HEIGHT, not a bar
# count, so the read adapts to box width (tight boxes have short limbs, wide ones
# long). Measured by core.structure.metrics.measure_traversal. v1 is
# measure-first / archive-only — TRAVERSAL_GATE_ENABLED stays False until the
# live archive proves TRAVERSAL_MIN against forward outcomes / seed-recall.
TRAVERSAL_NOISE_FRAC = 0.15      # a swing < this fraction of box height is chop, merged away
TRAVERSAL_FULL_FRAC = 0.55       # a limb spanning >= this fraction of the box is a real rail-to-rail trip
TRAVERSAL_LOW_ZONE = 0.30        # a swing turn at/below this box fraction "reached" the support side
TRAVERSAL_HIGH_ZONE = 0.70       # a swing turn at/above this box fraction "reached" the resistance side
TRAVERSAL_MIN = 2                # >= this many full traversals = a genuinely two-sided range (crossed and re-crossed)
TRAVERSAL_MIN_DENSITY = 0.08     # >= this share of significant swings must be rail-to-rail. Count alone lets a
                                 # LONG base pass on a few full swings amid a sea of interior chop (BMRN: 5/111
                                 # = 0.045); winners run dense (seed floor ~0.14, median ~0.52). Low density =
                                 # the box is too wide / mis-anchored. 0.08 sits in the empty gap (BMRN/FRPH ~0.04
                                 # vs winner-min 0.14) so it drops the sprawl with margin and clips zero winners.
TRAVERSAL_GATE_ENABLED = True    # v2 LIVE: pool-aware re-anchor gate (winner floor validated = MIN, 2026-06-15)

# Descent-tail gate: a WIDE box whose support rail was abandoned EARLY — price
# left the low rail (last_support_frac <= LSF_MAX, the time-position 0..1 of the
# last support touch) then coiled in DEAD SPACE above it (coil_floor_pos >= CFP_MIN,
# the box-position of the lowest Low after that touch) — is a mis-anchored /
# dead-space framing (CHCT, DGII). Read on the ACTIVE box (the inner box when the
# LPS re-anchored there, else the parent), so a setup with a clean PROMOTABLE inner
# survives (QUAD). TIGHT boxes (box_width <= BASE_AGE_DEADSPACE_WIDTH) are EXEMPT —
# their dead band is small in absolute terms so the tell is a false positive
# (saves the EQIX winner, box_width 0.038). Validated 2026-06-19 (pre + post the
# LPS recall work): drops ZERO firing seed winners; drops ~6/97 universe dead-space
# fires incl. the user's CHCT + DGII. Measured by measure_traversal (metrics.py).
DESCENT_TAIL_GATE_ENABLED = True
DESCENT_TAIL_LSF_MAX = 0.40
DESCENT_TAIL_CFP_MIN = 0.20

# Sign-of-strength (SOS) breakout tolerance for Phase-B validation. A worked
# range whose RIGHT side has already broken out above R and HELD above support —
# a creek-jump then back-up (SOS -> BUEC) — is the setup, not a failed box. The
# legacy respect/occupancy gates measured to the live edge, so they counted that
# breakout as a boundary failure and rejected the range (e.g. NMM: a clean April
# box buried under a sustained May breakout above R, backing up to an early-June
# LPS). Fix: validate the range over its WORKED CAUSE — trim a trailing sustained
# above-R run that holds support before measuring boundary-respect + occupancy.
# No-op unless price has already broken out and held, so in-range setups are
# untouched and the change can only RESCUE SOS-BUEC framings (recall-positive).
# Outer Phase-B only (like the traversal gate); inner boxes are never trimmed.
SOS_TRIM_ENABLED = True
SOS_TRIM_MIN_RUN = 3             # a breakout tail must be >= this many consecutive above-(R+buffer) bars (not a one-bar wick)
SOS_TRIM_MIN_PREFIX_FRAC = 0.30  # the worked cause before the breakout must be >= this fraction of the candidate window

# Markup-leg qualification (Phase A in find_outer_box)
TREND_MIN_GAIN_PCT = 0.15        # Markup leg must gain >= 15% start->end
TREND_MIN_MOVE_BARS = 20         # Markup leg must span at least this many bars
TREND_PRIOR_LOOKBACK = 100       # Search this far back for prior trough/peak
LOCAL_PEAK_BARS = 30             # Anchor must be the local extremum over this window
ROOT_TREND_SMA = 200             # Long-trend MA gate in collect_root_anchors: a root requires
                                 # latest close > this SMA (the Stage-2 / uptrend filter). Daily=200;
                                 # HTF presets scale it (weekly ~30 = Weinstein MA-30, monthly ~10) so
                                 # the rolling mean isn't all-NaN on the shorter resampled frame.

# Phase-B ATR window (median over recent N base bars; used when no override is given)
# FROZEN-CONFIG MANIFEST (Lane A): part of the frozen ATR/volatility frame —
# changing it is a new engine_config_version (re-baseline). See the marked region
# at STRUCTURE_EDGE_SKIP_BARS / STRUCTURE_ATR_SAMPLE_OFFSET below.
PHASE_B_ATR_WINDOW = 30

# Automatic Reaction validation (required)
AR_MIN_DROP_PCT = 0.05           # Price must drop >= 5% from BC high (or rise from SC low)
AR_MAX_BARS = 15                 # ...within this many bars of the climax

# ============================================================
# PHASE 3 — LPS & BREAKOUT DETECTION
# ============================================================
# descent_frac is the fraction of pair-wise (i<j) low comparisons where the later
# bar's low is <= the earlier bar's low (perfect descent = 1.0, perfect rally =
# 0.0, ~0.5 for random/sideways). It is now a PURELY GRADED quality input — it
# multiplies LPS quality so cleaner descents outrank sloppy ones — with NO hard
# floor (both floors retired to 0.0, 2026-06-19).
# Why no floor: a rising-bottom LPS coil is not "chop" — it is ASCENDING SUPPORT
# (gradual rising buyer pressure, the bullish VCP / Minervini pivot), which the
# engine already MEASURES and REWARDS via measure_support_slope ->
# ascending_support_quality -> SCORE_ASCENDING_SUPPORT. A hard descent reject
# double-counted that as a defect while the scorer counts it as a strength.
# Shadow (descent floor 0, pullback 0.40): seed recall 22->27 (+KEYS/MSGS/EWTX/
# NBR/PKE, 0 lost); universe +33 fires (S:17/A:8). The pullback / vol-contraction
# / spread / zone / window-box-range gates + the graded quality still filter.
LPS_MIN_DESCENT_FRAC = 0.0
LPS_MIN_HIGH_DESCENT_FRAC = 0.0
# Operator definition of the LPS swing: measured from the HIGH of the first bar
# to the LOW of the last bar — a "peak that goes down". When enabled, the window
# must START at its peak (first-bar High == window High, within tolerance) AND
# END at its trough (last-bar Low == window Low, within tolerance). This rejects
# the "up-swing LPS": a window that climbs into a LATER peak (peak_not_first) or
# dips to an interior low then RISES into the last bars (trough_not_last — the
# rising_support_shelf shape). Tolerance is a fraction of box height so bar noise
# and RMAX/PLXS-class (last Low ~0.02 box above the min) stay valid. Rejection at
# the candidate level lets the selector re-anchor to a clean peak->trough window
# if one exists, else the setup drops ("re-anchor, else drop").
# NOTE: this intersects the deliberate "ascending support = good VCP pivot"
# decision below (descent floor 0) that recovered KEYS/MSGS/EWTX/NBR/PKE — so it
# ships default-OFF and is gated on a seed-recall measurement before any flip.
LPS_REQUIRE_PEAK_DOWN = False
LPS_PEAK_DOWN_TOL_BOX = 0.10
LPS_MAX_WINDOW_BOX_RANGE = 0.85   # LPS should be a support test, not span most/all of the box
# "Reaction not markup" gate for the rising_support_shelf rescue (default OFF =
# None). The rescue (core/structure/lps.py) re-admits a non-terminal-low window
# whose LOW sits near support, but checks only the low's LOCATION, never the
# window's CHARACTER. A vertical markup that merely LAUNCHED from support (OHI
# 2026-06: +6.6% close-to-close, 0 down-bars, closes at R, elected S-Tier "LPS")
# therefore passes. The genuine ascending-support coils the rescue exists to
# catch are near-FLAT (curated winners DIBS/GRDN/SILC: net close-to-close all
# <= ~+0.7%). When set, a rescued shelf whose net advance
# (last Close - first Close)/box_height exceeds this is rejected as a markup —
# the selector re-anchors to a shorter terminal test if one exists, else drops.
# None = disabled. Set to 0.21 (validated 2026-06-26: seed-recall 0 curated
# winners dropped; live it drops OHI/AEF/NVT/SPCB run-ups + keeps NMAI's gradual
# shelf) — HELD uncommitted for the operator's chart eyeball, revert to None to
# disable (see project_lps_peak_down). Midpoint of winner-max +0.096 and the
# run-up cluster +0.324; SPCB (+0.234) is the lone borderline to eyeball.
LPS_RESCUE_MAX_ADVANCE_BOX = 0.21
LPS_INSIDE_HIGH_EXTENSION_BOX_MAX = 0.35  # INSIDE LPS cannot launch far above R before testing support
LPS_INSIDE_HIGH_EXTENSION_ATR_MAX = 0.75
LPS_SCAN_OFFSET_MAX = 7         # Today + up to 6 days back (offsets 0..6) — last 7 active LPS bars
LPS_LENGTH_MIN = 2               # Shortest LPS formation (days)
LPS_LENGTH_MAX = 7               # Longest LPS formation (days)
LPS_HOLD_TOLERANCE = 0.95        # Price can't crash > 5% below LPS low (was 0.97;
                                 # loosened 2026-06-27 to admit slightly deeper
                                 # tests/springs as still-holding — a loosening,
                                 # so recall can only grow)
LPS_PROFILE_BOX_FRACTION_FLOOR = 0.15  # Profile unit floor: wider boxes get more absolute wiggle room
LPS_PULLBACK_PROFILE_MIN = 0.40        # Min first-bar High -> last-bar Low pullback in profile units.
                                       # 0.65 (the old floor) fought tightness: a tight contracting VCP pivot
                                       # near R has a small high->low span by construction, so genuine clean
                                       # LPS coils (BP pull 0.59, NVMI 0.44 — both descent_frac 1.0) were
                                       # rejected on pullback magnitude alone. Lowered to 0.40 (shadow 2026-06-19):
                                       # seed recall 18->22 (+BP/NVMI/FOSL/NGL, 0 lost); universe +5 fires
                                       # (4 of 5 A/S-tier, the 1 dead-space caught by the descent-tail read).
                                       # The descent + vol-contraction + spread + zone gates still filter junk.
LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R = 1.25
LPS_PULLBACK_PROFILE_MAX = 4.50        # Staleness / too-wide reaction cap in profile units
LPS_TERMINAL_LOW_TOL_PROFILE = 0.10    # Last Low may sit this many profile units above window Low
LPS_SPREAD_MAX_PROFILE_MULT = 1.25     # Any LPS bar spread must stay within this profile multiple
LPS_SPREAD_EXPANSION_MAX_PROFILE = 0.35 # Last spread may widen over prior by this many profile units

# Drawn LPS/Test staircase filter (DISPLAY-ONLY, recall-safe). The screener's
# `_lps_tests` staircase is measure-only — it does NOT elect the active LPS or
# gate firing — but it is what paints the gold support-test bands on the chart.
# Unlike the active election it had no direction/right-side filter, so the
# rising_support_shelf rescue + the descent gates above (deliberately 0.0) leaked
# up-march footprints onto the chart (e.g. NCV Jun 9-15: an 80%-rising shelf
# spanning 83% of the box, starting pre-Phase-D). Draw only footprints whose
# low-descent fraction is at least this (a pure reaction is 1.0, sideways ~0.5,
# an up-swing <0.3) AND that start at/after the right-side floor (spring recovery,
# else V-tip). Separate knob from LPS_MIN_DESCENT_FRAC so the recall-sensitive
# election is untouched. The raw staircase still feeds the Phase-D evidence.
LPS_DRAW_MIN_DESCENT_FRAC = 0.40

# Zone gate — LPS low must sit in one of 3 zones relative to the box:
#   INSIDE        : S <= low <= R
#   OVERSHOOT_R   : R < low <= R + k*ATR       (backtest of breakout)
#   UNDERCUT_S    : S - k*ATR <= low < S       (spring)
LPS_ZONE_ATR_MULT = 0.5

# Phase-C bin measurement (archive/UI only, never a gate). A spring is a PHASE,
# not a one-bar V: a bounded EXCURSION below support that is reclaimed and HELD.
# It can be a clean fast V OR a choppy linger below S before recovering — both
# are valid. We key on the three invariants — genuine penetration, reclaim, and
# HOLD (the reclaim sticks = supply absorbed) — NOT on the shape of the dip.
# Grounded in Wyckoff (Phase C ~1-2 weeks; Spring #2 mild vs Spring #1 / terminal
# shakeout deep; price returns to the range within ~5 sessions; the tell is that
# the reclaim holds) and in real misses (KIDS: 2.1 ATR / 0.55-of-box, 6-bar
# linger — a terminal shakeout the old clean-fast-V template rejected).
BIN_C_UNDERCUT_ATR_MIN = 0.30      # tip Low must dip >= this far below S (a real test, not a touch)
BIN_C_UNDERCUT_ATR_MAX = 3.00      # depth cap, terminal-shakeout tolerant (was 1.5 — too tight, missed deep springs); beyond this it's a breakdown not a spring
BIN_C_UNDERCUT_BOX_MAX = 0.65      # also cap depth as a fraction of box (was 0.35; ~0.55 is a valid deep spring, ~0.8+ breaks the range)
BIN_C_RECOVERY_BARS_MAX = 8        # Close must reclaim S within this many bars of the trough (was 3 — clean fast V only; widened for the linger)
BIN_C_LINGER_BARS_MAX = 12         # the whole below-support episode (first penetration -> reclaim) must be bounded; a spring lingers, a breakdown never ends
BIN_C_HOLD_BARS = 3                # after reclaim, Close must HOLD above S (within tol) for this many bars — the absorption confirmation that rejects poke-and-fail
BIN_C_HOLD_TOL_ATR = 0.50          # one dip up to this far below S during the hold window is tolerated (a secondary test); a sustained close-below is not
# Significance — the user's "it's not a simple bar breach and recovery". A spring
# is EITHER a visible clean-V dip (deep enough on its own) OR a genuine multi-bar
# struggle below support (a shallower undercut that lingers). A trivial one-bar
# wick a fraction of an ATR below S that snaps back is neither — it's noise, not
# Phase C. (Calibrated to the live split: shallow-fast pokes ran <=0.7 ATR, real
# springs >=0.8 ATR or multi-bar.)
BIN_C_SIGNIF_UNDERCUT_ATR = 0.75   # a clean-V spring must dip >= this far below S to count on depth alone
BIN_C_MIN_LINGER_BARS = 2          # else the below-S episode (first penetration -> reclaim) must span >= this many bars
BIN_C_LATE_BOX_FRACTION = 0.50     # only look for Phase C in the late half of the base

# Phase B->D divider from the V-tip (display only). Separate from the Phase-C
# spring gate above: ANY recovered late-base low (even a shallow one that is NOT
# a true spring) is still the tip of the final 'V' and marks where the right-side
# markup begins ("Phase B ends here, Phase D starts here"). We're good at finding
# the tip even when small, so we repurpose it for the boundary, not a spring tag.
PHASE_D_VTIP_LATE_FRACTION = 0.35  # only look for the tip in the late part of the base
PHASE_D_VTIP_RECOVERY_BARS = 6     # a higher High within this many bars = it recovered

# Spread rules (core quality signal):
# Final LPS bar range must be < P-percentile of bar ranges across the base.
# 0.5 = median ("less than most bars in consolidation"); 0.33 stricter.
LPS_RANGE_PERCENTILE = 0.5
LPS_SPREAD_MUST_DECLINE = True    # Declining final spread earns full quality; widening is discounted, not gated

LPS_VOL_CONTRACTION_MAX = 0.85   # LPS avg volume must be <= 85% of 50d avg

# Shared structural-frame constants.
# --- FROZEN-CONFIG MANIFEST (Lane A) ---
# The four constants below define the engine's daily VOLATILITY/EDGE FRAME and
# are part of the frozen-config contract (core/freeze/manifest.py). DECISION:
# the ATR window is FROZEN as-is (no EWMA switch). Changing any value here is a
# new engine_config_version => the shadow baseline must be re-captured and the
# archive re-baselined. Do NOT tweak these casually. (PHASE_B_ATR_WINDOW and
# DAILY_STRUCTURE_PERIOD, also frozen, are likewise tagged at their definitions.)
STRUCTURE_EDGE_SKIP_BARS = 5      # Reserve latest bars for trigger/edge action when anchoring boxes
# Daily ATR is sampled one bar before the reserved edge-skip window so the volatility
# frame matches the bars the box/LPS were anchored on (df.iloc[-(skip+1)]). Bound ONCE
# at import to the DAILY value (5+1=6); do NOT recompute settings.STRUCTURE_EDGE_SKIP_BARS+1
# at a call site — that knob is overridden to 1 inside HTF weekly/monthly window contexts,
# whereas this daily eval bar must stay fixed.
STRUCTURE_ATR_SAMPLE_OFFSET = STRUCTURE_EDGE_SKIP_BARS + 1   # = 6 (daily)
# --- end FROZEN-CONFIG MANIFEST (Lane A) region ---
INNER_SEARCH_FRACTION = 0.5       # Search recent half for nested Phase-D mini-consolidation
INNER_TIGHTNESS_RATIO = 0.75      # Inner box must be at least 25% tighter than parent
INNER_MIN_DAYS = 15               # Min length of an inner CANDIDATE box (room pre-filter only; inner_zigzag separately requires the search WINDOW >= MIN_BASE_DAYS — the binding floor)

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
# Dead-space dock on base-age "cause": a long base only earns full cause credit if
# its swings actually worked rail-to-rail. A WIDE base (box_width > this) with low
# traversal density is dead space, not cause, so its base_age is scaled down by the
# density shortfall (toward 0). Tight boxes are EXEMPT — their low density is a
# small-box / spring artifact (e.g. PRA, width 0.017), not dead space.
BASE_AGE_DEADSPACE_WIDTH = 0.06
SCORE_TOUCH_DENSITY = 25        # 15 base + 10 bonus (was 20)
SCORE_VOL_CONTRACTION = 20      # Volume dry-up (was 10)
SCORE_LPS_TIGHTNESS = 20        # Final candle tightness (was 35)
SCORE_BOX_TIGHTNESS = 22        # Tightness now bites (was 15) — separates a tight coil from a wide-but-clean range
SCORE_ATR_SQUEEZE = 8           # Volatility contraction (was 10)
# ADR-relative box tightness. The absolute-% tightness grade above rewards flat low-ADR
# drifts as "coils" — corr(box_tightness, ADR) = -0.73 on the 2026-06-25 universe (GBTG @
# 0.52% ADR earned the book's highest tightness for a 1.3% box that is ~2.5 ADR wide). When
# enabled, tightness is measured in ADR units: a box wider than MAX_BOX_WIDTH_ADR daily-ranges
# earns zero tightness, matching how a VCP / the eye reads contraction relative to the stock's
# OWN volatility. Absolute MAX_BOX_WIDTH stays the validity GATE (which setups fire is
# unchanged) — this only re-bases the SCORE component.
# FLIPPED ON 2026-06-30 after operator chart-eyeball (docs/adr_flip_2026-06-30/): the flip's
# demotions (GBTG buyout-deadpin/HIO/IX flat low-ADR drifts) and promotions (SPCB/DHX/TECX
# real coils on lively movers) both read correctly. Score-only / recall-safe; shadow baseline
# re-captured to match. Was default-off & measure-first since 2026-06-25.
TIGHTNESS_ADR_AWARE = True
MAX_BOX_WIDTH_ADR = 4.5         # (R-S)/S expressed in ADRs; >= this earns zero tightness credit
# Candle-spread readability multiplier on box_tightness. Box width says how tight the RANGE
# is; this grades the TEXTURE inside it — a base whose bars are individually quiet vs its OWN
# box and ATR reads as a more genuine coil than one of equal width with choppy bars. SELF-
# REFERENTIAL by construction (spread/box, spread/ATR, tight-bar % are already box/ATR-
# normalized), NEVER an absolute bar-width threshold — so a high-ADR but orderly mover (TITN:
# spread/box 0.34, spread/ATR 0.68, tight-bar 0.77) is read against its own volatility, not
# penalized for raw bar width, while a messy wide-bar base (DHX: spread/box ~0.55) is docked.
# Multiplicative grade in [CANDLE_GRADE_FLOOR, 1.0]: a silent box keeps full tightness, a noisy
# box is discounted toward the floor (a GRADE, never a veto). Measure-first / DEFAULT OFF until
# an operator chart-eyeball clears it (sibling of the ADR flip); flag-off is byte-identical (the
# term lives ONLY inside `if CANDLE_SPREAD_AWARE` in score_setup). Missing texture -> neutral 1.0.
CANDLE_SPREAD_AWARE = False
CANDLE_GRADE_FLOOR = 0.55       # worst-case multiplier — a choppy base keeps >= 55% of its tightness
# Ramp anchors (universe medians, 2026-06-30 scan: spread/box ~0.31, spread/ATR ~0.85, tight-bar
# ~0.68). Each sub-grade ramps full(1)->zero(0) across clean->messy; these are CALIBRATION
# references the operator tunes on the A/B pack, not hard gates.
CANDLE_SPREAD_BOX_CLEAN = 0.35  # median spread/box <= this -> full readability (lower = tighter)
CANDLE_SPREAD_BOX_MESSY = 0.60  # median spread/box >= this -> zero on this measure (DHX ~0.55)
CANDLE_SPREAD_ATR_CLEAN = 0.90  # median spread/ATR <= this -> full readability
CANDLE_SPREAD_ATR_MESSY = 1.40  # median spread/ATR >= this -> zero on this measure
CANDLE_TIGHTBAR_CLEAN = 0.65    # tight-bar % >= this -> full readability (higher = cleaner)
CANDLE_TIGHTBAR_MESSY = 0.30    # tight-bar % <= this -> zero on this measure
# L2 SOS calibration (measure-only event reader; gates/scores nothing). An SOS is a Phase-D
# creek-jump that TESTS the rail and HOLDS. Two box-relative bounds keep markup out of the SOS
# bucket so it stops over-firing in active/extended boxes (AMRZ fired ~15 SOS):
#  (1) NEAR R — the wave-top peak must sit near R (peak_box_pos <= SOS_NEAR_R_MAX_BOX); a reach
#      far above R (AMRZ pkPos 2.0-2.4) is post-breakout MARKUP, typed `markup`, not SOS.
#  (2) REAL HOLD — the post-top hold window must be a genuine mini-consolidation (its High-Low
#      span <= SOS_HOLD_MAX_RANGE_BOX of the box), not merely "no drop to the low-zone in N bars".
# Both are box fractions so they scale across the universe; operator-eyeball-tuned.
SOS_NEAR_R_MAX_BOX = 1.5        # wave-top box_pos ceiling for an SOS (1.0 = R; > this box-frac above R = markup)
SOS_HOLD_MAX_RANGE_BOX = 0.55   # post-top hold-window High-Low span as box fraction to count as a consolidation
# E3 puzzle-quality graded sub-score — wires the L2 assembled Wyckoff puzzle (assemble_box_narrative,
# read on the engine's OWN elected box) into the score as ONE additive, BONUS-ONLY term: a single
# [0,1] composite * cap. Sibling of CANDLE_SPREAD_AWARE: flag-off the term AND its computation are
# fully inert (byte-identical, zero new compute; _puzzle_quality + assemble_box_narrative both live
# ONLY inside `if PUZZLE_SCORE_ENABLED`). Grades-not-vetoes: it can only RAISE a score, never gate /
# reject / touch firing. completeness and chronology are CORRELATED (intact => full spine), so they
# combine into ONE composite (not two terms). The live flip + the forward-return validation are
# operator-gated (matured ~07-15+ data).
PUZZLE_SCORE_ENABLED = False    # default-off; the flip is an operator chart-eyeball + matured-data decision
SCORE_PUZZLE_QUALITY = 8.0      # cap for the puzzle sub-score (~half a tier gap; sibling of SCORE_ADR/BREADTH)
PUZZLE_W_COMPLETENESS = 0.70    # composite weight on completeness/4 (0..4 distinct pieces present)
PUZZLE_W_CHRONOLOGY = 0.30      # composite weight on the chronology factor (weights sum to 1.0 -> composite in [0,1])
PUZZLE_CHRONO_PARTIAL = 0.50    # chronology factor: intact=1.0, partial=this, absent=0.0

# ── Technical Analysis Score v2 (hybrid / dynamic, 0-100) ───────────────────────
# Master flag for the Visual "Technical Analysis Score" rework (specs/ta-score-rework.md):
# folds the sub-scores AND the setup-tags into one hybrid 0-100 grade with the tier derived
# from it, and demotes market regime (breadth + SPY) to an informational label. Sibling of
# PUZZLE_SCORE_ENABLED / CANDLE_SPREAD_AWARE: flag-OFF the entire v2 formula and any new keys
# are inert (byte-identical, zero new compute); the ON behavior lands incrementally behind
# this flag. The live flip is an operator A/B-eyeball decision.
TA_SCORE_V2 = False
# Traversal quality — the 2-sidedness the validity gate only screens for, now a
# graded REWARD: a box whose limbs genuinely run rail-to-rail (high nFull/nSwings
# density) scores up; a dead-space framing that hangs off one rail (dwell asymmetry)
# or anchors a rail on a one-off spike (max_swing_frac > 1) is docked. Box-relative
# inputs only — no box_width, so no double-count with SCORE_BOX_TIGHTNESS.
SCORE_TRAVERSAL_QUALITY = 10           # cap — lifts a clean box over a dead-space one without bloating S-tier
TRAVERSAL_QUALITY_DENSITY_FULL = 0.33  # nFull/nSwings >= this earns full density credit (winner median ~0.5)
TRAVERSAL_QUALITY_DWELL_PENALTY = 8    # max dock for dwell asymmetry + one-off-spike overshoot

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

# Ascending support / higher lows (Minervini "tennis-ball action", Qullamaggie
# "higher lows surfing the rising EMA"): are the swing-low valleys stair-stepping
# UP across the base? Measured by core.structure.metrics.measure_support_slope
# (ATR-normalized least-squares slope through the zigzag valley lows). Bonus-only,
# measure-first — a flat or sagging floor simply earns zero, never penalized.
SCORE_ASCENDING_SUPPORT = 8          # cap for the ascending-support sub-score
ASCENDING_SUPPORT_FULL_SLOPE = 0.10  # valley lows rising ≥ 0.10 ATR/bar → full slope credit

# ADR% absolute volatility (Qullamaggie "mover" character): does the stock
# travel enough each day to be worth trading? Bonus-only, measure-first.
ADR_WINDOW = 20        # bars used for the Average Daily Range %
SCORE_ADR = 8          # cap for the ADR sub-score
ADR_FULL_PCT = 5.0     # ADR% >= 5.0 earns full credit (~5% mover threshold)

# Touch density bonus trigger
TOUCH_BONUS_INDIVIDUAL = 3       # Need >= 3 touches on EACH side
TOUCH_BONUS_TOTAL = 6            # OR >= 6 total touches
TOUCH_BONUS_POINTS = 10          # Bonus awarded (part of the 25 pts max)


# ============================================================
# DATA & CACHING
# ============================================================
# Live archiving — when True, every daily screener run upserts its full output
# (winners AND the setups that later fizzle) into setup_archive with
# source="screener". This is the fuel the calibration/analysis tools need:
# without live non-winners, every outcome metric is biased by the seed gallery.
# Idempotent per (ticker, scan_date); re-running the same day updates in place.
ARCHIVE_LIVE_SCANS = True

# Market-data source. The screener fetches its canonical panel through
# core.pipeline.providers.get_provider(), not directly from a vendor, so a
# bulk-EOD source can be added behind the same contract and validated against
# the incumbent (tools/provider_parity.py) before it feeds an archiveable scan.
# "yahoo" wraps the existing yfinance path verbatim — the default is a no-op.
MARKET_DATA_PROVIDER = "yahoo"

CACHE_FILENAME = "market_data_cache_5y.parquet"
CACHE_META_FILENAME = "cache_meta.json"
MARKET_CONTEXT_FILENAME = "market_context.json"
PARQUET_ENGINE = "pyarrow"
PARQUET_COMPRESSION = "zstd"
DOWNLOAD_PERIOD = "5y"            # 5y of daily history so weekly (~260 bars) and monthly (~60 bars)
                                 # resampling for HTF context has enough depth. The DAILY structure
                                 # read is trimmed back to DAILY_STRUCTURE_PERIOD so this deeper cache
                                 # does NOT change daily behavior (see HTF section below + core.structure.htf).
                                 # Renaming the cache file forces a clean cold 5y backfill on next run.
TICKER_CACHE_MAX_AGE_DAYS = 1     # Refresh the ticker universe CSV daily
TICKER_SKIPLIST_FILENAME = "ticker_skiplist.txt"  # One symbol per line; skipped before any Yahoo request
TICKER_ADMISSION_ENABLED = True
TICKER_ADMISSION_FILENAME = "ticker_admission.json"
ADMISSION_MIN_HISTORY_BARS = 200   # Same minimum used by the baseline history gate
ADMISSION_YOUNG_RECHECK_DAYS = 21  # Alive but too young: re-test after it may have gained bars
ADMISSION_EMPTY_RECHECK_DAYS = 7   # No Yahoo history: short cooldown before re-probing

# ============================================================
# HIGHER-TIMEFRAME (HTF) STRUCTURE CONTEXT
# ============================================================
# The structure engine reads the SAME Wyckoff Trend+Box (A->B->C->D) logic on
# weekly/monthly bars as on daily — "it's all relative and derivative". Its RATIO
# thresholds (MAX_BOX_WIDTH, MIN_BOUNDARY_RESPECT_PCT, ATR/box ratios, traversal
# fractions, LPS profiles) are scale-invariant and transfer untouched; only the
# BAR-COUNT WINDOWS are daily-calibrated. core.structure.htf temporarily rescales
# ONLY those windows (timeframe_windows CM) around the same Trend+Box brick walk
# on the resampled frame. These presets are FIRST-PASS (~daily/5 weekly, /~4 again
# monthly) and a calibration target — eyeball + tune via tools/htf_audit.py.
HTF_CONTEXT_ENABLED = True        # compute + archive + chip HTF context on FIRING setups; never gates

# The daily read is sliced to this trailing window before read_structure, so the
# 5y cache (needed for HTF resampling) does NOT feed the daily oldest-first root
# walk extra history and drift it (the FOSL _MAX_ANCHORS sensitivity). Keeps daily
# byte-identical; validate with tools.shadow_diff once real 5y data is present.
# FROZEN-CONFIG MANIFEST (Lane A): the daily read window is part of the frozen
# engine contract — changing it is a new engine_config_version (re-baseline).
DAILY_STRUCTURE_PERIOD = "2y"

HTF_STAGE_MA = 30                 # HTF Stage-2 trend MA (Weinstein weekly MA-30 ~ daily MA-150/200)
HTF_STAGE_MA_SLOPE_BARS = 4       # the stage MA must be rising over this many HTF bars

# settings-attr -> weekly value. ONLY bar-count windows appear here; every ratio
# threshold is deliberately absent so it keeps its calibrated daily value.
HTF_WEEKLY_WINDOWS = {
    "MIN_BASE_DAYS": 6,
    "STRUCTURE_EDGE_SKIP_BARS": 1,
    "TREND_MIN_MOVE_BARS": 5,
    "TREND_PRIOR_LOOKBACK": 26,
    "LOCAL_PEAK_BARS": 8,
    "ROOT_TREND_SMA": 30,
    "PHASE_B_ATR_WINDOW": 8,
    "AR_MAX_BARS": 4,
    "MAX_CONSECUTIVE_OUTSIDE_DAYS": 3,
    "PIVOT_ORDER_THRESHOLD": 12,
    "EQ_MIN_TOUCHES_PER_RAIL": 2,
    "LPS_SCAN_OFFSET_MAX": 2,
    "LPS_LENGTH_MIN": 1,
    "LPS_LENGTH_MAX": 4,
    "BIN_C_RECOVERY_BARS_MAX": 3,
    "BIN_C_LINGER_BARS_MAX": 4,
    "BIN_C_HOLD_BARS": 1,
    "BIN_C_MIN_LINGER_BARS": 1,
    "PHASE_D_VTIP_RECOVERY_BARS": 2,
}

HTF_MONTHLY_WINDOWS = {
    "MIN_BASE_DAYS": 4,
    "STRUCTURE_EDGE_SKIP_BARS": 1,
    "TREND_MIN_MOVE_BARS": 3,
    "TREND_PRIOR_LOOKBACK": 12,
    "LOCAL_PEAK_BARS": 4,
    "ROOT_TREND_SMA": 10,
    "PHASE_B_ATR_WINDOW": 6,
    "AR_MAX_BARS": 3,
    "MAX_CONSECUTIVE_OUTSIDE_DAYS": 2,
    "PIVOT_ORDER_THRESHOLD": 8,
    "EQ_MIN_TOUCHES_PER_RAIL": 2,
    "LPS_SCAN_OFFSET_MAX": 1,
    "LPS_LENGTH_MIN": 1,
    "LPS_LENGTH_MAX": 2,
    "BIN_C_RECOVERY_BARS_MAX": 2,
    "BIN_C_LINGER_BARS_MAX": 3,
    "BIN_C_HOLD_BARS": 1,
    "BIN_C_MIN_LINGER_BARS": 1,
    "PHASE_D_VTIP_RECOVERY_BARS": 1,
}

# Incremental fetch tuning
TTL_FRESH_HOURS_MARKET = 1        # Re-fetch latest bars if cache is older than this during market hours
TTL_FRESH_HOURS_OFFHOURS = 12     # ...or this outside market hours
FULL_REFRESH_INTERVAL_DAYS = 7    # Force a cold 5y refetch at least weekly
INCREMENTAL_OVERLAP_BDAYS = 5     # Re-download this many business days before last_cached_date for split-probe overlap
INCREMENTAL_MAX_GAP_BDAYS = 10    # Above this gap, fall back to full refetch instead of incremental
MARKET_DATA_MIN_LATEST_COVERAGE = 0.95  # Required latest-session close coverage before cache/archive is trusted
# Deep-history corruption floor (the "second half" of the multi-universe cache bug).
# A trusted cache spans years; the NaN-wipe failure leaves recent bars but ~6 bars of
# deep history. Only judged when the PANEL itself spans >= MIN_HISTORY_BARS rows (so a
# short/new cache is never falsely flagged); below MIN_HISTORY_COVERAGE of symbols
# clearing the bar floor => cache is deep-history-corrupted => force a full cold refetch.
# 100 is well below ADMISSION_MIN_HISTORY_BARS(200) yet ~16x above a wiped cache.
MARKET_DATA_MIN_HISTORY_BARS = 100
MARKET_DATA_MIN_HISTORY_COVERAGE = 0.5
LATEST_REPAIR_BATCH_SIZE = 100     # Smaller latest-bar repair batches after a sparse Yahoo response
LATEST_REPAIR_SLEEP_SECONDS = 2.0  # Gentle pause between repair batches to reduce Yahoo rate limits
MARKET_DATA_REPAIR_FIRST_RETRY_MINUTES = 10   # Sparse eligible-symbol repair: first unchanged retry window
MARKET_DATA_REPAIR_SECOND_RETRY_MINUTES = 20  # Sparse eligible-symbol repair: second unchanged retry window

# Outbound Yahoo request rate limit (core.pipeline.rate_limit). yfinance spawns its
# own download threads and the screener fans the universe across a worker pool, so
# without a SHARED ceiling the concurrent workers each throttle independently and
# collectively burst Yahoo into 429s — the 2%-coverage stale-data days. Every
# yf.download call now passes through ONE process-global token bucket, and the
# download pool is bounded (workers) to cap concurrent connections. (yfinance 1.2.1
# requires a curl_cffi session and rejects a stdlib requests.Session, so a
# requests-ratelimiter LimiterSession can't be injected — hence the explicit gate.)
# Tuned from read-only probes on the active-ready universe. Higher rates (40-70/s)
# can complete after retries, but they trip Yahoo's rolling Too Many Requests path.
YAHOO_RATE_LIMIT_ENABLED = True
YAHOO_RATE_LIMIT_PER_SEC = 20.0    # sustained outbound requests/sec to Yahoo (global ceiling)
YAHOO_RATE_LIMIT_BURST = 40        # token-bucket capacity (max short burst)
YAHOO_DOWNLOAD_WORKERS = 24        # bounded download-pool size (caps simultaneous connections)
YAHOO_RATE_LIMIT_BACKOFF_SECONDS = 45.0  # shared cooldown after explicit Yahoo 429/rate-limit errors

# Split-detection probe (defends against yfinance's auto_adjust=True silently rescaling history)
SPLIT_PROBE_SAMPLE_SIZE = 30                 # Number of cached tickers (+ SPY) to probe for split-induced drift
SPLIT_PROBE_DRIFT_THRESHOLD = 0.005          # Ticker-level: ratio (fresh/cached) deviating by > 0.5% on overlap = split
SPLIT_PROBE_UNIVERSE_DRIFT_PCT = 0.02        # If > 2% of probed tickers drift → cold refetch
SPLIT_PROBE_REFERENCE_SYMBOL = "SPY"         # Always included in the probe sample if present in cache

# Dead-ticker quarantine — the universe (~6.9k NASDAQ-traded symbols) has a long
# tail of delisted / halted / invalid tickers that return nothing from Yahoo every
# run, wasting requests, driving 429s, and triggering per-ticker recovery storms.
# Symbols that come back empty on repeated COLD full-refetches (the strongest death
# signal) are skipped, then re-probed after a cooldown so a re-listing recovers.
# Updates are gated on a healthy run so a rate-limited day can't quarantine the
# whole universe. Index symbols are never quarantined. See core/pipeline/fetch_health.py.
QUARANTINE_ENABLED = True
QUARANTINE_FILENAME = "ticker_quarantine.json"
QUARANTINE_EMPTY_STREAK = 2          # consecutive empty cold-refetches before quarantine
QUARANTINE_COOLDOWN_DAYS = 7         # re-probe a quarantined ticker after this many days
QUARANTINE_MIN_HEALTHY_RATIO = 0.85  # only judge deadness on a near-complete run: a rate-limited day (429s crater the return ratio) falls below this and can't penalize missing tickers, while a healthy run returns ~95%+ of requested

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
ALERT_ON_DEGRADED_FETCH = True    # also alert when a scan succeeds but its fetch-health came back unhealthy (low return ratio) — an early warning before a stale_data failure

# ============================================================
# --- DATA PRIMITIVES (Lane C) ---
# ============================================================
# Additive, NOT-YET-WIRED data layers (core/fundamentals, core/regime) that a
# later scoring/enrichment wave will consume. They read market data ONLY through
# core.pipeline.providers.get_provider() and compute pure functions over already-
# fetched frames, so nothing here changes the engine's computed output today.
# Every flag defaults OFF; the modules read these lazily via getattr(settings, ...)
# to respect the backend's config-vs-cwd shadowing constraint. Wire-up (feeding
# scoring / archive_models) is a separate, later wave — see each module docstring.

# Fundamentals: the 5 per-ticker metrics (core/fundamentals/metrics.py) — qtr EPS
# growth YoY, qtr sales growth YoY, EPS-growth acceleration, earnings surprise %,
# in-house RS rating. Null-safe (missing -> None). Read via the provider's
# get_income_stmt / get_earnings_dates / info accessors.
FUNDAMENTALS_ENABLED = False
FUNDAMENTALS_EARNINGS_HISTORY_LIMIT = 12   # quarters of earnings history to request
FUNDAMENTALS_MIN_QUARTERS_YOY = 5          # need >= this many quarters for a YoY-acceleration read (4-back + prior 4-back)
# Point-in-time filing lag: yfinance carries no per-quarter SEC filing date, so a
# quarter keyed by its PERIOD-END date would be read before it was actually filed
# (lookahead leak). A quarter is only treated as usable when
# period_end + this many days <= as_of. 75 days is the conservative ceiling — the
# SEC 10-Q deadline for a non-accelerated filer (45 days) plus margin — so the
# gate can be a few weeks LATE but never admits a not-yet-filed quarter. Earnings
# history is gated on its own report-date index (no lag needed there).
FUNDAMENTALS_FILING_LAG_DAYS = 75

# RS line (core/regime/rs_line.py) — stock/SPY ratio series + rs_line_new_high.
RS_LINE_ENABLED = False
RS_LINE_NEW_HIGH_LOOKBACK = 252            # ratio is a "new high" vs its rolling max over this many sessions (~52w)

# In-house RS rating (core/regime/percentile.py drives it via trailing return).
RS_RATING_LOOKBACK = 252                   # trailing-return window the RS rating percentile-ranks across the universe

# SPDR sector ranking (core/regime/sector_ranking.py) — rank the 11 SPDR sector
# ETFs by sector/SPY rs_ratio momentum over multiple lookbacks.
SECTOR_RANKING_ENABLED = False
SECTOR_RANKING_LOOKBACKS = (21, 63, 126)   # trading-day windows for the multi-horizon sector RS rank
SECTOR_RANKING_ETFS = (
    "XLK", "XLV", "XLF", "XLY", "XLP", "XLC",
    "XLI", "XLE", "XLU", "XLRE", "XLB",
)
