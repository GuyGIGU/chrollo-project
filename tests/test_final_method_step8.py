"""Build step 8 of the final method (docs/final_method_2026-09.md point 22): the LPS leaves the election.

"The LPS stops being a brick of the box election (today no LPS means the walk skips to the next root and the
chart returns nothing). The 'no LPS yet' charts sit in a watch lane apart from the leaderboard, with a display
floor of two turns at each rail on the line that touches no fire." One default-off switch,
LPS_LEAVES_ELECTION_ENABLED: the root walk returns the first valid box with or without an LPS; a structure
without an LPS never fires; every chart the door admits carries ONE state word from the closed table into
market_context["watch"]; the lane's rows sit behind WATCH_LANE_MIN_TURNS_PER_RAIL. Flag-off byte-identical
(the fleet, junk, marks and reader-pin guards prove that at scale); these tests prove the mechanics.
"""
from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha import evaluation
from engine_alpha.evaluation import (
    EVAL_ERROR,
    WATCH_LANE_STATES,
    WATCH_WIRE_STATES,
    _chart_state,
    _lane_row,
    _resolve_lps_context,
    _run_eval_chain,
    _walk_refused_state,
    evaluate_ticker_with_watch,
    watch_verdict,
)
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure.narrative import Structure, read_structure
from engine_alpha.structure.pivots import turns_at_rails
from tools.replay import flag_capture

SWITCH = "LPS_LEAVES_ELECTION_ENABLED"
FLOOR = "WATCH_LANE_MIN_TURNS_PER_RAIL"
N = 60
LO, HI = 100.0, 125.0


def _frame(n=N):
    idx = pd.bdate_range("2026-01-05", periods=n)
    close = 110.0 + np.sin(np.arange(n) / 3.0)
    return pd.DataFrame({"Open": close, "High": close + 0.5, "Low": close - 0.5, "Close": close,
                         "Volume": 1e6}, index=idx)


def _zigzag_frame(n=80, half=8, lo=LO, hi=HI):
    """A triangle wave between lo and hi: valleys every 2*half days from day 0, peaks between them (the
    step-7 frame). With a unit of 1.0 the line commits every turn: five at each rail on 80 days."""
    t = np.arange(n)
    phase = (t % (2 * half)) / half
    mid = np.where(phase <= 1, lo + (hi - lo) * phase, hi - (hi - lo) * (phase - 1))
    idx = pd.bdate_range("2025-06-02", periods=n)
    return pd.DataFrame({"Open": mid, "High": mid + 0.5, "Low": mid - 0.5, "Close": mid,
                         "Volume": 1e6}, index=idx)


def _one_turn_frame(n=40):
    """Up to 125 on day 8, down to 100 on day 16, then flat at 112: one peak at R, two valleys at S."""
    t = np.arange(n)
    mid = np.where(t <= 8, LO + (HI - LO) * t / 8,
                   np.where(t <= 16, HI - (HI - LO) * (t - 8) / 8, 112.0))
    idx = pd.bdate_range("2025-06-02", periods=n)
    return pd.DataFrame({"Open": mid, "High": mid + 0.5, "Low": mid - 0.5, "Close": mid,
                         "Volume": 1e6}, index=idx)


def _box(R=110.0, S=100.0, start=20):
    return SimpleNamespace(S=S, R=R, start_bar=start, box_width=(R - S) / S, r_anchor_bar=start + 5,
                           s_anchor_bar=start, base_len=N - start)


class _Bricks:
    """Scripted roots and boxes (the fake of tests/test_final_method_step6.py): ``stories`` maps a root's
    climax bar to (box, lps); the walk visits them oldest first."""

    def __init__(self, stories):
        self.stories = stories

    def find_root_swing(self, df, search_from_bar, atr):
        for climax in sorted(self.stories):
            if climax >= search_from_bar:
                return SimpleNamespace(climax_bar=climax, ar_bar=climax + 5, R=110.0, S=100.0)
        return None

    def validate_equilibrium(self, df, root, atr, trace=None):
        return self.stories[root.climax_bar][0]

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = next(l for b, l in self.stories.values() if b is box)
        return (lps, Counter({"bought: a later high crossed the trigger": 1}) if lps is None else Counter()) \
            if diagnose else lps

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=True, bridge_validated=True, pre_box_trend="", box_trend="",
                               lps_tightness_ratio=0.0)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar


