"""
Centralized configuration for the Wyckoff VCP/LPS Screener.
All tunable parameters in one place for easy adjustment.
"""

# ============================================================
# 1. UNIVERSE & BASELINE FILTERS
# ============================================================
# Price-series regime (operator rule, 2026-07-02): structural analysis runs on
# REAL traded prices. False = as-traded OHLC (split-adjusted only — exactly what
# TradingView shows); True = legacy dividend+split-adjusted series, which
# repaints history every ex-div and shows prices that were never traded
# (confirmed distorting income names: GOOD/ENIC passed baseline only on
# adjusted data, DKL's box start moved). The cache meta is stamped with the
# regime; a mismatch forces a full cold refetch — regimes are never mixed.
DATA_DIVIDEND_ADJUSTED = False

MIN_PRICE = 3.0
MIN_VOLUME_50D = 50_000          # 50-day average daily volume floor
MIN_YEARLY_RETURN = -0.20        # Allows modest drawdowns (v1 used +0.30)

# --- The 50-day dip exception (miss program 2026-08-28; DARK) ---------------
# The universe door's sma50 leg refuses a chart whose own drawn story dragged
# price under the 50-day — SKYT's deep spring held it below for ~4 weeks and
# the engine elects a COMPLETE structure the day the door is held open; ST
# lost 2 of its 10 candidate sessions the same way. The exception admits an
# sma50 refusal into chart reading (geometry stays the only veto) when the
# dip is a bounded, recent event that has already recovered to the rail of
# the 50-day: the last close at/above SMA_50 printed within
# SMA50_DIP_MAX_SESSIONS, and the close now sits within SMA50_DIP_MAX_ATR
# ATR_10 below it. The SMA_200 and YoY legs still gate (a dip exception is
# not a downtrend exception — MDT's bottoming base is deliberately out of
# scope: its wall is the sma200 rule at BOTH the door and anchor seeding,
# a species ruling for the operator). Flip = operator decision vs the
# miss-program A/B (docs/miss_program_2026-08.md).
SMA50_DIP_EXCEPTION_ENABLED = False
SMA50_DIP_MAX_SESSIONS = 25      # the dip began at most this many sessions ago
SMA50_DIP_MAX_ATR = 1.0          # close within this many ATR_10 under SMA_50

# --- The bottoming-base lane (miss program, operator ruling 2026-08-29; DARK)
# MDT is the corpus's one bottoming base and the operator ruled it a wanted
# catch ("I don't want to miss them"). Its wall is the sma200 rule at TWO
# layers — the universe door AND anchor seeding (collect_root_anchors refuses
# any frame under the 200-day) — while the engine, held open diagnostically,
# elects his drawn box to the penny (R 82.83, start 2026-06-04). The lane
# opens BOTH layers together, under ONE condition: the 50-day is reclaimed
# (close >= SMA_50) — a bottoming base being read only once its intermediate
# trend has turned. Price/volume/YoY legs still gate; geometry stays the only
# veto. Flip = operator decision vs the miss-program A/B + fleet census.
BOTTOMING_BASE_LANE_ENABLED = False
# The seeding half's reclaimed-50-day clock (promoted from a hardcoded literal
# — council review 2026-08-30, McKinney: the constant that decides who seeds
# must live in the frozen-config contract). Mirrors the universe door's SMA_50
# window; the HTF weekly/monthly presets pin the LANE off instead of rescaling
# this (the ruling + fleet census cover the daily clock only).
BOTTOMING_SMA50_BARS = 50

# --- The ceiling-rest LPS exception (miss program, operator ruling 2026-08-29; DARK)
# NOK elects his box at his exact rails and dies at ONE LPS leg: the INSIDE
# window that "launched above resistance" (the after-SOS giveback opens on the
# extension top) is refused as a late/off-structure pullback — even when the
# REST itself lands ON the ceiling (NOK: support low 0.24 ATR under R,
# pos_box 0.88 — the drawn corpus's most common terminal form, the rail
# rest). The exception sanctions the straddle ONLY when the rest sits within
# LPS_CEILING_REST_MAX_BELOW_R_ATR ATRs under R: a launch above R with a rest
# ON the rail is the preceding advance giving back to resistance, not a dive
# back into the box (which stays refused). The bar is DRAWN-evidence-placed:
# the corpus's launched-above shelves rest at 0.010/0.087/0.148/0.241 ATR
# under R (DSGN/MATX/MSGS/NOK; YPF at 0.77 is a mid-box shape, not this form)
# while the nearest junk (ENIC, must-not-fire) rests at 0.314 — 0.3 splits
# the drawn cluster from the junk with ~0.06 ATR on each side, a stated
# razor for the operator's eyeball at flip. Flip = operator decision vs the
# miss-program A/B (shadow drift + ratchet + junk corpus measured).
LPS_CEILING_REST_ENABLED = False
LPS_CEILING_REST_MAX_BELOW_R_ATR = 0.3

MIN_BASE_DAYS = 20               # Minimum consolidation length (reject < 20 day chop)
MAX_BOX_WIDTH = 0.18             # (R - S) / S ceiling. A range wider than this is
                                 # not a tradeable tight equilibrium — it's the
                                 # BC->AR extremes, not a worked Phase B box.
                                 # (was 0.25; tightened with the worked-equilibrium
                                 #  rewrite. Doubles as the box-tightness scoring scale.)
CRASH_FILTER_MULT = 0.70         # Floor cap for the box-width-scaled crash filter
EXTENSION_FILTER_MULT = 1.15     # Price above R * this = too extended

# ============================================================
# 2. PHASE A — TREND END & ANCHOR
# ============================================================
# Pivot detection
PIVOT_ORDER_SHORT = 1            # Used when equity window < 40 bars
PIVOT_ORDER_LONG = 2             # Used when equity window >= 40 bars
PIVOT_ORDER_THRESHOLD = 40       # Bar count threshold for switching ORDER

# Markup-leg qualification (Phase A in find_outer_box)
TREND_MIN_GAIN_PCT = 0.15        # Markup leg must gain >= 15% start->end
TREND_MIN_MOVE_BARS = 20         # Markup leg must span at least this many bars
TREND_PRIOR_LOOKBACK = 100       # Search this far back for prior trough/peak
LOCAL_PEAK_BARS = 30             # Anchor must be the local extremum over this window
ROOT_TREND_SMA = 200             # Long-trend MA gate in collect_root_anchors: a root requires
                                 # latest close > this SMA (the Stage-2 / uptrend filter). Daily=200;
                                 # HTF presets scale it (weekly ~30 = Weinstein MA-30, monthly ~10) so
                                 # the rolling mean isn't all-NaN on the shorter resampled frame.

# Automatic Reaction validation (required)
AR_MIN_DROP_PCT = 0.05           # Price must drop >= 5% from BC high (or rise from SC low)
AR_MAX_BARS = 15                 # ...within this many bars of the climax

# Cause-before-effect election precondition (engine_alpha/structure/bricks.cause_maturity,
# consulted in narrative.read_structure). A box may not be elected over a live trend that
# never matured a cause: the MIDD class, where price trends UP through both rails into a
# blow-off so the consolidation predates its own climax. Veto ONLY when ALL THREE reads
# agree the cause is absent -- the box-INDEPENDENT macro bridge abstains AND the HH/HL
# staircase reads a live up-run each side of the box open AND the elected LPS shelf never
# tightened (CAUSE_LPS_LOOSE_MAX, the third leg documented just below). Depth-free (a deep throwback like
# CTOS keeps its validated bridge) and fail-OPEN (never veto on missing data -- recall is the
# pass/fail gate). FLIPPED LIVE 2026-07-20 (operator grant): the recall pre-flight passed (hermetic
# seed 43/43, marks ratchet held, MIDD rejects) and the live A/B eyeball removed 7 of 234 fired names,
# all operator-confirmed skips (MIDD/FLG/BNS/CVCO/HWM/NTCT-current/TPL). See docs/flag_ledger.md
# (Retired) + docs/strategy_alpha.md "Cause before effect".
CAUSE_BEFORE_EFFECT_VETO_ENABLED = True

# Third leg of the cause-before-effect veto (consulted ONLY when the flag above is ON and
# both top-down reads already agree the cause is absent): the elected LPS's final shelf
# candle must ALSO be loose to veto -- its tightness_ratio (spread of the last shelf bar /
# base profile unit) strictly ABOVE this. The separator hunt (2026-07-20, wf_8a6fdb42)
# found MIDD's shelf never tightened (tightness_ratio 0.957 == sub_lps_tightness 1.73, the
# global minimum of the seed+MIDD census) while all 43 seeded winners tightened more
# (nearest VIST 0.842); 0.90 centers the cut in the empty band between them. AND-narrowing:
# a third AND-leg can only SHRINK the veto, so a tight-shelf winner (BP/LECO/MEOH/NTCT/VLO,
# all tightness_ratio < 0.71) is rescued and never dropped. A distinct axis from the
# box-geometry respect gate and the dist-above-R depth cap the fleet census killed. Fail-OPEN
# (a missing/NaN ratio reads 0.0 -> never loose -> never vetoes). See docs/strategy_alpha.md
# "Cause before effect".
CAUSE_LPS_LOOSE_MAX = 0.90

