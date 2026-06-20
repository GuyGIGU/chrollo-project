# Seed-Recall Misses Findings

Date: 2026-06-20

## Summary

Fresh recheck of the 8 names in `docs/refactor_seed_recall_misses_codex.md`
originally found that **FOSL could already fire again** in the smaller targeted
download, while GRDN/SILC were close LPS misses and the other names remained
structural collateral.

After Guy's chart review, three LPS variants were accepted as real setups and
implemented without changing global thresholds:

- a compact rising support shelf whose true support low occurs early, then
  tightens upward;
- a long shallow BUEC / resistance shelf that holds just above old R.
- a clean anchor-high to final-valley downswing whose pullback spans more of
  the box, but is one readable swing rather than broad multi-direction chop.

Targeted recall on the original 8 now recovers **GRDN**, **SILC**, and
**SYRE** while leaving **TERN** out. The remaining unrecovered names from this
set are NKTR, PGC, PKE, and TERN. FOSL remains data-sensitive: it fired in the
smaller targeted download but appeared as a miss in the all-seed fresh run.

## Method

- Reproduced the listed cases with `core.archive.seed.fired_seeds_fresh(...)`.
- Walked the same seed scan window used by `core.archive.seed`: 10 calendar days
  back through 3 calendar days forward.
- For the best failing as-of date, replayed the chronological `read_structure`
  spine and the root-walk/box diagnostics used by `tools.structure_case_audit`,
  but on the fresh historical slice.
- For LPS misses, enumerated the detector's candidate windows and recorded the
  first binding reject plus margin.

## Per-Ticker Findings

| Ticker | Seed date | Fresh status | Best as-of | Rejection point | Binding gate and margin | Classification |
|---|---:|---|---:|---|---|---|
| FOSL | 2026-02-18 | Data-sensitive | 2026-02-17 | none in targeted run | Targeted run fired S-tier LPS, score 136.5; full all-seed download still listed it as a miss. | not changed here |
| GRDN | 2026-02-02 | Recovered | 2026-01-28 | Phase D / LPS | Recovered inside the parent box. Current best signal elects LPS 2026-01-22 through 2026-01-28; final valley 2026-01-28; pullback profile 0.758. | recovered |
| NKTR | 2026-04-13 | Miss | 2026-04-13 | Phase B / box | No worked box before LPS is evaluated. The visual 2026-04-01 -> 2026-04-07 LPS sits above a box the reader currently anchors too low; closest quality candidates fail lower dwell after choosing S near 64.5 instead of the higher visual shelf. | needs box-reader work |
| PGC | 2026-03-30 | Miss | 2026-03-30 | Phase B / box/traversal | No worked box before LPS is evaluated. The visual 2026-03-25 -> 2026-03-27 LPS sits on a high/tight shelf, but candidates fail dwell/traversal as mid-box chop rather than a resolved high shelf. | needs box-reader work |
| PKE | 2026-02-24 | Miss | 2026-02-24 | Phase D / LPS | Valid box from 2025-10-10. Candidate lows are above the valid LPS zone; nearest zone miss is +1.3559 above R ceiling. Nearest terminal-low miss is +0.2730. | acceptable |
| SILC | 2026-04-13 | Recovered | 2026-04-10 | Phase D / LPS | Recovered as long shallow BUEC shelf above R. Elected LPS window 2026-04-06 through 2026-04-10; zone OVERSHOOT_R; pullback profile 1.027. | recovered |
| SYRE | 2026-02-12 | Recovered | 2026-02-12 | Phase D / LPS | Recovered as clean anchor-high to final-valley downswing. Elected LPS window 2026-02-09 through 2026-02-11; the wide window range is accepted because highs and lows descend cleanly into the valley. | recovered |
| TERN | 2026-02-23 | Miss | 2026-02-23 | Phase D / actionability | Valid box from 2026-01-12. Older Feb 13 LPS candidates pass geometry but are no longer actionable on Feb 23: close 40.85 vs trigger 38.80. On Feb 13 itself, baseline fails SMA50 by -0.2472. Current pullback is shallow: overshoot-R profile 0.4393 vs min 1.25. | acceptable |

## Proposed Changes

Implemented in `core.structure.lps`:

- preserve the terminal-low guard for ordinary reactions, but allow a compact
  multi-bar inside-box rising support shelf to elect the window low as the LPS
  low;
- preserve the strict overshoot-R pullback floor for ordinary breakout retests,
  but allow a longer shallow shelf above R when price is still sitting low on R
  and the pullback is clearly below the normal overshoot profile floor.
- preserve the broad-window rejection for ordinary chop, but allow a fully clean
  anchor-high to final-valley downswing to span more of a tight box.

## Guard Status

Guard results after the GRDN/SILC/SYRE recovery change:

- Targeted spot checks: GRDN fires with LPS 2026-01-22 -> 2026-01-28,
  SILC fires with LPS 2026-04-06 -> 2026-04-10, and SYRE fires with LPS
  2026-02-09 -> 2026-02-11. NKTR and PGC still miss before the LPS layer
  because no valid box is elected.
- `python -m tools.shadow_diff --check`: pass, no canonical drift across 31
  frozen live outputs.
- `python -m core.archive.seed_recall --fresh`: completed after the GRDN/SILC
  change; GRDN and SILC no longer appeared in the fresh miss list. Overall
  fresh recall printed 28/55 active seeds re-detected. Not rerun after the SYRE
  targeted clean-downswing change.
- `python -m pytest tests/ -q`: 213 passed.
- `python -m pytest tests/test_core_logic.py -q -k "lps"`: 29 passed.
