"""Screener data, scan status, and manual scan stream endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services import scan_runner, scan_status
from services.earnings import days_until, get_next_earnings_batch
from services.screener_data import invalidate_screener_cache, read_screener_data

router = APIRouter(prefix="", tags=["screener"])

_screener_json_path = ""


class EarningsBatchIn(BaseModel):
    tickers: list[str]


def configure_screener_routes(screener_json_path: str) -> None:
    global _screener_json_path
    _screener_json_path = screener_json_path


@router.get("/screener-data/")
def get_screener_data():
    return read_screener_data(_screener_json_path)


@router.get("/scan-status/latest")
def get_latest_scan_status():
    return scan_status.latest_run() or {
        "id": None,
        "started_at": None,
        "finished_at": None,
        "status": "never",
        "n_setups": None,
        "error": None,
        "trigger": None,
    }


@router.get("/scan-status/history")
def get_scan_status_history(limit: int = Query(20, ge=1, le=100)):
    return {"runs": scan_status.recent_runs(limit)}


@router.post("/screener-data/earnings")
def screener_earnings(payload: EarningsBatchIn):
    if not payload.tickers:
        return {}
    raw = get_next_earnings_batch([ticker.upper().strip() for ticker in payload.tickers if ticker])
    return {
        ticker: {"date": date, "days_until": days_until(date)}
        for ticker, date in raw.items()
    }


@router.get("/run-scan-stream/")
def run_screener_scan_stream():
    def execute_and_yield():
        try:
            yield from scan_runner.stream_manual_scan()
        finally:
            invalidate_screener_cache()

    return StreamingResponse(execute_and_yield(), media_type="text/event-stream")
