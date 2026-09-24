"""Offline tests for the Lane E advisory wiring.

Cover the flag-gated, null-safe ADVISORY metadata layer that attaches
fundamentals / RS-line / RS-rating / sector-rank as graded tag-chip data onto a
firing setup WITHOUT touching Score/Tier or the geometric veto. The assembly
under test is the conductor post-pass (``core.fundamentals.post_pass``) — the
old in-worker ``per_ticker_advisory`` was retired 2026-08-17 (council review,
EC-3), and this battery moved WITH the assembly so it can never again stay
green against a builder nothing calls:

  * flags OFF -> the post-pass returns ``None`` and makes ZERO provider calls
    (the byte-identical guarantee at the unit level);
  * flags ON  -> the metrics attach, point-in-time safe (no future quarter),
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

from core.fundamentals import advisory, post_pass
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


def _price_df(closes, end="2026-04-10"):
    # The post-pass derives each ticker's as-of from its frame's LAST bar —
    # frames are built ending on the date the old explicit as_of named.
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"Close": closes}, index=idx)


def _post(results, frames, prov, tmp_path, monkeypatch, *, fund, rs):
    from config import settings
    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", fund, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", rs, raising=False)
    return post_pass.attach_fundamentals_post_pass(
        results, frames, provider=prov,
        cache_path=str(tmp_path / "fund_cache.json"))


# ── flags OFF: None + zero provider calls ────────────────────────────────────
def test_all_flags_off_is_none_and_zero_calls(tmp_path, monkeypatch):
    prov = _FakeProvider()
    results = [{"Ticker": "AAA"}]
    out = _post(results, {"AAA": _price_df([1.0] * 300)}, prov, tmp_path,
                monkeypatch, fund=False, rs=False)
    assert out is None
    assert results == [{"Ticker": "AAA"}]
    assert prov.calls == []  # no provider hit at all when flags are off


# ── FUNDAMENTALS_ENABLED on: point-in-time fundamentals attach ───────────────
def test_fundamentals_on_attaches_point_in_time(tmp_path, monkeypatch):
    ends = ["2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"]
    eps = [9.99, 1.20, 1.10, 1.05, 1.00, 1.00]  # 9.99 = not-yet-filed future qtr
    rev = [200.0, 120.0, 118.0, 115.0, 100.0, 100.0]
    prov = _FakeProvider(stmt=_income(ends, eps=eps, revenue=rev), next_earnings="2026-05-01")

    # as_of (frame end) just after the 2025-12-31 quarter's filing window but
    # BEFORE 2026-03-31's.
    row = {"Ticker": "AAA"}
    _post([row], {"AAA": _price_df([10.0] * 300, end="2026-04-10")}, prov,
          tmp_path, monkeypatch, fund=True, rs=False)

    # YoY read off the latest AVAILABLE quarter (2025-12-31), not the leaking 9.99.
    assert row["_fund_eps_growth_yoy"] == pytest.approx(0.20)
    assert row["_fund_sales_growth_yoy"] == pytest.approx(0.20)
    # Only 5 quarters are available as of 2026-04-10 (the 9.99 future qtr is gated
    # out), and acceleration needs 6 -> it correctly degrades to an ABSENT key
    # rather than reaching back to a not-yet-filed quarter.
    assert "_fund_eps_growth_accel" not in row
    assert row["_days_to_earnings"] == (pd.Timestamp("2026-05-01") - pd.Timestamp("2026-04-10")).days
    # The next-earnings date is fetched ONCE; days-to-earnings is arithmetic
    # on it, never a second provider call (2026-08-17 review, Performance).
    assert prov.calls.count("earnings_date") == 1


def test_accel_available_after_filing(tmp_path, monkeypatch):
    ends = ["2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"]
    eps = [1.50, 1.20, 1.10, 1.05, 1.00, 1.00]
    prov = _FakeProvider(stmt=_income(ends, eps=eps))
    # as_of well after 2026-03-31's filing window -> all 6 quarters available.
    row = {"Ticker": "AAA"}
    _post([row], {"AAA": _price_df([10.0] * 300, end="2026-07-01")}, prov,
          tmp_path, monkeypatch, fund=True, rs=False)
    # q0 vs q4: 1.50/1.00=+50%; q1 vs q5: 1.20/1.00=+20%; accel=+30%.
    assert row["_fund_eps_growth_accel"] == pytest.approx(0.30)


def test_fundamentals_missing_is_absent(tmp_path, monkeypatch):
    prov = _FakeProvider(stmt=pd.DataFrame(), earnings=pd.DataFrame(), next_earnings=None)
    row = {"Ticker": "ZZZ"}
    counts = _post([row], {"ZZZ": _price_df([5.0] * 300)}, prov, tmp_path,
                   monkeypatch, fund=True, rs=False)
    # No fundamentals keys at all (missing -> absent, never a penalty value),
    # and the failure is VISIBLE on the counter block.
    assert not any(k.startswith("_fund_") for k in row)
    assert "_days_to_earnings" not in row
    assert counts["attempted"] == 1 and counts["populated"] == 0
    assert counts["failed"] == 1


# ── RS_LINE_ENABLED on ───────────────────────────────────────────────────────
def test_rs_line_on_attaches_and_counts(tmp_path, monkeypatch):
    # Stock outpaces bench at the end -> RS line at a new high.
    stock = [10.0 + i * 0.05 for i in range(300)]
    bench = [100.0] * 300
    prov = _FakeProvider(stock_close=stock, bench_close=bench)
    row = {"Ticker": "AAA"}
    counts = _post([row], {"AAA": _price_df(stock)}, prov, tmp_path,
                   monkeypatch, fund=False, rs=True)
    assert row["_rs_line_new_high"] is True
    assert row["_rs_line_latest"] is not None
    # The RS-line half carries its OWN attempted/populated pair — a 0-of-N
    # silence on this half must be visible (2026-08-17 review, Ramírez).
    assert counts["rs_attempted"] == 1 and counts["rs_populated"] == 1


def test_rs_line_failure_is_counted_not_raised(tmp_path, monkeypatch):
    prov = _FakeProvider(stock_close=None, bench_close=None)  # empty candles
    row = {"Ticker": "AAA"}
    counts = _post([row], {"AAA": _price_df([10.0] * 300)}, prov, tmp_path,
                   monkeypatch, fund=False, rs=True)
    assert "_rs_line_latest" not in row
    assert counts["rs_attempted"] == 1 and counts["rs_populated"] == 0


# ── yfinance fully mocked (brief's explicit requirement) ─────────────────────
def test_post_pass_with_mocked_yfinance(tmp_path, monkeypatch):
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

    from core.pipeline.market_data.providers import YahooProvider

    row = {"Ticker": "AAA"}
    _post([row], {"AAA": _price_df([10.0] * 300, end="2026-06-01")},
          YahooProvider(), tmp_path, monkeypatch, fund=True, rs=False)
    # 2025-12-31 quarter is filed by 2026-06-01 -> YoY 1.20 vs 1.00 = +20%.
    assert row["_fund_eps_growth_yoy"] == pytest.approx(0.20)
    # Next earnings 2026-06-22 minus as_of 2026-06-01 = 21 days forward.
    assert row["_days_to_earnings"] == 21


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


# ── the assembly has ONE home ────────────────────────────────────────────────
def test_evaluate_ticker_attaches_nothing_in_worker(monkeypatch):
    """The in-worker attach point is gone — with flags off OR on, the eval
    worker adds no advisory keys (the conductor post-pass is the one
    assembly; EC-3, 2026-08-17 review)."""
    from engine_alpha import evaluation

    sentinel = {"Ticker": "AAA", "Score": 100.0, "Tier": "S"}
    monkeypatch.setattr(evaluation, "_run_eval_chain", lambda *a, **k: dict(sentinel))

    from config import settings
    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", True, raising=False)

    out = evaluation._evaluate_ticker("AAA", _price_df([1.0] * 300))
    assert out == sentinel  # flags ON and still no in-worker advisory keys
    assert not hasattr(advisory, "per_ticker_advisory")  # retired, not dormant
