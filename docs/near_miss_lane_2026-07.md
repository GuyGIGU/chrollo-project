# The Near-Miss Lane — protocol record (2026-07)

Program: `PLAN-near-miss-lane.md` (13 tasks; council plan 2026-07-26). Measure-first
telemetry for one-leg box-election-gate refusals. **No gate moves; a near-miss never
scores, never fires, never enters the picks.** Gate loosening / margin compensation /
threshold fuzzing are PERMANENTLY out (tested-dead — rail program 2026-07-25).

This document is the lane's committed evidence trail (EC-16): the pre-registration
(§2, sealed BEFORE the census tables were seen), the measured volume counters (§3),
the census evidence (§4, appended at scoring time), and the operator ruling (§5,
appended at the Task-6 sitting with its standing-ruling stamp).

---

## §1 Instruments

- **Volume probe (Task 4):** run-dir scratch (counters only; results recorded in §3).
- **Margin census (Task 5):** `python -m tools.near_miss_census` — full signed-margin
  vectors (`engine_alpha.structure.gate_margins.complete_leg_vector`, native quanta,
  raw numerators, sign-locked) over drawn / examined / junk populations; cached-row
  iteration via `--json`/`--from`; identity + headline pins via `--check`.
- Measurement seams under both: the Task-1 leg registry (`box_gates.GATE_LEGS`), the
  Task-2 framing identity (`election_identity.framing_date_key`), the Task-3 margin
  core. All measure-only; nothing here touches an election.

## §2 Pre-registration — SEALED 2026-07-26, before any census table was seen

Written and committed after the Task-4 volume counters (which carry pair/refusal
COUNTS only, no margin separations) and before the first render of the Task-5 census
report. Scored ONCE against the census; a new candidate taxonomy or narrowness form
requires a fresh pre-registration and a fresh run — never iteration against these
tables.

### §2.1 Candidate leg taxonomies

- **T-FINE-15** — the registry's finest grain, crash IN as its own leg:
  `width, window, respect_share, respect_run, crash, r_touches, s_touches,
  r_touch_thirds, s_touch_thirds, lower_dwell, upper_dwell, mid_dwell, coverage,
  traversal_count, traversal_density`.
  Rationale for crash-in: a slightly-too-deep undercut is a spring-shaped refusal;
  today it vanishes at an early return with no trace of how near it was.
- **T-FINE-14** — as above, crash OUT (crash refusals excluded from the lane: the
  crash filter is a catastrophe guard, not a tightness law).
- **T-COARSE-8** — the occupancy family collapsed to ONE leg:
  `width, window, respect_share, respect_run, crash, occupancy, traversal_count,
  traversal_density`. Rationale: the dwell trio partitions to one concept and
  touch-thirds are bounded by touches — "exactly one leg" at fine grain may
  mislabel a single occupancy CONCEPT failing as multi-leg.
- **Policy stages are OUT of every taxonomy** (pre-registered, not rulable):
  `dethroned`, `rescue_unused`, `story` are election policy, not gate legs.
- **Leg dynamics (recorded expectation, not a filter):** window misses self-resolve
  (the base grows into the floor within days); width misses are permanent (a
  framing never narrows). Recurrence semantics (§2.3) must not average the two.

### §2.2 Candidate narrowness definitions

For integer-quantum margins (bars / touches / thirds / bins / traversals and the
count-form dwell legs):

- **N1 (one native quantum):** margin == −1.
- **N2 (two native quanta):** margin ∈ {−1, −2}.

For float-quantum legs (width, crash ratio, traversal density):

- **N-F (junk-calibrated decile):** deficit smaller than the 10th percentile of the
  junk population's deficits on that same leg (the nearest tenth of junk mass) —
  computed per leg from the census junk rows, stated numerically in the ruling.

Composite candidates put to the ruling: **N1 across T-COARSE-8**, **N1 across
T-FINE-15**, **N2 across T-COARSE-8**, each with float legs under N-F. The ruled
definition becomes ONE predicate (EC-18) with a truth-table pin; **no lane code
that filters by margin exists before that ruling** (the plan's hard gate).

### §2.3 Cross-scan recurrence semantics (menu for the ruling)

- **R-EPISODE:** one row per framing identity (`framing_date_key`), first-seen /
  last-seen / nights-seen counters updated on re-observation.
- **R-NIGHTLY:** one row per (identity, scan date); the census weights by identity.
- Either way the **forward-return clock anchors at the FIRST refusal date** (the
  first-fire analog for a non-fire cohort), and per-night rows are never averaged
  as independent samples (one persistent box ≠ thirty observations).

### §2.4 Retention / purge posture (menu for the ruling)

- **P-KEEP:** rows persist indefinitely (partitioned by `engine_config_version` +
  lane-ruleset version; a re-ruling partitions, never reinterprets).
- **P-MATURED:** rows purge after forward-return maturation + K days.

## §3 Volume counters — Task 4, executed 2026-07-26 (engine `53c208dc…`)

51 evaluations (33 marks at pinned eval days + 18 negative-corpus frames):

| statistic | median | p90 | max |
|---|---|---|---|
| roots consulted / evaluation | 1 | 47 | 54 |
| pair examinations / evaluation | 147 | 2651 | 3612 |
| refusals / evaluation | 146 | 2650 | 3533 |
| **unique framings / evaluation** | **98** | 115 | **118** |
| completable refusals / evaluation | 108 | 2023 | 2294 |
| **exactly-one-leg (T-FINE, canonical law) / evaluation** | **5** | 137 | 245 |

- One-leg share of completed refusals: **5.6%** (2095/37331); the failing-legs
  histogram peaks at 2–3 legs (masked co-failures are the NORM, exactly as the
  plan's watchpoint predicted — the completion primitive is load-bearing).
- Stage-of-death: respect 41,888 (76%) · width 7,508 · occupancy 4,870 ·
  rescue_unused 571 · traversal 158 · dethroned 128 · story 95. Rescued/band
  framings not completable from the trace: 10,379 (the Task-7 seam capture is
  the fix).
- Busiest evaluations: KWR 3,612 pairs · FLG 3,580 · EGBN 3,519 · YPF 3,175 ·
  ORMP-05-08 2,809 — the 69×44 figure is confirmed as the TAIL; the median
  evaluation examines ~147 pairs and holds ~98 unique framings.
- **Sizing consequences (Task 7/8 knobs):** per-evaluation dedup map ≈ 128
  entries; top-K completion per ticker sized against median 5 / p90 137 one-leg
  candidates; write caps sized in the ruling from the census's junk shares.

## §4 Census evidence — appended at scoring time (see seal note below)

*(appended after §2 was committed; the census is scored once)*

## §5 Operator ruling — Task 6 (pending)

*(the closed decision menu, the ruling, and the standing-ruling stamp land here;
every citing surface updates in the same change — EC-15/EC-16)*
