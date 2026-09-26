"""Offline unit tests for the regime data primitives (Lane C):
percentile-rank, RS line, and SPDR sector ranking.

All pure-function tests (no network); the two fetch wrappers are exercised against
a tiny fake provider object. They pin: None/NaN exclusion in the percentile
denominator, midrank ties, RS-line inner-join alignment + new-high (no lookahead),
and the sector composite ranking.
"""
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.regime.percentile import percentile_rank
from core.regime import rs_line as rs_mod
from core.regime import sector_ranking as sr_mod


# ── percentile_rank ──────────────────────────────────────────────────────────
def test_percentile_rank_orders_strong_high():
    out = percentile_rank({"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0})
    assert out["d"] > out["c"] > out["b"] > out["a"]
    # Midrank: lowest of 4 -> 0.5/4 = 12.5; highest -> 3.5/4 = 87.5.
    assert out["a"] == pytest.approx(12.5)
    assert out["d"] == pytest.approx(87.5)


def test_percentile_rank_ties_share_midrank():
    out = percentile_rank({"a": 5.0, "b": 5.0, "c": 1.0})
    assert out["a"] == out["b"]
    assert out["c"] < out["a"]


def test_percentile_rank_none_and_nan_excluded():
    out = percentile_rank({"a": 1.0, "b": None, "c": float("nan"), "d": 3.0})
    # Only a,d rankable -> denominator 2, b/c -> None.
    assert out["b"] is None and out["c"] is None
    assert out["a"] == pytest.approx(25.0)   # 0.5/2
    assert out["d"] == pytest.approx(75.0)   # 1.5/2


def test_percentile_rank_single_value_is_50():
    assert percentile_rank({"only": 9.0}) == {"only": 50.0}


def test_percentile_rank_all_missing():
    assert percentile_rank({"a": None, "b": float("nan")}) == {"a": None, "b": None}


def test_percentile_rank_order_independent():
    a = percentile_rank({"x": 3.0, "y": 1.0, "z": 2.0})
    b = percentile_rank({"z": 2.0, "x": 3.0, "y": 1.0})
    assert a == b


# ── rs_line ──────────────────────────────────────────────────────────────────
def _series(vals, start="2026-01-01"):
    return pd.Series(vals, index=pd.date_range(start, periods=len(vals), freq="D"))


def test_rs_line_ratio_and_alignment():
    stock = _series([10.0, 11.0, 12.0])
    bench = _series([100.0, 100.0, 100.0])
    out = rs_mod.rs_line(stock, bench)
    assert list(out.round(3)) == [0.1, 0.11, 0.12]


def test_rs_line_inner_join_only_shared_dates():
    stock = _series([10.0, 11.0, 12.0], start="2026-01-01")
    bench = _series([100.0, 100.0], start="2026-01-02")  # offset by a day
    out = rs_mod.rs_line(stock, bench)
    assert len(out) == 2  # only the two overlapping dates


def test_rs_line_drops_zero_benchmark():
    stock = _series([10.0, 11.0])
    bench = _series([0.0, 100.0])
    out = rs_mod.rs_line(stock, bench)
    assert len(out) == 1
    assert float(out.iloc[0]) == pytest.approx(0.11)


def test_rs_line_empty_inputs():
    assert rs_mod.rs_line(pd.Series(dtype="float64"), _series([1.0])).empty


def test_rs_line_new_high_true_at_peak():
    ratio = _series([1.0, 1.1, 1.2, 1.3])
    assert rs_mod.rs_line_new_high(ratio, 252) is True


def test_rs_line_new_high_false_off_peak():
    ratio = _series([1.0, 1.5, 1.2, 1.3])  # latest below the 1.5 peak
    assert rs_mod.rs_line_new_high(ratio, 252) is False


def test_rs_line_new_high_respects_lookback_window():
    # A high early in the series falls outside a short lookback, so the recent
    # bar IS a new high within that window (no lookahead/peek beyond the window).
    ratio = _series([5.0, 1.0, 1.1, 1.2, 1.3])
    assert rs_mod.rs_line_new_high(ratio, 3) is True       # window [1.1,1.2,1.3]
    assert rs_mod.rs_line_new_high(ratio, 252) is False    # 5.0 still dominates


def test_rs_line_new_high_empty_is_none():
    assert rs_mod.rs_line_new_high(pd.Series(dtype="float64"), 252) is None


# ── compute_rs_line (fake provider) ──────────────────────────────────────────
class _CandleProvider:
    def __init__(self, frames):
        self._frames = frames

    def daily_candles(self, symbol, days, **kwargs):
        return self._frames.get(symbol, pd.DataFrame())


def _ohlc(closes, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="D")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_compute_rs_line_wrapper():
    prov = _CandleProvider({
        "AAA": _ohlc([10.0, 11.0, 12.0, 13.0]),
        "SPY": _ohlc([100.0, 100.0, 100.0, 100.0]),
    })
    out = rs_mod.compute_rs_line("AAA", lookback=252, provider=prov)
    assert out["latest"] == pytest.approx(0.13)
    assert out["rs_line_new_high"] is True


def test_compute_rs_line_missing_data_is_null_safe():
    prov = _CandleProvider({"SPY": _ohlc([100.0, 100.0])})  # no AAA
    out = rs_mod.compute_rs_line("AAA", lookback=252, provider=prov)
    assert out["latest"] is None
    assert out["rs_line_new_high"] is None
    assert out["ratio"].empty


# ── sector_ranking ───────────────────────────────────────────────────────────
def test_rank_sectors_orders_leaders_first():
    # SPY flat; XLK ratio rising hardest, XLU falling -> XLK ranks above XLU.
    panel = {
        "SPY": _series([100.0] * 130),
        "XLK": _series([100.0 + i for i in range(130)]),    # strongly rising vs SPY
        "XLU": _series([100.0 - 0.1 * i for i in range(130)]),  # falling vs SPY
        "XLF": _series([100.0 + 0.2 * i for i in range(130)]),  # mildly rising
    }
    out = sr_mod.rank_sectors(panel, benchmark="SPY", lookbacks=(21, 63, 126))
    ranked = out["ranked"]
    assert ranked[0] == "XLK"
    assert ranked.index("XLK") < ranked.index("XLF") < ranked.index("XLU")
    assert out["composite"]["XLK"] >= out["composite"]["XLU"]


def test_rank_sectors_short_history_scores_none_that_horizon():
    # 30 bars: the 126d horizon can't be computed -> None there, but 21d can.
    panel = {
        "SPY": _series([100.0] * 30),
        "XLK": _series([100.0 + i for i in range(30)]),
    }
    out = sr_mod.rank_sectors(panel, benchmark="SPY", lookbacks=(21, 126))
    assert out["per_horizon"][126]["XLK"] is None
    assert out["per_horizon"][21]["XLK"] is not None
    # Composite still computes from the one available horizon.
    assert out["composite"]["XLK"] is not None


def test_rank_sectors_missing_benchmark_returns_empty():
    out = sr_mod.rank_sectors({"XLK": _series([1.0, 2.0])}, benchmark="SPY")
    assert out == {"per_horizon": {}, "percentile": {}, "composite": {}, "ranked": []}


def test_rank_sectors_empty_panel():
    assert sr_mod.rank_sectors({}, benchmark="SPY")["ranked"] == []


def test_compute_sector_ranking_wrapper():
    n = 130
    frames = {
        "SPY": _ohlc([100.0] * n),
        "XLK": _ohlc([100.0 + i for i in range(n)]),
        "XLU": _ohlc([100.0 - 0.1 * i for i in range(n)]),
    }
    prov = _CandleProvider(frames)
    out = sr_mod.compute_sector_ranking(
        etfs=("XLK", "XLU"), lookbacks=(21, 63), provider=prov
    )
    assert out["ranked"][0] == "XLK"


def test_compute_sector_ranking_drops_unfetchable_etf():
    n = 130
    frames = {
        "SPY": _ohlc([100.0] * n),
        "XLK": _ohlc([100.0 + i for i in range(n)]),
        # XLU absent -> dropped from the panel, never crashes the rank.
    }
    prov = _CandleProvider(frames)
    out = sr_mod.compute_sector_ranking(
        etfs=("XLK", "XLU"), lookbacks=(21, 63), provider=prov
    )
    assert "XLK" in out["ranked"]
    assert "XLU" not in out["ranked"]
