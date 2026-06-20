"""Live quote endpoints."""
from __future__ import annotations

import logging
import re

import yfinance as yf
from fastapi import APIRouter, Query

from services import alpaca_prices, scan_status

router = APIRouter(prefix="", tags=["prices"])
_log = logging.getLogger("chrollo.prices")
_QUOTE_SYMBOL_RE = re.compile(r"^[A-Z0-9._-]{1,16}$")


@router.get("/live-prices/")
def get_live_prices(tickers: str = Query("")):
    ticker_list = [
        ticker.strip().upper()
        for ticker in tickers.split(",")
        if _is_external_quote_symbol(ticker.strip().upper())
    ]
    if not ticker_list:
        return {}

    prices: dict[str, float] = {}
    # fetch_quotes returns None when Alpaca isn't configured or a request fails;
    # guard so the yfinance fallback below still runs (dict.update(None) raises).
    alpaca_quotes = alpaca_prices.fetch_quotes(ticker_list)
    if alpaca_quotes:
        prices.update(alpaca_quotes)

    if _scan_is_running():
        return prices

    for ticker in [item for item in ticker_list if item not in prices]:
        price = _fetch_yfinance_price(ticker)
        if price is not None:
            prices[ticker] = price
    return prices


def _is_external_quote_symbol(ticker: str) -> bool:
    return bool(_QUOTE_SYMBOL_RE.fullmatch(ticker))


def _scan_is_running() -> bool:
    try:
        latest = scan_status.latest_run()
    except Exception:
        return False
    return (latest or {}).get("status") == "running"


def _fetch_yfinance_price(ticker: str) -> float | None:
    try:
        ticker_obj = yf.Ticker(ticker)
        value = ticker_obj.fast_info.get("lastPrice") or ticker_obj.info.get("currentPrice")
        return round(float(value), 2) if value else None
    except Exception as exc:
        _log.warning("live price fetch failed for %s: %s", ticker, exc)
        return None
