# Chrollo Engine α — the frozen chart-reading base

**Released 2026-07-06.** `engine_config_version` = `efa9e0ff7b693461dd568ede639793dde5629503f0e7bd9a04e841bf7872154f` (167 manifest keys). *(Rotated from `7c36b006…` by the second-pass amendment below — the reading surface is byte-identical; only the manifest allow-list grew.)*

Engine α is the **first named release of Chrollo's full chart-*reading* algorithm** — the geometry-and-structure layer that turns a price series into an explainable Wyckoff/VCP read. It is meant to be the **frozen base** every future engine change builds on.

The title is scoped honestly:

- **α = the chart-reading algorithm is complete and frozen.** The reading model is authoritative in [`strategy_v2.md`](strategy_v2.md), its config is hashed, and its output is regression-guarded byte-for-byte.
- **β = the edge is calibrated.** Scoring reweighting, cross-regime forward-return validation, and the advisory/enrichment lanes are the *next* milestone. The engine's standalone predictive edge is measured-but-thin (one bull regime); proving it across regimes is **calendar-gated** (needs a non-bull stretch + ~60d maturation), so it does not gate this α.

α does **not** claim a proven edge. It claims a complete, frozen, documented reader.

## What's in α

The frozen reading surface (all measure-first; **geometry is the only veto**, richer reads are graded confidence):

- **Trend / Phase-A** — climax→AR root swing via `resolve_phase_a` with the BC-downswing invariant; the flag-gated first-reaction AR tightening is present but **OFF** (see deferred).
- **Phase-B equilibrium** — worked-equilibrium box election (touch + zigzag + occupancy), R/S rail anchoring, boundary-respect veto, shared-rail back-extension start pinning, inner-box refinement.
- **Limb-traversal** — rail-to-rail count/density floor + graded traversal-quality.
- **Filters** — descent-tail gate, SOS breakout trim, crash/extension filters.
- **Phase-C spring** — bounded-excursion detector (penetration → reclaim → significance → hold).
- **LPS / Phase-D** — LPS detection + rising-support-shelf rescue + the markup gate (`LPS_RESCUE_MAX_ADVANCE_BOX = 0.21`, live) + V-tip Phase-D boundary.
- **L2 event reader** — E1 rail events / E2 `assemble_box_narrative` chronology+spine / E3 puzzle completeness, consumed as the **live, bonus-only** puzzle-quality score term (`PUZZLE_SCORE_ENABLED`). Never a gate.
- **Live scoring reads** — candle-spread readability multiplier, ADR-aware box tightness, PIP macro Phase-A read (all flipped live 2026-07-04).
- **HTF context** — measure-only (`HTF_CONTEXT_ENABLED`); deliberately **not** scored.
- **Price regime** — as-traded (`DATA_DIVIDEND_ADJUSTED = False`) as the single reading substrate.
- **Freeze battery** — `shadow_diff` canonical-field guard, hermetic offline seed-recall, negative-corpus precision, provider-parity, and the manifest-completeness + flag-ledger provenance invariants, all wired as hard CI + regression tests.

## Deferred to β

| Item | Why it waits |
|---|---|
| **Edge calibration** — scoring reweight + cross-regime forward returns | Calendar-gated on a non-bull regime maturing; can't gate α |
| **`AR_FIRST_REACTION_ENABLED` live flip** | Byte-identical on scoring/tier/canonical, but a flip shifts the archived `bin_a_*` columns (`ar_bar` → `measure_bins` → `analyze`) with no covering gate — needs a `bin_a_*` guard / `engine_config_version` archive partition first. Rides into α as measure-only substrate, flag off. |
| **`TA_SCORE_V2`** reader build | Reserved manifest name only in α; a β build (P0–P6.5 + operator A/B) |
| **Lane-C wire-up** (`FUNDAMENTALS_ENABLED` / `RS_LINE_ENABLED` / `SECTOR_RANKING_ENABLED`) | Advisory substrate built + provenance-tracked; the score/archive consumption wave is β |
| **Shelf-R secondary anchor** | Box R can pin to a post-reaction bounce high vs the tight shelf (TOL 154 vs ~139); parked lever, its own track |

## Council α-audit (2026-07-06)

An 8-seat adversarial release audit ([`engine-alpha-release-audit` workflow](../.claude), 9 agents) returned **go-with-fixes**: the frozen reading surface was sound and byte-identical flag-off across every seat, the `structure measures / scoring judges` invariant was clean, and all findings were doc/ledger drift or provenance hardening — **no reading-behavior defects**. Every finding was resolved before this freeze:

