# Map of the Engine (`engine_alpha/` + `core/`)

A plain-English tour of how the screener is organized. No coding knowledge needed —
this is the "where does X live?" cheat sheet.

The engine is built as **two engines and a conductor**, plus a measuring stick. The
reading half (structure + scoring + per-ticker evaluation) was extracted from `core/`
into the frozen **`engine_alpha/`** package in the 2026-07-18/20 engine-α freeze; the
conductor and the archive stay in `core/`:

```
        core/pipeline/   "THE CONDUCTOR"
        runs the show, in order
                 │
        ┌────────┴────────┐
        ▼                 ▼
engine_alpha/        engine_alpha/
structure/           scoring/
"HOW WE SEE          "HOW WE RATE
 THE CHART"           THE SETUP"
 (measurement)        (opinion)

        core/archive/    "THE MEASURING STICK"
        records what happened, so we can learn
```

The golden rule: **structure measures, scoring judges, pipeline coordinates.**
The structure folder reports *facts* and never decides if a setup is good.
The scoring folder turns those facts into points and never looks at a chart itself.

This map covers `engine_alpha/`, `core/pipeline/` and `core/archive/`. For `core/backtest/`,
`core/regime/`, `core/fundamentals/`, the backend, frontend, tests and tools, see
[`docs/architecture.md`](../docs/architecture.md).

---

## 1. `engine_alpha/structure/` — the Visual Structure Engine ("how we SEE the chart")

Pure geometry and measurement. Give it price bars, it tells you *what is there* —
with zero opinion about whether it's worth buying. **This is the prime directive:
draw the consolidation accurately and measure its tightness faithfully.**

The folder is split by what each part measures. Rows below carry the subfolder.

| Subfolder | Its job |
|-----------|---------|
| `box/` | The box election: which R/S range is the real one, the gates it must pass, the nested inner range, and the election's diagnostics. |
| `phases/` | Phase boundaries, the trend/range split, and measurements over the named phase regions. |
| `lps/` | The Last Point of Support. |
| `events/` | Chart events (swings, SOS, spring, test, LPS, breakout or shakeout) and the one vocabulary that names them. |
| `narrative/` | The left-to-right reader and the detector bricks it calls. |
| `metrics/` | Shared pivots, indicators, and measurements of a base already found. |
| `context/` | Context around a reading: higher timeframe, campaign, chart regions, the Power-Play species. |

`lps/`, `narrative/` and `metrics/` re-export their main functions from the folder itself
(`from engine_alpha.structure.lps import detect_lps`); the other folders are imported by file.