# Coarse->fine MACRO Phase-A read (phase_a.macro_bridge_zigzag; see
# engine_alpha/structure/phase_a.py, docs/pip_macro_phase_a.md). The earlier FLAT PIP wire
# (PIP_PIVOTS_ENABLED — segment_swings sourcing its whole zigzag from one
# fixed-dist_min PIP skeleton) was eyeball-gated OFF as a wash (fixes some
# inverted climax->AR overlays, creates others — GBTG/PLSE/CGNX, commit
# d43e7fd) and DELETED 2026-07-03 (docs/flag_ledger.md); this is the
# multi-resolution retry: source segment_swings' zigzag from the SMALLEST
# top-K importance prefix holding a confirmed climax->AR bridge (interior AR),
# so late range retests / noise dips are not in the skeleton to steal the
# climax or AR. Deliberately NOT applied to read_market_structure — event
# labels want the fine skeleton, the Phase-A bridge wants the coarse one.
# Feeds ONLY the Phase-A overlay via resolve_phase_a, never R/S/score/tier.
# FLIPPED LIVE 2026-07-04: operator eyeball on the overlay A/B (19/140 overlays re-anchor
# to the genuine trend-top -> reaction, 0 stolen climaxes in EITHER mode, 0 score/fire/tier
# — Phase-A OVERLAY only). The phase-ordering hold (LUV: macro AR landed AFTER the box
# start) was a REAL overlay defect, not an over-strict invariant: the box-overrunning macro
# bridge now abstains (resolve_phase_a bridge_end_max = phase_b_start_bar, 142bf50); the
# sibling always-on order-N hole was closed in 5882226.
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

# Climax terminality for the CALIBRATED Phase-A resolution (resolve_phase_a).
# The same True-Root rule the macro bridge enforces above, applied to the
# bridge/seed fallback paths that had none: between the resolved climax and the
# box open, price may exceed the climax by at most this fraction of the bridge
# height (ATR floor guards a degenerate height). A violating pair is a mid-trend
# pause, not the trend end (FLXS: +38.5% ran past the claimed climax into the
# box) — it re-anchors to the box's own run-up extreme. Overlay + Phase-A
# diagnostics only (bars_since_BC / descent_length / bin_a); no rail or score.
PHASE_A_CLIMAX_TERMINALITY_EXCESS = 0.25

# ============================================================
# 3. PHASE B — RAILS & EQUILIBRIUM
# ============================================================
# Phase-B ATR window (median over recent N base bars; used when no override is given)
# FROZEN-CONFIG MANIFEST (Lane A): part of the frozen ATR/volatility frame —
# changing it is a new engine_config_version (re-baseline). See the marked region
# at STRUCTURE_EDGE_SKIP_BARS / STRUCTURE_ATR_SAMPLE_OFFSET below.
PHASE_B_ATR_WINDOW = 30

# Shared structural-frame constants.
# --- FROZEN-CONFIG MANIFEST (Lane A) ---
# The four constants below define the engine's daily VOLATILITY/EDGE FRAME and
# are part of the frozen-config contract (engine_alpha/freeze/manifest.py). DECISION:
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

# Dynamic Recursive S/R Scanning (Phase B)
BOUNDARY_ATR_BUFFER = 0.50       # ATR multiplier for boundary respect zone

MAX_CONSECUTIVE_OUTSIDE_DAYS = 10 # Max consecutive bars whose full range pierces the buffered boundary (high>R+buf or low<S-buf). (was 30 — absurdly lenient; tightened with the worked-equilibrium rewrite.)
MIN_BOUNDARY_RESPECT_PCT = 0.80  # At least 80% of bars must keep their full range inside [S-buffer, R+buffer]
TOUCH_TOLERANCE_ATR = 0.5        # ATR multiplier for S/R touch zone (price-level agnostic)

# Engagement measure yardstick (Move 1, gap-breach Task 3; MEASURE-ONLY).
# The archived eq_engagement_respect_frac re-reads an outside bar as a "hang"
# when its excursion beyond the buffered rail stays within this x ATR and its
# close came back inside (bar-basis primary per the operator ruling
# 2026-07-24; close supplementary). NEVER a gate: an election-gate variant of
# this exact rule was built and REJECTED 2026-07-24 — the negative corpus
# admitted FLG+BBVA at every bound >= 0.5 (SPCB/DBD/ENIC too at 1.5) while
# converting ZERO Guided List misses (NKTR's no-box is width-dominated).
# The wick-basis respect gate IS the junk defense; see strategy_alpha.md.
ENGAGEMENT_MAX_EXCURSION_ATR = 1.5

# Worked-equilibrium validity (Phase B) — a candidate Resistance/Support-anchor
# pair is only a real trading range if price RESPECTS, TOUCHES, and ZIGZAGS
# THROUGH both rails CONSTANTLY, with no dead space. These gates replace the old
# "2 touches per side + N midline crosses" rule, which let the widest BC->AR box
# win (dead space below a one-time AR low, or mid-box churn). Candidate selection
# uses close-residence dwell/coverage; public measure_dwell_balance also reports
# High/Low range occupancy for analysis. Starting points are calibrated against
# seed-recall, not hard-coded blind.
EQ_MIN_TOUCHES_PER_RAIL = 3      # >= this many touches within TOUCH_TOLERANCE_ATR of EACH rail
EQ_MIN_TOUCH_THIRDS = 2          # each rail touched in >= this many of 3 time-thirds (constant, not clustered)
EQ_MIN_HALF_DWELL = 0.15         # >= this fraction of closes in BOTH the lower and the upper box third (both halves worked -> no dead space)
EQ_MAX_MID_DWELL = 0.45          # <= this fraction of closes in the middle box third for box-of-record selection
EQ_MIN_COVERAGE = 0.80           # >= this fraction of box-height bins must hold real close dwell (starved-band / dead-space detector)
EQ_COVERAGE_BINS = 6             # number of equal box-height bins for the coverage measure
EQ_COVERAGE_MIN_FRAC = 0.03      # a bin counts as "filled" if it holds >= this fraction of closes

# Dwell BASIS note (bar-as-unit gate variant tested and REJECTED 2026-07-25,
# docs/bar_dwell_protocol_2026-07.md §8): judging the dwell trio on bar
# extremes instead of closes converts EGBN at the operator's exact rails BUT
# breaks 10/26 hit elections (MATX lost, five displaced winners) and fires
# DGII+FLG junk — close residence is load-bearing for ELECTION STABILITY, not
# just junk defense ("Phase-B rails do not drift" is measured fact). The
# bar-unit read survives as measure-only (`box_gates._dwell_bar_basis`);
# never re-wire it into the gate.

# Limb-traversal read (Phase B) — the swing-structural complement to the
# occupancy gate above. The occupancy gate asks where price resides; this asks
# whether the up/down swing LIMBS of the chop actually travel rail-to-rail
# (S<->R), or hang off one rail and leave dead space (the tell that R/S were
# marked too wide). Swing size is judged as a FRACTION OF BOX HEIGHT, not a bar
# count, so the read adapts to box width (tight boxes have short limbs, wide ones
# long). Measured by engine_alpha.structure.metrics.measure_equilibrium. The
# gate is permanent engine behavior (unconditional in code since the Purity Pass
# flag fold, 2026-07-18); the floors below are the live knobs.
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

# Descent-tail gate: a WIDE box whose support rail was abandoned EARLY — price
# left the low rail (last_support_time_pos <= LSF_MAX, the time-position 0..1 of the
# last support touch) then coiled in DEAD SPACE above it (low_position_in_box >= CFP_MIN,
# the box-position of the lowest Low after that touch) — is a mis-anchored /
# dead-space framing (CHCT, DGII). Read on the ACTIVE box (the inner box when the
# LPS re-anchored there, else the parent), so a setup with a clean PROMOTABLE inner
# survives (QUAD). TIGHT boxes (box_width <= BASE_AGE_DEADSPACE_WIDTH) are EXEMPT —
# their dead band is small in absolute terms so the tell is a false positive
# (saves the EQIX winner, box_width 0.038). Validated 2026-06-19 (pre + post the
# LPS recall work): drops ZERO firing seed winners; drops ~6/97 universe dead-space
# fires incl. the user's CHCT + DGII. Measured by measure_equilibrium (metrics.py).
DESCENT_TAIL_LSF_MAX = 0.40
DESCENT_TAIL_CFP_MIN = 0.20

# Sign-of-strength (SOS) breakout tolerance for Phase-B validation. A worked
# range whose RIGHT side has already broken out above R and HELD above support —
# a break above R then a rest back on it (SOS -> LPS above R) — is the setup, not a failed box. The
# legacy respect/occupancy gates measured to the live edge, so they counted that
# breakout as a boundary failure and rejected the range (e.g. NMM: a clean April
# box buried under a sustained May breakout above R, backing up to an early-June
# LPS). Fix: validate the range over its WORKED CAUSE — trim a trailing sustained
# above-R run that holds support before measuring boundary-respect + occupancy.
# No-op unless price has already broken out and held, so in-range setups are
# untouched and the change can only RESCUE break-above-R-then-rest framings (recall-positive).
# Outer Phase-B only (like the traversal gate); inner boxes are never trimmed.
SOS_TRIM_MIN_RUN = 3             # a breakout tail must be >= this many consecutive above-(R+buffer) bars (not a one-bar wick)
SOS_TRIM_MIN_PREFIX_FRAC = 0.30  # the worked cause before the breakout must be >= this fraction of the candidate window

# Box-START shared-rail back-extension (calibration gap #3 — AGCO, 2026-07-02).
# Candidate starts are pinned to their anchor pair (cand_start = min(r_anchor,
# s_anchor)), so the earliest-valid election can never reach an earlier start
# its own gates would bless (AGCO: dissection proved the elected rails valid
# from 03-25; the anchor pair proposes only 04-02). When enabled, the ELECTED
# box's start walks LEFT to the earliest zigzag pivot that re-touches an
# elected rail within TOUCH_TOLERANCE_ATR (peak~R / valley~S) with every
# intervening bar inside the BOUNDARY_ATR_BUFFER band — on AGCO it lands on the
# 03-30 S-touching valley (3 bars shy of full validity: the 03-25 peak never
# re-touches R). Requiring the rail re-touch is what separates worked cause
# from drift: raw band-conformance alone swallowed WDI's descent leg (+80) and
# BYD's mid-band chop (+26) in the PRE-cutover adjusted-price census. On
# as-traded data 94% of fires band-conform leftward (median +5), but the built
# lever moves only 42/140 starts (median 6 bars) with 0 fires gained/lost/
# re-storied (box-backext A/B, tool retired Task 9). Rails, gate verdicts and the
# election are untouched — but every read anchored to the box start re-measures
# over the extended span (the base-window suite: base-age, traversal,
# contractions, support slope, dwell, touch-volume, bar compression; plus the
# spring / inner-box / LPS windows, bin evidence and the event-story read).
# Implemented in box_primitives.backext_shared_rail; applied post-election in
# BOTH bricks.validate_equilibrium (live) and phase_b_zigzag (diagnostics).
# FLIPPED ON 2026-07-03 after the operator eyeballed the A/B renders
# (tools/fidelity/box_backext/); shadow baseline re-captured at the flip.

