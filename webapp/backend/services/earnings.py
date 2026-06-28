"""Earnings calendar lookups with a 24h in-memory cache.

yfinance ``Ticker.calendar`` returns a small DataFrame whose first row holds
the next earnings event. We cache the resolved date per ticker so a screener
grid with 50 tickers doesn't pound the network on every page render.

If a ticker has no upcoming earnings (delisted / inactive / sparse data),
the cache stores ``None`` so subsequent lookups don't re-query.
"""
from __future__ import annotations

import time
from datetime import datetime
from threading import Lock
from typing import Optional

# {ticker: (epoch_when_cached, isodate_or_None)}
_CACHE: dict[str, tuple[float, Optional[str]]] = {}
_CACHE_TTL = 24 * 3600  # one day
_LOCK = Lock()


def _resolve(ticker: str) -> Optional[str]:
    """Look up the next earnings date. Returns ISO date or None.

    Routes through the market-data provider's ``earnings_date`` (which owns the
    yfinance ``.calendar`` shape-handling and the daemon-thread timeout) instead
    of calling yfinance raw, so a hung ``.calendar`` scrape can't stall the
    earnings-batch endpoint.
    """
    from core.pipeline.providers import get_provider

    return get_provider().earnings_date(ticker)


def get_next_earnings(ticker: str) -> Optional[str]:
    """Return next earnings date for ``ticker`` (ISO YYYY-MM-DD) or None.

    Read-through cached for 24 hours.
    """
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(ticker)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    resolved = _resolve(ticker)
    with _LOCK:
        _CACHE[ticker] = (now, resolved)
    return resolved


def get_next_earnings_batch(tickers: list[str]) -> dict[str, Optional[str]]:
    """Batch wrapper. Sequential because yfinance per-ticker calls don't
    parallelize cleanly without rate-limit risk."""
    return {t: get_next_earnings(t) for t in tickers}


def days_until(iso_date: Optional[str], today: Optional[datetime] = None) -> Optional[int]:
    """Calendar days from ``today`` to ``iso_date``. Negative if past."""
    if not iso_date:
        return None
    try:
        target = datetime.strptime(iso_date[:10], "%Y-%m-%d")
        ref = today or datetime.today()
        return (target.date() - ref.date()).days
    except Exception:
        return None
