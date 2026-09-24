"""Task 4 — broad-market context sourcing for the small ETF universes.

For an ETF universe the breadth scoring input must be neutralized (degenerate over
10-40 names) and the SPY/regime context borrowed from the broad US-Stocks context
ONLY for the same trading session (no lookahead). These tests pin that behavior
with the file IO monkeypatched, so no real cache files are touched.
"""
from __future__ import annotations

import pandas as pd
import pytest

import core.pipeline.context.market_context as mc


def _etf_panel(asof: str) -> pd.DataFrame:
    idx = pd.date_range(end=asof, periods=4, freq="B")
    return pd.concat(
        {"GLD": pd.DataFrame({"Close": [1.0, 2.0, 3.0, 4.0], "Volume": [1, 1, 1, 1]}, index=idx)},
        axis=1,
    )


@pytest.fixture
def _no_write(monkeypatch):
    monkeypatch.setattr(mc, "_write_meta", lambda path, ctx: None)


def test_etf_context_neutralizes_breadth_and_borrows_when_session_matches(monkeypatch, _no_write):
    asof = "2026-06-25"
    broad = {
        "spy_6m_return": 0.123,
        "breadth_pct": 0.71,
        "regime": {"state": "UPTREND", "indexes": {}, "breadth_50_pct": 0.71},
        "spy_last_bar_date": asof,
    }
    monkeypatch.setattr(mc, "_read_meta", lambda path: broad)

    ctx = mc.get_market_context(_etf_panel(asof), {}, universe="commodities_etf")

    assert ctx["breadth_pct"] is None                 # neutralized -> 0 breadth bonus
    assert ctx["spy_6m_return"] == pytest.approx(0.123)  # borrowed broad SPY ref
    assert ctx["regime"]["state"] == "UPTREND"        # anchored to broad regime
    assert ctx["context_basis"] == "broad_market"


def test_etf_context_falls_back_to_neutral_on_session_mismatch(monkeypatch, _no_write):
    # Broad context is for an EARLIER session than this ETF scan -> borrowing it
    # would be lookahead, so the context must fall back to neutral.
    broad = {
        "spy_6m_return": 0.2,
        "regime": {"state": "UPTREND"},
        "spy_last_bar_date": "2026-06-20",
    }
    monkeypatch.setattr(mc, "_read_meta", lambda path: broad)

    ctx = mc.get_market_context(_etf_panel("2026-06-25"), {}, universe="commodities_etf")

    assert ctx["breadth_pct"] is None
    assert ctx["spy_6m_return"] == 0.0                # NOT borrowed
    assert ctx["regime"]["state"] == "NEUTRAL"
    assert ctx["context_basis"] == "neutral"


def test_etf_context_neutral_when_no_broad_context(monkeypatch, _no_write):
    monkeypatch.setattr(mc, "_read_meta", lambda path: {})  # broad context missing
    ctx = mc.get_market_context(_etf_panel("2026-06-25"), {}, universe="us_sectors")
    assert ctx["breadth_pct"] is None
    assert ctx["spy_6m_return"] == 0.0
    assert ctx["context_basis"] == "neutral"
