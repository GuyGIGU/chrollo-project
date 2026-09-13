# AGENTS.md

Operating manual for AI coding agents working in Chrollo. Read this first, then
[`README.md`](README.md). For algorithm questions the single source of truth is
[`docs/strategy_alpha.md`](docs/strategy_alpha.md); for the engine layout see [`core/MAP.md`](core/MAP.md).

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
  fine (it does not run lifespan) — but it **does** run the DB migrations, so set `CHROLLO_DB_PATH` first
  (see *Verification an agent may run*).
- **Do not install/register** the NSSM service or OS scheduled tasks — those need elevation; hand the
  user the command instead.

## 🧮 Engine rules (the screener's prime directive)
- **Read [`docs/strategy_alpha.md`](docs/strategy_alpha.md) BEFORE touching any chart-reading algorithm code**
  (`engine_alpha/structure/`, `engine_alpha/scoring/`, or their detection/scoring knobs in `config/settings.py`) — its
  Reading Model section is the source of truth for *how Chrollo understands a chart*, not just a mirror
  of the code. **Update it in the same change** when behavior moves; doc/engine drift is a defect.
- The engine docs are split by lifecycle, and each has one job:
  **[`strategy_alpha.md`](docs/strategy_alpha.md)** = theory (what a good setup IS; deliberately names no
  files or functions so it cannot rot) · **[`engine_reference.md`](docs/engine_reference.md)** = how it is
  built and why it took that shape · **[`decisions.md`](docs/decisions.md)** = operator rulings + the
  **Tested-DEAD** registry, append-only.
- **Check `decisions.md` before proposing any new knob, threshold, or heuristic.** This engine has a real
  graveyard — overshoot-magnitude tests, `root.kind` keying, shelf-R, HTF scoring — and re-proposing a dead
  lever costs a full A/B cycle. Measured 2026-07-27: four designs falsified in one session, two of them
  already documented and still missed.
- **Wyckoff is a source of ideas, not a specification** — and so are Minervini and O'Neil: before
  arguing from *their* books (Power Play, VCP, CANSLIM, trend template, RS), read
  [`docs/minervini_oneil_canon.md`](docs/minervini_oneil_canon.md), the growth-canon concordance.
  Before arguing any change from Wyckoff
  doctrine, read [`docs/wyckoff_canon.md`](docs/wyckoff_canon.md) — it records what Chrollo took,
  adapted, and *deliberately left* (PS, ST, the distribution mirror, effort-vs-result), the words
  he uses differently here (LPS, upthrust, markup, `sos_reclaim`, Phase C/D), the jargon
  deliberately RETIRED (creek, ice, BU/BUEC, Mini-BC — describe the event plainly instead), and
  the levers already tested-DEAD. Textbook fidelity is not a success criterion; **never open a change whose whole
  justification is "canon has this and we don't."**
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
Interpreter: the repo venv, `.\.venv\Scripts\python.exe` — this machine's bare `python` is a
documented trap (two colliding 3.14 installs; `docs/deploy.md` §2).
```powershell
.\setup.bat                                                  # one-time: install deps + build frontend
.\.venv\Scripts\python.exe run_screener.py                   # one CLI scan → output/screener_data.json → archive
.\.venv\Scripts\python.exe -m core.archive.forward_returns   # backfill outcomes (--min-age N, --force)
.\.venv\Scripts\python.exe -m core.archive.analyze           # winner-fingerprint report card
npm --prefix webapp\frontend run build                       # build the React app
npm --prefix webapp\frontend run lint                        # eslint
.\.venv\Scripts\python.exe -m tools.pointer_audit --report   # evidence pointers still resolve (--report adds the advisory)
.\.venv\Scripts\python.exe -m tools.marks_corpus --check      # the sealed must-fire ratchet (~1.5 min; also prints the graduation-drift advisory)
.\.venv\Scripts\python.exe -m tools.negative_corpus --check   # labeled junk must NOT fire on any day of the 10-day fired window (~1.5 min: 17 cases x 10 days)
.\.venv\Scripts\python.exe -m tools.shadow_diff --check       # fleet canonical output + first/last fire day on the same window (~2.5 min: 37 tickers x 10 days)
.\.venv\Scripts\python.exe -m tools.reader_pin --check        # per-event reader-vocabulary pin (~5s; zero-diff is the fold acceptance)
.\update_dashboard.bat                                       # USER runs this: rebuild frontend + restart service (1 UAC)
```
- **Verification an agent may run:** `.\.venv\Scripts\python.exe -m py_compile <file>` on touched
  backend files; `npm --prefix webapp\frontend run build`; importing `main` in a subprocess to
  confirm routes register — **but point the DB somewhere throwaway first**:
  ```powershell
  $env:CHROLLO_DB_PATH = "$env:TEMP\chrollo-verify.db"   # then import main
  ```
  `import main` runs `initialize_database()` at *import* scope: `create_all`, the ALTER list, three
  rebuild migrations that copy a 44 MB backup, and `_reconcile_orphaned_runs`, which rewrites any
  `scan_runs` row still `running` to `failed` — that string is in the operator's archive because a
  bare `pytest` used to do exactly this (council review 2026-09-07). `pytest` now sets the same
  variable for itself in `tests/conftest.py`; the **service must never set it** (`docs/deploy.md` §2).
