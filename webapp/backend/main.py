"""
Chrollo API - FastAPI backend for Trading Journal & Wyckoff Screener.
"""
from __future__ import annotations

import asyncio
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
from middleware.same_app import DEV_ORIGINS, SameAppOriginGuard
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
from services import auto_import, scan_diagnosis, scheduler
from services.frontend import mount_frontend_assets, serve_frontend_index
from services.health import build_health_report
from services.log_encoding import force_utf8
from services.startup import initialize_database

# UTF-8 BEFORE the handlers are built, or the split below writes through the
# Windows locale codec: under NSSM these two streams are files on cp1252, and a
# record carrying a char cp1252 lacks (the "→" the scan relay repeats) is not
# written at all — emit() raises and logging drops the line. Same defect the
# scan child was already immunised against; see services/log_encoding.py for
# why there is nothing to fold with it.
force_utf8(sys.stdout)
force_utf8(sys.stderr)

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

# uvicorn's own access log is a TWIN of chrollo.request: the same event, with
# LESS information (no request id, no duration) and no quiet list. Silencing
# the stderr flood only moved it — measured right after the 2026-08-25
# redeploy, 2,296 of the next 3,000 stdout lines were uvicorn logging
# GET /ibkr/status, and every real request was being written twice. One access
# log, and it is ours. Errors are unaffected: chrollo.request logs every
# non-2xx at INFO and every exception with a traceback.
#
# uvicorn configures its loggers before importing this module, so this runs
# after its dictConfig and sticks (the same ordering the handler swap above
# relies on).
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

initialize_database()

_SCREENER_JSON = os.path.join(_ROOT_DIR, "output", "screener_data.json")
_FRONTEND_DIST = os.path.join(_ROOT_DIR, "webapp", "frontend", "dist")
_FRONTEND_INDEX = os.path.join(_FRONTEND_DIST, "index.html")
_FRONTEND_ASSETS = os.path.join(_FRONTEND_DIST, "assets")

screener_router.configure_screener_routes(_SCREENER_JSON)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background services around the app lifecycle."""
    # Work out WHY any interrupted scan run died, off the event loop. It reads
    # the Windows event log, which is only up at a real service start — never at
    # the import-time boot migrations, where the reconcile itself can run inside
    # a dying Windows session. Best-effort by construction: an unresolved row
    # simply stays pending for the next start, so startup never waits on it.
    asyncio.get_running_loop().run_in_executor(None, scan_diagnosis.resolve_pending)
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

# INNERMOST, so a refusal still returns THROUGH RequestIDMiddleware: the guard's
# own warning line carries no request id, but the access line paired with it
# does, and the 403 answers with an x-request-id header. The default-on half of
# the same-app posture rule: every request, not the 15 routes someone remembered
# to decorate, and the only mechanism that reaches the SSE streams (EventSource
# cannot send the header). See middleware/same_app.py.
app.add_middleware(SameAppOriginGuard)
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
    allow_origins=list(DEV_ORIGINS),
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
