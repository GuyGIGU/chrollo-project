# Structure Reader Upgrade Plan for Claude

Date: 2026-06-20

Owner context: Guy is trying to turn Chrollo from a good tight-box/LPS screener
into a genuinely stateful chart reader: one that understands nested structure,
individual price-action swings, shakeouts/springs, SOS/BUEC, LPS, and the
"Last Supper" large-extension/large-correction risk pattern without inviting
low-quality junk.

This document is a handoff from Codex to Claude for the current structure-reader
pass. It assumes the project rules in `AGENTS.md`: structure measures, scoring
judges, pipeline coordinates; avoid global loosening; no scoring weights or tier
threshold changes unless explicitly requested.

## Executive Summary

The current engine foundation is strong. The live reader is already a
chronological narrative:

`read_structure -> root swing -> parent box -> optional spring -> optional inner box -> active LPS`

The remaining frontier is not adding more indicators. It is teaching the
structure layer to understand swing episodes as semantic chart events:

- a shakeout/spring is not just "a low below S"; it is a down-swing, reclaim,
  and hold sequence;
- an SOS/BUEC is not just "above R"; it is a creek jump, sustained hold, and
  backup-to-edge sequence;
- an LPS is not just "last-bar low"; it is an anchor-high to valley swing whose
  footprint can be terminal, rising-shelf, BUEC-shelf, or clean down-swing;
- a high shelf near resistance can be real seller weakness even if it does not
  traverse the whole parent range;
- a "Last Supper" is an LPS/correction forming too far above the box that
  birthed it, i.e. far from the energy source. It should be measured first as a
  risk axis, not immediately used as a hard reject.

The safest implementation path is to keep the strict existing parent-box path
as the default and add narrow fallback variants only after strict validation
fails:

1. recovered-support re-anchor after shakeout/recovery;
2. high/resistance-shelf box promotion;
3. event-anchored inner-box starts;
4. richer LPS swing labels and archived raw fields;
5. Last Supper measurements as archive/UI context first.

No global relaxation of `_validate_base_quality`, traversal, boundary respect,
or LPS gates should happen. Every new path should be narrow, source-labeled, and
guarded by seed recall, shadow diff, and focused tests.

## What Happened Until Now

### Starting Problem

`docs/refactor_seed_recall_misses_codex.md` listed 8 seed-recall misses after
recent structure changes:

- FOSL 2026-02-18
- GRDN 2026-02-02
- NKTR 2026-04-13
- PGC 2026-03-30
- PKE 2026-02-24
- SILC 2026-04-13
- SYRE 2026-02-12
- TERN 2026-02-23

The work order was: diagnose first, recover only clean visual winners, and keep
the shadow guard green.

### Diagnosed Outcomes

Detailed findings live in `docs/seed_recall_misses_findings.md`.

- FOSL: data-sensitive. Fired in targeted download but appeared in the full
  all-seed miss list.
- GRDN: recovered.
- SILC: recovered.
- SYRE: recovered.
- NKTR: still missed before LPS because no valid box is elected.
- PGC: still missed before LPS because no valid high/tight shelf box is elected.
- PKE: acceptable miss under current rules. Candidate lows are above the LPS
  zone.
- TERN: acceptable miss under current rules. Older LPS is no longer actionable;
  current pullback is shallow as a breakout retest.

### LPS Problems Already Solved

Implemented in `core/structure/lps.py`:

1. Compact rising support shelf:
   - A multi-bar shelf can print its real support low early, then tighten upward.
   - The detector can elect that early window low as the LPS low instead of
     insisting that the final bar be the absolute low.

2. Long shallow BUEC/resistance shelf:
   - An OVERSHOOT_R shelf holding just above old R can use the normal pullback
     floor when price is still sitting low on R.
   - This covers SILC-like behavior: SOS 2026-03-23 -> 2026-03-25, then LPS
     2026-04-06 -> 2026-04-10.

3. Clean anchor-high to final-valley downswing:
   - If highs and lows descend cleanly into the final valley, the window can
     span more of a tight box because it is one readable swing, not broad chop.
   - This covers SYRE 2026-02-09 -> 2026-02-11.

Current targeted spot checks:

