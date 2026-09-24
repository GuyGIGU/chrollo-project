# AGENTS.md

Operating manual for AI coding agents working in Chrollo. Read this first, then
[`README.md`](README.md). For algorithm questions the single source of truth is
[`docs/strategy_alpha.md`](docs/strategy_alpha.md); for the engine layout see [`core/MAP.md`](core/MAP.md);
for the whole repo's layout and import rules see [`docs/architecture.md`](docs/architecture.md); for
what is live, dark and next see [`docs/current_state.md`](docs/current_state.md).

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
  (`engine_alpha/structure/`, `engine_alpha/scoring/`, or their knobs: detection in `config/engine.py`,
  scoring in `config/scoring.py`) — its
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
- **To change a factor's *weight*, edit `config/scoring.py`** (`SCORE_*` / `TIER_*`) — never the
  measurement code. Runtime reads and scoped overrides stay on `config.settings`
  (`from config import settings`): it re-exports every default by name and is the one namespace
  overrides patch, so never import `config.engine` / `config.scoring` directly. A new setting goes
  in its domain file **and** in `config/settings.py`'s import list.
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
documented trap (two colliding 3.14 installs; `docs/deploy.md` §2). A linked worktree has no `.venv`
of its own; use the main checkout's: `& "$(git rev-parse --git-common-dir)\..\.venv\Scripts\python.exe"`.
```powershell
.\setup.bat                                                  # one-time: install deps + build frontend
.\.venv\Scripts\python.exe run_screener.py                   # one CLI scan → output/screener_data.json → archive
.\.venv\Scripts\python.exe -m core.archive.forward_returns   # backfill outcomes (--min-age N, --force)
.\.venv\Scripts\python.exe -m core.archive.analyze           # winner-fingerprint report card
npm --prefix webapp\frontend run build                       # build the React app (a worktree only; see below)
npm --prefix webapp\frontend run lint                        # eslint
.\.venv\Scripts\python.exe -m tools.audits.pointer_audit --report   # evidence pointers still resolve (--report adds the advisory)
.\.venv\Scripts\python.exe -m tools.regression.marks_corpus --check      # the operator-marks ratchet (~2 min): fails on a lost pinned hit, and as STALE once the operator redraws (refresh: tools.calibration.guided_list_export, then --build-fixture)
.\.venv\Scripts\python.exe -m tools.regression.reader_pin --check        # per-event reader-vocabulary pin (~5s; zero-diff is the fold acceptance)
.\update_dashboard.bat                                       # USER runs this: rebuild frontend + restart service (1 UAC; refuses while a scan is running)
```
- **Verification an agent may run:** `.\.venv\Scripts\python.exe -m py_compile <file>` on touched
  backend files; `npm --prefix webapp\frontend run build` **in a worktree only**. The live service
  serves `webapp\frontend\dist` from the main checkout, and a bare build there swaps its bundle with
  no rollback copy (`update_dashboard.bat` keeps one). To build from the main checkout, use Git Bash:
  `npm --prefix webapp/frontend run build -- --outDir "$TEMP/chrollo-build" --emptyOutDir`. Also
  importing `main` in a subprocess to confirm routes register — **but point the DB somewhere throwaway first**:
  ```powershell
  $env:CHROLLO_DB_PATH = "$env:TEMP\chrollo-verify.db"   # then import main
  ```
  `import main` runs `initialize_database()` at *import* scope: `create_all`, the ALTER list, four
  rebuild migrations that copy a 44 MB backup, and `_reconcile_orphaned_runs`, which rewrites any
  `scan_runs` row still `running` to `failed` — that string is in the operator's archive because a
  bare `pytest` used to do exactly this (council review 2026-09-07). `pytest` now sets the same
  variable for itself in `tests/conftest.py`; the **service must never set it** (`docs/deploy.md` §2).
- **After MOVING, ARCHIVING or DELETING any file, run `tools.audits.pointer_audit --check`.** A citation
  rots when some *other* file moves, so the commit that breaks it never touches the file that
  carries it — no diff review can catch this. It is also in pytest, so a normal run covers it; the
  explicit call is for when you are mid-sweep and want the answer before committing.
- **Loading code changes is the user's job** — tell them to run `update_dashboard.bat`; do not start the
  service yourself.

## Repository layout
Full map, import direction and compatibility paths: [`docs/architecture.md`](docs/architecture.md).
- `engine_alpha/` — the reading engine, a leaf (never imports `core.pipeline`, `core.archive`,
  `webapp` or `tools`). `structure/{box,phases,lps,events,narrative,metrics,context}/` measure (no
  opinion); `scoring/` judges (`scoring.py`: `score_setup`, `compose_ta_grade`,
  `calculate_structure_tier`; `taxonomy.py`; `tags.py` chip verdicts); `evaluation.py` is the one
  per-ticker chain; `freeze/manifest.py` is the engine config hash.
