"""COPIED from engine_alpha/structure/indicators.py at cd87fcc (two-eyes-reader task 7): the daily range (ATR) — `_fast_ewm`, `_fast_ewm_valid`, `_true_range`, `calculate_atr`.

Verbatim, function for function, but for this: nothing — the original reads no setting, so not one token changed. The original stays in the old
engine, frozen, and the old engine keeps reading it; this copy is the new reader's, and changes on
purpose from here. tests/test_two_eyes_copies_equal_originals.py pinned the two equal once, on the
fixtures; the task that first changes this copy deletes that pin in the same commit.

The original's own documentation, unchanged:

Technical indicator calculations — ATR and ADX.
"""
import numpy as np
import pandas as pd
from scipy.signal import lfilter


def _fast_ewm(x, period):
    """Extremely fast Exponential Weighted Moving Average using IIR filter."""
    x_arr = np.asarray(x, dtype=float)
    isnan = np.isnan(x_arr)
    if isnan.any():
        # Handle nan padding from pandas (like diff() prepending nans)
        # Find first valid index
        valid_idx = np.where(~isnan)[0]
        if len(valid_idx) == 0:
            return x_arr
        first_valid = valid_idx[0]
        y = np.full_like(x_arr, np.nan)
        y[first_valid:] = _fast_ewm_valid(x_arr[first_valid:], period)
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
    """Average True Range using Wilder's exponential smoothing."""
    tr = _true_range(df)
    atr = _fast_ewm(tr, period)
    return pd.Series(atr, index=df.index)
