"""Build step 5 of the final method (Mon 14/09/2026): the words on the line, DARK, behind five flags.

The reader (``engine_alpha/structure/line_words.py``) is measure-only: nothing that elects, vetoes, grades or
displays reads it, and with every step-5 flag off the evaluation never calls it. These tests pin each rule's
clauses on hand-built lines (a line is a list of ``(bar, kind, price, knowable_bar)`` turns, exactly what
``pivots.turn_line`` returns), in more than one daily range so no rule can silently drop its unit; the reader end
to end on a real line; its totality; what each flag lets out; and the fire path's byte-identity through the real
cascade.

His words behind the rules: docs/final_method_2026-09.md (Q11, Q13, Q14, Q15 and the sixteenth-sitting answers).
The rules themselves are my defaults, placed or measured on his 35 marks and recorded as such in
docs/decisions.md (build step 5); his word on THE SOS, the Phase C and Phase D is still owed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure import line_words as W

V, P = "valley", "peak"
STEP5_FLAGS = ("LINE_WORD_SOS_ENABLED", "LINE_WORD_LAST_SUPPER_ENABLED", "LINE_WORD_PHASE_C_ENABLED",
               "LINE_WORD_PHASE_D_ENABLED", "LINE_WORD_MINI_ENABLED")
STEP5_NUMBERS = {"LINE_WORD_AREA_ATR": 0.5, "LINE_WORD_SOS_MIN_GROUND_ATR": 1.70,
                 "LINE_WORD_SUPPER_DIG_ATR": 1.5, "LINE_WORD_SUPPER_MAX_DAYS": 4}
RECORD_KEYS = {"basis", "thrusts", "the_sos", "last_suppers", "phase_c", "spring_tests", "phase_d", "mini"}
HI = np.full(40, 1000.0)         # highs for Phase C lines whose reach bar the test does not read
UNITS = pytest.mark.parametrize("u", [1.0, 2.5])


def _s(line, u):
    """The same line in a daily range of ``u``: every price scaled, so every distance in ranges is unchanged."""
    return [(b, k, p * u, w) for (b, k, p, w) in line]


@dataclass
class _Box:
    start_bar: int
    R: float
    S: float
    base_len: int = 40


def _frame(highs, lows, atr=1.0):
    return pd.DataFrame({"High": list(highs), "Low": list(lows), "Close": list(lows), "Open": list(lows),
                         "ATR_10": atr})


def _wave_frame():
    """A frame whose daily range is about 1, with waves of 4 to 6 inside a box from bar 20."""
    path = np.interp(np.arange(60), [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 59],
                     [20.0, 14.0, 19.0, 12.0, 16.0, 11.0, 15.5, 11.5, 15.0, 11.0, 14.0])
    return _frame(path + 0.5, path - 0.5), _Box(start_bar=20, R=15.5, S=11.0)


def test_every_step5_flag_is_dark_and_rides_the_manifest():
    for name in STEP5_FLAGS:
        assert getattr(settings, name) is False, name
        assert name in ENGINE_SETTINGS_KEYS, name
    for name, value in STEP5_NUMBERS.items():
        assert getattr(settings, name) == value, name
        assert name in ENGINE_SETTINGS_KEYS, name
    assert set(W._WORDS_BY_FLAG) == set(STEP5_FLAGS), "one flag per word, and every flag lets out a word"


# ── the thrust (point 11) ────────────────────────────────────────────────────

@UNITS
def test_a_thrust_swallows_a_pause_smaller_than_a_last_supper_drop(u):
    line = _s([(0, V, 10.0, 0), (2, P, 12.0, 3), (3, V, 11.0, 4), (5, P, 14.0, 6)], u)
    (t,) = [x for x in W.thrusts(line, 0, R=13.5 * u, unit=u) if x["top_bar"] == 5]
    assert (t["launch_bar"], t["ground_ranges"]) == (0, 4.0), "a 1-range pause is inside the thrust"


@UNITS
def test_a_last_supper_sized_pause_ends_the_thrust(u):
    line = _s([(0, V, 9.0, 0), (2, P, 12.0, 3), (3, V, 10.5, 4), (5, P, 14.0, 6)], u)
    (t,) = [x for x in W.thrusts(line, 0, R=13.5 * u, unit=u) if x["top_bar"] == 5]
    assert (t["launch_bar"], t["ground_ranges"]) == (3, 3.5), "a 1.5-range pause ends the leg"


def test_a_higher_high_inside_ends_the_thrust():
    # The pause off the earlier 13.0 high is only 1.0 range, so ONLY the higher-high clause can stop the walk.
    line = [(0, V, 9.0, 0), (2, P, 13.0, 3), (3, V, 12.0, 4), (5, P, 12.5, 6)]
    assert [x for x in W.thrusts(line, 0, R=12.0, unit=1.0) if x["top_bar"] == 5] == []


@UNITS
@pytest.mark.parametrize("top, named", [(11.5, False), (11.75, True)])
def test_a_thrust_covers_at_least_his_smallest_sos(top, named, u):
    line = _s([(0, V, 10.0, 0), (1, P, top, 2), (2, V, 10.9, None)], u)
    assert bool(W.thrusts(line, 0, R=11.8 * u, unit=u)) is named, "his smallest SOS covers 1.70 ranges"


@UNITS
def test_a_thrust_must_reach_the_resistance_area_or_clear_the_last_swing_high(u):
    short = _s([(0, P, 16.0, 1), (2, V, 10.0, 3), (4, P, 12.0, 5)], u)
    assert W.thrusts(short, 0, R=14.0 * u, unit=u) == [], "under the R area and under the last high"
    higher = _s([(0, P, 11.5, 1), (2, V, 10.0, 3), (4, P, 12.0, 5)], u)
    assert [x["top_bar"] for x in W.thrusts(higher, 0, R=14.0 * u, unit=u)] == [4], "a higher high qualifies it"
    at_r = _s([(0, P, 16.0, 1), (2, V, 11.0, 3), (4, P, 13.6, 5)], u)
    assert [x["top_bar"] for x in W.thrusts(at_r, 0, R=14.0 * u, unit=u)] == [4], "R - 0.5 qualifies it"


def test_a_two_step_push_is_measured_against_the_high_before_it_began():
    """The leg's own pause sits under its top by construction, so it can never be the swing high the push must
    clear: a 1.8-range push in two steps, 3.5 ranges under the high before it, is no thrust."""
    line = [(0, P, 15.3, 1), (5, V, 10.0, 6), (7, P, 11.6, 8), (8, V, 10.8, 9), (10, P, 11.8, 11)]
    assert W.thrusts(line, 0, R=20.0, unit=1.0) == []
    cleared = [(0, P, 11.7, 1)] + line[1:]
    assert [x["top_bar"] for x in W.thrusts(cleared, 0, R=20.0, unit=1.0)] == [10], "clearing it qualifies it"


def test_a_thrust_launches_inside_the_box():
    line = [(0, V, 10.0, 0), (3, P, 14.0, 4)]
    assert W.thrusts(line, 1, R=13.5, unit=1.0) == [], "launch on bar 0, box opens on bar 1"
    assert W.thrusts(line, 0, R=13.5, unit=1.0), "the same leg inside the box is a thrust"
    walk = [(0, V, 9.0, 0), (2, P, 12.0, 3), (3, V, 11.0, 4), (5, P, 14.0, 6)]
    (inside,) = [x for x in W.thrusts(walk, 1, R=13.5, unit=1.0) if x["top_bar"] == 5]
    assert (inside["launch_bar"], inside["ground_ranges"]) == (3, 3.0), "the leg walk stops at the box start"


_TH = [{"top_bar": 10, "launch_bar": 5}, {"top_bar": 20, "launch_bar": 15}, {"top_bar": 30, "launch_bar": 26}]


def test_the_sos_is_the_thrust_the_lps_hangs_from_or_the_last_before_it():
    assert W.pick_the_sos(_TH, 21)["top_bar"] == 20, "the LPS low on day 21 hangs from the day-20 top"
    assert W.pick_the_sos(_TH, 25)["top_bar"] == 20, "or the last thrust before it"
    assert W.pick_the_sos(_TH, 25)["in_progress"] is False
    assert W.pick_the_sos(_TH, 9) is None, "no thrust before the LPS: none is forced"
    live = W.pick_the_sos(_TH, None)
    assert (live["top_bar"], live["in_progress"]) == (30, True), "no LPS yet: the last thrust, in progress"
    assert W.pick_the_sos([], None) is None


def test_the_sos_is_bounded_by_the_lps_low_not_the_window_s_first_day():
    """A window that opens on day 19, a day before the peak it hangs from: bounding by its first day would name the
    day-10 push; the day-23 low keeps the day-20 push (NDSN on the fleet)."""
    assert W.pick_the_sos(_TH, 23)["top_bar"] == 20
    assert W.pick_the_sos(_TH, 19)["top_bar"] == 10, "what the first-day bound would have named"


def test_the_sos_launches_after_the_phase_c_tip_or_the_earlier_lps():
    assert W.pick_the_sos(_TH, 25, after=12)["top_bar"] == 20, "the day-15 launch is after a day-12 tip"
    assert W.pick_the_sos(_TH, 25, after=16) is None, "no push launched after the tip tops before the LPS"
    assert W.pick_the_sos(_TH, 31, after=16)["top_bar"] == 30
    assert W.pick_the_sos(_TH, None, after=27) is None


# ── the last supper (point 15) ───────────────────────────────────────────────

_SUPPER_HIGHS = np.array([10, 11, 12, 13, 14, 14.5, 14, 13.4, 13.2, 13.0, 12.6, 12.4], dtype=float)


@UNITS
def test_a_last_supper_digs_at_least_one_and_a_half_ranges_within_four_trading_days(u):
    th = [{"top_bar": 5, "launch_bar": 0, "top_price": 14.5 * u}]
    lows = (_SUPPER_HIGHS - 0.4) * u
    (s,) = W.last_suppers(th, lows, unit=u, lps_start=11)
    assert (s["top_bar"], s["low_bar"], s["dig_ranges"], s["days"]) == (5, 9, 1.9, 4)
    slow = np.array([9.6, 10.6, 11.6, 12.6, 13.6, 14.1, 14.0, 13.8, 13.6, 13.4, 12.6, 12.4]) * u
    assert W.last_suppers(th, slow, u, lps_start=11) == [], \
        "a 1.1-range dig inside 4 days is not one, even when price goes lower on day 5"


def test_a_last_supper_is_hindsight_and_never_shares_a_day_with_the_lps():
    th = [{"top_bar": 5, "launch_bar": 0, "top_price": 14.5}]
    lows = _SUPPER_HIGHS - 0.4
    assert W.last_suppers(th, lows, 1.0, lps_start=None) == [], "no later LPS yet: no last supper"
    assert W.last_suppers(th, lows, 1.0, lps_start=6) == [], "a drop straight into the LPS is that LPS"
    (s,) = W.last_suppers(th, lows, 1.0, lps_start=9)
    assert (s["low_bar"], s["dig_ranges"]) == (8, 1.7), "the drop is sought only before the LPS opens (MRK)"


# ── the Phase C and the spring test (points 8 and 14) ────────────────────────

@UNITS
def test_phase_c_is_the_deepest_dip_recovered_by_the_swing(u):
    line = _s([(0, P, 11.0, 1), (1, V, 9.0, 2), (2, P, 10.2, 3), (3, V, 9.5, 4),   # 1.0 under S, recovered
               (4, P, 10.6, 5), (5, V, 8.0, 6), (6, P, 10.1, 7), (7, V, 9.2, 8),   # 2.0 under S, recovered
               (8, P, 11.0, None)], u)
    pc = W.phase_c(line, HI * u, 0, 10.0 * u, unit=u)
    assert (pc["tip_bar"], pc["depth_ranges"], pc["state"], pc["start_bar"]) == (5, 2.0, "recovered", 4)


def test_a_deeper_dip_that_has_not_recovered_is_not_the_phase_c():
    line = [(0, P, 11.0, 1), (1, V, 9.0, 2), (2, P, 10.2, 3), (3, V, 9.5, 4),
            (4, P, 10.6, 5), (5, V, 7.0, 6), (6, P, 9.0, None)]            # 3.0 under, short of S - 0.5
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0)["tip_bar"] == 1, "the deepest RECOVERED dip"


def test_a_deeper_dip_whose_answer_is_still_forming_is_not_the_phase_c():
    line = [(0, P, 11.0, 1), (1, V, 9.0, 2), (2, P, 10.2, 3), (3, V, 9.5, 4),
            (4, P, 10.6, 5), (5, V, 7.0, 6), (6, P, 9.8, 7), (7, V, 8.0, None)]  # its higher low is still forming
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0)["tip_bar"] == 1, "recovering is not recovered"


@UNITS
def test_a_dip_inside_the_support_area_is_never_a_phase_c_candidate(u):
    line = _s([(0, P, 11.0, 1), (1, V, 9.6, 2), (2, P, 10.8, 3), (3, V, 10.0, 4), (4, P, 11.0, None)], u)
    assert W.dips(line, HI * u, 0, 10.0 * u, unit=u) == [], "0.4 ranges under S sits inside the 0.5 area"


def test_a_dip_before_the_box_is_not_the_box_s_phase_c():
    line = [(0, P, 11.0, 1), (1, V, 8.0, 2), (2, P, 10.2, 3), (3, V, 9.0, 4),
            (4, P, 10.6, 5), (5, V, 9.2, 6), (6, P, 11.0, None)]
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0)["tip_bar"] == 1
    assert W.phase_c(line, HI, 2, 10.0, unit=1.0)["tip_bar"] == 3, "the box opens on bar 2"


@pytest.mark.parametrize("tail, state", [
    ([(2, P, 9.8, 3), (3, V, 9.4, 4)], "recovered"),                  # reaches S - 0.5, then a higher low
    ([(2, P, 9.8, 3), (3, V, 9.4, None)], "recovering"),              # the higher low is still forming
    ([(2, P, 9.8, None)], "recovering"),                              # reaches, not answered yet
    ([(2, P, 9.8, 3), (3, V, 8.6, 4)], "failed"),                     # a lower low than the tip
    ([(2, P, 9.8, 3), (3, V, 9.0, 4)], "failed"),                     # an equal low is no higher low
    ([(2, P, 9.2, None)], "under S, undetermined"),                   # the up-swing is short of the area
    ([(2, P, 9.3, 3), (3, V, 9.1, 4), (4, P, 9.9, 5), (5, V, 9.3, 6)], "recovered"),   # a later swing reaches
])
def test_recovery_is_read_by_the_swing(tail, state):
    line = [(0, P, 11.0, 1), (1, V, 9.0, 2)] + tail
    d = next(x for x in W.dips(line, HI, 0, 10.0, unit=1.0) if x["tip_bar"] == 1)
    assert d["state"] == state


def test_the_recovery_stamps_its_reach_confirm_and_commit_bars():
    highs = np.array([11, 10, 9, 8.3, 9.0, 9.6, 10.0, 9.5, 9.4, 10.5], dtype=float)
    line = [(0, P, 11.0, 1), (3, V, 8.0, 4), (6, P, 10.0, 7), (8, V, 9.0, 9), (9, P, 10.5, None)]
    (d,) = [x for x in W.dips(line, highs, 0, 10.0, unit=1.0) if x["tip_bar"] == 3]
    assert (d["reach_bar"], d["confirm_bar"], d["knowable_bar"]) == (5, 8, 9), \
        "the first high at S - 0.5 (bar 5, before the peak), the answering valley, its commit"


@UNITS
def test_the_spring_test_is_the_first_valley_back_inside_the_support_area_after_the_phase_c(u):
    pc = {"tip_bar": 1, "tip_price": 8.0 * u}
    line = _s([(0, P, 11.0, 1), (1, V, 8.0, 2), (2, P, 10.2, 3),
               (3, V, 9.2, 4),                  # 0.8 under S: not back inside the area yet
               (4, P, 10.5, 5), (5, V, 9.7, 6),     # 0.3 under S, higher than the tip: THE test
               (6, P, 11.0, 7), (7, V, 9.8, 8),     # another valley in the area: not named
               (8, P, 11.2, None)], u)
    assert [t["tip_bar"] for t in W.spring_tests(line, pc, 10.0 * u, unit=u)] == [5], "one test per Phase C"
    assert W.spring_tests(line, None, 10.0 * u, unit=u) == [], "no Phase C, no spring test"


# ── Phase D (point 12) ───────────────────────────────────────────────────────

_RT_LINE = [(0, P, 14.0, 1), (2, V, 8.5, 3), (4, P, 13.6, 5), (6, V, 9.8, 7), (8, P, 12.5, 9), (10, V, 11.0, None)]
_RT_PC = {"tip_bar": 2, "tip_price": 8.5}


def test_phase_d_opens_on_the_round_trip_after_the_phase_c():
    pdr = W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, _RT_PC, None, None, 10)
    assert (pdr["open_bar"], pdr["opener"], pdr["position"], pdr["after_middle"]) == (6, "round trip", 0.6, True)
    broke = [t if t[0] != 6 else (6, V, 9.2, 7) for t in _RT_LINE]
    assert W.phase_d(broke, 0, 14.0, 10.0, 1.0, _RT_PC, None, None, 10) is None, \
        "the valley after the recovery breaks the support area: no round trip"


def test_a_recovery_whose_peak_is_still_forming_opens_nothing_and_raises_nothing():
    line = [(0, P, 14.0, 1), (2, V, 8.5, 3), (4, P, 13.8, None)]
    assert W.phase_d(line, 0, 14.0, 10.0, 1.0, _RT_PC, None, None, 4) is None


def test_phase_d_opens_on_the_staircase_near_resistance():
    line = [(0, P, 14.0, 1), (2, V, 12.5, 3), (4, P, 13.7, 5), (6, V, 12.8, 7), (8, P, 14.2, None)]
    assert W.phase_d(line, 0, 14.0, 10.0, 1.0, None, None, None, 8)["openings"] == {"staircase": 6}
    assert W.phase_d(line, 1, 14.0, 10.0, 1.0, None, None, None, 8)["position"] == round(5 / 7, 3), \
        "the position is read from the box start"
    low_peak = [t if t[0] != 4 else (4, P, 13.2, 5) for t in line]
    assert W.phase_d(low_peak, 0, 14.0, 10.0, 1.0, None, None, None, 8) is None, "the peak between is under the R area"
    under_mid = [t if t[0] != 2 else (2, V, 11.9, 3) for t in line]
    assert W.phase_d(under_mid, 0, 14.0, 10.0, 1.0, None, None, None, 8) is None, "a valley under the middle"
    assert W.phase_d(line, 3, 14.0, 10.0, 1.0, None, None, None, 8) is None, "the first valley left of the box"


def test_the_staircase_counts_only_after_the_phase_c():
    """His SYRE answer: the right side opens after the spring and after the price recovers."""
    line = [(0, P, 14.0, 1), (2, V, 12.5, 3), (4, P, 13.7, 5), (6, V, 12.8, 7), (8, P, 14.0, 9),
            (10, V, 8.0, 11), (12, P, 13.6, 13), (14, V, 12.9, 15), (16, P, 13.8, 17), (18, V, 13.0, None)]
    pdr = W.phase_d(line, 0, 14.0, 10.0, 1.0, {"tip_bar": 10, "tip_price": 8.0}, None, None, 18)
    assert pdr["openings"] == {"round trip": 14, "staircase": 18}, "the staircase before the Phase C is Phase B"


def test_phase_d_opens_at_the_earliest_of_its_openings():
    sos = {"launch_bar": 3, "in_progress": False}
    pdr = W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, _RT_PC, sos, 9, 10)
    assert (pdr["open_bar"], pdr["opener"]) == (3, "SOS")
    assert pdr["openings"] == {"round trip": 6, "SOS": 3, "LPS": 9}
    live = {"launch_bar": 3, "in_progress": True}
    assert W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, None, live, 9, 10)["openings"] == {"LPS": 9}, \
        "an SOS with no LPS after it opens nothing; the LPS is the fail-safe"


# ── the mini (point 13) ──────────────────────────────────────────────────────

@UNITS
def test_the_mini_is_today_s_elected_inner_box_and_the_lps_reads_against_it_when_near(u):
    inner = SimpleNamespace(R=12.0 * u, S=11.0 * u, start_bar=40, position="inside")
    m = W.mini(inner, SimpleNamespace(start_bar=50, low_bar=52, low=11.2 * u), u, 59)
    assert m == {"start_bar": 40, "end_bar": 59, "R": 12.0 * u, "S": 11.0 * u, "days": 20, "height_ranges": 1.0,
                 "position": "inside", "lps_reads_against": "mini"}
    near = W.mini(inner, SimpleNamespace(start_bar=50, low_bar=52, low=10.6 * u), u, 59)
    assert near["lps_reads_against"] == "mini", "within the rail area under the band"
    far = W.mini(inner, SimpleNamespace(start_bar=50, low_bar=52, low=10.4 * u), u, 59)
    assert far["lps_reads_against"] == "parent"
    assert W.mini(inner, None, u, 59)["lps_reads_against"] is None
    assert W.mini(None, None, u, 59) is None


# ── the reader ───────────────────────────────────────────────────────────────

def test_the_reader_end_to_end_on_a_real_line():
    """The wave path read in full: every word is pinned, so a reader that swaps the rails, shifts the box start
    or drops the LPS goes red. Bars 0.4 ranges wide, so no bar covers the 0.75 floor on its own and the line turns
    only at the knots. Hand-read: peaks 36 (15.7), 48 (15.2); valleys 30 (10.8), 42 (11.3), 54 (10.8); the
    forming top on bar 59 (14.2). Box from bar 20, R 15.5, S 11.5. The engine's LPS window opens on bar 47, a day
    BEFORE the bar-48 peak it hangs from, with its low on bar 54 (the NDSN shape)."""
    path = np.interp(np.arange(60), [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 59],
                     [20.0, 14.0, 19.0, 12.0, 16.0, 11.0, 15.5, 11.5, 15.0, 11.0, 14.0])
    df = _frame(path + 0.2, path - 0.2)
    box = _Box(start_bar=20, R=15.5, S=11.5)
    lps = SimpleNamespace(start_bar=47, low_bar=54, low=10.8)
    inner = SimpleNamespace(R=16.0, S=14.0, start_bar=44, position="inside")
    rec = W.read_line_words(df, box, 1.0, lps=lps, inner=inner)
    assert [(t["launch_bar"], t["top_bar"]) for t in rec["thrusts"]] == [(30, 36), (42, 48)]
    assert (rec["the_sos"]["top_bar"], rec["the_sos"]["in_progress"]) == (48, False), "the push the LPS hangs from"
    assert [(s["top_bar"], s["low_bar"], s["days"]) for s in rec["last_suppers"]] == [(36, 40, 4)]
    assert (rec["phase_c"]["tip_bar"], rec["phase_c"]["state"], rec["phase_c"]["depth_ranges"]) == (30, "recovered", 0.7)
    assert [t["tip_bar"] for t in rec["spring_tests"]] == [42]
    assert rec["phase_d"]["openings"] == {"round trip": 42, "SOS": 42, "LPS": 47}
    assert (rec["phase_d"]["opener"], rec["phase_d"]["position"]) == ("round trip", round(22 / 39, 3))
    assert rec["mini"]["lps_reads_against"] == "parent"
    assert rec["basis"] == {"unit_atr": 1.0, "area_atr": 0.5, "read_bar": 59}


def test_the_reader_names_no_sos_that_launched_before_the_phase_c():
    """His Q11: the SOS sits after the V tip, "either by after Phase C". Bars 0.4 ranges wide. Hand-read: a push
    from bar 0 (9.8) to bar 5 (14.2) reaches the R area; the dip to bar 10 (8.8) recovers by the swing (peak 15 at
    12.2, then the higher low on bar 18 at 10.8, the LPS low). The last leg swallows the 1.4-range pause off bar
    15, so it launches at bar 10 and tops on bar 22 at 12.7: under the R area and under the bar-5 high, no thrust."""
    path = np.interp(np.arange(23), [0, 5, 10, 15, 18, 22], [10.0, 14.0, 9.0, 12.0, 11.0, 12.5])
    rec = W.read_line_words(_frame(path + 0.2, path - 0.2), _Box(start_bar=0, R=14.0, S=10.5), 1.0,
                            lps=SimpleNamespace(start_bar=16, low_bar=18, low=10.8))
    assert [(t["launch_bar"], t["top_bar"]) for t in rec["thrusts"]] == [(0, 5)]
    assert rec["phase_c"]["tip_bar"] == 10
    assert rec["the_sos"] is None, "the only push before the LPS launched before the Phase C: no SOS is named"


@pytest.mark.parametrize("case", ["empty", "one bar", "nan unit", "zero unit", "no range column", "flat"])
def test_the_reader_is_total(case):
    highs = np.array([10, 12, 11, 13, 12.5, 14, 13, 15.0])
    df, unit = _frame(highs, highs - 1), 1.0
    if case == "empty":
        df = df.iloc[:0]
    elif case == "one bar":
        df = df.iloc[:1]
    elif case == "nan unit":
        unit = float("nan")
    elif case == "zero unit":
        unit = 0.0
    elif case == "no range column":
        df = df.drop(columns="ATR_10")
    elif case == "flat":
        df = _frame([10.0] * 8, [10.0] * 8, atr=0.0)
    rec = W.read_line_words(df, _Box(start_bar=2, R=14.0, S=10.0), unit, lps=None, inner=None)
    assert set(rec) == RECORD_KEYS
    json.dumps(rec)


def test_the_reader_reads_the_line_it_is_given_and_nothing_else(monkeypatch):
    df, box = _wave_frame()
    lps = SimpleNamespace(start_bar=49, low_bar=54, low=10.5)
    rec = W.read_line_words(df, box, 1.0, lps=lps)
    assert rec["thrusts"] and rec["phase_d"] is not None, "the wave frame carries words"
    for name, value in (("TRAVERSAL_NOISE_FRAC", 0.99), ("SOS_NEAR_R_MAX_BOX", 0.01),
                        ("SOS_HOLD_MAX_RANGE_BOX", 0.01), ("EVENT_HOLD_MIN_BARS", 99),
                        ("TURN_LINE_ENABLED", True), ("TURN_LINE_TREND_ENABLED", True)):
        monkeypatch.setattr(settings, name, value)
    assert W.read_line_words(df, box, 1.0, lps=lps) == rec, \
        "no box-height knob, hold clock or line flag moves a word"


def test_each_flag_lets_out_only_its_own_words(monkeypatch):
    df, box = _wave_frame()
    rec = W.read_line_words(df, box, 1.0, lps=SimpleNamespace(start_bar=49, low_bar=54, low=10.5))
    assert not W.any_word_enabled()
    assert json.loads(W.emitted(rec)) == {"basis": rec["basis"]}
    for flag, keys in W._WORDS_BY_FLAG.items():
        monkeypatch.setattr(settings, flag, True)
        assert W.any_word_enabled(), flag
        assert set(json.loads(W.emitted(rec))) == {"basis", *keys}, flag
        monkeypatch.setattr(settings, flag, False)


def test_no_step5_flag_moves_the_swing_map(monkeypatch):
    from engine_alpha.structure.event_map import read_swing_map
    df, box = _wave_frame()
    off = read_swing_map(df, box, 1.0)
    for flag in STEP5_FLAGS:
        monkeypatch.setattr(settings, flag, True)
    assert read_swing_map(df, box, 1.0) == off, "the words never feed the swings the cause veto reads"


# ── the real cascade (EC-17) ─────────────────────────────────────────────────

def _fixture():
    from tools.shadow_diff import _load_fixture

    frames, scalars = _load_fixture()
    breadth = scalars.get("breadth_pct")
    return frames, scalars, float(scalars.get("spy_6m_return", 0.0)), (float(breadth) if breadth is not None else None)


def _first_firing_fixture_ticker():
    """One real firing (ticker, frame, result, spy, breadth) off the committed shadow fixture."""
    from core.pipeline.screener import _evaluate_ticker
    from engine_alpha.evaluation import EVAL_ERROR

    frames, scalars, spy, breadth = _fixture()
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = _evaluate_ticker(ticker, df, spy, breadth)
        if result is not None and result is not EVAL_ERROR:
            return ticker, df, result, spy, breadth
    raise AssertionError("no shadow-fixture ticker fires — rebuild the fixture")


def test_flag_off_the_evaluation_never_reads_the_words(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("the words were read with every step-5 flag off")

    monkeypatch.setattr(W, "read_line_words", _boom)
    _ticker, _df, result, _spy, _breadth = _first_firing_fixture_ticker()
    assert "_line_words_json" not in result and result["Score"] > 0


def test_flag_on_the_words_ride_out_and_nothing_else_moves(monkeypatch):
    """Every fixture ticker that fires, flags off then on: one diagnostic key added and nothing else moved. The
    words are tied to the fire's own record: the thrusts launch inside the elected box (its _base_len), and the
    mini is the fire's own inner box."""
    from core.pipeline.screener import _evaluate_ticker
    from engine_alpha.evaluation import EVAL_ERROR
    from tools.shadow_diff import CANONICAL_FIELDS

    frames, scalars, spy, breadth = _fixture()
    off = {}
    for ticker in scalars["tickers"]:
        if frames.get(ticker) is not None:
            r = _evaluate_ticker(ticker, frames[ticker], spy, breadth)
            if r is not None and r is not EVAL_ERROR:
                off[ticker] = r
    for flag in STEP5_FLAGS:
        monkeypatch.setattr(settings, flag, True)
    minis = 0
    for ticker, before in off.items():
        on = _evaluate_ticker(ticker, frames[ticker], spy, breadth)
        assert on is not EVAL_ERROR and on is not None, f"{ticker}: the words cost a fire"
        assert set(on) - set(before) == {"_line_words_json"}, ticker
        assert {k: on[k] for k in before} == before, f"{ticker}: a pre-existing field moved flag-on"
        for key in CANONICAL_FIELDS:
            assert on[key] == before[key], (ticker, key)
        words = json.loads(on["_line_words_json"])
        assert set(words) == RECORD_KEYS, ticker
        assert "LPS" in words["phase_d"]["openings"], f"{ticker}: the elected LPS reached the reader"
        assert words["the_sos"] is None or words["the_sos"]["in_progress"] is False, ticker
        box_start = words["basis"]["read_bar"] + 1 - int(before["_base_len"])
        assert all(t["launch_bar"] >= box_start for t in words["thrusts"]), ticker
        if words["mini"] is not None:
            minis += 1
            assert (words["mini"]["R"], words["mini"]["S"]) == (before["_inner_R"], before["_inner_S"]), ticker
            assert words["mini"]["start_bar"] == before["_inner_start_bar"], ticker
    assert len(off) >= 20 and minis >= 1, (len(off), minis)
