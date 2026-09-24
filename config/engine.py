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
# long). Measured by engine_alpha.structure.metrics.base.measure_equilibrium. The
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
# dead-space framing (DGII; CHCT too, which he ruled a valid setup on Sun 13/09/2026,
# so under the final method, LPS_LEAVES_ELECTION_ENABLED, the tail is a COMMENT on
# the fire and refuses nothing: build step 12). Read on the ACTIVE box (the inner box when the
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
# which is exactly what refused the global POWER_PLAY_STORY_FORM_ENABLED flip (2026-08-19)
# (the WCC 2.2x-wider re-election). A rescued fire stamps
# elected_pool='story' with the self-naming contraction profile. Flip =
# operator decision vs the miss-program A/B (docs/miss_program_2026-08.md);
# flipping re-seals the marks ratchet (EGBN/PKE leave the expected-miss list).
CONTRACTION_RESCUE_ENABLED = False
# The resistance-contraction STORY form the rescue lane arms (event_map.
# resistance_contraction_admission, the second named ruled form inside the one
# story admission; named by operator ruling 2026-08-18: the record says the
# behavior, never an invented umbrella word). Dark and toggled ONLY under the
# scoped override (htf.window_override) around the rescue re-walk, so the
# paying scan's admission never consults it. Its global flip was refused on
# 2026-08-19 (EGBN and PKE fired, a ratchet break; the WCC 2.2x-wider
# re-election). The Power-Play species lane that once rode it under its own
# 8-day clock was DELETED at the final method's build step 12, point 25 (Sat
# 19/09/2026), with its preset, pole and breakout-wall keys; this flag stays
# because the rescue lane above is its remaining consumer.
POWER_PLAY_STORY_FORM_ENABLED = False

# --- Bar-posture rescue lane (consolidation-method Task 7; DARK) ------------
# The measured bar-as-unit fix to the story pool's ceiling leg, landed as a
# VERSIONED second form — never an in-place edit of frame_terminal_posture
# (the ONE close-basis predicate the S-test prefilter and the episode reader
# both resolve through; its promotion counts are pinned). On a full refusal
# (same scope, same escalation walk as the contraction rescue above), the
# story pool may also admit through the S-test form with its ceiling leg in
# the operator's unit: the bar's HIGH engages the resistance zone
# (event_map.story_admission_bar_posture — terminal_r_engagement instead of
# terminal_r_posture). Banked A/B (research/evidence/consolidation_evidence_2026-08-31/
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

# ── The final method, build step 2 (Sun 13/09/2026): the ruled stack behind ──
# ── flags, DARK (every flag default OFF; flag-off is byte-identical).       ──
# The operator's rulings R1 and R7 to R18 (docs/decisions.md, 2026-09-05 to
# 2026-09-12), each as it was MEASURED in process on his 37 LPS windows, the
# junk corpus and the fleet fixture (rulings ledger, rulings_ab2 to ab8). One
# flag per ruling SITE so each can be measured alone (six flip only together); the values
# are placed from his drawings, never tuned. Every name here rides the engine
# manifest so a flip rotates engine_config_version from day one.
#
# R1 (respect): a bar is OUTSIDE the box only when the WHOLE bar sits beyond
# the rail area (low above R + area, or high under S - area); a poke or a
# straddle is respect. Today a wick beyond the area counts as outside.
RESPECT_WHOLE_BAR_ENABLED = False
# R13 (the bar is the unit of dwell; graded): the whole occupancy exam never
# refuses a box (both end-third dwells, the mid churn, the coverage; their
# values stay facts). Alone it regresses MATX: live only with the stack.
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
# the first high to the window low is at least 0.68 ranges (his minimum under
# R18's last-run window, ORMP Thu 09/04/2026; 0.71 on his windows as drawn,
# where the first build placed 0.70: review finding RF-13, Mon 14/09/2026),
# and the last day's high is not back at the first high (R15: read on the
# HIGH; his 36 windows: last high <= first high + 0.25 ranges, WTS 0.21).
LPS_GRADED_TRAITS_ENABLED = False
LPS_CORRECTION_DIG_MIN_ATR = 0.68
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
# the support side is read on WHOLE BARS: more than half of the window's
# high-to-low travel under the support area refuses (his Q18, "not below the
# support area"), more than half under S types it UNDERCUT_S, so a poke never
# refuses (his JAZZ answer: on support "since most of the move is above it").
# The ceiling above R stays (R12).
# 19: the three post-window checks go (the close 5 percent under the LPS low,
# the post-window low test, the post-window spread test): under one window per
# read day there is no post-window day to check. The depth cap in profile units
# goes with them; the window height in ranges is the one "too deep" refusal left.
# 20: volume never refuses and never elects (quality is volume-free); the ratio
# stays a fact on the card. No points is the grade ledger's job (step 12).
LPS_REFUSALS_TO_GRADES_ENABLED = False
# 19, his answer on AEF (Mon 14/09/2026), DARK: "3 bars with huge increases in both spread and price
# changes meaning the pull back is increasing with sellers" (R9: an LPS is broken when seller strength
# rises). FATAL in the election, never the measure-only staircase: the window's last three days each wider
# than the day before and each falling further (a day's fall is the mean of its high's and its low's drop),
# and the last fall bigger than the whole range of the day before (the prior bar is the yardstick: his 37
# windows reach 0.66 of it, AEF Thu 04/06/2026 1.29, the nearest fleet fire JAKK 0.85).
LPS_SELLERS_RISING_FATAL_ENABLED = False

