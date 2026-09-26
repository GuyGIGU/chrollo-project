"""Build step 10 of the final method (docs/final_method_2026-09.md points 3 and 4): the climax first, on the line,
and the walk from it.

His rule (Sat 19/09/2026): "the swings for BC and AR are needed to be decided before the Root Swing, because said
root swing can either be them, or a swing later". One default-off switch, CLIMAX_FIRST_WALK_ENABLED: the roots are
the runs the ONE turn line prints (climax.runs_on_the_line), the window opens at the climax with the climax and its
reaction as the first candidate pair, a pair is a candidate once its rails are answered, the painter and the cause
veto retire, the run rides as a fact. Flag-off byte-identical (the guards prove that at scale).
"""
from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha import evaluation
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure.box import box_primitives
from engine_alpha.structure.narrative import bricks
from engine_alpha.structure.events import market_structure
from engine_alpha.structure.phases import phase_a
from engine_alpha.structure.phases.climax import runs_on_the_line
from engine_alpha.structure.narrative import Structure, read_structure

SWITCH = "CLIMAX_FIRST_WALK_ENABLED"

# A rise of two higher highs and two higher lows, ended by a lower high on day 20; the reaction after the
# climax (118 on day 12) makes a lower low on day 24 before the first higher low on day 32.
LINE_UP = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 104), (12, "peak", 118), (16, "valley", 108),
           (20, "peak", 114), (24, "valley", 106), (28, "peak", 112), (32, "valley", 109), (36, "peak", 113)]


def _turns(spec, forming_last=False):
    out = [(b, k, float(p), b + 1) for b, k, p in spec]
    if forming_last:
        b, k, p, _ = out[-1]
        out[-1] = (b, k, p, None)
    return out


def _frame(spec, n=60, band=0.25):
    """OHLC bars through the spec's turns (linear legs, then flat), highs and lows a quarter either side."""
    bars = [b for b, _, _ in spec]
    prices = [float(p) for _, _, p in spec]
    close = np.interp(np.arange(n), bars, prices)
    idx = pd.bdate_range("2025-06-02", periods=n)
    return pd.DataFrame({"Open": close, "High": close + band, "Low": close - band, "Close": close,
                         "Volume": 1e6}, index=idx)


@pytest.fixture
def switch_on(monkeypatch):
    monkeypatch.setattr(settings, SWITCH, True)


def test_the_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, SWITCH) is False
    assert SWITCH in ENGINE_SETTINGS_KEYS


# ── the climax and its reaction on the line ──────────────────────────────────

def test_a_run_ends_at_the_first_swing_that_fails_it_and_the_reaction_low_precedes_the_first_higher_low():
    runs = runs_on_the_line(_turns(LINE_UP))
    assert len(runs) == 1
    r = runs[0]
    assert (r["kind"], r["climax_bar"], r["climax_price"]) == ("BC", 12, 118.0)
    assert (r["ar_bar"], r["ar_price"]) == (24, 106.0), "the lowest low of the reaction before the first higher low"
    assert (r["launch_bar"], r["end_bar"]) == (0, 20), "launched on day 0, ended by the lower high on day 20"


def test_a_run_ended_by_a_lower_low_reacts_from_that_low():
    spec = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 104), (12, "peak", 118), (16, "valley", 102),
            (20, "peak", 109), (24, "valley", 105)]
    r = runs_on_the_line(_turns(spec))[0]
    assert (r["climax_bar"], r["ar_bar"], r["end_bar"]) == (12, 16, 16), "the lower low both ends the run and opens the reaction"


def test_a_selling_climax_is_the_mirror():
    spec = [(0, "peak", 120), (4, "valley", 110), (8, "peak", 116), (12, "valley", 100), (16, "peak", 108),
            (20, "valley", 104), (24, "peak", 111), (28, "valley", 106), (32, "peak", 109)]
    r = runs_on_the_line(_turns(spec))[0]
    assert (r["kind"], r["climax_bar"], r["climax_price"]) == ("SC", 12, 100.0)
    assert (r["ar_bar"], r["ar_price"]) == (24, 111.0), "the highest high of the reaction before the first lower high"


def test_no_higher_low_yet_means_no_reaction_and_no_root():
    assert runs_on_the_line(_turns(LINE_UP[:8])) == [], "the reaction is still running: the climax is not proven"
    assert runs_on_the_line(_turns(LINE_UP[:9], forming_last=True)) == [], "a forming turn never anchors"


