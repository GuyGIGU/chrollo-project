# Plan — E3: Puzzle-Quality Graded Sub-Score (`PUZZLE_SCORE_ENABLED`, default-off)

**Branch:** `engine/l2-event-reader` · **Lane:** engine · **Spec:** `specs/engine-reading-quality-e3.md`
**Council plan critique:** 5 seats, all **sound-with-changes**, fully convergent. Every must-fix below is baked in.

## Design (council-hardened)

### Box source — reuse the engine's OWN elected box (Fowler/Performance/Hunt/Ramírez)
The narrative is read on `structure_ctx["structure"].box` — the **exact `EquilibriumBox`** `read_structure`
passed to `find_spring` (`narrative.py:330`) and `find_lps` (`narrative.py:345`) and stored verbatim
(`box=box`, `narrative.py:381`). `assemble_box_narrative` re-runs those detectors on that same object →
reproduces the fired structure's spring/LPS **bit-for-bit**. **Pass it UNMODIFIED:** `s.box`'s anchors are
**absolute** (what `find_lps` wants); the `-pbs` rebasing at `evaluation.py:93` is only for the legacy tuple
and does **not** mutate `s.box`. Reconstructing a box / rebasing anchors would read a *different* structure —
forbidden. `df = prepared["df"]` (the trimmed window `read_structure` used); `atr = structure_ctx["atr_for_zone"]`
(bit-identical to `read_structure`'s `df.iloc[-STRUCTURE_ATR_SAMPLE_OFFSET]['ATR_10']`).
**Inner-box note (documented, intentional):** the puzzle is always read on the **parent** equilibrium box, so in
`lps_in_inner` cases the spine LPS is the parent-frame read and may differ from the engine's inner trigger LPS.
A setup cannot fire without a clean parent box, so `structure.box` is always valid at the score call; `find_spring`/
`find_lps` may each still return None → completeness 1–2, a correct partial bonus.

### Formula — one combined composite, NOT two terms (McKinney)
`completeness` and `chronology` are correlated (`intact` ⇒ all three spine pieces ⇒ completeness ≥ 3), so two
independent additive terms would double-count. One `[0,1]` composite:
```
_puzzle_quality(narrative):
    if not isinstance(narrative, dict): return 0.0          # None (flag-off) / malformed -> neutral
    completeness = int(narrative.get("completeness", 0) or 0)
    chrono = {"intact":1.0, "partial":PUZZLE_CHRONO_PARTIAL, "absent":0.0}.get(
             narrative.get("chronology","absent"), 0.0)
    return PUZZLE_W_COMPLETENESS*(completeness/4.0) + PUZZLE_W_CHRONOLOGY*chrono   # in [0,1]
```
`s_puzzle = _clamp(_puzzle_quality(narrative) * SCORE_PUZZLE_QUALITY, SCORE_PUZZLE_QUALITY)`.
Monotonic (more pieces → higher; intact ≥ partial ≥ absent at equal completeness), bounded, deterministic,
neutral-0.0 on None/empty. **First cut = completeness + chronology only** (defer the per-event cleanliness term;
if added later, route every spine scalar through `_ramp`, cap ≤ 0.15).

### Constants (config/settings.py, beside the candle knobs)
`PUZZLE_SCORE_ENABLED = False` · `SCORE_PUZZLE_QUALITY = 8.0` (sibling of ADR/ASCENDING/BREADTH; ~½ a tier gap)
· `PUZZLE_W_COMPLETENESS = 0.70` · `PUZZLE_W_CHRONOLOGY = 0.30` · `PUZZLE_CHRONO_PARTIAL = 0.50`.

### Flag containment — byte-identical flag-off (Hunt/Performance/McKinney)
In `score_setup` (new keyword-only `narrative: Optional[dict] = None`, sibling of `bar_compression`):
`s_puzzle` starts 0.0; **only inside `if settings.PUZZLE_SCORE_ENABLED:`** is `_puzzle_quality` called and
`s_puzzle` set. `total` adds `+ s_puzzle` (a `+0.0` no-op flag-off → `round(...,1)` byte-identical). The
`'puzzle_quality'` breakdown key is inserted **only** inside the same flag — **absent flag-off** (so `_sub_scores`
is key-identical). Flag-off: `_puzzle_quality` is never called, no key added, total unchanged.

### Eval-chain wiring — the single call site, both twins fold (Ramírez)
In `_score_eval_context` (evaluation.py:431 — the ONE `score_setup` call at :448, reached by both
`_evaluate_ticker` and `_evaluate_at_date` via `_run_eval_chain`):
```
narrative = (assemble_box_narrative(df, structure_ctx["structure"].box, structure_ctx["atr_for_zone"])
             if settings.PUZZLE_SCORE_ENABLED else None)      # zero compute flag-off
score_result = score_setup(..., bar_compression=measurements["bar_compression"], narrative=narrative, **...)
```
NOT in `_evaluate_ticker` / `_build_live_result` / `_measure_base_context` (twin-drift or unconditional cost).

### Archive — behind-flag for E3 (no schema change); surface accrual as an operator decision
E3 ships **no archive columns**: flag-off is fully inert (zero compute, zero new columns, byte-identical).
The A/B is measured by a flag-flip harness (below), not the archive. Ramírez's accrual case (capture grades at
scan time for the matured-data validation) is real but trades the spec's hard "flag-off zero compute" for a small
always-on cost — surfaced as an operator decision (an always-measure `PUZZLE_ARCHIVE_ENABLED` is a clean
follow-up once they opt into the flip path).

