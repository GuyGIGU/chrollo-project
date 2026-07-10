# Map of the Engine (`core/`)

A plain-English tour of how the screener is organized. No coding knowledge needed —
this is the "where does X live?" cheat sheet.

The engine is built as **two engines and a conductor**, plus a measuring stick:

```
        core/pipeline/   "THE CONDUCTOR"
        runs the show, in order
                 │
        ┌────────┴────────┐
        ▼                 ▼
core/structure/      core/scoring/
"HOW WE SEE          "HOW WE RATE
 THE CHART"           THE SETUP"
 (measurement)        (opinion)

        core/archive/    "THE MEASURING STICK"
        records what happened, so we can learn
```

The golden rule: **structure measures, scoring judges, pipeline coordinates.**
The structure folder reports *facts* and never decides if a setup is good.
The scoring folder turns those facts into points and never looks at a chart itself.

---

## 1. `core/structure/` — the Visual Structure Engine ("how we SEE the chart")

Pure geometry and measurement. Give it price bars, it tells you *what is there* —
with zero opinion about whether it's worth buying. **This is the prime directive:
draw the consolidation accurately and measure its tightness faithfully.**

| File | What it does (in plain terms) |
|------|-------------------------------|
| `consolidation.py` | Public box detector: finds the outer Wyckoff range, then optionally refines into a tighter inner Phase D range. |
| `box_primitives.py` | Shared box toolkit: root anchors, zigzag R/S candidates, boundary respect, R/S touch density, and worked-equilibrium dwell/coverage. |
| `metrics.py` | Measures already-detected bases: bar compression, VCP contractions, rising support, and volume at R/S touches. |
| `pivots.py` | Shared pivot and zigzag helpers used by consolidation and segmentation. |
| `pip.py` | Alternative multi-resolution swing skeleton (Perceptually Important Points): ranks turning points by importance so the same chart can be read coarse (macro trend) to fine (inner structure). Flag-gated (`PIP_MACRO_PHASE_A_ENABLED`, dark); feeds only the Phase-A overlay. |
| `segmentation.py` | The trend/range middle layer: labels swings with ATR displacement, measures swing efficiency, and locates the **root swing** (climax → first big counter-burst) that bridges trend into range. |
| `narrative.py` | The chronological "pair of eyes": reads A → B → (C?) → D left-to-right as one story, each phase validated by a calibrated detector brick. Its `Structure` is the single source of truth consumers read. |
| `bricks.py` | The narrative's building blocks: each phase detector wrapped as a pure `fits_here?` function (root swing, box, spring, LPS, Phase-A overlay resolution). |
| `market_structure.py` | The chart in Highs & Lows: labels the swing skeleton HH/HL/LH/LL and marks mechanical breaks (BOS / reversal). Layer 0 of the event reader. |
| `box_events.py` | The Wyckoff event reader (L2): calibrated SOS / spring / test / LPS / markup pieces + `assemble_box_narrative`, which orders them into a scored, traceable story. |
| `event_map.py` | The Event Map: (1) the mechanical swing layer — ONE whole-frame pivot walk sliced into a pre-box trend view + the (byte-identical) in-box staircase, every swing stamped with when it *became knowable*; (2) the narrative-role layer — the L2 event zones re-emitted as stamped, tri-stated role labels fed the engine's ELECTED spring/LPS (never re-detecting). Measure-only; staged on the fire path behind `EVENT_MAP_ENABLED` (dark); owns the `event_map_*` archive column family. |
| `bin_features.py` | Splits the base into left/right halves (bins) and measures how the right side improves on the left — range, support quality, tight-bar share. |
| `phase_d.py` | Phase-D boundary resolution: where the right side of the base actually starts. |
| `htf.py` | The same trend+box engine on resampled weekly/monthly bars — the higher-timeframe context read. |
| `scope.py` | Chart-region labels: which bars belong to which phase, for display and archiving. |
| `lps.py` | Finds the **Last Point of Support** — the quiet, tight pullback that defines the actionable support test. Classifies it: inside the box, a backtest above the ceiling, or a spring below the floor. |
| `indicators.py` | The math helpers — ATR (volatility), ADX (trend strength), and ADR% (absolute daily range). |

