# Flag ledger — dark engine flags and the decision each is waiting on

Every flag-gated engine capability that shipped **default-off** is listed here
with the decision that blocks its flip and a **kill-by date**. A dark flag is
not free: it is a dead branch in the reader, a row in the freeze manifest, and
a standing "we'll validate later" IOU. By its kill-by date a flag must be
**flipped live**, **deleted**, or **re-dated with a written reason** — never
silently carried.

Maintenance rules:
- A new default-off engine flag lands with a row here **in the same change**.
- Flips/deletions move the row to *Retired* (keep the evidence trail).
- Live flags (`TRAVERSAL_GATE_ENABLED`, `DESCENT_TAIL_GATE_ENABLED`,
  `SOS_TRIM_ENABLED`, `BOX_BACKEXT_ENABLED`, `TIGHTNESS_ADR_AWARE`,
  `HTF_CONTEXT_ENABLED`, ...) are deliberately NOT here — they are engine
  identity (frozen in `core/freeze/manifest.py`), not pending decisions.

## Dark flags (default-off, decision pending)

| Flag | Built | Blocking decision | Evidence | Kill-by |
|---|---|---|---|---|
| `PIP_MACRO_PHASE_A_ENABLED` | 2026-07-02 (`25b98cb`) | Operator APPROVED the flip 2026-07-04 on the overlay A/B (`tools/phase_a_pip_diff.py`: 24/140 overlays move, 0 score/fire/tier), but **HELD**: making macro the default breaks the phase-ordering invariant (LUV macro AR lands AFTER the box start) + the `test_segment_swings_finds_root_bridge` unit test — resolve whether that's a real overlay defect or an over-strict invariant, then flip | [pip_macro_phase_a.md](pip_macro_phase_a.md); `test_invariants::test_phase_ordering_monotone` | 2026-08-15 |
| `LPS_REQUIRE_PEAK_DOWN` | 2026-06-24 (`dba8005`) | Was gated on a seed-recall measurement before any flip; the census found NO peak-down threshold that separates winners, and the OHI run-up class it targeted is now killed by the live markup gate (`LPS_RESCUE_MAX_ADVANCE_BOX = 0.21`). **Recommendation: delete unless a new census revives it** | `settings.LPS_REQUIRE_PEAK_DOWN` comment; markup-gate validation 2026-06-26 | 2026-08-01 |
| `TA_SCORE_V2` | 2026-07-01 (`d4c90bd`) | Build P0–P6.5 reweight-neutral behind the flag, then STOP at the A/B eyeball (weights untouched); flip is an operator A/B decision | [../specs/ta-score-rework.md](../specs/ta-score-rework.md), [../specs/ta-score-hybrid-design.md](../specs/ta-score-hybrid-design.md) | 2026-08-31 |
| `FUNDAMENTALS_ENABLED` (Lane C) | 2026-06-29 (`b8753a1`) | The scoring/enrichment wire-up wave (fundamentals feeding score/archive) — substrate is built and unit-tested, consumption wave not yet scheduled | `core/fundamentals/` docstrings | 2026-09-30 |
| `RS_LINE_ENABLED` (Lane C) | 2026-06-29 (`b8753a1`) | Same wire-up wave (RS-line new-high chip / score input) | `core/regime/rs_line.py` docstring | 2026-09-30 |
| `SECTOR_RANKING_ENABLED` (Lane C) | 2026-06-29 (`b8753a1`) | Same wire-up wave (sector-RS context for the health board / regime label) | `core/regime/sector_ranking.py` docstring | 2026-09-30 |

## Retired

| Flag | Built | Outcome | Evidence |
|---|---|---|---|
| `PIP_PIVOTS_ENABLED` (+ `PIP_PIVOTS_DIST_MIN`) | 2026-06-25 (`c08e61f`) | **DELETED 2026-07-03** — eyeball-rejected as a wash (fixes some inverted climax→AR overlays, creates others: GBTG/PLSE/CGNX, `d43e7fd`); dead branches removed from `segment_swings` / `read_market_structure`, keys removed from the freeze manifest. `pip.py` itself stays (`macro_bridge_zigzag` refines the same substrate) | [pip_macro_phase_a.md](pip_macro_phase_a.md) §history; byte-parity gates green at deletion |
| `CANDLE_SPREAD_AWARE` | 2026-06-30 (`ed6b82e`) | **FLIPPED LIVE 2026-07-04** — operator A/B eyeball (`tools/candle_ab.py`): 61/128 choppy bases docked (mean −0.39, min −3.0), 0 tier flips, clean bases preserved at grade 1.0; shadow baseline re-captured | `settings.CANDLE_SPREAD_AWARE`; E1 Track B A/B |
| `PUZZLE_SCORE_ENABLED` | 2026-06-30 (`d2db80c`) | **FLIPPED LIVE 2026-07-04** — operator A/B eyeball (`tools/puzzle_ab.py`): 128/128 fires lifted (mean +4.5, max +8.0), 22 tier flips; shadow baseline re-captured. Forward-return validation still due ~2026-07-15+ (a revisit, not a blocker) | `settings.PUZZLE_SCORE_ENABLED`; [engine_pass/](engine_pass/) E2/E3 |
