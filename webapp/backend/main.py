"""
Chrollo API — FastAPI backend for Trading Journal & Wyckoff Screener.
"""
import os
import sys
import json
import time
import uuid
import logging
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

import models
import archive_models
import schemas
import config
from config import settings
from database import engine, get_db
from ibkr import get_ibkr_service
from routers import portfolio as portfolio_router
from routers import tags as tags_router
from routers import analytics as analytics_router
from routers import journal as journal_router
from routers import archive as archive_router
from services import auto_import

# ── Bootstrap ────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)
archive_models.SetupArchive.metadata.create_all(bind=engine)

# Additive migrations: new columns on trade_logs. Each ALTER is wrapped so existing DBs
# upgrade non-destructively. SQLite ignores IF NOT EXISTS on ALTER TABLE, hence try/except.
from sqlalchemy import text as _text

_MIGRATIONS = [
    "ALTER TABLE trade_logs ADD COLUMN actions_json TEXT",
    "ALTER TABLE trade_logs ADD COLUMN source VARCHAR DEFAULT 'manual'",
    "ALTER TABLE trade_logs ADD COLUMN ibkr_account VARCHAR",
    "ALTER TABLE trade_logs ADD COLUMN perm_id VARCHAR",
    "ALTER TABLE trade_logs ADD COLUMN planned_stop FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN r_anchor INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN s_anchor INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN score_uptrend_bonus FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN mfe_20d_date VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN mae_20d_date VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN r_multiple_20d FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN r_multiple_60d FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN trigger_volume_ratio FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN rs_vs_sector_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN dist_52w_high_pct FLOAT",
]
_mig_log = logging.getLogger("chrollo.migrate")
with engine.connect() as _conn:
    for _stmt in _MIGRATIONS:
        try:
            _conn.execute(_text(_stmt))
            _conn.commit()
            _mig_log.info("applied: %s", _stmt)
        except Exception as _e:
            msg = str(_e).lower()
            # SQLite raises "duplicate column name" when the column already exists —
            # that's the expected idempotent path. Anything else is a real problem.
            if "duplicate column" in msg or "already exists" in msg:
                continue
            _mig_log.warning("migration skipped (%s): %s", _e.__class__.__name__, _stmt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the IBKR service + auto-import writer around the app lifecycle."""
    auto_import.start_writer()
    svc = get_ibkr_service()
    svc.add_execution_listener(auto_import.submit_execution)
    if settings.ibkr_auto_connect:
        try:
            svc.start()
        except Exception:
            logging.exception("Failed to start IBKR service")
    try:
        yield
    finally:
        try:
            svc.stop()
        except Exception:
            logging.exception("Failed to stop IBKR service")
        try:
            auto_import.stop_writer()
        except Exception:
            logging.exception("Failed to stop auto-import writer")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
_req_log = logging.getLogger("chrollo.request")


class RequestIDMiddleware:
    """Pure-ASGI middleware: tags every HTTP request with a short ID + logs timing.

    Implemented at the ASGI layer (not BaseHTTPMiddleware) so StreamingResponse
    bodies aren't buffered — critical for the SSE endpoints (/stream/portfolio,
    /run-scan-stream, /stream/positions-pnl).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        rid = headers.get("x-request-id") or uuid.uuid4().hex[:8]
        scope.setdefault("state", {})["request_id"] = rid

        start = time.perf_counter()
        status_code = {"v": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code["v"] = message["status"]
                hdrs = list(message.get("headers", []))
                hdrs.append((b"x-request-id", rid.encode("latin-1")))
                message["headers"] = hdrs
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _req_log.exception(
                "rid=%s %s %s -> 500 (%.1f ms)",
                rid, scope.get("method"), scope.get("path"), elapsed_ms,
            )
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        _req_log.info(
            "rid=%s %s %s -> %d (%.1f ms)",
            rid, scope.get("method"), scope.get("path"), status_code["v"], elapsed_ms,
        )


app = FastAPI(title="Chrollo API", lifespan=lifespan)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

app.include_router(portfolio_router.router)
app.include_router(tags_router.router)
app.include_router(analytics_router.router)
app.include_router(journal_router.router)
app.include_router(archive_router.router)

# Resolve the project root once at startup
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCREENER_JSON = os.path.join(_ROOT_DIR, "output", "screener_data.json")
_SCREENER_SCRIPT = os.path.join(_ROOT_DIR, "run_screener.py")


# ── Health Check ─────────────────────────────────────────────────
@app.get("/")
def read_root():
    return {"status": "ok", "app": "Chrollo API"}


# ── IBKR Status ──────────────────────────────────────────────────
@app.get("/ibkr/status")
def ibkr_status():
    svc = get_ibkr_service()
    snap = svc.snapshot()
    return {
        "available": svc.is_available(),
        "connected": snap["connected"],
        "mode": snap["mode"],
        "client": snap["client"],
        "host": snap["host"],
        "port": snap["port"],
        "client_id": snap["client_id"],
        "last_update": snap["last_update"],
        "last_error": snap["last_error"],
        "stale": snap.get("stale", False),
        "daily_restart": snap.get("daily_restart", False),
        "session_competition": snap.get("session_competition", False),
        "paused": svc.is_paused(),
    }


from pydantic import BaseModel as _PydBaseModel


class _ModePayload(_PydBaseModel):
    mode: str
    confirm: bool = False


class _ClientPayload(_PydBaseModel):
    client: str


@app.post("/ibkr/mode")
def set_ibkr_mode(payload: _ModePayload):
    """Flip between paper (port 7497) and live (port 7496) at runtime.

    Live-mode switch requires ``confirm=true`` in the body — a small guardrail
    against an accidental UI click connecting you to real money.
    """
    mode = payload.mode.strip().lower()
    if mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="mode must be 'paper' or 'live'")
    if mode == "live" and not payload.confirm:
        raise HTTPException(status_code=400, detail="switching to live requires confirm=true")

    svc = get_ibkr_service()
    try:
        svc.stop()
    except Exception:
        logging.exception("Failed to stop IBKR before mode switch")

    config.set_mode(mode)
    svc.apply_settings()

    try:
        svc.start()
    except Exception:
        logging.exception("Failed to start IBKR after mode switch")

    snap = svc.snapshot()
    return {
        "mode": snap["mode"],
        "port": snap["port"],
        "connected": snap["connected"],
    }


