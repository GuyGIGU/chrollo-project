# Council Review: Engine Reading-Quality Pass E3 — Puzzle-Quality Graded Sub-Score

**Scope:** branch `engine/l2-event-reader` — `config/settings.py` (PUZZLE_* knobs), `core/scoring/scoring.py`
(`_puzzle_quality` + the flag-gated `s_puzzle` term), `core/pipeline/evaluation.py` (narrative on the engine's
elected box at the single call site + the `puzzle_fields` surface), `core/structure/__init__.py` (re-export),
`tests/test_scoring.py` (E3 tests), `tools/puzzle_ab.py` (A/B harness).
**Nature:** the FIRST baseline-moving L2 wire-in, shipped DEFAULT-OFF (flag-off byte-identical).

**Council dispatched (6):** McKinney, Fowler, Ramírez, Hunt, Performance returned **ship**; Beck **ship-after-fixes**.
**Verdict: SHIPPING-QUALITY — zero P1.** Gates: pytest **663**, shadow **no canonical drift** (flag-off),
seed_recall **PASS (54.5% = baseline)**.

## Plan phase (5 seats, all *sound-with-changes*, fully convergent)
Every must-fix folded in before implementation:
- **Engine's own box, unmodified** — Fowler corrected the brief: `s.box`'s anchors are *absolute* (what `find_lps`
  wants), so pass `structure.box` verbatim; reconstructing/rebasing would read a different structure. Reproduces
  the fired spring/LPS bit-for-bit.
- **One combined composite** (McKinney) — completeness and chronology are correlated, so `0.70·completeness/4 +
  0.30·chrono`, not two terms; cap 8.
- **Both `total +=` and the breakdown key behind the flag** (Hunt); computed at the single shared call site so
  both twins fold (Ramírez); zero flag-off compute (Performance).

## Review phase — findings
**P1: none.**

**P2 (Beck) — fixed in-branch (test coverage):**
1. The flag-off byte-identity was pinned only at the `score_setup` level — Beck *proved* the gap by dropping the
   `if PUZZLE_SCORE_ENABLED` guard around `assemble_box_narrative`: it leaked `_puzzle_*` into every flag-off
   result and ran the assembler flag-off, yet all 7 tests passed (only `shadow_diff` caught it). → Added
   `test_e3_flag_off_result_has_no_puzzle_and_runs_no_narrative` (runs `_evaluate_ticker` flag-off on every fixture
   fire; asserts no `puzzle` key in the result or `_sub_scores`, and that `assemble_box_narrative` is never called
   — a `_boom` spy whose `AssertionError` escapes the eval's except list).
2. The box-source object-identity test returned on the first (parent-LPS) fire, never exercising the inner-LPS
   branch. → Restructured to loop **every** fire, asserting `box is structure.box` (+ the full `(df, atr)` triple
   identity vs what `read_structure` used) and, on inner-LPS fires, `box is not structure.inner` (parent frame is
   the puzzle frame regardless of LPS election).

**P3 — addressed / accepted:**
- Hardened `_puzzle_quality` to self-enforce its `[0,1]` bound (`min(4, max(0, completeness))`) and return neutral
  on a non-numeric completeness (try/except) — closes Beck's "malformed→neutral" + out-of-domain P3s (McKinney/Beck).
- Fowler P3 (spy signature + df/atr identity) folded into the restructured box-source test.
- Accepted/deferred (flip-time, not E3): the redundant `find_spring`/`find_lps` re-run flag-on (reuse
  `structure.spring`/`.lps` only if the flip's full-scan wall-time delta is material — Performance); centralizing the
  `_puzzle_*` surface key names as constants when E3 graduates (Ramírez); recording the flip wall-time in the brief.
- Accepted as-is: the `s_puzzle` upper `_clamp` is dead-on-the-upper-side by construction (defensive, matches the
  sibling convention); `puzzle_fields` hard subscripts are safe (the narrative always carries those keys).

## Confirmed good (across seats)
Formula reproduces every A/B point exactly; monotonic + bounded over the full domain; neutral-0.0 on
None/empty/malformed; flag-off byte-parity by construction (`+0.0` no-op proved over 100k randoms; `_puzzle_quality`
never called flag-off; key only inside the flag — all reads are live `settings.X`, no module-capture/default-arg
binding); both twins fold through the single `score_setup`; the narrative reads the engine's own box by **object
identity** (and reproduces the fired spring/LPS); grades-not-vetoes (bonus-only, capped, `calculate_tier` untouched
— a bonus can only raise a tier); native-python leaves.

## Verdict
Ship to the branch for the operator eyeball — not to main, and **the flag stays OFF**. The flip + the forward-return
validation are gated on the operator's read and the ~07-15+ matured data. Most critical domain at the flip:
Performance (full multi-universe wall-time) + the matured-data validation of the lift.
