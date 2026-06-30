# Council Review: Engine Reading-Quality Pass E1 — L2 Event Reader + Candle-Spread Grade

**Scope:** branch `engine/l2-event-reader` — 7 files (config/settings.py, core/scoring/scoring.py, core/pipeline/evaluation.py, core/structure/metrics.py, tools/l2_staircase_render.py, tests/test_market_structure.py, tests/test_scoring.py).
**Context:** measure-first / flag-gated engine reading-quality work (L2 event reader measure-only; candle grade default-off). Byte-parity is the contract.
**Council dispatched (10):** McKinney (2), Fowler (3), Performance (2), Saarinen (3), Friedman (4), Beck (3) found items; Ramírez / Hunt / Leach / Dodds returned **no findings** (clean in lane).
**Verdict up front: SHIPPING-QUALITY — zero P1.** Automated gates: pytest **642**, shadow **no canonical drift**, seed_recall **PASS (54.5% = baseline, 0 winners lost)**. All P2 findings were addressed in-branch; remaining items are P3 deferrals.

---

## P2 — Fixed in this branch

### 1. `read_box_events` recomputed the full staircase 3× per call
| | |
|---|---|
| **File** | `core/structure/metrics.py` (read_box_events / the two event fns) |
| **Council** | Pipeline Performance × Carmack — cost transparency; Cross-ref: Fowler (twin V-definition), McKinney (determinism) |

**Finding:** the heaviest L2 primitive (`read_box_staircase`) ran once for the V and again inside each of `measure_resistance_events` / `measure_support_tests`. **Fix (applied):** build the staircase ONCE in `read_box_events` and thread `swings` into both event functions as an optional precomputed arg; extracted `_deepest_valley_bar(swings)` so the V definition lives once (resolves McKinney + Fowler + Performance convergence); dropped the vestigial `noise_frac` kwarg no caller passed (Fowler). Verified byte-identical (shadow PASS, 27 L2 tests green, TITN read unchanged).

### 2. Render: event-class colors collided with structural/raw colors; no zone legend
| | |
|---|---|
| **File** | `tools/l2_staircase_render.py` |
| **Council** | Karri Saarinen × Vitaly Friedman × Carmack — color communicates / no visible reasoning behind a rank |

**Finding:** the shaded event-zone classes had no on-image legend (color→class lived only in the docstring), and raw breach markers shared green/red with the confirmed SOS/upthrust zones (opposite epistemic status, same hue). **Fix (applied):** added a second "event zones" legend (each class + color); recolored raw breach markers to neutral grey so "a swing poked the rail" never shares a hue with a classified zone; the title now names + counts provisional `in_progress`/`failed` bands.

### 3. Assembler tests never exercised the non-zero index-origin merge or the tie-break
| | |
|---|---|
| **File** | `tests/test_market_structure.py` |
| **Council** | Kent Beck × Carmack — test what might break / assertions are the test |

**Finding:** both `read_box_events` tests used `box.start_bar=0`, so the `- box.start_bar` translation of `find_spring`/`find_lps` df-relative bars (the stated key risk) was multiplied by zero and untested; the ordering test only checked `zone_start`, leaving the type-priority/rail tie-break unpinned. **Fix (applied):** new `test_l2_read_box_events_offset_origin_translation_and_tiebreak` — a box at `start_bar=3` with `find_spring`/`find_lps` monkeypatched to known df-relative bars, asserting the box-relative translation (`start+2 → 2`, `low start+3 → 3`) AND that a spring (priority 0) precedes an LPS (priority 3) at a shared `zone_start`. Pins the offset merge + the deterministic order + that the reused-detector paths actually emit.

---

## P3 — Deferred (noted, not blocking)

- **McKinney** — translated spring/LPS bars now clamped to `[0, base_n-1]` (belt-and-braces; applied).
- **Saarinen** — same-rail captions can still overprint when two same-rail zones are adjacent in x; the white-bordered boxes + the new legend mitigate it. Stagger on the next render pass if it bites.
- **Friedman** — saved PNGs carry no cache-vintage stamp; the data-vintage caveat is surfaced in prose (`E1_eyeball_2026-06-30.md`). Add a corner timestamp later.
- **Fowler** — the staircase-threading made the 3× recompute moot; no residual.

---

## Findings Breakdown by Expert
| Expert | P1 | P2 | P3 | Total | Key Areas |
|--------|----|----|----|----|-----------|
| McKinney (Numerical) | 0 | 0 | 2 | 2 | V tie-break dedup, bar clamp |
| Fowler (Structure) | 0 | 0 | 3 | 3 | noise_frac, V dedup, 3× staircase |
| Performance (Pipeline) | 0 | 1 | 1 | 2 | 3× staircase recompute |
| Saarinen (UI) | 0 | 1 | 2 | 3 | zone legend, color collisions |
| Friedman (UX) | 0 | 2 | 2 | 4 | zone legend, raw-vs-confirmed color |
| Beck (Tests) | 0 | 2 | 1 | 3 | offset merge + tie-break coverage |
| Ramírez / Hunt / Leach / Dodds | 0 | 0 | 0 | 0 | clean in lane |
| **TOTAL** | **0** | **3 (all fixed)** | **~7** | — | |

## Verdict
The crown-jewel engine math is clean — the three seats whose domain is correctness (McKinney, Hunt) and integrity (Leach) found **no P1/P2**, confirming no lookahead, no byte-parity break, no silent NaN demotion, and no persistence drift. The only structural P2 (the 3× staircase) was a cost/clarity issue, not correctness, and folded naturally with the V-dedup the council triple-flagged. The render and test P2s mattered because the render IS the operator's eyeball instrument and the assembler's index-origin merge was the one stated risk left uncovered — both now addressed. Most critical domain going forward: **McKinney/numerical**, as E2/E3 begin to consume these reads. Ship it (to the branch, for the operator eyeball — not to main).
