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

## 3. Results

_(to be appended by the validation run — empty at sealing time)_

## 4. Changelog

- 2026-07-25 — §1–2 sealed pre-run (council-implement build, Rail Program
  Task 6).
