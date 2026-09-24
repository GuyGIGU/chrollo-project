"""Score weights, grading scales and tier thresholds.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

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
# Fire-path staging of the Event Map (engine_alpha/structure/events/event_map.py): compute the
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

# ── The final method, build step 12 (Sat 19/09/2026): the grade ledger, DARK ──
# Point 21 of docs/final_method_2026-09.md, his answer 10 ("Volume: no hard gates, no points") and his Wed
# 12/08/2026 ruling (a setup is more complete with a clear Phase C). The ledger, docs/grade_ledger_2026-09.md,
# gives every one of today's 171 points a fate; under the switch the grade reads three things: the box's height
# in daily ranges (the tightness term, moved from ADR units to ATR_10 ranges), the spread profile (the LPS
# window's mean bar spread in ranges; the box's own bar texture stays the multiplier it is) and the event map
# (the committed turns at each rail on the line replace touch bars; the story's completeness keeps its small
# weight). Base age, the volume dry-up, the ATR squeeze, the VCP contractions, ascending support, ADR and the
# 52-week proximity go to zero weight and stay archived. The dead-space dock's pardon is keyed to a named leg
# on the map (the spring's own leg, an upthrust, THE SOS, a last supper): a named leg is never dead space; an
# unnamed lunge beyond a rail is docked as today, spring or no spring. Tier S keeps a ceiling, in ranges.
# Every number below is placed from his 35 marks (Sat 19/09/2026, the ledger's table) and measured on the
# junk; he sees the weights before they move. Flag-off byte-identical: every cap reads its setting above.
GRADE_LEDGER_ENABLED = False
GRADE_LEDGER_CAPS = {                  # the caps the ledger moves; every other cap stays as set above
    "SCORE_BASE_AGE": 0,               # rank correlation with the tail 0.04; the age stays archived
    "SCORE_VOL_CONTRACTION": 0,        # his answer 10: volume is shown, never graded
    "SCORE_ATR_SQUEEZE": 0,            # a right-edge ATR ratio, not a read of the box
    "SCORE_CONTRACTION": 0,            # the VCP footprint reads the old pivot recipe, not the line
    "SCORE_ASCENDING_SUPPORT": 0,      # rising lows are the staircase, an event-map read, not a term
    "SCORE_ADR": 0,                    # tradability, not structure; shown
    "SCORE_52W_HIGH_PROXIMITY": 0,     # context, not structure; shown
}
BOX_HEIGHT_FULL_RANGES = 1.0           # the tightness term is full at or under this height in ranges (his tightest, UNF 1.00)
BOX_HEIGHT_ZERO_RANGES = 4.0           # and zero at or over this (his widest ROIV 3.14; the junk boxes' median 3.50)
TURNS_POINT_RATE = 1.5                 # points per committed turn at a rail on the line (his q25 of 10 turns earns the 15 base points)
LPS_SPREAD_FULL_RANGES = 0.6           # the LPS term is full at or under this mean bar spread in ranges (his tightest window 0.55)
LPS_SPREAD_ZERO_RANGES = 1.6           # and zero at or over this (his loosest, PBT 1.38); his median window 0.83
TIER_S_MAX_HEIGHT_RANGES = 2.5         # tier S's ceiling in ranges (his q75 2.08; ROIV 3.14 and BWA 2.82 held to A)
# The letter's cuts on the re-based 0-100 scale (85 points): one tier up from today's 62 / 52 / 42 / 32, which
# the 171-point scale placed. Measured on the fire days under the whole method: at today's cuts his 20 fires
# grade S 15 / A 5 and 2 of the 3 junk fires reach S; at these, his S 11 / A 8 / B 1 and the junk A 3.
GRADE_LEDGER_TIER_CUTS = (72, 62, 52, 42)
