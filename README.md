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

1. **Pulls market data** for the US common-stock universe from yfinance into a 5-year parquet cache
   (incremental daily refresh; weekly cold refetch). The daily read trims to 2 years, while the
   deeper cache feeds weekly/monthly context. SPY rides along for market context.
2. **Screens** every ticker through a 4-phase pipeline: baseline filters → consolidation/box
   detection → Last-Point-of-Support detection → scoring & tier (S/A/B/C/D). See `strategy_alpha.md`.
3. **Renders** the survivors in a React dashboard: candlestick charts with the detected box/LPS
   drawn on, "why-ranked" tag chips, Visual/Market score pills, filtering, sorting, and a
   star-able watchlist.
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
                          │   engine_alpha/structure/  Visual Structure Engine │
                          │               (pure geometry: boxes, LPS,          │
                          │                contractions, ADR) — no opinion     │
                          │   engine_alpha/scoring/    Scoring Engine          │
                          │               (facts → points → tier; all          │
                          │                knobs in config/settings.py)        │
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
        │   • APScheduler: daily scan + forward-returns (18:00 ET, Mon–Fri)│
        │   • IBKR service (manual connect; portfolio snapshots only)     │
        └─────────────────────────────────┬──────────────────────────────┘
                                          │ HTTP / SSE
                          webapp/frontend  — React + Vite (lightweight-charts)
```

**Two engines + a conductor** is the core design principle: `engine_alpha/structure/` *measures*
(it has no opinion and never assigns points), `engine_alpha/scoring/` *judges* (every weight is a
tunable in `config/settings.py`), and `core/pipeline/` wires them together. `core/archive/` exists
so the opinions in `scoring/` can eventually be validated against real forward outcomes rather
than intuition. (The reading engine was extracted from `core/` into `engine_alpha/` in the
2026-07-18/20 engine-α freeze.)

### Measure-first philosophy

New signals are added as **bonus sub-scores**: never gated, never penalizing (a name that lacks the
trait simply earns 0), with the raw measurement archived for later calibration. Tier thresholds are
**not** recalibrated when a sub-score is added — that waits until the live archive shows the new
distribution. GAP 1 (VCP progressive contraction), GAP 2 (ascending support), and GAP 3 (ADR%
absolute volatility) were all added this way.

---

## Repository layout

```
engine_alpha/          The frozen reading engine (see core/MAP.md)
  structure/           Visual Structure Engine — geometry: box/LPS detection, contractions,
                         ADR (no opinion)
  scoring/             Scoring Engine — score_setup, calculate_tier (opinion; weights live
                         in config/settings.py)
  evaluation.py        Per-ticker evaluation: baseline filter → structure → LPS → scoring
core/
  pipeline/            Conductor — data.py public API; tickers.py, downloads.py,
                         market_context.py, cache.py; screener.py (run_screener);
                         scan_job.py (scan → dashboard → archive)
  archive/             writer.py, forward_returns.py, analyze.py, seed.py, purge.py
config/                settings.py (all tunables), tickers.csv (cached universe)
output/                Generated screener_data.json, watchlists, logs (data files gitignored)
webapp/
  backend/             FastAPI app — main.py, routers/, services/ (scan_runner, scheduler,
                         scan_status, scan_watchdog, health), ibkr/, broker_config.py,
                         database.py
  frontend/            React + Vite — src/components/, src/hooks/, api.js, App.jsx,
                         dist/ (built, gitignored)
docs/                  strategy_alpha.md (theory), engine_reference.md (how built),
                         decisions.md (rulings), structure_legend.md (vocab), deploy.md (go-live)
tools/                 Dev/backtest and fidelity harnesses
run_screener.py        CLI entry: one scan → dashboard JSON → archive
setup.bat              One-time: install Python + frontend deps, build the frontend
start_dashboard.bat    Manual launcher: one uvicorn process serving UI + API at :8000
```

---

## The web app

A single FastAPI process serves both the JSON API and the **built** React app from
`http://127.0.0.1:8000` (no separate dev server in production). Key surfaces:

- **Screener grid** — one card per surviving setup: a candlestick chart with the detected box (R/S)
  and LPS window drawn on, the tier + score, "why-ranked" **tag chips** (e.g. 🌀 VCP Coil,
  📈 Ascending Support, ⚡ High ADR, 🤫 No Supply, ⚠️ Heavy Resistance), **Visual / Market
  score pills**, distance-to-trigger, plus tier/setup/tag filters and sorting.
- **Watchlist** — a user-curated star toggle persisted to SQLite; bridges the grid to manual
  review in TWS / TradingView.
- **Archive view** — historical setups with their forward outcomes (the regression dataset).
- **Trade journal** — manual + IBKR-imported trades with P&L / R stats (paginated table).
- **IBKR panel** — connection status and a manual **Reconnect** button for portfolio snapshots.

Tag chips and score pills render verdicts the engine already resolved on the wire — no scoring
cap, threshold, or fire-rule is re-declared in frontend JS (conventions.md EC-28);
the legacy client-side score path RETIRED 2026-08-23 — `setupScoreMath.js` and its fire rules
are gone, and `webapp/frontend/src/components/tagCatalog.js` carries what remains: labels,
groups and tones, never a threshold.

---

## The archive (regression dataset)

Every scan upserts each setup to the `setup_archive` table in
`webapp/backend/trading_journal.db` (keyed on `ticker + scan_date`), capturing the full structural
fingerprint (box width, touches, LPS shape, contraction/support/ADR sub-scores, market context).
A few days later, `update_forward_returns` backfills `fwd_return_{1,5,10,20,60}d`, MFE/MAE, and
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
.\setup.bat          # installs Python + frontend deps, builds the React app into webapp/frontend/dist
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
APScheduler then runs the scan + forward-returns daily at **18:00 ET, Mon–Fri**, tracks run health
(`/scan-status/latest`, surfaced in the header), and a scheduled task backs up the DB + cache.
Full runbook: [`docs/deploy.md`](docs/deploy.md).

### Archive maintenance (CLI)
```powershell
.\.venv\Scripts\python.exe -m core.archive.seed              # bootstrap known-winner setups (--force to overwrite)
.\.venv\Scripts\python.exe -m core.archive.forward_returns   # backfill outcomes (--min-age N, --force)
```

### Verification guard stack

Use the smallest guard that proves the change, then widen only when the touched surface warrants it:

- Local edits: run focused tests for the touched module, then `.\.venv\Scripts\python.exe -m pytest -q` before merge.
- Detector or market-data intake changes: run `.\.venv\Scripts\python.exe -m tools.shadow_diff --check` to catch canonical drift.
- Structure-reader, fetch, or seed-recall-sensitive changes: run `.\.venv\Scripts\python.exe -m core.archive.seed_recall --check`.
  The checked baseline is intentionally `basis: "fresh"`; only recapture it with an explicit review decision.
- Frontend changes: run `npm --prefix webapp\frontend run lint`, `npm --prefix webapp\frontend test`,
  and `npm --prefix webapp\frontend run build`.

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
SQLite (WAL) · React + Vite + lightweight-charts · runs locally on Windows, localhost-only.
