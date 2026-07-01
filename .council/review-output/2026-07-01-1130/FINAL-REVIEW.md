# Council Review: E3 faithfulness fix (elected-brick injection + flip-time hardening)

**Scope:** working-tree diff on `engine/l2-event-reader` — `core/structure/metrics.py`,
`core/scoring/scoring.py`, `core/pipeline/evaluation.py`, `output/dashboard.py`,
`tools/l2_staircase_audit.py`, `tests/test_market_structure.py`, `tests/test_scoring.py`.
**Context:** fixes an inner-LPS faithfulness bug — the flag-gated E3 puzzle score re-detected
`find_spring`/`find_lps` on the parent box, so on an inner-LPS fire it described a *different* LPS
than the engine fired (understating completeness for the tightest inner-box setups). The fix injects
the engine's already-elected `structure.spring`/`structure.lps` via a `_DETECT` sentinel; bundles
F3/F4/F5/B1 flip-time hardening. Both flags stay default-off.
**Council dispatched (6 with jurisdiction):** McKinney, Hunt, Ramírez, Fowler, Performance, Beck all
returned findings. No-surface (not dispatched): Saarinen/Friedman/Dodds (no React/visual change),
Leach (no SQLite/parquet/schema).

## Automated gates (Phase 0) — all GREEN
pytest **667 passed** · shadow_diff `--check` **no canonical drift** (flag-off byte-identical) ·
seed_recall `--check` **54.5% = baseline** · puzzle_ab flag-on **51/51 lifted**.

## Verdict: SHIPPING-QUALITY — ZERO P1.
Every focus area verified correct against the real code: the inner-LPS bar-translation is sound
(absolute df bars, `inner ⊆ parent` ⇒ `lstart ≥ 0`, no rebasing); the `_DETECT` three-state sentinel
keeps the measure-only path byte-identical; flag-off is provably inert; the eval-twins fold; the fix
is a net subtraction (removes 2 detector passes/fire); and the rewritten identity test genuinely
pins faithfulness (`seen["lps_arg"] is structure.lps` fails the moment the call site stops injecting).

## P2 — Fix Soon

### 1. Untested `lps_pre_v_dropped == True` observable  ✅ RESOLVED in-branch
| | |
|---|---|
| **File** | `core/structure/metrics.py` (assemble_box_narrative) |
| **Council** | Beck × Carmack — Test Desiderata (Behavioral / Predictive) |

**Finding:** the "never silently drops the elected LPS" guarantee had no test forcing the truthy
branch — only the key's existence was asserted.
**Fix (done):** added `test_e2_injected_lps_gate_drop_is_observable` — injects an elected brick with
no surviving lps event, asserts `lps_pre_v_dropped is True` + the trace note, and controls that
injected-`None` and the detect path both stay `False`.

### 2. Two Hats — F3 behavioral change folded into the faithfulness commit
| | |
|---|---|
| **File** | `core/structure/metrics.py` (upthrust_terminal) |
| **Council** | Fowler × Carmack — Two Hats (Principle 8) |

**Finding:** the F3 `upthrust_terminal` held-range change moves output on its own, mixing a second
behavioral hat into the injection commit.
**Disposition (Chair):** bundled intentionally — this is the single "E3 fix" scope the operator
approved in the brief. It is contained: F3 moves only the flag-on *descriptive* `_puzzle_upthrust_terminal`
field (never the score, never firing), and the flag-off byte-parity of the WHOLE diff is proven by
shadow + seed regardless of hat count. Documented explicitly in the commit message.

## P3 — Consider (dispositions)
- **Fowler — naming shadow (`lps` bound 3 ways):** ✅ RESOLVED — renamed the loop-local to
  `lps_event`, which let the `injected_lps` capture be dropped entirely (observable now reads the
  param directly). Shadow eliminated.
- **Beck — `_ramp` guard test missing the None arm:** ✅ RESOLVED — added `_ramp(None, 0.4, 0.4, 1.0)`
  proving the guard sits before the None/value check.
- **McKinney — inner⊆parent rests on a bare `assert` (stripped under `-O`):** accepted; the following
  `lstart >= 0` gate is a safe fallback and the suite never runs `-O`.
- **Beck — `exp_anchor` re-implements `_clip`:** accepted; the object-identity assertions
  (`seen["lps_arg"] is s.lps`) carry the real pin, so the anchor restatement is a secondary check.
- **Hunt — `lps_pre_v_dropped` present on all narrative paths:** accepted (byte-neutral for every
  consumer; `read_box_events` — the measure-only surface — is unaffected as it returns only events).
- **Ramírez — twins' broad `except (…AttributeError)` could swallow a *future* injection-contract
  drift:** accepted as latent-only (not reachable given `structure.lps` is guaranteed non-None on a fire).
- **Fowler — `lps_pre_v_dropped` widens the deferred schema-dup clump; Performance — a doc-drift
  note + staircase-on-Structure reuse:** accepted / correctly deferred (out of this fix's scope).

## Summary
| # | Finding | Severity | Council | Status |
|---|---------|----------|---------|--------|
| 1 | Untested gate-drop observable | P2 | Beck | ✅ fixed |
| 2 | F3 Two-Hats bundling | P2 | Fowler | Disposed (intentional, documented) |
| 3 | Naming shadow (`lps` ×3) | P3 | Fowler | ✅ fixed (rename) |
| 4 | `_ramp` None-arm coverage | P3 | Beck | ✅ fixed |
| 5 | bare assert / exp_anchor / dict-shape / twin-except / doc-drift | P3 | McKinney/Beck/Hunt/Ramírez/Perf | Accepted |

## Findings Breakdown by Expert
| Expert | P1 | P2 | P3 | Total | Key Areas |
|--------|----|----|----|----|-----------|
| McKinney (Numerical) | 0 | 0 | 1 | 1 | bar-translation (verified sound), assert-under-O |
| Hunt (Integrity) | 0 | 0 | 1 | 1 | byte-parity containment (holds), dict-shape wording |
| Ramírez (Backend) | 0 | 0 | 1 | 1 | eval-twin fold (holds), latent twin-except |
| Fowler (Structure) | 0 | 1 | 2 | 3 | Two-Hats, naming shadow, schema-dup |
| Performance | 0 | 0 | 2 | 2 | net subtraction (confirmed), doc-drift |
| Beck (Tests) | 0 | 1 | 4 | 5 | identity test pins fix; untested observable |
| **TOTAL** | **0** | **2** | **11** | **13** | |

**Post-review:** both P2s addressed (Beck fixed, Fowler disposed+documented); 2 of the P3s fixed, the
rest accepted/deferred. Re-ran pytest 667 + shadow (no drift) after the fixes — still green.
