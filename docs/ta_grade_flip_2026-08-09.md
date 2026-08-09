# TA-Grade flip — 2026-08-09 (the distilled evidence)

`TA_SCORE_V2` went live on the operator's A/B eyeball. This is the EC-16
evidence record the flag ledger cites: what was decided, on what numbers, what
deliberately did not move, and what the re-bless actually re-blessed.

## The decision

Operator, after reading the A/B on the 2026-08-09 scan: **"Sure lets do 62 /52
/42"**, then **"okay the lets do it"**. The tier cuts are his; the fourth cut
(`TIER_C_STRUCT = 32`) continues his own 10-point spacing and was named before
execution — D was empty on that scan under every candidate ladder, so nothing
rode on it.

## The A/B basis — why this scan and not the previous one

The 2026-08-08 read was NOT a valid basis and was rejected at the time. Its
rows predated the grade columns, so `score_setup_quality` was NULL and the
replay graded the term absence-neutral 0 while the stored v1 score still
carried its points. The whole ±31 movers list decomposed to exactly that
differential (LKFN/ELS/CATO −31/−28/−26, ABBV +26; verified 6/6 against the
wire). The tool now banners this basis on both output modes, and the checklist
carries the rule: judge movement only on a scan archived by the merged code.

The 2026-08-09 scan is the first archived under the merged, renamed code —
`setup_quality` populated on 256/256 rows. The A/B reports
`setup_quality_absent_rows: 0` and `identity_ok: true`
(population fingerprint `670c3f85e6497a1b`).

Grades over the 256 fires: **min 35.5 · median 59.0 · mean 58.0 · max 76.3**.
No saturation at either end — the top name reaches 76 of 100, not 100.

## The chosen cuts

Where today's letters landed on the new scale, before any re-base:

| Tier | n | min | median | max |
|---|---|---|---|---|
| S | 92 | 60.7 | 65.3 | 76.3 |
| A | 111 | 52.2 | 56.8 | 72.8 |
| B | 49 | 40.1 | 47.9 | 51.7 |
| C | 4 | 35.5 | 37.2 | 39.1 |

| Candidate | S | A | B | C+D |
|---|---|---|---|---|
| 61.5 / 52.2 / 40.1 (count-preserving) | 92 | 111 | 49 | 4 |
| **62 / 52 / 42 (chosen)** | **85** | **118** | **41** | **12** |
| 60 / 50 / 40 | 114 | 102 | 36 | 4 |
| 65 / 55 / 45 | 53 | 121 | 62 | 20 |

The count-preserving set was rejected on purpose: it reproduced the old S
population exactly but sat **0.19 points** above the next grade — a knife edge
that reshuffles on any scan. 62 is stable and costs seven S names.

### The S/A overlap is the width cap, not a defect

A's ceiling (72.8) sits well above S's floor (60.7). Ten non-S names outgrade
the weakest S, and all ten are above `S_MAX_BOX_WIDTH = 0.15` (0.151 to 0.225);
the widest genuine S is 0.1477, just under the line. Twenty-two of the 111
A-tier names are width-capped. AAP is the sharpest case — 4th-highest grade on
the scan, held at A by a 0.151 box.

The cap therefore **survives the re-base unchanged**, applied on top of the new
ladder. Live proof at the flip: CATO grades 63.9 (above the 62 S-cut) and still
reads tier A on its 0.1799 box.

## What deliberately did NOT move

`SCORE_SPRING` and the four `SCORE_STORY_*` caps stay **0**;
`TA_WARN_TERMINAL_DRIFT` and `TA_WARN_WEAK_MONTHLY` stay **1.0**.

This is measure-first, not caution. Those sub-scores are flag-gated, so the
archive holds no live values to calibrate against — setting a cap now would be
calibrating at add time, the one thing the doctrine forbids. The flip starts
that archive; real costs get set later against it.

The consequence, stated so it is not mistaken for a null result: at these
weights the flip **re-expresses the existing read on a 0-100 scale with
chapters and re-bases the tier ladder — it does not change the judgment.**
Within-date rank movement is **median 0, max ±2**, with 67 of 256 rows moving
at all.

For when the warnings are funded: `terminal_drift` flags 20 names including
LEVI at rank 1 and AON at rank 3, so that dial reorders the very top of the
list the moment it costs anything. `weak_monthly` flags 13, best rank 33.

Mean points per chapter across the 256 fires (of the 58.0 mean grade):

| Chapter | mean points |
|---|---|
| Phase B | 24.58 |
| Phase D | 15.89 |
| Cause | 9.20 |
| Trend | 6.40 |
| Phase C | 1.96 |

