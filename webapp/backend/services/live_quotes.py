"""Shared live quote fetcher for UI routes and background alerts."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable

import yfinance as yf

from ibkr import get_ibkr_service
from services import alpaca_prices, scan_status

log = logging.getLogger("chrollo.prices")

_QUOTE_SYMBOL_RE = re.compile(r"^[A-Z0-9._-]{1,16}$")


def fetch_live_quotes(
    tickers: Iterable[str],
    *,
    ibkr_quote_fn: Callable[[list[str]], dict[str, float]] | None = None,
    alpaca_fn: Callable[[list[str]], dict[str, float] | None] | None = None,
    scan_running_fn: Callable[[], bool] | None = None,
    yfinance_fn: Callable[[str], float | None] | None = None,
) -> dict[str, float]:
    """Return best-effort live quotes, prioritizing IBKR -> Alpaca -> yfinance."""
    ticker_list = normalize_quote_tickers(tickers)
    if not ticker_list:
        return {}

    ibkr_quote_fn = ibkr_quote_fn or fetch_ibkr_quote_prices
    alpaca_fn = alpaca_fn or alpaca_prices.fetch_quotes
    scan_running_fn = scan_running_fn or _scan_is_running
    yfinance_fn = yfinance_fn or _fetch_yfinance_price

    prices: dict[str, float] = {}
    prices.update(ibkr_quote_fn(ticker_list) or {})

    missing = [ticker for ticker in ticker_list if ticker not in prices]
    if missing:
        # fetch_quotes returns None when Alpaca isn't configured or a request fails;
        # guard so the yfinance fallback below still runs.
        alpaca_quotes = alpaca_fn(missing)
        if alpaca_quotes:
            prices.update(alpaca_quotes)

    if scan_running_fn():
        return prices

    for ticker in [item for item in ticker_list if item not in prices]:
        price = yfinance_fn(ticker)
        if price is not None:
            prices[ticker] = price
    return prices


def normalize_quote_tickers(tickers: Iterable[str]) -> list[str]:
    """Normalize and filter symbols accepted by external quote providers."""
    out: list[str] = []
    seen: set[str] = set()
    for raw_ticker in tickers:
        ticker = str(raw_ticker or "").strip().upper()
        if not is_external_quote_symbol(ticker) or ticker in seen:
            continue
        out.append(ticker)
        seen.add(ticker)
    return out


def is_external_quote_symbol(ticker: str) -> bool:
    return bool(_QUOTE_SYMBOL_RE.fullmatch(ticker))


def fetch_ibkr_quote_prices(tickers: list[str]) -> dict[str, float]:
    """Read current prices from the read-only IBKR portfolio snapshot."""
    wanted = set(tickers)
    try:
        snapshot = get_ibkr_service().snapshot()
    except Exception:
        log.warning("IBKR quote snapshot unavailable", exc_info=True)
        return {}

    if not snapshot.get("connected") or snapshot.get("stale"):
        return {}

    prices: dict[str, float] = {}
    for position in snapshot.get("portfolio") or snapshot.get("positions") or []:
        symbol = str(position.get("symbol") or "").strip().upper()
        if symbol not in wanted:
            continue
        price = _finite_positive(position.get("market_price"))
        if price is not None:
            prices[symbol] = price
    return prices


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
        log.warning("live price fetch failed for %s: %s", ticker, exc)
        return None


def _finite_positive(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or number != number:
        return None
    return number
