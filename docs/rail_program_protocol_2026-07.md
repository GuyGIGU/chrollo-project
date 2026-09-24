# Rail Program — pre-registered campaign protocol (2026-07)

**Status: SEALED before any variant run.** This document is committed BEFORE the first A/B
measurement of the campaign. It exists because this program diagnosed the exact failing values
off the sealed corpus (EGBN lower_dwell 0.1304, YPF lower_dwell 0.1429 / mid_dwell 0.50, PKE
respect 0.77) — it already knows precisely where to park a floor to pass its own gate. Every
criterion below is therefore fixed in advance; a green gate obtained by moving a criterion after
seeing evidence is not a result, it is overfitting with a paper trail.

**Amendment rule:** after the first variant run, ANY edit to a grid, an accept condition, or a
verdict template requires an explicit operator ruling recorded in the changelog at the bottom of
this file. Grids never grow mid-campaign — "the value we need is just off-grid" is a NO, not an
amendment.

---

## 1. Campaign identity (pinned)

| Pin | Value |
|---|---|
| Marks population | `guided-list` (docs/marks/guided_list_2026-07.json, sealed EC-7) |
| Marks fingerprint | `b671e056a91fc14fea5b8a724b843c7321a26f4d7d7a6aa5b00741dc93df2523` |
| Baseline engine manifest hash | `aaf853bd0103bc65afa6356ccc8f898d9e8d1f29f6f142f998a5717abdfa0465` |
| Ratchet baseline | 26/33 must-fire (tools/marks_corpus.py --check, digest-verified fixture) |
| Negative corpus | 18 labeled must-NOT-fire cases (tests/baselines/negative_corpus_meta.json, captured 2026-07-03) |
| Harness policy | HARNESS_POLICY_VERSION = 3 (tools/calibration_harness.py) |

Every report produced under this campaign stamps the population name, this fingerprint, and the
manifest hash of the EXACT configuration it ran (baseline hash for baseline runs; the variant's
effective hash for variant runs). A baseline/variant pair whose stamps do not pair is void
evidence — rerun it, don't argue from it.

Variant runs are **CLI-subprocess only** (`python -m tools.calibration.calibration_harness --variant …`,
`python -m tools.regression.negative_corpus`, `python -m tools.regression.marks_corpus`). The backend's in-process
fired seam is baseline-only by contract. A grading-SEMANTICS change that moves no manifest
constant requires a `HARNESS_POLICY_VERSION` bump in the same change.

## 2. The levers and their FIXED grids

Comparison semantics as implemented in `engine_alpha/structure/box_gates.py`: dwell floors pass
non-strict (`lower_dwell >= floor` and `upper_dwell >= floor`), the mid cap passes non-strict
(`mid_dwell <= cap`), respect passes non-strict (`respect_pct >= floor`).

Grid values are chosen on a coarse natural scale (eighths/tenths), deliberately NOT parked at
the known failing values. The known values (0.1304, 0.1429, 0.50, 0.7727) appear in this
document only as the diagnosis; no grid value is derived from them beyond "the grid must contain
at least one value that would convert, else the A/B is pointless".

### L1 — dwell floor: `EQ_MIN_HALF_DWELL` (baseline 0.15)

- **Grid:** 0.125, 0.10. (Two values, tested independently, full triad each.)
- **Predicted conversions:** EGBN alone; YPF only JOINTLY with L2 (see §3).
- **The statistic in counts:** lower/upper-third close-dwell. A fraction floor `f` over a
  window of `n` closes means "at least `ceil(f·n)` closes in that third". All evidence tables
  print the counts, not just the fractions.

### L2 — mid-churn cap: `EQ_MAX_MID_DWELL` (baseline 0.45)

- **Grid:** 0.50, 0.55.
- **Predicted conversions:** none alone; YPF only JOINTLY with L1 (see §3).

### L3a — respect floor as a RATE move: `MIN_BOUNDARY_RESPECT_PCT` (baseline 0.80)

