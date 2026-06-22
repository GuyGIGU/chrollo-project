# Algorithm Knob Audit

This is a working taxonomy of Chrollo's live screener knobs after the
chronological reader migration. It is intentionally about the algorithm, not
runtime/cache/dashboard settings.

The goal is to separate:

- hard geometry rules: violations mean "not the setup"
- quality evidence: useful to rank, tag, or choose among candidates
- fallback/tolerance: keeps the reader robust around edge cases
- scoring-only: opinions after the structure has already passed
- cleanup candidates: stale, duplicated, or hidden knobs

## Status (2026-06-22 cleanup pass)

Several "cleanup candidate" items below were already RESOLVED — verified this pass:

- **Five-bar edge skip: centralized.** Every root/box/inner path reads
  `settings.STRUCTURE_EDGE_SKIP_BARS`; only explanatory comments still show `:-5`.
- **`INNER_MIN_DAYS`: moved to `config/settings.py`** beside `INNER_SEARCH_FRACTION` /
  `INNER_TIGHTNESS_RATIO`; read as `settings.INNER_MIN_DAYS` at use-sites (byte-identical).
- **`scope.py` Phase-D docstring: already current** (earliest right-side evidence; LPS the
  mandatory gate/fallback) — not stale.
- **Frontend score caps (`setupScoreMath.js`): in sync** with the Python `SCORE_*`.

All verified byte-identical (`shadow_diff --check` PASS, 281 tests green). The remaining
substantive work is architectural — see "Recommended Next Work" at the bottom.

## Reader Model

The clean model is:

1. Phase A finds a climax -> automatic-reaction root swing.
2. Phase B validates a worked equilibrium, not merely a wide box.
3. Phase C spring is optional. If present, its recovery is a floor for the
   Phase-D search, not Phase D itself.
4. Phase D begins at the earliest credible right-side evidence after that floor:
   support-test cluster, inner box, or V-tip. The LPS remains the mandatory gate
   and fallback.
5. The setup LPS should be the latest actionable valid support test, not merely
   the highest-quality old slice.

## Phase 1: Universe Gates

Source: `config/settings.py`, `core/pipeline/evaluation.py`.

Hard rules:

- `len(df) >= 200` is hard-coded history sufficiency.
- `MIN_PRICE = 3.0`
- `MIN_VOLUME_50D = 50_000`
- latest close above SMA50 and SMA200, hard-coded.
- `MIN_YEARLY_RETURN = -0.20`

Taxonomy:

- These are coarse universe filters, not structure knobs.
- Keep as hard gates. They prevent garbage input and avoid bottom-fishing.
- If reduced later, do it from archive outcome evidence, not per-chart misses.

Hidden/local knobs:

- SMA windows 50 and 200 are hard-coded in `apply_baseline_filters`.
- The yearly-return lookback uses 252 bars, hard-coded.

## Phase A: Root Swing

Sources: `config/settings.py`, `core/structure/consolidation.py`,
`core/structure/bricks.py`, `core/structure/segmentation.py`.

Hard geometry rules:

- `MIN_BASE_DAYS = 20`
- `TREND_MIN_GAIN_PCT = 0.15`
- `TREND_MIN_MOVE_BARS = 20`
- `TREND_PRIOR_LOOKBACK = 100`
- `LOCAL_PEAK_BARS = 30`
- `AR_MIN_DROP_PCT = 0.05`
- `AR_MAX_BARS = 15`

Fallback/tolerance:

- The detector reserves the latest `STRUCTURE_EDGE_SKIP_BARS` bars when possible.
  The centralized setting prevents live-edge noise from changing the base.
- `resolve_phase_a` uses `_SEG_LEAD_IN = 60` and `_SEG_AR_TOL = 10` to reconnect
  a distant raw anchor to the local climax -> AR bridge of the accepted box.

Taxonomy:

- Keep root-swing thresholds as hard rules for now. They define "there was a
  real prior limb before the base."
- The local Phase-A resolver is a fallback/tolerance layer, not a detector to
  tune for score.

Cleanup candidates:

- `TREND_SMA_LOOKBACK` and `TREND_BULLISH_GAP_MAX` were confirmed unused and
  removed from `config/settings.py`.
- Five-bar edge skip — RESOLVED 2026-06-22: centralized as
  `settings.STRUCTURE_EDGE_SKIP_BARS` across root/box/inner paths.

