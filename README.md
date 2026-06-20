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
- [`core/MAP.md`](core/MAP.md) — plain-English tour of how `core/` is organized.
- [`docs/strategy_v2.md`](docs/strategy_v2.md) — the **single source of truth** for the screener
  algorithm: every gate, formula, and `config/settings.py` value, citing the function it lives in.
- [`docs/deploy.md`](docs/deploy.md) — how the app runs unattended as a local service.

---

## What it does, end to end

1. **Pulls market data** for the US common-stock universe from yfinance into a 2-year parquet cache
   (incremental daily refresh; weekly cold refetch). SPY rides along for market context.
2. **Screens** every ticker through a 4-phase pipeline: baseline filters → consolidation/box
   detection → Last-Point-of-Support detection → scoring & tier (S/A/B/C/D). See `strategy_v2.md`.
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
                          ┌─────────────────────────────────────────────┐
   yfinance ──▶ parquet ──▶│  core/  — the screener engine               │
                          │   structure/  Visual Structure Engine        │
                          │              (pure geometry: boxes, LPS,      │
                          │               contractions, ADR) — no opinion │
                          │   scoring/    Scoring Engine                  │
                          │              (facts → points → tier; all      │
                          │               knobs in config/settings.py)    │
                          │   pipeline/   the conductor (data + per-ticker │
                          │               orchestration, ProcessPool)     │
                          │   archive/    the measuring stick (record,    │
                          │               forward-returns, analyze)       │
                          └───────────────┬─────────────────────────────┘
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

**Two engines + a conductor** is the core design principle: `structure/` *measures* (it has no
opinion and never assigns points), `scoring/` *judges* (every weight is a tunable in
`config/settings.py`), and `pipeline/` wires them together. `archive/` exists so the opinions in
`scoring/` can eventually be validated against real forward outcomes rather than intuition.

### Measure-first philosophy

New signals are added as **bonus sub-scores**: never gated, never penalizing (a name that lacks the
trait simply earns 0), with the raw measurement archived for later calibration. Tier thresholds are
**not** recalibrated when a sub-score is added — that waits until the live archive shows the new
distribution. GAP 1 (VCP progressive contraction), GAP 2 (ascending support), and GAP 3 (ADR%
absolute volatility) were all added this way.

---

## Repository layout

```
core/                  The screener engine (see core/MAP.md)
  structure/           Visual Structure Engine — consolidation.py, box_primitives.py,
                         lps.py, indicators.py
  scoring/             Scoring Engine — scoring.py (score_setup, calculate_tier)
  pipeline/            Conductor — data.py public API; tickers.py, downloads.py,
                         market_context.py, cache.py; evaluation.py (_evaluate_ticker);
                         screener.py (run_screener); scan_job.py (scan → dashboard → archive)
  archive/             writer.py, forward_returns.py, seed.py, analyze.py, purge.py
config/                settings.py (all tunables), tickers.csv (cached universe)
output/                Generated screener_data.json, watchlists, logs (data files gitignored)
webapp/
  backend/             FastAPI app — main.py, routers/, services/ (scan_runner, scheduler,
                         scan_status), ibkr/, archive_models.py, models.py, database.py
  frontend/            React + Vite — src/components/ (ScreenerGrid, ArchiveTab,
                         SetupTags, ScoreBreakdown, TradeTable, charts),
                         dist/ (built, gitignored)
docs/                  strategy_v2.md (algorithm), structure_legend.md (vocab), deploy.md (go-live)
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

Tag chips and score pills are derived on the frontend from the engine's sub-score decomposition;
the sub-score caps mirror `config/settings.py` and live in one place
(`webapp/frontend/src/components/setupScoreMath.js`).

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

### One-time setup
```powershell
.\setup.bat          # installs Python + frontend deps, builds the React app into webapp/frontend/dist
```

### A single CLI scan (no web app)
```powershell
python run_screener.py     # scan → writes output/screener_data.json → archives the run
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
python -m core.archive.seed              # bootstrap known-winner setups (--force to overwrite)
python -m core.archive.forward_returns   # backfill outcomes (--min-age N, --force)
```

---

## IBKR / live-trading safety

This matters for any human or agent touching the code:

- **The app never executes trades, moves money, or places orders.** IBKR is used *only* for
  read-only portfolio snapshots; real trading happens in TWS / TradingView.
- The unattended service runs **broker-free at boot**: it does **not** set `IBKR_LIVE_CONFIRMED` and
  runs with `IBKR_AUTO_CONNECT=false`, so a reboot or crash-restart never auto-grabs the IBKR session
  (which would fight TradingView for the single allowed login). Connecting is always a **deliberate
  human action**: the dashboard **Connect IBKR** button pops a real-money confirmation in live mode
  and, only on your OK, hands the API session to Chrollo for that session; **Disconnect** releases it
  again. That confirmation is per-click and **never persisted** — the next boot is broker-free.
  The link is **read-only** (portfolio snapshots only); keeping IB Gateway's *Read-Only API* enabled
  is recommended as a broker-level guarantee that Chrollo can never place an order.
- `IBKR_LIVE_CONFIRMED=true` exists as a human-confirmation gate for connecting to a *live*
  brokerage. Do **not** set it in code, scripts, service configs, or automation. The in-app
  **Connect IBKR** button satisfies the same gate at runtime via a per-click `confirm=true` flag
  (`/ibkr/reconnect`, `service.start(confirmed=…)`) — a deliberate human click, never the env var,
  never persisted. The manual launcher (`start_dashboard.bat`) sets the env var as the human's own
  choice and is out of scope for automation.

---

## Tech stack

Python (pandas, numpy, scipy, yfinance, ib_async, APScheduler) · FastAPI + Uvicorn · SQLAlchemy +
SQLite (WAL) · React + Vite + lightweight-charts · runs locally on Windows, localhost-only.
