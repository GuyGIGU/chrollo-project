# Architecture

How Chrollo's code is laid out, which way the imports run, and where new code goes.
This is the map for the whole repo. For the engine's internals see
[`core/MAP.md`](../core/MAP.md); for what the engine is trying to see, see
[`strategy_alpha.md`](strategy_alpha.md); for how it is built, see
[`engine_reference.md`](engine_reference.md). The old-path to new-path table for the
September 2026 reorganisation is in
[`migrations/2026-09-domain-refactor.md`](migrations/2026-09-domain-refactor.md).
What is live, dark or open right now is in [`current_state.md`](current_state.md).

Every `python` in this doc means the repo venv, `.\.venv\Scripts\python.exe`: this machine's bare
`python` is a different install without the dependencies (`AGENTS.md`).

## 1. System overview

Chrollo is a local stock screener with a web app. It never places trades.

```
yfinance -> parquet cache -> core/pipeline (conductor)
                               |  calls, per ticker
                               v
                          engine_alpha (structure measures -> scoring judges)
                               |
             output/screener_data.json  +  SQLite archive (core/archive)
                               |
                         webapp/backend (FastAPI, one process, :8000)
                               |  HTTP / SSE
                         webapp/frontend (React, built into dist/)
```

- A scan runs in a child process (`run_screener.py`), started either by the in-process
  scheduler or by a manual button (`webapp/backend/services/scan_runner.py`).
- The backend serves the scan payload, the archive, the journal, the watchlist, the
  calibration workbench and the built frontend from one origin.
- IBKR is optional, manual and read-only (portfolio snapshots only). The rules are in
  [`AGENTS.md`](../AGENTS.md).

## 2. Dependency direction

Imports run one way. The arrows below are real imports, checked 2026-09-24 with
`git grep` over the tree.

```
webapp/frontend --HTTP/SSE--> webapp/backend
webapp/backend  --> core --> engine_alpha --> config (via config.settings)
webapp/backend  --> engine_alpha      (lazy only, inside functions)
tools, tests    --> anything
research/       --> nothing imports it
```