def test_a_lower_low_before_the_higher_high_is_not_part_of_the_rise():
    spec = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 96), (12, "peak", 118), (16, "valley", 108),
            (20, "peak", 114), (24, "valley", 104), (28, "peak", 112), (32, "valley", 107)]
    r = runs_on_the_line(_turns(spec))[0]
    assert (r["launch_bar"], r["climax_bar"], r["ar_bar"]) == (8, 12, 24),         "the rise needs a higher low AND a higher high: it launches from the day-8 low, not day 0"


def test_a_single_leg_or_an_equal_top_is_not_a_run():
    assert runs_on_the_line(_turns([(0, "valley", 100), (4, "peak", 110), (8, "valley", 104)])) == []
    flat = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 104), (12, "peak", 110), (16, "valley", 106)]
    assert runs_on_the_line(_turns(flat)) == [], "an equal top does not continue a rise"


# ── the root from the line, the window from the climax ───────────────────────

def test_the_root_comes_from_the_line_under_the_switch(monkeypatch):
    df = _frame(LINE_UP)
    seeds = []
    real = bricks.collect_root_anchors
    monkeypatch.setattr(bricks, "collect_root_anchors", lambda *a, **k: seeds.append(1) or real(*a, **k))
    bricks.find_root_swing(df, 0, 1.0)
    assert seeds == [1], "flag-off: today's seed"
    monkeypatch.setattr(settings, SWITCH, True)
    root = bricks.find_root_swing(df, 0, 1.0)
    assert seeds == [1], "under the switch the percent recipe is never consulted"
    assert (root.kind, root.climax_bar, root.ar_bar) == ("BC", 12, 24)
    assert (root.R, root.S) == (118.25, 105.75), "wick to wick: the climax high, the reaction low"
    assert root.run["launch_bar"] == 0 and root.run["days"] == 12 and root.run["ranges"] == 18.5, "wick to wick"
    assert bricks.find_root_swing(df, 13, 1.0) is None, "no later run on this line"


def test_the_window_opens_at_the_climax_with_its_reaction_as_the_first_pair(monkeypatch):
    df = _frame(LINE_UP)
    seen = []

    def spy(eq_df, atr_val, *a, **kw):
        seen.append((len(eq_df), kw))
        return []

    monkeypatch.setattr(bricks, "collect_zigzag_candidates", spy)
    monkeypatch.setattr(settings, SWITCH, True)
    root = bricks.find_root_swing(df, 0, 1.0)
    assert bricks.validate_equilibrium(df, root, 1.0) is None
    n_win, kw = seen[-1]
    assert n_win == 55 - 12, "the window opens on the climax bar (55 bars after the 5-day edge reserve)"
    assert kw["zigzag"][0] == (0, "peak", 118.25) and kw["zigzag"][1] == (4, "valley", 107.75)
    assert kw["extra_pairs"] == [(118.25, 105.75, 0, 12)], "the climax and its reaction, not a consecutive limb"
    assert kw["answer_area"] == 0.5
    assert kw["answer_line"] == kw["zigzag"], "one run on this line: its pairs are the whole window's"
    assert all(len(t) == 3 for t in kw["zigzag"]), "committed turns only, rebased to the window"
    assert kw["zigzag"][-1] == (20, "valley", 108.75), "the forming peak at the flat right edge is left out"
    monkeypatch.setattr(settings, SWITCH, False)
    root_off = SimpleNamespace(kind="BC", climax_bar=12, ar_bar=24, R=118.25, S=105.75, reaction_pct=0.1,
                               reaction_bars=12, run=None)
    assert bricks.validate_equilibrium(df, root_off, 1.0) is None
    n_win, kw = seen[-1]
    assert n_win == 55 - 24, "flag-off: the window opens on the reaction"
    assert not ({"zigzag", "extra_pairs", "answer_area", "answer_line"} & set(kw)), "flag-off: no line kwargs at all"


TWO_RUNS = LINE_UP + [(40, "valley", 107), (44, "peak", 119), (48, "valley", 112), (52, "peak", 118)]


def test_each_run_owns_its_pairs_and_the_answer_is_read_on_the_whole_line(monkeypatch):
    df = _frame(TWO_RUNS, n=75)
    monkeypatch.setattr(settings, SWITCH, True)
    second = bricks.find_root_swing(df, 13, 1.0)
    assert (second.climax_bar, second.ar_bar) == (36, 40), "the second run: climax on day 36, its reaction low on day 40"
    seen = []
    monkeypatch.setattr(bricks, "collect_zigzag_candidates", lambda eq_df, atr, *a, **kw: seen.append(kw) or [])
    first = bricks.find_root_swing(df, 0, 1.0)
    bricks.validate_equilibrium(df, first, 1.0)
    kw = seen[-1]
    assert kw["zigzag"][-1] == (24, "peak", 113.25), "the first run's pairs stop at the next run's climax (day 36)"
    assert kw["answer_line"][-1][0] > 24 and len(kw["answer_line"]) > len(kw["zigzag"]), "the answer reads the whole line"
    assert kw["extra_pairs"] == [(118.25, 105.75, 0, 12)]


