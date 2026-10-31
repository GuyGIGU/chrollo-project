# Chrollo

Chrollo is a **Wyckoff / VCP / LPS stock screener** wrapped in a local web app, with an optional
Interactive Brokers (IBKR) link for portfolio snapshots. It surfaces tight, pre-breakout
consolidation setups; the operator reviews them discretionarily and trades them by hand in
TWS / TradingView. Chrollo is an **idea-generation and bookkeeping tool — it does not place trades.**

> **Prime directive:** accurate detection of *visually tight structure*. The engine borrows the
> Wyckoff vocabulary (Buying/Selling Climax, Automatic Reaction, Last Point of Support) but is
> tuned as a **Minervini-VCP + Qullamaggie-momentum** screen, not a textbook Wyckoff
> classifier. When in doubt, it favors structural correctness over catching more names.

New here? Read this file top-to-bottom, then:
- [`docs/architecture.md`](docs/architecture.md) — where every part of the repo lives, which way
  imports run, and where new code belongs.
- [`docs/current_state.md`](docs/current_state.md) — what is live, what is dark, and what comes next.
- [`docs/finviz_workflow_review_2026-10.md`](docs/finviz_workflow_review_2026-10.md) — public Finviz workflow findings, the comparison table and module-ownership cleanup (merged 2026-10-24).
- [`core/MAP.md`](core/MAP.md) — plain-English tour of how the engine is organized.
- The engine docs are split by lifecycle, and each has one job:
  [`docs/strategy_alpha.md`](docs/strategy_alpha.md) = the **theory** (what a good setup IS;
  deliberately names no files or functions so it cannot rot) ·
  [`docs/engine_reference.md`](docs/engine_reference.md) = how it is built and why it took that
  shape · [`docs/decisions.md`](docs/decisions.md) = operator rulings + the **Tested-DEAD**
  registry, append-only.
- [`docs/deploy.md`](docs/deploy.md) — how the app runs unattended as a local service.

---

## What it does, end to end

1. **Pulls market data** from yfinance into a 5-year parquet cache (`DOWNLOAD_PERIOD = "5y"`,
   incremental daily refresh, a cold refetch at least weekly). The daily structure read trims back
   to 2 years (`DAILY_STRUCTURE_PERIOD`), while the deeper cache feeds weekly/monthly context.
   SPY and QQQ ride along as market context (`INDEX_SYMBOLS`). Three universes run off the same
   engine, each with its own cache and artifact: **US Stocks** (the NASDAQ common-stock default),
   **US Sectors + Market**, and **Commodities + ETFs**.
2. **Screens** every ticker through the gate, then the alpha reader, in his order: the swing
   line → the box (the end of the trend, the pair, the box's life) → the LPS and its trigger → the story →
   the grade (a letter S/A/B/C and a place within it) → the state word. See `strategy_alpha.md`.
3. **Renders** the survivors in a React dashboard: OHLC bar charts with the detected box/LPS
   drawn on, the tier, "why-ranked" tag chips, filtering, sorting, and a star-able watchlist.
4. **Archives** every scan to SQLite and **backfills forward returns** over the following days, so
   the structural fingerprint of each setup can later be regressed against what actually happened.
5. **Optionally** connects to IBKR (manual, on-demand) to show a live portfolio snapshot. The user
   does their real trading in TWS / TradingView.

The screener half (1–4) is **fully decoupled from the broker** — automation never touches IBKR.

---

## Architecture

```
                          ┌───────────────────────────────────────────────────┐
   yfinance ──▶ parquet ──▶│  the screener engine                              │
                          │   engine_alpha/gate.py     the gate, the one way in│
                          │               (frame, the floors, then the read)   │
                          │   engine_alpha/reader.py   the alpha reader        │
                          │               (chart → line → box/ → LPS → story → │
                          │                grade → state word: one record; the │
                          │                numbers in numbers.py)              │
                          │   engine_alpha/result.py   the voice               │
                          │               (the record as the scan's result row)│
                          │   core/pipeline/  the conductor (data + per-ticker │
                          │                orchestration, ProcessPool)         │
                          │   core/archive/   the measuring stick (record,     │
                          │                forward-returns, analyze)           │
                          └───────────────┬───────────────────────────────────┘
                                          │ writes
                    output/screener_data.json   +   SQLite setup_archive
                                          │
        ┌─────────────────────────────────▼──────────────────────────────┐
        │  webapp/backend  — FastAPI                                      │
        │   • serves the screener JSON + archive + watchlist + trade log  │
        │   • serves the built React app (one origin, no Vite in prod)    │
        │   • APScheduler: daily scan + forward-returns (17:00 ET, Mon–Fri)│
        │   • IBKR service (manual connect; portfolio snapshots only)     │
        └─────────────────────────────────┬──────────────────────────────┘
                                          │ HTTP / SSE
                          webapp/frontend  — React 19 + Vite (lightweight-charts)
```

**One reader + a conductor** is the core design principle: the alpha reader (`engine_alpha/reader.py`,
one call per stage) *reads* a chart in
his order (the line, the box, the LPS, the story, the grade, the state word) into one record of measured
facts and dated words, and nothing outside it re-decides any of that; `engine_alpha/result.py`
*speaks* the record in the scan's result shape; `engine_alpha/gate.py` is the *gate*, the one way in every
caller reads through (the floors first); and `core/pipeline/` wires them together. `engine_alpha/` is a
leaf: it never imports the pipeline, the archive, the web app or the tools. `core/archive/` exists so the
reader's grades can be validated against real forward outcomes rather than intuition. (The reading engine
was extracted from `core/` into `engine_alpha/` in the 2026-07-18/20 engine-α freeze; that old engine —
`structure/` measuring, `scoring/` judging — was retired on Sat 31/10/2026 for the alpha reader built
beside it from 20/09/2026: `docs/engine_reference.md`, "The old engine retired".)