| Rule | Where it is enforced or recorded |
|---|---|
| `engine_alpha` is a leaf. It may import `config` and numeric libraries. It may not import `webapp`, `tools`, `ib_async`, `sqlalchemy`, `yfinance`, `requests`, `httpx`, `apscheduler`, `fastapi` or `uvicorn`, and from `core` only `core.fundamentals.advisory` (allow-listed; nothing uses it today). It never touches `sys.path`. | [`tests/integration/test_engine_alpha_runtime.py`](../tests/integration/test_engine_alpha_runtime.py) (`test_engine_alpha_is_a_leaf_package`, `test_engine_alpha_never_touches_sys_path`) |
| The FastAPI boot path loads no `engine_alpha` module. Backend code that needs the engine imports it inside the function. | same file, `test_fastapi_boot_stays_engine_free` |
| No live code (Python, or the frontend's JS) names a module the refactor moved. | [`tests/integration/test_moved_module_paths.py`](../tests/integration/test_moved_module_paths.py) |
| Nothing in production imports `research/`. | [`research/README.md`](../research/README.md) |
| Production code (`core`, `config`, `webapp/backend`, `run_screener.py`) never imports `tools/`. | [`tests/integration/test_production_never_imports_tools.py`](../tests/integration/test_production_never_imports_tools.py) |

One seam runs against the arrows. It is known and lazy:

| Seam | Why it exists | Status |
|---|---|---|
| `core/archive/*` and `core/pipeline/screening/dashboard.py` (`_resolve_sector_etf`) import the backend's ORM by bare name (`archive_models`, `database`), and `core/archive` in two places also `services.scan_status` and `domains.archive.queries`, with `webapp/backend` on `sys.path`. | The archive tables are declared once, as backend models; the archive writer, forward returns, seed and purge write through them, and the payload writer reads the sector-ETF map from them. | Accepted. The DB location itself lives in `core/archive/db_path.py` so the backend reads it from `core`, not the other way round. |

A second seam, the backend's calibration chips importing `tools.calibration.*`, was retired on 2026-09-24: that code now
lives in `core/calibration/` and `webapp/backend/domains/calibration/grading.py`, and the harness CLI calls the same code.

## 3. Directory ownership

| Path | Owns | Kind of code |
|---|---|---|
| `engine_alpha/` | Reading a chart and judging it. `evaluation.py` is the one per-ticker chain. | Production (frozen engine) |
| `core/pipeline/` | Data, universe, market context, running a scan, writing the payload. | Production |
| `core/archive/` | The SQLite archive: writing rows, maturing outcomes, analysis, seeding, purging. | Production |
| `core/backtest/` | The edge report and backtest statistics. The backend's edge tile and `core/archive/analyze_stats.py` import it. | Production |
| `core/calibration/` | Replaying the engine on frozen calibration frames (`replay.py`) and the mark-agreement taxonomy (`agreement.py`), shared by the backend's workbench chips and the calibration tools. | Production |
| `core/regime/`, `core/fundamentals/` | Relative strength, sector ranking and fundamentals. Dark behind flags (see [`flag_ledger.md`](flag_ledger.md)). | Production (dark) |
| `config/` | Every default setting, split by domain; `settings.py` is the one namespace. | Production |
| `webapp/backend/` | The HTTP API, the database, the scheduler, the IBKR link. | Production |
| `webapp/frontend/` | The React app. | Production |
| `tools/` | Command-line instruments: regression ratchets, audits, calibration, research studies, maintenance, ops. | Tooling |
| `tests/` | pytest suite, one folder per thing it protects; sealed baselines and fixtures. | Test |
| `research/` | Evidence files the rulings cite: census JSON, chart renders, logs and A/B sheets. | Evidence, no importable code |
| `docs/` | Theory, implementation reference, rulings, dated studies, the operator's marks. | Docs |
| `output/` | Runtime files the scan writes (payload, logs). Only the README is tracked. | Generated |
| `run_screener.py` | CLI entry for one scan. | Production entry point |

## 4. Engine and scoring boundaries

**Structure measures, scoring judges, the pipeline coordinates.**

| Part | Job | Must not |
|---|---|---|
| `engine_alpha/structure/` | Report facts about the chart: the box, phases, LPS, events, the reader, metrics, context. Subfolders: `box/`, `phases/`, `lps/`, `events/`, `narrative/`, `metrics/`, `context/`. | Assign points or decide whether a setup is good. |
| `engine_alpha/scoring/` | Turn facts into points (`scoring.py`: `score_setup`, `compose_ta_grade`, `calculate_structure_tier`), name the sub-scores (`taxonomy.py`), and resolve chip verdicts (`tags.py`). | Read a chart. |
| `engine_alpha/evaluation.py` | The one per-ticker chain: baseline filter, structure, LPS, scoring. The scan's worker processes pickle `_evaluate_ticker` by this name. | Fetch data or write files. |
| `engine_alpha/freeze/manifest.py` | The engine config hash: a hand-picked list of settings (`ENGINE_SETTINGS_KEYS`) that can move a detector decision. `python -m engine_alpha.freeze.manifest --hash` prints it. | Include ops settings (cache, scheduler, rate limits). |

Settings:

- Detection knobs default in `config/engine.py`. Weights, grade scales and tier thresholds
  default in `config/scoring.py` (`SCORE_*`, `TIER_*`).
- Every consumer reads them as `from config import settings`. `config/settings.py`
  re-exports each default by name, and scoped overrides patch that one module
  (`engine_alpha/structure/context/htf.py`, `window_override`), so every reader sees the
  same value. Never import `config.engine` or `config.scoring` directly in engine code.
- A new setting goes in its domain file **and** in the import list of `config/settings.py`.
  If it can move a detector decision, add it to `ENGINE_SETTINGS_KEYS` on purpose; that
  rotates the engine config hash, which is an archive seam.
- Before changing any of this, read the three engine docs in the order `CLAUDE.md` gives.

## 5. Pipeline boundaries

`core/pipeline/` holds no strategy opinion. It gets data, calls the engine, and hands
results on.

| Module | Owns |
|---|---|
| `data.py` | The public data door: `fetch_data`, `get_tickers`, `get_market_context`, `get_provider`. Import from here, not from the subpackages, unless you need something it does not export. |
| `market_data/` | Providers; downloads (`downloads.py`, `fetch_data`'s cache state machine; `panel_fetch.py`, cold and incremental panel builds and their repairs; `yahoo_download.py`, Yahoo requests, retry and the shared rate limit; `price_regime.py`, as-traded vs adjusted prices); the parquet cache, freshness, the market calendar, rate limiting, the cache file lock, fetch health. |
| `universe/` | Universe descriptors, ticker lists, ticker admission. |
| `context/` | Market regime (`market_context.py`) and the sector health board. |
| `screening/` | `screener.py` (`run_screener`: evaluate every ticker in a process pool), `scan_job.py` (scan, then payload, then archive; the nightly job), `dashboard.py` and `terminal.py` (the payload writers). |
| `telemetry/` | Scan stage timings. |
| `json_safety.py` | Making payloads safe for stdlib JSON. |

The handoff to the archive is one call: `scan_job` calls
`core.archive.writer.archive_scan_results`. A stale-data guard refuses to archive a run
whose last bar is not the latest completed session.

## 6. Backend domains

`webapp/backend/main.py` builds the app, adds middleware and includes every router.
Route handlers are sync `def` on purpose (FastAPI's threadpool); the SSE stream endpoints
in `domains/portfolio/streams.py` are the `async def` exceptions.

| Domain | Routers | Owns |
|---|---|---|
| `archive` | `router.py` (`/archive`, aggregates `browse.py`, `reviews.py`, `calibration.py`, `actions.py`); `edge_router.py` (`/engine-edge`) | Archive ORM models (`models.py`, `review_models.py`), queries and episode grouping, the read-verdict concordance, the engine-edge summary (reads `core.backtest`), sector and market metadata for archive rows. `calibration.py` here is archive stats and health, not operator marks. |
| `calibration` | `router.py` (`/calibration`) | The operator's marks (models, validation), frozen replay frames (`frame_store.py`), per-mark grading (`grading.py`, shared with `python -m tools.calibration.calibration_harness`), and the agreement, fired and trigger-grade chips. |
| `ibkr` | `router.py` (`/ibkr/status`, `/ibkr/reconnect`, `/ibkr/disconnect`, ...) | The `ib_async` client on its own thread (`service.py`), event fan-out, object mapping. Manual connect only. |
| `market_data` | `router.py` (`/market-data`), `candles.py` (`/candles`), `prices.py` (`/live-prices`) | The UI's single door onto the provider (`service.py`), candle caches, earnings lookups, live quotes. |
| `portfolio` | `router.py` (`/portfolio/*`, `/ibkr/import-csv`), `streams.py` (`/stream/*`, SSE) | The portfolio snapshot cache and its shaping. |
| `screener` | `router.py` | The scan payload (`/screener-data/`, `/screener-summary/`), scan status, and the manual scan and download SSE streams. |
| `trading` | `router.py` (trades, `/journal-stats`), `journal.py`, `tags.py`, `analytics.py` (`/analytics`), `risk_router.py` (`/live-risk`) | The trade journal models, IBKR execution and CSV import, statistics, open-trade risk. |
| `watchlist` | `router.py` (`/watchlist`) | The dated watchlist event ledger. |

Outside the domains:

| Path | Owns |
|---|---|
| `app/` | Startup (`startup.initialize_database`), the lifespan that starts background services (`lifecycle.py`), migrations (`migrations/{additive,archive,calibration,watchlist}.py`), orphaned-run reconciliation, the same-app dependency, serving the built frontend, UTF-8 log streams, and `core_settings.load_core_settings` (a fresh copy of `config/settings.py` for the scheduler). |
| `services/` | The scan lifecycle, which crosses domains: `scan_runner`, `scheduler` (`America/New_York`), `scan_status`, `scan_watchdog`, `health`, `scan_diagnosis` (the failure verdicts and their words), `interruption_cause` (why an interrupted run died, read from the Windows event log at startup). |
| `middleware/` | Request ids and the same-app origin guard. |
| `database.py` | Engine and session setup (SQLite WAL). |
| `broker_config.py` | IBKR settings. It stays top-level because it carries its own manual-connection safety contract. |

## 7. Frontend features

`webapp/frontend/src/`:

| Path | Owns |
|---|---|
| `app/` | `App.jsx` (the route table), the shell (`components/`), appearance and UI scale. |
| `features/<name>/` | One screen each: `home`, `screener`, `watchlist`, `journal` (the `/dashboard` route), `options`, `portfolio`, `archive`, `calibration`, plus `ibkr` (status and controls used by the shell). Each has a `<Name>Route.jsx` where it is a page, and `components/`, `hooks/`, `model/` (pure logic) and `presentation/` (labels and formatting) as needed. |
| `shared/` | Only code used by unrelated features: `charts/`, `components/`, `formatting/` (the one null guard `fx` is in `shared/formatting/format.js`; `portfolioFormat.js`, the portfolio money format the journal also uses), `hooks/` (`screenerStore.js`, the scan data cache the screener, home and watchlist read), `navigation/`, `presentation/`, `setup/` (the setup card, lens and chip catalog `tagCatalog.js`). |
| `api/base.js` | `API_BASE`, the one backend URL. |

Rules that go with this layout:

- A piece used by one feature lives in that feature. Move it to `shared/` only when a second,
  unrelated feature needs it.
- The wire carries verdicts, never rules: no threshold or fire rule is re-declared in
  frontend code (`conventions.md` EC-28).
- The test list is in `package.json` and `src/testManifest.test.js` fails if a test file is
  missing from it.
- Features import each other one way only (today: home to journal, screener and watchlist; options and
  portfolio to journal; screener to watchlist). `src/featureImportCycles.test.js` fails when two features
  import each other.

## 8. Archive and research

| Thing | What it is | Where |
|---|---|---|
| Daily observation | One archive row per ticker per scan day per universe. | `core/archive/writer.py` writes it; `setup_archive` table |
| Episode | A base re-flagged day after day, collapsed into one event. Every statistic should count episodes. | `core/archive/episodes.py` |
| Outcome | Forward returns, MFE/MAE, trigger, barrier label, filled once a row is old enough. | `core/archive/forward_returns.py`, `core/archive/outcomes.py` |
| Analysis | The winner fingerprint and signal-edge read. | `python -m core.archive.analyze` (`analyze_features.py`, `analyze_stats.py` and `analyze_report.py` hold its columns, numbers and text) |
| Backtest statistics | Edge report, null model, in-sample/out-of-sample split. Production code, not a scratch area. | `core/backtest/` |
| Instruments | Census and study scripts that produce evidence. | `tools/research/` |
| Evidence | The JSON and renders those scripts produced, kept so rulings can be re-read. | `research/evidence/`, `research/fidelity/` |
| Write-ups and rulings | Dated studies; the rulings they led to. | `docs/*_2026-*.md`, [`decisions.md`](decisions.md) |

Sealed ground truth is not in `research/`: the operator's marks are in `docs/marks/` and the
regression baselines in `tests/baselines/`. `tools/_bootstrap.py` refuses any tool write
into either. [`research/README.md`](../research/README.md) has the full lifecycle.

## 9. Public entry points

| Entry point | Use |
|---|---|
| `run_screener.py` | One CLI scan: fetch, evaluate, write `output/screener_data.json`, archive. The backend runs this same script as its scan child process. |
| `core.pipeline.data` | The data door (`fetch_data`, `get_tickers`, `get_market_context`, `get_provider`). |
| `core.pipeline.screening.run_screener` | Evaluate a universe and return ranked results (also importable as `core.pipeline.run_screener`, lazily). |
| `core.pipeline.screening.scan_job` | `run_scan_and_export`, `run_all_universe_scans`: the full scan, payload and archive job. |
| `engine_alpha.evaluation` | The per-ticker chain (`_evaluate_ticker`, `evaluate_ticker_with_near_miss`, `evaluate_ticker_with_power_play`). |
| `webapp/backend/main.py` | The FastAPI app. Do not boot it as an agent; importing it runs the DB migrations, so set `CHROLLO_DB_PATH` first. |
| `python -m core.archive.<x>` | `forward_returns`, `analyze`, `seed`, `seed_recall`, `purge`. |
| `python -m tools.<category>.<x>` | Categories: `regression`, `audits`, `calibration`, `research`, `maintenance`, `ops`. |
| `python -m engine_alpha.freeze.manifest --hash` | The engine config hash. |

## 10. Compatibility paths and why they remain

| Path | Real implementation | Why it stays |
|---|---|---|
| `config/settings.py` | `config/{engine,scoring,enrichment,archive,market_data,market_context,runtime}.py` | It is the one runtime namespace. Scoped overrides set attributes on it, the manifest reads it, and every consumer must see the same values. Not a shim to remove. |
| `webapp/backend/frame_store.py`, `webapp/backend/marks_validity.py` | `domains/calibration/frame_store.py`, `domains/calibration/validation.py` | Tools and tests import them by the old names, both bare and as `webapp.backend.<name>`. Each alias swaps itself in `sys.modules` for its target, resolved relative to its own name: bare `frame_store` is `domains.calibration.frame_store`, and `webapp.backend.frame_store` is `webapp.backend.domains.calibration.frame_store` (the same for `marks_validity` and `validation`). These are two module instances with separate globals, exactly as before the move, so a test or tool that patches a global (`FRAMES_DIR`, say) must patch both, as `tests/backend/test_frame_store.py` does. |
| `webapp/backend/models.py`, `webapp/backend/archive_models.py` | `domains/*/models.py`, `domains/archive/models.py` and `market_context.py` | Registries: importing them registers every model before `create_all` in `app/startup.py`. `core/archive` and many tests import `archive_models` by bare name. |
| Lazy `__init__.py` in `engine_alpha/structure/{lps,narrative,metrics}/` and `core/pipeline/{universe,market_data,screening}/`, plus `core/pipeline/__init__.py` | `detection.py`, `reader.py`, `base.py`, `descriptor.py`, `providers.py`, `screening/screener.py` | They keep short import names for a few public functions. The `core/pipeline` ones are lazy so the backend boot stays engine-free; the engine ones save nothing at load time, because `engine_alpha/structure/__init__.py` imports its subpackages eagerly. |
| `tools/calibration/replay.py`, `tools/calibration/agreement.py` | `core/calibration/{replay,agreement}.py` | Branches cut before the move import these names, and two engine comments cite them. Each alias swaps itself in `sys.modules`, so both names give one module. Remove them once those branches are ported, then add both names to `test_moved_module_paths.py`. |
| Names re-exported by `core/archive/analyze.py` | `analyze_features.py`, `analyze_stats.py` | The backend's calibration route, `tools/research/backtest_engine.py` and tests import them from `analyze`. |
| `_batched_download`, `_is_yahoo_rate_limit_text`, `price_auto_adjust` in `core/pipeline/market_data/downloads.py` | `yahoo_download.py`, `price_regime.py` | Their existing importers use `downloads`. A test that patches a name must patch the module that looks it up. |
| `tools/run_maturation.bat` | `tools/ops/run_maturation.bat` | The Windows scheduled task "Chrollo Forward Returns" was registered with this absolute path. Remove it once the task points at `tools/ops/` (an elevated change, the operator's). |
| `tools/fidelity/README.md` | `research/fidelity/` | Sealed records still cite `tools/fidelity/...`, and a sealed file is never edited to follow a move. |
| `output/README.md` | `core/pipeline/screening/` (writers), `research/evidence/` (old evidence) | Says `output/` is runtime-only and where the evidence went; `decisions.md` still cites the `output/` paths. |

## 11. Where new code belongs

Answer the six questions in [`AGENTS.md`](../AGENTS.md) ("Before creating a file") first.
Then:

| I am adding... | Put it in | Also |
|---|---|---|
| A detector measure (a fact about the chart) | The matching `engine_alpha/structure/<subfolder>/` module | Knob default in `config/engine.py` plus the `config/settings.py` import list. Measure-first: archive the raw value, never gate or penalise at add time. Update `engine_reference.md`. |
| A score term or weight | `engine_alpha/scoring/scoring.py`, named in `taxonomy.py` | Weight in `config/scoring.py`. Do not change existing weights or tiers without being asked. |
| A chip verdict | `engine_alpha/scoring/tags.py` | Label and tone only in `shared/setup/tagCatalog.js`. |
| A flag-gated engine capability | Behind a `*_ENABLED` key in `config/engine.py` | A row in [`flag_ledger.md`](flag_ledger.md) in the same change, with a kill-by date. |
| A market-data source | `core/pipeline/market_data/providers.py` (behind `get_provider`) | Settings in `config/market_data.py`. |
| A universe | `core/pipeline/universe/descriptor.py` | Ticker list in `config/`. |
| An archive column | The model in `webapp/backend/domains/archive/models.py` | The additive migrator adds nullable columns on the next boot; the writer in `core/archive/writer.py`. |
| An API endpoint | `webapp/backend/domains/<domain>/router.py` (thin), logic in a module beside it | Include a new router in `main.py`. Sync `def`. |
| Scan lifecycle behaviour | `webapp/backend/services/` | Heavy work in a subprocess or thread under `SCAN_LOCK`. |
| A DB migration | `webapp/backend/app/migrations/<area>.py` | Call it from `app/startup.initialize_database`. Additive columns need nothing. |
| A UI surface | `webapp/frontend/src/features/<feature>/` | A route in `app/App.jsx` if it is a page. |
| A UI piece two unrelated features share | `webapp/frontend/src/shared/<kind>/` | Only once the second feature needs it. |
| A one-off study | `tools/research/` | Its output under `research/evidence/`; the write-up in `docs/`. |
| A regression ratchet | `tools/regression/` | A pytest wrapper in `tests/regression/`; baselines in `tests/baselines/` (sealed). |
| An audit or static check | `tools/audits/` | Put it in pytest too, or it rots. |
| An ops or recovery script | `tools/ops/` | Hand the operator any elevated command; never register services or tasks. |
| A test | `tests/<category>/` with a unique basename | Import paths from `tests/_paths.py`. |