# ── Deep-excursion (terminal-shakeout) pair events (Event Map Task 11) ──────
# DARK, default OFF. Last-resort pair-election pool (outer Phase B only,
# consulted ONLY when the strict and rescued pools are both empty — an ordinary
# box's election can never move): the CHRONOLOGICAL zigzag pairs re-judged with
# band-leaving excursions typed as events that must reclaim/fail-back and HOLD
# (the spring invariants at terminal-shakeout scale) or the pair dies. Event
# bars are excised; the UNCHANGED respect/occupancy/traversal gates run
# full-strength on the judged window. Operator rulings 2026-07-10 (BODI marked
# chart + chat): the Feb collapse is PHASE C inside ONE box; rails anchor from
# the chronological swings, measured wick to wick. A pair carrying a qualified
# DEEP below-rail event may measure up to BAND_MAX_BOX_WIDTH (BODI's
# chronological pair reads 0.20-0.23) — the allowance exists ONLY with the
# event, so it can never act as a general width loosening. Calibration set:
# docs/phase_c_marks_2026-07.json.
# Live flip operator-granted 2026-07-16 (solve-the-engine flip checklist #2).
BAND_RAILS_ENABLED = True
BAND_MAX_BOX_WIDTH = 0.23        # wick-to-wick cap for a pair WITH a qualified deep event
BAND_EVENT_MIN_BARS = 2          # a deep event is multi-bar; one-bar pokes stay respect-buffer business
# Depth cap on a qualified below-rail event, in ATRs below the S rail: deeper
# is a genuine breakdown, never a terminal shakeout (the EGBN flip-pause
# ruling — a 7.68-9.98 ATR excision electing a stale box is the over-reach
# this kills). Calibrated between BODI's progressive chain (0.86 -> 3.34 ATR,
# must pass) and the EGBN class (must refuse).
BAND_EVENT_MAX_DEPTH_ATR = 5.0
# Duration cap on one merged below-rail event: an episode is penetration ->
# reclaim -> hold, bounded in time — a run below the rail lasting months is a
# markdown leg, not a shakeout (EGBN's stale April framing rode a 40-bar
# "event"; BODI's real episodes run 12-18 bars). 2x the respect gate's own
# MAX_CONSECUTIVE_OUTSIDE_DAYS.
BAND_EVENT_MAX_BARS = 20

# --- Story-rescue LAST-RESORT pool (Event Map program Task 8, dark) ----------
# Consulted ONLY when the strict, rescued, AND band pools are all empty, so an
# ordinary election can never move (the BAND_RAILS insertion pattern). A pair
# is admitted on the RULED narrative form (operator ruling 2026-07-25, census
# Option A; canonical spec in strategy_alpha.md "The rail-episode read"):
# >= 2 completed support tests + terminal resistance posture + no terminal
# support drift, read AS-OF the judged window's last bar
# (event_map.story_admission). The form replaces ONLY the occupancy-family
# judgment — width/window/respect/crash run unchanged, and the traversal gate
# judges the returned pool (measured: traversal kills 30/69 junk occupancy
# deaths; the form is not asked to carry them alone). Target class: EGBN
# (S+ S+ S+ R^) vs the drift-junk zero-completed-episode twins (DGII/FLG).
# LIVE 2026-07-26: operator chart eyeball passed both A/B conversions (NKTR
# rails/box confirmed; YPF confirmed pre-breakout — broke out, LPS'd
# 05-12..05-15, then broke out truly). Ratchet resealed 26 -> 28
# (docs/flag_ledger.md row Retired; evidence docs/event_map_program_2026-07.md).
STORY_POOL_ENABLED = True

# --- Contraction-rescue lane (miss program 2026-08-28; DARK) ----------------
# When the WHOLE root walk elects nothing (full refusal — never after a
# cause-before-effect abstention), read_structure re-walks ONCE with the
# species resistance-contraction form armed inside the story pool
# (event_map.resistance_contraction_admission — the operator ruled its
# EGBN/PKE conversions real, 2026-08-19). Scoped to full refusals by
# construction: it can never displace an existing election or re-frame a box,
# which is exactly what refused the global POWER_PLAY_STORY_FORM_ENABLED flip
# (the WCC 2.2x-wider re-election). A rescued fire stamps
# elected_pool='story' with the self-naming contraction profile. Flip =
# operator decision vs the miss-program A/B (docs/miss_program_2026-08.md);
# flipping re-seals the marks ratchet (EGBN/PKE leave the expected-miss list).
CONTRACTION_RESCUE_ENABLED = False

# --- Near-miss lane — the RULED one-leg-narrow form (Task 6 ruling) ----------
# Measurement constants for the operator-ruled near-miss predicate
# (engine_alpha.structure.gate_margins.ruled_near_miss; ruling record
# docs/near_miss_lane_2026-07.md §5, 2026-07-26): taxonomy T-COARSE-8 (the
# eight occupancy checks judged as ONE concept; crash IN as its own leg;
# policy stages never legs), narrowness = every failing fine leg within
# NEAR_MISS_MAX_QUANTA native quanta, float-quantum legs within their
# junk-calibrated decile deficits (census §4, sealed 2026-07-26 — junk
# 10th-percentile deficits on width / crash / traversal_density). These are
# TELEMETRY constants: nothing here gates, scores, or moves a rail; a
# re-ruling changes them (new lane ruleset + manifest rotation), never tuning.
NEAR_MISS_MAX_QUANTA = 1
NEAR_MISS_WIDTH_DEFICIT_MAX = 0.0081
NEAR_MISS_CRASH_DEFICIT_MAX = 0.0083
NEAR_MISS_DENSITY_DEFICIT_MAX = 0.011

# LIVE 2026-07-27 (near-miss lane Task 7) — the refusal collector: a
# numbers-only, per-evaluation recorder on the outer Phase-B consultation seam
# (never the inner-box calls, never the diagnostic mirror). Records every gate
# refusal's kill-site tuple keyed on the framing identity; a near-miss NEVER
# scores, never fires, never enters the picks — telemetry for the archived
# cohort + review report only. Flag-off is byte-identical and compute-free.
# Flipped on the §6b re-measured A/B: all three pre-registered bounds FAIL
# (p50 +7.10ms / p95 +57.97ms / wall +2.96%); overrun ACCEPTED by the operator
# ("3% aint a biggie"). The flip HARDENS ruleset 2026-07-26.A + the per-pool
# grain (docs/near_miss_lane_2026-07.md §5/§7).
NEAR_MISS_LANE_ENABLED = True
# Recording-shape knobs (Tasks 8/9; manifest-listed with the flag so a change
# partitions the cohort by engine seam). Sized from the Task-4 counters
# (docs/near_miss_lane_2026-07.md §3: one-leg median 5 / p90 137 per
# evaluation; ruled junk density ~1 per corpus frame). Every cap drop is
# COUNTED and reported — a silent cap reads as "covered everything".
NEAR_MISS_TOP_K = 32            # deferred full-vector completions per evaluation
NEAR_MISS_WRITER_TICKER_CAP = 8     # cohort rows persisted per ticker per night
NEAR_MISS_WRITER_GLOBAL_CAP = 200   # cohort rows persisted per scan night

# DARK (solve-the-engine task 13) — stale-frame dethronement: a
# rescue-propped framing whose buffered R the tape has left FULLY behind for
# the trailing N sessions loses the election in favor of a later valid
# framing (MATX: stale spring boxes blind the fresh shelf). The sibling
# rescued-pool arbitration lever was built and REJECTED (it killed VIK's
# pinned corpus hit; see box_primitives — the shelf-R lesson at election
# scope).
# Live flip operator-granted 2026-07-16 (solve-the-engine flip checklist #4).
ELECTION_DETHRONE_ENABLED = True
ELECTION_DETHRONE_SESSIONS = 10   # matches the respect gate's own outside-run cap

# ── Election stability — persistence under backward eval-day shifts ─────────────
# Measure-only probe on FIRING setups (engine_alpha/stability.py): re-run the
# eval-twin prep + the structure election alone at D-1..D-k on the same raw frame
# and ask, via the one cross-frame identity predicate, whether the SAME reading
# elects. Real structures persist; junk flickers (BODI's band pair exists 04-15,
# dies 04-16; VLO's read 07-07, not 07-08). Never a gate, never a score: emits
# only underscore diagnostics (_stability_same_frac / _streak / _probes).
# Flag-off is byte-identical with ZERO new compute (import + computation live
# inside the flag). Flip is operator-gated on the measured cost bound (EC-8).
ELECTION_STABILITY_ENABLED = False
ELECTION_STABILITY_LOOKBACK = 3   # backward shifts probed (D-1..D-k); election stage only

# ── Election-trace export — the walk's narration, published (Surface the Read) ──
# read_structure's own trace (every root tried, every candidate pair's gate
# verdict — the explainability rule) captured during the SAME election that
# fired and summarized engine-side (trace_export.py) to a compact date-anchored
# story: per-root refusal counts + how far the best candidate got + the elected
# framing's provenance. The RAW trace never leaves the engine (measured
# 2026-08-04 on 40 real fires: median ~106 KB, p90 3.6 MB per ticker). Archived
# raw on every fire (election_trace TEXT, NULL = never captured, no backfill)
# and served in the payload narrative block. Changes NO election, gate, or
# score — capture cost only, measured +20.3 ms per evaluated ticker
# (~+111 s per full US-Stocks scan); the flip is gated on that bound
# re-measured in the scan-metrics evaluation phase (EC-8).
ELECTION_TRACE_EXPORT_ENABLED = False