## Phase B: Worked Equilibrium

Sources: `config/settings.py`, `core/structure/box_primitives.py`,
`core/structure/metrics.py`.

Hard geometry rules:

- `MAX_BOX_WIDTH = 0.18`
- `CRASH_FILTER_MULT = 0.70`
- `BOUNDARY_ATR_BUFFER = 0.50`
- `MAX_CONSECUTIVE_OUTSIDE_DAYS = 10`
- `MIN_BOUNDARY_RESPECT_PCT = 0.80`
- `TOUCH_TOLERANCE_ATR = 0.5`
- `EQ_MIN_TOUCHES_PER_RAIL = 3`
- `EQ_MIN_TOUCH_THIRDS = 2`
- `EQ_MIN_HALF_DWELL = 0.15`
- `EQ_MAX_MID_DWELL = 0.45`
- `EQ_MIN_COVERAGE = 0.80`
- `EQ_COVERAGE_BINS = 6`
- `EQ_COVERAGE_MIN_FRAC = 0.03`
- `TRAVERSAL_GATE_ENABLED = True`
- `TRAVERSAL_MIN = 2`
- `TRAVERSAL_MIN_DENSITY = 0.08`

Fallback/tolerance:

- `PIVOT_ORDER_SHORT = 1`
- `PIVOT_ORDER_LONG = 2`
- `PIVOT_ORDER_THRESHOLD = 40`
- `PHASE_B_ATR_WINDOW = 30`
- `TRAVERSAL_NOISE_FRAC = 0.15`
- `TRAVERSAL_FULL_FRAC = 0.55`
- `TRAVERSAL_LOW_ZONE = 0.30`
- `TRAVERSAL_HIGH_ZONE = 0.70`

SOS/BUEC rescue:

- `SOS_TRIM_ENABLED = True`
- `SOS_TRIM_MIN_RUN = 3`
- `SOS_TRIM_MIN_PREFIX_FRAC = 0.30`
- `EXTENSION_FILTER_MULT = 1.15` is reused to avoid accepting stale rescued boxes.

Taxonomy:

- The equilibrium and traversal rules should stay hard. They are the standard
  "boundary-to-boundary, no dead space" definition.
- The EQ dwell/coverage gates are close-residence rules for stable box-of-record
  selection; public `measure_equilibrium()` also reports High/Low range
  occupancy as analysis geometry.
- SOS trim is not a loosened box rule. It says: validate the worked cause before
  a sustained breakout tail, then let the LPS/BUEC decide if the setup is active.
- Two-sided rail-working is now BOTH a hard validity rule (the traversal gate)
  and a graded scoring reward (`SCORE_TRAVERSAL_QUALITY`, which replaced the
  rail-blind `oscillation` term). The `worked_equilibrium` chip (formerly
  `two_sided_range`) is the descriptive surface — now sourced off the real
  `traversal_density` field, not the looser close-based CoG-crossing proxy.

Hidden/local knobs:

- Candidate quality uses fixed weights: `0.4 * tightness + 0.4 * touch_density
  + 0.2 * coverage`.
- Touch-density quality divides by 10.
- The selector uses earliest valid candidate, tie-broken by quality.

## Inner Box: Phase-D Mini Consolidation

Sources: `core/structure/consolidation.py`, `core/structure/box_primitives.py`,
`core/structure/bricks.py`.

Hard geometry rules:

- `INNER_MIN_DAYS = 15`
- `INNER_SEARCH_FRACTION = 0.5`
- `INNER_TIGHTNESS_RATIO = 0.75`
- The inner box reuses the same worked-equilibrium box validation.

Taxonomy:

- Inner is evidence, not a mandatory setup gate.
- It should remain a first-class brick because it changes the active LPS context
  and gives a closer trigger/stop.

Cleanup candidates:

- `INNER_MIN_DAYS` — RESOLVED 2026-06-22: moved to `config/settings.py` with the
  other inner knobs (read as `settings.INNER_MIN_DAYS`; byte-identical).

## Phase C: Spring

Source: `config/settings.py`, `core/structure/bin_features.py`.

Hard geometry rules for calling a spring real:

