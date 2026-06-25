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
| `IBKR_PORT`           | auto          | TWS: 7497/7496; Gateway: 4002/4001             |
| `IBKR_CLIENT_ID`      | `137`         | Must be unique across connected clients        |
| `IBKR_MODE`           | `live`        | Set to `paper` only when using a paper account |
| `IBKR_AUTO_CONNECT`   | `false`       | Keep broker-free at boot; connect from the UI  |
| `ALPACA_KEY_ID`       | _(unset)_     | Alpaca Market Data API key. If set together with `ALPACA_SECRET_KEY`, the `/live-prices/` endpoint serves real-time IEX quotes via Alpaca's batch endpoint instead of polling yfinance one-symbol-at-a-time. Missing keys → silently falls back to yfinance. |
| `ALPACA_SECRET_KEY`   | _(unset)_     | Alpaca Market Data API secret (paired with `ALPACA_KEY_ID`). Free signup at [alpaca.markets](https://alpaca.markets); the Market Data v2 endpoint is included on the free tier (real-time IEX, 200 req/min). |

When `IBKR_MODE=live`, the sidebar shows a red **LIVE** badge. Default is live because Chrollo reads the real portfolio, but boot still stays broker-free: live connections require the dashboard's per-click confirmation before the backend starts IBKR.

## Running

```bash
cd webapp/backend
uvicorn main:app --reload --port 8000
```

Visit [http://localhost:8000/ibkr/status](http://localhost:8000/ibkr/status) — if `connected: true`, everything is wired.

## Database migrations

`trade_logs` schema evolves additively. Two migration paths exist:

- **Automatic**: on startup, `main.py` runs a list of `ALTER TABLE … ADD COLUMN` statements wrapped in try/except so existing databases upgrade in place (see `_MIGRATIONS` in [main.py](main.py)).
- **One-off**: [migrate.py](migrate.py) for standalone scripts (currently adds `target_r`).

New tables (`Execution`, `Tag`, `TradeTag`, `TradePlan`, `TradeNote`, `TradeAttachment`) are created via `models.Base.metadata.create_all(...)` on first run.

To start from a fresh DB: delete `trading_journal.db` and restart the backend.

## Live-mode guardrail

Chrollo is read-only against IBKR. Do not add order-placement, order-modification, or money-movement endpoints to this backend. The red LIVE badge is only an operator-facing reminder that portfolio snapshots are coming from a real-money account.

## Logging

Every HTTP request is tagged with an 8-char `x-request-id` (round-tripped as a response header). Logs look like:

```
2026-04-19 12:00:01 INFO [chrollo.request] rid=a1b2c3d4 POST /trades/ -> 200 (12.3 ms)
```

Clients can pass their own `x-request-id` header to correlate frontend actions with backend logs.
