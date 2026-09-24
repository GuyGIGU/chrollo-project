"""Chart measurement, baseline admission and reading presets.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

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

# Cause-before-effect election precondition (engine_alpha/structure/narrative/bricks.cause_maturity,
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
# engine_alpha/structure/phases/phase_a.py, docs/pip_macro_phase_a.md). The earlier FLAT PIP wire
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
# (research/fidelity/box_backext/); shadow baseline re-captured at the flip.

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

# --- Bar-posture rescue lane (consolidation-method Task 7; DARK) ------------
# The measured bar-as-unit fix to the story pool's ceiling leg, landed as a
# VERSIONED second form — never an in-place edit of frame_terminal_posture
# (the ONE close-basis predicate the S-test prefilter and the episode reader
# both resolve through; its promotion counts are pinned). On a full refusal
# (same scope, same escalation walk as the contraction rescue above), the
# story pool may also admit through the S-test form with its ceiling leg in
# the operator's unit: the bar's HIGH engages the resistance zone
# (event_map.story_admission_bar_posture — terminal_r_engagement instead of
# terminal_r_posture). Banked A/B (output/consolidation_evidence_2026-08-31/
# battery.log, chair-verified): junk corpus 18/18 silent, shadow panel
# byte-identical on all 32 fixture fires, ratchet breaks on EXACTLY EGBN
# (fires 2026-01-07 tier A) + PKE (2026-02-18 tier B) — both operator-ruled
# real dates. The full-refusal scope is what makes the census's QTTB loss
# unreachable (QTTB reads at baseline, so the rescue never runs there) while
# all 12 census new fires stay reachable (verified 12/12 full refusals).
# Flip = operator decision (ledger row; reseal shares EGBN/PKE with the
# contraction rescue's).
BAR_POSTURE_RESCUE_ENABLED = False

# --- Sentence-token archive family (consolidation-method Tasks 8/9; DARK) ---
# The folded ONE-language tape archived per fire: every reader's output
# (puzzle waves + role stamps, rail episodes, the mini-consolidation) folded
# through the signed vocabulary (event_vocabulary.unify_events) and
# serialized date-anchored into the sentence_* column family — measured in
# the ONE shared eval chain, once per elected box, so live/seed/manual rows
# carry identical sentences by construction. Measure-only: never gates,
# never scores, never sorts. Flag off = {} in the result row = the family
# archives NULL (not measured); a refused read (unreadable geometry) NULLs
# the whole family. Tokens are closed-set-asserted at mint (EC-55).
# FLIPPED LIVE 2026-09-02 on the operator's ruling (decisions.md asks-sweep
# row part 9): the archive is measure-only, so the flip cannot move a score,
# a tier, an election or a sort - only the sentence_* columns gain values.
# Pre-flip rows stay NULL forever; there is no backfill, and the epoch
# rotation is what keeps the two eras separable. The cost bound rides ONE
# armed nightly scan (ledger row: <= 60 s added to the evaluation phase
# against an expectation of 1-3 s), read the next morning from
# market_context._scan_metrics.phases_s.evaluation - a one-word revert if it
# breaks, and the trial night's rows KEEP (they carry their own engine stamp).
SENTENCE_ARCHIVE_ENABLED = True

# --- Near-miss lane — the RULED one-leg-narrow form (Task 6 ruling) ----------
# Measurement constants for the operator-ruled near-miss predicate
# (engine_alpha.structure.box.gate_margins.ruled_near_miss; ruling record
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
# Two RAW campaign-context measures per fire (structure/context/strategy_read.py):
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
# None). The rescue (engine_alpha/structure/lps/detection.py) re-admits a non-terminal-low window
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
                                 # rejected (companion pin in tests/engine/test_lps.py); Vol_50 gained
                                 # a non-finite refusal guard in the same change.
# ============================================================
# HIGHER-TIMEFRAME (HTF) STRUCTURE CONTEXT
# ============================================================
# The structure engine reads the SAME Wyckoff Trend+Box (A->B->C->D) logic on
# weekly/monthly bars as on daily — "it's all relative and derivative". Its RATIO
# thresholds (MAX_BOX_WIDTH, MIN_BOUNDARY_RESPECT_PCT, ATR/box ratios, traversal
# fractions, LPS profiles) are scale-invariant and transfer untouched; only the
# BAR-COUNT WINDOWS are daily-calibrated. engine_alpha.structure.context.htf temporarily rescales
# ONLY those windows (timeframe_windows CM) around the same Trend+Box brick walk
# on the resampled frame. These presets are FIRST-PASS (~daily/5 weekly, /~4 again
# monthly) and a calibration target — eyeball + tune via tools/audits/htf_audit.py.
HTF_CONTEXT_ENABLED = True        # compute + archive + chip HTF context on FIRING setups; never gates

# The daily read is sliced to this trailing window before read_structure, so the
# 5y cache (needed for HTF resampling) does NOT feed the daily oldest-first root
# walk extra history and drift it (the FOSL _MAX_ANCHORS sensitivity). Keeps daily
# byte-identical; validate with tools.regression.shadow_diff once real 5y data is present.
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
# (engine_alpha.structure.context.htf.window_override) — never a forked collector. The
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
