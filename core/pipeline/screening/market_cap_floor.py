"""The market-cap floor (operator 2026-10-03): a fire under ``MIN_MARKET_CAP``
dollars leaves the scan.

It is the one entry rule the price data cannot answer, so it runs on the FIRES
after the chart read (about a hundred lookups a night), not on the whole
universe before it. A fire whose market cap cannot be read STAYS — a missing
number is never a refusal (the entry gate's own rule: a NaN sample passes).
Each kept fire carries ``_market_cap`` for the detail panel and the archive.

Stocks only: a curated ETF universe (``ticker_source == "csv"``) has no market
cap to speak of and skips the floor.
"""
from __future__ import annotations

import sys


def apply_market_cap_floor(results: list, universe, *, provider=None) -> dict | None:
    """Drop the fires under the floor from ``results`` IN PLACE and stamp
    ``_market_cap`` on the rest. Returns the counts, or ``None`` when the
    universe is not a stock universe (nothing was looked up)."""
    if getattr(universe, "ticker_source", None) == "csv":
        return None
    from config import settings

    floor = float(settings.MIN_MARKET_CAP)
    if provider is None:
        from core.pipeline.market_data.providers import get_provider
        provider = get_provider()

    kept, refused, unknown = [], [], 0
    for result in results:
        ticker = result.get("Ticker")
        try:
            cap = provider.market_cap(ticker) if ticker else None
        except Exception as e:  # noqa: BLE001 — one bad lookup never costs the scan
            print(f"  [market cap skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)
            cap = None
        if cap is None:
            unknown += 1
            kept.append(result)
        elif cap < floor:
            refused.append(ticker)
        else:
            result["_market_cap"] = cap
            kept.append(result)
    results[:] = kept
    if refused:
        print(f"  Market-cap floor ${floor / 1e6:,.0f}M removed {len(refused)} fire(s): "
              f"{', '.join(sorted(refused))}")
    return {"checked": len(kept) + len(refused), "refused": len(refused), "unknown": unknown,
            "refused_tickers": sorted(refused)}