# ── The strategy read — held-through-correction, measure-first (dark) ────────
# Two RAW campaign-context measures per fire (structure/strategy_read.py):
# how deep the base floor cut below the resolved climax high
# (strategy_correction_depth_pct) and whether that floor held at/above the
# automatic reaction's low (strategy_floor_above_ar). Never gates, never
# scores; NULL = never measured; a ruled judgment over these is a LATER
# calibration against the live archive, not an add-time threshold. Reads only
# facts the walk already resolved — two array lookups per FIRE, expected
# evaluation-phase delta ~0 s; the flip still requires the ScanTimer
# re-measure on a real nightly scan (EC-8).
STRATEGY_READ_ENABLED = False

# ============================================================
# 4. PHASE C — SPRING
# ============================================================
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

# ============================================================
# 5. PHASE D & LPS
# ============================================================
# Phase B->D divider from the V-tip (display only). Separate from the Phase-C
# spring gate above: ANY recovered late-base low (even a shallow one that is NOT
# a true spring) is still the tip of the final 'V' and marks where the right-side
# markup begins ("Phase B ends here, Phase D starts here"). We're good at finding
# the tip even when small, so we repurpose it for the boundary, not a spring tag.
PHASE_D_VTIP_LATE_FRACTION = 0.35  # only look for the tip in the late part of the base
PHASE_D_VTIP_RECOVERY_BARS = 6     # a higher High within this many bars = it recovered

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
LPS_MAX_WINDOW_BOX_RANGE = 0.85   # LPS should be a support test, not span most/all of the box
# DARK (solve-the-engine task 10): for OVERSHOOT_R windows (breakout
# throwbacks resting ABOVE R) the window-localization denominator becomes
# max(box_height, LPS_OVERSHOOT_WINDOW_ATR_MULT * ATR) — above the box, box
# height is the wrong yardstick for a NARROW base (CTOS: his marked shelf is
# 1.06 box-heights but only 1.42 ATR). Scoped to one zone; max() can only
# grow the denominator, so wide boxes and other zones are untouched.
# Live flip operator-granted 2026-07-16 (solve-the-engine flip checklist #3).
LPS_OVERSHOOT_WINDOW_ATR_ENABLED = True
LPS_OVERSHOOT_WINDOW_ATR_MULT = 2.0   # k*ATR floor: k >= 1.67 admits CTOS; 2.0 = margin
# "Reaction not markup" gate for the rising_support_shelf rescue (default OFF =
# None). The rescue (engine_alpha/structure/lps.py) re-admits a non-terminal-low window
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
# shelf). ENABLED + committed in 232afd0 ("Enable LPS calibration: rescue-markup
# gate 0.21 + hold tolerance 0.95") and blessed for engine-alpha (see
# flag_ledger.md); revert to None to disable. Midpoint of winner-max +0.096 and
# the run-up cluster +0.324; SPCB (+0.234) was the lone borderline.
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

# ── Cause before effect, Phase C -> Phase D: the LPS may not open before the
# spring (LIVE from birth 2026-08-09; doctrine-gate repair, invariant C6) ──
# The LAST point of support cannot predate the shakeout that conducts the turn.
# The narrative already floors the Phase-D REGION at the spring recovery
# (phase_d.resolve_phase_d_boundary) — only the elected LPS brick, the
# mandatory Phase-D evidence, was unfloored. When set, read_structure passes the
# spring TIP as the LPS window floor (the tip, not the recovery: an LPS window
# may legally OPEN on the spring low — that is the sanctioned undercut_rebound
# form — it just may not open left of it).
# The defect this repairs (KYMR, live payload 2026-08-08/09): the elector picks
# the latest window whose trigger is still overhead, with no chronology floor, so
# when the true post-spring LPS is already triggered it reaches BACK past the
# spring for a stale window. KYMR's "LPS" rested at 104.32 on 07-30; price then
# fell to 99.52 on 08-03 (the elected spring, 1.06 ATR under S) — support that
# broke, elected as the last point of support, 8 bars before its own cause.
# Blast radius is provably the C6 violator set: the floor only REMOVES
# candidates, and the elected window is the argmax, so an election that already
# satisfies tip <= lps.start cannot move. Fleet census 2026-08-09 (256 setups /
# 69 with a spring): lps.start - spring.tip is positive on 68, minimum +2, median
# +21 — KYMR at -8 is the sole violator and sits 10 bars clear of the nearest
# legal read, so the floor clips no sanctioned form.
LPS_AFTER_SPRING_ENABLED = True

# ── Holding-shelf LPS completion form (Event Map Task 8) — DARK, default OFF ──
# The SECOND completion form of the two-form LPS doctrine (Wyckoff: the back-up
# is "a simple pullback or a new TR at a higher level"; see
# docs/lps_final_structure_canon_2026-07-10.md): a short flat-or-descending rest
# HOLDING HIGH in the structure, judged on GEOMETRY ONLY. Consulted inside the
# one detect_lps window scan wherever the pullback-and-rest form rejects at its
# depth or volume-dry-up judgments; every machinery gate (shape march, zone
# bounds, window range, high-extension, spread, hold, post-window hold) still
# binds both forms. A shelf-saved window carries swing_type "holding_shelf" and
# a volume-free quality; cross-form election ties break on an integer form rank
# (pullback wins), never on float quality. Flag-off consults nothing —
# byte-identity is structural. Calibration: the operator's marked WTS + PBT
# shelves (frozen marks corpus; probe 2026-07-10 — WTS dies on the OVERSHOOT_R
# depth floor + a 0.87-vs-0.85 volume margin, PBT on volume alone at 1.40x).
# Live flip operator-granted 2026-07-16 (solve-the-engine flip checklist #1).
LPS_HOLDING_SHELF_ENABLED = True
LPS_SHELF_LENGTH_MIN = 3          # a 2-bar pause is not a shelf; marked shelves run 3-5 sessions.
                                  # The 3->2 move was ATTEMPTED 2026-07-17 (flip checklist #5,
                                  # would convert VCTR) and REVERTED at the flip battery: KWR
                                  # (tier B) + FLG (tier S) — labeled dead-space must-NOT-fires —
                                  # both fired via 2-bar shelves; at n=2 the monotone axis is one
                                  # comparison and carries no real discrimination. Do not
                                  # re-attempt without a shelf predicate that discriminates at
                                  # n=2 (the negative corpus is the arbiter).
LPS_SHELF_MIN_LOW_POS_BOX = 0.5   # shelf low at/above the box midpoint — the canon position test
                                  # (SMI: the back-up completes between the range's halfway point
                                  # and the broken resistance; IBD: handle midpoint above the base midpoint).
                                  # Flat-and-LOW is the named failure geometry, never sanctioned.

# Drawn-LPS trim (DISPLAY-ONLY, recall-safe): the offset into the elected LPS
# window where its DRAWN zone starts (phase_d.drawn_lps_zone_start via
# scope_consolidation) — a rising shelf's window includes the climb INTO the
# shelf, so the drawn gold box is trimmed forward to the longest down/sideways
# suffix (low-descent fraction >= this; a pure reaction is 1.0, sideways ~0.5,
# an up-swing <0.3). Separate knob from LPS_MIN_DESCENT_FRAC so the
# recall-sensitive election is untouched.
# The drawn prior-test STAIRCASE this knob also filtered was RETIRED 2026-08-09
# (operator ruling: ONE drawn LPS per setup — the chronological terminal one in
# Phase D). The raw staircase (detect_lps_tests) still feeds the Phase-D
# boundary evidence and the LPS-shrink measurement; it is just never drawn.
LPS_DRAW_MIN_DESCENT_FRAC = 0.40

# Zone gate — LPS low must sit in one of 3 zones relative to the box:
#   INSIDE        : S <= low <= R
#   OVERSHOOT_R   : R < low <= R + k*ATR       (backtest of breakout)
#   UNDERCUT_S    : S - k*ATR <= low < S       (spring)
LPS_ZONE_ATR_MULT = 0.5