- `BIN_C_UNDERCUT_ATR_MIN = 0.30`
- `BIN_C_UNDERCUT_ATR_MAX = 3.00`
- `BIN_C_UNDERCUT_BOX_MAX = 0.65`
- `BIN_C_RECOVERY_BARS_MAX = 8`
- `BIN_C_LINGER_BARS_MAX = 12`
- `BIN_C_HOLD_BARS = 3`
- `BIN_C_HOLD_TOL_ATR = 0.50`
- `BIN_C_SIGNIF_UNDERCUT_ATR = 0.75`
- `BIN_C_MIN_LINGER_BARS = 2`
- `BIN_C_LATE_BOX_FRACTION = 0.50`

Taxonomy:

- These are hard only for the label "spring".
- Spring itself is optional and measure-first. No setup should require it.
- Spring recovery is a Phase-D search floor, not a Phase-D boundary source.

## Phase D Boundary Evidence

Sources: `config/settings.py`, `core/structure/phase_d.py`,
`core/structure/narrative.py`, `core/structure/bin_features.py`,
`core/structure/scope.py`.

Evidence types:

- support-test cluster
- inner box
- V-tip
- LPS fallback

Hard rule:

- No LPS means no valid setup.

Fallback/tolerance:

- `PHASE_D_VTIP_LATE_FRACTION = 0.35`
- `PHASE_D_VTIP_RECOVERY_BARS = 6`
- support-test cluster requires at least two detected tests in the right half.
- evidence tie rank is hard-coded: support-tests, then inner-box, then V-tip.

Taxonomy:

- Phase-D boundary resolution should stay centralized in `phase_d.py`.
- Support-test, rising-support, SOS/reclaim, inner, and V-tip should all speak
  through the same `PhaseDBoundary.evidence` vocabulary.
- Rising support and SOS/reclaim are not first-class detectors yet. Today they
  collapse mostly into support-test cluster, inner box, V-tip, or LPS fallback.

Cleanup candidates:

- `scope.py` Phase-D wording — RESOLVED 2026-06-22: docstring matches the shared
  boundary helper (earliest right-side evidence; LPS remains the mandatory gate).
- `strategy_v2.md` still describes a partly older Phase-D boundary model in
  places. It should be refreshed after the next calibration pass.

## LPS Candidate Detection

Sources: `config/settings.py`, `core/structure/lps.py`,
`core/structure/bricks.py`.

Hard geometry rules:

- `LPS_LENGTH_MIN = 2`
- `LPS_LENGTH_MAX = 7`
- `LPS_SCAN_OFFSET_MAX = 7`
- `LPS_PROFILE_BOX_FRACTION_FLOOR = 0.15`
- `LPS_PULLBACK_PROFILE_MIN = 0.40`
- `LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R = 1.25`
- `LPS_PULLBACK_PROFILE_MAX = 4.50`
- `LPS_TERMINAL_LOW_TOL_PROFILE = 0.10`
- `LPS_SPREAD_MAX_PROFILE_MULT = 1.25`
- `LPS_SPREAD_EXPANSION_MAX_PROFILE = 0.35`
- `LPS_MIN_DESCENT_FRAC = 0.50`
- `LPS_MIN_HIGH_DESCENT_FRAC = 0.45`
- `LPS_MAX_WINDOW_BOX_RANGE = 0.85`
- `LPS_INSIDE_HIGH_EXTENSION_BOX_MAX = 0.35`
- `LPS_INSIDE_HIGH_EXTENSION_ATR_MAX = 0.75`
- `LPS_HOLD_TOLERANCE = 0.97`
- `LPS_ZONE_ATR_MULT = 0.5`
- `LPS_RANGE_PERCENTILE = 0.5`
- `LPS_VOL_CONTRACTION_MAX = 0.85`

Quality evidence:

- `LPS_SPREAD_MUST_DECLINE = True` discounts candidate quality through
  `spread_decline_quality`; it no longer rejects a visually tight LPS by itself.
  The hard spread rule is now "spread cannot expand too much" in profile units.

Fallback/tolerance:

- Tight boxes widen zone tolerance: if `box_width < 0.10`, use
  `max(LPS_ZONE_ATR_MULT * ATR, 0.5 * box_height)`.
- LPS range threshold is `max(base spread percentile, 1.2 * ATR)`.
- The active LPS selector skips non-actionable candidates, then picks the latest
  valid LPS by `end_index`, `low_index`, length, and finally quality.
- `detect_lps_tests` can enumerate up to `max_tests = 8` support-test evidence
  blocks.

