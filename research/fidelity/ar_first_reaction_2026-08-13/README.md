# First-reaction AR anchor — the eyeball set, 2026-08-13

`AR_FIRST_REACTION_ENABLED` (dark). Re-anchors the DRAWN Phase-A automatic
reaction to the low of the first *continuous* reaction after the terminal swing,
instead of the raw fallback. **Overlay-only and tighten-only**: the climax never
moves, and the AR only ever pulls earlier. Nothing about scoring, rails, tier or
election changes — `CANONICAL_FIELDS` excludes the AR bars, so a flip is
byte-identical on every scored output.

## Measured 2026-08-13 on the live cache

`python -m tools.ar_first_reaction_diff --scan --no-render` (raw output:
[`scan_2026-08-13.txt`](scan_2026-08-13.txt))

| | |
|---|---|
| tickers scanned | 5,511 |
| have an overlay (fire) | 291 |
| **overlays that re-anchor** | **100 of 291** |
| OFF span (climax→AR), median | **39 bars** — 24 of the 100 at ≥58 |
| ON span, median | **7.5 bars** — 50 of the 100 collapse to ≤7 |
| tighten, median / max | **19 / 59 bars** |

**This is much bigger than the ledger's recorded 19/140 (median 8, max 53)**,
measured 2026-07-05 — before the Engine-α extraction and everything since. On a
third of live reads the drawn climax→AR stripe currently smears across ~39 bars
where the actual reaction is ~7.

## What to look at

The twelve renders are the largest tighteners, drawn by
`tools.full_package_render` — the WHOLE structural read on one frame, because the
AR overlay is illegible in isolation (you cannot tell which consolidation and
root swing the engine elected). On each chart:

- **hollow purple circle** = the raw AR (flag OFF, today's drawing)
- **filled green dot** = the first-reaction AR (flag ON, the proposal)
- the text panel's `AUTOMATIC REACTION` block gives both spans and `dAR`

The question for each: **is the green dot where the reaction off that climax
actually ended?** The retarget was already tuned once against the operator's own
dated BC/AR marks (PH/TOL/AVNT/AAP/AGCO/TFX, 2026-07-05) — exact on TOL/AVNT,
and it surgically fixes the AAP-class second-leg overshoot.

## Status

The archive-seam blocker this flag carried — *partition `bin_a_*` before a flip
pools two AR-mode populations into one fingerprint* — was **cleared 2026-08-13**
in `core/archive/analyze.py` (`PHASE_A_ANCHOR_FEATURES`, gate
`tests/test_analyze_anchor_seam.py`). What remains is the operator's ruling.

## Re-run

```
python -m tools.ar_first_reaction_diff --scan --no-render
python -m tools.full_package_render EC BCPC CATO NRIM SFL CNI HTH LMNR OXY AMH INVH LZB --out DIR
```