| File | What it does (in plain terms) |
|------|-------------------------------|
| `box/consolidation.py` | Public box detector: finds the outer Wyckoff range, then optionally refines into a tighter inner Phase D range. |
| `box/box_primitives.py` | Root anchors + the box ELECTION: zigzag R/S candidate collection/scoring, pool selection, the break-above-R-then-rest rescue, and the shared-rail back-extension. Judges live in `box_gates.py`. |
| `box/box_gates.py` | Gate application (split from `box_primitives.py` 2026-07-18): boundary respect, the SOS worked-window trim, close-residence dwell/coverage, worked-equilibrium occupancy, and the traversal floor — the validity judges every candidate pair must pass. |
| `box/box_trace.py` | Trace plumbing for the box election cascade (split from `box_primitives.py` 2026-07-18): the two helpers every gate/election verdict narrates through; no-op when no trace is requested. |
| `box/inner_box.py` | The inner-box family (split from `box_primitives.py` 2026-07-18): the Phase-D nested range one scale down — inner climax/root-swing detection, inner-stage zigzag, and `select_inner_box`, the one selection rule shared by the live reader and diagnostics. |
| `box/rail_qualification.py` | Deep-excursion (terminal-shakeout) event qualification for the pair election (formerly `band_rails.py`): every band-leaving excursion must reclaim/fail back and HOLD, else the pair disqualifies. Last-resort pool, consulted only when strict + rescued pools are empty (`BAND_RAILS_ENABLED`, live since 2026-07-16). |
| `box/near_miss.py` | The near-miss lane's inline recorder: at the outer Phase-B consultation it records the raw-numbers tuple of every gate refusal (live since 2026-07-27, `NEAR_MISS_LANE_ENABLED`). Measure-only — a near-miss never scores, fires, or enters the picks. |
| `box/gate_margins.py` | Per-leg gate margins in native quanta (bars, touches, thirds...): a SIGNED pass/deficit margin for every `box_gates.GATE_LEGS` leg, plus the post-hoc full-vector completion. Measure-only; consumed by the near-miss lane and its census, never by the live path. |
| `box/trace_export.py` | Election-trace export (dark, `ELECTION_TRACE_EXPORT_ENABLED`): summarizes the walk's own same-run narration into one compact, date-anchored story; the raw trace never leaves the engine, and operator-facing sentences render from the structured gate-leg records, never internal prose. |
| `phases/phase_a.py` | The macro Phase-A read (formerly `pip.py`): a multi-resolution swing skeleton (Perceptually Important Points) that ranks turning points by importance so the climax→AR bridge can be read coarse-to-fine. Feeds only the Phase-A overlay (unconditional since the 2026-07-18 fold, overlay-only; formerly flag `PIP_MACRO_PHASE_A_ENABLED`). |
| `phases/segmentation.py` | The trend/range middle layer: labels swings with ATR displacement, measures swing efficiency, and locates the **root swing** (climax → first big counter-burst) that bridges trend into range. |
| `phases/phase_features.py` | Measures the named phase regions of a detected base (`measure_phases`): Phase A/B/D windows, the Phase-C spring candidate, LPS position, and the Last-Supper stretch — pure measurement, archived as the `bin_*` column family. |
| `phases/phase_d.py` | Phase-D boundary resolution: where the right side of the base actually starts. |
| `lps/detection.py` | Finds the **Last Point of Support** — the quiet, tight pullback that defines the actionable support test. Classifies it: inside the box, a backtest above the ceiling, or a spring below the floor. |
| `events/market_structure.py` | The chart in Highs & Lows: labels the swing skeleton HH/HL/LH/LL and marks mechanical breaks (BOS / reversal). Layer 0 of the event reader. |
| `events/box_events.py` | The Wyckoff event reader (L2): calibrated SOS / spring / test / LPS / markup pieces + `assemble_box_narrative`, which orders them into a scored, traceable story. |
| `events/event_map.py` | The Event Map: (1) the mechanical swing layer — ONE whole-frame pivot walk sliced into a pre-box trend view + the (byte-identical) in-box staircase, every swing stamped with when it *became knowable*; (2) the narrative-role layer — the L2 event zones re-emitted as stamped, tri-stated role labels fed the engine's ELECTED spring/LPS (never re-detecting). Measure-only; on the fire path and live (`EVENT_MAP_ENABLED`); owns the `event_map_*` archive column family. |
| `events/event_vocabulary.py` | The ONE event vocabulary: folds what the three rail readers say (the typed waves, the role labels, the rail visits) into one chronological stream in one set of words. It adds names, never facts, and never touches a price bar. |
| `events/displacement.py` | How a structure resolves: a close beyond the ceiling (breakout) or a violent break under the floor (shakeout), measured by the one ruled breakout-wall arithmetic that the Power-Play lane and the story chains share. |
| `narrative/reader.py` | The chronological "pair of eyes": reads A → B → (C?) → D left-to-right as one story, each phase validated by a calibrated detector brick. Its `Structure` is the single source of truth consumers read. |
| `narrative/bricks.py` | The narrative's building blocks: each phase detector wrapped as a pure `fits_here?` function (root swing, box, spring, LPS, Phase-A overlay resolution). |
| `narrative/chain.py` | The story-chain coordinator: reads a second structure after a resolved one (a story with a sequel) through the same reader, with the first one frozen. Not wired into the scan yet; only its tests call it. |
| `metrics/base.py` | Measures already-detected bases: bar compression, VCP contractions, rising support, and volume at R/S touches. |
| `metrics/pivots.py` | Shared pivot and zigzag helpers used by consolidation and segmentation. |
| `metrics/indicators.py` | The math helpers — ATR (volatility), ADX (trend strength), and ADR% (absolute daily range). |
| `context/htf.py` | The same trend+box engine on resampled weekly/monthly bars — the higher-timeframe context read. |
| `context/scope.py` | Chart-region labels: which bars belong to which phase, for display and archiving. |
| `context/strategy_read.py` | The strategy read (dark, `STRATEGY_READ_ENABLED`): two campaign-context measures per fire — how deep the correction cut below the resolved climax, and whether the base floor held the automatic reaction's low. Archived raw, measure-first; never gates, never scores. |
| `context/power_play.py` | The Power-Play species archive family: the family's declaration, its one writer-facing extraction, the species lane's fields builder, and the shared episode mechanics. Never gates, never scores; the lane orchestration itself lives with the composed twin in `engine_alpha/evaluation.py`. |