def test_the_walk_visits_every_run_under_the_switch(monkeypatch):
    calls = []

    class _Many:
        def find_root_swing(self, df, search_from_bar, atr):
            calls.append(search_from_bar)
            return (SimpleNamespace(climax_bar=search_from_bar, ar_bar=search_from_bar + 1, R=1.0, S=0.0, kind="BC")
                    if search_from_bar < 70 else None)

        def validate_equilibrium(self, df, root, atr, trace=None):
            return None

    df = _frame(LINE_UP, n=90)
    read_structure(df, 1.0, bricks=_Many())
    assert len(calls) == 64, "flag-off: the seed's loop cap"
    calls.clear()
    monkeypatch.setattr(settings, SWITCH, True)
    read_structure(df, 1.0, bricks=_Many())
    assert len(calls) == 71, "under the switch every run is visited, then the walk ends on None"


# ── the answering stage ──────────────────────────────────────────────────────

def test_the_climax_pair_is_examined_before_the_consecutive_limbs():
    spec = [(0, "peak", 118), (4, "valley", 108), (8, "peak", 114), (12, "valley", 106), (16, "peak", 112),
            (20, "valley", 109), (24, "peak", 116), (28, "valley", 107)]
    df = _frame(spec, n=40)
    zig = [(b, k, float(p) + (0.25 if k == "peak" else -0.25)) for b, k, p in spec]
    trace = []
    box_primitives.collect_zigzag_candidates(df, 1.0, zigzag=zig, extra_pairs=[(118.25, 105.75, 0, 12)],
                                             answer_area=0.5, trace=trace)
    assert (trace[0]["r_anchor_bar"], trace[0]["s_anchor_bar"]) == (0, 12), "his first candidate: the climax and its reaction"
    assert (trace[1]["r_anchor_bar"], trace[1]["s_anchor_bar"]) == (0, 4), "then the consecutive limbs, in time order"


def test_a_pair_is_answered_by_a_later_turn_at_each_rail():
    z = [(0, "peak", 110.0), (4, "valley", 100.0), (8, "peak", 109.7), (12, "valley", 100.4), (16, "peak", 112.0)]
    assert box_primitives._answered(z, 110.0, 100.0, 4, 0.5) is True
    assert box_primitives._answered(z[:3], 110.0, 100.0, 4, 0.5) is False, "S not answered yet"
    assert box_primitives._answered(z, 110.0, 100.0, 12, 0.5) is False, "turns at or before the second anchor do not count"
    beyond = [(0, "peak", 110.0), (4, "valley", 100.0), (8, "peak", 111.0), (12, "valley", 99.0)]
    assert box_primitives._answered(beyond, 110.0, 100.0, 4, 0.5) is False, "a turn beyond the area is no answer"


def test_the_answering_stage_refuses_an_unanswered_pair_in_the_trace():
    spec = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 110),
            (20, "valley", 100), (24, "peak", 110), (28, "valley", 100), (32, "peak", 118), (36, "valley", 114)]
    df = _frame(spec, n=45)
    zig = [(b, k, float(p) + (0.25 if k == "peak" else -0.25)) for b, k, p in spec]
    trace = []
    box_primitives.collect_zigzag_candidates(df, 1.0, zigzag=zig, answer_area=0.5, trace=trace)
    stages = {(r["r_anchor_bar"], r["s_anchor_bar"]): r["stage"] for r in trace}
    assert stages[(32, 36)] == "answering", "the last pair's rails were never answered"
    assert stages[(0, 4)] != "answering", "the first pair was answered by the turns after it"
    trace = []
    box_primitives.collect_zigzag_candidates(df, 1.0, zigzag=zig[:2], answer_area=0.5, answer_line=zig, trace=trace)
    assert trace[0]["stage"] != "answering", "with its own turns only the pair is unanswered; the answer line answers it"
    trace = []
    box_primitives.collect_zigzag_candidates(df, 1.0, zigzag=zig[:2], answer_area=0.5, trace=trace)
    assert trace[0]["stage"] == "answering"


# ── the painter, the veto, the RF-4 sites, the fire row ──────────────────────