# ── The final method, build step 2 (Sun 13/09/2026): the ruled stack behind ──
# ── flags, DARK (every flag default OFF; flag-off is byte-identical).       ──
# The operator's rulings R1 and R7 to R18 (docs/decisions.md, 2026-09-05 to
# 2026-09-12), each as it was MEASURED in process on his 37 LPS windows, the
# junk corpus and the fleet fixture (rulings ledger, rulings_ab2 to ab8). One
# flag per ruling SITE so each can be measured and flipped alone; the values
# are placed from his drawings, never tuned. Every name here rides the engine
# manifest so a flip rotates engine_config_version from day one.
#
# R1 (respect): a bar is OUTSIDE the box only when the WHOLE bar sits beyond
# the rail area (low above R + area, or high under S - area); a poke or a
# straddle is respect. Today a wick beyond the area counts as outside.
RESPECT_WHOLE_BAR_ENABLED = False
# R13 (the bar is the unit of dwell; graded): the two close-dwell legs of the
# occupancy exam never refuse a box (their values stay measured facts).
DWELL_GRADED_ENABLED = False
# R11 (hand-over): the break-above-R rescue keeps an old box only while the
# last close sits within this many daily ranges above its R (today: within
# 15% of PRICE, EXTENSION_FILTER_MULT). Measured: PBT's exact box, EWTX's
# January box, at no fleet cost.
BOX_HANDOVER_RANGES_ENABLED = False
BOX_HANDOVER_MAX_ABOVE_R_ATR = 1.5
# R17 (Phase C): a noticeable dip under support that recovers shortly. The
# box-height depth cap (BIN_C_UNDERCUT_BOX_MAX) and the late-half rule
# (BIN_C_LATE_BOX_FRACTION) both refused his own SYRE spring and are lifted;
# depth stays bounded by BIN_C_UNDERCUT_ATR_MAX (3.0 ranges).
SPRING_BOUNDS_LIFTED_ENABLED = False
# R8 + R12 (the LPS in daily ranges): the three box-height clauses of the LPS
# read re-cut to daily ranges, placed from his 36 windows (max height 2.43,
# above-R launch max 2.40), and the zone's R-side ceiling at 1.35 ranges (his
# farthest above-R LPS low: ST at 1.30; "Lets go with that ceiling 1.35").
LPS_RANGES_YARDSTICK_ENABLED = False
LPS_WINDOW_SPAN_ATR_MAX = 2.5        # window height, wick to wick (was 0.85 box heights)
LPS_LAUNCH_ABOVE_R_ATR_MAX = 2.5     # an INSIDE window's poke above R (was 0.35 box AND 0.75 ranges)
LPS_SHELF_ABOVE_R_ATR_MAX = 1.5      # the resistance shelf's close lift above R (was 0.35 box)
LPS_ZONE_CEILING_ATR = 1.35          # the LPS zone's ceiling above R, in ranges (floor: the zone tolerance)
# R9/R9b + R15 (the LPS is defined by graded traits): rest-on-its-low, the
# markup-leg test, the depth minimum, the bar-spread cap, the final-spread
# expansion cap and every volume ask stop refusing (their values stay facts;
# quality is volume-free). What stays a refusal is the story position, "it
# must be a PULLBACK": the window's high comes before its low, the dig from
# the first high to the window low is at least 0.70 ranges (his minimum
# 0.71), and the last day's high is not back at the first high (R15: read on
# the HIGH; his 36 windows: last high <= first high + 0.25 ranges, WTS 0.21).
LPS_GRADED_TRAITS_ENABLED = False
LPS_CORRECTION_DIG_MIN_ATR = 0.70
LPS_CORRECTION_LAST_HIGH_MAX_ABOVE_FIRST_ATR = 0.25
# R18 + the sixteenth sitting (one window per read day): a receding day makes
# a lower high OR a lower low than the day before (his 37 of 37); the window
# is the last run of receding days with the day before the run as its top,
# it ends ON the last receding day of the frame, the trigger is that day's
# high, and a window may not end on a breakout day (a close more than 0.10
# ranges above the prior day's high; his 36: at most +0.06). The 2..7 length
# enumeration goes; length is archived. One-day runs are legal.
LPS_WINDOW_RECEDING_ENABLED = False
LPS_BREAKOUT_DAY_CLOSE_ABOVE_PRIOR_HIGH_ATR = 0.10
# The narrow buy-day clause (his Q9 default): the "still live" test reads the
# HIGH. Once a later day's high crossed the trigger the setup was bought and
# shows nothing, even when that day closed back under the trigger.
LPS_BUY_DAY_READS_HIGH_ENABLED = False

# ── The final method, build step 3 (Sun 13/09/2026): LPS refusals to grades, ──
# ── DARK. His points 18, 19 and 20 in ONE flag (docs/final_method_2026-09.md). ──
# 18: no refusal on the support side. The LPS low's position is a fact (JAZZ's
# low sits 0.67 ranges under S and the next day is the buy); the zone word on
# the support side is typed by the window's CLOSES ("JAZZ's LPS is ON support:
# closes above S, only wicks poke under ... typed by the window's bars, never
# its lowest wick"), and the tight-box widening in percent of price goes with
# the floor it served. The ceiling above R stays (R12).
# 19: the three post-window checks go (the close 5 percent under the LPS low,
# the post-window low test, the post-window spread test): under one window per
# read day there is no post-window day to check. The depth cap in profile units
# goes with them; the window height in ranges is the one "too deep" refusal left.
# 20: volume never refuses and never elects (quality is volume-free); the ratio
# stays a fact on the card. No points is the grade ledger's job (step 12).
LPS_REFUSALS_TO_GRADES_ENABLED = False

# ── The final method, build step 4 (Sun 13/09/2026): the ONE turn line, DARK. ──
# His points 1 and 2 (docs/final_method_2026-09.md): one line over the WHOLE
# chart, ONE floor of TURN_LINE_FLOOR_ATR daily ranges, wick to wick, no
# retracement ratio; the first bar is a turn by its shape and the running
# extreme at the right edge is a FORMING turn, so the line carries no edge
# mask and no five-day right-edge reserve. Named events stay turns by law
# (the LPS valley, the trigger cross) wherever a caller asks for them.
#
# MEASURED on his 35 drawn marks (186 named turns: both rail anchors, every
# LPS peak and low, every spring and spring-test tip, every SOS peak):
#   today's order-1 walk + the 15 percent collapse   112 of 186,   0 of 35 marks complete
#   the line at 0.75, one range from the read day    183 of 186,  32 of 35
#   the line at 0.75, each day's OWN range           186 of 186,  35 of 35
# The three the read-day unit misses are S anchors two years back, where one
# range from the read day is the wrong unit; hence the per-bar floor. Extra
# turns inside his boxes: about 8 per 10 trading days (today's walk: 3).
#
# One flag per SITE so each can be measured and flipped alone. The box
# election is deliberately NOT a site: it stays on today's skeleton until
# build step 10.
TURN_LINE_ENABLED = False          # the event map's swing layer reads the line
TURN_LINE_TREND_ENABLED = False    # the HH/HL/LH/LL trend labels read the line
TURN_LINE_FLOOR_ATR = 0.75         # his floor, in daily ranges, wick to wick

# ── The final method, build step 5 (Mon 14/09/2026): the words on the line, DARK. ──
# His points 11 to 15 (docs/final_method_2026-09.md): a MEASURE-ONLY reader
# (engine_alpha/structure/line_words.py) over the one turn line, the elected
# rails, the elected LPS and the mini. Nothing that elects, vetoes, grades or
# displays reads it; each flag only adds its own word to ONE JSON diagnostic
# on a fire (_line_words_json). The words read the line whatever
# TURN_LINE_ENABLED says, so they flip with or after it. Not built: the
# upthrust (10: its collapse test is unplaced, he has drawn none), the
# shakeout (parked by him), the dead-space pardon keyed to a named leg (21:
# a grade change, his question still open).
#
# MEASURED on his 35 marks, his rails, fed his drawn LPS windows
# (python -m tools.word_recall; a hit is within one trading day; CHANCE is
# the same score with his day moved three trading days either way):
#   a thrust at his SOS top   25 of 26 (chance 12)   THE SOS  15 of 25 (chance 1.5)
#   last supper               10 of 10 (chance 1)    Phase C   8 of 10 (chance 0)
#   spring test                3 of 6  (chance 1)    mini      0 of 5
# Under all five flags nothing moves: ratchet 30 of 35, junk the identical
# 8 of 16, fleet and reader pin PASS. The rules' defaults that are mine (his
# word owed) are listed in line_words.py and the decisions record.
LINE_WORD_SOS_ENABLED = False          # 11: every thrust, and THE SOS by the LPS after it
LINE_WORD_LAST_SUPPER_ENABLED = False  # 15: the last supper, in hindsight only
LINE_WORD_PHASE_C_ENABLED = False      # 14: one Phase C per box, and its spring test
LINE_WORD_PHASE_D_ENABLED = False      # 12: where the right side opens
LINE_WORD_MINI_ENABLED = False         # 13: today's elected mini, as facts
LINE_WORD_AREA_ATR = 0.5               # the ruled rail area, in daily ranges (as TOUCH_TOLERANCE_ATR, MINI_POSITION_TOL_ATR)
LINE_WORD_SOS_MIN_GROUND_ATR = 1.70    # his smallest SOS, launch low to top, on his own spans
LINE_WORD_SUPPER_DIG_ATR = 1.5         # a last supper digs this far (his ten: 1.75 to 3.76); a pause this deep ends a thrust
LINE_WORD_SUPPER_MAX_DAYS = 4          # his longest last supper, in trading days

# Spread rules (core quality signal):
# Final LPS bar range must be < P-percentile of bar ranges across the base.
# 0.5 = median ("less than most bars in consolidation"); 0.33 stricter.
LPS_RANGE_PERCENTILE = 0.5
LPS_SPREAD_MUST_DECLINE = True    # Declining final spread earns full quality; widening is discounted, not gated

LPS_VOL_CONTRACTION_MAX = 0.87   # LPS avg volume must be <= 87% of 50d avg. Moved 0.85->0.87
                                 # 2026-07-17 (operator grant, flip checklist #6; converts AGCO
                                 # at its 0.87-vs-0.85 margin). Archive evidence (1,679 matured
                                 # episodes): outcome quality is FLAT up to the old edge
                                 # (0.80-0.85 band n=174, +6.7% mean 20d, 80% win) — no cliff;
                                 # deeper dry-up is not better in this archive. 0.88+ stays
                                 # rejected (companion pin in tests/test_lps.py); Vol_50 gained
                                 # a non-finite refusal guard in the same change.

# ============================================================
# 6. SCORING & TIERS
# ============================================================
# Tier thresholds — calibrated against the live archive distribution
# (avg ~95, max ~126 under prior weights). With the 52w-high proximity
# bonus added, S sits at roughly the top quartile rather than catching
# 75% of all setups.
# (The legacy raw-sum cuts TIER_S/A/B/C retired with the legacy ladder at the
# 2026-08-22 consolidation — decisions.md row of that date.)