- **Grid:** 0.75. (One value. 0.70 is pre-declared out of consideration: at the corpus's
  window lengths it tolerates 6+ outside bars on a 20-bar box, which is not a boundary that is
  "respected" in any reading of the doctrine.)
- **Predicted conversions:** PKE.

### L3b — respect floor as a ONE-BAR TOLERANCE (reframing, not a settings value)

- **Single candidate:** `allowed_outside = floor((1 - MIN_BOUNDARY_RESPECT_PCT) · n) + 1` —
  the documented rate, plus grace for exactly one bar.
- **Predicted conversions:** PKE.
- **Mandatory disclosure in EVERY report this framing appears in:** the tolerance is an
  n-dependent loosening — worth ~5 respect points on a 20-bar window and ~1.7 on a 60-bar
  window; it loosens most exactly where windows are shortest and evidence thinnest.
- **Implementation doctrine if accepted:** a behavior change inside the ONE existing respect
  leg in `box_gates.py`, behind a full EC-8 flag — never a `_v2` sibling gate.

**Respect doctrine (both framings):** `MIN_BOUNDARY_RESPECT_PCT` is never loosened on anecdote
(shelf-R lesson, operator-standing rule). ANY reformulation of the respect judgment — the
one-bar tolerance included — IS a respect-gate change and inherits the same doctrine. The
expected outcome of L3a/L3b is NO; that outcome is worth exactly as much as a conversion and is
frozen per §6.

**Selection rule (pre-committed):** if more than one grid value on a lever satisfies ALL accept
conditions, the LEAST-loosening admissible value is chosen. If none is admissible, the lever's
answer is NO. There is no third outcome.

## 3. The YPF coupling rule

YPF's drawn box fails BOTH the dwell floor (0.1429 < 0.15) and the mid cap (0.50 > 0.45).
Converting YPF requires L1 AND L2 to move together. Each lever is evidence-gated SEPARATELY on
its own accept conditions over its own distributions; a YPF conversion justifies neither lever
alone. If L1 is admissible and L2 is not (or vice versa), YPF stays a miss and only the
admissible lever may land (for its other predicted conversions, if any).

## 4. Accept conditions — ALL must hold for a lever value to be admissible

- **A. Predicted conversions only.** The variant converts exactly the misses predicted for that
  lever in §2. Any UNPREDICTED conversion is investigated to root cause before any pin; it is
  never absorbed as good news. If investigation attributes it to the lever loosening something
  the diagnosis didn't name, that is evidence AGAINST the move.
- **B. Zero new negative-corpus fires.** All 18 labeled junk cases still cleanly reject under
  the variant (flag-relevant sibling variants included, per the existing flag-ON corpus tests).
- **C. Junk margin-consumption bound.** For every negative-corpus case, on the moved gate leg:
  the case's margin-to-passing after the move must be at least HALF its baseline margin,
  measured in integer counts with rounding in the junk's favor. A junk chart that stays
  binary-green while the move eats its whole safety margin is a failure of this condition.
- **D. Separation clearance.** Over the Task-2 distributions, the proposed value must sit in a
  visible gap: on the moved statistic, every converting mark must be strictly on the pass side
  and every negative-corpus candidate strictly on the reject side with at least one full
  count-unit (one bar) of clearance at its own window length. If the converting marks sit
  INSIDE the junk range on that statistic — i.e. the populations interleave — the answer is NO
  regardless of what the binary gates say.
- **E. Ratchet pins held, elections and rails diffed.** All 26 baseline hits still fire with
  UNCHANGED elected boxes and rails (the diff is over elections AND rails, not fire counts —
  a loosened floor can let an earlier/wider framing displace a pinned winner; the recorded
  arbitration lesson). Pinned first-fire dates hold.
- **F. Stamped, paired evidence.** Per §1.

## 5. Conversion protocol (per accepted move) — one lever, one signed change, one reseal

