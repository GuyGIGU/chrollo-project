# Scoring demotion — rs_bonus + uptrend_bonus to measure-only (2026-07-25)

**Operator-authorized 2026-07-25** ("we can also implement your ideas for
Change and Remove"). Weights only, per the standing rule — measurement code
untouched; both signals stay archived raw.

## What changed

| Knob | Was | Now | Evidence |
|---|---|---|---|
| `SCORE_RS_BONUS` | 15 | **0** | harmful on both edge reads (corr −0.22 with forward returns at n=1977 — the worst term in the book; `docs/edge_read_2026-07-22.md`) |
| `SCORE_UPTREND_BONUS` | 15 | **0** | harmful on both edge reads (corr −0.19 at n=1977) |

Raw signals preserved for any regime-spanning revisit: `excess_return_6m`
(already archived) and **`yearly_return` (new model-only archive column**,
stamped from the universe baseline's own computation — no re-derivation).
Manifest hash rotates `aaf853bd… → ab5bf340…` (both knobs are
manifest-listed): an archive bin seam, one cause. Shadow baseline
deliberately re-captured in the same change (the guard's job is to make this
drift loud, and it did).

## Blast radius — archive-wide tier migration (7,147 scored rows, old thresholds)

| old → new | rows |
|---|---|
| S → S | 2,064 |
| **S → A** | **1,375** |
| **S → B** | 181 |
| A → A | 1,847 |
| **A → B** | 530 |
| A → C | 7 |
| B → B | 1,057 |
| B → C | 23 |
| C → C | 63 |

Moved: 2,116 / 7,147 (30%). Points removed: median 5, p90 30 (the full
double-bonus load — exactly the momentum-heavy names the edge reads said
were being over-ranked).

**S-tier population: 51% of the book → 29%.** The tier doc's stated intent
is "S ≈ the top quartile"; the demotion RESTORES that without touching a
tier threshold. Whether to rebase `TIER_*` afterwards is a separate,
operator-owned calibration question (the "EGBN feels like an easy S"
disagreement is logged as its first data point).

## Shadow-guard drift (32 fixture tickers, before re-capture)

Scores drop up to 30 points; VLO falls S → B; the ranking reorders
meaningfully — SWK/TNC/HOG/LUV rise (structure-strong, momentum-light),
EC/VLO/PLPC fall (rank was carried by the bonuses). Full listing:
session evidence `score_demotion_shadow_drift.txt`.

## What did NOT change

Fire/no-fire decisions (score never gates firing): the Guided List ratchet
(26/33), the negative corpus (18/18), and every election are untouched.
The marks baseline's per-hit `tier` fields are informational and will
refresh at the next deliberate reseal.

## Operator

Run `update_dashboard.bat` after merging to load the new weights; expect
tonight's scan to show fewer S tiers and a reshuffled top of the board —
that reshuffle is the point (the removed points ranked AGAINST forward
returns).