# The tier ladder on the TA-grade's 0-100 scale (flip 2026-08-09):
# `Tier` is derived from `ta_grade`, not from the raw ~122-point sum. It
# retires. Operator-chosen from the A/B on the 2026-08-09 scan (256 fires,
# grades 35.5-76.3, median 59.0): "lets do 62 /52 /42".
# Why 62 and not the count-preserving 61.5 — 61.5 reproduced the old S
# population exactly (92 names) but sat 0.19 points above the next grade, a
# knife edge that reshuffles on any scan; 62 is stable and costs 7 S names.
# On that scan the ladder reads S=85 / A=118 / B=41 / C+D=12.
# TIER_C_STRUCT continues the operator's own 10-point spacing (D was empty on
# the A/B scan under any candidate cut, so nothing rode on it).
# The S_MAX_BOX_WIDTH cap still applies ON TOP: it is the operator's rule that
# a wide base is never elite, and the A/B showed it is what holds 22 of 111
# A-tier names out of S — including AAP, the 4th-highest grade on the scan at
# 0.151 box width against the 0.15 cap.
TIER_S_STRUCT = 62
TIER_A_STRUCT = 52
TIER_B_STRUCT = 42
TIER_C_STRUCT = 32
# Below TIER_C_STRUCT = Tier D

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
# box is discounted toward the floor (a GRADE, never a veto). LIVE since 2026-07-04 (operator
# eyeball A/B: 61/128 choppy bases docked, mean -0.39, 0 tier flips; clean bases preserved at
# grade 1.0). Missing texture -> neutral 1.0.
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
# break above R that TESTS the rail and HOLDS. Two box-relative bounds keep markup out of the SOS
# bucket so it stops over-firing in active/extended boxes (AMRZ fired ~15 SOS):
#  (1) NEAR R — the wave-top peak must sit near R (peak_box_pos <= SOS_NEAR_R_MAX_BOX); a reach
#      far above R (AMRZ pkPos 2.0-2.4) is post-breakout MARKUP, typed `markup`, not SOS.
#  (2) REAL HOLD — the post-top hold window must be a genuine mini-consolidation (its High-Low
#      span <= SOS_HOLD_MAX_RANGE_BOX of the box), not merely "no drop to the low-zone in N bars".
# Both are box fractions so they scale across the universe; operator-eyeball-tuned.
SOS_NEAR_R_MAX_BOX = 1.5        # wave-top box_pos ceiling for an SOS (1.0 = R; > this box-frac above R = markup)
SOS_HOLD_MAX_RANGE_BOX = 0.55   # post-top hold-window High-Low span as box fraction to count as a consolidation
# E3 setup-quality graded sub-score — wires the L2 assembled Wyckoff story (assemble_box_narrative,
# read on the engine's OWN elected box) into the score as ONE additive, BONUS-ONLY term: a single
# [0,1] composite * cap. Grades-not-vetoes: it can only RAISE a score, never gate /
# reject / touch firing (a missing/None narrative grades neutral 0.0). completeness and
# chronology are CORRELATED (intact => full spine), so they combine into ONE composite
# (not two terms). LIVE 2026-07-04 (operator A/B eyeball: 128/128 fires lifted, mean +4.5,
# 22 tier flips); the forward-return validation stays a revisit (~07-15+ data).
SCORE_SETUP_QUALITY = 8.0      # cap for the setup-quality sub-score (~half a tier gap; sibling of SCORE_ADR/BREADTH)
SETUP_QUALITY_W_COMPLETENESS = 0.70    # composite weight on completeness/4 (0..4 distinct pieces present)
SETUP_QUALITY_W_CHRONOLOGY = 0.30      # composite weight on the chronology factor (weights sum to 1.0 -> composite in [0,1])
SETUP_QUALITY_CHRONO_PARTIAL = 0.50    # chronology factor: intact=1.0, partial=this, absent=0.0

# ── Event Map — whole-chart event read (docs/archive/PLAN-event-tape.md, stage 1) ─
# Fire-path staging of the Event Map (engine_alpha/structure/event_map.py): compute the
# stamped mechanical swing map + the narrative-role labels for FIRING setups only,
# reusing the elected bricks (spring/lps) — the story-read placement, dozens of
# tickers a night. MEASURE-ONLY and additive: gates nothing, scores nothing, moves
# no rail; emits only underscore-prefixed diagnostic fields (never canonical).
# Flag-off is byte-identical with ZERO new compute (import + computation live only
# inside the flag). FLIPPED LIVE 2026-07-25 (Event Map program Task 13, operator
# grant at the program scope gate): fires-only, canonical outputs untouched (the
# map-ON parity contract — only archive columns gain values), cost measured
# median +2.2 ms per firing ticker incl. the rail-episode substrate (Task 12).
# The flip is the archive family's FIRST SEAM (engine_config_version rotates).
# The chart-overlay payload still arrives in a later Event Map stage.
EVENT_MAP_ENABLED = True

# ── Technical Analysis Score v2 (hybrid / dynamic, 0-100) ───────────────────────
# Master flag for the Visual "Technical Analysis Score" rework (docs/archive/specs/ta-score-rework.md):
# folds the sub-scores AND the setup-tags into one hybrid 0-100 grade with the tier derived
# from it, and demotes market regime (breadth + SPY) to an informational label. Same flag-OFF
# discipline as the retired PUZZLE_SCORE_ENABLED / CANDLE_SPREAD_AWARE keys (folded 2026-07-18):
# flag-OFF the entire v2 formula and any new keys are inert (byte-identical, zero new
# compute); the ON behavior lands incrementally behind
# this flag. The live flip is an operator A/B-eyeball decision.
# FLIPPED LIVE 2026-08-09 on the operator's A/B eyeball of the 2026-08-09 scan
# (256 fires, the first archived under the merged code so setup_quality was
# measured on every row — the 2026-08-08 read's ±31 movers were entirely the
# missing-term artifact and are gone). Movement at these weights is median 0 /
# max ±2 ranks BY DESIGN: the story caps stay 0 and the warnings stay 1.0, so
# the flip re-expresses the existing read on a 0-100 scale with chapters and
# re-bases the tier ladder — it does not change the judgment. Those caps are
# deliberately NOT set here: their sub-scores are flag-gated, so the archive
# holds no live values to calibrate against yet; the flip starts that archive
# and the operator sets real costs later against it (measure-first).
# TA-grade v2 vocabulary pre-registrations (2026-08-08, build task 1 — ONE
# batched engine_config_version seam; registration only, scores byte-identical):
#  - SCORE_SPRING: the spring term's point cap. The term itself lands with the
#    v2 composite (shape port of the stale ta-score-v2 branch); 0 = shape-only
#    until the operator's A/B eyeball assigns weights (weights move LAST).
#  - The three named slopes promote the scorer's last hidden in-code literals
#    (touches * 2.0 at scoring.py touch density; the * 2 saturation slopes on
#    lps_tightness / vol_contraction). WIRED 2026-08-20 — until then they were
#    inert and the literals were authoritative. There is only ONE site per
#    slope: the shared score_setup term, which the v2 grade re-reads out of
#    sub_scores, so the promotion covers both paths at once. It was
#    byte-identical because every declared value equalled the literal it
#    replaced (2.0 vs 2.0, 2.0 vs 2, 2.0 vs 2), which is also what keeps
#    flag-off byte-identical. Turning one now MOVES the reading on both
#    paths — treat it as a weight (operator A/B, engine_config_version).
# FROZEN AT 0 by the 2026-08-12 ruling — a spring is a MARK, not a grade. The
# term moved to taxonomy layer 'marker', so it is off the ta layer entirely and
# this cap can no longer reach the grade even if it were raised. There is no A/B
# coming for it; raising it does nothing.
SCORE_SPRING = 0                  # spring term cap — marker layer, never graded
TOUCH_POINT_RATE = 2.0            # points per rail touch (v1 literal: touches * 2.0)
LPS_TIGHTNESS_SLOPE = 2.0         # saturation slope: full credit at tightness_ratio <= 0.5
VOL_CONTRACTION_SLOPE = 2.0       # saturation slope: full credit at vol_contraction >= 0.5
# Story terms + warnings (task-4 batch — the build's third declared seam).
# The story terms grade the Event-Map substrate INSIDE the chapters (operator
# ruling 2026-08-06: grade the setups by their story). All caps start 0 =
# shape-only (weights move LAST, at the operator's A/B eyeball); the anchors
# are provisional calibration references recalibrated against the live archive
# at the A/B — the measure-first pattern, never gates, never penalties.
SCORE_STORY_S_TESTS = 0            # completed support tests (Consolidation chapter)
SCORE_STORY_R_REJECTIONS = 0       # completed resistance rejections (Consolidation chapter)
SCORE_STORY_ALTERNATIONS = 0       # rail alternations across completed episodes (Consolidation chapter)
SCORE_STORY_TERMINAL_POSTURE = 0   # right-edge R-engagement stance (Phase-D chapter)
STORY_COMPLETED_TESTS_FULL = 3     # rail-test count at saturation (EGBN separator: 3 completed S-tests vs drift junk 0)
STORY_ALTERNATIONS_FULL = 2        # alternation count at full credit
STORY_UNREADABLE_NAN_BARS = 5      # all-zero counts with >= this many NaN bars read ABSENT, never zero
# Zero-by-GEOMETRY is the NaN leg's sibling (LEVI 2026-08-10): the episode
# zones are ATR-fixed (2 x TOUCH_TOLERANCE_ATR of box height between them),
# so on a box tighter than ~2 ATR they swallow the neutral middle and distinct
# tests merge into one unresolved visit — all-zero counts on a chart that
# consolidated cleanly. Coverage >= this floor (zones eat half the box; the
# neutral strip is thinner than one average bar) with all-zero counts reads
# ABSENT, never zero. Scan evidence 2026-08-10: sub-2-ATR boxes average 2.57
# completed events vs 4.72+ above — monotone in coverage. NONZERO counts stay
# evidence at any coverage (FXNC read 5 completed at 0.66).
STORY_UNREADABLE_ZONE_COVERAGE = 0.5  # touch-zone fraction of box height at which all-zero counts read ABSENT
# ── The ONE-Event-Map manifest rotation (Task 12, 2026-08-30) ────────────────
# Four reader-behavior constants promoted from module level into the frozen
# manifest in ONE declared epoch. Three moved VALUES UNCHANGED; the fourth,
# MINI_POSITION_TOL_ATR, moved AT its ruled new value 0.5 (was 1.0 at module
# level) — that value change IS the declared 2026-08-30 rail-area seam, with
# its own baseline recapture, not a refactoring passenger.
# They decide what the archived sentences MEAN, so a future edit must rotate
# engine_config_version; at module level it silently would not have.
EPISODE_MAX_GAP_BARS = 2      # episode merge horizon: same-rail visits <= this many inside bars apart are ONE episode
EPISODE_DRIFT_MIN_BARS = 3    # an open terminal S episode at least this long reads as drift
EVENT_HOLD_MIN_BARS = 6       # the wave/test hold-confirmation window (was box_events._EVENT_HOLD_MIN_BARS)
MINI_POSITION_TOL_ATR = 0.5   # the mini-consolidation position band, in candidate ATRs — the RULED ±0.5-ATR rail area (decisions.md 2026-08-30)
# Warnings are floored multiplicative discounts applied to the bounded 0-100
# (never the raw sum); a missing warning input is factor 1.0 EXACTLY.
# terminal_drift is the first registered warning — neutral 1.0 until the A/B.
TA_WARN_TERMINAL_DRIFT = 1.0       # discount when the window ends in an open S-drift episode
TA_GRADE_WARNING_FLOOR = 0.5       # the warning product never discounts below this factor
# Wave-1 charter measurements (task-7 batch — fourth declared seam). Pure
# folds over data already in hand, fires-only in the shared eval chain
# (unconditional since the 2026-08-22 legacy retirement), archived RAW
# (measure-first: never gating, never weighted until the operator's A/B).
LPS_SHRINK_MIN_TESTS = 3           # fewer usable support tests -> the shrink fraction is ABSENT (1 step quantizes to 0-or-1)
STORY_RICHNESS_FULL = 0.15         # story events per bar at saturation (den floored at MIN_BASE_DAYS)
# Wave-2 charter measurement (task-8 batch — fifth declared seam): ONE bounded
# box-walk on the up-segment-restricted sub-frame producing the Minervini base
# count AND the inter-base width ratio together. Fires-only in the shared eval
# chain (unconditional since the 2026-08-22 legacy retirement).
TREND_BASE_COUNT_CAP = 4           # count saturates where grading value does (Minervini counts bases 1-4)
TREND_BASE_WALK_MAX_ROOTS = 12     # root attempts on the sub-frame (the full HTF walk allows 40 on a whole frame)
# Tag fire-rule thresholds (task-10 batch — sixth declared seam): the
# touch-volume z judgments absorbed from frontend JS (setupTagsData.js
# :32-34) into the ONE registry — values relocated VERBATIM so the flip does
# not silently change which chips fire. The worked-equilibrium density rule
# links to TRAVERSAL_QUALITY_DENSITY_FULL (no more unlinked 0.33 twin).
TOUCH_VOL_Z_NO_SUPPLY = -0.30      # no_supply fires when r_touch_vol_z < this
TOUCH_VOL_Z_SPRING = 0.30          # demand_at_s fires when s_touch_vol_z > this
TOUCH_VOL_Z_HEAVY_R = 0.50         # heavy_resistance fires when r_touch_vol_z > this
# weak_monthly's grade-side disposition (the 2026-08-06 HTF ruling): the chip
# stays in the vocabulary AND registers as a warning discount — neutral 1.0
# until the operator's A/B assigns its cost.
TA_WARN_WEAK_MONTHLY = 1.0
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
# DEMOTED TO MEASURE-ONLY (weight 0) 2026-07-25, operator-authorized: the
# archived sub-score graded HARMFUL on both edge reads (corr −0.19 at n=1977,
# docs/edge_read_2026-07-22.md) — momentum context was hurting the ranking it
# was meant to help. The RAW signal stays archived (yearly_return column) so a
# regime-spanning revisit can re-open the question with evidence.
MIN_STRONG_YEARLY_RETURN = 0.30
MAX_STRONG_YEARLY_RETURN = 0.60   # Saturation point for the ramp
SCORE_UPTREND_BONUS = 0           # was 15 until 2026-07-25

