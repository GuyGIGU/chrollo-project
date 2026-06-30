# Context + Feature Brief for Council Plan — Engine Reading-Quality Pass E1

## Codebase context

Chrollo is a Wyckoff/VCP structure-reader: a deterministic pandas/numpy quant engine (`core/`) wrapped by a FastAPI backend, with a React SPA front-end. This feature touches ONLY the engine math (`core/structure/`, `core/scoring/`, `core/pipeline/`) + tools + tests. No frontend, no FastAPI routes, no SQLite schema, no parquet writes.

The engine reads structure in layers. L0 builds an HH/HL/LH/LL swing skeleton (`core/structure/market_structure.py::label_market_structure`). L2 reads "events off the staircase": `read_box_staircase(base_df, R, S, atr_val)` (metrics.py:632) emits a chronological, rail-annotated labeled staircase; `measure_resistance_events(base_df, R, S, atr_val, *, v_bar, hold_min_bars=6)` (metrics.py:745-892) reads R-rail wave events (SOS/upthrust/range/rejection/in_progress). Both are **measure-only — imported by nothing in `core/pipeline`** (verified: only `tools/l2_staircase_*` + `tests/test_market_structure.py` reference them). So any change to them is shadow/seed byte-identical by construction.

Scoring: `core/scoring/scoring.py::score_setup(...)` returns ~15 sub-scores including `box_tightness`. The box-tightness block (lines 72-86) already has one flag-gated refinement — `TIGHTNESS_ADR_AWARE` (live since 2026-06-30) re-bases width into ADR-widths. There is a `_ramp()` / `_clamp()` helper convention in the scorer.

Eval-twins: the live path (`core/pipeline/evaluation.py::_evaluate_ticker`) and the seed/replay path (`core/archive/seed.py::_evaluate_at_date`) BOTH route through one shared chain `_run_eval_chain` → `_measure_base_context` (computes `measure_bar_compression` → `measurements["bar_compression"]`) → `_score_eval_context` → `score_setup`. A test (`tests/test_scoring.py::test_eval_twins_share_the_folded_core`) enforces the fold. Because both twins hit the SAME single `score_setup` call site, a new scoring input threaded there reaches both with no copy.

The candle-spread metrics ALREADY EXIST measure-only: `measure_bar_compression(base_df, box_height, atr_val)` (metrics.py:13-58) returns `median_spread_atr`, `p80_spread_atr`, `median_spread_pct_box`, `tight_bar_pct`; archived as `_base_median_spread_*`. They are NOT currently passed into `score_setup` — that thread is the candle-spread track's only wiring.

## Stack in use

Python 3.11 / pandas / numpy. `pytest` + two engine regression gates: `tools/shadow_diff.py --check` (compares 9 CANONICAL_FIELDS — Setup, Score, Tier, Base Len, Box Width, LPS Length, _R, _S, _trigger_price — against a frozen baseline) and `core/archive/seed_recall.py --check` (fresh network re-eval of curated winners; firing-invariant so score-only changes can't regress it). NOT in use here: SQLite/SQLAlchemy schema changes, parquet writes, FastAPI routes, React, IBKR.

## Accepted conventions (relevant)

- **EC-2**: NaN-coerce archive/pandas cells with `pd.isna(...)`, never a truthiness test (`bool(np.nan)` is True). The candle metrics can be `None`.
- **EC-3**: Fold twin code paths; logic that must agree across eval-twins lives in ONE shared implementation both import (the single `score_setup` call satisfies this).
- **AP/byte-parity discipline**: detector/score changes ship in small evidence-driven steps validated against shadow + seed; measure-first, flag-gated; geometry is the only veto — richer reads are grades, never gates.
- **Determinism / byte-parity is a hard requirement** (no LLM in product; reproducibility gates the engine).

## Feature scope (AGREED — from specs/engine-reading-quality-e1.md)

ONE engine-lane task, two tracks, on branch `engine/l2-event-reader`, measure-first / flag-gated, surfaced for operator chart-eyeball, committed (NOT merged/pushed):

**Track A — finish the L2 event reader (measure-only):**
1. Calibrate `measure_resistance_events` to stop SOS over-firing in active/extended boxes (AMRZ fires ~15 SOS today): (a) "held" must be a genuine mini-consolidation/tightening, not merely "no drop to the low-zone within `hold_min_bars`"; (b) bound SOS to reaches NEAR R — peaks far above R (`peak_box_pos` 2.0+) are markup, not creek-jumps. Keep the wave-based terminal-outcome model, shakeout-tolerant. Anchors that must hold: AEF Jun-16 SOS, BHF Jun-16 SOS, NMAI Jun-9 spring, TITN run-up = ONE upthrust (zero SOS).
2. Add the remaining independent, AREA-based event-zone bricks (each on its own geometry, NEVER gated on another): spring (reuse `find_spring`), test = touch of S that holds (stage-agnostic — the only genuinely-new detector), LPS (reuse `detect_lps`/`find_lps`, Phase-D-gated), upthrust (already emitted by `measure_resistance_events` as failed+breached — surface it). Assemble them into a unified independent event view for rendering/audit.

**Track B — candle-spread readability grade (flag-gated, default-off):**
3. Thread `measurements["bar_compression"]` into `score_setup` and, behind a new `CANDLE_SPREAD_AWARE=False` flag (sibling of `TIGHTNESS_ADR_AWARE`), multiply the `box_tightness` ratio by a self-referential readability grade ∈ [0,1] composed from the bar-texture measures (spread/box, spread/ATR, tight-bar %). Self-referential normalization (each base vs its OWN box/ATR), NEVER a global bar-width threshold. Grade not veto. Missing metrics → neutral (1.0). Flag-off → byte-identical (containment). TITN must stay clean (spread/box 0.34, spread/ATR 0.68), DHX-class (spread/box ~0.55) must discount.

**Out of scope:** chronological event assembly into the puzzle (E2); any graded puzzle sub-score wiring (E3); wiring L2 events into live firing/eligibility/score/tier; re-weighting existing scoring weights; any change to which setups fire; flipping a flag or locking a threshold without operator eyeball.

## Key observations

- Both tracks are byte-parity-safe by construction; the plan should preserve that (L2 stays out of `core/pipeline`; candle flag stays default-off; candle term enters only inside the existing flag-gated box-tightness block).
- The operator-corrected event taxonomy is load-bearing and must NOT be re-derived: events are AREAS not bars; detect each independently, chronology is a quality grade never a gate; SOS = confirmed by a HOLD (real mini-consolidation), continuation ≠ confirmation, a wave ending in a non-recovering breakdown is ONE upthrust (retroactive), shakeout-tolerant; upthrust = breach above R that fails back; spring = breach below S that reclaims; test = touch of S that holds; SOS+LPS are right-of-the-V (Phase D), tests+upthrusts stage-agnostic. Do NOT re-add the absolute-ATR V-arm check to the spring detector (tight-box bias).
- This is measure → render → OPERATOR EYEBALL → tune. The calibration thresholds (the "near R" ceiling, the real-hold tightness criterion, the candle-grade ramp anchors) are eyeball-gated, not auto-decided.
- Numerical-correctness surface (highest stakes): staircase window slicing / off-by-ones, NaN/None in the candle metrics and ramps, float comparisons on prices/ratios (use tolerances), determinism (no order-dependence), units/scale consistency (box-relative vs ATR-relative vs absolute), no lookahead in the wave terminal-outcome read.