# ── The final method, build step 4 (Sun 13/09/2026): the ONE turn line, DARK. ──
# His points 1 and 2 (docs/final_method_2026-09.md): one line over the WHOLE
# chart, ONE floor of TURN_LINE_FLOOR_ATR daily ranges, wick to wick, no
# retracement ratio; the first bar is a turn by its shape and the running
# extreme at the right edge is a FORMING turn, so the line carries no edge
# mask and no five-day right-edge reserve. Not built: named events as turns
# by law (the LPS valley, the trigger cross), final method point 1.
#
# MEASURED on his 35 drawn marks (186 named turns: both rail anchors, every
# LPS peak and low, every spring and spring-test tip, every SOS peak):
#   today's order-1 walk + the 15 percent collapse   112 of 186,   0 of 35 marks complete
#   the line at 0.75, one range from the read day    183 of 186,  32 of 35
#   the line at 0.75, each day's OWN range           186 of 186,  35 of 35
# The three the read-day unit misses are support anchors on the box's first
# days, 26 to 35 trading days back, each 2 trading days off (corrected Mon
# 14/09/2026: not "two years back"). Extra turns inside his boxes: about 6.2
# per 10 trading days (today's walk: 2.4). The recall is density, not proof:
# his day moved three trading days still lands 173 of 186 (exact day: 175).
#
# One flag per SITE so each can be measured alone. The box
# election is deliberately NOT a site: it stays on today's skeleton until
# build step 10.
TURN_LINE_ENABLED = False          # the event map's swing layer reads the line
TURN_LINE_TREND_ENABLED = False    # the HH/HL/LH/LL trend labels read the line
TURN_LINE_FLOOR_ATR = 0.75         # placed by the sweep on his 186 turns (his Q1 asked for a search)

