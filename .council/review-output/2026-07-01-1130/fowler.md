# Fowler (Structural) Review — E3 faithfulness fix

Scope: `core/structure/metrics.py` (`_DETECT` sentinel, two-hop `spring`/`lps` pass-through, docstrings, `injected_lps` capture, `lps_pre_v_dropped` observable + its return-branch duplication) and `core/pipeline/evaluation.py` (call-site injection + comment). Economic test applied — flagged only where the current structure will actually slow the next calibration step or hide a bug, not where it merely reads busy.

Overall: the sentinel design is clean and the one-way `metrics → bricks` boundary is correctly preserved by passing loose bricks (not `Structure`). The docstring corrections are accurate. Findings below are the residue: one genuine two-hats scope leak, and two P3 clarity/duplication items.

---

FINDING:
- Title: F3 `upthrust_terminal` range-clearing change is a second behavioral hat riding on the faithfulness fix
- File: core/structure/metrics.py:1254-1269 (and its test at tests/test_market_structure.py:672-690)
- Principle: The Two Hats rule (Principle 8)
- Severity: P2
- What's wrong: The stated one behavioral change is the inner-LPS injection; but this diff also adds a Phase-D `range` term (with a `anchor > v_bar` guard) to the `upthrust_terminal` clear condition, which moves `upthrust_terminal` output independently of the injection path and is a distinct calibration decision.
- Consequence: The reviewer (and the shadow/A-B evidence) cannot attribute an output move to one cause, and the F3 change is not validated by the injection's own recall/shadow story — two hats in one commit blur what each proved.
- Fix: Split F3 into its own commit with its own before/after evidence, or if it must ride along, call it out explicitly as a second behavioral change with its own parity/recall line rather than folding it into the faithfulness narrative.

---

FINDING:
- Title: `lps_pre_v_dropped` now duplicated across the degenerate-empty and main return dicts, widening an already-flagged schema clump
- File: core/structure/metrics.py:1204-1210 (empty branch) and 1325-1337 (main branch)
- Principle: Data Clumps / Duplicated schema (Principle 5)
- Severity: P3
- What's wrong: The two return branches already hand-maintain the same key set independently; this fix adds `lps_pre_v_dropped` to both, so the narrative's public shape is now asserted in two hand-synced places (and a test at test_market_structure.py:287 pins the bool set), meaning a fourth key added later must be threaded through both branches again.
- Consequence: The next narrative-schema addition is shotgun surgery across two literals that drift silently if one is missed — the exact "keys hand-synced in N places" smell that compounds.
- Fix: Correctly deferred for now (the brief already parks it and the empty branch is intentionally a distinct trace shape), but fold when the schema next grows: build a base dict of the shared keys once, then the two branches override only what genuinely differs (`trace`, the grades). Do not unify the branches wholesale — the empty-vs-summary trace distinction is load-bearing.

---

FINDING:
- Title: `injected_lps` vs the reused local `lps` vs the param `lps` — three bindings of one name, kept correct only by a comment
- File: core/structure/metrics.py:1155-1156 (param), 1194-1196 (`injected_lps` capture), 1214 + 1223-1224 (local `lps` rebind)
- Principle: Names reveal design / Comments as deodorant (Principle 4)
- Severity: P3
- What's wrong: The param `lps` (an injected brick-or-sentinel), the captured `injected_lps` (its pre-shadow snapshot), and the loop-local `lps` (a filtered event dict, a different type entirely) all coexist; correctness rests on the reader honoring the "keep the injected brick before the spine locals shadow the name" comment — the comment exists because the code shadows.
- Consequence: A future edit that reorders the capture below the `spring = lps = None` rebind would silently make `lps_pre_v_dropped` read the event dict instead of the injected brick — a latent trap, not a live bug.
- Fix: Rename the loop-local event binding to `lps_event` (mirroring `sos`/`spring` which are also event dicts, so the whole spine block reads as events) so the param and its snapshot need no defensive comment; the `lp`/`lps` split inside `_box_events_with_meta` is fine as-is (`lp` = the resolved brick, `lps` = the source arg — a clear shadow-free pair).

---

## Points reviewed and found clean

- **`_DETECT` sentinel + loose pass-through (Focus 1):** Clean. `_DETECT = object()` compared with `is` is the idiomatic three-state (detect / inject-brick / inject-None) and the module comment pins the `is`-not-`==` rule for a good reason (dataclass `__eq__`). Passing loose `spring`/`lps` rather than the `Structure` is the RIGHT call — it keeps `metrics → bricks` one-way with no import of `narrative.Structure`, avoiding a dependency cycle. The two kwargs are not a flag-argument smell (they don't switch the function's mode into two behaviors sharing little code — both paths converge on the same translate-and-gate block); they are optional dependency injection with a measure-only default. No finding.

- **Docstring corrections (Focus 2):** Accurate. The stale "no new find_spring/find_lps calls" / "bit-for-bit" claims in both the metrics docstrings and the evaluation.py comment are corrected to the new two-source contract, and the "byte-identical to before" claim is now correctly scoped to the `_DETECT` default path only. The evaluation.py comment (evaluation.py:16-26 of the diff) accurately describes the inner-⊆-parent translation and the two-pass drop. No remaining stale contract found.

- **The inner-⊆-parent assertion (metrics.py:1113):** Correctly guards ONLY the injected path (`if lps is not _DETECT`) and pins a real geometry invariant loudly rather than silently mis-translating — a good defensive placement, not over-assertion.

- **Scope discipline otherwise (Focus 5):** Aside from the F3 hat above, the fix stayed minimal — the `lps_pre_v_dropped` observable is scoped to make the rare gate-drop auditable (not a new gate), and the dashboard/audit-tool edits are the thin display tails of the same change. No opportunistic refactor leaked into the pure detector math.