@pytest.fixture
def switch_on(monkeypatch):
    monkeypatch.setattr(settings, SWITCH, True)


def test_the_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, SWITCH) is False
    assert getattr(settings, FLOOR) == 2, "his display floor: two turns at each rail"
    assert {SWITCH, FLOOR} <= set(ENGINE_SETTINGS_KEYS)


# ── the root walk: a box without an LPS is a legal return ────────────────────

def test_the_walk_returns_a_box_without_an_lps_only_under_the_switch(monkeypatch):
    box = _box()
    bricks = _Bricks({10: (box, None)})
    df = _frame()
    assert read_structure(df, 1.0, bricks=bricks) is None, "flag-off: no LPS, no structure"
    monkeypatch.setattr(settings, SWITCH, True)
    trace = []
    s = read_structure(df, 1.0, bricks=bricks, trace=trace)
    assert isinstance(s, Structure)
    assert s.lps is None and s.lps_in_inner is False and s.box is box
    assert s.terminator == "none" and s.phase_b_end_bar == N - 1, "Phase B runs to the right edge"
    assert (s.R, s.S) == (110.0, 100.0)
    assert trace[-1]["outcome"] == "no_lps" and "parent" in trace[-1]["lps_rejects"], \
        "the trace still says what the walk knows: this box has no LPS"


def test_the_walk_no_longer_skips_to_a_later_root_for_an_lps(monkeypatch):
    older, younger = _box(start=15), _box(R=112.0, S=104.0, start=35)
    bricks = _Bricks({10: (older, None), 30: (younger, SimpleNamespace(start_bar=55))})
    df = _frame()
    off = read_structure(df, 1.0, bricks=bricks)
    assert off is not None and off.box is younger and off.lps is not None, \
        "flag-off the walk moves on to the root whose box has an LPS"
    monkeypatch.setattr(settings, SWITCH, True)
    on = read_structure(df, 1.0, bricks=bricks)
    assert on.box is older and on.lps is None, "under the switch the first valid box is the structure"


def test_a_box_with_an_lps_reads_the_same_under_the_switch(monkeypatch):
    bricks = _Bricks({10: (_box(), SimpleNamespace(start_bar=55))})
    df = _frame()
    off = read_structure(df, 1.0, bricks=bricks)
    monkeypatch.setattr(settings, SWITCH, True)
    on = read_structure(df, 1.0, bricks=bricks)
    fields = ("R", "S", "phase_b_start_bar", "phase_b_end_bar", "terminator", "phase_d_start_bar",
              "phase_d_source", "lps_in_inner")
    assert [getattr(off, f) for f in fields] == [getattr(on, f) for f in fields]
    assert on.lps is off.lps and on.terminator == "lps"


# ── the state word at each exit of the chain ─────────────────────────────────

def _no_lps_structure(R=110.0, S=100.0, lps=None):
    return SimpleNamespace(R=R, S=S, lps=lps, lps_in_inner=False,
                           box=SimpleNamespace(start_bar=0, r_anchor_bar=8, s_anchor_bar=0))


def test_a_structure_without_an_lps_never_fires_and_reads_lines_no_lps_yet():
    df = _frame()
    ctx = {"structure": _no_lps_structure(), "atr_for_zone": 1.0}
    watch = {"trace": [{"lps_rejects": {"parent": {"window too short": 2}}}]}
    assert _resolve_lps_context(df, df.iloc[-1], ctx, watch=watch) is None
    assert watch["state"] == "lines, no LPS yet"
    quiet = {}
    assert _resolve_lps_context(df, df.iloc[-1], ctx) is None, "no recorder: the same refusal, nothing written"
    assert quiet == {}