**Want to change how the box or LPS is *detected*?** This folder.

## 2. `engine_alpha/scoring/` — the Scoring Engine ("how we RATE the setup")

The opinion layer. It takes the measured facts from the Structure Engine and turns
them into a number and a letter grade (S / A / B / C / D).

| File | What it does |
|------|--------------|
| `scoring.py` | `score_setup` measures the ingredients (box tightness, touches, volume dry-up, contraction footprint, ADR%, 52-week-high proximity, market breadth, ...) as sub-scores. `compose_ta_grade` sums them into the one Technical Analysis grade (0–100, shown as story chapters), and `calculate_structure_tier` turns that grade into the letter (a wide base is never S). |
| `taxonomy.py` | The single registry of every sub-score term (its key, archive column, point cap, layer, flag) — the one place consumers derive their lists from instead of re-declaring literals. |
| `tags.py` | Decides every chip (VCP Coil, No Supply, ...) once, engine-side, from the registry in `taxonomy.py`. The dashboard shows the verdict and never re-decides it. |

**Want to change how much a factor is *worth*?** Edit the numbers in `config/scoring.py`
(the `SCORE_*` and `TIER_*` constants) — never the measurement code. Code still reads
them through `config.settings`, which re-exports every default and is the one namespace
that scoped overrides and tests patch.

### Also in `engine_alpha/`

| File | What it does |
|------|--------------|
| `evaluation.py` | The ONE per-ticker chain that live scans and seed replays share (see section 3). |
| `frames.py` | The engine's own 2-year daily window rule — what the reader sees — kept here so the engine never imports the download code. |
| `freeze/manifest.py` | The engine's identity: an explicit list of every setting that can change a decision, hashed, so two runs can prove they used the same engine. |
| `stability.py` | Measure-only and dark (`ELECTION_STABILITY_ENABLED`): does the elected reading survive moving the evaluation day back? Real structures persist; junk flickers. |
| `election_identity.py` | The one test of whether two elected structures are the SAME reading, shared by the operator-agreement harness and the stability read. |

## 3. `core/pipeline/` — the Conductor ("runs the screen")

The only part that knows the *order of operations*. For each stock it: filters the
junk, asks the Structure Engine where the box/LPS is, asks the Scoring Engine how good
it is, and assembles the ranked list.

Two files sit at the top of the folder; the rest is grouped by job. `market_data/`,
`universe/` and `screening/` re-export their main names from the folder itself.