Taxonomy:

- LPS should be thought of as two layers:
  1. candidate detector: find all valid LPS/Test-like support behaviors.
  2. setup selector: choose the latest actionable valid one for the current setup.
- Spread decline belongs to quality evidence, not hard gating. Current code now
  matches that principle.
- Volume contraction and descent-shape gates are still hard. They are the next
  likely blind-zone candidates to audit against forward outcomes and missed
  visual winners.

Candidate future simplification:

- Keep zone, length, drop depth, hold, and trigger-above-current as hard geometry.
- Consider moving low/high descent fractions and volume contraction toward
  quality/selector evidence if the edge harness shows they reject visually clean
  winners more than they protect against losers.

## Current-Setup Firing Gates

Source: `core/pipeline/evaluation.py`.

Hard rules after structure passes:

- latest close must not be below `S * CRASH_FILTER_MULT`.
- latest close must not be above `R * EXTENSION_FILTER_MULT`.
- distance to trigger must be positive: current price below trigger.

Taxonomy:

- Keep these as hard setup-state gates. They answer "is there still a trade
  location?"

## Measurement-Only Structure Signals

Sources: `core/structure/metrics.py`, `core/structure/bin_features.py`,
`core/structure/indicators.py`.

Measure-first / evidence:

- bar compression: spread/ATR and spread/box readings.
- contractions: count, progressive tightening, final depth, volume trend.
- support slope: ascending-support quality.
- touch volume z-scores.
- traversal/dead-space metrics.
- Bin A/B/C/D/LPS region features.
- trend template.
- ADR%.

Taxonomy:

- Keep these non-gating unless later archive evidence proves a specific rule.
- They are exactly the right layer for "what makes the setup high quality?".

Hidden/local knobs:

- VCP quality uses fixed weights: 0.40 count, 0.35 progressive tightening,
  0.25 final tightness.
- Volume trend across contractions uses 5% non-rising tolerance and 50/50
  progressive/final-lightest weighting.
- Ascending support quality uses 0.60 slope score and 0.40 higher-low fraction.
- Bin-B CoG uses hard-coded 4-8 adaptive columns and needs at least 8 bars.

## Scoring-Only Knobs

Source: `config/settings.py`, `core/scoring/scoring.py`.

Tier/ranking knobs:

- `TIER_S = 110`
- `TIER_A = 95`
- `TIER_B = 75`
- `TIER_C = 55`
- `S_MAX_BOX_WIDTH = 0.15`
- `SCORE_BASE_AGE = 22`
- `BASE_AGE_CAP_DAYS = 120`
- `SCORE_TOUCH_DENSITY = 25`
- `SCORE_VOL_CONTRACTION = 20`
- `SCORE_LPS_TIGHTNESS = 20`
- `SCORE_BOX_TIGHTNESS = 22`
- `SCORE_ATR_SQUEEZE = 8`
- `SCORE_UPTREND_BONUS = 15`
- `SCORE_RS_BONUS = 15`
- `SCORE_52W_HIGH_PROXIMITY = 8`
- `SCORE_BREADTH_BONUS = 8`
- `SCORE_CONTRACTION = 12`
- `SCORE_ASCENDING_SUPPORT = 8`
- `SCORE_ADR = 8`

Scoring ramp knobs:

- `MIN_STRONG_YEARLY_RETURN = 0.30`
- `MAX_STRONG_YEARLY_RETURN = 0.60`
- `RS_LOOKBACK_BARS = 126`
- `RS_MAX_EXCESS_RETURN = 0.30`
- `HIGH_PROXIMITY_FULL_PCT = -0.05`
- `HIGH_PROXIMITY_ZERO_PCT = -0.20`
- `BREADTH_FULL_PCT = 0.60`
- `BREADTH_ZERO_PCT = 0.35`
- `CONTRACTION_IDEAL_MIN = 2`
- `CONTRACTION_IDEAL_MAX = 6`
- `CONTRACTION_FINAL_TIGHT_PCT = 0.03`
- `CONTRACTION_FINAL_LOOSE_PCT = 0.12`
- `ASCENDING_SUPPORT_FULL_SLOPE = 0.10`
- `ADR_WINDOW = 20`
- `ADR_FULL_PCT = 5.0`
- touch bonus: `TOUCH_BONUS_INDIVIDUAL = 3`,
  `TOUCH_BONUS_TOTAL = 6`, `TOUCH_BONUS_POINTS = 10`

