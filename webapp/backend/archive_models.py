"""Compatibility facade for archive ORM and metadata enrichment.

New code imports domains.archive.models or domains.archive.market_context.
"""
from database import Base
from domains.archive.models import SetupArchive, NearMissArchive
from domains.archive.market_context import (
    get_sector_etf, resolve_sector_etf, get_market_context, get_sector_trend,
    _SECTOR_TO_ETF, _history_window, _market_context_impl, _sector_etf_impl,
    _SECTOR_INFO_TIMEOUT_S, _MARKET_CONTEXT_TIMEOUT_S,
)
