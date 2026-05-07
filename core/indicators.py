"""
Technical indicator calculations — ATR and ADX.
"""
import pandas as pd
import numpy as np
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


def calculate_adx(df, period=14):
    """Average Directional Index using Wilder's smoothing."""
    high = df['High'].values
    low = df['Low'].values

    # Prepend nan to match shift(1) format
    high_diff = np.insert(np.diff(high), 0, np.nan)
    low_diff = np.insert(np.diff(low), 0, np.nan)
    
    plus_dm = np.where((high_diff > -low_diff) & (high_diff > 0), high_diff, 0.0)
    minus_dm = np.where((-low_diff > high_diff) & (-low_diff > 0), -low_diff, 0.0)

    tr = _true_range(df)
    atr = _fast_ewm(tr, period)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        plus_di = 100 * (_fast_ewm(plus_dm, period) / atr)
        minus_di = 100 * (_fast_ewm(minus_dm, period) / atr)
        
        dx = 100 * (np.abs(plus_di - minus_di) / (plus_di + minus_di))
        
    adx = _fast_ewm(dx, period)

    return pd.Series(adx, index=df.index)

