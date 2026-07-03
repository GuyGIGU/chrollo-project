"""Screener data, scan status, and manual scan stream endpoints."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.pipeline.universe import (
    DEFAULT_UNIVERSE_KEY,
    default_universe,
    drilldown_map,
    resolve_universe,
    universe_keys,
)
from services import scan_runner, scan_status
from services.earnings import days_until, get_next_earnings_batch
from services.screener_data import invalidate_screener_cache, read_screener_data

router = APIRouter(prefix="", tags=["screener"])

_screener_json_path = ""


class EarningsBatchIn(BaseModel):
    tickers: list[str]


def configure_screener_routes(screener_json_path: str) -> None:
    # Retained for the US-Stocks default / health report; the data route resolves
    # each universe's artifact through the descriptor below.
    global _screener_json_path
    _screener_json_path = screener_json_path


def _artifact_state(universe: str):
    """Resolve a universe to its artifact path + freshness facts.

    Validates against the closed registry BEFORE any path is built — an unknown
    universe is a 422, never a filesystem lookup (no path traversal).
    'never_scanned' (valid universe, no artifact yet) is distinct from a real
    scan that matched nothing — so the UI can say "run a scan" vs "0 matched".
    The artifact mtime lets the UI distinguish a fresh "ready" from a stale one
    (the ETF universes refresh only on the scheduled scan).
    """
    try:
        uni = resolve_universe(universe)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown universe '{universe}'")

    path = uni.artifact_path()
    exists = os.path.exists(path)
    status = "ready" if exists else "never_scanned"
    scanned_at = None
    if exists:
        try:
            scanned_at = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()
        except OSError:
            pass
    return uni, path, status, scanned_at


@router.get("/screener-data/")
def get_screener_data(
    universe: str = Query(
        DEFAULT_UNIVERSE_KEY,
        description=f"Which universe's latest scan to serve. One of: {', '.join(universe_keys())}.",
    )
):
    uni, path, status, scanned_at = _artifact_state(universe)
    payload = read_screener_data(path)
    return {**payload, "universe": uni.key, "status": status, "scanned_at": scanned_at}


@router.get("/screener-summary/")
def get_screener_summary(
    universe: str = Query(
        DEFAULT_UNIVERSE_KEY,
        description=f"Which universe's latest scan to summarize. One of: {', '.join(universe_keys())}.",
    )
):
    """Slim scan read for light surfaces (Home tiles, freshness polls, the
    sector health board): full setup metadata + market context WITHOUT the
    per-ticker candle/volume arrays — the bulk of the ~13MB artifact."""
    uni, path, status, scanned_at = _artifact_state(universe)
    payload = read_screener_data(path)
    chart_data = payload.get("chart_data") or {}
    # Every per-ticker bar array (daily + the resampled weekly/monthly pairs) —
    # together ~95% of the artifact's weight.
    heavy = {"candles", "volumes", "weekly_candles", "weekly_volumes", "monthly_candles", "monthly_volumes"}
    setups = {
        ticker: {k: v for k, v in (data or {}).items() if k not in heavy}
        for ticker, data in chart_data.items()
    }
    return {
        "universe": uni.key,
        "status": status,
        "scanned_at": scanned_at,
        "ordered_tickers": payload.get("ordered_tickers", []),
        "market_context": payload.get("market_context"),
        "setups": setups,
    }


@router.get("/screener-data/drilldown/")
def get_drilldown(etf: str = Query(..., min_length=1, max_length=12)):
    """Top-down cross-link: the US-Stock setups related to a firing sector/commodity
    ETF, intersected with the latest US-Stocks scan.

    - Sector ETFs (XLK, …) resolve via each stock setup's ``sector_etf`` tag.
    - Commodity/thematic ETFs resolve via the curated ``commodity_equity_map``.
    ``basis`` lets the UI tell "no curated mapping" from "mapped, none fired today".
    """
    etf_u = etf.strip().upper()
    us = read_screener_data(default_universe().artifact_path())
    us_chart = us.get("chart_data", {}) or {}
    us_ordered = us.get("ordered_tickers", []) or []

    cmap = drilldown_map()
    if etf_u in cmap:
        targets = set(cmap[etf_u])
        members = [t for t in us_ordered if t in targets]
        basis = "commodity"
    else:
        from output.dashboard import SECTOR_ETF_NAMES  # lazy: heavier import

        if etf_u in SECTOR_ETF_NAMES:
            members = [
                t for t in us_ordered
                if str((us_chart.get(t) or {}).get("sector_etf") or "").upper() == etf_u
            ]
            basis = "sector"
        else:
            members, basis = [], "none"

    return {
        "etf": etf_u,
        "basis": basis,  # 'sector' | 'commodity' | 'none' (no curated mapping)
        "source_universe": DEFAULT_UNIVERSE_KEY,
        "ordered_tickers": members,
        "chart_data": {t: us_chart[t] for t in members if t in us_chart},
    }


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


@router.get("/run-evaluation-stream/")
def run_cached_evaluation_stream():
    def execute_and_yield():
        try:
            yield from scan_runner.stream_cached_evaluation()
        finally:
            invalidate_screener_cache()

    return StreamingResponse(execute_and_yield(), media_type="text/event-stream")


@router.get("/download-data-stream/")
def download_market_data_stream():
    return StreamingResponse(scan_runner.stream_data_download(), media_type="text/event-stream")