| Ticker | Status | Current engine LPS |
|---|---|---|
| GRDN | recovered | 2026-01-22 -> 2026-01-28 |
| SILC | recovered | 2026-04-06 -> 2026-04-10 |
| SYRE | recovered | 2026-02-09 -> 2026-02-11 |
| NKTR | still miss | blocked before LPS |
| PGC | still miss | blocked before LPS |

Validation already run after the LPS work:

- `python -m pytest tests/ -q`: 213 passed
- `python -m pytest tests/test_core_logic.py -q -k "lps"`: 29 passed
- `python -m tools.shadow_diff --check`: pass, no canonical drift across 31
  frozen live outputs

The full `python -m core.archive.seed_recall --fresh` was run after GRDN/SILC
but not after the later SYRE targeted clean-downswing change. The post-GRDN/SILC
run printed 28/55 active seeds re-detected.

## Current Code Architecture to Use

### Narrative Spine

`core/structure/narrative.py`

- `read_structure(df, atr)` is the live entry point.
- It walks candidate roots oldest-first and returns the first complete
  `Structure`.
- A complete structure requires:
  - root swing from `bricks.find_root_swing`;
  - parent box from `bricks.validate_equilibrium`;
  - optional spring from `bricks.find_spring`;
  - optional inner from `bricks.find_inner_box`;
  - mandatory LPS from `bricks.find_lps`, inner first then parent.

Recommendation: keep this spine. Do not fork a second live reader. Add richer
brick variants behind the existing brick functions.

### Brick Adapter Layer

`core/structure/bricks.py`

This is the best place to surface new structure concepts as typed facts:

- `EquilibriumBox`
- `InnerBox`
- `Spring`
- `Lps`

Possible minimal extension:

- add `source: str = "strict"` or `variant: str = "strict"` to `EquilibriumBox`;
- add fields for re-anchored/recovered support only if needed by the dashboard or
  archive;
- keep defaults so existing consumers do not break.

### Box Primitive Layer

`core/structure/box_primitives.py`

This is where current Phase-B validity lives:

- root anchors: `collect_root_anchors`;
- candidate R/S pairs: `collect_zigzag_candidates`;
- strict validity:
  - `_is_boundary_respected`;
  - `_validate_base_quality`;
  - `_apply_traversal_gate`;
- selection: `select_phase_b_candidate`.

Current behavior is intentionally strict:

- a parent range must be worked on both rails;
- lower/upper dwell must both clear `EQ_MIN_HALF_DWELL`;
- mid dwell must not dominate;
- traversal must show rail-to-rail movement.

Recommendation: do not loosen these strict rules globally. Add fallback candidate
pools that run only when the strict pool is empty.

### Existing Swing/Region Measurements

Useful existing pieces:

- `metrics.measure_traversal`: already reads swing limbs inside a box.
- `metrics.measure_support_slope`: already reads rising support/higher lows.
- `bin_features._phase_c_candidate`: already measures spring/shakeout episodes.
- `phase_d.support_test_evidence_starts`: already classifies right-side support
  tests into support cluster, SOS reclaim, and rising support evidence.
- `phase_d.resolve_phase_d_boundary`: already picks the earliest credible
  Phase-D evidence after spring/search floors.
- `measure_bins`: already archives Phase-D, spring, LPS position, and Last
  Supper stretch fields.

Recommendation: reuse these instead of inventing a parallel system. The missing
piece is a shared swing-event vocabulary that these helpers can consume.

## Remaining Misses and Why They Matter

### NKTR: Recovered Support After Shakeout

Guy's intended LPS:

- NKTR LPS: 2026-04-01 -> 2026-04-07

Current failure:

- rejected before LPS;
- the box reader anchors S too low, around the earlier shakeout/reaction low
  near 64.5;
- the visual active shelf is higher, roughly the recovered 68-75 area;
- the current candidate fails because lower dwell is too low after the old low
  becomes dead space.

Human chart read:

- the low event was a shakeout/reaction;
- price recovered;
- the active floor moved higher;
- the right-side LPS should be judged against the recovered working floor, not
  the old shakeout low.

Needed upgrade:

- post-shakeout support re-anchor.

### PGC: High/Tight Shelf Near Resistance

Guy's intended LPS:

- PGC LPS: 2026-03-25 -> 2026-03-27

Current failure:

- rejected before LPS;
- candidate boxes fail dwell/traversal;
- the right side sits high and tight near resistance, which a human reads as
  seller weakness;