# ── The final method, build step 5 (Mon 14/09/2026): the words on the line, DARK. ──
# His points 10 to 15 (docs/final_method_2026-09.md): a MEASURE-ONLY reader
# (engine_alpha/structure/events/line_words.py) over the one turn line, the elected
# rails, the elected LPS and the mini. Nothing that elects, vetoes, grades or
# displays reads it; each flag only adds its own word to ONE JSON diagnostic
# on a fire (_line_words_json). The words read the line whatever
# TURN_LINE_ENABLED says, so they flip with or after it. THE SOS, the
# upthrust and the last supper follow his SOS answers of Tue 15/09/2026 and
# his upthrust tweaks of Wed 16/09/2026, on defaults of mine (docs/decisions.md). Not built: the shakeout (parked by
# him), the dead-space pardon keyed to a named leg (21: a grade change, his
# question still open).
#
# MEASURED on his 35 marks, his rails, fed his drawn LPS windows
# (python -m tools.calibration.word_recall; a hit is within one trading day; CHANCE is
# the same score with his day moved three trading days either way):
#   a thrust at his SOS top   25 of 26 (chance 12)   THE SOS  23 of 25 (chance 0)
#   last supper               10 of 10 (chance 0.5)  Phase C  10 of 10 (chance 0)
#   spring test                4 of 6  (chance 1)    mini      0 of 5
#   upthrust: his UNF named, ONE per box (listed, not scored: the app cannot
#             record one). On his words to Sat 19/09/2026, 3 named on his
#             35 boxes: his UNF, FOSL and his VIK.
# Under all six flags nothing moves: ratchet 30 of 35, junk clean on every
# unpinned day, fleet and reader pin PASS. The rules' defaults that are mine
# (his word owed) are listed in line_words.py and the decisions record.
LINE_WORD_SOS_ENABLED = False          # 11: every thrust, and THE SOS by the LPS after it
LINE_WORD_LAST_SUPPER_ENABLED = False  # 15: the last supper, in hindsight only
LINE_WORD_PHASE_C_ENABLED = False      # 14: one Phase C per box, and its spring test
LINE_WORD_PHASE_D_ENABLED = False      # 12: where the right side opens
LINE_WORD_MINI_ENABLED = False         # 13: today's elected mini, as facts
LINE_WORD_UPTHRUST_ENABLED = False     # 10: his upthrust, ONE per box (Tue 15/09 + Wed 16/09/2026)
LINE_WORD_AREA_ATR = 0.5               # the ruled rail area, in daily ranges (as TOUCH_TOLERANCE_ATR, MINI_POSITION_TOL_ATR)
LINE_WORD_UPTHRUST_MIN_POKE_ATR = 1.25  # an upthrust climbs this far over R: between the breach he crossed out (his UNF, 0.94) and his smallest (his VIK note, 1.55)
LINE_WORD_SOS_MIN_GROUND_ATR = 1.70    # his smallest SOS, launch low to top, on his own spans
LINE_WORD_SUPPER_DIG_ATR = 1.5         # a last supper digs this far (his ten: 1.75 to 3.76); a pause this deep ends a thrust
LINE_WORD_SUPPER_MAX_DAYS = 4          # his longest last supper, in trading days

# ── The final method, build step 6 (Mon 14/09/2026): the 15-day floor from the first anchor, DARK ──
# His answers: "Lets go with 15 days" (Q9 of the 26) and "15 for a base minimum yes" (the twelve
# follow-ups). Point 9 of docs/final_method_2026-09.md: the floor applies to the box's AGE, counted from
# its FIRST RAIL ANCHOR as day 1, not from the root's reaction bar, where MIN_BASE_DAYS counts today (the
# seed clock of bricks.find_root_swing and validate_equilibrium). Flag-on the seed clock yields to
# BASE_AGE_MIN_DAYS less the edge reserve (never above MIN_BASE_DAYS, so the weekly, monthly and Power
# Play presets keep their own), and the root walk refuses a box whose first anchor is younger than
# BASE_AGE_MIN_DAYS: that box is "forming, N of 15" in the walk trace, never elected, graded or fired.
# MIN_BASE_DAYS keeps every other use (the matured-cause 2x floors, the richness denominator, the age
# points, the mini, the transition zone, the live cause veto's import-time copy). Flag-off byte-identical.
BASE_AGE_FROM_ANCHOR_ENABLED = False
BASE_AGE_MIN_DAYS = 15                 # his number

