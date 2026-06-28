"""Small market-data endpoints for UI chart panels."""
from __future__ import annotations

import math
import re
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from services.market_data import chart_candles, daily_candle_frame

router = APIRouter(prefix="/market-data", tags=["market-data"])


def _clean_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9._-]{1,16}", value):
        raise HTTPException(status_code=400, detail="Invalid symbol")
    return value


def _is_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


@router.get("/chart/{symbol}")
def chart(symbol: str, days: int = Query(180, ge=20, le=730)) -> Dict[str, Any]:
    """Return real daily OHLCV candles for a portfolio symbol."""
    ticker = _clean_symbol(symbol)
    try:
        raw = daily_candle_frame(ticker, days, auto_adjust=False)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data fetch failed: {exc}") from exc

    if raw is None or raw.empty:
        raise HTTPException(status_code=404, detail="No chart data found")

    candles, volumes = chart_candles(
        raw,
        up_color="rgba(95, 184, 130, 0.28)",
        down_color="rgba(238, 99, 82, 0.28)",
        require_finite=True,
        volume_as_int=False,
    )

    if not candles:
        raise HTTPException(status_code=404, detail="No usable chart data found")
    return {"symbol": ticker, "candles": candles, "volumes": volumes}


@router.get("/status")
def market_data_status() -> Dict[str, Any]:
    from core.pipeline.cache_status import build_market_data_status

    return build_market_data_status()