def test_a_bought_window_reads_crossed_off_the_walks_own_rejects():
    df = _frame()
    trace = [{"lps_rejects": {"inner": {}, "parent": {"bought: a later high crossed the trigger": 1}}}]
    assert _chart_state(df, _no_lps_structure(), 1.0, trace)["state"] == "crossed"
    assert _chart_state(df, _no_lps_structure(), 1.0, [])["state"] == "lines, no LPS yet"


def test_the_open_right_edge_reads_precedence_row_five():
    df = _frame()
    beyond = df.copy()
    beyond.loc[beyond.index[-3:], ["Low", "High", "Close"]] = [[111.0, 113.0, 112.0]] * 3   # whole bars over R + 0.5
    state = _chart_state(beyond, _no_lps_structure(), 1.0, [])
    assert (state["state"], state["days"]) == ("beyond R, undetermined", 3)
    under = df.copy()
    under.loc[under.index[-2:], ["Low", "High", "Close"]] = [[97.0, 99.0, 98.0]] * 2         # whole bars under S - 0.5
    state = _chart_state(under, _no_lps_structure(), 1.0, [])
    assert (state["state"], state["days"]) == ("under S, undetermined", 2)
    touching = df.copy()
    touching.loc[touching.index[-1], ["Low", "High", "Close"]] = [110.4, 113.0, 112.0]       # the low is inside the area
    assert _chart_state(touching, _no_lps_structure(), 1.0, [])["state"] == "lines, no LPS yet"
    bought = [{"lps_rejects": {"parent": {"bought: a later high crossed the trigger": 1}}}]
    assert _chart_state(beyond, _no_lps_structure(), 1.0, bought)["state"] == "beyond R, undetermined", \
        "the right edge is read first"


def test_a_refused_read_with_an_lps_names_its_refusal():
    df = _frame()
    with_lps = _no_lps_structure(lps=SimpleNamespace(start_bar=50))
    state = _chart_state(df, with_lps, 1.0, [], why="extension veto")
    assert (state["state"], state["why"]) == ("crossed", "extension veto")
    state = _chart_state(df, with_lps, 1.0, [], why="crash floor")
    assert (state["state"], state["why"]) == ("under S, undetermined", "crash floor")


def test_a_crossed_trigger_reads_crossed():
    df = _frame()
    lps = SimpleNamespace(detection={"trigger_price": 105.0, "setup_type": "LPS", "length": 3, "offset": 0,
                                     "vol_contraction": 0.5, "tightness_ratio": 0.5})
    ctx = {"structure": _no_lps_structure(lps=lps), "atr_for_zone": 1.0, "inner": None,
           "parent_ctx": (100.0, 110.0, 1.0, 40, 8)}
    watch = {}
    assert _resolve_lps_context(df, df.iloc[-1], ctx, watch=watch) is None, "the close 110 sits over the trigger"
    assert watch["state"] == "crossed"


def test_the_door_names_its_leg():
    watch = {}
    assert _run_eval_chain("X", _frame(10), watch=watch) is None
    assert (watch["state"], watch["why"]) == ("not scanned", "bars")


def test_a_refused_walk_reads_forming_or_no_lines():
    assert _walk_refused_state([]) == {"state": "no lines", "why": "no root"}
    assert _walk_refused_state([{"outcome": "no_box"}, {"outcome": "cause_absent"}]) == \
        {"state": "no lines", "why": "cause_absent"}
    trace = [{"outcome": "no_box"},
             {"outcome": "forming", "forming": {"age": 9, "of": 15}, "box": {"R": 1, "S": 0, "start_bar": 3}},
             {"outcome": "forming", "forming": {"age": 12, "of": 15}, "box": {"R": 2, "S": 1, "start_bar": 5}}]
    state = _walk_refused_state(trace)
    assert state["state"] == "forming N of 15" and state["forming"] == {"age": 12, "of": 15}, "the oldest young box"
    assert state["box"]["start_bar"] == 5


