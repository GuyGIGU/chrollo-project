"""Stock-level measurements the reader and the scan share: the daily range (ATR), ADR%, the distance to the
52-week high, Minervini's trend template, and the weekly/monthly resample.

Measure-only, no opinion, no settings. Every function here was the old engine's (``structure/metrics/indicators.py``
and ``structure/context/htf.py``); those modules import these names back until they are deleted.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from scipy.signal import lfilter


def _fast_ewm(x, period):
    """Extremely fast Exponential Weighted Moving Average using IIR filter.

    NaN contract: every NaN sample — leading pad or interior hole — is masked
    OUT of the recursive filter, which runs over the valid subsequence and
    scatters its results back onto those positions. A NaN input bar therefore
    yields a NaN output bar (honest: no measurement where there is no data)
    and NOTHING else. It does NOT leak forward (council review 2026-09-07,
    finding 14). With no NaN, or a leading run only, the valid subsequence IS
    the old slice and the output is byte-identical.
    """
    x_arr = np.asarray(x, dtype=float)
    isnan = np.isnan(x_arr)
    if isnan.any():
        valid_idx = np.flatnonzero(~isnan)
        if len(valid_idx) == 0:
            return x_arr
        y = np.full_like(x_arr, np.nan)
        y[valid_idx] = _fast_ewm_valid(x_arr[valid_idx], period)
        return y
    return _fast_ewm_valid(x_arr, period)


def _fast_ewm_valid(x, period):
    alpha = 1.0 / period
    b = np.array([alpha])
    a = np.array([1.0, -(1.0 - alpha)])
    zi = np.array([x[0] * (1.0 - alpha)])
    y, _ = lfilter(b, a, x, zi=zi)
    return y


def _true_range(df):
    """Compute True Range using vectorized np.maximum (avoids pd.concat overhead)."""
    high = df['High'].values
    low = df['Low'].values
    prev_close = df['Close'].shift(1).values
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    return np.maximum(tr1, np.maximum(tr2, tr3))


def calculate_atr(df, period=14):
    """Average True Range using Wilder's exponential smoothing.

    A missing OHLC cell makes True Range NaN at that bar (and at the next, via
    the shifted Close), and ``_fast_ewm``'s mask keeps the NaN THERE: the ATR
    series resumes on the next readable bar instead of dying to the right edge.
    Callers keep their own ``_finite(atr)`` guards — a NaN ATR is still a
    refusal, just a local one.
    """
    tr = _true_range(df)
    atr = _fast_ewm(tr, period)
    return pd.Series(atr, index=df.index)


def adr_pct(df, window: int = 20) -> float:
    """Average Daily Range % over the last ``window`` bars.

    Qullamaggie ADR%: 100 * (SMA(High / Low) - 1). Returns a plain percent
    such as 6.2 for 6.2%. Degenerate, insufficient, or non-finite input returns
    0.0 so dashboard/archive JSON never receives NaN/Inf from this metric.
    """
    try:
        if df is None or len(df) < window:
            return 0.0
        high = df["High"].tail(window).to_numpy(dtype=float)
        low = df["Low"].tail(window).to_numpy(dtype=float)
        if len(high) < window or len(low) < window:
            return 0.0
        if (not np.isfinite(high).all()) or (not np.isfinite(low).all()):
            return 0.0
        if (low <= 0).any():
            return 0.0

        ratios = high / low
        if (not np.isfinite(ratios).all()) or (ratios < 1.0).any():
            return 0.0
        value = (float(np.mean(ratios)) - 1.0) * 100.0
        if not np.isfinite(value) or value <= 0.0:
            return 0.0
        return float(value)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return 0.0


def distance_to_52w_high_pct(high, current_price, lookback: int = 252):
    """Fraction the current price sits below its trailing ``lookback``-bar high
    (e.g. -0.07 = 7% below the 52-week high); ``None`` when there is no valid high.

    One measurement shared by the fire's trend read and the health-board classifier, so the drawdown
    basis can never drift between them. A degenerate window (empty, non-positive, or all-NaN max)
    yields ``None`` rather than ``NaN``: the guard is ``not (max_high > 0)`` so a NaN max takes the
    ``None`` branch."""
    window = high.iloc[-min(lookback, len(high)):]
    max_high = float(window.max()) if len(window) else 0.0
    if not (max_high > 0):
        return None
    return (float(current_price) - max_high) / max_high


def trend_template(df, *, dist_52w_high_pct=None) -> dict:
    """Minervini Stage-2 trend-template criteria (measure-only, no opinion).

    The classic price/structure template, computed self-contained from df:
      1. price > SMA_150 and price > SMA_200
      2. SMA_150 > SMA_200
      3. SMA_200 trending up over the last ~1 month (21 bars)
      4. SMA_50 > SMA_150 > SMA_200
      5. price > SMA_50
      6. price >= 30% above the 52-week low
      7. price within 25% of the 52-week high

    Minervini's 8th criterion (RS rating >= 70, a universe percentile) is
    deliberately omitted — Chrollo measures relative strength SPY-relatively
    elsewhere and does not compute a universe rank — so the pass count is out
    of 7 and ``stage2_trend_pass`` means all 7.

    Returns a JSON-safe dict (un-prefixed keys). Every field is None/False-safe
    on insufficient (< 200 bars) or non-finite input — never raises, never NaN.
    """
    empty = {
        "stage2_ma_stack_pass": False,
        "stage2_ma200_slope_1m_pct": None,
        "stage2_52w_low_pct": None,
        "stage2_trend_pass_count": 0,
        "stage2_trend_pass": False,
    }
    try:
        if df is None or len(df) < 200 or "Close" not in df.columns:
            return empty
        close = df["Close"].astype(float)
        n = len(close)
        price = float(close.iloc[-1])
        sma50 = float(close.iloc[-50:].mean())
        sma150 = float(close.iloc[-150:].mean())
        sma200 = float(close.iloc[-200:].mean())
        if not all(np.isfinite(v) for v in (price, sma50, sma150, sma200)):
            return empty
        if price <= 0 or min(sma50, sma150, sma200) <= 0:
            return empty

        # 200-day MA slope over ~1 month (21 trading days), as a percent.
        slope_pct = None
        if n >= 221:
            sma200_prev = float(close.iloc[-221:-21].mean())
            if np.isfinite(sma200_prev) and sma200_prev > 0:
                slope_pct = (sma200 - sma200_prev) / sma200_prev * 100.0
                if not np.isfinite(slope_pct):
                    slope_pct = None

        # 52-week low distance (fraction above the 252-bar low).
        low_252 = float(df["Low"].iloc[-min(252, n):].min())
        low_pct = ((price - low_252) / low_252) if (np.isfinite(low_252) and low_252 > 0) else None

        c1 = price > sma150 and price > sma200
        c2 = sma150 > sma200
        c3 = slope_pct is not None and slope_pct > 0
        c4 = sma50 > sma150 > sma200
        c5 = price > sma50
        c6 = low_pct is not None and low_pct >= 0.30
        c7 = dist_52w_high_pct is not None and float(dist_52w_high_pct) >= -0.25
        count = int(sum(bool(c) for c in (c1, c2, c3, c4, c5, c6, c7)))

        return {
            "stage2_ma_stack_pass": bool(price > sma50 > sma150 > sma200),
            "stage2_ma200_slope_1m_pct": (round(slope_pct, 4) if slope_pct is not None else None),
            "stage2_52w_low_pct": (round(low_pct, 4) if low_pct is not None else None),
            "stage2_trend_pass_count": count,
            "stage2_trend_pass": bool(count == 7),
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return empty


_AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
_RULE = {"weekly": "W-FRI", "monthly": "ME"}


def resample_ohlc(df: pd.DataFrame, tf: str) -> Optional[pd.DataFrame]:
    """Resample a daily OHLCV frame to weekly (``W-FRI``) or monthly (``ME``).

    Keeps the latest (still-forming) period as the final bar. Returns None on
    an unusable frame.
    """
    rule = _RULE.get(tf)
    if rule is None:
        raise ValueError(f"unknown timeframe {tf!r}")
    if df is None or len(df) == 0:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        # Only coerce a genuinely date-like (string/object) index. A numeric index
        # would be silently epoch-coerced into 1970 and collapse every bar — skip it.
        if df.index.dtype != object:
            return None
        try:
            df = df.set_index(pd.to_datetime(df.index))
        except (ValueError, TypeError):
            return None
    cols = {c: how for c, how in _AGG.items() if c in df.columns}
    if not {"High", "Low", "Close"} <= set(cols):
        return None
    try:
        out = df.resample(rule).agg(cols)
    except (ValueError, KeyError):
        # Older pandas: 'ME'/'W-FRI' alias fallback.
        out = df.resample("M" if tf == "monthly" else "W").agg(cols)
    out = out.dropna(subset=["High", "Low", "Close"])
    return out if len(out) else None
