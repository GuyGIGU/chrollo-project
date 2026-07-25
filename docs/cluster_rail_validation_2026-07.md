# Cluster-rail statistic — Task-6 validation record (Rail Program)

Governed by `docs/rail_program_protocol_2026-07.md` §8. The statistic under
test is `cluster_rails` (`engine_alpha/structure/rail_qualification.py`): the
representative resting extreme — R = the highest bar-high with at least
`EQ_MIN_TOUCHES_PER_RAIL` bar-highs resting within `TOUCH_TOLERANCE_ATR` ATRs
of it, S mirrored. No new knobs: both constants are the touch machinery's own.

## 1. Why this exists

The operator's ruling: rails sit at bar High/Low — the question a
wick-inflated window poses (NKTR) is WHICH bars' extremes define the rail.
The statistic must answer that with a counting rule the outlier wick cannot
inflate. Its only prospective consumer is the dark cluster-width form
(Task 8); it earns that role ONLY by reproducing the operator's rails
everywhere, not by fixing NKTR.

## 2. Pre-registered acceptance — SEALED BEFORE THE FIRST RUN

Written and committed before `tools.cluster_rail_validation` ever executed;
amending any value after a run requires an operator ruling in the changelog
below (protocol amendment rule).

Over ALL 33 Guided List boxes, on the operator's drawn window, on the sealed
fixture basis (fingerprint `b671e056…`):

- **A. Tolerance:** a cluster rail matches the drawn rail when
  `|cluster − drawn| ≤ 0.5 ATR` (the touch tolerance — the machinery's own
  definition of "the same level").
- **B. Coverage:** at least **60 of 66** rails (33 boxes × 2) within
  tolerance. A missing cluster level (`None`) counts as a failed rail.
- **C. Centering:** median `|delta|` ≤ **0.25 ATR** over all measured rails.
- **D. NKTR lands:** BOTH NKTR rails within tolerance, AND on at least one
  side the cluster rail must sit strictly closer to the drawn rail than the
  plain extreme anchor (max High / min Low) — a statistic that only ties the
  wick anchor solves nothing.
- **E. Tail-fit guard:** if D passes while B or C fails, the definition
  matched only NKTR — the answer is NO (protocol §8).

Verdict is computed by the tool, never eyeballed; the constants are mirrored
in `tools/cluster_rail_validation.py` (`ACCEPT_*`).

## 3. Results — VERDICT: NO (2026-07-25, first run after sealing)

Run: `python -m tools.cluster_rail_validation` at engine `aaf853bd…`,
fingerprint `b671e056…`, 33/33 boxes measured, 0 rails returned None.

- **Coverage 20/66** rails within 0.5 ATR (needed ≥ 60). Median |delta|
  **0.883 ATR** (needed ≤ 0.25). Worst 3.81 ATR (CTOS R).
- **NKTR does not even move:** the cluster level equals the plain extreme
  anchor on BOTH rails (dR +0.65, dS −1.12 ATR) — at the touch tolerance the
  supposed outlier wick has ≥ 3 resting neighbors, so nothing is quarantined.
- **Sensitivity sweep** (k ∈ {2,3,4,5} × tol ∈ {0.1, 0.25, 0.5} ATR, run as
  diagnostic AFTER the sealed verdict, recorded to kill re-proposals): best
  coverage anywhere is **34/66** (k=4, tol=0.1); no cell approaches 60/66.
  The one cell that lands NKTR almost exactly (k=5, tol=0.1: dR 0.03,
  dS −0.04) has coverage 33/66 — the literal tail fit §2.E exists to reject.
- **The systematic signature** is the real finding: cluster R sits ABOVE the
  drawn R and cluster S BELOW the drawn S almost everywhere (often equal to
  the plain extremes). The operator's rails are NOT the outermost level with
  k resting neighbors — where his rail IS the clustered extreme the statistic
  matches exactly (PKE R, SKYT R, NGL-01 R, EGBN S: delta 0.000), everywhere
  else he chooses a **representative interior bar's extreme**.

**Tested-DEAD record:** the outermost-supported-extreme family (any k, any
ATR tolerance) cannot reproduce the operator's drawn rails. Do not re-propose
a cluster/order-statistic LEVEL rule for rail placement; any future
rail-placement statistic must model the operator's ANCHOR-BAR CHOICE (which
bar answers for the rail), not an outermost level. This file plus
`tools.cluster_rail_validation` (sealed acceptance, computed verdict) is the
mechanical tripwire: a re-proposal must beat §2 as written, and the sweep
above shows the whole family cannot.

**Consequence for the Rail Program:** Tasks 7–9 (cluster instrumentation,
dark width form, flip evaluation) are NOT BUILT — their premise failed
validation. NKTR stays a correct miss under the current reading; the margin
campaign (Tasks 3–5) proceeds independently.

## 4. Changelog

- 2026-07-25 — §1–2 sealed pre-run (council-implement build, Rail Program
  Task 6).
- 2026-07-25 — §3 results appended after the first run: VERDICT NO; cluster
  branch terminated.