**Want to change how the box or LPS is *detected*?** This folder.

## 2. `core/scoring/` — the Scoring Engine ("how we RATE the setup")

The opinion layer. It takes the measured facts from the Structure Engine and turns
them into a number and a letter grade (S / A / B / C / D).

| File | What it does |
|------|--------------|
| `scoring.py` | `score_setup` adds up 14 ingredients (box tightness, touches, volume dry-up, contraction footprint, ADR%, 52-week-high proximity, market breadth, ...) into a total. `calculate_tier` maps that total to a letter. |
| `taxonomy.py` | The single registry of every sub-score term (its key, archive column, point cap, layer, flag) — the one place consumers derive their lists from instead of re-declaring literals. |

**Want to change how much a factor is *worth*?** Edit the numbers in `config/settings.py`
(the `SCORE_*` and `TIER_*` constants) — never the measurement code.

## 3. `core/pipeline/` — the Conductor ("runs the screen")

The only part that knows the *order of operations*. For each stock it: filters the
junk, asks the Structure Engine where the box/LPS is, asks the Scoring Engine how good
it is, and assembles the ranked list.

| File | What it does |
|------|--------------|
| `data.py` | The stable public doorway: exports `get_tickers`, `fetch_data`, `get_market_context`, and `get_provider`. |
| `tickers.py` | Loads and refreshes the cached common-stock universe. |
| `providers.py` | Market-data source abstraction. The screener fetches its panel through `get_provider().fetch(...)`, not a vendor directly, so a bulk-EOD source can be slotted in behind one contract. Today only `yahoo` (wraps `downloads.fetch_data`). |
| `downloads.py` | The Yahoo provider's implementation: yfinance downloads, retry/recovery, split-drift checks, and the parquet cache. |
| `ticker_admission.py` | Ticker admission ledger: rejects obvious non-common instruments from directory facts, remembers too-young / empty Yahoo-history symbols, and skips them until a recheck window. |
| `fetch_health.py` | Dead-ticker quarantine (skip symbols that keep returning nothing, re-probed after a cooldown) + per-run fetch-health telemetry written to `cache_meta.json`. Cuts wasted requests/429s on the delisted tail. |
| `scan_metrics.py` | Per-scan timing telemetry: records universe load, market-data fetch, frame prep, market context, evaluation, and result assembly into `cache_meta.json` + `output/scan_metrics.jsonl`. |
| `market_context.py` | Computes the SPY 6-month return and universe breadth broadcast used by scoring. |
| `cache.py` | Small filesystem, metadata, and market-clock helpers used by the data modules. |
| `evaluation.py` | Per-ticker evaluation: baseline filter, structure pass, LPS check, scoring, and result row assembly. |
| `screener.py` | `run_screener`: loads data, prepares ticker frames, broadcasts market context, runs workers, and ranks results. |

## 4. `core/archive/` — the Measuring Stick ("learn from outcomes")

**Not part of the live screen.** It records every setup the engine finds, fills in what
actually happened afterward, and lets us study which setups won. This is how we earn
the right to re-tune the scoring.

| File | Run it with | What it does |
|------|-------------|--------------|
| `writer.py` | (automatic) | Saves each scan's results into the archive database. |
| `seed.py` | `python -m core.archive.seed` | Bootstraps the archive with known historical setups. |
| `forward_returns.py` | `python -m core.archive.forward_returns` | Fills in real outcomes once setups are old enough. |
| `analyze.py` | `python -m core.archive.analyze` | The report card: winner fingerprint, what predicted returns, bias warnings. |
| `purge.py` | `python -m core.archive.purge` | Cleans uncurated rows out of the archive. |

---

## The one-line flow

`python run_screener.py` → **pipeline** loads **data**, and for each stock asks
**structure** "what's here?" then **scoring** "how good?", ranks them, shows the
dashboard, and (if enabled) hands the results to **archive** to remember.
