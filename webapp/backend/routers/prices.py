"""Live quote endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from services import alpaca_prices, live_quotes

router = APIRouter(prefix="", tags=["prices"])


@router.get("/live-prices/")
def get_live_prices(tickers: str = Query("")):
    return live_quotes.fetch_live_quotes(
        tickers.split(","),
        alpaca_fn=alpaca_prices.fetch_quotes,
        scan_running_fn=_scan_is_running,
        yfinance_fn=_fetch_yfinance_price,
    )


def _is_external_quote_symbol(ticker: str) -> bool:
    return live_quotes.is_external_quote_symbol(ticker)


def _scan_is_running() -> bool:
    return live_quotes._scan_is_running()


def _fetch_yfinance_price(ticker: str) -> float | None:
    return live_quotes._fetch_yfinance_price(ticker)
