"""Build step 11 of the final method (docs/final_method_2026-09.md points 6, 8 and 26): the box's end and the
hand-over by swings.

His Q6: "if the price continues to Rise/Fall with out recovering we can deduce that either that the consolidating
structure we measured ended and the price began to trend"; point 26: after the breakout the first swing whose valley
holds in or above the parent's R area is the child's root candidate, confirmed by a later turn at one of its anchors;
point 8: a dip under the support area that fails to recover by the swing is a breakdown, the box ended at its last
turn before the dip. One default-off switch, BOX_END_ENABLED; flag-off byte-identical.
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
from engine_alpha.structure import box_primitives, bricks
from engine_alpha.structure.box_end import _child_end, _leave_bar, box_end, election_bar
from engine_alpha.structure.narrative import Structure, read_structure

SWITCH = "BOX_END_ENABLED"
R, S, UNIT = 110.0, 100.0, 1.0          # a box of ten; the area is half a range


def _turns(spec, forming_last=False):
    out = [(b, k, float(p), b + 1) for b, k, p in spec]
    if forming_last:
        b, k, p, _ = out[-1]
        out[-1] = (b, k, p, None)
    return out


def _closes(n, level=105.0, **at):
    """Closes inside the box, with the days given (bar=price) overridden."""
    c = np.full(n, level, dtype=float)
    for bar, price in at.items():
        c[int(bar[1:])] = price
    return c


@pytest.fixture
def switch_on(monkeypatch):
    monkeypatch.setattr(settings, SWITCH, True)


def test_the_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, SWITCH) is False
    assert settings.BOX_END_BREAKOUT_ATR == 0.10, "R15's margin"
    assert {SWITCH, "BOX_END_BREAKOUT_ATR"} <= set(ENGINE_SETTINGS_KEYS)


# ── the election day and the breakout day ────────────────────────────────────

def test_the_election_commits_when_both_rails_are_answered():
    line = _turns([(0, "peak", 110), (4, "valley", 100), (8, "peak", 109.8), (12, "valley", 100.3), (16, "peak", 112)])
    assert election_bar(line, R, S, 4, 0.5) == 13, "the later of the two answering turns' commits (day 12 commits on 13)"
    assert election_bar(line[:3], R, S, 4, 0.5) is None, "S not answered yet"
    assert election_bar(_turns([(0, "peak", 110), (4, "valley", 100)]), R, S, 4, 0.5) is None


def test_the_breakout_day_is_the_first_close_over_r_by_the_margin():
    closes = _closes(30, b20=110.05, b22=110.2)
    assert _leave_bar(closes, R, 0.10, 4, True) == 22, "110.05 is inside the margin (0.10 ranges); 110.20 is not"
    assert _leave_bar(_closes(30), R, 0.10, 4, True) is None
    assert _leave_bar(_closes(30, b18=99.8, b24=99.95), S, 0.10, 4, False) == 18, "the mirror: the first close under S by the margin"


# ── the hand-over by swings ──────────────────────────────────────────────────

CHILD = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 111),
         (20, "valley", 104), (24, "peak", 118), (28, "valley", 110.2), (32, "peak", 118.3), (36, "valley", 110.4)]


def test_a_child_is_confirmed_when_both_its_anchors_are_answered():
    end, candidate = _child_end(_turns(CHILD), _closes(40, b22=112.0), R, 0.5, 0.10, 12, True)
    assert candidate is None and end is not None
    assert end["kind"] == "hand-over" and end["left_bar"] == 22
    assert (end["child"]["climax_bar"], end["child"]["ar_bar"]) == (24, 28), "the swing off the breakout run's top, holding in the R area"
    assert (end["end_bar"], end["known_bar"]) == (36, 37), "the later of the two answering turns, known on its commit"


def test_one_turn_at_one_anchor_is_the_parents_lps_above_r_not_a_child():
    one_turn = CHILD[:9] + [(36, "valley", 113.0), (40, "peak", 125.0)]
    end, candidate = _child_end(_turns(one_turn), _closes(44, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is None and (candidate["climax_bar"], candidate["ar_bar"]) == (24, 28), \
        "the top was answered, the low was not: the parent goes on (row 1 before row 4)"
    one_low = CHILD[:8] + [(32, "peak", 125.0), (36, "valley", 110.4), (40, "peak", 130.0)]
    end, candidate = _child_end(_turns(one_low), _closes(44, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is None and candidate["ar_bar"] == 28, "the low was answered, the top was not"


def test_a_run_that_comes_back_into_the_box_hands_nothing_over():
    spec = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 114),
            (20, "valley", 106), (24, "peak", 112), (28, "valley", 101), (32, "peak", 109)]
    end, candidate = _child_end(_turns(spec), _closes(36, b14=111.0), R, 0.5, 0.10, 12, True)
    assert end is None and candidate is None, "the first valley after the breakout sits under the R area: the box goes on"
    spec2 = spec + [(36, "valley", 103), (40, "peak", 120), (44, "valley", 112), (48, "peak", 120.2), (52, "valley", 112.3)]
    end, candidate = _child_end(_turns(spec2), _closes(56, b14=111.0, b38=113.0), R, 0.5, 0.10, 12, True)
    assert end is not None and end["left_bar"] == 38 and end["child"]["ar_bar"] == 44 and end["end_bar"] == 52


def test_candidates_accumulate_and_the_first_one_answered_ends_the_parent():
    spec = CHILD[:8] + [(32, "peak", 125), (36, "valley", 118.5), (40, "peak", 124.8), (44, "valley", 118.7)]
    end, candidate = _child_end(_turns(spec), _closes(48, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is not None and end["end_bar"] == 44, "the higher swing's two anchors were both revisited"
    assert (end["child"]["climax_bar"], end["child"]["ar_bar"]) == (32, 36)
    end, candidate = _child_end(_turns(spec[:11]), _closes(44, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is None and candidate["ar_bar"] == 28, "unconfirmed: the first candidate is the chart's state"


def test_no_breakout_means_no_hand_over_and_no_close_level_ends_a_box():
    spec = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 110.4)]
    end, candidate = _child_end(_turns(spec), _closes(20), R, 0.5, 0.10, 12, True)
    assert end is None and candidate is None


# ── the breakdown, the mirror ────────────────────────────────────────────────

BELOW = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 108),
         (20, "valley", 92.0), (24, "peak", 99.6), (28, "valley", 91.8), (32, "peak", 99.4), (36, "valley", 92.2)]


def test_a_child_below_confirmed_by_its_answering_is_the_breakdown():
    end, _ = _child_end(_turns(BELOW), _closes(40, b18=99.8), S, 0.5, 0.10, 12, False)
    assert end is not None and end["kind"] == "breakdown" and end["left_bar"] == 18
    assert (end["child"]["climax_bar"], end["child"]["ar_bar"]) == (20, 24), "the swing off the decline's low, its peak in the S area"
    assert (end["end_bar"], end["known_bar"]) == (32, 33), "the second pair answers both anchors of the child below"
    end, candidate = box_end(_turns(BELOW), _closes(40, b18=99.8), R, S, 0, 4, UNIT)
    assert end["kind"] == "breakdown" and end["end_bar"] == 16, "the parent froze at its last turn before price left"


def test_a_dip_that_recovers_or_confirms_no_child_below_is_not_an_end():
    spring = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 108),
              (20, "valley", 98.0), (24, "peak", 104.0), (28, "valley", 101.0), (32, "peak", 109)]
    assert _child_end(_turns(spring), _closes(36, b18=99.8), S, 0.5, 0.10, 12, False) == (None, None), \
        "the first peak after the dip sits back inside the box: the run came back"
    open_dip = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 108),
                (20, "valley", 92.0), (24, "peak", 99.0), (28, "valley", 90.0)]
    end, candidate = _child_end(_turns(open_dip), _closes(32, b18=99.8), S, 0.5, 0.10, 12, False)
    assert end is None and candidate["ar_bar"] == 24, "a candidate below, unanswered: under S, undetermined"


def test_the_earliest_known_end_wins():
    spec = BELOW + [(40, "peak", 118), (44, "valley", 110.5), (48, "peak", 118.2), (52, "valley", 110.6)]
    end, candidate = box_end(_turns(spec), _closes(56, b18=99.8, b38=112.0), R, S, 0, 4, UNIT)
    assert end["kind"] == "breakdown" and candidate is None


# ── the walk moves on past an ended box ──────────────────────────────────────

class _Bricks:
    """Two roots: the first's box ended (a hand-over), the second's is live with a child candidate."""

    def __init__(self, ends):
        self.ends = ends
        self.reads = []
        self.boxes = {10: SimpleNamespace(S=100.0, R=110.0, start_bar=12, box_width=0.1, r_anchor_bar=16, s_anchor_bar=12,
                                          base_len=40),
                      40: SimpleNamespace(S=112.0, R=120.0, start_bar=42, box_width=0.07, r_anchor_bar=46,
                                          s_anchor_bar=42, base_len=30)}

    def find_root_swing(self, df, search_from_bar, atr):
        for climax in sorted(self.boxes):
            if climax >= search_from_bar:
                return SimpleNamespace(climax_bar=climax, ar_bar=climax + 2, R=1.0, S=0.0, kind="BC", run=None)
        return None

    def validate_equilibrium(self, df, root, atr, trace=None):
        return self.boxes[root.climax_bar]

    def read_box_end(self, df, box, atr):
        self.reads.append(box.R)
        return self.ends.get(box.R, (None, None, 1.0))

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = SimpleNamespace(start_bar=70, end_bar=74, low_bar=72, low=113.0, trigger_price=116.0, length=5, offset=5)
        return (lps, Counter()) if diagnose else lps

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=True, bridge_validated=True, pre_box_trend="", box_trend="", lps_tightness_ratio=0.0)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar


def _frame(n=80):
    idx = pd.bdate_range("2026-01-05", periods=n)
    close = 110.0 + np.sin(np.arange(n) / 3.0)
    return pd.DataFrame({"Open": close, "High": close + 0.5, "Low": close - 0.5, "Close": close, "Volume": 1e6}, index=idx)


def test_an_ended_box_is_never_the_structure_and_the_walk_resumes_after_it(monkeypatch):
    hand_over = {"kind": "hand-over", "end_bar": 36, "known_bar": 37, "left_bar": 30, "child": {"climax_bar": 32, "ar_bar": 34}}
    b = _Bricks({110.0: (hand_over, None, 1.2), 120.0: (None, {"climax_bar": 60, "ar_bar": 64}, 1.4)})
    df = _frame()
    off = read_structure(df, 1.0, bricks=b)
    assert off.R == 110.0 and b.reads == [], "flag-off: the first box is the structure and the end is never read"
    monkeypatch.setattr(settings, SWITCH, True)
    on = read_structure(df, 1.0, bricks=b)
    assert on.R == 120.0, "the ended box is skipped; the walk resumed at the breakout day and found the next run's box"
    assert b.reads == [110.0, 120.0]
    assert on.child == {"climax_bar": 60, "ar_bar": 64} and on.unit == 1.4, "the live box carries its child and its frozen unit"
    # the trace names the end (a provider whose second root has no box, so the walk ends on None)
    b2 = _Bricks({110.0: (hand_over, None, 1.2)})
    b2.boxes = {10: b2.boxes[10]}
    trace = []
    assert read_structure(df, 1.0, bricks=b2, trace=trace) is None
    assert trace[0]["outcome"] == "ended" and trace[0]["end"]["kind"] == "hand-over" and trace[0]["box"]["R"] == 110.0


def test_after_a_breakdown_the_walk_moves_on_to_the_next_run(monkeypatch):
    breakdown = {"kind": "breakdown", "end_bar": 30, "known_bar": 39, "left_bar": 33, "child": {"climax_bar": 34, "ar_bar": 36}}
    b = _Bricks({110.0: (breakdown, None, 1.0), 120.0: (None, None, 1.0)})
    monkeypatch.setattr(settings, SWITCH, True)
    seen = []
    real = b.find_root_swing
    b.find_root_swing = lambda df, search_from_bar, atr: seen.append(search_from_bar) or real(df, search_from_bar, atr)
    on = read_structure(_frame(), 1.0, bricks=b)
    assert on.R == 120.0 and seen == [0, 11], "the ended box is skipped and the next run is asked for, no jump"


def test_fakes_without_the_end_read_keep_working(switch_on):
    b = _Bricks({})
    del b.__class__.read_box_end        # a provider that never learned the read
    try:
        assert read_structure(_frame(), 1.0, bricks=b).R == 110.0
    finally:
        _Bricks.read_box_end = lambda self, df, box, atr: self.ends.get(box.R, (None, None, 1.0))


# ── the retirements ──────────────────────────────────────────────────────────

def test_the_extension_veto_retires_under_the_switch(monkeypatch):
    n = 40
    df = pd.DataFrame({"High": 106.0, "Low": 104.0, "Close": 105.0, "ATR_10": 2.0, "ATR_50": 2.0},
                      index=pd.bdate_range("2026-01-05", periods=n))
    monkeypatch.setattr(evaluation, "read_structure", lambda *a, **k: SimpleNamespace(lps=None))
    monkeypatch.setattr(evaluation, "_structure_to_boxes", lambda s, n: {
        "parent": (20, 110.0, 100.0, 0.10, 3, 3, 0, 1, 2, 0, n - 20, False), "inner": None})
    latest = pd.Series({"Close": 200.0})                   # far over R times 1.15
    assert evaluation._resolve_structure_context(df, latest) is None, "flag-off: the extension veto drops the chart"
    monkeypatch.setattr(settings, SWITCH, True)
    ctx = evaluation._resolve_structure_context(df, latest)
    assert ctx is not None and ctx["res_avg"] == 110.0, "under the switch the box's end decides, never a close level"


def test_the_stale_box_rescues_percent_test_and_the_dethrone_pass_retire(monkeypatch):
    assert box_primitives._still_backing_up(200.0, 110.0, 1.0) is False
    monkeypatch.setattr(settings, "ELECTION_DETHRONE_ENABLED", True)
    assert box_primitives._dethrone_armed(2) is True and box_primitives._dethrone_armed(1) is False
    monkeypatch.setattr(settings, SWITCH, True)
    assert box_primitives._still_backing_up(200.0, 110.0, 1.0) is True, "no close level decides staleness any more"
    assert box_primitives._dethrone_armed(2) is False


def test_a_mini_whose_bottom_holds_the_r_area_is_the_child_not_a_mini(monkeypatch):
    from engine_alpha.structure import inner_box as inner_box_module
    box = SimpleNamespace(S=100.0, R=110.0, start_bar=10, base_len=50, box_width=0.1)
    picked = {"S": 109.8, "R": 116.0, "start_bar": 40, "base_len": 20, "box_width": 0.056, "r_touches": 2, "s_touches": 2,
              "r_anchor_bar": 2, "s_anchor_bar": 0, "source": "midpoint", "search_start_bar": 35, "climax_bar": None,
              "reaction_bar": None, "reaction_pct": None, "reaction_bars": None, "position": None}
    monkeypatch.setattr(bricks, "select_inner_box", lambda *a, **k: dict(picked))
    df = _frame(70)
    assert bricks.find_inner_box(df, box, 1.0) is not None, "flag-off: a tighter band above R is today's mini"
    monkeypatch.setattr(settings, SWITCH, True)
    assert bricks.find_inner_box(df, box, 1.0) is None, "its bottom holds the parent's R area: the child, read by the hand-over"
    picked["S"] = 104.0
    assert bricks.find_inner_box(df, box, 1.0) is not None, "a band inside the box stays a mini"


# ── the states ───────────────────────────────────────────────────────────────

def test_an_unconfirmed_child_is_the_charts_state():
    df = _frame(40)
    s = SimpleNamespace(R=110.0, S=100.0, lps=None, child={"climax_bar": 30, "ar_bar": 34}, lps_in_inner=False)
    out = evaluation._chart_state(df, s, 1.0, [])
    assert out["state"] == "root candidate, unconfirmed" and out["child"] == {"climax_bar": 30, "ar_bar": 34}
    s.child = None
    assert evaluation._chart_state(df, s, 1.0, [])["state"] == "lines, no LPS yet"


def test_a_breakdown_with_nothing_after_it_reads_broke_down():
    end = {"kind": "breakdown", "end_bar": 30, "known_bar": 39}
    trace = [{"outcome": "no_box"}, {"outcome": "ended", "end": end, "box": {"R": 110.0, "S": 100.0, "start_bar": 12}},
             {"outcome": "no_box"}]
    assert evaluation._walk_refused_state(trace) == {"state": "broke down", "end": end}
    handed = {"kind": "hand-over", "end_bar": 36, "known_bar": 37, "left_bar": 30, "child": {}}
    trace[1]["end"] = handed
    assert evaluation._walk_refused_state(trace) == {"state": "no lines", "why": "handed over", "end": handed}
    later = trace + [{"outcome": "no_lps", "box": {"R": 1, "S": 0, "start_bar": 50}}]
    assert evaluation._walk_refused_state(later) == {"state": "no lines", "why": "no_lps"}, "a later box outranks the ended one"