The settings diff, the deliberate `--build-fixture` reseal with EXACTLY the predicted keys
removed from `STAGE_TAGS`, and the hard hit-floor bump (26 → 27/28…) land in the SAME commit,
with boundary-value unit pins at the new numbers: just-inside passes, just-outside fails; for
the tolerance framing additionally one-bar-short passes, two-bars-short fails, and a deep or
close-out breach is never the tolerated bar. The manifest-hash rotation is recorded in
`docs/strategy_alpha.md` (each rotation is an archive bin seam — budgeted, never a dribble; one
cause per reseal, never a batch). The change ends with "operator restarts the service
(update_dashboard.bat)".

## 6. NO protocol (per rejected lever value)

A NO lands in three places: (1) the `strategy_alpha.md` tested-DEAD record; (2) the miss keeps
its stage tag (re-tagged deliberately at the closing reseal if its family name changed); (3) the
specific junk charts the flag-ON A/B showed WOULD fire — or whose margin/separation the value
violates — are frozen as labeled negative-corpus cases carrying the lever's name, so any future
re-proposal trips a fixture mechanically.

## 7. Verdict templates (pre-committed; operator units, one sentence per case)

- **YES:** "Moving `<knob>` from `<old>` to `<new>` converts `<case(s)>` — `<case>` has
  `<k>` of `<n>` bars where the gate asked `<k′>`; the nearest junk chart (`<ticker>`) stays
  `<m>` bars clear of the new floor; nothing else moved. Operator: run update_dashboard.bat."
- **NO:** "The floor cannot move to `<X>` without admitting `<named junk tickers>` —
  `<case>` stays a correct miss."
- **NO (separation):** "`<case>`'s `<statistic>` sits inside the junk range (`<junk ticker>`
  at `<value>`) — no floor separates them; `<case>` stays a correct miss."

## 8. NKTR cluster-width program (Tasks 6–9) — pre-registered criteria

- **Validation gate (Task 6, before ANY engine wiring):** the cluster-rail statistic — a pure
  counting/order-statistic (a level where ≥k bar extremes rest within ATR-scaled tolerance;
  never mean/std) — must reproduce the operator's drawn rails over ALL 33 Guided List boxes
  within a tolerance pinned IN the Task-6 evidence doc before NKTR is evaluated, AND land on
  his NKTR rails. A definition that matches only NKTR is a tail fit: NO.
- **Pinned routes:** NaN extremes excluded; non-finite ATR → no cluster rail; fixed tie-break.
  Suffix-precomputable over the eq window (O(1) per pair in the hot loop).
- **Precedence (declared default):** cluster candidates FILL ABSENCE ONLY — they never outrank
  a strict framing. Flipping that later is an operator-ruling event.
- **Flip gates (Task 9):** rail stability under append on the frozen frames; measured flag-off
  vs flag-on cost with a worst-case ceiling on the NKTR-shaped chart (the true cost is
  admission past the width shield); the full flag-ON triad with elections+rails diff. If the
  form converts NKTR only when PAIRED with a respect/width loosening, that is the dead
  engagement lever again: NO.
- **Junk direction pin:** a genuinely wide, volatile chart (SPCB-shaped) must NOT read narrow
  under the cluster form. Both directions are hand-specified measure pins in the Task-8 dark
  build.

## 9. Changelog

- 2026-07-25 — v1 sealed (pre-registration; no variant has run). Author: council-implement
  build, operator GO of the council plan PLAN-rail-program.md.
- 2026-07-25 — campaign EXECUTED, zero amendments: every lever answered NO under this document
  as sealed (L1@0.125 failed only condition D — ten junk dwell-leg crossings; L1@0.10, L2 both
  values, L1+L2, L3a failed E and/or B; L3b's only predicted conversion is provably
  unreachable). Results: docs/rail_program_close_2026-07.md. Amending condition D to accept
  the EGBN conversion remains an available OPERATOR ruling, recorded here if taken.
