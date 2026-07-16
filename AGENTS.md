# AGENTS.md

Operating manual for AI coding agents working in Chrollo. Read this first, then
[`README.md`](README.md). For algorithm questions the single source of truth is
[`docs/strategy_v2.md`](docs/strategy_v2.md); for the engine layout see [`core/MAP.md`](core/MAP.md).

## What this project is
Chrollo is a **Wyckoff / VCP / LPS stock screener** in a local web app, with an optional, manual,
**read-only** IBKR link for portfolio snapshots. It surfaces tight pre-breakout setups; the operator
reviews them by eye and trades them by hand in TWS / TradingView. **Chrollo generates ideas and keeps
books — it never places trades.**

## 🚫 Hard safety rules (never violate, no exceptions)
- **Never execute trades, place/modify/cancel orders, move money, or auto-confirm anything brokerage.**
  IBKR is **read-only portfolio snapshots only**.
- **Never set, export, or default `IBKR_LIVE_CONFIRMED`** in code, scripts, service configs, env files,
  or shell. It is a per-click human gate satisfied only by the in-app **Connect IBKR** button.
- **Boot stays broker-free.** Keep `IBKR_AUTO_CONNECT=false`. A reboot/crash-restart must never
  auto-grab the single IBKR session (it would fight TradingView for the one allowed login).
- **Do not boot the backend** (no `uvicorn`, no `start_dashboard.bat`) — the lifespan handler starts the
  scheduler and would let a connect path touch the broker. *Importing* `main` for a verification check is
  fine (it does not run lifespan).
- **Do not install/register** the NSSM service or OS scheduled tasks — those need elevation; hand the
  user the command instead.

## 🧮 Engine rules (the screener's prime directive)
- **Read [`docs/strategy_v2.md`](docs/strategy_v2.md) BEFORE touching any chart-reading algorithm code**
  (`engine_alpha/structure/`, `engine_alpha/scoring/`, or their detection/scoring knobs in `config/settings.py`) — its
  Reading Model section is the source of truth for *how Chrollo understands a chart*, not just a mirror
  of the code. **Update it in the same change** when behavior moves; doc/engine drift is a defect.
- **structure measures, scoring judges, pipeline coordinates.** `engine_alpha/structure/` reports facts and never
  assigns points. `engine_alpha/scoring/` turns facts into points and never reads a chart.
- **To change a factor's *weight*, edit `config/settings.py`** (`SCORE_*` / `TIER_*`) — never the
  measurement code.
- **Do not change scoring weights or tier thresholds without being asked.** New signals are added
  **measure-first**: as never-gated, never-penalizing bonus sub-scores, with the raw value archived;
  thresholds are only recalibrated later against the live archive — not at add time.
- The prime directive is **accurate detection of visually tight structure**. When in doubt, favor
  structural correctness over catching more names.

## Tech stack
- **Engine:** Python (pandas, numpy, scipy, yfinance, ib_async, APScheduler).
- **Backend:** FastAPI + Uvicorn, SQLAlchemy + SQLite (WAL mode, `busy_timeout=30000`).
- **Frontend:** React 19 + Vite, lightweight-charts + recharts. Plain JS/JSX (no TypeScript).
- **Runtime:** local, Windows, localhost-only; production = always-on NSSM service `ChrolloDashboard`.

## Setup, run, verify (exact commands)
```powershell
.\setup.bat                              # one-time: install deps + build frontend
python run_screener.py                   # one CLI scan → output/screener_data.json → archive
python -m core.archive.forward_returns   # backfill outcomes (--min-age N, --force)
python -m core.archive.analyze           # winner-fingerprint report card
npm --prefix webapp\frontend run build   # build the React app
npm --prefix webapp\frontend run lint    # eslint
.\update_dashboard.bat                   # USER runs this: rebuild frontend + restart service (1 UAC)
```
- **Verification an agent may run:** `python -m py_compile <file>` on touched backend files;
  `npm --prefix webapp\frontend run build`; importing `main` in a subprocess to confirm routes register.
- **Loading code changes is the user's job** — tell them to run `update_dashboard.bat`; do not start the
  service yourself.

## Repository layout
- `engine_alpha/structure/` — geometry: box/LPS detection, contractions, ADR (no opinion).
- `engine_alpha/scoring/` — `score_setup`, `calculate_tier` (opinion; weights live in `config/settings.py`).
- `core/pipeline/` — conductor: `data.py`, `screener.py`, `scan_job.py`.
- `core/archive/` — `writer.py`, `forward_returns.py`, `analyze.py`, `seed.py`, `purge.py`.
- `webapp/backend/` — `main.py`, `routers/`, `services/` (`scan_runner`, `scheduler`, `scan_status`,
  `scan_watchdog`, `health`), `ibkr/`, `config.py`, `database.py`.
- `webapp/frontend/src/` — `components/`, `hooks/`, `api.js`, `App.jsx`.

## Coding style
- Prefer the simplest working solution. Minimal, explicit, readable, maintainable code.
- Keep functions small; use descriptive names; avoid deep nesting and clever abstractions.
- No speculative features, no abstractions for single-use code, no "configurability" that wasn't asked
  for, no error handling for impossible scenarios. If 200 lines could be 50, rewrite it.
- Treat 200 lines as a cohesion check, not a blind split rule. Going over is acceptable when a file
  still has one clear responsibility and is simpler to read as one unit. Split files when they have
  multiple reasons to change, mixed responsibilities, reusable/testable logic, or rising cognitive load.
- Match the surrounding style even if you'd do it differently.

## Surgical changes
- Touch only what the task requires. Don't refactor, reformat, or "improve" adjacent code.
- Keep diffs small and targeted. If you notice unrelated dead code, **mention it — don't delete it**.
- Clean up only the imports/variables your own change orphaned.

## Backend rules
- Layered structure: `routers/` (HTTP) → `services/` (logic) → models/db. Keep routers thin.
- Route handlers are sync `def` and run in FastAPI's threadpool — **this is intentional**; do not
  "fix" them to `async`. Do not block on long work in a request; offload heavy jobs to a subprocess
  or background thread under `SCAN_LOCK` (see `services/scan_runner.py`).
- The scan runs as a UTF-8-forced subprocess (`PYTHONUTF8`/`PYTHONIOENCODING`) — keep that.
- The scheduler timezone is **`America/New_York`** by design (scan after the US close); never change it to
  local time.
- Replace `print` with `logging.getLogger("chrollo.*")`.

## Frontend rules
- One main component per file; keep components focused. Split large UI into smaller pieces.
- **Null-safety is mandatory** for any rendered number — never call `.toFixed()` on possibly-null data.
  Reuse the established guard: `const fx = (v, d) => (v == null || !Number.isFinite(Number(v))) ? '—' :
  Number(v).toFixed(d);`.
- Every `EventSource`/SSE stream must be stored in a ref and `close()`d on unmount (see `hooks/useSSE.js`).
- Every `fetch` needs a `.catch` / try-catch so a backend hiccup logs instead of hanging the UI.
- Tag-chip / score-pill caps mirror `config/settings.py` and live in one place
  (`components/setupScoreMath.js`) — keep them in sync, don't duplicate.

## Libraries
- Introduce a library only when it makes the code meaningfully faster, cleaner, or improves UX. Before
  adding one, briefly weigh 2–3 options and pick the lowest-complexity fit.

## Workflow & communication
- **State assumptions explicitly; if uncertain, ask. Don't pick silently between interpretations.**
- State the plan briefly before larger changes. Flag anything that feels overcomplicated and offer the
  simpler option.
- **Commit/push only when asked.** If on the default branch, create a feature branch first.
- End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