Phase C is nearly dormant — springs are rare in this population (69 of 256 on
the archive-wide replay) — and will stay that way until `SCORE_SPRING` is
funded. Breadth (6.5) is excluded from the grade by the regime-layer ruling.

## Measured drift

Across all five flag-on shadow guards and `tools.shadow_diff`, the **only**
canonical drift is:

```
FOF.Tier: B -> A
HVT.Tier: B -> A
```

No score, rail, ranking, or field movement anywhere else — 32 firing tickers,
ranking of 32 unchanged. The tier field's source changed and two fixture names
cross a cut on the new ladder; nothing else did anything.

## Re-bless record (all inside the flip commit — EC-29)

| Step | Result |
|---|---|
| `shadow_diff --capture` → `--check` | PASS — 32 firing tickers, fields + ranking unchanged |
| `seed_recall --fresh-capture` → `--fresh-check` | PASS — recall **66.2%** baselined |
| `marks_corpus --build-fixture` → `--check` | PASS — **ratchet held 28/33**, every expected miss still misses |
| `seed_recall --build-fixture` → `--hermetic-capture` | rebuilt — the offline twin must mirror the fresh baseline, so it follows it at the same seam |
| `fold_parity --capture` | captured, 37 tickers → `output/flip_fold_parity.json` |
| `settings_reference --write` | Quick-Reference regenerated |

The seed-recall baseline was **stale before this flip, not broken by it**: the
pre-flip `--fresh-check` already failed with recall *improved* 56.9% → 66.2%
(7 winners recovered — BODI, LECO, NKTR, NTCT, PBT, VIST, WTS — against one new
miss, KALV). NKTR in that list dates the old baseline to before the story-pool
flip. The recapture records the improvement; it does not paper over a loss.

### One interaction the flip surfaced (not a defect, but now on the record)

With the grade live, `_story_richness_rate` — a measure-only charter field —
became visible to the Event Map's additivity guard, and it moves with that flag
(0.909 map-on vs 0.227 map-off on the fixture ticker). That is the field doing
its job: it CONSUMES the map's completed-S/R and alternation counts, so without
them it reads lower. It was invisible to the guard before only because the whole
v2 field family was absent flag-off.

Production is unaffected — `EVENT_MAP_ENABLED` has been live since 2026-07-25,
and the field is never scored (every `SCORE_STORY_*` is 0). The guard was made
precise rather than loosened: the one map-consuming diagnostic is named and
excluded, and the canonical outputs are now asserted explicitly against
`shadow_diff.CANONICAL_FIELDS` instead of riding on a blanket dict equality —
strictly more teeth than before.

Worth knowing for later: if `SCORE_STORY_*` is ever funded while the map could
be off, this field's map-dependence becomes a scoring dependence. It is not one
today.

## Cost certification (EC-8)

`tools.ta_grade_timing`, 32 firing fixture tickers, worst-case right-edge start:

- **median 0.45 ms · p90 0.62 ms · max 1.02 ms** per fire
- ~0.3 s worst case per 300-fire scan

Better than the post-review baseline (median 0.64 / p90 1.02 / max 1.37) and
three orders inside the evaluation budget.

Payload, measured over 10 live fires: the v2 block is **20 keys, median 1,019
bytes per setup** (min 962, max 1,144) — about **255 KB added at 256 fires**
against a 25.3 MB artifact, roughly 1%.

## Expected churn — named in advance, not a defect

- `engine_config_version` rotates. Calibration chip caches recompute; a new
  IS/OOS seam appears in the edge harness; the calibration harness `--prev`
  comparison will report "ENGINE moved".
- The cockpit's "Fresh S-tier" selects a different population under the
  re-based ladder (85 rather than 92 on the A/B scan).
- Pre-flip rows keep NULL grade columns **forever** — the 2026-08-09
  archive-purity ruling. Measured history lives in the read-only sidecar
  (`tools.ta_grade_archive_replay`), never backfilled.
- The mixed-epoch badges were already lit before this flip by ordinary manifest
  rotations. The flip-day signal is different: the first rows whose GRADE
  columns are non-NULL.

## Still open after this commit

- **The 1536×864 lens eyeball** — the operator's, after `update_dashboard.bat`.
  Two named checks: the 26px grade headline visible without scrolling on a
  graded row, and chapter hover lighting the chart region with the cell's
  is-active border answering.
- **The grade-verdict UI.** The channel is live end-to-end on the backend and
  round-trips on the identity GET, but has no lens control — a grade judgment
  can still only be recorded via the API. Named deferral, carried forward.
- **Staged retirement** of the legacy path (checklist §2) — only after the
  operator declares the flip good. The legacy path IS the rollback until then.