### Measure-first philosophy

New signals are added as **bonus sub-scores**: never gated, never penalizing (a name that lacks the
trait simply earns 0), with the raw measurement archived for later calibration. Tier thresholds are
**not** recalibrated when a sub-score is added — that waits until the live archive shows the new
distribution. GAP 1 (VCP progressive contraction), GAP 2 (ascending support), and GAP 3 (ADR%
absolute volatility) were all added this way.

---

## Repository layout

The full map, with import rules, compatibility paths and a "where do I put this?" table, is
[`docs/architecture.md`](docs/architecture.md).

```
engine_alpha/          The reading engine (see core/MAP.md)
  gate.py              The gate, the one way in: evaluate_ticker, scan_read, run_eval_chain,
                         read_record, and the floors before the read (price, volume, SMA50, SMA200, YoY)
  reader.py            The alpha reader: read(ticker, df), his seven stages one call each
  chart.py, line.py    Stage 1: the frame contract, the daily range, the NYSE calendar; the swing line
  box/                 Stages 2-4, the walk: pairs.py, handover.py, walk.py, mini.py (off)
  story.py, lps.py     Stage 5 the words and their dated events; stage 6 the LPS and its trigger
  grade.py, state.py   Stage 7 the letter and the traits; the state word, decided last
  record.py            The shape of a read: Read, Box, Lps, Event, Grade; the roles; the state words
  result.py            The record spoken as the scan's result row + the screen block; archive.py the
                         archive columns; numbers.py the reader's numbers (hashed); stock.py the
                         stock's own facts (ADR%, 52-week, trend template, the weekly stage)
  stamp.py             The engine config hash (python -m engine_alpha.stamp --hash)
core/
  pipeline/            Conductor — data.py (public data door); market_data/, universe/,
                         context/, telemetry/; screening/ (screener.py run_screener,
                         scan_job.py scan → dashboard → archive, dashboard.py + terminal.py)
  archive/             writer.py, forward_returns.py, analyze.py (+ analyze_features/stats/report),
                         seed.py, purge.py, episodes.py, outcomes.py
  calibration/         Engine replay on frozen calibration frames (workbench chips + calibration tools)
  backtest/            Edge report + backtest statistics (production: the edge tile uses it)
  regime/, fundamentals/   Relative strength, sector ranking, fundamentals (RS rating + fundamentals live, display only)
config/                Defaults by domain: universe.py (the gate's floors), reader.py (the
                         ruleset, the 2y window, the ADR window), enrichment.py, archive.py,
                         market_data.py, market_context.py, runtime.py; settings.py = the one namespace code
                         reads. tickers.csv (cached NASDAQ universe, gitignored),
                         tickers_us_sectors.csv / tickers_commodities_etf.csv (the curated ETF
                         universes), commodity_equity_map.json (ETF → related-equity drill-down)
output/                Runtime files: screener_data.json, watchlists, logs (gitignored)
webapp/
  backend/             FastAPI app — main.py; domains/ (archive, calibration, ibkr,
                         market_data, portfolio, screener, trading, watchlist); app/
                         (startup, lifespan, migrations); services/ (scan_runner, scheduler,
                         scan_status, scan_watchdog, health, scan_diagnosis,
                         interruption_cause);
                         broker_config.py, database.py
  frontend/            React + Vite — src/app/ (routes, shell), src/features/<screen>/,
                         src/shared/ (used by unrelated features), src/api/base.js;
                         dist/ (built, gitignored)
docs/                  architecture.md (layout), current_state.md (live/dark/next),
                         strategy_alpha.md (theory), engine_reference.md (how built),
                         decisions.md (rulings), structure_legend.md (vocab), deploy.md (go-live)
tools/                 Dev tools, one folder per job: regression/ (drift ratchets), audits/,
                         calibration/, research/ (censuses, A/Bs, renders), maintenance/,
                         ops/ (backup, restore drill, service recovery)
tests/                 pytest, one folder per thing it protects (engine/, pipeline/,
                         market_data/, archive/, backend/, contracts/, tooling/, regression/,
                         integration/); baselines/ and fixtures/ are data
research/              Evidence the rulings cite: evidence/ (census JSON), fidelity/ (renders, logs, A/B sheets)
run_screener.py        CLI entry: one scan → dashboard JSON → archive
setup.bat              One-time: install Python + frontend deps, build the frontend
start_dashboard.bat    Manual launcher: one uvicorn process serving UI + API at :8000
```