- the current Phase-B box validator treats it as insufficient lower-zone work or
  mid/high chop.

Human chart read:

- the shelf near R is the structure that matters;
- it does not need to traverse the full parent range to prove seller weakness;
- the LPS is the small pullback/settle on that high shelf.

Needed upgrade:

- high/resistance-shelf box primitive or event-anchored inner-box promotion.

## Core Design Principle for the Upgrade

Do not make the existing strict box looser.

Instead:

1. Keep the existing strict worked-equilibrium candidate pool exactly as the
   preferred path.
2. If strict candidates exist, select as today.
3. If strict candidates are empty, try narrow alternate structures:
   - recovered-support box;
   - high-shelf/resistance-shelf box.
4. Require the alternate structure to complete with an active LPS.
5. Label the source so the archive can later compare outcomes:
   - `strict`
   - `recovered_support`
   - `high_shelf`
   - possibly `sos_buec` if separated from current SOS trim.

This avoids the trap of making bad wide boxes pass by relaxing dwell/traversal.

## Proposed Upgrade Plan

### Pass 0: Better Diagnostics Before More Detection

Goal: make Claude's implementation loop observable.

Add or extend a read-only diagnostic tool. Options:

- extend `tools.structure_case_audit`;
- or create `tools.structure_event_audit.py`.

The audit should print, for a ticker/as-of date:

- root swings walked by `read_structure`;
- strict box candidates and first binding reject;
- candidate R/S, start date, width, dwell, touches, traversal;
- detected Phase-C spring/shakeout episodes;
- support-test evidence starts;
- possible recovered-support floors;
- possible high-shelf windows;
- LPS candidate windows with anchor high, elected low, low date, trigger, zone,
  and swing type.

Initial cases:

- NKTR as of 2026-04-13
- PGC as of 2026-03-30
- SYRE as of 2026-02-12
- SILC as of 2026-04-13
- GRDN as of 2026-02-02
- TERN as of 2026-02-23 as a negative/actionability control
- PKE as of 2026-02-24 as a negative/zone control

This pass should not change detector output.

### Pass 1: Shared Swing Event Vocabulary

Goal: let box, spring, Phase D, and LPS talk about the same swing episodes.

Suggested implementation location:

- `core/structure/swing_events.py` or small helpers inside `box_primitives.py`
  first, then split only if complexity justifies it.

Use existing pivot machinery:

- `_find_pivots`
- `_build_zigzag`
- `_collapse_swings`

Measure swing limbs as facts:

- start bar/date;
- end bar/date;
- direction: up or down;
- anchor high / anchor low;
- valley / peak;
- percent move;
- ATR move;
- box position of start/end if R/S are known;
- volume ratio or volume z where relevant;
- reclaim bar and hold status when crossing S/R.

Event labels should be measurement facts, not scoring:

- `root_reaction`: BC/SC -> AR;
- `shakeout`: under S, reclaim, hold;
- `spring`: a stronger/validated shakeout matching current Phase-C rules;
- `sos`: sustained above R / creek jump;
- `buec`: backup to edge after SOS;
- `lps_pullback`: anchor high -> valley support test;
- `high_shelf`: tight residence near R;
- `last_supper`: stretched LPS/correction far above source box.

Do not use this to replace the current detectors immediately. First use it to
feed diagnostics and fallback candidate generation.

### Pass 2: Recovered-Support Box Fallback

Goal: recover NKTR-style cases without accepting dead-space wide boxes.

Current problem:

- old S is a real event low but no longer the active support rail;
- lower dwell fails because the old low has become dead space;
- a human would treat that old low as shakeout/reaction context and re-anchor S
  to the recovered shelf.

Suggested shape:

Add a fallback after strict `collect_zigzag_candidates(...)` returns empty:

`collect_recovered_support_candidates(eq_df, base_length, atr_val)`

Candidate requirements:

- there is an identifiable undercut/shakeout/reaction low in the earlier or
  middle part of the candidate window;
- price reclaims above the candidate recovered floor;
- after reclaim, lows hold above the recovered floor with no meaningful failure;
- the recovered floor has multiple touches or a tight low cluster;
- R is still defined by real swing highs, not by a one-off wick;
- box width against recovered S remains within `MAX_BOX_WIDTH`;
- boundary respect is measured against recovered S/R after the recovery floor,
  not against the old shakeout low;