- **After MOVING, ARCHIVING or DELETING any file, run `tools.pointer_audit --check`.** A citation
  rots when some *other* file moves, so the commit that breaks it never touches the file that
  carries it — no diff review can catch this. It is also in pytest, so a normal run covers it; the
  explicit call is for when you are mid-sweep and want the answer before committing.
- **Loading code changes is the user's job** — tell them to run `update_dashboard.bat`; do not start the
  service yourself.

## Repository layout
- `engine_alpha/structure/` — geometry: box/LPS detection, contractions, ADR (no opinion).
- `engine_alpha/scoring/` — `score_setup`, `calculate_tier` (opinion; weights live in `config/settings.py`).
- `core/pipeline/` — conductor: `data.py`, `screener.py`, `scan_job.py`.
- `core/archive/` — `writer.py`, `forward_returns.py`, `analyze.py`, `seed.py`, `purge.py`.
- `webapp/backend/` — `main.py`, `routers/`, `services/` (`scan_runner`, `scheduler`, `scan_status`,
  `scan_watchdog`, `health`), `ibkr/`, `broker_config.py`, `database.py`.
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
  Reuse the established guard: `import { fx } from 'utils/format.js'` — the app's ONE null guard
  (null/NaN → em-dash). Never re-declare it inline; the old inline one-liner this rule used to quote
  minted drifting copies (council review 2026-08-17).
- Every `EventSource`/SSE stream must be stored in a ref and `close()`d on unmount (see `hooks/useSSE.js`).
- Every `fetch` needs a `.catch` / try-catch so a backend hiccup logs instead of hanging the UI.
- **The wire carries verdicts, never rules (conventions.md EC-28):** no scoring cap, threshold,
  fire-rule, or chapter-membership may be re-declared in frontend JS — every judgment crosses the
  wire already resolved by the engine; the frontend keeps only presentational lookups (labels,
  tones, ordering, copy). The legacy score path RETIRED 2026-08-23 (`setupScoreMath.js` and the
  client-side fire rules are gone); `components/tagCatalog.js` carries the presentational chip
  catalog — labels/groups/tones only, never a threshold.

## Libraries
- Introduce a library only when it makes the code meaningfully faster, cleaner, or improves UX. Before
  adding one, briefly weigh 2–3 options and pick the lowest-complexity fit.

## Workflow & communication
- **State assumptions explicitly; if uncertain, ask. Don't pick silently between interpretations.**
- State the plan briefly before larger changes. Flag anything that feels overcomplicated and offer the
  simpler option.
- **Commit/push only when asked.** If on the default branch, create a feature branch first.
- End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
