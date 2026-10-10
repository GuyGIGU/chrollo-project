"""COPIED from engine_alpha/structure/metrics/indicators.py at cd87fcc (two-eyes-reader task 7), RE-COPIED at 61c88cc (the port onto main, Sat 26/09/2026): the daily range (ATR) — `_fast_ewm`, `_fast_ewm_valid`, `_true_range`, `calculate_atr`.

Verbatim, function for function, but for this: nothing — the original reads no setting, so not one token changed. The re-copy carries the original's fix of 2026-09-07 (council review, finding 14): a missing price in the MIDDLE of a chart costs the day that has no previous close and no other, where the task-7 copy lost every later day. The original stays in the old
engine, frozen, and the old engine keeps reading it; this copy is the new reader's, and changes on
purpose from here. tests/engine/test_two_eyes_copies_equal_originals.py pinned the two equal once, on the
fixtures; the task that first changes this copy deletes that pin in the same commit.

The original's own documentation, unchanged:

Technical indicator calculations — ATR and ADX.
"""
import numpy as np
import pandas as pd
from scipy.signal import lfilter


def _fast_ewm(x, period):
    """Extremely fast Exponential Weighted Moving Average using IIR filter.

    NaN contract: every NaN sample — leading pad or interior hole — is masked
    OUT of the recursive filter, which runs over the valid subsequence and
    scatters its results back onto those positions. A NaN input bar therefore
    yields a NaN output bar (honest: no measurement where there is no data)
    and NOTHING else. It does NOT leak forward.

    Before 2026-09-07 only a LEADING NaN run was masked (the ``diff()`` pad the
    docstring named); one interior NaN entered ``lfilter``'s state and poisoned
    every later sample, so a single bad OHLC cell anywhere in a two-year frame
    silently deleted that ticker's whole chart read from that bar onward — the
    downstream ``_finite(atr)`` brick guards then refused everything with no
    counted reason (council review 2026-09-07, finding 14). Masking is a strict
    superset of the old handling: with no NaN, or a leading run only, the valid
    subsequence IS the old slice and the output is byte-identical.
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
    series resumes on the next readable bar instead of dying to the right edge
    (council review 2026-09-07, finding 14). Callers keep their own
    ``_finite(atr)`` guards — a NaN ATR is still a refusal, just a local one.
    """
    tr = _true_range(df)
    atr = _fast_ewm(tr, period)
    return pd.Series(atr, index=df.index)
