"""Market-context measures broadcast to the screener scoring pass."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from config import settings
from core.pipeline.cache import _is_market_hours, _now_iso, _project_root, _read_meta, _write_meta


def _market_context_path() -> str:
    return os.path.join(_project_root(), settings.MARKET_CONTEXT_FILENAME)


def get_market_context(data: pd.DataFrame,
                       ticker_frames: dict[str, pd.DataFrame]) -> tuple[float, float | None]:
    """
    Return ``(spy_6m_return, breadth_pct)``. Cached in a JSON sidecar with a
    TTL of 1h during market hours, 12h otherwise. Recomputed if the cached
    SPY-last-bar-date doesn't match the parquet's current SPY last bar.

    Inputs:
    - ``data``: full parquet panel (must include SPY as a top-level column key
      if SPY 6m return is to be computed). If SPY is missing, returns 0.0 for
      the RS reference (consistent with the previous fallback behavior).
    - ``ticker_frames``: per-ticker DataFrames used to compute breadth.
    """
    path = _market_context_path()
    cached = _read_meta(path)  # JSON read/write helpers are general-purpose

    spy = settings.SPY_SYMBOL
    spy_last_bar = None
    if isinstance(data.columns, pd.MultiIndex) and spy in data.columns.get_level_values(0):
        try:
            spy_close_series = data[spy]['Close'].dropna()
            if not spy_close_series.empty:
                spy_last_bar = spy_close_series.index[-1].strftime('%Y-%m-%d')
        except KeyError:
            spy_last_bar = None

    ttl_hours = (settings.MARKET_CONTEXT_TTL_HOURS_MARKET if _is_market_hours()
                 else settings.MARKET_CONTEXT_TTL_HOURS_OFFHOURS)

    if cached and 'computed_at' in cached:
        try:
            cached_ts = datetime.fromisoformat(cached['computed_at'])
            age_hours = (datetime.now(timezone.utc) - cached_ts).total_seconds() / 3600.0
            if (age_hours < ttl_hours
                    and cached.get('spy_last_bar_date') == spy_last_bar
                    and 'spy_6m_return' in cached
                    and 'breadth_pct' in cached):
                spy_ret = float(cached['spy_6m_return'])
                bp = cached['breadth_pct']
                bp_val = float(bp) if bp is not None else None
                print(f"Market context loaded from cache (age {age_hours:.2f}h, "
                      f"TTL {ttl_hours}h): SPY 6m={spy_ret*100:.2f}%, "
                      f"breadth={'n/a' if bp_val is None else f'{bp_val*100:.1f}%'}",
                      flush=True)
                return spy_ret, bp_val
        except Exception:
            pass

    # Compute fresh.
    spy_6m_return = 0.0
    if spy_last_bar is not None:
        try:
            spy_close = data[spy]['Close'].dropna()
            if len(spy_close) > settings.RS_LOOKBACK_BARS:
                spy_6m_return = float(
                    spy_close.iloc[-1] / spy_close.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0
                )
                print(f"SPY 6m return: {spy_6m_return*100:.2f}% (RS reference)")
        except Exception as e:
            print(f"  [SPY compute failed: {type(e).__name__}: {e}] — RS bonus disabled this run")

    breadth_pct: float | None = None
    if ticker_frames:
        breadth_count = 0
        breadth_total = 0
        for tdf in ticker_frames.values():
            close = tdf['Close']
            if len(close) >= 50:
                last_50_mean = float(close.iloc[-50:].mean())
                if pd.notna(last_50_mean):
                    breadth_total += 1
                    if float(close.iloc[-1]) > last_50_mean:
                        breadth_count += 1
        if breadth_total > 0:
            breadth_pct = breadth_count / breadth_total
            print(f"Market breadth (Close > SMA_50): {breadth_pct*100:.1f}% "
                  f"({breadth_count}/{breadth_total})")

    _write_meta(path, {
        'spy_6m_return': spy_6m_return,
        'breadth_pct': breadth_pct,
        'spy_last_bar_date': spy_last_bar,
        'computed_at': _now_iso(),
    })
    return spy_6m_return, breadth_pct
