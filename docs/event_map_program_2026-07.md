# Event Map program — sealed evidence record (2026-07)

The committed, durable record of the evidence the Event Map program's decisions were made
on. The flag-ledger rows for `EVENT_MAP_ENABLED` (retired — flipped live 2026-07-25) and
`STORY_POOL_ENABLED` (retired — flipped live 2026-07-26) point HERE; the raw captures lived in the
machine-local council run folder (`.council/implement-output/2026-07-25-1707/`, gitignored)
and everything decision-bearing is reproduced below. Reproduce any of it fresh with the
standing instrument:

```bash
python -m tools.research.event_map_census --check
```

(ChrolloDashboard venv python. `--check` recomputes everything from the sealed fixtures +
the calibration DB and pins BOTH the headline evidence and the marks fingerprint — a
re-drawn mark moves the fingerprint and fails the gate by name.)

## 1. The ruling (Task 6 — operator, 2026-07-25)

**Option A** of the census decision menu is the story-pool admission form:

> ≥ 2 completed support tests AND terminal resistance posture AND no terminal support
> drift, on the AS-OF episode read of the candidate window.

Canonical spec: `docs/strategy_alpha.md` → "The rail-episode read" (RULED paragraph).
Live predicate: `engine_alpha/structure/event_map.py::story_admission` (truth table pinned
in `tests/test_event_map.py`). A re-ruling replaces that function, cuts a NEW archive seam,
and re-runs the census — never a silent predicate edit.

## 2. Census evidence the ruling was made on (2026-07-25)

- Populations: 33 Guided List drawn boxes (sealed corpus + calibration-DB windows,
  fingerprint `b671e056a91fc14fea5b8a724b843c7321a26f4d7d7a6aa5b00741dc93df2523`) and 95
  respect-surviving junk candidates from the negative corpus. Ruled at engine manifest
  `ab5bf340…` (pre-flip).
- Pinned headline (the `--check` constants): marks parse (v1) **15/33**; junk parse-pass
  (v1) **17/95**; EGBN drawn-box profile **`S+ S+ S+ R^`** (3 completed S-tests + terminal
  R posture); drift-junk ZEROS — DGII 0/11, CHCT 0/7, COLM 0/10, FLG 0/2 candidates parse.
  DGII and FLG are the two junk cases that FIRED in the bar-dwell A/B — the episode read
  refuses both while admitting the EGBN class: ORDER separates what aggregates never did.
- Form A (= the ruled predicate) on the as-of reads: **22/33 marks admitted at drawn
  rails, zero live junk exposure** — every parsing junk sentence is pool-UNREACHABLE
  (ordinary election stands: KWR/NVT/GOOD) or traversal-killed in-pool; RLGT, the ONE
  pool-reachable junk case, is admitted by NO form.
- Measured in-pool requirement: of 69 junk occupancy deaths, the traversal gate kills 30
  in-pool — it MUST keep judging story candidates (it does; red-stepped guard).
- EGBN drill-down (drawn window, drawn rails):

```
EGBN:2026-01-15 (MISS)  profile: S+ S+ S+ R^
  S completed 2025-12-04..2025-12-10  (5 bars)   knowable 2025-12-15
  S completed 2025-12-24..2025-12-24  (1 bars)   knowable 2025-12-30
  S completed 2025-12-31..2026-01-05  (3 bars)   knowable 2026-01-08
  R open      2025-12-04..2026-01-15  (29 bars)  in-progress  TERMINAL-POSTURE
```

## 3. Fire-level A/B — EXECUTED 2026-07-25 (Task 14)

Sealed-fixture agreement harness (policy v3), 33 marks, baseline vs
`STORY_POOL_ENABLED=true`. **Result: fired-in-window 26/33 → 28/33.**

- **NKTR@2026-04-10 converts** — FIRED 2026-04-09, tier A, via the story pool. Admitting
  sentence `R+ S+ R+ S+ R+ S+~ R^` (the `~` rendering landed 2026-07-26: the final S-test
  is identity-unfixed on fire day and correctly excluded from the as-of counts — admission
  passed on the knowable tests; semantics identical to the A/B capture).
- **YPF@2026-05-18 converts** — FIRED 2026-05-06, tier S, via the story pool. Admitting
  sentence `S+ R+ S+ R^`.
