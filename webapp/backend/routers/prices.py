"""Live quote endpoints."""
from __future__ import annotations

import logging

import yfinance as yf
from fastapi import APIRouter, Query

from services import alpaca_prices

router = APIRouter(prefix="", tags=["prices"])
_log = logging.getLogger("chrollo.prices")


@router.get("/live-prices/")
def get_live_prices(tickers: str = Query("")):
    ticker_list = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()]
    if not ticker_list:
        return {}

    prices: dict[str, float] = {}
    # fetch_quotes returns None when Alpaca isn't configured or a request fails;
    # guard so the yfinance fallback below still runs (dict.update(None) raises).
    alpaca_quotes = alpaca_prices.fetch_quotes(ticker_list)
    if alpaca_quotes:
        prices.update(alpaca_quotes)

    for ticker in [item for item in ticker_list if item not in prices]:
        price = _fetch_yfinance_price(ticker)
        if price is not None:
            prices[ticker] = price
    return prices


def _fetch_yfinance_price(ticker: str) -> float | None:
    try:
        ticker_obj = yf.Ticker(ticker)
        value = ticker_obj.fast_info.get("lastPrice") or ticker_obj.info.get("currentPrice")
        return round(float(value), 2) if value else None
    except Exception as exc:
        _log.warning("live price fetch failed for %s: %s", ticker, exc)
        return None
