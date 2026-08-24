"""
Chrollo API - FastAPI backend for Trading Journal & Wyckoff Screener.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT_DIR not in sys.path:
    sys.path.append(_ROOT_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from broker_config import settings
from ibkr import get_ibkr_service
from middleware.request_id import RequestIDMiddleware
from routers import analytics as analytics_router
from routers import archive as archive_router
from routers import calibration as calibration_router
from routers import candles as candles_router
from routers import engine_edge as engine_edge_router
from routers import ibkr as ibkr_router
from routers import journal as journal_router
from routers import market_data as market_data_router
from routers import portfolio as portfolio_router
from routers import portfolio_streams as portfolio_streams_router
from routers import prices as prices_router
from routers import screener as screener_router
from routers import tags as tags_router
from routers import trade_risk as trade_risk_router
from routers import trades as trades_router
from routers import watchlist as watchlist_router
from services import auto_import, scheduler
from services.frontend import mount_frontend_assets, serve_frontend_index
from services.health import build_health_report
from services.startup import initialize_database

# Split the streams so the NSSM *error* log actually means errors. A plain
# basicConfig() sends every level to stderr, which is why routine INFO chatter
# filled chrollo-service-error.log to 167 MB while the stdout log sat at
# 1.2 MB — the file you open when something breaks was 99% noise. INFO and
# below now go to stdout, WARNING and above to stderr.
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    handlers=[_stdout_handler, _stderr_handler],
    force=True,
)

initialize_database()

_SCREENER_JSON = os.path.join(_ROOT_DIR, "output", "screener_data.json")
_FRONTEND_DIST = os.path.join(_ROOT_DIR, "webapp", "frontend", "dist")
_FRONTEND_INDEX = os.path.join(_FRONTEND_DIST, "index.html")
_FRONTEND_ASSETS = os.path.join(_FRONTEND_DIST, "assets")

screener_router.configure_screener_routes(_SCREENER_JSON)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background services around the app lifecycle."""
    auto_import.start_writer()
    scheduler.start_scheduler()
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
        _stop_services(svc)


def _stop_services(svc) -> None:
    for label, stop in (
        ("IBKR service", svc.stop),
        ("auto-import writer", auto_import.stop_writer),
        ("scan scheduler", scheduler.stop_scheduler),
    ):
        try:
            stop()
        except Exception:
            logging.exception("Failed to stop %s", label)


app = FastAPI(title="Chrollo API", lifespan=lifespan)

app.add_middleware(RequestIDMiddleware)
# Host allowlist BEFORE the browser-enforced defenses: CORS and the same-app
# header only bind cross-origin pages, so a DNS-rebound page (its domain
# re-pointed at 127.0.0.1) would be SAME-origin with this always-on service
# and could read/write every route. A rebound page's requests carry the
# attacker's own hostname in Host — refused here. "testserver" is the
# FastAPI TestClient's default host; a browser can never send it.
# (Council review 2026-08-17, finding 7 — Hunt.)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "testserver"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

app.include_router(portfolio_router.router)
app.include_router(portfolio_streams_router.router)
app.include_router(market_data_router.router)
app.include_router(tags_router.router)
app.include_router(analytics_router.router)
app.include_router(engine_edge_router.router)
app.include_router(journal_router.router)
app.include_router(archive_router.router)
app.include_router(watchlist_router.router)
app.include_router(calibration_router.router)
app.include_router(ibkr_router.router)
app.include_router(trades_router.router)
app.include_router(trade_risk_router.router)
app.include_router(screener_router.router)
app.include_router(prices_router.router)
app.include_router(candles_router.router)

mount_frontend_assets(app, _FRONTEND_ASSETS)


@app.get("/")
def read_root():
    return serve_frontend_index(_FRONTEND_INDEX)


@app.get("/health")
def health_check():
    return build_health_report(_SCREENER_JSON)


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    return serve_frontend_index(_FRONTEND_INDEX)
