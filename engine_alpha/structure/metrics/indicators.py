"""
Technical indicator calculations — ATR and ADX.

The ATR family, ADR%, the 52-week-high distance and the trend template moved to ``engine_alpha/metrics.py``
(the pieces the reader borrows); they are imported back here so every old import path still resolves.
"""
import pandas as pd
import numpy as np

from engine_alpha.metrics import (  # noqa: F401
    _fast_ewm,
    _fast_ewm_valid,
    _true_range,
    adr_pct,
    calculate_atr,
    distance_to_52w_high_pct,
    trend_template,
)


def calculate_adx(df, period=14):
    """Average Directional Index using Wilder's smoothing.

    Shares ``_fast_ewm``, so it inherits the same NaN contract: a missing OHLC
    cell reads NaN in ATR, then in +DI/-DI, then in DX, and the final smoothing
    masks that bar out rather than carrying the NaN to the right edge (council
    review 2026-09-07, finding 14). Known bounded residual, deliberately NOT
    changed here: the ``np.insert(..., np.nan)`` pad makes the directional
    movement of an unreadable bar compare False and land on 0.0 — Wilder's
    correct convention for bar 0 ("no previous bar"), a mild fabrication for an
    interior hole. Re-typing it would move ADX on every ticker, and the live
    pipeline drops incomplete rows before evaluation.
    """
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
