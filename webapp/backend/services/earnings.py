"""Earnings calendar lookups with a 24h in-memory cache.

yfinance ``Ticker.calendar`` returns a small DataFrame whose first row holds
the next earnings event. We cache the resolved date per ticker so a screener
grid with 50 tickers doesn't pound the network on every page render.

If a ticker has no upcoming earnings (delisted / inactive / sparse data),
the cache stores ``None`` so subsequent lookups don't re-query.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from threading import Lock
from typing import Optional

log = logging.getLogger("chrollo.earnings")

# {ticker: (epoch_when_cached, isodate_or_None)}
_CACHE: dict[str, tuple[float, Optional[str]]] = {}
_CACHE_TTL = 24 * 3600  # one day
_LOCK = Lock()


def _resolve(ticker: str) -> Optional[str]:
    """Look up the next earnings date via yfinance. Returns ISO date or None."""
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar
    except Exception as e:
        log.debug("earnings lookup failed for %s: %s", ticker, e)
        return None

    if cal is None:
        return None

    # yfinance has shipped a few shapes for `calendar` — handle dict and DataFrame.
    earnings_date = None
    try:
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                earnings_date = ed[0] if isinstance(ed, (list, tuple)) and ed else ed
        else:
            # Older yfinance: DataFrame with "Earnings Date" row
            if hasattr(cal, "loc") and "Earnings Date" in getattr(cal, "index", []):
                row = cal.loc["Earnings Date"]
                earnings_date = row.iloc[0] if hasattr(row, "iloc") else row
    except Exception as e:
        log.debug("earnings parse failed for %s: %s", ticker, e)
        return None

    if earnings_date is None:
        return None

    try:
        # Normalize to ISO date string
        if hasattr(earnings_date, "strftime"):
            return earnings_date.strftime("%Y-%m-%d")
        return str(earnings_date)[:10]
    except Exception:
        return None


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