- **EGBN does NOT convert — the honest headline.** The pre-registered expectation ("EGBN
  converts") FAILED: its framing is never PROPOSED at a story-passing shape — the engine
  anchors the pair elsewhere (rail PLACEMENT, upstream of any pool; traced over three
  sessions: drift-on-zone-overlap + the posture prefilter on fire days). The flagship is
  admission-certain at the DRAWN rails (§2) and conversion-blocked at proposal. Its fix is
  the rail-placement program, not any pool or gate change.
- Held expectations: all 26 existing hit elections per-identity byte-identical (canonical
  fields: rails/box/score/tier); whole-shadow-panel identity; negative bench fully
  refused, including RLGT. Zero junk fires.
- Remaining misses flag-ON (5): EGBN (rail placement), NOK, ORMP-05-08, PKE (respect-killed
  = correct), SKYT (universe gate, sma50 9/10 sessions).
- The two conversions are PINNED as a committed end-to-end guard:
  `tests/test_story_pool_guards.py::test_story_pool_elects_the_ab_conversions_end_to_end`
  (real cascade, production flags, story flag on; flag-off proves the fires are
  story-caused).

## 4. Cost A/B (Task 12)

**As-built capture (2026-07-25, fixture panels, best-of-3):**

```
(a) EVENT_MAP substrate, 32 firing tickers:
    per-fire delta ms: median +2.19  mean +2.41  max +10.64

(b) story-pool consultation, 55 panel tickers (37 shadow + 18 junk):
    tickers reaching the last-resort branch: 38/55
    per-consultation delta ms: median +7.53  mean +50.58  max +399.12
      worst: shadow:OPRA +399  junk:DGII +284  shadow:PKOH +245  shadow:WCC +241  junk:RLGT +237
```

**Re-measured 2026-07-26** after the council-review perf pass (boundary respect moved
ahead of the episode read — the O(1) posture prefilter degenerates to "close above R" on
exactly the frames where the pool matters, so respect is the gate that actually kills the
stale pairs; plus an array-view reader entry point that removes the per-pair DataFrame
slice and column copies). Output-invariant by the loop's conjunction property; the
per-identity election battery and the pinned conversions prove it:

```
(a) EVENT_MAP substrate, 32 firing tickers:
    per-fire delta ms: median +3.90  mean +0.00  max +63.65   (noise-dominated —
    the substrate computation is unchanged; the as-built +2.2 median stands as
    the reference, and the mean-zero delta confirms nothing regressed)

(b) story-pool consultation, 55 panel tickers (37 shadow + 18 junk):
    tickers reaching the last-resort branch: 38/55 (unchanged — output-invariant)
    per-consultation delta ms: median +3.28  mean +12.59  max +140.26
      worst: junk:DGII +140  junk:FLG +124  shadow:HOG +91  shadow:PKOH +74  shadow:WCC +59
```

vs the as-built capture: **median −56% (+7.5 → +3.3 ms), mean −75% (+50.6 → +12.6 ms),
tail −65% (+399 → +140 ms)**; the OPRA-class worst case left the top-5 entirely. The
scan-level estimate scales with the mean: roughly **+5–15 s** on a full universe
(was +20–60 s) — inside the order of the BAND flip's own measured cost.

Remaining safe tightening option if ever needed: per-root dedup of identical pair reads
(behavior-preserving memo). The per-consultation SURVIVOR CAP idea is NOT a perf knob — it
changes which pairs enter the pool and requires the full election-stability A/B; do not
exercise it as a routine tweak.

## 5. Seams and standing gates

- `EVENT_MAP_ENABLED` flip (2026-07-25) rotated `engine_config_version`
  `ab5bf340… → e3b000e9…` — the `event_map_*` family's FIRST archive seam; pre-flip NULL
  rows are never backfilled.
- 2026-07-26 (pre-deployment, no live substrate rows existed): episode typing gained the
  `unreadable` outcome (a NaN verdict close no longer prints a false `failed` — contract
  §5) and the profile gained `~` (identity-unfixed verdict) and `?` (unreadable) marks.
  Census re-run: all pins reproduce (EGBN profile unchanged); NKTR's archived admitting
  sentence gains one `~` (semantics identical).
- Standing gates before any merge/flip touching the episode reader:
  `python -m tools.research.event_map_census --check` (fingerprint + headline pins) alongside the
  pytest battery (truth table, truncation invariance, split-side horizon, the pinned
  NKTR/YPF conversions).
- `STORY_POOL_ENABLED` **FLIPPED LIVE 2026-07-26.** The final gate — the operator's
  per-fire chart eyeball of NKTR@2026-04-09 and YPF@2026-05-06 (rendered from the sealed
  fixture with the ENGINE's elected rails/windows/episode tape drawn on) — **PASSED**:
  - Verdict (operator, verbatim gist): "the Support and Resistance on both is correct …
    the engine did a good job at surfacing these pre-breakout." Both elections confirmed
    real tight pre-breakout structure at the engine's own rails (concordance doctrine:
    the pick belongs on the surface; 1:1 rail replication was never the bar).
  - YPF ruled early-but-right: the as-of window ends at the story fire (2026-05-06);
    after it the price broke out, LPS'd 2026-05-12..2026-05-15, then broke out truly —
    the surfacing preceded the real move, which is the job.
  - NKTR's pre-base gap ruled irrelevant: "it doesn't change anything regarding the box
    and its traits" — the election judges the window from the worked equilibrium onward;
    pre-box context is Phase-A material.
  - Flip mechanics executed: `STORY_POOL_ENABLED = True`; STAGE_TAGS entries for
    NKTR:2026-04-10 + YPF:2026-05-18 removed (the tool's converted-miss protocol);
    deliberate reseal `marks_corpus --build-fixture` → **28 pinned hits / 5 staged
    misses**, baseline diff surgical (two status conversions + timestamp + manifest
    restamp only, parquet byte-identical); floors re-pinned 26→28
    (`test_marks_corpus`, `test_story_pool_guards`); the election-stability guard now
    pins the two story-caused hits BY NAME as the only legally off-silent identities.
  - The flip rotates `engine_config_version` `e3b000e9… → 53c208dc…` — the story pool's
    archive seam; story fires archive `elected_pool='story'` +
    `story_admission_profile` from here forward.

## 6. Marks-fingerprint re-pin — 2026-08-10 (bookkeeping; the evidence did not move)

`--check` fails on exactly one pin — `marks fingerprint (ground-truth identity)`: got
`3cee17e01aaf1bc310047f00965b92a22534a152eb2b411727cc623a2ae947d4`, pinned `b671e056…`
(verified pre-existing on a clean main tree). Diagnosis, read-only against the live DB:

- The fingerprint deliberately covers EVERY box-verdict mark in the editable calibration
  DB (`load_box_marks` hashes exactly the rows it returns), not only the 33 Guided List
  marks the census reads. On 2026-07-27 18:09 UTC the operator drew ONE new box mark —
  `UNF@2026-07-10` (label `classic`) — and the whole-DB identity rotated. Timing is
  corroborated by the near-miss lane's flip re-pin earlier that same day, whose fresh
  walk still recorded `b671e056…`.
- The 33 Guided List marks are graduation-identical: the same fingerprint recipe
  recomputed over only the corpus-keyed rows still yields `b671e056…` exactly; every
  corpus-covered field (rails, LPS spans, frame digests, knowable_from, notes) matches
  the sealed corpus; no Guided List mark was edited after 2026-07-24. In particular the
  mover was NOT the 2026-07-26 Guided List reseal — the 26→28 reseal moved the
  `marks_corpus` BASELINE (two status conversions, §5), never the calibration DB, which
  is why `marks_corpus --check` kept passing while this gate tripped: the corpus gate
  re-prints its graduation-time provenance fingerprint, the census recomputes the live
  DB identity.
- Admission outcomes reproduce unchanged (re-run 2026-08-10, engine `f1680dd8…`): every
  other `--check` pin green (15/33 v1, 17/95 junk, EGBN `S+ S+ S+ R^`, drift-junk
  zeros), and the full census holds §2's Form-A headline — **22/33 marks admitted at
  drawn rails, zero live junk exposure** (every parsing junk candidate pool-unreachable
  or traversal-killed in-pool; RLGT admitted by no form; 69 occupancy deaths, 30
  traversal kills in-pool).
- Re-pin: `_PINNED_MARKS_FINGERPRINT` → `3cee17e0…`, copied from the check's own output
  (EC-37). `tools.near_miss_census` pins the same axis and drifted the same way (plus
  `engine_manifest`, rotated by the 2026-08-09/10 flips; its distribution pins all still
  reproduce) — its re-pin is a separate deliberate act, not folded into this one.