- current LPS must validate against this recovered box.

Use existing pieces:

- `_phase_c_candidate` for spring-like undercut/reclaim/hold logic;
- `measure_traversal(...).last_support_frac` and `coil_floor_pos` to identify
  "old support abandoned early";
- `measure_support_slope` to confirm the recovered right side is not collapsing;
- `detect_lps` as mandatory confirmation.

Important safety guard:

- this fallback should only run when the strict parent candidate pool is empty,
  or when all strict candidates fail specifically on lower dwell/dead-space after
  an old low;
- do not bypass boundary respect;
- do not bypass LPS;
- label the box `source="recovered_support"`.

Expected win:

- NKTR can preserve the shakeout as context while selecting the higher active
  support shelf needed for the 2026-04-01 -> 2026-04-07 LPS.

### Pass 3: High-Shelf / Resistance-Shelf Box Fallback

Goal: recover PGC-style cases where the right-side shelf near R is the real
structure even without full parent-range traversal.

Current problem:

- strict Phase-B validity expects two-sided rail work;
- PGC's meaningful structure is a high/tight shelf showing seller weakness;
- requiring lower-third dwell/traversal at the shelf scale misses the point.

Suggested shape:

Add another fallback pool:

`collect_high_shelf_candidates(eq_df, base_length, atr_val)`

Candidate requirements:

- shelf is in the right half or final third of the parent search window;
- shelf width is tight, preferably materially tighter than parent max width;
- closes reside mostly in upper/mid-upper region relative to the prior parent;
- repeated highs/touches occur near the shelf R;
- lows form a flat or rising shelf floor;
- volume/spread contracts or at least does not expand;
- no sustained failure below shelf S;
- active LPS validates against shelf S/R;
- optional: shelf begins after SOS/reclaim or after a support-test cluster.

Use existing pieces:

- `find_inner_box` already promotes a tighter mini-consolidation but only starts
  from midpoint or inner climax;
- `phase_d.support_test_evidence_starts` already finds support/SOS/rising
  evidence;
- `measure_support_slope` already grades rising lows;
- `measure_bar_compression` can support tightness checks if needed.

Implementation options:

1. Add high-shelf as a new fallback in `box_primitives.py`.
2. Or add more start candidates to `find_inner_box` and let existing
   `inner_box_at` validate them.

Preferred first attempt:

- extend `find_inner_box` start candidates before adding a new box validator:
  - midpoint start, as today;
  - inner climax start, as today;
  - Phase-C recovery bar when a spring exists;
  - first support-test cluster start;
  - SOS reclaim start;
  - rising-support start;
  - final V-tip bar.

Then require `inner_box_at` to pass normal inner validation. This is low churn
and uses existing box logic. If PGC still fails, add a dedicated high-shelf
validator as a second step.

Expected win:

- PGC can be recovered as a high/tight shelf whose LPS is 2026-03-25 ->
  2026-03-27.

### Pass 4: LPS Swing Semantics and Labels

Goal: make LPS output explicit about the type of swing it detected.

Current improvements already exist but are implicit:

- early elected low for rising support shelf;
- shallow BUEC shelf above R;
- clean down-swing range bypass for tight boxes.

Add a public field to LPS candidates:

- `swing_type`

Possible values:

- `terminal_valley`
- `rising_support_shelf`
- `buec_shelf`
- `clean_downswing`
- `undercut_rebound`

Also consider archiving:

- `lps_anchor_bar` / `lps_anchor_date`
- `lps_low_bar` / `lps_low_date`
- `lps_swing_depth_pct`
- `lps_swing_depth_atr`
- `lps_swing_depth_box`
- `lps_swing_type`

This would make Guy's rule explicit:

"Measure LPS from the High of the anchor bar before the pullback to the Low of
the final/elected LPS valley."

Safety:

- do not add scoring weight;
- do not gate by swing type yet;
- archive first so later analysis can tell which LPS types actually work.

### Pass 5: Last Supper Measurement

Goal: turn Guy's "Last Supper" concept into a measurable risk axis.

Existing foundation:

- `measure_bins` already emits:
  - `lps_stretch_atr`
  - `lps_stretch_box`

Definition proposal:

