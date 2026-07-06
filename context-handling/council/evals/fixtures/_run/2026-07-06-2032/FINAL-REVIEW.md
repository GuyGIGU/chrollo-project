# Council Review — fixtures/sample.py (drill D3/D4)

**Run:** 2026-07-06-2032 · **Mode:** council-review on context-core · **Chair:** Carmack

## Scope
Correctness review of `fixtures/sample.py` (two functions, ~12 lines), respecting `fixtures/conventions.md`.
Out of scope: the rest of the repo, the framework, consequence-free style.

## Context
- `average(values)` sums then returns `total / len(values)`.
- `last_or_none(items)` returns `items[len(items) - 1] if items else None`.
- Grounding gate: `python -m py_compile sample.py` → PASS (defects are runtime, not syntax).
- Memory read first: **AP-1** accepts `last_or_none`'s explicit `len-1` indexing → must not be flagged.

## Council dispatched
McKinney (numerical, 3), Beck (tests, 3), Fowler (structure, 1), Hunt (security, 0 — no surface).
Empty lanes logged, not dispatched: Ramírez, Leach, Pipeline Performance, Dodds, Saarinen, Friedman
(no FastAPI/DB/hot-loop/UI surface in a pure 2-function module).

## Findings

### P1
**1. `average` raises ZeroDivisionError on empty input** — `sample.py:4-8`
`Council: McKinney × Carmack — quality-llm.md P4 (empty-slice / boundary)`
Cross-ref: Fowler (guard placement, structure) · Beck #2 (the missing test that would catch it).
- Finding: with `values == []` the loop leaves `total = 0` and the return divides by `len(values) == 0`.
- Consequence: any caller reaching `average` with an empty sequence (filtered window, empty base) crashes instead of degrading.
- Fix: add an explicit empty-input guard at the top of `average` returning a defined sentinel before the division. **NO code emitted.**

### P2
**2. No test covers `average([])` (empty-input boundary)** — `sample.py:4-8`
`Council: Beck × Carmack — quality-testing.md P5/P4 (missing boundary variant)`
- The regression that would have caught finding #1 up front does not exist. Fix: add a boundary test pinning the agreed empty-case contract (defined return or asserted exception).

**3. No happy-path test pins `average` on a known mean** — `sample.py:4-8`
`Council: Beck × Carmack — quality-testing.md P5/P6 (assert the canonical case)`
- Core behavior has zero regression protection. Fix: assert an independently-reasoned mean within a float tolerance (not `==`).

### P3
**4. `average` does not quarantine NaN/inf** — `sample.py:4-8`
`Council: McKinney × Carmack — quality-llm.md P2 (NaN/inf at the boundary)`
- Real for production numeric data; **Carmack filter demoted P2→P3**: a 2-int teaching fixture has no NaN source, so this is forward-looking. Fix: filter non-finite elements before the mean *if this graduates beyond the fixture*.

**5. `last_or_none` branches untested** — `sample.py:11-12`
`Council: Beck × Carmack — quality-testing.md P5 (enumerate variants)`
- Low stakes (accepted-pattern function). Fix: two small branch tests (last element for non-empty; `None` for empty). The AP-1 indexing style itself is accepted and untouched.

*Folded as cross-references (Carmack filter, synthesis cap): McKinney's dtype-hygiene P3 and Fowler's
guard-placement P3 both reinforce #1 rather than stand alone.*

## Summary
| # | Finding | Severity | Expert | Fix effort |
|---|---------|----------|--------|-----------|
| 1 | `average` ZeroDivisionError on empty input | P1 | McKinney | trivial (one guard) |
| 2 | Missing empty-input test for `average` | P2 | Beck | trivial |
| 3 | Missing happy-path test for `average` | P2 | Beck | trivial |
| 4 | `average` doesn't quarantine NaN/inf | P3 | McKinney | small (contingent) |
| 5 | `last_or_none` branches untested | P3 | Beck | trivial |

Totals: 1 P1, 2 P2, 2 P3.

## Verdict
**Not shipping-quality** — one real P1: `average` crashes on empty input. The single most important
thing: **guard the empty case in `average`**. Most critical domain: **numerical correctness (McKinney)**;
the test-surface gaps (Beck) are what let it hide.

**AP-1 honored:** `last_or_none`'s explicit `len(items)-1` indexing was flagged by **no** worker —
read-before-review + the compound memory effect both held.

## Findings-Breakdown-by-Expert
| Expert | Lane | Raw items | Kept after synthesis |
|--------|------|-----------|----------------------|
| McKinney | numerical | 3 (1 P1, 1 P2, 1 P3) | 2 (#1, #4) + 1 folded |
| Beck | tests | 3 (1 P1→P2, 2 P2/P3) | 3 (#2, #3, #5) |
| Fowler | structure | 1 (P3) | folded into #1 |
| Hunt | security | 0 (clean lane) | 0 |

## Validation (Core phase 10 — each shipped item checked against sample.py)
- #1 ZeroDivisionError — CONFIRMED: `return total / len(values)`, no empty guard; `average([])` → raise.
- #2/#3/#5 missing tests — CONFIRMED: no test file exists for the fixture.
- #4 NaN/inf — CONFIRMED mechanically (`total += v` unfiltered); severity contingent, demoted honestly.
- AP-1 — CONFIRMED against all 4 worker files: `last_or_none` appears in zero findings. No lone dissenter to dismiss.