| File | What it does |
|------|--------------|
| `data.py` | The stable public doorway: exports `get_tickers`, `fetch_data`, `get_market_context`, and `get_provider`. |
| `json_safety.py` | Makes scan payloads safe for plain JSON (NaN, dates, numpy numbers). |
| `screening/screener.py` | `run_screener`: loads data, prepares ticker frames, broadcasts market context, runs workers, and ranks results. |
| `screening/scan_job.py` | The whole nightly job: scan → dashboard payload → freshness check → archive; also the download-only refresh. |
| `screening/dashboard.py` | Writes `output/screener_data.json` (and the per-universe variants), the data file the React frontend loads, on every scan. Despite the name it is not the retired HTML dashboard. Moved from `output/` on 2026-09-24. |
| `screening/terminal.py` | Formats scan results for the terminal (percentages, day counts, tier colours). Moved from `output/` on 2026-09-24. |
| `evaluation.py` (lives in `engine_alpha/`) | Per-ticker evaluation: baseline filter, structure pass, LPS check, scoring, and result row assembly — extracted with the reading engine it composes. |
| `market_data/providers.py` | Market-data source abstraction. The screener fetches its panel through `get_provider().fetch(...)`, not a vendor directly, so a bulk-EOD source can be slotted in behind one contract. Today only `yahoo` (wraps `downloads.fetch_data`). |
| `market_data/downloads.py` | The Yahoo provider's implementation: yfinance downloads, retry/recovery, split-drift checks, and the parquet cache. |
| `market_data/cache.py` | Small filesystem, metadata, and market-clock helpers used by the data modules. |
| `market_data/rate_limit.py` | The throttle on every Yahoo request, so the fetch stays under the provider's limit. |
| `market_data/file_lock.py` | The cross-process lock on each universe's price cache, so the scheduler, a manual job and a CLI run can't corrupt it by writing at once. |
| `market_data/fetch_health.py` | Dead-ticker quarantine (skip symbols that keep returning nothing, re-probed after a cooldown) + per-run fetch-health telemetry written to `cache_meta.json`. Cuts wasted requests/429s on the delisted tail. |
| `market_data/candles.py` | The one builder of chart bars for the wire (scan payload, health board, watchlist), so every chart gets identical data. |
| `market_data/data_freshness.py`, `market_data/market_calendar.py` | Is the price data current to the latest completed trading day (NYSE sessions)? Behind the stale-data guard. |
| `market_data/cache_status.py`, `market_data/market_data_health.py` | Cache coverage, health and repair state, for the dashboard. |
| `universe/descriptor.py` | Which market a scan covers (US stocks, US sectors, commodities and ETFs) and where each one's cache and output files live — the single source of truth. |
| `universe/tickers.py` | Loads and refreshes the cached common-stock universe. |
| `universe/ticker_admission.py` | Ticker admission ledger: rejects obvious non-common instruments from directory facts, remembers too-young / empty Yahoo-history symbols, and skips them until a recheck window. |
| `context/market_context.py` | Computes the SPY 6-month return and universe breadth broadcast used by scoring. |
| `context/health_board.py` | The Market & Sector Health Board: a looser position-in-cycle read of every sector and ETF member, separate from the setup engine. |
| `telemetry/scan_metrics.py` | Per-scan timing telemetry: records universe load, market-data fetch, frame prep, market context, evaluation, and result assembly into `cache_meta.json` + `output/scan_metrics.jsonl`. |

## 4. `core/archive/` — the Measuring Stick ("learn from outcomes")

**Not part of the live screen.** It records every setup the engine finds, fills in what
actually happened afterward, and lets us study which setups won. This is how we earn
the right to re-tune the scoring.

Run these with the repo venv, `.\.venv\Scripts\python.exe -m core.archive.<name>` — bare `python`
is a trap on this machine (`docs/deploy.md` §2).

| File | Run it with | What it does |
|------|-------------|--------------|
| `writer.py` | (automatic) | Saves each scan's results into the archive database. |
| `seed.py` | `-m core.archive.seed` | Bootstraps the archive with known historical setups. |
| `forward_returns.py` | `-m core.archive.forward_returns` | Fills in real outcomes once setups are old enough. |
| `analyze.py` | `-m core.archive.analyze` | The report card: winner fingerprint, what predicted returns, bias warnings. |
| `purge.py` | `-m core.archive.purge` | Cleans uncurated rows out of the archive. |
| `seed_recall.py` | `-m core.archive.seed_recall --hermetic-check` | Does the engine still re-find every known seed winner? The hermetic form replays committed data offline. |
| `near_miss_writer.py` | (automatic) | Records the setups the engine narrowly refused (the near-miss lane). Measure-only. |
| `near_miss_outcomes.py` | (automatic) | Fills in what happened after each near-miss, with the same outcome math. |
| `outcomes.py` | (shared) | The ONE home of outcome math (returns, MFE/MAE, trigger), used by the updater and the backtest alike. |
| `episodes.py` | (shared) | Collapses a base re-flagged day after day into one episode, so it counts once in any win rate. |
| `missed_winners.py` | (dashboard) | Did the engine flag winners the operator never engaged with? Its standalone edge against his discretion. |
| `result_adapter.py` | (shared) | Maps the live evaluation result onto the archive writer's column names. |
| `db_path.py` | (shared) | The one place that decides which database file the archive opens (`CHROLLO_DB_PATH`, else the live journal DB). |

---

## The one-line flow

`.\.venv\Scripts\python.exe run_screener.py` → **pipeline** loads **data**, and for each stock asks
**structure** "what's here?" then **scoring** "how good?", ranks them, shows the
dashboard, and (if enabled) hands the results to **archive** to remember.