# ── the display floor: turns of the line at each rail ────────────────────────

def test_turns_at_rails_counts_committed_turns_inside_the_area_only():
    line = [(0, "valley", 99.6, 0), (8, "peak", 125.4, 10), (16, "valley", 100.2, 18),
            (24, "peak", 130.0, 26), (32, "valley", 99.9, 34), (40, "peak", 125.0, None)]
    assert turns_at_rails(line, 0, 125.5, 99.5, 0.5) == (1, 2), \
        "a peak beyond the area is a thrust, the forming turn is not yet a turn, a valley 0.7 off S is not at S"
    assert turns_at_rails(line, 5, 125.5, 99.5, 0.5) == (1, 1), "the valley on day 0 sits before the box start"


def _lane_watch(df, R=HI + 0.5, S=LO - 0.5, start=0, unit=1.0):
    structure = SimpleNamespace(R=R, S=S, lps=None,
                                box=SimpleNamespace(start_bar=start, r_anchor_bar=8, s_anchor_bar=0))
    return {"df": df, "unit": unit, "structure": structure}


def test_the_lane_row_carries_the_facts_over_the_floor():
    row = _lane_row("AAA", _lane_watch(_zigzag_frame()), "lines, no LPS yet")
    assert row["ticker"] == "AAA" and row["state"] == "lines, no LPS yet"
    assert (row["R"], row["S"], row["open"]) == (125.5, 99.5, "2025-06-02")
    assert (row["turns_at_r"], row["turns_at_s"]) == (5, 5)
    assert row["age"] == 80, "the box's age from its first anchor, the anchor bar as day 1"


def test_one_turn_at_a_rail_sits_below_the_floor(monkeypatch):
    watch = _lane_watch(_one_turn_frame())
    assert _lane_row("AAA", watch, "lines, no LPS yet") is None, "one peak at R: below two"
    monkeypatch.setattr(settings, FLOOR, 1)
    row = _lane_row("AAA", watch, "lines, no LPS yet")
    assert row is not None and (row["turns_at_r"], row["turns_at_s"]) == (1, 2), "the floor is read, never assumed"


def test_a_forming_box_rows_from_the_walks_brief():
    watch = {"df": _zigzag_frame(), "unit": 1.0, "forming": {"age": 12, "of": 15},
             "box": {"R": HI + 0.5, "S": LO - 0.5, "start_bar": 0}}
    row = _lane_row("AAA", watch, "forming N of 15")
    assert row["forming"] == {"age": 12, "of": 15} and row["age"] == 12 and row["R"] == 125.5


# ── the twin and the wire ────────────────────────────────────────────────────

def test_the_twin_flag_off_is_exactly_the_inner_with_no_recorder():
    calls = []

    def inner(ticker, df, spy, breadth, **kw):
        calls.append(kw)
        return "BASE"

    assert evaluate_ticker_with_watch("X", _frame(), inner=inner) == ("BASE", None, {})
    assert calls == [{}], "flag-off no recorder is handed down"


def test_the_twin_types_the_state_off_the_one_read(switch_on):
    def refused(ticker, df, spy, breadth, watch):
        watch.update(state="not scanned", why="bars")
        return None

    assert evaluate_ticker_with_watch("X", _frame(), inner=refused) == (None, None, {"not scanned": 1})

    def fired(ticker, df, spy, breadth, watch):
        return {"Ticker": ticker}

    assert evaluate_ticker_with_watch("X", _frame(), inner=fired) == ({"Ticker": "X"}, None, {"fired": 1})

    def composed(ticker, df, spy, breadth, watch):
        return {"Ticker": ticker}, [], {}

    base, row, stats = evaluate_ticker_with_watch("X", _frame(), inner=composed)
    assert base == ({"Ticker": "X"}, [], {}) and row is None and stats == {"fired": 1}, "a triple stays a triple"

    def crashed(ticker, df, spy, breadth, watch):
        return EVAL_ERROR

    assert evaluate_ticker_with_watch("X", _frame(), inner=crashed) == (EVAL_ERROR, None, {"base errored": 1})


