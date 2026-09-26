"""Indicator NaN contract — one bad price cell may not delete a whole read.

Council review 2026-09-07, finding 14: ``_fast_ewm`` masked only a LEADING NaN
run; an interior NaN entered the recursive filter and propagated to every later
sample, so a single bad OHLC cell anywhere in a two-year frame silently deleted
that ticker's chart read from that bar onward (every downstream
``_finite(atr)`` brick guard refused, with no counted reason).

These guards pin the contract:

1. an interior NaN is LOCAL — NaN at that bar, finite after it;
2. the leading-pad case, and the no-NaN case, stay BYTE-identical to the
   pre-fix read (the fix must be a strict superset, never a re-calibration);
3. ``calculate_atr`` and ``calculate_adx``, which share the helper, inherit it.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from engine_alpha.structure.metrics.indicators import (  # noqa: E402
    _fast_ewm,
    _fast_ewm_valid,
    calculate_adx,
    calculate_atr,
)


def _ramp(n=40, start=100.0, step=0.7):
    """A gently trending series — every bar readable."""
    return np.array([start + step * i for i in range(n)], dtype=float)


def _frame(closes, span=1.0):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "High": closes + span,
        "Low": closes - span,
        "Close": closes,
        "Open": closes,
    })


# --- 1. the interior hole is LOCAL ------------------------------------------

def test_interior_nan_does_not_poison_later_samples():
    x = _ramp(20)
    x[10] = np.nan
    y = _fast_ewm(x, 14)

    assert np.isnan(y[10]), "the unreadable bar must read NaN, never a guess"
    assert np.isfinite(y[11:]).all(), (
        "an interior NaN leaked into the IIR state and deleted the tail — "
        "the read must resume on the next readable bar")
    assert np.isfinite(y[:10]).all()


def test_several_interior_nans_stay_local():
    x = _ramp(30)
    for i in (5, 6, 17, 28):
        x[i] = np.nan
    y = _fast_ewm(x, 14)

    holes = np.zeros(len(x), dtype=bool)
    holes[[5, 6, 17, 28]] = True
    assert np.isnan(y[holes]).all()
    assert np.isfinite(y[~holes]).all()


def test_interior_nan_filters_over_the_valid_subsequence():
    """The masked read equals the filter run on the compacted valid samples."""
    x = _ramp(20)
    x[10] = np.nan
    y = _fast_ewm(x, 14)

    valid = np.flatnonzero(~np.isnan(x))
    expected = _fast_ewm_valid(x[valid], 14)
    assert np.allclose(y[valid], expected, rtol=0, atol=0)


# --- 2. the pre-fix behaviour that must NOT move ----------------------------

def test_no_nan_read_is_the_bare_filter():
    x = _ramp(25)
    assert np.allclose(_fast_ewm(x, 14), _fast_ewm_valid(x, 14), rtol=0, atol=0)


def test_leading_nan_pad_is_byte_identical_to_the_legacy_slice():
    """The docstring's own case: pandas' diff() pad. The legacy read filtered
    x[first_valid:]; masking must reproduce it EXACTLY, not approximately."""
    x = _ramp(20)
    x[:3] = np.nan
    y = _fast_ewm(x, 14)

    assert np.isnan(y[:3]).all()
    legacy = _fast_ewm_valid(x[3:], 14)
    assert np.allclose(y[3:], legacy, rtol=0, atol=0)


def test_all_nan_returns_the_input_untouched():
    x = np.full(12, np.nan)
    y = _fast_ewm(x, 14)
    assert np.isnan(y).all() and len(y) == 12


# --- 3. the two indicators that share the helper ----------------------------

def test_calculate_atr_survives_one_bad_price_cell():
    closes = _ramp(60)
    df = _frame(closes)
    df.loc[df.index[30], "High"] = np.nan

    atr = calculate_atr(df, period=14)
    tail = atr.iloc[32:]
    assert np.isfinite(tail.to_numpy()).all(), (
        "one bad High cell deleted the ATR to the right edge — every brick's "
        "_finite(atr) guard would refuse the whole ticker with no reason")
    # index 0 is the shifted-Close pad, NaN by construction, before and after.
    assert np.isfinite(atr.iloc[1:30].to_numpy()).all()


def test_calculate_adx_survives_one_bad_price_cell():
    closes = _ramp(80)
    df = _frame(closes)
    df.loc[df.index[40], "Low"] = np.nan

    adx = calculate_adx(df, period=14)
    tail = adx.iloc[43:]
    assert np.isfinite(tail.to_numpy()).all(), (
        "one bad Low cell deleted the ADX to the right edge")


def test_clean_frames_read_identically_through_both_indicators():
    """No NaN anywhere: the fix may not move a single value on real data."""
    closes = _ramp(80)
    df = _frame(closes)
    atr = calculate_atr(df, period=14).to_numpy()
    adx = calculate_adx(df, period=14).to_numpy()
    # index 0 is the shifted-Close / diff pad in both series (unchanged).
    assert np.isfinite(atr[1:]).all()
    assert np.isfinite(adx[1:]).all()
