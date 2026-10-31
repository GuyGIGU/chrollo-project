"""The stock's own facts, not the box's: ADR%, the distance to the 52-week high, Minervini's trend template, the
weekly and monthly resample, and the weekly stage (1 to 4) with the week its advance began. They ride the row.
"""
from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
from scipy.signal import lfilter
from engine_alpha import numbers as M
from engine_alpha.chart import NYSE_BUSINESS_DAY


def adr_pct(df, window: int = 20) -> float:
    """Average Daily Range % over the last ``window`` bars: 100 * (SMA(High / Low) - 1), a plain percent such as 6.2;
    0.0 on degenerate or non-finite input, so no JSON ever receives NaN."""
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
    """The fraction the current price sits below its trailing ``lookback``-bar high (-0.07 = 7% below); ``None`` with no
    valid high (the guard is ``not (max_high > 0)``, so a NaN max takes the ``None`` branch)."""
    window = high.iloc[-min(lookback, len(high)):]
    max_high = float(window.max()) if len(window) else 0.0
    if not (max_high > 0):
        return None
    return (float(current_price) - max_high) / max_high

def trend_template(df, *, dist_52w_high_pct=None) -> dict:
    """Minervini's Stage-2 trend template, seven criteria measured on ``df`` (the RS-rating eighth is left out): a
    JSON-safe dict, None/False-safe under 200 bars or on non-finite input, never raising."""
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
    """Resample a daily OHLCV frame to weekly (``W-FRI``) or monthly (``ME``), the forming period kept as the last bar;
    None on an unusable frame."""
    rule = _RULE.get(tf)
    if rule is None:
        raise ValueError(f"unknown timeframe {tf!r}")
    if df is None or len(df) == 0:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        # Only a date-like (object) index is coerced: a numeric one would be epoch-coerced into 1970.
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


#: The facts this read gives, under the archive's names, each empty when not measured.
STAGE_FACTS = ("cycle_stage", "advance_start", "advance_weeks")

_WEEK = "W-FRI"

def _empty() -> dict:
    return {key: None for key in STAGE_FACTS}

def completed_weeks(daily: pd.DataFrame) -> pd.DataFrame:
    """The daily frame's weekly bars (weeks ending Friday), the forming week left out: a week is complete when the next
    trading session falls in a later week, so a week whose Friday is a holiday is complete on its Thursday."""
    index = pd.DatetimeIndex(daily.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    bars = pd.DataFrame({"High": daily["High"].to_numpy(float), "Low": daily["Low"].to_numpy(float),
                         "Close": daily["Close"].to_numpy(float)}, index=index)
    weeks = bars.resample(_WEEK).agg({"High": "max", "Low": "min", "Close": "last"})
    weeks = weeks.dropna(subset=["High", "Low", "Close"])
    if len(weeks):
        read_day = index[-1].normalize()
        next_session = read_day + NYSE_BUSINESS_DAY
        if next_session.to_period(_WEEK) == read_day.to_period(_WEEK):
            weeks = weeks.iloc[:-1]
    return weeks

def stages(weeks: pd.DataFrame) -> list:
    """The stage of every completed week (1 to 4), None where the average or its month-back value is not there
    yet. A week's stage reads that week and the last advance or decline week before it, never a later week."""
    span, slope = int(M.STAGE_MA_WEEKS), int(M.STAGE_SLOPE_WEEKS)
    close = weeks["Close"].to_numpy(float)
    average = weeks["Close"].rolling(span).mean().to_numpy(float)
    low_52 = weeks["Low"].rolling(int(M.STAGE_LOW_WEEKS), min_periods=1).min().to_numpy(float)
    off_low = 1.0 + float(M.STAGE_OFF_LOW_MIN)
    out, last = [None] * len(weeks), None
    for i in range(slope, len(weeks)):
        now, before = average[i], average[i - slope]
        if not (np.isfinite(now) and np.isfinite(before)):
            continue
        rising, falling = now > before, now < before
        if close[i] > now and rising and close[i] >= off_low * low_52[i]:
            last = "advance"
        elif close[i] < now and falling:
            last = "decline"
            out[i] = 4
            continue
        if last == "advance":
            out[i] = 2 if rising else 3
        else:
            out[i] = 1
    return out

def advance_start(weeks: pd.DataFrame, upto: int):
    """The position of the week the advance began, as of the completed week ``upto``: the week after the last weekly
    close under a 40-week average not rising; None with no such close, ``upto + 1`` when the week read closed under one."""
    close = weeks["Close"].to_numpy(float)
    average = weeks["Close"].rolling(int(M.STAGE_MA_WEEKS)).mean().to_numpy(float)
    start = None
    for i in range(1, upto + 1):
        if np.isfinite(average[i]) and np.isfinite(average[i - 1]) \
                and close[i] < average[i] and average[i] <= average[i - 1]:
            start = i + 1
    return start

def read_stage(daily: pd.DataFrame) -> dict:
    """The stage read of one stock on its frame's last day: ``cycle_stage`` (1 to 4), ``advance_start`` (ISO Friday) and
    ``advance_weeks``, each None when not measured; read on the whole frame, never the two-year window; never raises."""
    out = _empty()
    try:
        weeks = completed_weeks(daily)
        if len(weeks) <= int(M.STAGE_MA_WEEKS):
            return out
        stage = stages(weeks)[-1]
        out["cycle_stage"] = stage
        if stage == 2:
            last = len(weeks) - 1
            start = advance_start(weeks, last)
            if start is not None and start <= last:
                out["advance_start"] = weeks.index[start].date().isoformat()
                out["advance_weeks"] = last - start + 1
    except (KeyError, TypeError, ValueError, IndexError):
        return _empty()
    return out
