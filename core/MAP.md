# Map of the Engine (`engine_alpha/` + `core/`)

A plain-English tour of how the screener is organized. No coding knowledge needed —
this is the "where does X live?" cheat sheet.

The engine is built as **one reader and a conductor**, plus a measuring stick. The
reading half was extracted from `core/` into the **`engine_alpha/`** package in the
2026-07-18/20 engine-α freeze; on Sat 31/10/2026 that old engine (its `structure/` and
`scoring/` halves and the `evaluation.py` chain) was retired for the alpha reader built
beside it from Sun 20/09/2026 (`docs/engine_reference.md`, "The old engine retired"). The
conductor and the archive stay in `core/`:

```
        core/pipeline/   "THE CONDUCTOR"
        runs the show, in order
                 │
                 ▼
        engine_alpha/reader.py   "THE ONE DOOR"
        the frame contract, the universe door, then the read
                 │
                 ▼
        engine_alpha/two_eyes/   "THE ALPHA READER"
        line → box → LPS → story → grade → state word
        (one record of facts and dated words)
                 │
                 ▼
        engine_alpha/two_eyes_adapter.py   "THE VOICE"
        the record spoken as the scan's result row

        core/archive/    "THE MEASURING STICK"
        records what happened, so we can learn
```

The golden rule: **the reader reads, the adapter speaks, the pipeline coordinates.**
The reader reports what it saw — the box, the LPS, the words, the grade, the state word —
as one record, and nothing outside it re-decides any of that.

This map covers `engine_alpha/`, `core/pipeline/` and `core/archive/`. For `core/backtest/`,
`core/regime/`, `core/fundamentals/`, the backend, frontend, tests and tools, see
[`docs/architecture.md`](../docs/architecture.md).

---

## 1. `engine_alpha/two_eyes/` — the alpha reader ("how we SEE the chart")

Pure functions of the bars' highs and lows and each day's own range. Give it price bars,
it tells you *what is there*, in his order, stage by stage, and what it says is final: no
later layer re-reads the chart. **This is the prime directive: draw the consolidation
accurately and read its LPS faithfully.** The rules are in `docs/strategy_alpha.md`; the
mechanics, stage by stage, in `docs/engine_reference.md` ("The two-eyes reader").

