"""Public data-acquisition API for the screener pipeline.

The implementation is split by responsibility:
- ``tickers`` loads and refreshes the ticker universe.
- ``downloads`` owns yfinance downloads and parquet cache orchestration.
- ``market_context`` computes SPY/breadth context for scoring.

This module remains as the stable import doorway used by the rest of the app.
"""
from __future__ import annotations

from core.pipeline.downloads import fetch_data
from core.pipeline.market_context import get_market_context
from core.pipeline.providers import (
    MarketDataProvider,
    available_providers,
    get_provider,
)
from core.pipeline.tickers import get_tickers

__all__ = [
    "fetch_data",
    "get_market_context",
    "get_tickers",
    "get_provider",
    "available_providers",
    "MarketDataProvider",
]
