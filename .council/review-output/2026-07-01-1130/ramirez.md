# Ramírez (Backend/Pipeline) — E3 faithfulness fix review

Scope: `core/pipeline/evaluation.py` `_score_eval_context` injection + eval-twin fold + error surface, per Chair's dispatch. Verified against `core/structure/narrative.py` (`read_structure`, `Structure`), `core/structure/bricks.py` (`Spring`/`Lps` shapes), `core/archive/seed.py` (`_evaluate_at_date` → `_run_eval_chain`), and both twins' skip-guards.

## Verification summary (all five focus areas)

1. **Eval-twin fold — HOLDS.** `_score_eval_context` (evaluation.py:461-466) is still the single E3 call site. Both twins reach it through ONE chain: live `_evaluate_ticker` (evaluation.py:815) and seed `_evaluate_at_date` (seed.py:158) each call `_run_eval_chain` → `_resolve_structure_context` (evaluation.py:745), which builds `structure_ctx["structure"]` from a single `read_structure` call. The injected `.spring`/`.lps` are read off that one shared `Structure`, so live and replay inject byte-identical bricks by construction. No divergence path — confirmed convention EC-3.

2. **Error surface — SOUND, crashing is correct.** `read_structure` returns a `Structure` only after `if lps is None: continue` (narrative.py:346), so `structure.lps` is guaranteed non-None on EVERY fire path; `.spring` may be None and is explicitly handled (`if sp is not None`, metrics.py). The injected objects ARE the `Spring`/`Lps` dataclasses `find_spring`/`find_lps` produce (bricks.py:81-128) — the same fields the detect path reads — so the injection adds no new `AttributeError` surface. The new `assert lp.start_bar >= start` is the right tripwire: `AssertionError` is NOT in either twin's caught tuple (evaluation.py:816, seed.py:159), so a real inner⊄parent geometry violation propagates and crashes loudly (Principle 1, correct).

3. **Corrected comment — ACCURATE.** The prior "reproduces the fired spring/LPS bit-for-bit" was false (it re-detected on the parent, mis-describing inner-LPS fires); the new comment (evaluation.py:449-459) correctly describes reusing the already-elected bricks.

4. **Alias/boundary — CLEAN.** `_struct = structure_ctx["structure"]` is a thin local read; the injection passes existing dataclass instances as kwargs — no new type, no adapter, `core/` stays pure (Principle 4).

5. **Config-loading — NO new concern.** `settings.PUZZLE_SCORE_ENABLED` is read INSIDE `_score_eval_context`, not at import time, consistent with the file's existing `settings.` usage. No module-level root-config read introduced (Principle 5).

## Findings

FINDING:
- Title: Injection-contract violation surfaces as `AttributeError`, which both eval-twins silently swallow as a skip
- File: core/pipeline/evaluation.py:461-466 (guard at :816; twin at core/archive/seed.py:159-160)
- Principle: Programmer errors are assertion failures — crash, don't recover (Principle 1)
- Severity: P3
- What's wrong: The diff correctly pins the geometry invariant with `assert` (an uncaught `AssertionError` that crashes), but any OTHER contract breach on the injected bricks (e.g. a future refactor making `structure.lps` a differently-shaped object, raising `AttributeError` inside `assemble_box_narrative`) is caught by both twins' broad `except (... AttributeError)` skip-guard and turns a fire into a silent None. The invariant is structurally guaranteed today, so this cannot currently misfire — it is a latent gap in the tripwire, not a live bug.
- Consequence: A future contract drift on the elected bricks would silently drop a setup a human should have seen, rather than crashing — the exact "plausible wrong answer" failure mode, though only reachable if the guaranteed invariant is later broken.
- Fix: None required now; if hardening later, narrow the twins' caught tuple so an unexpected `AttributeError` from the scoring/narrative path propagates instead of joining the operational skip, keeping the tripwire intact.
