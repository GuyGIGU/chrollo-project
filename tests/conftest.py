"""Shared pytest fixtures for the core-logic test suite.

These are the frame-builder helpers that were previously redefined verbatim
across the (now split) ``test_core_logic.py`` modules. They are exposed as
factory fixtures: each fixture returns the builder function, so a test consumes
it by naming the fixture in its signature and calling it exactly as before
(e.g. ``_flat_ohlc(120)``). The builder bodies are unchanged.
"""

import pandas as pd
import pytest


@pytest.fixture
def _contraction_frame():
    """Build an OHLCV frame from a list of close levels (±0.5 High/Low band)."""
    def _build(levels, volumes):
        return pd.DataFrame({
            "High": [c + 0.5 for c in levels],
            "Low": [c - 0.5 for c in levels],
            "Close": list(levels),
            "Volume": list(volumes),
        })
    return _build


@pytest.fixture
def _lps_behavior_frame():
    def _build(highs, lows, closes=None):
        closes = closes or lows
        return pd.DataFrame([
            {
                "High": high,
                "Low": low,
                "Close": close,
                "Spread": high - low,
                "Volume": 500,
                "Vol_50": 1000,
            }
            for high, low, close in zip(highs, lows, closes)
        ])
    return _build


@pytest.fixture
def _ramp_frame():
    """Build a degenerate OHLC frame (High==Low==Close) that linearly ramps
    between the given pivot prices, so the zigzag pivots land predictably."""
    def _build(pivot_prices, bars_per_leg=6):
        prices = [float(pivot_prices[0])]
        for k in range(1, len(pivot_prices)):
            p0, p1 = float(pivot_prices[k - 1]), float(pivot_prices[k])
            for b in range(1, bars_per_leg + 1):
                prices.append(p0 + (p1 - p0) * b / bars_per_leg)
        return pd.DataFrame({"High": prices, "Low": prices, "Close": prices, "Open": prices})
    return _build


@pytest.fixture
def _cand():
    """Build a Phase-B candidate tuple (only combined [0] and cand_start [9]
    drive selection; the rest are placeholders)."""
    def _build(combined, cand_start, box_width=0.1):
        return (combined, 100.0, 90.0, box_width, 5, 5, 0, 10, 5, cand_start)
    return _build


@pytest.fixture
def _osc_frame():
    """OHLC frame with High/Low a fixed band around each close."""
    def _build(closes, band=1.0):
        return pd.DataFrame({
            "High": [c + band for c in closes],
            "Low": [c - band for c in closes],
            "Close": list(closes),
        })
    return _build


@pytest.fixture
def _flat_frame():
    """High == Low == Close, so a swing's amplitude is the raw close move (no
    band inflation) — needed to exercise genuinely sub-threshold reversals."""
    def _build(closes):
        return pd.DataFrame({"High": list(closes), "Low": list(closes), "Close": list(closes)})
    return _build


@pytest.fixture
def _flat_ohlc():
    """Uniform OHLC frame; callers mutate specific rows for region tests."""
    def _build(n, *, high=101.0, low=99.0, close=100.0, volume=1000.0):
        return pd.DataFrame([
            {"Open": close, "High": high, "Low": low, "Close": close, "Volume": volume}
            for _ in range(n)
        ])
    return _build


@pytest.fixture
def _scope_df():
    """A length-n OHLC-ish frame with a DatetimeIndex (Low + High are read)."""
    def _build(n=30, low=100.0):
        idx = pd.date_range("2026-01-01", periods=n, freq="D")
        return pd.DataFrame({"Low": [low] * n, "High": [low + 1.0] * n}, index=idx)
    return _build