- Documented the previously-silent live L2 puzzle reader; corrected the scoring table (15 components, candle-spread multiplier, max ≈209); fixed the LPS hold-tolerance doc (0.95); reworded the AR "byte-identical" claim to exclude the archive seam.
- Deleted the `LPS_REQUIRE_PEAK_DOWN` dark branch its own ledger recommended removing; blessed + documented the live `LPS_RESCUE_MAX_ADVANCE_BOX = 0.21` markup gate (a stale "un-adopted" comment was hiding a committed decision, `232afd0`).
- Confirmed the frozen base carries no orphaned `_last_opposite_pivot_before` helper — an earlier working-tree draft of the AR retarget used it, but the shipped full-leg API (`elected_trend_leg_base`) superseded it before the freeze, and `tools/full_package_render.py` imports only the shipped API.
- Added two provenance guards — a machine check tying the flag-ledger to the actual default-off flags, and an extended manifest-completeness scan covering the `_flag()` indirection seam. The extension **caught a real gap**: four Lane-C flags were escaping provenance; they are now in the manifest.

## Dark flags carried into α (each with a decision + kill-by)

| Flag | Status | Kill-by |
|---|---|---|
| `AR_FIRST_REACTION_ENABLED` | measure-only substrate, off; β-flip needs the archive-seam guard | 2026-08-15 |
| `TA_SCORE_V2` | reserved name, no live reader; β build | 2026-08-31 |
| `FUNDAMENTALS_ENABLED` / `RS_LINE_ENABLED` / `SECTOR_RANKING_ENABLED` | Lane-C advisory, off; β wire-up | 2026-09-30 |

See [`flag_ledger.md`](flag_ledger.md) for the full dark + retired ledger.

## Second-pass audit + amendment (2026-07-06)

Before tagging, the frozen commit was re-audited by an independent 9-seat adversarial workflow (Fable + Opus seats: AR math, overlay contract, LPS deletion, the two new provenance guards, docs drift, a live gate re-run, test-mutation probing, and a whole-diff fresh-eyes read, each finding refute-by-default verified). The verdict: **no blockers, no reading-behavior defects** — every gate reproduced byte-for-byte and the reading surface held under every seat. It did surface two real (latent) holes in the freeze's own new provenance guards plus doc drift, all fixed in this amendment:

- **Provenance guard — dead cap/flag regex.** The manifest-completeness scan's `cap_setting=/present_when=` regex matched zero lines (the scoring `TermSpec` registry is built positionally), so that arm was inert. Replaced with a runtime introspection of the taxonomy `REGISTRY` (`cap_setting` + `present_when` per term) — robust to construction style, and it now covers the registry-only read path (`TermSpec.cap()` / `.is_emitted()`).
- **Provenance guard — Lane-C tuning knobs escaping the scan.** Four numeric advisory knobs (`RS_LINE_NEW_HIGH_LOOKBACK`, `SECTOR_RANKING_LOOKBACKS`, `FUNDAMENTALS_FILING_LAG_DAYS`, `FUNDAMENTALS_EARNINGS_HISTORY_LIMIT`) were read one import-hop outside the scanned modules and sat in neither the manifest nor the ops exclusions — inconsistent with the pre-registration of their sibling `RS_RATING_LOOKBACK`. Added `core.regime.rs_line` / `core.regime.sector_ranking` / `core.fundamentals.metrics` to the scan and the four knobs to the manifest (`SECTOR_RANKING_ETFS`, a symbol set like `INDEX_SYMBOLS`, is ops-excluded). **This is the hash rotation** (163 → 167 keys); the flags stay dark, so live output is byte-identical.
- **Doc drift.** `strategy_v2.md`'s scoring/LPS tables now document the live ADR-aware box-tightness formula, the `LPS_RESCUE_MAX_ADVANCE_BOX = 0.21` markup gate, the S-tier width cap (and the real `calculate_tier()` name), the base-age dead-space dock, and the traversal overshoot exemption; three stale "default-off" comments were corrected; and the `QUALITY_DOCTRINE` flag inventory carries a dated resolution note.
- **Test coverage.** Added a test pinning the AR `end_bar` tighten-only clamp (previously every fixture set `end_bar == n-1`, so a regression dropping the clamp passed green).

## Verify the freeze

```
python -m pytest -q                          # 790 tests (reading + provenance guards)
python -m tools.shadow_diff --check          # canonical output byte-identical
python -m core.archive.seed_recall --hermetic-check   # recall guard (offline)
python -m tools.settings_reference --check   # config hash == doc block
```

At this freeze (post-amendment): **790 passed**, shadow **no canonical drift**, docs-sync green, `engine_config_version = efa9e0ff…`.