# Soft Relative Strength bonus — additive points for stocks outperforming SPY
# over a 6-month lookback. Not a filter; just rewards leadership.
# DEMOTED TO MEASURE-ONLY (weight 0) 2026-07-25, operator-authorized: HARMFUL
# on both edge reads (corr −0.22 at n=1977 — the worst term in the book). Raw
# signal stays archived (excess_return_6m column).
SCORE_RS_BONUS = 0                # was 15 until 2026-07-25
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
# contraction. Measured by engine_alpha.structure.metrics.measure_contractions over the
# base window; scored as a sub-component. Measure-first — scored, not gated.
SCORE_CONTRACTION = 12            # cap for the contraction-quality sub-score
CONTRACTION_IDEAL_MIN = 2         # Minervini: 2-6 contractions, 3-4 typical
CONTRACTION_IDEAL_MAX = 6
CONTRACTION_FINAL_TIGHT_PCT = 0.03  # final contraction ≤ 3% drawdown → full final-tightness
CONTRACTION_FINAL_LOOSE_PCT = 0.12  # final contraction ≥ 12% → zero

# Ascending support / higher lows (Minervini "tennis-ball action", Qullamaggie
# "higher lows surfing the rising EMA"): are the swing-low valleys stair-stepping
# UP across the base? Measured by engine_alpha.structure.metrics.measure_support_slope
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
# HIGHER-TIMEFRAME (HTF) STRUCTURE CONTEXT
# ============================================================
# The structure engine reads the SAME Wyckoff Trend+Box (A->B->C->D) logic on
# weekly/monthly bars as on daily — "it's all relative and derivative". Its RATIO
# thresholds (MAX_BOX_WIDTH, MIN_BOUNDARY_RESPECT_PCT, ATR/box ratios, traversal
# fractions, LPS profiles) are scale-invariant and transfer untouched; only the
# BAR-COUNT WINDOWS are daily-calibrated. engine_alpha.structure.htf temporarily rescales
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
    # The bottoming-base lane is DAILY-clock only: its ruling and fleet census
    # (2026-08-29, MDT) never measured a weekly/monthly "reclaimed 50-bar mean"
    # — the preset pins it off rather than rescaling BOTTOMING_SMA50_BARS
    # (council review 2026-08-30, McKinney).
    "BOTTOMING_BASE_LANE_ENABLED": False,
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
    # Daily-clock-only lane pinned off, as in the weekly preset above.
    "BOTTOMING_BASE_LANE_ENABLED": False,
}

# ============================================================
# POWER-PLAY SPECIES PRESET (dark — docs/power_play_program_2026-08.md)
# ============================================================
# Operator ruling c029555 (2026-08-14): Power Plays (Minervini; = O'Neil's High
# Tight Flag — see docs/minervini_oneil_canon.md) are WANTED setups. The species
# reads through the ONE cascade under a scoped window override
# (engine_alpha.structure.htf.window_override) — never a forked collector. The
# dict carries ONLY the keys the species moves: the reading clock, and its
# import-time copy PIP_MACRO_MIN_BASE_BARS EXPLICITLY (a bare MIN_BASE_DAYS
# patch would silently leave the macro-bridge overlay on the default clock —
# program Task 1 §D). STRUCTURE_EDGE_SKIP_BARS deliberately stays 5: the edge
# reserve is a data-integrity frame, not a maturity clock.
# THE CLOCK VALUE 8 IS RULED (operator, 2026-08-18 — decisions.md): the census
# evidence (clock 8's elected cohort the only forward-positive: median fwd_20
# +2.8%, 54% winners, n=79) + his 40 sheet rulings (S2: 8/10 of the 8-day
# wait's marginal catch KEPT). Species lane only; everything else stays the
# same. FLIPPED LIVE 2026-08-19 on the operator's word ("flip the power play
# thing... as long as everything works like I asked"), TOGETHER with
# POWER_PLAY_STORY_FORM_ENABLED as the flag-ledger requires — gated on the
# Guided-List ratchet holding 28/33 with both flags ON (it does) rather than on
# the ScanTimer bound, which cannot be measured while the lane is dark: the cost
# instrument only reports when this flag is on. The bound arrives with the first
# nightly scan; if it is too dear, this line is the one-word revert.
POWER_PLAY_PRESET_ENABLED = True   # the lane consults this (program Task 8); LIVE 2026-08-19
POWER_PLAY_WINDOWS = {
    "MIN_BASE_DAYS": 8,
    "PIP_MACRO_MIN_BASE_BARS": 8,
}
# The species STORY form (program Task 6): the resistance contraction — price
# contracting at or above resistance after the pole — as a second NAMED ruled
# form inside event_map's one story admission (named by operator ruling
# 2026-08-18: the record says the behavior, never an invented umbrella word).
# A separate gate from the
# lane chooser above BY DESIGN: the species read toggles it under the ONE
# scoped override (htf.window_override, riding the preset dict) around its
# own election only, so the paying scan's admission can never consult the
# shelf form even after the lane flag flips (a passenger never touches the
# paying read). Provisional form; calibrated by the operator's ruling sheets
# (program Task 4).
# FLIPPED LIVE 2026-08-19 with the preset above (the ledger's "the two flags flip
# together or not at all"). This is the half that reaches the PAYING read's
# admission, so it is the one the ratchet had to clear: Guided List 28/33 held,
# same marks fingerprint, with it ON. The form stays PROVISIONAL — the ruling
# sheets calibrate or re-rule it.
POWER_PLAY_STORY_FORM_ENABLED = False
# The breakout wall's departure yardstick (RULED 1.0, operator 2026-08-18 —
# decisions.md): an episode counts RESOLVED only when a close clears the
# pole peak by this many ATR10 — a close hugging the peak is base-building,
# not a resolution (the drift-up misfile: the old close-above-peak wall
# filed MAN not-watched at every clock while still basing). Evidence: the
# S1 rulings (the departure form keeps all four named anchors, files all
# four junks) + the full-cache A/B (MAN's breakout re-dates to 2026-08-13,
# HIS date, and MAN elects; 903 filings regain their looks; newly-elected
# cohort +2.6% med fwd_20 / 67% win; whole cohort quality preserved).
# 0.0 reproduces the close-above-peak wall byte-identically (kept as the
# legacy branch); species lane + instruments only — no paying consumer.
POWER_PLAY_BREAKOUT_DEPARTURE_ATR = 1.0
# The species precondition (the pole): literature anchors — Bulkowski >=90% in
# <=2 months, O'Neil/Minervini ~100%/8 weeks. The census reads these as its
# screen defaults; the engine lane consults them only behind the flag.
POWER_PLAY_POLE_MIN_GAIN = 0.90    # prior-leg gain floor over the pole window
POWER_PLAY_POLE_WINDOW_BARS = 40   # ~8 trading weeks

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

