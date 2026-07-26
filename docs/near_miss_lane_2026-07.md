# The Near-Miss Lane — protocol record (2026-07)

Program: [`docs/archive/PLAN-near-miss-lane.md`](archive/PLAN-near-miss-lane.md)
(13 tasks; council plan 2026-07-26 — retired to the committed archive per
EC-16; review 2026-07-26 finding 13). Measure-first
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

## §4 Census evidence — scored once, 2026-07-26

Basis: marks fingerprint `b671e056…`, junk fixture captured_at
`2026-07-03T12:20:14+00:00`, engine `53c208dc…`. Cached rows + full report:
`tools.near_miss_census --json` run of 2026-07-26. §2 was committed at
`docs(lane)` BEFORE this section's tables were first rendered. NOTE
(review 2026-07-26 finding 11): the branch ships at engine `28498359…`
after three named seam rotations, so the 2026-07-26 cache is superseded —
`--from` correctly REFUSES it now. Re-verification path: a fresh walk, or
`tools.near_miss_census --check`, whose pins carry the counts re-verified
at every rotation (unchanged through all three).

### §4.1 Junk co-failure structure (1,805 deduped proposed candidates)

- exactly-k failing legs, T-FINE-15: `{0:19, 1:75, 2:248, 3:284, 4:199, 5:160,
  6:207, 7:387, 8:128, 9:76, 10:21, 11:1}` — **one-leg junk = 75 (4.2%)**.
- exactly-k, T-COARSE-8: `{0:19, 1:104, 2:281, 3:536, 4:587, 5:230, 6:44, 7:4}`
  — coarse one-leg = 104.
- Top co-failing pairs: `respect_share+respect_run` 1,551 (the shared-mask twins,
  exactly as pre-registered), then `respect_share+coverage` 1,096,
  `respect_run+coverage` 1,069.
- 8,115 rescued/band framings were NOT completable from the trace (trimmed/masked
  windows) — the Task-7 seam capture is the fix; this census under-counts those
  pools by construction and says so.

### §4.2 Junk mass immediately under each floor (failing ONLY that leg)

| leg | n only-this-leg | at −1 | at −2 | at −3 | ≤−4 |
|---|---|---|---|---|---|
| respect_share | **58** | 7 | 5 | 8 | 38 |
| traversal_density (float) | 4 | nearest −0.007 / −0.019 / −0.035 | | | |
| lower_dwell | 3 | 2 | 1 | 0 | 0 |
| s_touch_thirds | 2 | 2 | 0 | 0 | 0 |
| mid_dwell | 2 | 1 | 1 | 0 | 0 |
| coverage | 2 | 1 | 1 | 0 | 0 |
| width (float) | 1 | nearest −0.057 | | | |
| respect_run | 1 | 1 | 0 | 0 | 0 |
| upper_dwell | 1 | 0 | 1 | 0 | 0 |
| traversal_count | 1 | 1 | 0 | 0 | 0 |

The junk one-leg mass is **77% respect_share**; every other leg's whole-corpus
only-fail count is 1–4 candidates. An N1 band (margin −1) holds ~7 junk
respect_share candidates and ~8 across ALL other integer legs combined.

- Passing-candidate headroom: 19 junk candidates pass every leg (they died at
  selection or downstream); thinnest legs `width×6, s_touch_thirds×4,
  r_touch_thirds×3, respect_share×3, s_touches×2, r_touches×1`, several at
  margin +0 — floors sit where junk begins, measured again.

### §4.3 The examined-candidate separation (the converting statistic)

- **EGBN:2026-01-15 (MISS): the engine-examined candidate at as_of sits at
  0.000 box-heights off the drawn rails and fails EXACTLY ONE leg —
  `lower_dwell` 3/4, margin −1.** The lane's flagship class is visible to the
  lane: the plan's "EGBN invisible" expectation held for the STORY-pool
  conversion (never proposed at a story-passing shape), but the refusal record
  itself is a textbook one-quantum near-miss. Junk-only-this-leg mass beside
  it: 3 candidates (−1, −1, −2).
- YPF:2026-05-18 examined: `lower_dwell −1 + mid_dwell −1` — two legs at
  T-FINE, ONE (occupancy) at T-COARSE. (Fires live via the story pool since
  2026-07-26 regardless.)
- ORMP:2026-05-08 examined: six failing legs (respect-killed, deep) —
  correctly far from any narrowness band. PKE: 3 legs (−1/−1/−3). SKYT:
  respect_share −5 — deep, plus universe-gate class.
- NOK:2026-02-17 examined: passes every box-election leg (died at
  `selection`/downstream — LPS territory, outside this lane's scope by
  boundary).
- Several HITS' examined candidates are one-leg refusals (JAZZ, VLO, MS
  respect_share −1; EWTX lower_dwell −1) — nearest-to-drawn framings that
  miss narrowly while the ticker fires via another framing; whether fired
  tickers' refusals enter the review cohort is a ruling axis (§5 menu — noted
  as a post-table addition, policy not narrowness).

### §4.4 What the evidence says about the pre-registered candidates