# ── The final method, build step 7 (Tue 15/09/2026): box gates to grades, DARK ──
# Point 7 of docs/final_method_2026-09.md, his Q7: "a box is a box because of its consolidating Zig zag
# behavior not it's height ... as long as we can understand the Price action within the box and it acts like
# a consolidation then we should be able to scan it". No height gate in any unit: the three percent-of-price
# width caps stop refusing a box and stop demoting a tier, MAX_BOX_WIDTH (18 percent: the strict, rescued
# and story pools and the occupancy judge, the inner search included), BAND_MAX_BOX_WIDTH (23 percent: the
# band pool) and S_MAX_BOX_WIDTH (15 percent: the tier-S ceiling). The width stays a fact and a grade (the
# ADR tightness term reads it); whether tier S keeps a ceiling in daily ranges is step 12's grade ledger.
# At his own rails the 18 percent cap refuses BODI (21 percent of price, 2.1 daily ranges) and the 15 percent
# ceiling holds ANRO (16 percent) out of tier S.
BOX_WIDTH_CAPS_GRADED_ENABLED = False
# Point 8, his Q8, asked on BODI's drawn Phase C against the 3-range spring cap: "It's hard to gate using a
# raw number in case we reject a valid setups because of a small neumeric gap". No depth number decides that a
# dip is too deep to be a spring: the box's crash floor (a low under CRASH_FILTER_MULT of S refuses the pair;
# at his rails it touches only BODI), the read day's crash floor (a close under it drops the chart), the
# spring's 3.0-range depth cap (BIN_C_UNDERCUT_ATR_MAX) and the band pool's two caps on a below-rail event
# (BAND_EVENT_MAX_DEPTH_ATR 5.0 ranges deep, BAND_EVENT_MAX_BARS 20 trading days long) stop refusing; the
# depth stays a fact. The spring's box-height cap is R17's switch (SPRING_BOUNDS_LIFTED_ENABLED); its day
# counts (reclaim, linger, hold) give way to recovery by the swing (point 14), not here.
DEPTH_CAPS_GRADED_ENABLED = False
# Point 6, his Q6: "a whole lone bar beyond the rail area isn't respecting it but if we come to learn that price
# action before that bar and after that bar DO then it changes the way we treat it, a Long run of bars beyond the
# rail could mean a long Spring or UP thrust as well". Respect refuses nothing: the respect share
# (MIN_BOUNDARY_RESPECT_PCT, 80 percent of days inside the rail area) and the run cap (MAX_CONSECUTIVE_OUTSIDE_DAYS,
# 10 trading days beyond a rail) stop refusing a pair, and the band pool stops refusing a stay above R longer than
# that cap; the outside share, the longest run and the deepest excursion stay facts. What a run beyond a rail was
# (a spring, an upthrust, the end of the box) is read from what follows it (the words, steps 5 and 11).
RESPECT_GRADED_ENABLED = False

# ── The final method, build step 8 (Sat 19/09/2026): the LPS leaves the election, DARK ──
# Point 22 of docs/final_method_2026-09.md: "The LPS stops being a brick of the box election (today no LPS means
# the walk skips to the next root and the chart returns nothing; 72 of the study's 224 day-reads had lines but no
# window and showed nothing). The 'no LPS yet' charts sit in a watch lane apart from the leaderboard, with a
# display floor of two turns at each rail on the line (all 35 of yours clear it) that touches no fire." Under the
# switch the root walk (narrative._walk_structure) returns the first valid box with or without an LPS (a
# Structure whose lps is None: lines, no LPS yet); a structure without an LPS never fires; and every chart the
# door admits carries ONE state word from the closed table (evaluation.WATCH_WIRE_STATES) into
# market_context["watch"]: fired, crossed, lines no LPS yet, forming N of 15, beyond R undetermined, under S
# undetermined (point 6's precedence row 5, the open right edge), not scanned (the door's leg named, point 24),
# no lines; "root candidate, unconfirmed" and "broke down" are step 11's words, on the table and never typed
# before it. The lane's rows are the charts with lines and no fire that clear the display floor below; the floor
# touches no fire. Flag-off byte-identical: no recorder, no trace, no block on the wire. Display is step 12.
LPS_LEAVES_ELECTION_ENABLED = False
WATCH_LANE_MIN_TURNS_PER_RAIL = 2      # his display floor (point 22): committed turns of the line inside each rail's area

# ── The final method, build step 9 (Sat 19/09/2026): the box opens on the anchors, DARK ──
# Point 5 of docs/final_method_2026-09.md, his ruling of Sat 12/09/2026: "No, Box opens on the anchors of each of the
# Boundary rail (Resistance & Support)". The box opens on the earlier anchor day, each rail from its own anchor, and
# never extends left: the shared-rail back-extension (box_primitives.backext_shared_rail, folded unconditional on
# 2026-07-18) stops moving the elected start to an earlier rail-touching pivot. Both its callers read the one
# function (bricks.validate_equilibrium, the live walk; find_outer_box's diagnostic mirror). Measured before the
# build (the critics' count, Sun 13/09/2026): the extension moves 0 days on 10 of the 11 early-opening boxes and 4
# days on ROIV; the early openings are older roots, steps 10 and 11's.
BOX_OPENS_ON_ANCHORS_ENABLED = False

