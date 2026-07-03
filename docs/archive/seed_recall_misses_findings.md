# Seed-Recall Misses Findings

Date: 2026-06-20

## Summary

Locked all-seed fresh recall after the GRDN/SILC/SYRE recovery change:
**29/55 measured seeds re-detected = 52.7% fresh recall**. The fresh hit tiers
were `{'A': 6, 'S': 23}`. The 26 fresh misses were WMT 2025-09-11, BWA
2026-01-26, IBP 2026-02-03, GXO 2026-02-11, NOK 2026-02-17, FOSL
2026-02-18, SHEL 2026-02-18, TERN 2026-02-23, GASS 2026-02-24, PKE
2026-02-24, VLO 2026-02-26, VIST 2026-03-05, SNDX 2026-03-06, PUMP
2026-03-11, NE 2026-03-13, RGR 2026-03-13, NTCT 2026-03-16, XWIN
2026-03-19, FOSL 2026-03-30, PGC 2026-03-30, RRBI 2026-03-31, DNTH
2026-04-08, LPTH 2026-04-08, SKYT 2026-04-08, CAPR 2026-04-13, and
NKTR 2026-04-13.

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

## FOSL Data-Sensitivity Diagnostic

X4 diagnosis: FOSL is a **lookback-window / root-walk cap sensitivity**, not a
split-adjustment issue and not `fired_seeds_fresh` nondeterminism.

- Targeted single-ticker range (`2024-01-20` -> `2026-06-18`) fires FOSL
  2026-02-18 as an S-tier LPS; best eval date is 2026-02-17, score 136.5,
  LPS 2026-02-13 -> 2026-02-17.
- Full single-ticker range (`2023-08-13` -> `2026-08-12`) misses, matching the
  all-seed fresh run.
- Full single-ticker FOSL data and FOSL extracted from the 52-ticker all-seed
  multi-download are identical over 714 common rows: max absolute OHLCV diff is
  0.0 for Open/High/Low/Close/Volume, with 0 differing rows.
- The failing stage is `read_structure`, before LPS. With the narrow frame,
  `read_structure` reaches the valid December 2025 root candidates and fires.
  With the full frame, the older 2023/early-2024 history adds enough stale root
  candidates that the `_MAX_ANCHORS = 64` safety cap is exhausted first.
  Narrow frame: 58 roots total, good LPS roots at indices 55-57. Full frame:
  74 roots total, good LPS roots at indices 71-73, beyond the cap.

No detector loosening was applied. A future fix, if desired, should make the
root-walk safety bound less sensitive to irrelevant old history, not widen
box/LPS gates.

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
- `python -m core.archive.seed_recall --fresh`: completed after the
  GRDN/SILC/SYRE recovery change; fresh recall printed 29/55 measured seeds
  re-detected, 52.7% recall, hit tiers `{'A': 6, 'S': 23}`, and 26 misses.
- `python -m pytest tests/ -q`: 213 passed.
- `python -m pytest tests/test_core_logic.py -q -k "lps"`: 29 passed.

## Box-Layer Deferral — NKTR / PGC (2026-06-20, Guy's call: PAUSE box fallbacks)

The two remaining misses are **box-layer** (no valid Phase-B box elected before the
LPS). Diagnosed with the new Pass-0 tool `python -m tools.structure_case_audit
NKTR --as-of 2026-04-13` (per-root strict candidate + first binding gate + margin):

- **NKTR** — strict enumeration anchors **S at the deep shakeout lows (62.5/64.5)**,
  so `lower_dwell` fails (0.074 < 0.15): price actually dwells in a **69–77 coil**
  while the 62–64 dips are reclaimed springs, plus a late **SOS breakout to 78+**
  (04-01). A valid box DOES exist — `R=75.21 / S=68.90` over 02-23..03-30 validates
  cleanly — but it is **region-defined, not pivot-pair-defined**: both rails sit
  *inside* the coil and the box must start at the coil's left edge with the breakout
  SOS-trimmed. Adjacent AND non-adjacent pivot-pair re-anchoring (cand_start at the
  pivot OR at 0, with SOS-trim) were tested through the real `_build_candidate` +
  traversal gate: **0 candidates validate**. Capturing it needs **region-based coil
  framing** (define the worked region → set its rails → treat deep dips as springs).
- **PGC** — a *tight* ~0.07 coil sits **mid-box** (`mid_dwell 0.5–0.6`,
  `upper/lower_dwell` ~0.1, `traversal nF=0`, `s_touches=1`); NO recovered-support
  signal. Needs a dedicated tight-coil validator that does not demand two-sided rail
  work — a different relaxation from NKTR.

**Decision: PAUSED.** Both treated as known-hard misses alongside PKE/TERN. Any
fallback strong enough to recover NKTR/PGC will also recover **junk coil-with-spikes
/ tight-mid-coil look-alikes universe-wide**, so it is too precision-dangerous to
ship without a measure-first build behind a flag + a **full-universe new-fires
eyeball** (the 31-ticker shadow fixture won't catch new fallback fires) + archive
outcome evidence. Revisit with that evidence later. The diagnostic tool +
`--as-of DATE` are in place for the revisit.
