"""Small market-data endpoints for UI chart panels."""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

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
    import yfinance as yf

    ticker = _clean_symbol(symbol)
    try:
        raw = yf.download(
            ticker,
            period=f"{days}d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            timeout=20,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data fetch failed: {exc}") from exc

    if raw is None or raw.empty:
        raise HTTPException(status_code=404, detail="No chart data found")
    if hasattr(raw.columns, "nlevels") and raw.columns.nlevels > 1:
        raw.columns = raw.columns.get_level_values(0)

    candles: List[Dict[str, Any]] = []
    volumes: List[Dict[str, Any]] = []
    for timestamp, row in raw.iterrows():
        values = {name: row.get(name) for name in ("Open", "High", "Low", "Close")}
        if not all(_is_number(value) for value in values.values()):
            continue
        date = timestamp.strftime("%Y-%m-%d")
        close = float(values["Close"])
        candles.append({
            "time": date,
            "open": float(values["Open"]),
            "high": float(values["High"]),
            "low": float(values["Low"]),
            "close": close,
        })
        volume = row.get("Volume")
        if _is_number(volume):
            volumes.append({
                "time": date,
                "value": float(volume),
                "color": "rgba(95, 184, 130, 0.28)" if close >= float(values["Open"]) else "rgba(238, 99, 82, 0.28)",
            })

    if not candles:
        raise HTTPException(status_code=404, detail="No usable chart data found")
    return {"symbol": ticker, "candles": candles, "volumes": volumes}