def test_the_painter_retires_under_the_switch(monkeypatch):
    df = _frame(LINE_UP)
    root = SimpleNamespace(kind="BC", climax_bar=12, ar_bar=24, R=118.25, S=105.75)
    box = SimpleNamespace(start_bar=24, base_len=30, R=118.25, S=105.75)
    raw = []
    monkeypatch.setattr(bricks, "_resolve_phase_a_raw", lambda *a, **k: raw.append(1) or (12, 24))
    monkeypatch.setattr(bricks, "_enforce_bc_downswing", lambda df, root, box, c, a: (c, a))
    monkeypatch.setattr(bricks, "_enforce_climax_terminality", lambda *a, **k: (12, 24))
    assert bricks.resolve_phase_a(df, root, box, 1.0) == (12, 24) and raw == [1]
    monkeypatch.setattr(settings, SWITCH, True)
    assert bricks.resolve_phase_a(df, root, box, 1.0) == (12, 24) and raw == [1], "the root's own pair, no painter"


class _Bricks:
    """A root with a run, a box, an LPS, and a cause read that says the cause is absent."""

    def __init__(self):
        self.cause_calls = 0
        self.box = SimpleNamespace(S=100.0, R=110.0, start_bar=20, box_width=0.1, r_anchor_bar=25, s_anchor_bar=20,
                                   base_len=40)

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar > 10:
            return None
        return SimpleNamespace(climax_bar=10, ar_bar=15, R=110.0, S=100.0, kind="BC",
                               run={"launch_bar": 2, "end_bar": 18, "days": 8, "ranges": 5.0})

    def validate_equilibrium(self, df, root, atr, trace=None):
        return self.box

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = SimpleNamespace(start_bar=55)
        return (lps, Counter()) if diagnose else lps

    def cause_maturity(self, df, box, atr, lps=None):
        self.cause_calls += 1
        return SimpleNamespace(matured=False, bridge_validated=False, pre_box_trend="up", box_trend="up",
                               lps_tightness_ratio=0.99)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar


def test_the_walk_no_longer_abstains_on_the_cause_and_carries_the_run(monkeypatch):
    df = _frame(LINE_UP)
    b = _Bricks()
    monkeypatch.setattr(settings, "CAUSE_BEFORE_EFFECT_VETO_ENABLED", True)
    assert read_structure(df, 1.0, bricks=b) is None and b.cause_calls == 1, "flag-off: the live veto abstains"
    monkeypatch.setattr(settings, SWITCH, True)
    s = read_structure(df, 1.0, bricks=b)
    assert isinstance(s, Structure) and b.cause_calls == 1, "under the switch the cause is never asked"
    assert s.trend == {"launch_bar": 2, "end_bar": 18, "days": 8, "ranges": 5.0}
    assert (s.climax_bar, s.ar_bar) == (10, 15)


def test_the_two_rf4_sites_read_the_line_under_the_switch(monkeypatch):
    df = _frame(LINE_UP)
    seen = []
    import engine_alpha.structure.events.event_map as event_map
    monkeypatch.setattr(phase_a, "macro_bridge_zigzag", lambda *a, **k: [])
    monkeypatch.setattr(event_map, "read_swing_map", lambda df, box, atr, **kw: seen.append(kw.get("line")) or
                        {"pre_box": {"trend_state": "up"}, "box": {"trend_state": "up"}})
    box = SimpleNamespace(S=100.0, R=110.0, start_bar=20, base_len=30, box_width=0.1)
    bricks.cause_maturity(df, box, 1.0, lps=None)
    monkeypatch.setattr(settings, SWITCH, True)
    bricks.cause_maturity(df, box, 1.0, lps=None)
    assert seen == [False, None], "the cause read's staircase: today's skeleton flag-off, the line under the switch"
    floors = []
    monkeypatch.setattr(market_structure, "read_market_structure",
                        lambda df, **kw: floors.append(kw.get("line")) or {"points": []})
    monkeypatch.setattr(settings, SWITCH, False)
    market_structure.trend_terminal_floor(df)
    monkeypatch.setattr(settings, SWITCH, True)
    market_structure.trend_terminal_floor(df)
    assert floors == [False, None]


def test_the_run_rides_the_fire_row_only_under_the_switch(monkeypatch):
    s = SimpleNamespace(trend={"launch_bar": 2, "end_bar": 18, "days": 8, "ranges": 5.0})
    assert evaluation._trend_run_fields(s) == {}
    monkeypatch.setattr(settings, SWITCH, True)
    assert evaluation._trend_run_fields(s) == {"_trend_run_ranges": 5.0, "_trend_run_days": 8}
    assert evaluation._trend_run_fields(SimpleNamespace(trend=None)) == {"_trend_run_ranges": None, "_trend_run_days": None}
