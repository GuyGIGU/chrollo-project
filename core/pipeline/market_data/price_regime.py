"""Which price series the cache holds: as-traded (split-adjusted only) or dividend-adjusted.

``DATA_DIVIDEND_ADJUSTED`` decides it. Every price download takes its ``auto_adjust``
from :func:`price_auto_adjust`, and the cache meta is stamped with :func:`_price_regime`
so a cache fetched under the other regime is refetched cold, never mixed in.
"""
from __future__ import annotations

from config import settings


def price_auto_adjust() -> bool:
    """The ONE source for every price download's ``auto_adjust`` flag.

    False (the shipped default via ``DATA_DIVIDEND_ADJUSTED = False``) =
    as-traded OHLC, split-adjusted only — what TradingView shows and what the
    operator trades. Seed / forward-returns / writer downloads must import this
    so their series can never diverge from the cache regime (eval-twin rule).
    The getattr fallback matches the settings default (as-traded) so a process
    with a shadowed/stale config degrades to the SAME regime, never a mix."""
    return bool(getattr(settings, "DATA_DIVIDEND_ADJUSTED", False))


def _price_regime() -> str:
    """The regime tag stamped into cache meta for the current settings."""
    return "div_adjusted" if price_auto_adjust() else "as_traded"


def _meta_regime_mismatch(meta: dict) -> bool:
    """True when the on-disk cache was fetched under a DIFFERENT price regime.

    Caches written before the tag existed are dividend-adjusted (the old
    default). A mismatched cache must never be served fresh, returned current,
    or incrementally patched — mixing regimes in one panel corrupts every
    structural read. Only a full cold refetch may replace it."""
    return meta.get("price_series", "div_adjusted") != _price_regime()