| File | Stage | What it does (in plain terms) |
|------|-------|-------------------------------|
| `frame.py` | before any read | The frame contract: what a chart must be (two years of daily bars, no trading day missing from the middle, no day twice). A frame that is not a chart is refused by name, never repaired. |
| `line.py`, `swing_line.py` | 1 | The ONE swing line over the whole chart (a turn commits when price backs off the running extreme by 0.75 of the bar's own range), and the far view that is the same line seen from further back. Everything after inherits its dates. |
| `runs.py`, `walk.py` | 2, 3, 4 | The end of the trend (each run's climax and reaction, decided on the line first), the rule of the pair (two rails on the ends of earlier swings, moved one in front of the other), and the box's life: when it is answered and alive, when a later box takes over (a run past the far rail, the way back, the step up, the wrap), when it ends. |
| `mini.py` | 4 (off) | A smaller box alongside its parent, read with the walk's own life rules. Sunset on his word, Fri 30/10/2026 (`MINI_ENABLED` False); kept whole behind the switch. |
| `story.py`, `line_words.py` | 5 | The words the drawing printed against the box shown: every push and THE SOS, the upthrust, the last supper, Phase C and its spring test, where Phase D opens. Each in the box's own daily range; they describe a chart and never filter one. |
| `lps.py` | 6 | The Last Point of Support and its trigger, read on the reader's own box: the run of receding days, his four sentences, the trigger at the high. |
| `grade.py`, `clarity.py`, `traits.py` | 7 | The grade: the letter (S/A/B/C) from his dead space and whether the base held (`grade.py`); the place within the letter from his traits — tightness, clean swings, right-side contraction, no dead space, rails the turns sit on, the stock's stage (`clarity.py` measures the swings and the rails, `traits.py` is the table; weights `TRAIT_WEIGHTS` in `two_eyes_numbers.py`). |
| `state.py` | last | The ONE state word a chart carries on the screen (fired, crossed, lines no LPS yet, forming, ...), one closed table. |
| `record.py` | — | The shape of a read: the boxes (parent, mini, the earlier ones), the LPS and which box it used, the events, the grade, the state word and the trail that explains it. The adapter, the archive and the screen share this contract. |
| `daily_range.py` | — | The daily range (ATR), the reader's own copy: the unit every word and rail area is measured in. |

**Want to change how the box or LPS is *read*?** This folder — and the number it reads, in
`two_eyes_numbers.py`, never a copy inside the stage.

## 2. Beside the reader in `engine_alpha/`

| File | What it does |
|------|--------------|
| `reader.py` | The ONE door. `evaluate_ticker` (the whole chain under the skip guard: a result row, `None`, or `EVAL_ERROR`), `scan_read` (the nightly scan's pool worker: the same, plus `NotRead` for a frame the reader would not read, listed apart from the crashes), `run_eval_chain` (the chain that raises `ReadFailed`, for the seed and the chart-state page), `read_record` (the reader's own record, for the workbench, the health board and word recall). Every one of them: the frame contract, then the universe door, then the read. |
| `universe_door.py` | The baseline gate before the read, ONE implementation: price → 50-day volume → SMA50 → SMA200 → year-over-year return; the first fail names the reason. A chart it refuses is "not scanned" and never read. Floors in `config/universe.py`. |
| `two_eyes_adapter.py` | The record spoken in the scan's result shape (`REQUIRED_KEYS`: `Score` the grade's number, `Tier` its letter, `_R`/`_S`, the trigger, the dates), the screen block, the trend template and the stock's stage on every fire. The one place the reader's words and the result row meet. |
| `two_eyes_archive.py` | The reader's archive column family (dated rails, both boxes, the LPS, the story, the grade): ONE producer for the scan writer, the seed and the manual add. |
| `two_eyes_roles.py` | The roles a box can hold (parent, mini, earlier), one tuple, import-free. |
| `two_eyes_numbers.py` | Every number the reader reads, one plain line each, and its switches (`MINI_ENABLED`, `RESPECT_ELECTS`, `WRAP_TAKES_OVER`, ...). Import-free; the version stamp hashes all of it, so a changed number moves the night's `engine_config_version`. |
| `metrics.py` | The stock measures the reader and the scan share: ATR, ADR%, the distance to the 52-week high, Minervini's trend template, the weekly/monthly resample. Measure-only, no settings. |
| `stage_read.py` | The stock's life-cycle stage (1 neglect, 2 advance, 3 top, 4 decline) on its weekly chart and the week its advance began; attached to every fire, display and archive only. |
| `sentinels.py` | `EVAL_ERROR` (the failed read, an Enum member so it survives the process pool) and the closed table of state words the wire carries. |
| `market_sessions.py` | When the market was open: the NYSE session rules, owned here so the leaf never imports `core`. |
| `freeze/manifest.py` | The engine's identity: 29 settings that can change a decision plus the reader's own numbers, hashed, so two runs can prove they used the same engine. |

**Who reads a chart, and how** (every one through the door, the frame contract and the
universe door first; `reader_pin` alone reads before the door, on purpose):

| Caller | Through the door | Why it reads |
|---|---|---|
| `core/pipeline/screening/screener.py` | `scan_read` | the nightly scan; the night prints the ruleset it read with (`TWO_EYES_RULESET`) |
| `core/archive/seed.py` | `run_eval_chain` | the archive seed, and a single row's re-read from `webapp/backend/domains/archive/actions.py` |
| `webapp/backend/domains/screener/chart_state.py` | `run_eval_chain` | one ticker's state word, on demand |
| `webapp/backend/domains/calibration/grading.py` · `fired.py` | `evaluate_ticker` · `read_record` | the workbench's fired chip (the harness `tools/calibration/calibration_harness.py` shares it) and "why did this mark miss" |
| `core/pipeline/context/health_board.py` | `read_record` | the health board's box for every ETF member |
| `core/calibration/replay.py` | `evaluate_ticker` | the seam the ratchets and the calibration boards share |
| `tools/regression/marks_corpus.py` · `negative_corpus.py` · `shadow_diff.py` | `evaluate_ticker` | the marks ratchet, the junk pin, the fleet shadow |
| `tools/audits/live_reader_audit.py` | `read_record`, `scan_read` | the saved scan replayed, read twice for consistency |
| `tools/calibration/word_recall.py` | `read_record` | his drawn words against the reader's own |
| `tools/regression/reader_pin.py` | `two_eyes.read`, before the door | what the reader SAYS about 105 fixture charts, the ones the door refuses included |


## 3. `core/pipeline/` — the Conductor ("runs the screen")

The only part that knows the *order of operations*. For each stock it asks the one door:
is this chart admitted, where are its box and LPS, what grade, what state word; then it
assembles the ranked list.

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
| `market_data/providers.py` | Market-data source abstraction. The screener fetches its panel through `get_provider().fetch(...)`, not a vendor directly, so a bulk-EOD source can be slotted in behind one contract. Today only `yahoo` (wraps `downloads.fetch_data`). |
| `market_data/downloads.py` | The Yahoo provider's `fetch_data`: the parquet cache's state machine (meta, quarantine, admission, the absent-session ledger). |
| `market_data/panel_fetch.py` | Cold and incremental panel builds and their repairs: missing-ticker recovery, latest-session repair, the split probe, the overlap merge, the forming-bar cap. |
| `market_data/yahoo_download.py` | Yahoo requests: retry, backoff, the shared rate limit, the download pool (the archive downloads use it too). |
| `market_data/price_regime.py` | The as-traded vs dividend-adjusted flag and its cache tag. |
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
| `analyze_features.py` | (shared) | The report's column lists and the engine-epoch seam. |
| `analyze_stats.py` | (shared) | The report's numbers: outcomes, signal edge. |
| `analyze_report.py` | (shared) | The report's seven sections as text (the seventh: his calibration setups beside the fires). |
| `purge.py` | `-m core.archive.purge` | Cleans uncurated rows out of the archive. |
| `seed_recall.py` | `-m core.archive.seed_recall --hermetic-check` | Does the engine still re-find every known seed winner? The hermetic form replays committed data offline. |
| `calibration_outcomes.py` | (automatic) | Fills in what happened after each of his calibration setups, measured like a fire (ruling 2026-10-03: archived setups too), and loads them for every study as their own group. |
| `outcomes.py` | (shared) | The ONE home of outcome math (returns, MFE/MAE, trigger), used by the updater and the backtest alike. |
| `episodes.py` | (shared) | Collapses a base re-flagged day after day into one episode, so it counts once in any win rate. |
| `missed_winners.py` | (dashboard) | Did the engine flag winners the operator never engaged with? Its standalone edge against his discretion. |
| `result_adapter.py` | (shared) | Maps the live evaluation result onto the archive writer's column names. |
| `db_path.py` | (shared) | The one place that decides which database file the archive opens (`CHROLLO_DB_PATH`, else the live journal DB). |

---

## The one-line flow

`.\.venv\Scripts\python.exe run_screener.py` → **pipeline** loads **data**, and for each stock asks
the **door** "is this a chart we scan, and what does the reader see?" — the box, the LPS, the
words, the grade, the state word — ranks the fires by grade, shows the dashboard, and (if
enabled) hands the results to **archive** to remember.
