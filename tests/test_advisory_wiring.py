"""Offline tests for the Lane E advisory wiring.

Cover the flag-gated, null-safe ADVISORY metadata layer that attaches
fundamentals / RS-line / RS-rating / sector-rank as graded tag-chip data onto a
firing setup WITHOUT touching Score/Tier or the geometric veto:

  * flags OFF -> the per-ticker advisory returns ``{}`` and makes ZERO provider
    calls (the byte-identical guarantee at the unit level);
  * flags ON  -> the metrics are attached, point-in-time safe (no future quarter),
    via a fake provider AND via a fully yfinance-mocked provider;
  * the universe RS-rating post-pass ranks across the firing set;
  * the per-setup sector-rank mapping from the scan-wide ranking;
  * a missing/failed read degrades to an ABSENT key (never a chip, never a raise).

No network: a fake provider object or ``monkeypatch.setitem(sys.modules,
'yfinance', fake)``.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.fundamentals import advisory
from core.regime import scan_context


# ── Fakes ────────────────────────────────────────────────────────────────────
class _FakeProvider:
    """Records calls so a test can assert zero-call behavior when flags are off."""

    def __init__(self, *, stmt=None, earnings=None, next_earnings=None,
                 stock_close=None, bench_close=None):
        self._stmt = stmt if stmt is not None else pd.DataFrame()
        self._earnings = earnings if earnings is not None else pd.DataFrame()
        self._next_earnings = next_earnings
        self._stock_close = stock_close
        self._bench_close = bench_close
        self.calls: list[str] = []

    def get_income_stmt(self, ticker, *, quarterly=True):
        self.calls.append("get_income_stmt")
        return self._stmt

    def get_earnings_dates(self, ticker, limit=12):
        self.calls.append("get_earnings_dates")
        return self._earnings

    def earnings_date(self, ticker):
        self.calls.append("earnings_date")
        return self._next_earnings

    def daily_candles(self, symbol, days):
        self.calls.append(f"daily_candles:{symbol}")
        close = self._bench_close if symbol == "SPY" else self._stock_close
        if close is None:
            return pd.DataFrame()
        return pd.DataFrame({"Close": close})


def _income(end_dates, eps=None, revenue=None):
    cols = [pd.Timestamp(d) for d in end_dates]
    data = {}
    if revenue is not None:
        data["Total Revenue"] = revenue
    if eps is not None:
        data["Diluted EPS"] = eps
    return pd.DataFrame({c: {k: data[k][i] for k in data} for i, c in enumerate(cols)})


def _price_df(closes, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"Close": closes}, index=idx)


# ── flags OFF: empty + zero provider calls ───────────────────────────────────
def test_per_ticker_advisory_all_flags_off_is_empty(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", False, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)
    prov = _FakeProvider()
    out = advisory.per_ticker_advisory("AAA", _price_df([1.0] * 300), provider=prov)
    assert out == {}
    assert prov.calls == []  # no provider hit at all when flags are off


# ── FUNDAMENTALS_ENABLED on: point-in-time fundamentals attach ───────────────
def test_per_ticker_advisory_fundamentals_on(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)

    ends = ["2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"]
    eps = [9.99, 1.20, 1.10, 1.05, 1.00, 1.00]  # 9.99 = not-yet-filed future qtr
    rev = [200.0, 120.0, 118.0, 115.0, 100.0, 100.0]
    prov = _FakeProvider(stmt=_income(ends, eps=eps, revenue=rev), next_earnings="2026-05-01")

    df = _price_df([10.0] * 300)
    # as_of just after the 2025-12-31 quarter's filing window but BEFORE 2026-03-31's.
    out = advisory.per_ticker_advisory("AAA", df, as_of="2026-04-10", provider=prov)

    # YoY read off the latest AVAILABLE quarter (2025-12-31), not the leaking 9.99.
    assert out["_fund_eps_growth_yoy"] == pytest.approx(0.20)
    assert out["_fund_sales_growth_yoy"] == pytest.approx(0.20)
    # Only 5 quarters are available as of 2026-04-10 (the 9.99 future qtr is gated
    # out), and acceleration needs 6 -> it correctly degrades to an ABSENT key
    # rather than reaching back to a not-yet-filed quarter.
    assert "_fund_eps_growth_accel" not in out
    assert out["_days_to_earnings"] == (pd.Timestamp("2026-05-01") - pd.Timestamp("2026-04-10")).days


def test_per_ticker_advisory_accel_available_after_filing(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)

    ends = ["2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"]
    eps = [1.50, 1.20, 1.10, 1.05, 1.00, 1.00]
    prov = _FakeProvider(stmt=_income(ends, eps=eps))
    # as_of well after 2026-03-31's filing window -> all 6 quarters available.
    out = advisory.per_ticker_advisory("AAA", _price_df([10.0] * 300),
                                       as_of="2026-07-01", provider=prov)
    # q0 vs q4: 1.50/1.00=+50%; q1 vs q5: 1.20/1.00=+20%; accel=+30%.
    assert out["_fund_eps_growth_accel"] == pytest.approx(0.30)


def test_per_ticker_advisory_fundamentals_missing_is_absent(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)
    prov = _FakeProvider(stmt=pd.DataFrame(), earnings=pd.DataFrame(), next_earnings=None)
    out = advisory.per_ticker_advisory("ZZZ", _price_df([5.0] * 300), as_of="2026-04-10", provider=prov)
    # No fundamentals keys at all (missing -> absent, never a penalty value).
    assert not any(k.startswith("_fund_") for k in out)
    assert "_days_to_earnings" not in out


# ── RS_LINE_ENABLED on ───────────────────────────────────────────────────────
def test_per_ticker_advisory_rs_line_on(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", False, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", True, raising=False)
    # Stock outpaces bench at the end -> RS line at a new high.
    stock = [10.0 + i * 0.05 for i in range(300)]
    bench = [100.0] * 300
    prov = _FakeProvider(stock_close=stock, bench_close=bench)
    out = advisory.per_ticker_advisory("AAA", _price_df(stock), provider=prov)
    assert out["_rs_line_new_high"] is True
    assert out["_rs_line_latest"] is not None


# ── yfinance fully mocked (brief's explicit requirement) ─────────────────────
def test_per_ticker_advisory_with_mocked_yfinance(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)

    ends = pd.to_datetime(["2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"])
    stmt = pd.DataFrame({
        ends[0]: {"Total Revenue": 120.0, "Diluted EPS": 1.20},
        ends[1]: {"Total Revenue": 118.0, "Diluted EPS": 1.10},
        ends[2]: {"Total Revenue": 115.0, "Diluted EPS": 1.05},
        ends[3]: {"Total Revenue": 112.0, "Diluted EPS": 1.02},
        ends[4]: {"Total Revenue": 100.0, "Diluted EPS": 1.00},
    })

    class _Ticker:
        def __init__(self, symbol):
            self.symbol = symbol
            self.quarterly_income_stmt = stmt
            # Next earnings ~3 weeks out -> a positive days_to_earnings.
            self.calendar = {"Earnings Date": [pd.Timestamp("2026-06-22")]}

        def get_earnings_dates(self, limit=12):
            return pd.DataFrame()

    fake_yf = SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    from core.pipeline.providers import YahooProvider

    out = advisory.per_ticker_advisory(
        "AAA", _price_df([10.0] * 300), as_of="2026-06-01", provider=YahooProvider()
    )
    # 2025-12-31 quarter is filed by 2026-06-01 -> YoY 1.20 vs 1.00 = +20%.
    assert out["_fund_eps_growth_yoy"] == pytest.approx(0.20)
    # Next earnings 2026-06-22 minus as_of 2026-06-01 = 21 days forward.
    assert out["_days_to_earnings"] == 21


# ── universe RS-rating post-pass ─────────────────────────────────────────────
def test_attach_rs_ratings_ranks_across_firing_set(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    results = [
        {"Ticker": "LOW", "_rs_trailing_return": 0.05},
        {"Ticker": "MID", "_rs_trailing_return": 0.20},
        {"Ticker": "HIGH", "_rs_trailing_return": 0.50},
        {"Ticker": "NONE"},  # no trailing return -> no rating
    ]
    scan_context.attach_rs_ratings(results)
    assert results[0]["_rs_rating"] < results[1]["_rs_rating"] < results[2]["_rs_rating"]
    assert "_rs_rating" not in results[3]


def test_attach_rs_ratings_off_is_noop(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", False, raising=False)
    results = [{"Ticker": "A", "_rs_trailing_return": 0.1}]
    scan_context.attach_rs_ratings(results)
    assert "_rs_rating" not in results[0]


# ── per-setup sector-rank fields ─────────────────────────────────────────────
def test_sector_rank_fields_maps_position_and_pct():
    ranking = {"composite": {"XLK": 0.90, "XLF": 0.10}, "ranked": ["XLK", "XLF"]}
    out = scan_context.sector_rank_fields("XLK", ranking)
    assert out["_sector_rank_pct"] == pytest.approx(0.90)
    assert out["_sector_rank_pos"] == 1  # strongest sector = position 1


def test_sector_rank_fields_unknown_etf_is_empty():
    ranking = {"composite": {"XLK": 0.90}, "ranked": ["XLK"]}
    assert scan_context.sector_rank_fields("XLE", ranking) == {}
    assert scan_context.sector_rank_fields(None, ranking) == {}
    assert scan_context.sector_rank_fields("XLK", {}) == {}


# ── _evaluate_ticker attaches advisory without breaking the result ───────────
def test_evaluate_ticker_attaches_advisory_in_place(monkeypatch):
    """The live wrapper attaches advisory metadata onto a firing result; with
    flags off it adds nothing (the byte-identical path)."""
    from engine_alpha import evaluation

    sentinel = {"Ticker": "AAA", "Score": 100.0, "Tier": "S"}
    monkeypatch.setattr(evaluation, "_run_eval_chain", lambda *a, **k: dict(sentinel))

    from config import settings
    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", False, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)

    out = evaluation._evaluate_ticker("AAA", _price_df([1.0] * 300))
    assert out == sentinel  # flags off -> no advisory keys added


def test_evaluate_ticker_advisory_failure_does_not_drop_setup(monkeypatch):
    """If the advisory layer raises, the firing setup is STILL returned intact —
    advisory can never veto geometry."""
    from engine_alpha import evaluation

    fired = {"Ticker": "AAA", "Score": 100.0, "Tier": "S"}
    monkeypatch.setattr(evaluation, "_run_eval_chain", lambda *a, **k: dict(fired))

    def _boom(*a, **k):
        raise RuntimeError("advisory blew up")

    monkeypatch.setattr("core.fundamentals.advisory.per_ticker_advisory", _boom)
    out = evaluation._evaluate_ticker("AAA", _price_df([1.0] * 300))
    assert out["Score"] == 100.0 and out["Tier"] == "S"