# ============================================================
# 7. ARCHIVE & TELEMETRY
# ============================================================
# Live archiving — when True, every daily screener run upserts its full output
# (winners AND the setups that later fizzle) into setup_archive with
# source="screener". This is the fuel the calibration/analysis tools need:
# without live non-winners, every outcome metric is biased by the seed gallery.
# Idempotent per (ticker, scan_date); re-running the same day updates in place.
ARCHIVE_LIVE_SCANS = True

# ============================================================
# =================== ENGINE / APP FENCE =====================
# Keys ABOVE this line are engine territory — the reading-model
# knobs, (mostly) frozen into the engine manifest
# (engine_alpha/freeze/manifest.py); changing one rotates
# engine_config_version. Keys BELOW this line are app /
# pipeline / scheduler / alerts knobs. Do not prune across
# this line.
# ============================================================

# ============================================================
# 8. APP / PIPELINE / SCHEDULER / ALERTS
# ============================================================
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
                                 # does NOT change daily behavior (see HTF section below + engine_alpha.structure.htf).
                                 # Renaming the cache file forces a clean cold 5y backfill on next run.
TICKER_CACHE_MAX_AGE_DAYS = 1     # Refresh the ticker universe CSV daily
TICKER_SKIPLIST_FILENAME = "ticker_skiplist.txt"  # One symbol per line; skipped before any Yahoo request
TICKER_ADMISSION_ENABLED = True
TICKER_ADMISSION_FILENAME = "ticker_admission.json"
ADMISSION_MIN_HISTORY_BARS = 200   # Same minimum used by the baseline history gate
ADMISSION_YOUNG_RECHECK_DAYS = 21  # Alive but too young: re-test after it may have gained bars
ADMISSION_EMPTY_RECHECK_DAYS = 7   # No Yahoo history: short cooldown before re-probing

# Incremental fetch tuning
TTL_FRESH_HOURS_MARKET = 1        # Re-fetch latest bars if cache is older than this during market hours
TTL_FRESH_HOURS_OFFHOURS = 12     # ...or this outside market hours
FULL_REFRESH_INTERVAL_DAYS = 7    # Force a cold 5y refetch at least weekly
INCREMENTAL_OVERLAP_BDAYS = 5     # Re-download this many business days before last_cached_date for split-probe overlap
INCREMENTAL_MAX_GAP_BDAYS = 10    # Above this gap, fall back to full refetch instead of incremental
MARKET_DATA_MIN_LATEST_COVERAGE = 0.95  # Required latest-session close coverage before cache/archive is trusted
# A daily bar is NOT final at the closing bell: Yahoo keeps settling the last-hour prints
# for a few minutes after the close. Until close + this margin, the current session is
# treated as NOT YET COMPLETE (latest_completed_session), so a partial/forming bar is never
# cached-as-complete nor archived (see _drop_forming_rows). The scheduled scan runs well
# after (18:00 ET) and is unaffected; this only guards near-close MANUAL refreshes/scans.
SESSION_FINALIZATION_MARGIN_MINUTES = 30
# Deep-history corruption floor (the "second half" of the multi-universe cache bug).
# A trusted cache spans years; the NaN-wipe failure leaves recent bars but ~6 bars of
# deep history. Only judged when the PANEL itself spans >= MIN_HISTORY_BARS rows (so a
# short/new cache is never falsely flagged); below MIN_HISTORY_COVERAGE of symbols
# clearing the bar floor => cache is deep-history-corrupted => force a full cold refetch.
# 100 is well below ADMISSION_MIN_HISTORY_BARS(200) yet ~16x above a wiped cache.
MARKET_DATA_MIN_HISTORY_BARS = 100
MARKET_DATA_MIN_HISTORY_COVERAGE = 0.5
# The provider can simply LOSE a whole trading session. Measured 2026-07-24: a normal
# Friday (S&P 500 settled 7,411.98) for which Yahoo carries no bar at all — every symbol
# probed goes 07-23 -> 07-27. Our calendar was right; the data was missing. Every freshness
# gate keys on Close, so that reads as 0% coverage and a cache complete through 07-23 looks
# dead. Allow EVALUATION (never archiving) to proceed on a cache this many completed
# sessions behind, provided the cache's own last session clears
# MARKET_DATA_MIN_LATEST_COVERAGE. 0 restores the previous hard block.
MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS = 1
# A cold refetch that fails its coverage gate persists nothing, so repeating it for the SAME
# expected session re-pays the full-universe download (~30 min measured) to learn the same fact.
# When a full fetch proves a session essentially unpublished upstream, that session is recorded in
# cache_meta's `absent_sessions` ledger and no further cold fetch is attempted FOR THAT SESSION.
# Deliberately not time-bounded: a wall-clock window is dead exactly when it is needed (the measured
# repeats were ~24h apart, and a Friday loss spans ~72h to Monday's close). A newly completed
# session always gets a fresh attempt, and the operator's Refresh click clears the ledger, so the
# human override stays intact. Capped so meta cannot grow without bound.
ABSENT_SESSION_LEDGER_MAX = 20
# A session counts as "the provider does not have this" only at essentially-zero coverage — the
# measured 2026-07-24 incident recorded 0.0018. A partial response is a repair target, not an
# absent session, and must stay retryable.
PROVIDER_ABSENT_SESSION_MAX_COVERAGE = 0.02
LATEST_REPAIR_BATCH_SIZE = 100     # Smaller latest-bar repair batches after a sparse Yahoo response
LATEST_REPAIR_SLEEP_SECONDS = 2.0  # Gentle pause between repair batches to reduce Yahoo rate limits
# When essentially EVERY symbol lacks the latest close the cause is provider-side (an absent
# session), not per-symbol sparseness, and the batch-by-batch repair cannot help — skip it instead
# of paying ~55 serial batches. Uses the same "essentially unpublished" bar as the absent-session
# ledger, deliberately NOT a 50% one: between 51% and 95% missing the repair CAN lift a partial
# response back over the trust bar, and discarding it there would throw away a ~30-minute download.
LATEST_REPAIR_MAX_MISSING_FRACTION = 1.0 - PROVIDER_ABSENT_SESSION_MAX_COVERAGE
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
YAHOO_BACKOFF_JITTER = 0.5         # fraction of each retry backoff that is randomized (0=off, 0.5=lower half random) so concurrently rate-limited workers don't retry in lockstep
YAHOO_COOLDOWN_JITTER_SECONDS = 2.0  # after a shared 429 cooldown clears, each worker waits up to this many extra random seconds so they don't all resume at once (thundering-herd guard)

# Split-detection probe — EVERY cached ticker is checked on the incremental
# overlap window (under the as-traded regime a split is the only corporate
# action that shifts the series, so this probe is the entire defense).
SPLIT_PROBE_DRIFT_THRESHOLD = 0.005          # Ticker-level: ratio (fresh/cached) deviating by > 0.5% on overlap = split
SPLIT_PROBE_UNIVERSE_DRIFT_PCT = 0.02        # If > 2% of probed tickers drift → cold refetch

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
DASHBOARD_CHART_DAYS = 300           # Max daily candles shown per chart
DASHBOARD_CHART_WEEKS = 110          # Max weekly candles per higher-timeframe chart
DASHBOARD_CHART_MONTHS = 60          # Max monthly candles per higher-timeframe chart

# ============================================================
# SCHEDULED WEBAPP SCANS
# ============================================================
# The backend scheduler runs in America/New_York time, after the regular US
# close so yfinance has time to publish the completed daily bar.
# 17:00 ET is 00:00 in the operator's local time (Israel), chosen 2026-09-07 so the
# ~17-minute run finishes well before his habitual 01:00-02:00 local power-off, which
# had been killing the scan mid-flight. Do NOT move this earlier than 16:30 ET without
# first measuring the provider: the close is 16:00 ET and SESSION_FINALIZATION_MARGIN_MINUTES
# (30) means 16:30 is the FIRST instant today's bar counts as final, so 16:30 has zero
# slack and a minute earlier silently scans YESTERDAY's session instead.
SCAN_SCHEDULE_HOUR_ET = 17
SCAN_SCHEDULE_MINUTE_ET = 0
FORWARD_RETURNS_MIN_AGE_DAYS = 5
ALERT_WEBHOOK_URL_ENV = "ALERT_WEBHOOK_URL"
ALERT_ON_ZERO_RESULTS = True
ALERT_ON_DEGRADED_FETCH = True    # also alert when a scan succeeds but its fetch-health came back unhealthy (low return ratio) — an early warning before a stale_data failure

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
# the backend config-vs-cwd shadowing trap. See core/pipeline/health_board.py,
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
