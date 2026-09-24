"""Public data-acquisition API for the screener pipeline.

The implementation is split by responsibility:
- ``universe.tickers`` loads and refreshes the ticker universe.
- ``market_data.downloads`` owns downloads and parquet cache orchestration.
- ``context.market_context`` computes SPY/breadth context for scoring.

This module remains as the stable import doorway used by the rest of the app.
"""
from __future__ import annotations

from core.pipeline.market_data.downloads import fetch_data
from core.pipeline.context.market_context import get_market_context
from core.pipeline.market_data.providers import (
    MarketDataProvider,
    available_providers,
    get_provider,
)
from core.pipeline.universe.tickers import get_tickers

__all__ = [
    "fetch_data",
    "get_market_context",
    "get_tickers",
    "get_provider",
    "available_providers",
    "MarketDataProvider",
]