def test_a_lane_state_rows_over_the_floor_and_counts_under_it(switch_on, monkeypatch):
    df = _zigzag_frame()

    def lines(ticker, frame, spy, breadth, watch):
        watch.update(_lane_watch(frame), state="lines, no LPS yet")
        return None

    base, row, stats = evaluate_ticker_with_watch("AAA", df, inner=lines)
    assert base is None and row["ticker"] == "AAA" and stats == {"lines, no LPS yet": 1}
    monkeypatch.setattr(settings, FLOOR, 9)
    base, row, stats = evaluate_ticker_with_watch("AAA", df, inner=lines)
    assert row is None and stats == {"lines, no LPS yet": 1, "below the floor": 1}


def test_an_unknown_word_never_reaches_the_wire(switch_on):
    with pytest.raises(ValueError):
        watch_verdict({"state": "meh"}, fired=False)
    assert watch_verdict({}, fired=False) == "no lines" and watch_verdict({"state": "meh"}, fired=True) == "fired"

    def odd(ticker, df, spy, breadth, watch):
        watch["state"] = "meh"
        return None

    assert evaluate_ticker_with_watch("X", _frame(), inner=odd) == (None, None, {"errored": 1}), \
        "the lane swallows and counts; the scan never sees it"


def test_the_table_is_his_ten_words():
    assert WATCH_WIRE_STATES == ("fired", "crossed", "lines, no LPS yet", "forming N of 15",
                                 "root candidate, unconfirmed", "beyond R, undetermined",
                                 "under S, undetermined", "broke down", "not scanned", "no lines")
    assert set(WATCH_LANE_STATES) < set(WATCH_WIRE_STATES)
    assert "fired" not in WATCH_LANE_STATES and "crossed" not in WATCH_LANE_STATES, "nothing on the board twice"


class _InlineFuture:
    def __init__(self, fn, *args):
        self._result = fn(*args)

    def result(self):
        return self._result


class _InlinePool:
    """Executes submits inline (a spawned worker would re-import settings and lose the flag flip)."""

    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *args):
        return _InlineFuture(fn, *args)


def test_the_conductor_publishes_the_lane_to_market_context(monkeypatch):
    import core.pipeline.screener as screener_module

    df = _zigzag_frame(480)

    class _Provider:
        def fetch(self, tickers, universe=None):
            return df

    def lines(ticker, frame, spy, breadth, watch=None):
        assert watch is not None, "the ladder's rung is called through the twin"
        watch.update(_lane_watch(frame), state="lines, no LPS yet")
        return None

    monkeypatch.setattr(screener_module, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(screener_module, "as_completed", lambda futures: iter(list(futures)))
    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: _Provider())
    monkeypatch.setattr(screener_module, "get_market_context",
                        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0})
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics, universe=None: None)
    monkeypatch.setattr(screener_module, "_evaluate_ticker", lines)

    with flag_capture(LPS_LEAVES_ELECTION_ENABLED=True, NEAR_MISS_LANE_ENABLED=False,
                      POWER_PLAY_PRESET_ENABLED=False):
        _results, _data, _tickers, market_context = screener_module.run_screener()
    block = market_context["watch"]
    assert [r["ticker"] for r in block["candidates"]] == ["AAA"]
    assert block["candidates"][0]["state"] == "lines, no LPS yet"
    assert block["counts"] == {"lines, no LPS yet": 1}

    def plain(ticker, frame, spy, breadth, watch=None):
        assert watch is None, "flag-off: no recorder"
        return None

    monkeypatch.setattr(screener_module, "_evaluate_ticker", plain)
    with flag_capture(NEAR_MISS_LANE_ENABLED=False, POWER_PLAY_PRESET_ENABLED=False):
        _results, _data, _tickers, market_context = screener_module.run_screener()
    assert "watch" not in market_context