---

## The web app

A single FastAPI process serves both the JSON API and the **built** React app from
`http://127.0.0.1:8000` (no separate dev server in production). Key surfaces:

- **Screener grid** — one card per surviving setup, kept to the chart itself: an OHLC bar chart with
  the detected box (R/S) and LPS window drawn on, the tier badge, the weekly/monthly read, live price
  and daily change, and "why-ranked" **tag chips** (e.g. 🌀 VCP Coil, 📈 Ascending Support,
  ⚡ High ADR, 🤫 No Supply, ⚠️ Heavy Resistance), plus tier/setup/tag filters and sorting. The
  score, setup name, sub-scores and distance-to-trigger live in the click-through detail lens.
- **Watchlist** — a user-curated star toggle persisted to SQLite; bridges the grid to manual
  review in TWS / TradingView.
- **Archive view** — historical setups with their forward outcomes (the regression dataset).
- **Trade journal** — manual + IBKR-imported trades with P&L / R stats (paginated table).
- **IBKR panel** — connection status and a manual **Reconnect** button for portfolio snapshots.

Tag chips and score pills render verdicts the engine already resolved on the wire — no scoring
cap, threshold, or fire-rule is re-declared in frontend JS (conventions.md EC-28);
the legacy client-side score path RETIRED 2026-08-23 — `setupScoreMath.js` and its fire rules
are gone, and `webapp/frontend/src/shared/setup/tagCatalog.js` carries what remains: labels,
groups and tones, never a threshold.

---

## The archive (regression dataset)

Every scan upserts each setup to the `setup_archive` table in
`webapp/backend/trading_journal.db` (keyed on `ticker + scan_date + universe_type`), capturing the full structural
fingerprint (box width, touches, LPS shape, contraction/support/ADR sub-scores, market context).
A few days later, `core.archive.forward_returns` backfills `fwd_return_{1,5,10,20,60}d`, MFE/MAE, and
whether/when the breakout trigger fired. `core/archive/analyze.py` turns this into a winner
fingerprint. This is the feedback loop that will eventually justify (or reject) scoring-weight
changes — see the measure-first note above.

A **stale-data guard** refuses to archive a run whose last price bar isn't the latest completed
trading session, so unattended scans never archive setups computed on stale data.

---

## Running it

**Interpreter:** every Python command below names the repo venv explicitly —
`.\.venv\Scripts\python.exe`. On this machine bare `python` is a documented trap (two colliding
3.14 installs; see [`docs/deploy.md`](docs/deploy.md) §2).

### One-time setup
```powershell
.\setup.bat          # creates the repo venv if missing, installs the pinned Python deps into it + the frontend deps, builds the React app into webapp/frontend/dist
```

### A single CLI scan (no web app)
```powershell
.\.venv\Scripts\python.exe run_screener.py     # scan → writes output/screener_data.json → archives the run
```

### The app, manually (one terminal)
```powershell
.\start_dashboard.bat      # one uvicorn process serving UI + API at http://127.0.0.1:8000
```

### The app, unattended (recommended)
Run the backend as an always-on local Windows service (NSSM) with start-on-boot + auto-restart;
APScheduler then runs the scan + forward-returns daily at **17:00 ET, Mon–Fri**
(`SCAN_SCHEDULE_HOUR_ET`), tracks run health (`/scan-status/latest`, surfaced in the header), and a
scheduled task backs up the DB + cache. Code changes go live with `update_dashboard.bat`, which
**refuses to deploy while a scan is running** (`-Force` overrides).
Full runbook: [`docs/deploy.md`](docs/deploy.md).