Last Supper = an LPS/correction whose support test forms far above the box that
birthed it. It may still be tradable, but it is no longer close to the cause; it
is a stretched support test after a meaningful extension.

Measure-only fields to consider:

- `last_supper_stretch_atr`: same as current `lps_stretch_atr`;
- `last_supper_stretch_box`: same as current `lps_stretch_box`;
- `last_supper_pullback_from_extension_pct`: recent anchor high to LPS low;
- `last_supper_source_box_age`: bars since price left the source box;
- `last_supper_reclaim_quality`: did price recover cleanly or keep widening?

Initial use:

- display/diagnostic tag only, or archive-only;
- no hard rejection until outcome data proves the threshold;
- maybe warning tag later, similar to "Heavy Resistance".

Do not confuse this with a normal BUEC. A BUEC is near the creek/edge. Last
Supper is when the LPS foot is meaningfully stretched above the source.

### Pass 6: Archive and UI Payload Hygiene

Only after detector behavior is stable:

- add new raw fields to pipeline outputs with underscore prefixes;
- update archive writer/seed parity if fields need persistence;
- keep null-safe defaults for older rows;
- update frontend tags only if a field is stable and useful.

Candidate fields:

- `_box_source`
- `_box_recovered_support`
- `_box_recovery_bar`
- `_box_high_shelf`
- `_lps_swing_type`
- `_lps_anchor_date`
- `_lps_low_date`
- `_last_supper_*`

No scoring changes in this pass.

## Validation Contract

Every implementation step should pass:

1. Syntax:
   - `python -m py_compile <touched backend files>`

2. Unit tests:
   - `python -m pytest tests/ -q`

3. Shadow guard:
   - `python -m tools.shadow_diff --check`

4. Seed recall:
   - targeted first with `core.archive.seed.fired_seeds_fresh(...)`;
   - full when behavior changes are ready:
     `python -m core.archive.seed_recall --fresh`

5. Case expectations:

| Case | Expected |
|---|---|
| GRDN 2026-02-02 | still recovered |
| SILC 2026-04-13 | still recovered |
| SYRE 2026-02-12 | still recovered |
| NKTR 2026-04-13 | recover only if recovered-support box is clean |
| PGC 2026-03-30 | recover only if high-shelf/inner box is clean |
| PKE 2026-02-24 | should likely remain out unless Guy reclassifies |
| TERN 2026-02-23 | should remain out due actionability/current structure |

If shadow diff shows new live tickers, do not automatically accept them. Print
their structure summaries and ask Guy to eyeball. A new live fire is only okay
if it is an intended chart-reader improvement, not drift from loosened gates.

## Suggested Implementation Order for Claude

1. Create diagnostics for NKTR and PGC:
   - no behavior changes;
   - prove exact strict-candidate failure and candidate recovered/high-shelf
     alternatives.

2. Extend `find_inner_box` start candidates:
   - try event-derived starts using existing validation;
   - this is the lowest-churn path for PGC.

3. Add recovered-support fallback:
   - narrow, source-labeled, strict LPS confirmation required;
   - aim at NKTR.

4. Add high-shelf fallback only if extended inner starts do not recover PGC:
   - narrow, source-labeled, strict LPS confirmation required.

5. Add `lps_swing_type` and optional raw swing fields:
   - no behavior change if possible;
   - improves archive and debugging.

6. Add Last Supper raw measurements:
   - archive/UI context first;
   - no score/gate until outcomes prove it.

## Non-Goals

- Do not lower `EQ_MIN_HALF_DWELL` globally.
- Do not lower traversal globally.
- Do not widen `MAX_BOX_WIDTH`.
- Do not make LPS volume/spread gates globally softer.
- Do not replace `read_structure` with a second reader.
- Do not add scoring points for new signals during this pass.
- Do not recalibrate tiers.

## Why This Plan Should Stay Recall-Safe

The existing strict path remains the preferred path. New logic only activates
where the current reader has no valid strict box or no valid event-anchored
inner structure. Each alternate structure must still prove:

- boundaries are respected;
- price is tight enough to be a real shelf/range;
- support/reclaim holds;
- active LPS validates;
- current price is still actionable.

That lets the engine learn the chart-reading nuance Guy is pointing at without
undoing the hard-won improvements that removed dead-space boxes and wide junk.

