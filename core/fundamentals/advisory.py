"""ADVISORY primitives (Lane E).

The per-ticker advisory ASSEMBLY lives in ``core.fundamentals.post_pass``
(the conductor-level post-pass, Power-Play program Task 12) — the old
in-worker builder ``per_ticker_advisory`` was retired 2026-08-17 (council
review, EC-3: one assembly, one owner; it had kept a green battery with zero
production callers). This module keeps the shared primitives.

ADVISORY CONTRACT (the hard rules the assembly must never break):
  * It is metadata ONLY — it never gates a setup, never changes Score/Tier.
  * Every flag defaults OFF; with all OFF the assembly returns ``None`` and
    makes ZERO provider calls, so the engine output stays byte-identical.
  * Null-safe by construction: a missing/short/failed read degrades to an
    ABSENT key (never a chip, never a penalty).
  * The in-house ``rs_rating`` is a universe-relative percentile the screener
    computes over all firing tickers (``core.regime.percentile``); this layer
    only emits the single-ticker inputs.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def _flag(name: str, default=False):
    try:
        from config import settings

        return getattr(settings, name, default)
    except Exception:  # pragma: no cover - settings import guard
        return default


def _trailing_return(df: pd.DataFrame, lookback: int) -> Optional[float]:
    """Trailing close-to-close return over ``lookback`` bars ending at the latest
    bar of ``df``; the universe-relative RS rating percentile-ranks this. ``None``
    when the frame is too short or the base close is non-positive."""
    if df is None or "Close" not in getattr(df, "columns", []) or len(df) <= lookback:
        return None
    try:
        last = float(df["Close"].iloc[-1])
        base = float(df["Close"].iloc[-lookback - 1])
    except (IndexError, TypeError, ValueError):
        return None
    if base <= 0:
        return None
    return last / base - 1.0
