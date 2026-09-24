"""Build step 12 of the final method, part three (points 22, 23 and 24): the display states.

One chart's state word on demand (services.chart_state) for a ticker the payload does not list: "not scanned"
with the door's leg in his words and the distance in ranges, or the lines the walk found and their facts; the
ticker page's fired / crossed lookup (the archive's ticker filter); the watch lane's row facts without the
display floor. Read-only, off the cached frame, never a new pick.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

# The backend package is imported by its own name (`services`, `routers`), the way the archive guards do it.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from config import settings  # noqa: E402
from engine_alpha import evaluation  # noqa: E402
from services import archive_queries, chart_state  # noqa: E402


def _frame(n=400, close=100.0, slope=0.0, band=0.5):
    idx = pd.bdate_range("2025-01-06", periods=n)
    c = close + slope * np.arange(n)
    return pd.DataFrame({"Open": c, "High": c + band, "Low": c - band, "Close": c, "Volume": 1e6}, index=idx)


def _serve(frame, status="ok"):
    return lambda ticker, universe_key=None: (SimpleNamespace(key="us_equities"), frame, status)


def test_the_door_words_are_his_and_cover_every_leg():
    legs = {"bars", "price", "vol50", "sma50", "sma200", "yoy"}
    assert set(chart_state.DOOR_WORDS) == legs
    assert chart_state.DOOR_WORDS["sma50"] == "under the 50-day average"
    assert "20 percent" in chart_state.DOOR_WORDS["yoy"]


def test_not_scanned_names_the_leg_and_the_distance_in_ranges(monkeypatch):
    # A steady decline: the last close sits under its 50-day average by a known number of ranges.
    frame = _frame(slope=-0.2)
    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    out = chart_state.read_chart_state("abc")
    assert out["ticker"] == "ABC" and out["state"] == "not scanned"
    assert out["why"] == "under the 50-day average"
    assert out["distance_ranges"] is not None and out["distance_ranges"] > 0
    assert out["as_of"] == str(frame.index[-1].date()) and out["close"] == pytest.approx(float(frame["Close"].iloc[-1]))
    assert "R" not in out


def test_a_frame_the_cache_cannot_serve_is_not_scanned_with_the_reason(monkeypatch):
    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(None, "unknown"))
    out = chart_state.read_chart_state("ZZZZ")
    assert out["state"] == "not scanned" and out["why"] == "not in any scanned universe"
    assert out["as_of"] is None and out["close"] is None


def test_a_read_that_raises_says_so_instead_of_raising(monkeypatch):
    frame = _frame()
    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))

    def boom(*a, **k):
        raise RuntimeError("degenerate frame")

    monkeypatch.setattr(chart_state.evaluation, "_run_eval_chain", boom)
    out = chart_state.read_chart_state("ABC")
    assert out["state"] == "no lines" and out["why"] == "the read failed"


def test_every_state_the_service_returns_is_on_the_table(monkeypatch):
    frame = _frame()
    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    out = chart_state.read_chart_state("ABC")
    assert out["state"] in evaluation.WATCH_WIRE_STATES


def test_the_lane_row_facts_ride_without_the_display_floor(monkeypatch):
    """The ticker page shows the lines' facts however few turns they have: floor=0 skips the lane's floor."""
    frame = _frame(n=60, band=0.2)          # bars under the turn floor: the line has no turns at all
    watch = {"df": frame, "unit": 1.0, "structure": SimpleNamespace(
        R=101.0, S=99.0, box=SimpleNamespace(start_bar=10, r_anchor_bar=12, s_anchor_bar=15)), "why": "x"}
    assert evaluation._lane_row("ABC", watch, "lines, no LPS yet") is None, "flat bars: no turns, under the floor"
    row = evaluation._lane_row("ABC", watch, "lines, no LPS yet", floor=0)
    assert row["ticker"] == "ABC" and row["R"] == 101.0 and row["S"] == 99.0 and row["age"] == 48
    assert row["turns_at_r"] == 0 and row["turns_at_s"] == 0 and row["why"] == "x"
    monkeypatch.setattr(settings, "WATCH_LANE_MIN_TURNS_PER_RAIL", 0)
    assert evaluation._lane_row("ABC", watch, "lines, no LPS yet")["turns_at_r"] == 0, "the setting is the default floor"


def test_the_service_carries_the_lane_facts_for_a_chart_with_lines(monkeypatch):
    frame = _frame(n=60, band=0.2)
    fake_structure = SimpleNamespace(R=101.0, S=99.0, box=SimpleNamespace(start_bar=10, r_anchor_bar=12, s_anchor_bar=15))

    def chain(ticker, df, spy, breadth, watch=None):
        watch.update(df=df, unit=1.0, structure=fake_structure, state="lines, no LPS yet")
        return None

    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    monkeypatch.setattr(chart_state.evaluation, "_run_eval_chain", chain)
    out = chart_state.read_chart_state("ABC")
    assert out["state"] == "lines, no LPS yet"
    assert out["R"] == 101.0 and out["S"] == 99.0 and out["open"] == str(frame.index[10].date())
    assert out["turns_at_r"] == 0 and out["age"] == 48


class _Query:
    def __init__(self):
        self.filters = []

    def filter(self, clause):
        self.filters.append(str(clause))
        return self


def test_the_archive_ticker_filter_narrows_to_one_symbol_uppercased():
    q = archive_queries._apply_setup_filters(_Query(), universe_type=None, ticker=" jazz ")
    assert any("ticker" in f for f in q.filters) and len(q.filters) == 1
    assert not archive_queries._apply_setup_filters(_Query(), universe_type=None).filters


def test_the_state_route_refuses_a_malformed_ticker():
    from routers.screener import _TICKER_RE

    assert _TICKER_RE.match("BRK.B") and _TICKER_RE.match("NGL") and _TICKER_RE.match("BF-B")
    assert not _TICKER_RE.match("../etc") and not _TICKER_RE.match("") and not _TICKER_RE.match("A B")


# ── the descent tail as a comment on the fire (point 22, under the states switch) ──

def _first_fire(monkeypatch):
    from core.pipeline.screener import _evaluate_ticker
    from engine_alpha.evaluation import EVAL_ERROR
    from tools.shadow_diff import _load_fixture

    frames, scalars = _load_fixture()
    breadth = scalars.get("breadth_pct")
    spy, breadth = float(scalars.get("spy_6m_return", 0.0)), (float(breadth) if breadth is not None else None)
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        off = _evaluate_ticker(ticker, df, spy, breadth)
        if isinstance(off, dict) and off is not EVAL_ERROR:
            return ticker, df, spy, breadth, off
    pytest.fail("no fire on the fixture")


def test_the_descent_tail_refuses_flag_off_and_comments_under_the_switch(monkeypatch):
    from core.pipeline.screener import _evaluate_ticker

    ticker, df, spy, breadth, off = _first_fire(monkeypatch)
    assert "_descent_tail" not in off, "flag-off the row carries no comment"
    monkeypatch.setattr(evaluation, "descent_tail_drops", lambda *a, **k: True)
    assert _evaluate_ticker(ticker, df, spy, breadth) is None, "flag-off the tail still refuses"
    watch = {}
    assert evaluation._run_eval_chain(ticker, df, spy, breadth, watch=watch) is None
    assert (watch.get("state"), watch.get("why")) == ("no lines", "descent tail")
    monkeypatch.setattr(settings, "LPS_LEAVES_ELECTION_ENABLED", True)
    on = _evaluate_ticker(ticker, df, spy, breadth)
    assert isinstance(on, dict) and on["_descent_tail"] is True, "under the switch the fire stands, commented"
    monkeypatch.setattr(evaluation, "descent_tail_drops", lambda *a, **k: False)
    assert _evaluate_ticker(ticker, df, spy, breadth)["_descent_tail"] is False


def test_the_comment_is_never_read_by_the_score(monkeypatch):
    """The tail is shown, not graded: the score and the grade do not move when the comment flips."""
    from core.pipeline.screener import _evaluate_ticker

    ticker, df, spy, breadth, _off = _first_fire(monkeypatch)
    monkeypatch.setattr(settings, "LPS_LEAVES_ELECTION_ENABLED", True)
    monkeypatch.setattr(evaluation, "descent_tail_drops", lambda *a, **k: True)
    tailed = _evaluate_ticker(ticker, df, spy, breadth)
    monkeypatch.setattr(evaluation, "descent_tail_drops", lambda *a, **k: False)
    clean = _evaluate_ticker(ticker, df, spy, breadth)
    assert (tailed["Score"], tailed["_ta_grade"], tailed["Tier"]) == (clean["Score"], clean["_ta_grade"], clean["Tier"])