- `core/pipeline/` — conductor: `data.py` (public data door), `market_data/`, `universe/`, `context/`,
  `screening/` (`screener.py` `run_screener`, `scan_job.py` the nightly job, `dashboard.py` +
  `terminal.py` payload writers), `telemetry/`.
- `core/archive/` — `writer.py`, `forward_returns.py`, `analyze.py`, `seed.py`, `purge.py`, `episodes.py`,
  `outcomes.py`, `db_path.py`. `core/backtest/` is production (the edge tile imports it);
  `core/regime/` and `core/fundamentals/` are dark lanes.
- `config/` — defaults by domain (`engine.py`, `scoring.py`, `enrichment.py`, `archive.py`,
  `market_data.py`, `market_context.py`, `runtime.py`); `settings.py` is the one namespace.
- `webapp/backend/` — `main.py`; `domains/{archive,calibration,ibkr,market_data,portfolio,screener,
  trading,watchlist}/`; `app/` (startup, lifespan, migrations); `services/` (the scan lifecycle);
  `middleware/`; `database.py`; `broker_config.py`.
- `webapp/frontend/src/` — `app/` (routes, shell, appearance), `features/<feature>/`, `shared/`,
  `api/base.js`.
- `tools/{regression,audits,calibration,research,maintenance,ops}/` (`python -m tools.<category>.<name>`),
  `tests/<category>/`, `research/` (evidence, no importable code), `output/` (runtime files only).

## Before creating a file
Answer these, then use the "Where do I put this?" table in
[`docs/architecture.md`](docs/architecture.md#11-where-new-code-belongs):
1. What domain owns it?
2. Is it production, research, test, or maintenance code?
3. Does an existing module already own the responsibility?
4. Is it genuinely reusable?
5. Does its name describe its responsibility?
6. Will another developer know where to find related code?

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
- Layered structure: `domains/<domain>/router.py` (HTTP, thin) → the domain's own modules (logic,
  models, schemas) → `database.py`. `app/` owns startup, the lifespan and migrations
  (`app/migrations/`, called from `app/startup.initialize_database`); `services/` owns the scan
  lifecycle that crosses domains (`scan_runner`, `scheduler`, `scan_status`, `scan_watchdog`,
  `health`, `scan_diagnosis`).
- Route handlers are sync `def` and run in FastAPI's threadpool — **this is intentional**; do not
  "fix" them to `async`. Do not block on long work in a request; offload heavy jobs to a subprocess
  or background thread under `SCAN_LOCK` (see `services/scan_runner.py`).
- The boot path stays engine-free: import `engine_alpha` only inside the function that needs it.
- The scan runs as a UTF-8-forced subprocess (`PYTHONUTF8`/`PYTHONIOENCODING`) — keep that.
- The scheduler timezone is **`America/New_York`** by design (scan after the US close); never change it to
  local time.
- Replace `print` with `logging.getLogger("chrollo.*")`.

## Frontend rules
- One main component per file; keep components focused. Split large UI into smaller pieces.
- A screen's code lives in its `features/<feature>/` folder (`components/`, `hooks/`, `model/`,
  `presentation/`). `shared/` holds only code that unrelated features use; move something there
  when the second feature needs it, not before.
- **Null-safety is mandatory** for any rendered number — never call `.toFixed()` on possibly-null data.
  Reuse the established guard: `fx` from `src/shared/formatting/format.js` — the app's ONE null guard
  (null/NaN → em-dash). Never re-declare it inline; the old inline one-liner this rule used to quote
  minted drifting copies (council review 2026-08-17).
- Every `EventSource`/SSE stream must be stored in a ref and `close()`d on unmount (see `features/portfolio/hooks/useSSE.js`).
- Every `fetch` needs a `.catch` / try-catch so a backend hiccup logs instead of hanging the UI.
- **The wire carries verdicts, never rules (conventions.md EC-28):** no scoring cap, threshold,
  fire-rule, or chapter-membership may be re-declared in frontend JS — every judgment crosses the
  wire already resolved by the engine; the frontend keeps only presentational lookups (labels,
  tones, ordering, copy). The legacy score path RETIRED 2026-08-23 (`setupScoreMath.js` and the
  client-side fire rules are gone); `shared/setup/tagCatalog.js` carries the presentational chip
  catalog — labels/groups/tones only, never a threshold.

## Libraries
- Introduce a library only when it makes the code meaningfully faster, cleaner, or improves UX. Before
  adding one, briefly weigh 2–3 options and pick the lowest-complexity fit.

## Workflow & communication
- **State assumptions explicitly; if uncertain, ask. Don't pick silently between interpretations.**
- State the plan briefly before larger changes. Flag anything that feels overcomplicated and offer the
  simpler option.
- **Commit/push only when asked.** If on the default branch, create a feature branch first.
- End commit messages with a `Co-Authored-By:` line naming the **latest Claude Opus release**:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` as of 2026-09. When a newer Opus ships, use
  its name; never pin an older version.
