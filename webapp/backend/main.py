"""
Chrollo API - FastAPI backend for Trading Journal & Wyckoff Screener.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from ibkr import get_ibkr_service
from middleware.request_id import RequestIDMiddleware
from routers import analytics as analytics_router
from routers import archive as archive_router
from routers import ibkr as ibkr_router
from routers import journal as journal_router
from routers import market_data as market_data_router
from routers import portfolio as portfolio_router
from routers import portfolio_streams as portfolio_streams_router
from routers import position_calculator as position_calculator_router
from routers import prices as prices_router
from routers import screener as screener_router
from routers import tags as tags_router
from routers import trades as trades_router
from routers import watchlist as watchlist_router
from services import auto_import, scheduler
from services.frontend import mount_frontend_assets, serve_frontend_index
from services.health import build_health_report
from services.startup import initialize_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

initialize_database()

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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
app.include_router(journal_router.router)
app.include_router(archive_router.router)
app.include_router(watchlist_router.router)
app.include_router(ibkr_router.router)
app.include_router(position_calculator_router.router)
app.include_router(trades_router.router)
app.include_router(screener_router.router)
app.include_router(prices_router.router)

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
