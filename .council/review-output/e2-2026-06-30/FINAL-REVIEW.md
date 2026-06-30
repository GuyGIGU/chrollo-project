# Council Review: Engine Reading-Quality Pass E2 — Chronological Assembly + Trace

**Scope:** branch `engine/l2-event-reader` — `assemble_box_narrative` + the `_box_events_with_meta`
extraction in `core/structure/metrics.py`, 13 E2 tests in `tests/test_market_structure.py`, the narrative
print in `tools/l2_staircase_audit.py`.
**Nature:** measure-only chronological assembly of E1's independent event pieces into the Wyckoff puzzle +
an explainable trace. Byte-parity is the contract.

**Council dispatched (5):** McKinney, Fowler, Hunt, Performance returned **ship**; Beck **ship-after-fixes**.
**Verdict: SHIPPING-QUALITY — zero P1.** Gates: pytest **655**, shadow **no canonical drift**, seed_recall
**PASS (54.5% = baseline, 0 winners lost)**.

## Plan phase (5 seats, all *sound-with-changes*, fully convergent)
Every must-fix was folded into the contract before implementation:
- **Spine by filter, not re-detect** — selecting spine pieces by filtering the passthrough `events[]`
  (never re-calling `find_spring`/`find_lps`/`measure_*`), so the LPS Phase-D gate E1 already applied
  cannot be bypassed and no O(n) detector re-runs.
- **Single-sourced V** via `_box_events_with_meta` (one staircase build; the resolved `v_bar` threaded into
  the SOS gate + LPS gate *and* returned for phases — cannot desync).
- **Frozen chronology bars** (spring=tip, SOS=peak, LPS=low), strict `<`.
- **No-lookahead `upthrust_terminal`** (refined to require zero SOS anywhere + no markup/in_progress after
  the last upthrust — enforces the `not(spine.sos and upthrust_terminal)` invariant by construction).
- **Held-tests-only completeness**; **no veto-shaped field**; **native-python JSON leaves**.

## Review phase — findings
**P1: none.**

**P2 (Beck) — fixed in-branch (test coverage):**
1. The `upthrust_terminal` *un-terminal* branch (R-rail markup / in_progress after the upthrust → False;
   S-rail in_progress → stays True) was only passing incidentally. → Added
   `test_e2_upthrust_terminal_un_terminaled_by_later_r_wave` (3 synthetic cases).
2. The chronology strict-`<` boundary (a tie or out-of-order trio must read partial, not intact) was
   unpinned. → Added `test_e2_chronology_strict_order_boundary` + `test_e2_partial_from_single_piece_and_phase_d_at_right_edge`
   (single-piece → partial; V-at-last-bar → Phase-D suppressed).

**P3 — addressed / accepted:**
- Degenerate early-return: added a comment that its empty trace is intentional (vs the summary-only trace
  the main path emits) so a future editor won't unify the paths (Fowler).
- Plan doc drift: updated the helper signature to the shipped 4-tuple `(events, v_bar, base_n, has_valley)`
  (McKinney/Fowler).
- Accepted as-is (cosmetic / tooling, no correctness or byte-parity impact): the guarded second `events`
  scan in `upthrust_terminal` (tiny list, only in the candidate case), the audit tool's triple staircase
  build (offline read-only eyeball tool), the trace `hold_range_box` interpolation (never None on a real
  SOS), and the import-isolation tripwire scanning only `core/pipeline` (Hunt confirmed containment is
  clean repo-wide).

## Confirmed good (across seats)
V single-sourcing (no desync); no right-edge lookahead; deterministic spine selection + strict ordering;
no numpy leakage (exhaustive runtime leaf walk on real data); `read_box_events` refactor output-preserving
(public contract byte-identical); no off-by-one in phases (`B.end+1==D.start`, D suppressed at the right
edge); no veto/threshold encoded; measure-only containment verified repo-wide; exactly one staircase build
per call, spine references into `events[]` (no copy).

## Verdict
Ship to the branch for the operator eyeball — not to main. Most critical domain going into E3:
McKinney/numerical, as the assembled read begins to feed a graded sub-score. Two operator decisions remain
surfaced (markup-after-upthrust un-terminal-ing; Phase-C spring weight in the tally) — both deferred to the
eyeball / E3, neither blocking.
