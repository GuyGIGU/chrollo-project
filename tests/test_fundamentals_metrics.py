"""Offline unit tests for the 5-metric fundamentals layer (Lane C).

Pure-function tests over hand-built income-statement / earnings frames (no network,
no provider), plus one ``compute_metrics`` test with a fake provider object. They
pin: the YoY / acceleration / surprise math, the >= 5 / >= 6 quarter history
floors, and that missing / gappy / zero-base data degrades the affected metric to
``None`` without crashing or contaminating the others.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.fundamentals import metrics


def _income(eps=None, revenue=None):
    """Build a quarterly income statement, columns MOST-RECENT-FIRST.

    ``eps`` / ``revenue`` are lists ordered most-recent-first; their length sets
    the number of quarterly columns. Missing line item -> row omitted."""
    n = max(len(eps or []), len(revenue or []))
    cols = pd.date_range("2026-03-31", periods=n, freq="-3MS")
    data = {}
    if revenue is not None:
        data["Total Revenue"] = revenue
    if eps is not None:
        data["Diluted EPS"] = eps
    # Rows = line items, columns = dates.
    return pd.DataFrame({c: {k: data[k][i] for k in data} for i, c in enumerate(cols)})


# ── eps_growth_yoy / sales_growth_yoy ────────────────────────────────────────
def test_eps_growth_yoy_basic():
    # q0=1.20 vs q-4=1.00 -> +20%.
    stmt = _income(eps=[1.20, 1.15, 1.10, 1.05, 1.00])
    assert metrics.eps_growth_yoy(stmt) == pytest.approx(0.20)


def test_sales_growth_yoy_basic():
    stmt = _income(revenue=[120.0, 115.0, 110.0, 105.0, 100.0])
    assert metrics.sales_growth_yoy(stmt) == pytest.approx(0.20)


def test_yoy_shallow_history_is_none():
    # Only 4 quarters -> cannot do a YoY (needs the 5th, a year-ago quarter).
    stmt = _income(eps=[1.20, 1.15, 1.10, 1.05])
    assert metrics.eps_growth_yoy(stmt) is None


def test_yoy_negative_base_keeps_sign():
    # q0=0.50 vs q-4=-1.00 -> (0.50 - -1.00)/|−1.00| = +1.5 (turned profitable).
    stmt = _income(eps=[0.50, 0.0, -0.50, -0.80, -1.00])
    assert metrics.eps_growth_yoy(stmt) == pytest.approx(1.5)


def test_yoy_zero_base_is_none():
    stmt = _income(eps=[1.20, 1.0, 0.8, 0.5, 0.0])
    assert metrics.eps_growth_yoy(stmt) is None


def test_yoy_missing_eps_row_is_none():
    stmt = _income(revenue=[120.0, 115, 110, 105, 100])  # no EPS row
    assert metrics.eps_growth_yoy(stmt) is None


def test_yoy_gap_at_irrelevant_quarter_still_reads():
    # A NaN at an INTERMEDIATE quarter (q-1) doesn't touch the YoY cells (q0,q-4),
    # so positions are preserved and the read stands (no silent misalignment).
    stmt = _income(eps=[1.20, float("nan"), 1.10, 1.05, 1.00])
    assert metrics.eps_growth_yoy(stmt) == pytest.approx(0.20)


def test_yoy_gap_at_year_ago_cell_is_none():
    # A NaN AT the quarter-4-back cell -> the YoY base is missing -> None.
    stmt = _income(eps=[1.20, 1.15, 1.10, 1.05, float("nan")])
    assert metrics.eps_growth_yoy(stmt) is None


def test_yoy_empty_frame_is_none():
    assert metrics.eps_growth_yoy(pd.DataFrame()) is None
    assert metrics.sales_growth_yoy(pd.DataFrame()) is None


# ── eps_growth_accel ─────────────────────────────────────────────────────────
def test_eps_growth_accel_positive():
    # q0 vs q4: 1.50/1.00 -> +50%.  q1 vs q5: 1.20/1.00 -> +20%.  accel = +30%.
    stmt = _income(eps=[1.50, 1.20, 1.10, 1.05, 1.00, 1.00])
    assert metrics.eps_growth_accel(stmt) == pytest.approx(0.30)


def test_eps_growth_accel_needs_six_quarters():
    stmt = _income(eps=[1.50, 1.20, 1.10, 1.05, 1.00])  # only 5
    assert metrics.eps_growth_accel(stmt) is None


# ── earnings_surprise ────────────────────────────────────────────────────────
def test_earnings_surprise_from_percent_column():
    df = pd.DataFrame(
        {"EPS Estimate": [1.10], "Reported EPS": [1.20], "Surprise(%)": [9.1]},
        index=pd.to_datetime(["2026-04-15"]),
    )
    assert metrics.earnings_surprise(df) == pytest.approx(0.091)


def test_earnings_surprise_fallback_to_reported_minus_estimate():
    # No Surprise(%) column -> compute from reported vs estimate. (1.20-1.00)/1.00.
    df = pd.DataFrame(
        {"EPS Estimate": [1.00], "Reported EPS": [1.20]},
        index=pd.to_datetime(["2026-04-15"]),
    )
    assert metrics.earnings_surprise(df) == pytest.approx(0.20)


def test_earnings_surprise_skips_unreported_future_row():
    # Most-recent row has no reported EPS yet (future) -> fall to the next row.
    df = pd.DataFrame(
        {"EPS Estimate": [1.30, 1.00], "Reported EPS": [float("nan"), 1.20]},
        index=pd.to_datetime(["2026-07-15", "2026-04-15"]),
    )
    assert metrics.earnings_surprise(df) == pytest.approx(0.20)


def test_earnings_surprise_empty_is_none():
    assert metrics.earnings_surprise(pd.DataFrame()) is None


# ── compute_metrics (with a fake provider, no network) ───────────────────────
class _FakeProvider:
    def __init__(self, stmt, earnings):
        self._stmt = stmt
        self._earnings = earnings

    def get_income_stmt(self, ticker, *, quarterly=True):
        return self._stmt

    def get_earnings_dates(self, ticker, limit=12):
        return self._earnings


def test_compute_metrics_full():
    stmt = _income(
        eps=[1.50, 1.20, 1.10, 1.05, 1.00, 1.00],
        revenue=[120.0, 118, 115, 112, 100, 100],
    )
    earnings = pd.DataFrame(
        {"EPS Estimate": [1.10], "Reported EPS": [1.20], "Surprise(%)": [9.1]},
        index=pd.to_datetime(["2026-04-15"]),
    )
    out = metrics.compute_metrics(
        "AAA", rs_rating=87.5, provider=_FakeProvider(stmt, earnings)
    )
    assert out["eps_growth_yoy"] == pytest.approx(0.50)
    assert out["sales_growth_yoy"] == pytest.approx(0.20)
    assert out["eps_growth_accel"] == pytest.approx(0.30)
    assert out["earnings_surprise"] == pytest.approx(0.091)
    assert out["rs_rating"] == pytest.approx(87.5)


def test_compute_metrics_all_missing_is_all_none():
    out = metrics.compute_metrics(
        "ZZZ", provider=_FakeProvider(pd.DataFrame(), pd.DataFrame())
    )
    assert out == {
        "eps_growth_yoy": None,
        "sales_growth_yoy": None,
        "eps_growth_accel": None,
        "earnings_surprise": None,
        "rs_rating": None,
    }


def test_compute_metrics_partial_does_not_contaminate():
    # Good EPS history but NO earnings frame: 3 of 5 compute, surprise -> None.
    stmt = _income(eps=[1.50, 1.20, 1.10, 1.05, 1.00, 1.00])
    out = metrics.compute_metrics(
        "AAA", rs_rating=None, provider=_FakeProvider(stmt, pd.DataFrame())
    )
    assert out["eps_growth_yoy"] == pytest.approx(0.50)
    assert out["eps_growth_accel"] == pytest.approx(0.30)
    assert out["sales_growth_yoy"] is None      # no revenue row
    assert out["earnings_surprise"] is None     # no earnings frame
    assert out["rs_rating"] is None
