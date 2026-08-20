# Chrollo Backend — Setup

## TWS / IB Gateway configuration

Chrollo connects to Interactive Brokers over the TWS API (`ib_async`). Before starting the backend, enable the API in TWS (or IB Gateway):

1. **File → Global Configuration → API → Settings**
2. Check **"Enable ActiveX and Socket Clients"**
3. Keep **"Read-Only API"** checked. Chrollo is read-only and never places orders.
4. **Socket port**:
   - Paper: **7497** (TWS) / **4002** (Gateway)
   - Live:  **7496** (TWS) / **4001** (Gateway)
5. **Trusted IP Addresses**: add `127.0.0.1`
6. Uncheck **"Download open orders on connection"** if you see duplicate order events
7. Click **OK** and restart TWS

## Environment variables

| Variable              | Default       | Notes                                          |
|-----------------------|---------------|------------------------------------------------|
| `IBKR_HOST`           | `127.0.0.1`   | TWS host                                       |
| `IBKR_CLIENT`         | `gateway`     | `tws` or `gateway` — decides which port `auto` picks |
| `IBKR_PORT`           | auto          | TWS: 7497/7496; Gateway: 4002/4001. Set explicitly and the port is pinned — a later mode/client switch keeps it |
| `IBKR_CLIENT_ID`      | `137`         | Must be unique across connected clients        |
| `IBKR_MODE`           | `live`        | Set to `paper` only when using a paper account |
| `IBKR_AUTO_CONNECT`   | `false`       | Keep broker-free at boot; connect from the UI  |
| `ALPACA_KEY_ID`       | _(unset)_     | Alpaca Market Data API key. If set together with `ALPACA_SECRET_KEY`, the `/live-prices/` endpoint serves real-time IEX quotes via Alpaca's batch endpoint instead of polling yfinance one-symbol-at-a-time. Missing keys → silently falls back to yfinance. |
| `ALPACA_SECRET_KEY`   | _(unset)_     | Alpaca Market Data API secret (paired with `ALPACA_KEY_ID`). Free signup at [alpaca.markets](https://alpaca.markets); the Market Data v2 endpoint is included on the free tier (real-time IEX, 200 req/min). |

When `IBKR_MODE=live`, the app's top bar shows a red **LIVE** badge (the old vertical sidebar was replaced by the single global bar). Default is live because Chrollo reads the real portfolio, but boot still stays broker-free: `IBKRService.start()` ([ibkr/service.py](ibkr/service.py)) refuses a live start without a per-click confirmation, so the backend only reaches IBKR after **Connect IBKR** is clicked in the top bar.

## Running

Production is the always-on NSSM service `ChrolloDashboard` — one uvicorn process serving both the API and the built React app on `http://127.0.0.1:8000`. Install/update steps live in [../../docs/deploy.md](../../docs/deploy.md); the operator loads code changes with `update_dashboard.bat`.

`start_dashboard.bat` (repo root) is the manual launcher: it frees port 8000, then runs the same process with the working directory set to this folder. For a reload-on-edit run, from the repo root:

```powershell
cd webapp\backend
..\..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Use the repo venv interpreter, never a bare `python` / `uvicorn` — this machine has two colliding 3.14 installs (docs/deploy.md §2).

Visit [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) — `status: "ok"` means the db, last-scan, screener-data and scheduler checks all pass. IBKR is reported there but deliberately never degrades the status, because boot is broker-free: [http://127.0.0.1:8000/ibkr/status](http://127.0.0.1:8000/ibkr/status) reads `connected: false` until you click **Connect IBKR**.

## Database migrations

Every migration is automatic and runs at **import** of [main.py](main.py) — `initialize_database()` in [services/startup.py](services/startup.py) is called at module level, before the app object exists and before the lifespan handler starts the scheduler. It does six things, in this order:

1. `models.Base.metadata.create_all(...)` + `archive_models.SetupArchive.metadata.create_all(...)` — creates any missing table. Both modules declare against the one `Base` from [database.py](database.py), so between them this covers every model in [models.py](models.py) (`TradeLog`, `Execution`, `Tag`, `TradeTag`, `TradePlan`, `TradeNote`, `TradeAttachment`, `Watchlist`, `SetupReview`, `ReadVerdict`, `CalibrationMark`, `CalibrationMarkEvent`, `PortfolioSnapshotCache`) and in [archive_models.py](archive_models.py) (`SetupArchive`, `NearMissArchive`). `scan_runs` is the one table no model declares — it is hand-built by the `CREATE TABLE IF NOT EXISTS` at the head of `_MIGRATIONS`.
2. `_apply_migrations()` — the hand-written `_MIGRATIONS` list: mostly `ALTER TABLE … ADD COLUMN`, plus a few one-off `DROP COLUMN`s for retired columns. Each statement is wrapped in try/except and is idempotent — "duplicate column"/"already exists" (a re-run ADD) and "no such column" (a re-run DROP) both mean the end state already holds and are skipped quietly.
3. `migrate_universe_type(...)` — one-off table rebuild widening the `setup_archive` identity to `(ticker, scan_date, universe_type)`. Takes a file backup first; no-op once migrated.
4. `migrate_watchlist_ledger(...)` — one-off rebuild of `watchlist` from ticker-PK rows to the dated event ledger. Same backup-first pattern; no-op once migrated.
5. `_apply_model_add_columns(...)` — the model-derived ADD-only pass. It diffs each table listed in `_MIGRATED_ARCHIVE_MODELS` (`setup_archive`, `near_miss_archive`, `read_verdicts`) against its model and ADDs whatever the model declares and the DB lacks. **A new column on one of those models therefore needs no hand-written statement at all** — declare it on the model and it lands on the next boot. A new archive table must be registered in that tuple at birth, or its model-only columns silently never reach the live DB. ADD-only by design: a retirement is always an explicit `DROP COLUMN` in `_MIGRATIONS`, never inferred.
6. `_reconcile_orphaned_runs(...)` — flips any `scan_runs` row left `status='running'` by a hard kill to `failed`, so `latest_run()` reflects reality.

There is no standalone migration script. There used to be: `migrate.py` sat beside this file and carried the `trade_logs.target_r` ALTER. It was folded into `_MIGRATIONS` and deleted on 2026-08-20 (commit `680917c`) — a doc or comment still naming it is describing history, not a file you can run.

To start from a fresh DB: stop the backend, delete `trading_journal.db` **and its `-wal` / `-shm` siblings** (the DB runs in WAL mode), then restart. Note the archive tables live in this same file, so this discards the setup archive too.

## Live-mode guardrail

Chrollo is read-only against IBKR. Do not add order-placement, order-modification, or money-movement endpoints to this backend. The red LIVE badge is only an operator-facing reminder that portfolio snapshots are coming from a real-money account.

## Logging

Every HTTP request is tagged with an `x-request-id` — the client's own if it sent one, otherwise a generated 8-char id — round-tripped as a response header. Logs look like:

```
2026-04-19 12:00:01 INFO [chrollo.request] rid=a1b2c3d4 POST /trades/ -> 200 (12.3 ms)
```

Clients can pass their own `x-request-id` header to correlate frontend actions with backend logs.

Successful requests to the endpoints the frontend polls forever (`/live-prices`, `/scan-status`, `/health`, `/stream/`) log at DEBUG instead — see `_NOISY_PATH_PREFIXES` in [middleware/request_id.py](middleware/request_id.py). Anything 4xx/5xx stays at INFO regardless of path, so an error on a polled endpoint is still visible at the default level.
