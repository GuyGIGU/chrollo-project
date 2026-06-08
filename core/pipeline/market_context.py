"""Market-context measures broadcast to the screener scoring pass."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from config import settings
from core.pipeline.cache import _is_market_hours, _now_iso, _project_root, _read_meta, _write_meta


def _market_context_path() -> str:
    return os.path.join(_project_root(), settings.MARKET_CONTEXT_FILENAME)


def _finite_float(value) -> float | None:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    return val if pd.notna(val) else None


def _get_index_frame(data: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
    if not isinstance(data.columns, pd.MultiIndex):
        return None
    if symbol not in data.columns.get_level_values(0):
        return None
    try:
        frame = data[symbol].dropna(how='all')
    except KeyError:
        return None
    return frame if not frame.empty else None


def _last_bar_date(frame: pd.DataFrame | None) -> str | None:
    if frame is None or frame.empty or 'Close' not in frame:
        return None
    close = frame['Close'].dropna()
    if close.empty:
        return None
    return close.index[-1].strftime('%Y-%m-%d')


def _compute_index_trend(frame: pd.DataFrame) -> dict:
    close = pd.to_numeric(frame.get('Close'), errors='coerce').dropna()
    if close.empty:
        return {}
    if 'Volume' in frame:
        volume = pd.to_numeric(frame['Volume'], errors='coerce').reindex(close.index)
    else:
        volume = pd.Series(index=close.index, dtype='float64')

    latest_close = _finite_float(close.iloc[-1])
    trend = {
        'close': latest_close,
        'last_bar_date': close.index[-1].strftime('%Y-%m-%d'),
    }

    for period in settings.REGIME_MA_PERIODS:
        sma = close.rolling(period).mean()
        ma_val = _finite_float(sma.iloc[-1]) if len(sma) else None
        trend[f'sma_{period}'] = ma_val
        trend[f'above_sma_{period}'] = (
            latest_close > ma_val if latest_close is not None and ma_val is not None else None
        )

    slope_period = settings.REGIME_SLOPE_MA_PERIOD
    slope_lookback = settings.REGIME_SLOPE_LOOKBACK
    slope_sma = close.rolling(slope_period).mean()
    slope_pct = None
    if len(slope_sma.dropna()) > slope_lookback:
        now = _finite_float(slope_sma.iloc[-1])
        then = _finite_float(slope_sma.iloc[-slope_lookback - 1])
        if now is not None and then not in (None, 0):
            slope_pct = now / then - 1.0
    trend[f'sma_{slope_period}_slope_pct'] = slope_pct
    trend[f'sma_{slope_period}_rising'] = bool(slope_pct is not None and slope_pct > 0)

    ret = close.pct_change()
    distribution = (
        (ret <= -settings.REGIME_DISTRIBUTION_DAY_DROP)
        & (volume > volume.shift(1))
    ).tail(settings.REGIME_DISTRIBUTION_DAY_LOOKBACK)
    trend['distribution_days'] = int(distribution.fillna(False).sum())
    return trend


def _compute_breadth(ticker_frames: dict[str, pd.DataFrame], period: int) -> tuple[float | None, int, int]:
    if not ticker_frames:
        return None, 0, 0
    count = 0
    total = 0
    for tdf in ticker_frames.values():
        if 'Close' not in tdf:
            continue
        close = pd.to_numeric(tdf['Close'], errors='coerce').dropna()
        if len(close) >= period:
            ma = _finite_float(close.iloc[-period:].mean())
            last = _finite_float(close.iloc[-1])
            if ma is not None and last is not None:
                total += 1
                if last > ma:
                    count += 1
    return (count / total if total else None), count, total


def _synthesize_regime(index_trends: dict[str, dict],
                       breadth_50_pct: float | None,
                       breadth_200_pct: float | None) -> str:
    if not index_trends:
        return 'NEUTRAL'
    primary = index_trends.get(settings.SPY_SYMBOL) or next(iter(index_trends.values()), {})
    primary_above_50 = primary.get('above_sma_50')
    primary_above_200 = primary.get('above_sma_200')
    primary_50_rising = primary.get('sma_50_rising')
    pressure_days = max((int(t.get('distribution_days') or 0) for t in index_trends.values()), default=0)

    weak_50 = breadth_50_pct is not None and breadth_50_pct < settings.REGIME_BREADTH_50_WEAK
    weak_200 = breadth_200_pct is not None and breadth_200_pct < settings.REGIME_BREADTH_200_WEAK
    healthy_50 = breadth_50_pct is not None and breadth_50_pct >= settings.REGIME_BREADTH_50_HEALTHY
    healthy_200 = breadth_200_pct is not None and breadth_200_pct >= settings.REGIME_BREADTH_200_HEALTHY

    if primary_above_200 is False or (primary_above_50 is False and weak_200):
        return 'CORRECTION'
    if pressure_days >= settings.REGIME_DISTRIBUTION_DAY_PRESSURE or weak_50:
        return 'UNDER_PRESSURE'
    if primary_above_50 is True and primary_50_rising is True and healthy_50 and healthy_200:
        return 'UPTREND'
    return 'NEUTRAL'


def _compute_regime(data: pd.DataFrame,
                    ticker_frames: dict[str, pd.DataFrame]) -> dict:
    index_trends = {}
    for symbol in getattr(settings, 'INDEX_SYMBOLS', [settings.SPY_SYMBOL]):
        frame = _get_index_frame(data, symbol)
        if frame is not None:
            trend = _compute_index_trend(frame)
            if trend:
                index_trends[symbol] = trend

    breadth_50_pct, breadth_50_count, breadth_50_total = _compute_breadth(ticker_frames, 50)
    breadth_200_pct, breadth_200_count, breadth_200_total = _compute_breadth(ticker_frames, 200)
    state = _synthesize_regime(index_trends, breadth_50_pct, breadth_200_pct)
    pressure_days = max((int(t.get('distribution_days') or 0) for t in index_trends.values()), default=0)

    return {
        'state': state,
        'indexes': index_trends,
        'breadth_50_pct': breadth_50_pct,
        'breadth_50_count': breadth_50_count,
        'breadth_50_total': breadth_50_total,
        'breadth_200_pct': breadth_200_pct,
        'breadth_200_count': breadth_200_count,
        'breadth_200_total': breadth_200_total,
        'distribution_days': pressure_days,
    }


def get_market_context(data: pd.DataFrame,
                       ticker_frames: dict[str, pd.DataFrame]) -> dict:
    """
    Return a run-level market-context dict. ``spy_6m_return`` and
    ``breadth_pct`` remain the only scoring inputs; ``regime`` is descriptive
    context for dashboard/archive measurement.

    Inputs:
    - ``data``: full parquet panel (must include SPY as a top-level column key
      if SPY 6m return is to be computed). If SPY is missing, returns 0.0 for
      the RS reference (consistent with the previous fallback behavior).
    - ``ticker_frames``: per-ticker DataFrames used to compute breadth.
    """
    path = _market_context_path()
    cached = _read_meta(path)  # JSON read/write helpers are general-purpose

    index_last_bar_dates = {}
    for symbol in getattr(settings, 'INDEX_SYMBOLS', [settings.SPY_SYMBOL]):
        index_last_bar_dates[symbol] = _last_bar_date(_get_index_frame(data, symbol))
    spy_last_bar = index_last_bar_dates.get(settings.SPY_SYMBOL)

    ttl_hours = (settings.MARKET_CONTEXT_TTL_HOURS_MARKET if _is_market_hours()
                 else settings.MARKET_CONTEXT_TTL_HOURS_OFFHOURS)

    if cached and 'computed_at' in cached:
        try:
            cached_ts = datetime.fromisoformat(cached['computed_at'])
            age_hours = (datetime.now(timezone.utc) - cached_ts).total_seconds() / 3600.0
            if (age_hours < ttl_hours
                    and cached.get('spy_last_bar_date') == spy_last_bar
                    and cached.get('index_last_bar_dates') == index_last_bar_dates
                    and 'spy_6m_return' in cached
                    and 'breadth_pct' in cached
                    and 'regime' in cached):
                spy_ret = float(cached['spy_6m_return'])
                bp = cached['breadth_pct']
                bp_val = float(bp) if bp is not None else None
                regime = cached.get('regime') or {}
                print(f"Market context loaded from cache (age {age_hours:.2f}h, "
                      f"TTL {ttl_hours}h): SPY 6m={spy_ret*100:.2f}%, "
                      f"breadth={'n/a' if bp_val is None else f'{bp_val*100:.1f}%'}, "
                      f"regime={regime.get('state', 'UNKNOWN')}",
                      flush=True)
                return {
                    'spy_6m_return': spy_ret,
                    'breadth_pct': bp_val,
                    'regime': regime,
                    'spy_last_bar_date': spy_last_bar,
                    'index_last_bar_dates': index_last_bar_dates,
                    'computed_at': cached.get('computed_at'),
                }
        except Exception:
            pass

    # Compute fresh.
    spy_6m_return = 0.0
    if spy_last_bar is not None:
        try:
            spy = settings.SPY_SYMBOL
            spy_close = data[spy]['Close'].dropna()
            if len(spy_close) > settings.RS_LOOKBACK_BARS:
                spy_6m_return = float(
                    spy_close.iloc[-1] / spy_close.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0
                )
                print(f"SPY 6m return: {spy_6m_return*100:.2f}% (RS reference)")
        except Exception as e:
            print(f"  [SPY compute failed: {type(e).__name__}: {e}] — RS bonus disabled this run")

    breadth_pct, breadth_count, breadth_total = _compute_breadth(ticker_frames, 50)
    if breadth_pct is not None:
        print(f"Market breadth (Close > SMA_50): {breadth_pct*100:.1f}% "
              f"({breadth_count}/{breadth_total})")

    regime = _compute_regime(data, ticker_frames)
    breadth_200_label = (
        'n/a' if regime['breadth_200_pct'] is None
        else f"{regime['breadth_200_pct'] * 100:.1f}%"
    )
    print(f"Market regime: {regime['state']} "
          f"(breadth200={breadth_200_label}, "
          f"distribution days={regime['distribution_days']})")

    context = {
        'spy_6m_return': spy_6m_return,
        'breadth_pct': breadth_pct,
        'regime': regime,
        'spy_last_bar_date': spy_last_bar,
        'index_last_bar_dates': index_last_bar_dates,
        'computed_at': _now_iso(),
    }
    _write_meta(path, context)
    return context
