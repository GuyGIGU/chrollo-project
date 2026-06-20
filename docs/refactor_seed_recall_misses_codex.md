# Codex work order — Diagnose the 8 seed-recall misses

**Owner:** Codex · **Reviewer:** Claude/Guy · **Type:** diagnosis-first; recall recovery only if recall-safe
**Branch:** `codex/simply-working-journal`

---

## 1. What happened

`python -m core.archive.seed_recall --check` currently reports the engine no
longer fires on **8 historical seed winners** (it recovered 4 others). This is
collateral from the recently-landed engine changes (descent-tail gate, LPS
pullback-profile floor, descent-floor retirement, traversal gate). It is NOT a
new regression from the box_primitives extraction (that was proven zero-drift).

**The 8 misses (ticker → seed date):**

| Ticker | Seed date | | Ticker | Seed date |
|---|---|---|---|---|
| FOSL | 2026-02-18 | | PKE | 2026-02-24 |
| GRDN | 2026-02-02 | | SILC | 2026-04-13 |
| NKTR | 2026-04-13 | | SYRE | 2026-02-12 |
| PGC | 2026-03-30 | | TERN | 2026-02-23 |

(SYRE was a known holdout chased last session — see [[project-engine-cleanup]] /
the eval-fold history. Treat it as likely-hard.)

## 2. Goal

**Diagnose, then recover only what is recoverable WITHOUT cost.** Do not blindly
loosen gates. For each miss, find the exact rejection point, decide whether it is
acceptable collateral (the setup genuinely no longer qualifies under the
corrected rules) or a real loss (a clean setup wrongly dropped), and only then
propose a fix — gated hard by the two guards below.

## 3. Method (per ticker — reuse the established instrument→shadow-test loop)

1. **Reproduce.** Re-evaluate the current engine at the seed date. Use
   `core.archive.seed.fired_seeds_fresh(...)` (downloads + scans back; returns
   `{(ticker, date): result|None}`) — the same path `seed_recall --fresh` drives.
   Confirm the miss reproduces (result is `None`).
2. **Localize the rejection.** Walk `core.structure.read_structure(df, atr)` for
   that ticker/date and record WHERE it returns None or drops the setup:
   - no root swing? (Phase A)
   - box rejected? which gate — boundary respect, worked-equilibrium
     dwell/coverage (`box_primitives.validate_base_quality`), the traversal gate
     (`box_primitives._apply_traversal_gate`, TRAVERSAL_MIN / TRAVERSAL_MIN_DENSITY),
     or the descent-tail gate (`metrics.descent_tail_rejects`)?
   - LPS not found? which `lps.detect_lps` reject reason (zone, pullback profile,
     range threshold, window)?
   Use `tools.structure_case_audit` for box-anchoring questions (per
   [[emergent-box-seed-root]] — the box is emergent; don't touch detector math
   before auditing).
3. **Classify** each miss: `acceptable` (rule is correctly excluding it) vs
   `recoverable` (a clean setup lost to an over-strict gate). Note the single
   binding gate and the margin by which it fails.
4. **Propose** — only for `recoverable` ones, and only the minimal change to the
   single binding gate. Prefer a SCORING demotion over a detection-gate loosening
   where the concern is dead-space/quality (the project's repeated lesson —
   [[two-sided-equilibrium-scoring]]).

## 4. Hard guards (a proposal is only valid if BOTH hold)

1. **Seed-recall must not regress:** `python -m core.archive.seed_recall --fresh`
   — the currently-firing seed winners must all still fire (recovering a miss must
   not drop a different winner). Net recall must go **up**, never down.
2. **No new live drift:** `python -m tools.shadow_diff --check` — the baseline was
   just re-captured to the validated output, so it is currently **green**. Any
   proposed change must keep it green (or every drifted ticker must be explicitly
   justified as an intended improvement and the baseline re-captured only with
   Guy's sign-off).
3. `python -m pytest tests/ -q` stays green.

## 5. Deliverable

A short report (here or a new `docs/seed_recall_misses_findings.md`): per-ticker
{rejection point, binding gate, classification, margin}, a recovered/total count,
and for each proposed change the guard results (recall delta, shadow drift,
tests). **Flag every `recoverable` case whose fix is not unambiguously
recall-safe for Guy to chart-eyeball before it lands** — recall recovery has
historically been a human-judgment loop, not an autonomous one.

## 6. Out of scope

Do not re-baseline the shadow guard, do not commit, and do not touch the live
detector thresholds without a passing guard run + reviewer sign-off. Diagnosis
and a guarded proposal is the deliverable; landing changes is a follow-up.