Hidden scoring knobs:

- Touches score at `touches * 2.0` before the touch bonus.
- Traversal-quality density credit is normalized at `density / 0.33` (full credit
  at `TRAVERSAL_QUALITY_DENSITY_FULL`); the rail-blind `oscillation` term it replaced
  has been removed (sub-score, `SCORE_OSCILLATION`, and the archive column are gone).
- LPS tightness and volume contraction are multiplied by `2 * score cap`.
- Base age uses sqrt scaling.

Taxonomy:

- These are not reader knobs. They should not change to fix missed structures.
- Retune only after the archive has enough mixed outcomes.

Frontend sync:

- `webapp/frontend/src/components/setupScoreMath.js` mirrors the current Python
  caps for `box_tightness` and `base_age` (22 and 22). Keep this file in sync
  whenever `SCORE_*` caps change.

## Dead Or Duplicated Knobs

Confirmed dead and removed from `config/settings.py`:

- `TREND_SMA_LOOKBACK`
- `TREND_BULLISH_GAP_MAX`
- `LPS_DROP_MIN`
- `LPS_DROP_MIN_OVERSHOOT_R`
- `LPS_DROP_MAX`
- `BREAKOUT_VOLUME_MULT`
- `BREAKOUT_DEFAULT_VOL_CONTRACTION`
- `BREAKOUT_DEFAULT_TIGHTNESS`
- `CACHE_MAX_AGE_HOURS` (runtime/cache, not algorithm)
- `CONTRACTION_QUALITY_TAG`
- `ASCENDING_SUPPORT_TAG`
- `ADR_TAG`
- `TOUCH_VOL_Z_NO_SUPPLY`
- `TOUCH_VOL_Z_SPRING`
- `TOUCH_VOL_Z_HEAVY_R`

Frontend-owned tag-chip thresholds that intentionally remain in
`webapp/frontend/src/components/setupTagsData.js`:

- `TOUCH_VOL_Z_NO_SUPPLY`
- `TOUCH_VOL_Z_SPRING`
- `TOUCH_VOL_Z_HEAVY_R`
- `firesAt(scores, 'contraction', 0.80)`
- `firesAt(scores, 'ascending_support', 0.80)`
- `firesAt(scores, 'adr', 0.80)`

Private algorithm knobs:

- `INNER_MIN_DAYS = 15` lives in `config/settings.py`.
- Several quality weights are hard-coded inside measurement functions.

## Lowest-Knob Baseline To Aim For

Keep hard:

- universe sanity filters
- root swing existence
- worked Phase-B box: width, boundary respect, two-sided touches, dwell/coverage,
  traversal density
- LPS existence in the right-side/actionable window
- LPS geometry: length, zone, drop depth, hold, trigger still above current price
- crash/extension state gates

Make quality/selector evidence:

- spread decline
- volume contraction strength
- exact descent cleanliness
- rising support
- VCP contraction quality
- support-test clustering
- SOS/reclaim evidence
- inner-box evidence
- V-tip evidence
- touch-volume signatures

Remove or centralize:

- dead constants
- duplicated inner constants
- repeated five-bar edge skip
- stale docs and stale frontend score caps

The guiding simplification: Phase-B decides whether the box is real; LPS decides
whether the setup is active; everything else should mostly help choose/describe
the best story rather than reject the stock outright.

## Recommended Next Work

(The original #1 "keep stale mirrors clean" and #5 "centralize duplicated knobs" are
DONE — see "Status (2026-06-22 cleanup pass)" at the top. What remains is the
substantive, engine-touching work — do it measure-first, each step guard-validated
with `shadow_diff --check` + `seed_recall`.)

1. `python -m tools.lps_gate_audit` to show reject/firing deltas by detector gate:
   especially LPS volume, descent fractions, zone, and range thresholds. Analysis-only;
   informs the two refactors below.
2. First-class the Phase-D evidence vocabulary in archive/overlay:
   `support_tests`, `rising_support`, `sos_reclaim`, `inner_box`, `v_tip`, `lps`.
3. Split LPS into explicit candidate detection vs active setup selection.
4. Refresh `strategy_v2.md`'s older Phase-D boundary wording — after the next calibration pass.
