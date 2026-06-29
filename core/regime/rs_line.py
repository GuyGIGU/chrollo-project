"""Relative-strength (RS) line primitive (Lane C).

The RS line is the classic ``stock_close / benchmark_close`` ratio (benchmark =
SPY). A rising RS line means the stock is outperforming the market; an RS line at
a NEW HIGH while the stock itself is still based is the leadership tell breakout
traders watch (the line leads price). This module emits the ratio series plus an
``rs_line_new_high`` boolean.

Pure core (``rs_line`` / ``rs_line_new_high``) takes already-fetched close series
and is fully unit-testable offline. ``compute_rs_line`` is the thin fetch wrapper
that pulls candles through ``get_provider()``; it is null-safe (insufficient or
missing data -> a result with ``None`` fields, never an exception).

Lookahead note: ``rs_line_new_high`` compares the LATEST ratio against the rolling
max of the window ENDING at that same bar (``min_periods`` lets a short history
still answer), so it never peeks at a future bar.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def rs_line(stock_close: pd.Series, bench_close: pd.Series) -> pd.Series:
    """Return the ``stock / benchmark`` ratio aligned on shared dates.

    The two series are inner-joined on their index (only dates present in BOTH
    contribute), zero/invalid benchmark points are dropped, and the result is a
    clean float Series indexed ascending. Empty inputs -> empty Series.
    """
    if stock_close is None or bench_close is None:
        return pd.Series(dtype="float64")
    if len(stock_close) == 0 or len(bench_close) == 0:
        return pd.Series(dtype="float64")

    joined = pd.concat(
        [stock_close.rename("stock"), bench_close.rename("bench")],
        axis=1,
        join="inner",
    ).dropna()
    if joined.empty:
        return pd.Series(dtype="float64")

    joined = joined[joined["bench"] != 0]
    if joined.empty:
        return pd.Series(dtype="float64")

    ratio = (joined["stock"] / joined["bench"]).astype("float64")
    return ratio.sort_index()


def rs_line_new_high(
    ratio: pd.Series, lookback: int, *, tol: float = 1e-9
) -> Optional[bool]:
    """Is the latest RS-line value a new high over the trailing ``lookback``?

    Compares the final ratio against the rolling max of the window ending on the
    final bar (so a series shorter than ``lookback`` still answers, using all the
    bars it has). Returns ``None`` when there is no data to judge. The ``tol``
    absorbs float noise so an exact re-test of the prior high still reads True.
    """
    if ratio is None or len(ratio) == 0:
        return None
    window = ratio.iloc[-lookback:] if lookback and lookback > 0 else ratio
    latest = float(window.iloc[-1])
    prior_max = float(window.max())
    return latest >= prior_max - tol


def compute_rs_line(
    ticker: str,
    *,
    lookback: Optional[int] = None,
    benchmark: str = "SPY",
    days: int = 400,
    provider=None,
) -> dict:
    """Fetch wrapper: RS line + new-high flag for ``ticker`` vs ``benchmark``.

    Returns ``{'ratio': pd.Series, 'latest': float|None,
    'rs_line_new_high': bool|None}``. Reads candles through the provider seam;
    any missing/short data degrades to ``None`` fields (never raises). ``lookback``
    defaults lazily to ``settings.RS_LINE_NEW_HIGH_LOOKBACK``.
    """
    if provider is None:
        from core.pipeline.providers import get_provider

        provider = get_provider()
    if lookback is None:
        from config import settings

        lookback = getattr(settings, "RS_LINE_NEW_HIGH_LOOKBACK", 252)

    empty = {"ratio": pd.Series(dtype="float64"), "latest": None, "rs_line_new_high": None}

    stock = provider.daily_candles(ticker, days)
    bench = provider.daily_candles(benchmark, days)
    if stock is None or bench is None or stock.empty or bench.empty:
        return empty
    if "Close" not in stock.columns or "Close" not in bench.columns:
        return empty

    ratio = rs_line(stock["Close"], bench["Close"])
    if ratio.empty:
        return empty

    return {
        "ratio": ratio,
        "latest": round(float(ratio.iloc[-1]), 6),
        "rs_line_new_high": rs_line_new_high(ratio, lookback),
    }
