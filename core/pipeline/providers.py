"""Market-data provider abstraction.

The screener reads its canonical daily-bar panel through a ``MarketDataProvider``,
never directly from a named vendor. Today the only provider is Yahoo (yfinance),
which simply wraps the incumbent ``fetch_data`` path verbatim. The interface
exists so a bulk-EOD vendor (EODHD, Polygon, ...) can be slotted in behind the
same contract and validated against Yahoo with ``tools/provider_parity.py``
*before* it ever feeds a real or archiveable scan.

Why this matters for Chrollo specifically: the engine's structural thresholds
(box geometry off High/Low, the LPS/descent-tail/traversal floors) are calibrated
against the exact adjusted series the incumbent returns. A different vendor's
split/dividend adjustment can shift those reads, so swapping providers is a
*recalibration* event, not a clean infra swap — hence the contract below pins the
panel shape AND the adjustment convention, and the parity harness gates the swap
on engine output, not just on prices matching.

Canonical panel shape (the contract every provider must satisfy):
  - index:   tz-naive ``DatetimeIndex`` of trading sessions, ascending
  - columns: pandas ``MultiIndex`` of ``(ticker, field)``
  - fields:  ``Open``, ``High``, ``Low``, ``Close``, ``Volume`` (and ``Adj Close``
             iff the incumbent carries it). If the active engine reads adjusted
             prices, a new provider MUST follow the SAME adjustment convention as
             the incumbent so the calibrated thresholds keep their meaning.
  - window:  the full ``settings.DOWNLOAD_PERIOD`` trailing history for every
             requested ticker, plus ``settings.INDEX_SYMBOLS`` (the screener pulls
             market-regime context from the same panel).
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd

from config import settings


class MarketDataProvider(Protocol):
    """Structural contract for a daily-bar source. See module docstring for the
    canonical panel shape every implementation must return from ``fetch``."""

    name: str

    def fetch(self, tickers: list[str]) -> pd.DataFrame:
        """Return the canonical panel for ``tickers`` (+ index symbols)."""
        ...


class YahooProvider:
    """yfinance-backed provider — a thin delegation to the incumbent path.

    Wrapping (not reimplementing) ``fetch_data`` keeps the move behind the
    interface byte-for-byte a no-op: same parquet cache, same incremental and
    split-probe logic, same output. ``downloads`` (and therefore ``yfinance``) is
    imported lazily so selecting a different provider never pays yfinance's import
    cost.
    """

    name = "yahoo"

    def fetch(self, tickers: list[str]) -> pd.DataFrame:
        from core.pipeline.downloads import fetch_data

        return fetch_data(tickers)


# Registry of name -> provider class. New vendors register here once their
# adapter passes tools/provider_parity.py against the incumbent.
_PROVIDERS: dict[str, type] = {
    YahooProvider.name: YahooProvider,
}


def available_providers() -> list[str]:
    """Sorted list of registered provider names."""
    return sorted(_PROVIDERS)


def get_provider(name: str | None = None) -> MarketDataProvider:
    """Return the configured market-data provider instance.

    Resolution order: explicit ``name`` arg, then ``settings.MARKET_DATA_PROVIDER``,
    then ``"yahoo"``. ``settings`` is read lazily here (not at import) to respect
    the backend's config-shadowing constraint.
    """
    key = (name or getattr(settings, "MARKET_DATA_PROVIDER", "yahoo") or "yahoo").lower()
    try:
        provider_cls = _PROVIDERS[key]
    except KeyError:
        raise ValueError(
            f"Unknown market-data provider {key!r}; "
            f"known providers: {', '.join(available_providers())}"
        ) from None
    return provider_cls()