*(compiled mechanically; the choice is the operator's — §5)*

- **T-FINE-15 + N1:** cohort ≈ 15 junk/corpus + EGBN-class marks; respect_share
  dominance means most rows are respect near-misses.
- **T-COARSE-8 + N1:** adds the YPF-class (occupancy-concept one-leg) at the
  cost of blurring WHICH occupancy check bound; the census keeps the fine
  vector on every row either way (NULL-free evidence, ruling-independent).
- **Crash in/out:** zero crash-only junk candidates in the corpus; keeping
  crash IN costs nothing measured and preserves the spring-shaped-refusal
  telemetry the plan motivated.

## §5 Operator ruling — Task 6 — **CLOSED 2026-07-26, PROVISIONAL until the flip** · ruleset `2026-07-26.A`

The closed five-axis menu was presented in-session on 2026-07-26 with a named
recommended slate and per-option exposure legs (§4 evidence). Provenance,
recorded honestly: the operator continued the build against the presented menu
("…other then that we can continue") — recorded as **adoption of the
recommended slate**, PROVISIONAL-STAMPED: it hardens at the Task-13 flip
decision (explicitly his); a re-rule before the flip re-pins the predicate at
zero archive-seam cost, the flag never having been live.

| Axis | Ruling |
|---|---|
| 1. Taxonomy × narrowness | **T-COARSE-8 + N1**: the eight occupancy checks judged as ONE concept; every failing fine leg within 1 native quantum; float legs (width / crash / traversal_density) within the junk-calibrated decile deficits **0.0081 / 0.0083 / 0.011** |
| 2. Crash filter | **IN**, as its own leg (zero crash-only junk measured; spring-shaped refusals stay visible) |
| 3. Recurrence | **R-EPISODE**: one row per framing identity, first/last-seen + nights-seen; the forward-return clock anchors at FIRST refusal |
| 4. Retention | **P-KEEP**: rows persist, partitioned by `engine_config_version` + lane-ruleset version (a re-ruling partitions, never reinterprets) |
| 5. Fired tickers | **Record always; the review report defaults to non-fired tickers** (`--all` reveals) — the shadow-signal hazard stays managed without discarding evidence |

**The ruled definition is ONE predicate (EC-18):**
`engine_alpha.structure.gate_margins.ruled_near_miss` (+ `coarse_failing_legs`),
constants `NEAR_MISS_MAX_QUANTA` / `NEAR_MISS_*_DEFICIT_MAX` (manifest-listed —
the rotation is the lane's first seam), truth-table pin
`tests/test_near_miss_ruling.py` (the table IS the ruling; a moved row is a
re-ruling). The census delegates (`--check` pins the ruled junk cohort at
**20**); the Task-7 collector and Task-11 report delegate to the same function.
Expected cohort scale at this ruling (census §4): ~20 junk rows per 18-frame
corpus (~1/frame), EGBN-class marks in, YPF-class occupancy-concept misses in.

**MENU CLOSED.** Re-ruling path: edit the predicate + constants (new ruleset
string), re-run `tools.near_miss_census`, re-pin, new seam — never a silent
predicate edit.

## §6 Cost A/B — EXECUTED 2026-07-26 (Task 13; engine `28498359…`)

Interleaved OFF/ON, best-of-3 per leg, 51 replay evaluations (33 marks at
pinned eval days + 18 negative frames):

| measure | pre-registered budget | measured | verdict |
|---|---|---|---|
| per-evaluation p50 | ≤ +1 ms | **+4.47 ms** | **OVER** |
| per-evaluation p95 | ≤ +10 ms | **+122.76 ms** (max +214.25) | **OVER** |
| corpus wall clock | ±2% | **+1.72%** (26.17s → 26.62s) | within |

- Inline screen selectivity (measured, per the pre-registration — never
  asserted): **94.5%** of deduped refusals screened out (4,744/5,018);
  274 completions corpus-wide; cap never bound (0 dropped); 0 completion
  refusals; 0 kill/vector mismatches; **52 ruled rows** on this
  (deliberately junk/busy-heavy) corpus.
- Cost shape: the inline recorder is effectively free; the p95/max tail is
  the DEFERRED completion on busy frames (KWR/FLG/EGBN-class) — up to the
  TOP_K=32 completions per evaluation (the cap never bound, so no frame
  exceeded 32; a "40+ finalists" figure previously here was impossible per
  these counters — corrected, review 2026-07-26 finding 11). Whole-scan
  figure: ≈ +4.5 ms × ~5,500 evaluations ≈ **+25 s (~+2%)** — a SERIAL,
  median-based bound (the live eval phase runs across a worker pool, which
  divides the wall impact; the corpus mean would roughly double the
  per-eval figure — two opposite approximations, stated as such).
- **The pre-registered per-evaluation bounds FAILED; the corpus bound
  held.** Recorded as measured (EC-15) — the budget is not retro-widened.
  The flip is the operator's decision against this record; the named
  levers if the tail matters to him:
  1. lower `NEAR_MISS_TOP_K` (cap the busy tail — the cap never binds at
     32, so a cut to 8–12 bounds the tail roughly proportionally at zero
     median cost; a new seam);
  2. **early-exit completion** (review finding 11, semantics-preserving):
     `ruled_near_miss` needs exactly ONE coarse failing leg, yet the
     completion always finishes the vector — stopping once two coarse
     concepts have failed yields byte-identical rows AND stats (222 of 274
     completions were not_ruled here). Trade: skipped legs skip the
     sign-lock tripwire; size it from the existing counters BEFORE
     building;
  3. accept ~+2% scan wall as the price of the cohort.
  No lever is pulled here.
- **Post-review caveat (2026-07-26, §7):** these numbers predate the
  review fixes — the per-pool dedup grain (finding 1) records strictly
  more refusals and re-materializes band completions, so the deferred tail
  can only have grown. If the flip decision stalls on the per-eval tail,
  RE-RUN this A/B on the fixed branch first. **→ Done: §6b.**

## §6b Cost A/B RE-RUN — EXECUTED 2026-07-27 (post-fix; merged main `38fe0b1`, engine `28498359…`)

Per the §6 caveat, re-measured after the review fixes, on a CLEAN temporary
worktree at the merge commit (the shared checkout carried another program's
uncommitted work — never measured through it). `tools.near_miss_census
--check` ran immediately before on the same worktree: **OK** (fingerprint
`b671e056…`, junk 1805, engine `28498359…`) — the merged instrument is the
sealed instrument. Same protocol: interleaved OFF/ON, best-of-3, 51
evaluations.

| measure | pre-registered budget | §6 (pre-fix) | §6b (post-fix) | verdict |
|---|---|---|---|---|
| per-evaluation p50 | ≤ +1 ms | +4.47 ms | **+7.10 ms** | **OVER** |
| per-evaluation p95 | ≤ +10 ms | +122.76 ms (max +214) | **+57.97 ms** (max +100.77) | **OVER** |
| corpus wall clock | ±2% | +1.72% | **+2.96%** (23.02s → 23.70s) | **OVER (was within)** |

- The per-pool grain is visible in every counter, as the caveat predicted:
  deduped refusal records 5,018 → **5,756** (rescued/band no longer
  shadowed by a strict occupation), completions 274 → **431**, ruled rows
  52 → **96**, selectivity 94.5% → **92.5%** (5,325/5,756 screened out),
  `pool_shadowed` 1; cap still never bound, 0 completion refusals, 0
  kill/vector mismatches.
- The tail measured LOWER despite strictly more completions (p95 +122.8 →
  +58.0; max +214 → +101) — treat that as run-to-run tail variance under a
  different machine state, not an improvement claim. The stable statistics
  — median and corpus wall — both worsened (+4.47 → +7.10 ms;
  +1.72% → +2.96%). Absolute walls also differ from §6 (off-leg 26.17s →
  23.02s): machine state; compare percentages, not seconds.
- **All three pre-registered bounds now FAIL.** Recorded as measured
  (EC-15); the budget is not retro-widened. The §6 levers stand unchanged
  (TOP_K cut / early-exit completion / accept the wall / hold dark) —
  early-exit now sized at **335 of 431** completions not_ruled. The flip
  remains the operator's decision against THIS record.

## §7 Council review + fixes — 2026-07-26 (post-build, pre-flip)

Ten-seat council review of the full branch (run `2026-07-26-2156`; findings
distilled here — the review scaffolding itself is machine-local): **15
findings (3 P1, 10 P2, 2 P3), all fixed on the branch** in four gated
batches (`fix(lane): council review batch A..D`). The load-bearing three:

1. **The dedup key was pool-blind (P1):** a strict kill permanently occupied
   the framing key, so every rescued/band re-judgment booked as a benign
   "repeat" — the lane was structurally blind to two of its three pools.
   Fixed: per-pool records; the deferred cut keeps ONE row per framing by
   pool precedence **strict > rescued > band** (`pool_shadowed` counted).
   **Grain ruling provenance:** the operator delegated the review fixes and
   rulings wholesale ("I don't really understand code like that, so I'll
   leave it you man, Kill it", 2026-07-26); the recommended per-pool grain
   was adopted under that delegation — PROVISIONAL like the §5 slate,
   re-rulable before the flip at zero seam cost.
2. **The deferred phase ran unguarded in the worker (P1):** one lane
   exception (including the sign-lock tripwire, which a one-ulp crash-leg
   basis split could fire on legitimate data) would have voided the whole
   nightly scan. Fixed: per-ticker containment (`lane_errored` counted), the
   crash leg's margin/verdict now share one comparison basis, the writer's
   operational span is covered, and a lane maturation failure can no longer
   fail the fires' shared job record.
3. **Band completions used the strict laws (P2):** width judged at 0.18 on
   a pool that legally measures to 0.23 (phantom second failing leg → never
   ruled), traversal on the wrong window form. Fixed: the electing pool's
   own laws thread into `complete_leg_vector`.

Measurement caveats now attached to older sections: the §3 volume counters
and the §6 cost A/B were measured on the PRE-fix collector (strict-only
records); the per-pool grain records strictly more. The §6 verdicts stand as
recorded (EC-15); re-run before a flip that stalls on the tail.
