"""Offline unit tests for the NEW YahooProvider fundamentals accessors (Lane C).

``info`` / ``get_income_stmt`` / ``get_earnings_dates`` wrap yfinance's modern
fundamentals surfaces behind the SAME daemon-thread wall-clock bound used by the
Track C capability methods. These tests mock yfinance entirely (never touch the
network) and assert: output shaping, miss -> empty/{} default, and that a
simulated hang falls back promptly instead of stalling.
"""
import sys
import time
from types import SimpleNamespace

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

import core.pipeline.market_data.providers as providers_module
from core.pipeline.market_data.providers import YahooProvider


class _FakeYF:
    def __init__(self, ticker):
        self._ticker = ticker

    def Ticker(self, symbol):  # noqa: N802 — mirror yfinance's capitalization
        return self._ticker(symbol)


@pytest.fixture
def fake_yf(monkeypatch):
    def _install(ticker):
        fake = _FakeYF(ticker)
        monkeypatch.setitem(sys.modules, "yfinance", fake)
        return fake
    return _install


def _income_frame():
    """A quarterly income statement: rows = line items, columns = period-end
    dates MOST-RECENT-FIRST (yfinance's native order)."""
    cols = pd.to_datetime(["2026-03-31", "2025-12-31", "2025-09-30"])
    return pd.DataFrame(
        {
            cols[0]: {"Total Revenue": 120.0, "Diluted EPS": 1.20},
            cols[1]: {"Total Revenue": 110.0, "Diluted EPS": 1.10},
            cols[2]: {"Total Revenue": 100.0, "Diluted EPS": 1.00},
        }
    )


def _earnings_frame():
    idx = pd.to_datetime(["2026-04-15", "2026-01-15"])
    return pd.DataFrame(
        {"EPS Estimate": [1.10, 1.00], "Reported EPS": [1.20, 1.05], "Surprise(%)": [9.1, 5.0]},
        index=idx,
    )


# ── info ────────────────────────────────────────────────────────────────────
def test_info_returns_dict(fake_yf):
    fake_yf(lambda s: SimpleNamespace(info={"sector": "Technology", "trailingPE": 30.0}))
    out = YahooProvider().info("AAA")
    assert out["sector"] == "Technology"
    assert out["trailingPE"] == 30.0


def test_info_empty_returns_empty_dict(fake_yf):
    fake_yf(lambda s: SimpleNamespace(info={}))
    assert YahooProvider().info("AAA") == {}


def test_info_failure_returns_empty_dict(fake_yf):
    def _boom(s):
        raise RuntimeError("info scrape failed")

    fake_yf(_boom)
    assert YahooProvider().info("AAA") == {}


# ── get_income_stmt ──────────────────────────────────────────────────────────
def test_income_stmt_quarterly_shape(fake_yf):
    fake_yf(lambda s: SimpleNamespace(quarterly_income_stmt=_income_frame()))
    out = YahooProvider().get_income_stmt("AAA", quarterly=True)
    assert not out.empty
    assert "Diluted EPS" in out.index
    # Most-recent column first.
    assert float(out.loc["Total Revenue"].iloc[0]) == 120.0


def test_income_stmt_annual_branch(fake_yf):
    fake_yf(lambda s: SimpleNamespace(income_stmt=_income_frame(), quarterly_income_stmt=pd.DataFrame()))
    out = YahooProvider().get_income_stmt("AAA", quarterly=False)
    assert not out.empty
    assert "Total Revenue" in out.index


def test_income_stmt_empty_returns_empty_frame(fake_yf):
    fake_yf(lambda s: SimpleNamespace(quarterly_income_stmt=pd.DataFrame()))
    out = YahooProvider().get_income_stmt("ZZZ")
    assert isinstance(out, pd.DataFrame) and out.empty


def test_income_stmt_failure_returns_empty_frame(fake_yf):
    def _boom(s):
        raise RuntimeError("statement fetch failed")

    fake_yf(_boom)
    out = YahooProvider().get_income_stmt("AAA")
    assert isinstance(out, pd.DataFrame) and out.empty


def test_income_stmt_hang_returns_empty_promptly(fake_yf, monkeypatch):
    monkeypatch.setattr(providers_module, "_INFO_TIMEOUT_S", 0.05)

    class _Hang:
        @property
        def quarterly_income_stmt(self):
            time.sleep(5)
            return _income_frame()

    fake_yf(lambda s: _Hang())
    started = time.monotonic()
    out = YahooProvider().get_income_stmt("AAA")
    elapsed = time.monotonic() - started
    assert out.empty
    assert elapsed < 2.0


# ── get_earnings_dates ───────────────────────────────────────────────────────
def test_earnings_dates_shape(fake_yf):
    captured = {}

    def _make(symbol):
        def _get(limit):
            captured["limit"] = limit
            return _earnings_frame()
        return SimpleNamespace(get_earnings_dates=_get)

    fake_yf(_make)
    out = YahooProvider().get_earnings_dates("AAA", limit=8)
    assert not out.empty
    assert captured["limit"] == 8
    assert "Reported EPS" in out.columns


def test_earnings_dates_empty_returns_empty_frame(fake_yf):
    fake_yf(lambda s: SimpleNamespace(get_earnings_dates=lambda limit: pd.DataFrame()))
    out = YahooProvider().get_earnings_dates("ZZZ")
    assert isinstance(out, pd.DataFrame) and out.empty


def test_earnings_dates_failure_returns_empty_frame(fake_yf):
    def _boom(s):
        raise RuntimeError("earnings fetch failed")

    fake_yf(_boom)
    out = YahooProvider().get_earnings_dates("AAA")
    assert isinstance(out, pd.DataFrame) and out.empty