### Archive maintenance (CLI)
```powershell
.\.venv\Scripts\python.exe -m core.archive.seed              # bootstrap known-winner setups (--force to overwrite)
.\.venv\Scripts\python.exe -m core.archive.forward_returns   # backfill outcomes (--min-age N, --force)
```

### Verification guard stack

Engineering gates and local commands: [`docs/engineering_quality.md`](docs/engineering_quality.md).
CI checks Python correctness, the core API contracts and the built frontend's daily browser flows
alongside the existing regression jobs.

Use the smallest guard that proves the change, then widen only when the touched surface warrants it:

- Local edits: run focused tests for the touched module, then `.\.venv\Scripts\python.exe -m pytest -q` before merge.
- Detector or market-data intake changes: run `.\.venv\Scripts\python.exe -m tools.regression.shadow_diff --check` (fleet canonical
  drift, ~2.5 min) and `.\.venv\Scripts\python.exe -m tools.regression.negative_corpus --check` (the junk charts' fire days, ~1.5 min).
  Both grade the marks ratchet's fired window (`core.calibration.replay.fired_window_walk`: the last 10 trading days ending at each
  frozen day, every clamp named), not the frozen day alone. The junk gate PINS the days each of the 16 junk charts fires
  (`tests/baselines/negative_corpus_baseline.json`: 47 days over 15 charts, GOOD silent) and fails on a fire on an unpinned day,
  on GOOD firing, on a crash or on a missing frame, with the day, score and tier named; a pinned day that goes quiet is named,
  not failed. A fleet ticker with no fire in the window is dropped; one that fires records the canonical fields of its LAST
  fire plus `first_fire` / `last_fire` / `fire_days`, so a fire that moves a day earlier reads as drift (final method build
  step 1, operator ruling 2026-09-13). Re-pinning the junk days is a declared seam (`--pin-known-fires`, recorded in
  `docs/decisions.md`), never a routine recapture.
- Reader, fetch, or seed-recall-sensitive changes: run `.\.venv\Scripts\python.exe -m core.archive.seed_recall --check`.
  The checked baseline is intentionally `basis: "fresh"`; only recapture it with an explicit review decision.
- Reader changes: also run `-m tools.regression.marks_corpus --check` (the operator-marks ratchet: his 52 drawings, 51
  fire on some day of their window), `-m tools.regression.reader_pin --check` (the reader's own record over 105 fixture
  charts; zero-diff is the fold acceptance), and, once the change has landed in the main checkout and a scan has run on it,
  `-m tools.audits.live_reader_audit --check --repeat` (the saved scan replayed through the gate; it refuses another
  engine hash, so the first scan after the deploy is what re-pins it).
- Frontend changes: run `npm --prefix webapp\frontend run lint`, `npm --prefix webapp\frontend test`,
  and `npm --prefix webapp\frontend run build` — the build in a worktree only, since the live service
  serves the main checkout's `webapp/frontend/dist` (`update_dashboard.bat` rebuilds it safely).

---

## IBKR / live-trading safety

This matters for any human or agent touching the code:

- **The app never executes trades, moves money, or places orders.** IBKR is used *only* for
  read-only portfolio snapshots; real trading happens in TWS / TradingView.
- The app defaults to `IBKR_MODE=live` because Chrollo reads the real portfolio, but the unattended
  service still runs **broker-free at boot**: it does **not** set `IBKR_LIVE_CONFIRMED` and
  runs with `IBKR_AUTO_CONNECT=false`, so a reboot or crash-restart never auto-grabs the IBKR session
  (which would fight TradingView for the single allowed login). Connecting is always a **deliberate
  human action**: the dashboard **Connect IBKR** button pops a real-money confirmation in live mode
  and, only on your OK, hands the API session to Chrollo for that session; **Disconnect** releases it
  again. That confirmation is per-click and **never persisted** — the next boot is broker-free.
  The link is **read-only** (portfolio snapshots only); keeping IB Gateway's *Read-Only API* enabled
  is recommended as a broker-level guarantee that Chrollo can never place an order.
- Do **not** use `IBKR_LIVE_CONFIRMED` in code, scripts, service configs, env files, or automation.
  The in-app **Connect IBKR** button is the live gate: it sends a per-click `confirm=true` flag
  (`/ibkr/reconnect`, `service.start(confirmed=...)`) after the user accepts the real-money prompt.
  That confirmation is never persisted and cannot pre-authorize the next boot.

---

## Tech stack

Python (pandas, numpy, scipy, yfinance, ib_async, APScheduler) · FastAPI + Uvicorn · SQLAlchemy +
SQLite (WAL) · React 19 + Vite, lightweight-charts + recharts, plain JS/JSX (no TypeScript) · runs
locally on Windows, localhost-only.
