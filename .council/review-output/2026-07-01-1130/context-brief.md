# Context Brief for Council Review — E3 faithfulness fix

## What this code does
Chrollo is a deterministic pandas/numpy Wyckoff/VCP structure screener. This diff fixes an
inner-LPS **faithfulness bug** in the flag-gated E3 "puzzle-quality" score: the puzzle read
re-detected `find_spring`/`find_lps` on the PARENT box, so on an inner-LPS fire it described a
*different* LPS than the engine actually elected (understating completeness for the tightest
inner-box setups). The fix injects the engine's already-elected `structure.spring`/`structure.lps`
into `assemble_box_narrative` and removes 2 redundant detector passes per fire.

## The diff (7 files, +214/-46) — all in `.council/review-output/2026-07-01-1130/fix.diff`
- `core/structure/metrics.py` — `_DETECT=object()` sentinel; `_box_events_with_meta` and
  `assemble_box_narrative` gain `*, spring=_DETECT, lps=_DETECT`; default `_DETECT` re-detects
  (measure-only, byte-identical), an injected brick is used verbatim, injected `None` = engine
  elected no piece (no fabrication). Inner-⊆-parent assertion (`lp.start_bar >= box.start_bar`) on
  the injected path. New `lps_pre_v_dropped` observable for the rare late-V gate-drop. F3:
  `upthrust_terminal` now cleared by a held Phase-D `range` (guard `anchor > v_bar`; markup/
  in_progress unchanged). Docstrings corrected (were: "no new find_spring/find_lps calls").
- `core/scoring/scoring.py` — F5: `_ramp` zero-divisor guard (`if full_at <= zero_at: return 0.0`,
  placed BEFORE the `value <= zero_at` check; polarity-safe neutral for the two `1.0 - _ramp(...)`
  inverting callers). Dead code for all six shipped anchors.
- `core/pipeline/evaluation.py` — the single E3 call site now injects `structure.spring`/
  `structure.lps`; the false "bit-for-bit" comment corrected. Flag-gated (PUZZLE_SCORE_ENABLED).
- `output/dashboard.py` — F4: `puzzle_quality` chip added to `sub_payload` CONDITIONALLY (only when
  the scorer emitted it → flag-off card payload byte-identical, no always-present 0.0).
- `tools/l2_staircase_audit.py` — B1: `markup` added to the audit tool's named-event display.
- `tests/test_market_structure.py`, `tests/test_scoring.py` — updated `_nar_spy` (threads spring/lps
  kwargs), rewrote the object-identity test to assert the narrative reads the ELECTED lps (identity
  + spine anchor == elected low_bar), and 3 new tests (sentinel three-state, F3 phase guard, F5 ramp).

## Stack in use
Pure `core/` engine (pandas/numpy) + one output-layer display tuple. NO SQLite/parquet, NO FastAPI
route change, NO React/frontend, NO new schema. Both flags (`PUZZLE_SCORE_ENABLED`,
`CANDLE_SPREAD_AWARE`) stay DEFAULT-OFF.

## Key invariants that must hold
1. **Flag-off byte-identical** to main (shadow-diff + seed-recall guards).
2. **Measure-only `read_box_events` byte-identical** (default `_DETECT` = re-detect, unchanged).
3. **Eval-twins fold** through one `score_setup`/`_score_eval_context` call site (confirmed: seed
   `_evaluate_at_date` → `_run_eval_chain`).
4. Determinism / native-python-JSON leaves (byte-stable).

## Automated check results (Phase 0)
- **pytest: 666 passed** (663 prior + 3 new). GREEN.
- **shadow_diff --check: PASS** — "no canonical drift, 31 firing tickers, all fields and ranking
  unchanged" (flag-off byte-identical).
- **seed_recall --check: PASS** — recall 54.5% (baseline 54.5%), no winners lost.
- **puzzle_ab (flag-on A/B): 51/51 lifted, mean +4.42, max +8.0** — the fix is live and non-crashing.
All green; no pre-existing failures.

## Domain assignments (Chair's scoping)
This is a backend/engine + tests diff. Seats WITH jurisdiction (dispatched):
- **McKinney (Numerical):** metrics.py (bar-translation, inner-LPS, `_deepest_valley_bar`, phases,
  upthrust_terminal), scoring.py `_ramp`. THE crux seat.
- **Fowler (Structure):** the `_DETECT` sentinel design, pass-through, docstring contracts.
- **Hunt (Integrity):** flag-off / measure-only byte-parity, the dashboard conditional, `_ramp`
  neutral, the assertion.
- **Ramírez (Backend):** the evaluation.py call-site injection, eval-twin fold, error surface.
- **Performance:** the detector-reuse (removes 2 passes/fire), no new hot-path cost.
- **Beck (Tests):** the rewritten identity test + 3 new tests — do they PIN the fix or are they hollow?

Seats with NO surface (recorded, not dispatched): Saarinen/Friedman/Dodds (no React/visual change;
dashboard.py is a data-tuple, no component), Leach (no SQLite/parquet/schema).