### A/B harness (Story 4) — `_evaluate_ticker` both ways (Hunt)
Flip the flag at the settings level and re-evaluate each current fire **on the same bar** off vs on (mirrors the
candle A/B). This avoids the seed best-of-window bar-shift (with the bonus on, the max-score eval-date could move),
so the per-setup lift is like-for-like. Report per setup: `s_puzzle`, off→on Score delta, Tier change,
completeness/chronology, and an `lps_in_inner` flag. `seed_recall --check` stays valid flag-off (bonus = 0).

## Tasks
1. **(settings.py)** add the 5 constants beside the candle knobs.
2. **(scoring.py)** add `_puzzle_quality`; add the flag-gated `s_puzzle` term + conditional `'puzzle_quality'` key to `score_setup` (new `narrative` kwarg).
3. **(evaluation.py)** compute the narrative behind the flag in `_score_eval_context`, thread `narrative=` into the single `score_setup` call; import `assemble_box_narrative`.
4. **(tests)** `_puzzle_quality` units (None/empty→0.0; bounded; monotonic over the 15-combo completeness×chronology domain; native float); flag-off byte-identical (`set(score_setup(...).keys())` unchanged + total unchanged + `assemble_box_narrative` NOT called via a spy); flag-on awards the bonus + adds the key + is bonus-only/capped; tier untouched flag-off; box-source identity (the chain feeds `structure.box`, and the narrative spring matches `find_spring(df, structure.box, atr)`).
5. **(A/B + gates + review + commit)** harness + brief; `pytest` / `shadow_diff --check` (flag-off byte-identical) / `seed_recall --check`; council review; commit to `engine/l2-event-reader` (NOT merge/push); memory. Flip + matured-data validation left gated.

## Surfaced for operator (eyeball / flip decisions)
- The flip (`PUZZLE_SCORE_ENABLED`), the weight (`SCORE_PUZZLE_QUALITY=8`), the split (0.70/0.30), `PUZZLE_CHRONO_PARTIAL=0.50`.
- Archive-always-for-accrual (capture grades now for the matured-data validation) vs behind-flag.
- Whether to flag `lps_in_inner` rows in the A/B (parent-frame puzzle ≠ inner trigger LPS).
- The flip checklist: re-measure full multi-universe scan wall-time flag-on vs off before going live (Performance).