@app.post("/ibkr/client")
def set_ibkr_client(payload: _ClientPayload):
    """Switch between TWS (7497/7496) and IB Gateway (4002/4001) at runtime."""
    client = payload.client.strip().lower()
    if client not in ("tws", "gateway"):
        raise HTTPException(status_code=400, detail="client must be 'tws' or 'gateway'")

    svc = get_ibkr_service()
    try:
        svc.stop()
    except Exception:
        logging.exception("Failed to stop IBKR before client switch")

    config.set_client(client)
    svc.apply_settings()

    try:
        svc.start()
    except Exception:
        logging.exception("Failed to start IBKR after client switch")

    snap = svc.snapshot()
    return {
        "client": snap["client"],
        "mode": snap["mode"],
        "port": snap["port"],
        "connected": snap["connected"],
    }


@app.post("/ibkr/reconnect")
def ibkr_reconnect():
    """Manually resume IBKR connection after session competition pause.

    When another platform (e.g. TradingView) kicks Chrollo off the IBKR
    session, auto-reconnect pauses to avoid an infinite fight. This endpoint
    lets the user resume when TradingView is done.
    """
    svc = get_ibkr_service()
    svc.resume()
    try:
        svc.start()
    except Exception:
        logging.exception("Failed to start IBKR after manual reconnect")
    snap = svc.snapshot()
    return {
        "connected": snap["connected"],
        "session_competition": snap.get("session_competition", False),
        "paused": svc.is_paused(),
    }


# ── Trade CRUD ───────────────────────────────────────────────────
@app.get("/trades/", response_model=List[schemas.TradeLog])
def read_trades(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.TradeLog).offset(skip).limit(limit).all()


@app.post("/trades/", response_model=schemas.TradeLog)
def create_trade(trade: schemas.TradeLogCreate, db: Session = Depends(get_db)):
    db_trade = models.TradeLog(**trade.model_dump())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade

@app.put("/trades/{trade_id}", response_model=schemas.TradeLog)
def update_trade(trade_id: int, trade_update: schemas.TradeLogUpdate, db: Session = Depends(get_db)):
    db_trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not db_trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    update_data = trade_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_trade, key, value)
        
    db.commit()
    db.refresh(db_trade)
    return db_trade

@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    db_trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not db_trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    db.delete(db_trade)
    db.commit()
    # Cascade-delete on-disk attachment files (ORM cascade only removes rows).
    journal_router.wipe_trade_uploads(trade_id)
    return {"status": "Trade deleted successfully"}


# ── Position Calculator ──────────────────────────────────────────
@app.post("/calculate-position/")
def calculate_position(risk_amount: float, entry_price: float, stop_price: float, direction: str = "L"):
    """Calculate shares from risk amount and stop distance."""
    if entry_price <= 0 or stop_price <= 0 or risk_amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid inputs. Must be positive.")

    stop_distance = abs(entry_price - stop_price)
    if stop_distance == 0:
        raise HTTPException(status_code=400, detail="Entry and Stop price cannot be the same.")

    shares = int(risk_amount / stop_distance)
    return {
        "shares": shares,
        "stop_distance": round(stop_distance, 4),
        "position_size": round(shares * entry_price, 2),
    }


