"""Alpaca Market Data v2 batch quote fetcher for the live-price endpoint.

Why Alpaca over Yahoo for the dashboard's open-position polling:
- Real-time IEX quotes on the free tier (Yahoo is ~15-min delayed).
- A single batch endpoint returns quotes for every symbol in one request, so
  polling 10 open positions is one HTTP round-trip instead of ten.
- Generous free-tier limit (200 req/min) means we can poll aggressively
  without burning budget.

Configuration: set ``ALPACA_KEY_ID`` and ``ALPACA_SECRET_KEY`` in the env.
If either is missing, ``fetch_quotes()`` returns ``None`` and the caller is
expected to fall back to its existing path (yfinance).
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, Optional

import requests

log = logging.getLogger(__name__)

_DATA_BASE = "https://data.alpaca.markets/v2"
_TIMEOUT = 6.0  # seconds — short, so a slow Alpaca doesn't stall the dashboard


def _credentials() -> Optional[tuple[str, str]]:
    key = os.environ.get("ALPACA_KEY_ID", "").strip()
    sec = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if not key or not sec:
        return None
    return key, sec


def is_configured() -> bool:
    return _credentials() is not None


def fetch_quotes(tickers: Iterable[str]) -> Optional[Dict[str, float]]:
    """Return ``{symbol: last_price}`` for the given symbols, or ``None`` if
    Alpaca isn't configured or the request failed. Missing symbols are simply
    absent from the returned dict — callers should fall back per-symbol.

    Uses the **latest-trade** endpoint rather than the quote (bid/ask) endpoint
    because the dashboard wants a single "current price" number, and trades are
    a more honest representation than the bid/ask midpoint for thinly-traded
    names. On the free IEX feed this is the most recent IEX-printed trade.
    """
    creds = _credentials()
    if creds is None:
        return None

    syms = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not syms:
        return {}

    key, sec = creds
    try:
        r = requests.get(
            f"{_DATA_BASE}/stocks/trades/latest",
            params={"symbols": ",".join(syms)},
            headers={
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": sec,
                "Accept": "application/json",
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        log.warning("Alpaca request failed: %s", e)
        return None

    if r.status_code != 200:
        # 401/403 usually means bad keys; 422 = malformed symbol list.
        log.warning("Alpaca returned %s: %s", r.status_code, r.text[:200])
        return None

    try:
        payload = r.json()
    except ValueError:
        log.warning("Alpaca returned non-JSON body")
        return None

    trades = payload.get("trades") or {}
    out: Dict[str, float] = {}
    for sym, trade in trades.items():
        if not isinstance(trade, dict):
            continue
        px = trade.get("p")  # 'p' is the trade price field in Alpaca's schema
        if px is None:
            continue
        try:
            out[sym.upper()] = round(float(px), 2)
        except (TypeError, ValueError):
            continue
    return out