# ── The final method, build step 10 (Sat 19/09/2026): the climax first, and the walk from it, DARK ──
# Points 3 and 4 of docs/final_method_2026-09.md and his rule of Sat 19/09/2026: "the swings for BC and AR are
# needed to be decided before the Root Swing, because said root swing can either be them, or a swing later".
# Under the switch the roots are the runs the ONE turn line prints (higher highs and higher lows, or the mirror;
# a run ends at the first swing that fails to continue it), each run's climax and its reaction low (the lowest low
# of the reaction before the first higher low, point 4's reaction-low rule) decided FIRST
# (engine_alpha/structure/phases/climax.py, bricks.find_root_swing); the window opens AT the climax and the candidate
# pairs are the line's own turns walked forward from it, the climax and its reaction the first pair; a pair is a
# candidate once the following swings answer to its rails (a later committed turn of the line inside each
# rail's area, LINE_WORD_AREA_ATR); first in time wins as before (R4). Retired under the switch: the seed's
# percent recipe (TREND_MIN_GAIN_PCT 15 percent in TREND_MIN_MOVE_BARS 20 days, AR_MIN_DROP_PCT, AR_MAX_BARS,
# LOCAL_PEAK_BARS, TREND_PRIOR_LOOKBACK) and its ROOT_TREND_SMA gate; the Phase A painter and the macro bridge
# (resolve_phase_a returns the root's own pair; PIP_MACRO_MIN_BASE_BARS then has no reader); the
# cause-before-effect veto (no abstention any more: the run's size in ranges and its length ride on the fire as
# facts, _trend_run_ranges / _trend_run_days, for step 12's trend-context grade); the two RF-4 sites read the
# line. T5, the opening leg's direction on the line, is the test of the anchoring, never a veto (Tested-DEAD).
# Flag-off byte-identical.
CLIMAX_FIRST_WALK_ENABLED = False

# ── The final method, build step 11 (Sat 19/09/2026): the box's end and the hand-over by swings, DARK ──
# Points 6, 8 and 26 of docs/final_method_2026-09.md, his Q6 ("if the price continues to Rise/Fall with out
# recovering we can deduce that either that the consolidating structure we measured ended and the price began to
# trend") and his dead-space drawings of Sat 19/09/2026. Under the switch an elected box is read for its END on the
# line (engine_alpha/structure/box/box_end.py): upward, the hand-over by swings (after the breakout day, R15's one use
# of the close, every swing whose valley holds in or above the parent's R area is a child root candidate, and the
# parent ends when a child's own answering completes, a later turn of the line inside the area of EACH of its
# anchors: one turn at one anchor is the parent's own LPS above R, row 1 of point 6's table, and the parent goes on
# and fires; a run that comes back into the box hands nothing over; no close level ends a box, a close-dated
# hand-over is Tested-DEAD); downward, the mirror (after the breakdown day, a swing whose peak holds in or below
# the S area is a child candidate below, confirmed by its own answering; a dip that confirms no child below is
# under S, undetermined). The parent freezes at its last turn before price left. An ended box is never the
# structure: the walk moves on to the next run. The unit of the area and the end tests is FROZEN with the rails: the ATR of the election day (the day the
# answering completed). An unconfirmed child rides as the chart's state, "root candidate, unconfirmed" (point 6's
# precedence row 4, a flag never a word); a breakdown with nothing after it reads "broke down". Retired under the
# switch: the read day's extension veto (a close 15 percent over R), the stale-box rescue's percent test, the
# dethrone pass, and a mini whose bottom holds the parent's R area (that band is the child, point 26's seam).
# Flag-off byte-identical.
BOX_END_ENABLED = False
BOX_END_BREAKOUT_ATR = 0.10            # R15: the breakout day closes this far over R, in daily ranges (his placed margin)

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