# ── Journal Stats ────────────────────────────────────────────────
@app.get("/journal-stats/")
def get_journal_stats(db: Session = Depends(get_db)):
    """Calculate journal performance metrics from all logged trades."""
    trades = db.query(models.TradeLog).all()

    empty_stats = {
        "total_pnl": 0, "win_rate": 0, "profit_factor": 0,
        "r_multiple_total": 0, "avg_win": 0, "avg_loss": 0,
        "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
    }

    if not trades:
        return empty_stats

    winners = [t for t in trades if t.pnl is not None and t.pnl > 0]
    losers = [t for t in trades if t.pnl is not None and t.pnl <= 0]

    total_wins = sum(t.pnl for t in winners)
    total_losses = abs(sum(t.pnl for t in losers))

    avg_win = total_wins / len(winners) if winners else 0
    avg_loss = total_losses / len(losers) if losers else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else (total_wins if total_wins > 0 else 0)
    total_pnl = sum(t.pnl for t in trades if t.pnl is not None)

    # R-Multiple: sum of (pnl / initial_risk) across all trades
    r_multiple_total = 0
    for t in trades:
        if t.pnl is not None and t.entry_price > 0 and t.stop_loss > 0 and t.quantity > 0:
            risk_dlr = abs(t.entry_price - t.stop_loss) * t.quantity
            if risk_dlr > 0:
                r_multiple_total += t.pnl / risk_dlr

    return {
        "total_pnl": total_pnl,
        "win_rate": round(len(winners) / len(trades) * 100, 2),
        "profit_factor": round(profit_factor, 2),
        "r_multiple_total": round(r_multiple_total, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(-avg_loss, 2),
        "total_trades": len(trades),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
    }


# ── Screener Data ────────────────────────────────────────────────
# Cache the last-read mtime so we only re-parse the 2.6MB JSON when the file changes.
_screener_cache = {"mtime": 0, "data": None}


@app.get("/screener-data/")
def get_screener_data():
    """Serve screener_data.json with file-modification caching."""
    if not os.path.exists(_SCREENER_JSON):
        return {"ordered_tickers": [], "chart_data": {}}

    current_mtime = os.path.getmtime(_SCREENER_JSON)
    if _screener_cache["data"] is None or current_mtime != _screener_cache["mtime"]:
        with open(_SCREENER_JSON, "r", encoding="utf-8") as f:
            _screener_cache["data"] = json.load(f)
        _screener_cache["mtime"] = current_mtime

    return _screener_cache["data"]


from pydantic import BaseModel as _BaseModel
from services.earnings import get_next_earnings_batch as _earnings_batch, days_until as _days_until


class _EarningsBatchIn(_BaseModel):
    tickers: list[str]


@app.post("/screener-data/earnings")
def screener_earnings(payload: _EarningsBatchIn):
    """Bulk earnings-date lookup for visible screener tickers.

    Returns ``{ticker: {"date": YYYY-MM-DD | null, "days_until": int | null}}``.
    Cached server-side for 24h per ticker, so flipping pages on the screener
    grid is effectively free after the first call.
    """
    if not payload.tickers:
        return {}
    raw = _earnings_batch([t.upper().strip() for t in payload.tickers if t])
    return {
        t: {"date": d, "days_until": _days_until(d)}
        for t, d in raw.items()
    }


import yfinance as yf
from fastapi import Query

# ── Screener Stream ──────────────────────────────────────────────
@app.get("/run-scan-stream/")
def run_screener_scan_stream():
    """Trigger the screener pipeline and stream terminal output via SSE."""

    def execute_and_yield():
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            process = subprocess.Popen(
                [sys.executable, _SCREENER_SCRIPT],
                cwd=_ROOT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=flags,
            )

            for line in process.stdout:
                yield f"data: {line}\n\n"

            process.stdout.close()
            process.wait()

            # Invalidate the screener cache so the next GET picks up new data
            _screener_cache["mtime"] = 0
            _screener_cache["data"] = None

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: ERROR: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(execute_and_yield(), media_type="text/event-stream")

# ── Live Prices ──────────────────────────────────────────────────
@app.get("/live-prices/")
def get_live_prices(tickers: str = Query("")):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return {}
    
    prices = {}
    for t in ticker_list:
        try:
            ticker_obj = yf.Ticker(t)
            val = ticker_obj.fast_info.get('lastPrice') or ticker_obj.info.get('currentPrice')
            if val:
                prices[t] = round(float(val), 2)
        except Exception as e:
            print(f"Error fetching live price for {t}: {e}")
    return prices
