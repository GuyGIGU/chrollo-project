# Context Brief for Council Review — Engine Reading-Quality Pass E1

## What this code does
Two measure-first / flag-gated engine changes on branch `engine/l2-event-reader` (off `main`): (A) finish the measure-only L2 "events off the staircase" reader, (B) add a flag-gated candle-spread readability grade to `box_tightness`. Spec: `specs/engine-reading-quality-e1.md`; plan: `PLAN-engine-reading-quality-e1.md`.

## Architecture / what changed (review scope — read the actual files)
- **core/structure/metrics.py** (the crown jewel; measure-only — imported by nothing in `core/pipeline`):
  - `measure_resistance_events` CALIBRATED: a box-relative **near-R bound** (`SOS_NEAR_R_MAX_BOX`) reclassifies far-above-R held reaches as a new `markup` type; a **real-consolidation hold** (`SOS_HOLD_MAX_RANGE_BOX`) requires the printed post-top window to be a tight band (not merely "no drop to low-zone"). Right-edge-honest (`bars_after < hold_min_bars → in_progress`), shakeout-tolerant. New event fields: `near_r`, `consolidation`, `hold_range_box`. v_bar tie-break made deterministic (`(box_pos, bar)`).
  - NEW `measure_support_tests`: S-rail "touch of S that holds" → `test`/`failed`/`in_progress`. A small pure sibling, NOT a clone of the R-rail wave machinery.
  - NEW `read_box_events`: the unified independent event view (reuses `find_spring`, `find_lps`, `measure_resistance_events`, `measure_support_tests`). **Index alignment is the key risk:** `find_spring`/`find_lps` return df-relative bars; resistance/support events are base_df-relative; the assembler normalizes ALL to box-relative (`- box.start_bar`). LPS is Phase-D-gated purely on bar position (`lstart > v_bar`), never on SOS presence. Deterministic ordering `(zone_start, type-priority, rail, anchor_bar)`.
- **core/scoring/scoring.py**: NEW `_candle_readability(bar_compression) → [floor, 1.0]` (self-referential from the three already-guarded spread measures; `pd.isna` neutral 1.0 on missing; reuses `_ramp`/`_clamp`). `score_setup` gained `bar_compression: Optional[dict] = None`; the box-tightness block multiplies `box_tightness_ratio` by the grade ONLY inside `if settings.CANDLE_SPREAD_AWARE:` (default OFF → flag-off path textually unchanged).
- **core/pipeline/evaluation.py**: ONE line — `bar_compression=measurements["bar_compression"]` threaded into the single `score_setup` call (both eval-twins inherit it; EC-3).
- **config/settings.py**: `CANDLE_SPREAD_AWARE=False` + ramp anchors (`CANDLE_GRADE_FLOOR`, `CANDLE_SPREAD_BOX/ATR_CLEAN/MESSY`, `CANDLE_TIGHTBAR_CLEAN/MESSY`) + SOS knobs (`SOS_NEAR_R_MAX_BOX=1.5`, `SOS_HOLD_MAX_RANGE_BOX=0.55`).
- **tools/l2_staircase_render.py**: render upgraded to draw `read_box_events` zones — one fixed color per event CLASS, AREA labels (R-rail up / S-rail down), event-count title line.
- **tests/test_market_structure.py** (+7) and **tests/test_scoring.py** (+4): the calibration/brick/assembler/grade tests.

## Stack in use
Python/pandas/numpy quant engine. NOT touched: FastAPI routes, SQLite schema, parquet writes, React, IBKR. No new persistence (the candle metrics were already archived).

## Accepted conventions (do NOT re-flag)
- **EC-2** NaN-coerce at the pandas boundary (`pd.isna`, never truthiness) — applied in `_candle_readability`.
- **EC-3** fold twin code paths — the candle term enters at the single shared `score_setup` call.
- Measure-first / flag-gated / grades-not-vetoes; geometry is the only veto. Byte-parity is a hard requirement.

## Automated check results
- `pytest -q` → **641 passed** (631 prior + 10 new). 
- `tools.shadow_diff --check` → **no canonical drift** (31 firing tickers) — flag-off containment + L2 measure-only both hold.
- `core.archive.seed_recall --check` → running (firing-invariant for both changes; pre-flight passed at 54.5%).
- Real-data validation: TITN reads spring/test/LPS/ONE-upthrust/zero-SOS (operator anchor); candle A/B preserves clean (TITN grade 1.0) and discounts messy (DHX 0.88); calibration non-destructive on live fires (OLD≡NEW SOS).

## Key things to scrutinize
- Numerical (McKinney): lookahead in the hold/test windows, off-by-one in the new slices, the index-origin merge in `read_box_events`, float comparisons, determinism, the candle ramp/NaN handling, flag-off byte-parity.
- Structure (Fowler): is the assembler boundary right (metrics.py vs tools)? is `measure_support_tests` appropriately minimal (no R-rail clone)? any premature generality for E2/E3?
- Backend/integrity (Ramírez/Hunt): the `score_setup` signature change; lazy settings read; missing-data degrade-not-crash; flag-off as an integrity tripwire.
- Tests (Beck): do the new tests actually pin behavior (over-fire reclassification, real-hold, flag-off identity, neutral-on-missing), or are they tautological?
- Render (Saarinen/Friedman): event-class color/label legibility, overlap, anchor captions.
