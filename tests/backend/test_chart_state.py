"""Build step 12 of the final method, part three (points 22, 23 and 24): the display states.

One chart's state word on demand (domains.screener.chart_state) for a ticker the payload does not list: "not scanned"
with the door's leg in his words and the distance in ranges, or the lines the reader found and their facts; the
ticker page's fired / crossed lookup (the archive's ticker filter). Read-only, off the cached frame, never a new
pick.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from _paths import BACKEND_DIR

# The backend package is imported by its own name (`domains`, `services`), the way the archive guards do it.
_BACKEND_DIR = str(BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from engine_alpha.record import STATE_WORDS as WATCH_WIRE_STATES  # noqa: E402
from domains.archive import queries as archive_queries  # noqa: E402
from domains.screener import chart_state  # noqa: E402


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


def test_a_read_that_raises_is_a_screen_state_never_one_of_his_words(monkeypatch):
    """The two-eyes build, task 15: *"a failed or pending read is a screen state, never one of your ten words"*.
    It used to answer "no lines", the word for a chart that genuinely has none, so a broken read and an empty chart
    looked the same on the card."""
    from engine_alpha import gate as door

    frame = _frame()
    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))

    def boom(*a, **k):
        raise RuntimeError("degenerate frame")

    monkeypatch.setattr(door, "run_eval_chain", boom)
    out = chart_state.read_chart_state("ABC")
    assert out["failed"] is True and out["why"] == "the read failed"
    assert out["state"] is None, "no word at all: the read did not get far enough to have one"
    assert out["as_of"] == str(frame.index[-1].date())


def test_the_word_and_the_lines_are_the_readers(monkeypatch):
    """The card's line is the reader's: its word, and its own box's lines and opening day, with the days that ride
    beside a word that counts them."""
    import datetime as dt

    from engine_alpha import gate as door
    from engine_alpha import record

    frame = _frame()
    box = record.Box(resistance=record.Line(101.25, dt.date(2026, 3, 2)), support=record.Line(98.5, dt.date(2026, 3, 4)),
                     opened_day=dt.date(2026, 3, 2), daily_range=1.0)
    read = record.Read(ticker="ABC", as_of=frame.index[-1].date(), boxes=(box,), state="beyond R, undetermined",
                       state_days=3, close=float(frame["Close"].iloc[-1]))

    def two_eyes_chain(ticker, df, spy, breadth, *, watch=None, **_k):
        watch.update(two_eyes=True, read=read, state=read.state)
        return None

    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    monkeypatch.setattr(door, "run_eval_chain", two_eyes_chain)
    out = chart_state.read_chart_state("ABC")
    assert out["state"] == "beyond R, undetermined"
    assert (out["R"], out["S"], out["open"], out["days"]) == (101.25, 98.5, "2026-03-02", 3)
    assert "failed" not in out


def test_a_crashed_two_eyes_read_is_the_same_screen_state(monkeypatch):
    """The door's chain RAISES on a failed two-eyes read (its contract); the page says the read failed."""
    from engine_alpha import gate as door

    frame = _frame()

    def refused(*a, **k):
        raise ValueError("two-eyes reader refused ABC: a day deleted from the middle")

    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    monkeypatch.setattr(door, "run_eval_chain", refused)
    out = chart_state.read_chart_state("ABC")
    assert (out["state"], out["failed"], out["why"]) == (None, True, "the read failed")


def test_every_state_the_service_returns_is_on_the_table(monkeypatch):
    frame = _frame()
    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    out = chart_state.read_chart_state("ABC")
    assert out["state"] in WATCH_WIRE_STATES


def test_a_word_off_the_table_is_refused_loudly(monkeypatch):
    """The state word is checked against the closed table at the publisher: a slug the reader never speaks is a
    bug, surfaced as a failed read, never a card line."""
    from engine_alpha import gate as door

    frame = _frame()

    def off_table(ticker, df, spy, breadth, *, watch=None, **_k):
        watch.update(two_eyes=True, state="somewhere else")
        return None

    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    monkeypatch.setattr(door, "run_eval_chain", off_table)
    with pytest.raises(ValueError, match="not on the table"):
        chart_state.read_chart_state("ABC")


def test_a_word_with_no_box_carries_no_lines(monkeypatch):
    """A chart the reader read but drew no box on ("no lines") says its word and nothing else: no R, no S, no
    opening day — the old engine's lane facts (age, turns at each rail) left with it."""
    from engine_alpha import gate as door
    from engine_alpha import record

    frame = _frame()
    read = record.Read(ticker="ABC", as_of=frame.index[-1].date(), boxes=(), state="no lines",
                       state_days=None, close=float(frame["Close"].iloc[-1]))

    def boxless(ticker, df, spy, breadth, *, watch=None, **_k):
        watch.update(two_eyes=True, read=read, state=read.state, why="no pair of swing ends became a box")
        return None

    monkeypatch.setattr(chart_state.watchlist_candles, "_serving_universe_and_frame", _serve(frame))
    monkeypatch.setattr(door, "run_eval_chain", boxless)
    out = chart_state.read_chart_state("ABC")
    assert out["state"] == "no lines" and out["why"] == "no pair of swing ends became a box"
    assert not {"R", "S", "open", "days", "age", "turns_at_r", "turns_at_s", "forming"} & set(out)


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
    from domains.screener.router import _TICKER_RE

    assert _TICKER_RE.match("BRK.B") and _TICKER_RE.match("NGL") and _TICKER_RE.match("BF-B")
    assert not _TICKER_RE.match("../etc") and not _TICKER_RE.match("") and not _TICKER_RE.match("A B")
