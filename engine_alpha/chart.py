"""Stage 1, the chart: the frame contract and the reading window (``check``, ``prepare``), the daily range
(the ATR the whole reader measures in — the ONE copy) and the NYSE calendar the contract reads gaps against.
"""
from __future__ import annotations

import pandas as pd
from engine_alpha import numbers as M
import numpy as np
from scipy.signal import lfilter
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
    sunday_to_monday,
)
from pandas.tseries.offsets import CustomBusinessDay


OHLC = ("Open", "High", "Low", "Close")

#: The column that carries each day's range once a frame is prepared; the line's floors read it by this name.
DAILY_RANGE = "ATR_10"

class FrameRefused(ValueError):
    """A chart that may not be read, and why, in one sentence; ``rule`` is the rule's name alone, so a night can
    count its refusals by rule."""
    rule: str = ""

def _refuse(rule: str, detail: str) -> None:
    refusal = FrameRefused(f"{rule}: {detail}")
    refusal.rule = rule
    raise refusal

def check(df: pd.DataFrame) -> None:
    """Refuse a frame no reader should be asked to read (returns None or raises): shape, then time, then the bars,
    so the first refusal is the most basic thing wrong."""
    if df is None or len(df) == 0:
        _refuse("empty frame", "no bars at all")

    missing = [c for c in OHLC if c not in df.columns]
    if missing:
        _refuse("missing column(s)", ", ".join(missing))

    index = df.index
    if not isinstance(index, pd.DatetimeIndex):
        _refuse("index is not dates", f"got {type(index).__name__}")
    if index.hasnans:
        _refuse("index has a missing date", "at least one day is NaT")

    # The WHOLE index first: a pairwise walk would blame the first gap it tripped over, not the frame.
    if not index.is_monotonic_increasing:
        for position in range(1, len(index)):
            if index[position] < index[position - 1]:
                _refuse("days out of order",
                        f"{index[position].date()} comes after "
                        f"{index[position - 1].date()}")

    for position in range(1, len(index)):
        before, after = index[position - 1], index[position]
        # The DAY, not the timestamp: 09:30 and 16:00 on one date are one day.
        if after.normalize() == before.normalize():
            _refuse("the same day twice", f"{after.date()} appears at "
                                          f"{position - 1} and {position}")
        gap = session_gap(before, after)
        if gap > 1:
            _refuse("a trading day is missing from the middle",
                    f"{gap - 1} session(s) between {before.date()} and "
                    f"{after.date()}")

    bad_bar = df[df["High"] < df["Low"]]
    if len(bad_bar):
        day = bad_bar.index[0]
        _refuse("a high under its low",
                f"{day.date()}: high {float(bad_bar.iloc[0]['High'])} < "
                f"low {float(bad_bar.iloc[0]['Low'])}")

    holed = df[df[list(OHLC)].isna().any(axis=1)]
    if len(holed):
        _refuse("a bar with a missing number",
                f"{holed.index[0].date()} — this is dropped upstream today, so "
                "its arrival here means the prep was bypassed")

def _trim_to_period(data: pd.DataFrame, period: str) -> pd.DataFrame:
    """Trim DataFrame index to the trailing period window (e.g., '2y')."""
    if data.empty:
        return data
    if period.endswith('y'):
        years = int(period[:-1])
        cutoff = data.index.max() - pd.Timedelta(days=365 * years + 5)
    elif period.endswith('mo'):
        months = int(period[:-2])
        cutoff = data.index.max() - pd.Timedelta(days=30 * months + 2)
    else:
        return data
    return data.loc[data.index >= cutoff]

def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """A chart made ready to read, in this order: the contract (``check``), each day's range on the LONG frame so
    the unit warms up before the window, then the cut to the reading window with the ranges carried. Returns a copy."""
    check(df)
    out = df.copy()
    out[DAILY_RANGE] = calculate_atr(out, M.DAILY_RANGE_DAYS)
    return _trim_to_period(out, M.READ_WINDOW)


def _fast_ewm(x, period):
    """Exponential moving average by IIR filter; every NaN sample is masked out and stays NaN, never leaking forward."""
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
    """True Range, vectorized."""
    high = df['High'].values
    low = df['Low'].values
    prev_close = df['Close'].shift(1).values
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    return np.maximum(tr1, np.maximum(tr2, tr3))

def calculate_atr(df, period=14):
    """Average True Range with Wilder's smoothing; a bar with a missing cell is NaN there and the series resumes after it."""
    tr = _true_range(df)
    atr = _fast_ewm(tr, period)
    return pd.Series(atr, index=df.index)


class NyseHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01",
                observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas Day", month=12, day=25, observance=nearest_workday),
    ]

#: Days the NYSE closed that no rule predicts — funerals, disasters, attacks — so they are listed.
UNSCHEDULED_CLOSURES = (
    "2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14",  # the attacks
    "2004-06-11",   # President Reagan's funeral
    "2007-01-02",   # President Ford's funeral
    "2012-10-29", "2012-10-30",     # Hurricane Sandy
    "2018-12-05",   # President Bush's funeral
    "2025-01-09",   # President Carter's National Day of Mourning
)

NYSE_BUSINESS_DAY = CustomBusinessDay(
    calendar=NyseHolidayCalendar(),
    holidays=[pd.Timestamp(day) for day in UNSCHEDULED_CLOSURES],
)

def normalize_session_date(day) -> pd.Timestamp:
    return pd.Timestamp(day).normalize()

def is_trading_session(day) -> bool:
    day = normalize_session_date(day)
    return not pd.date_range(day, day, freq=NYSE_BUSINESS_DAY).empty

def session_gap(last_session, expected_session) -> int:
    """How many trading sessions separate two days. Consecutive days give 1."""
    last_session = normalize_session_date(last_session)
    expected_session = normalize_session_date(expected_session)
    if last_session >= expected_session:
        return 0
    return max(0, len(pd.date_range(last_session, expected_session,
                                    freq=NYSE_BUSINESS_DAY)) - 1)
