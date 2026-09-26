"""Live quote endpoints."""
from __future__ import annotations

import re

from fastapi import APIRouter, Query

from domains.market_data import alpaca_prices as alpaca_prices
from services import scan_status

router = APIRouter(prefix="", tags=["prices"])
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
    """Single-symbol live price via the provider's timeout-bounded latest_price.

    The previous implementation called yfinance ``.fast_info``/``.info`` raw and
    UNTIMED — a slow Yahoo could stall this per-symbol loop indefinitely, freezing
    the open-position poll (and the one worker thread serving every request). The
    provider hard-bounds each lookup with a daemon thread, so a hung Yahoo now
    degrades to "no quote" (None) promptly instead of blocking. A symbol that
    fails or times out is simply absent from the provider result → None here.
    """
    from core.pipeline.market_data.providers import get_provider

    return get_provider().latest_price([ticker]).get(ticker)
