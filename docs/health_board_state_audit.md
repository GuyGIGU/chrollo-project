# Health Board — State-Taxonomy Engine Audit

Grounding for `specs/market-sector-health-board.md`. Produced by an adversarial 3-reader + synthesis audit of the engine's structure / trend / level surface (2026-06-30). Every state below was checked against real signals; states supported only by firing-only or measure-only surfaces were downgraded. **This is the engine map for council-plan and the implementers — it is not a plan.**

## The core constraint

The health read must be a **separate caller** into the box detector + standalone metrics, NOT `read_structure` with gates removed:
- `read_structure` (`core/structure/narrative.py`) only returns a `Structure` when a full A→B→(C?)→D narrative **with a completed LPS** exists → it collapses a good LPS-less base to `None` (would mislabel real consolidations as no-structure).
- Build on `find_outer_box`/`detect_boxes` (`core/structure/consolidation.py`) for R/S, plus the standalone, gate-free, no-lookahead metrics: `measure_traversal`, `measure_equilibrium`, `read_box_staircase` (`core/structure/metrics.py`), and freshly recomputed `trend_template`/`adr_pct` (`core/structure/indicators.py`) + `dist_52w_high_pct` (`core/pipeline/evaluation.py:300-305`).
- **Recompute per member.** The box fields and enrichment measures are surfaced today only for *firing* rows (prefixed `_`). Reading them off firing output blanks the exact non-firing cohort the board exists to show.
- **Byte-parity:** never touch `_run_eval_chain` / `_resolve_structure_context` / the baseline+crash+extension gates; never mutate shared constants/flags. `us_equities` output stays byte-identical.

## Hidden gate (shapes the whole taxonomy)

The box substrate is **not gate-free**: `collect_root_anchors` (`core/structure/box_primitives.py:52-53`) hard-returns `[]` when `Close <= SMA200`, and `find_outer_box` carries a bullish-context macro gate. So **all box-derived states are unavailable for below-SMA200 members** — they fall to `deep_correction` / `trending` / `no_structure`. Therefore **classify drawdown first** (from the pure `dist_52w_high_pct`), then attempt the box read for the above-SMA200 cohort. Relaxing this refusal for the health path is an engine change to shared primitives → Ask-first / future enhancement.

## State taxonomy (v1)

| State | Definition | Derivation | Confidence | Key caveat |
|---|---|---|---|---|
| **near_resistance** | coiled just under box ceiling R | box-position `(Close−S)/(R−S)` just below 1.0, not yet > R | medium | derived (pipeline arithmetic); needs a box (above-SMA200) |
| **post_breakout_markup** | established base, price now above R | box R, then `Close > R` (extension comparison, veto dropped) | medium | **coarse only**; needs a prior worked box; do NOT use measure-only L2 reader |
| **near_support** | pressed against box floor S | box-position near/below 0 (or high lower_dwell) | medium | derived; a member that fell OUT the box bottom is `deep_correction`, classify from drawdown |
| **consolidating** | worked two-sided box, price inside | box R/S + high `traversal_density`/`is_zigzag`, price in rails | medium | box detector not gate-free (above-SMA200 only); LPS not required |
| **trending** | clean directional move, no base | `trend_template` posture (ma_stack + 200d slope), no box | high | pure gate-free measure; recompute unconditionally; needs ≥200 bars |
| **deep_correction** | large drawdown / near 52w low | large-negative `dist_52w_high_pct` on raw df | high | MUST come from the pure drawdown measure, NOT the crash filter (which rejects the cohort) |
| **no_structure** | no readable base, nothing actionable | box detector empty AND not caught above | high | conflation risk — disambiguate from consolidating/deep_correction FIRST |

## Post-breakout verdict

- **Coarse (`price > established box R`) — feasible now.** Literally the `EXTENSION_FILTER` comparison at `evaluation.py:229` with the `return None` removed, run against a box from the looser detector. No new math, no measure-only readers. Honest v1.
- **Refined (re-anchored base + fresh LPS above the old range = confirmed continuation) — NOT feasible now.** Depends on: the L2 markup/SOS reader (`measure_resistance_events`, `assemble_box_narrative` — measure-only, `PUZZLE_SCORE_ENABLED=False`, wired downstream of the LPS/extension gates so it never runs for a broken-out member); a re-anchoring pass that detects a *new* base above the old R (no current engine surface emits this); HTF re-accum (`HTF_CONTEXT_ENABLED`, measure-only, window-preset calibration debt); matured forward-return data + an operator flip. Deferred to the L2/HTF track.

## Recommended sort key

Decision-proximity buckets: `near_resistance` → `post_breakout_markup` → `near_support` → `consolidating` → `trending` → `deep_correction` → `no_structure`. Tie-break `near_resistance`/`near_support` by absolute box-position distance to the rail (ascending); `post_breakout_markup` by `(Close/R − 1)` ascending (freshest breakouts first). Display-layer ordering over already-derived fields — touches nothing in the firing chain.

## Risks carried forward

- **Only-firing-tickers:** recompute every classifying measure per member; never read off firing output.
- **Measure-only immaturity:** do not build any v1 state on `measure_resistance_events`/`assemble_box_narrative`/HTF re-accum.
- **Hidden below-SMA200 gate:** classify drawdown first; box states are above-SMA200 only.
- **Byte-parity:** separate caller; never drop `read_structure`'s gates inline; never mutate shared chain state.
- **Conflation:** `read_structure` None / empty box merges no_structure + LPS-less base + below-SMA200 correction — disambiguate with the box-only detector + drawdown measure.
- **Labeling latency (not lookahead):** the deliberate `df[:-5]` edge offset (anti-lookahead) means a fresh breakout reads as `near_resistance` for ~5 bars — document so the board isn't mistaken for real-time.
