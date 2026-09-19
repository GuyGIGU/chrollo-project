"""Build step 5 of the final method (Mon 14/09/2026): the words on the line, DARK, behind six flags.

The reader (``engine_alpha/structure/line_words.py``) is measure-only: nothing that elects, vetoes, grades or
displays reads it, and with every step-5 flag off the evaluation never calls it. These tests pin each rule's
clauses on hand-built lines (a line is a list of ``(bar, kind, price, knowable_bar)`` turns, exactly what
``pivots.turn_line`` returns), in more than one daily range so no rule can silently drop its unit; the reader end
to end on a real line; its totality; what each flag lets out; and the fire path's byte-identity through the real
cascade.

His words behind the rules: docs/final_method_2026-09.md (Q11, Q13, Q14, Q15 and the sixteenth-sitting answers).
The rules themselves are my defaults, placed or measured on his 35 marks and recorded as such in
docs/decisions.md (build step 5); THE SOS, the upthrust and the last supper follow his words at the SOS sitting
(Tue 15/09/2026) and his upthrust tweaks of Wed 16/09/2026, on the defaults placed on his drawings then, recorded
as such in docs/decisions.md.
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
STEP5_FLAGS = ("LINE_WORD_SOS_ENABLED", "LINE_WORD_UPTHRUST_ENABLED", "LINE_WORD_LAST_SUPPER_ENABLED",
               "LINE_WORD_PHASE_C_ENABLED", "LINE_WORD_PHASE_D_ENABLED", "LINE_WORD_MINI_ENABLED")
STEP5_NUMBERS = {"LINE_WORD_AREA_ATR": 0.5, "LINE_WORD_SOS_MIN_GROUND_ATR": 1.70,
                 "LINE_WORD_SUPPER_DIG_ATR": 1.5, "LINE_WORD_SUPPER_MAX_DAYS": 4,
                 "LINE_WORD_UPTHRUST_MIN_POKE_ATR": 1.25}
RECORD_KEYS = {"basis", "thrusts", "the_sos", "the_upthrust", "last_suppers", "phase_c", "spring_tests", "phase_d",
               "mini"}
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
    assert (t["launch_bar"], t["swing_bar"], t["ground_ranges"]) == (0, 3, 4.0), \
        "a 1-range pause is inside the thrust; its last swing starts after the pause"


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


# ── THE SOS (his rulings, Tue 15/09/2026) ────────────────────────────────────
# "a push that's like a paradigm shift it signals local buyer strength", in Phase D, that "reaches or breaches local
# Significant Highs like the Resistance". A box from bar 0 read on bar 40 (the middle is bar 20), a daily range of u,
# the rail area 0.5 ranges; every high before the pushes sits at 10 ranges unless a test says otherwise.

def _push(launch, top, top_price):
    return {"launch_bar": launch, "top_bar": top, "top_price": top_price, "launch_price": top_price - 3.0}


def _pick(th, lps_low=38, after=None, highs=None, u=1.0, line=()):
    highs = np.full(41, 10.0 * u) if highs is None else highs
    return W.pick_the_sos(th, lps_low, after, line=list(line), highs=highs, start=0, read_bar=40, unit=u)


@UNITS
@pytest.mark.parametrize("later, picked", [(13.3, 25), (13.5, 25), (13.6, 30)])
def test_a_later_top_that_clears_the_sos_by_less_than_the_area_is_that_high_tested_again(later, picked, u):
    """ALB, NTCT, ST, VLO: his push, a small pause, then a top 0.13 to 0.31 ranges higher, where his last supper or
    his LPS starts. It clears his top by less than the area, so his push stays THE SOS; a top clear of the area is
    a new one."""
    th = [_push(22, 25, 13.0 * u), _push(22, 30, later * u)]
    assert _pick(th, u=u)["top_bar"] == picked


@UNITS
def test_a_push_up_out_of_a_last_supper_with_no_clean_new_high_is_the_run_into_the_lps(u):
    """NTCT, SILC, WTS, ROIV, NGL April: the push the LPS hangs from climbed out of his last supper and topped at most
    a quarter of a range over his SOS. EWTX: his second SOS climbed out of his last supper to a clean new high."""
    sos = _push(22, 25, 13.0 * u)
    assert _pick([sos, _push(30, 34, 13.2 * u)], u=u)["top_bar"] == 25
    assert _pick([sos, _push(30, 34, 13.7 * u)], u=u)["top_bar"] == 34


def test_with_no_push_breaching_the_local_high_the_sos_is_the_last_push_after_the_middle():
    """ANRO ("the last Clear Up swing before the LPS"), BWA, MDT, YPF: no push clears the earlier highs by the area."""
    highs = np.full(41, 10.0)
    highs[5] = 12.8
    th = [_push(22, 25, 13.0), _push(30, 34, 13.1)]
    assert _pick(th, highs=highs)["top_bar"] == 34


def test_the_sos_tops_in_phase_d_after_the_middle_of_the_box():
    """His "it most be in Phase D", and Phase D opens only after the middle (his must, Mon 14/09/2026)."""
    assert _pick([_push(5, 15, 13.0)]) is None, "a push in the first half is no SOS, even the only one"
    assert _pick([_push(12, 20, 13.0)]) is None, "exactly the middle is not after it"
    assert _pick([_push(12, 21, 13.0)])["top_bar"] == 21
    th = [_push(2, 15, 16.0), _push(22, 25, 13.0), _push(30, 34, 13.1)]
    assert _pick(th)["top_bar"] == 34, "a first-half push is no candidate, yet its top still sets the local high"


def test_the_local_high_is_read_before_the_push_began_not_on_its_launch_day():
    """PBT and YPF: a one-day push whose launch day already printed a high near its top still breaches the highs
    before it; reading the launch day too would hand the word to the push before it."""
    highs = np.full(41, 10.0)
    highs[21], highs[22] = 11.0, 12.9
    th = [_push(10, 21, 11.0), _push(22, 23, 13.0)]
    assert _pick(th, highs=highs)["top_bar"] == 23


def test_the_local_high_is_read_since_the_phase_c_tip():
    highs = np.full(41, 10.0)
    highs[8] = 14.0                                    # a Phase B high before the spring
    th = [_push(22, 25, 13.0), _push(30, 34, 13.1)]
    assert _pick(th, highs=highs)["top_bar"] == 34, "from the box start the 14.0 high blocks both: the last push"
    assert _pick(th, highs=highs, after=12)["top_bar"] == 25, "since the Phase C tip on bar 12, the first breaks"


def test_a_first_push_off_the_floor_day_reads_the_peak_the_floor_fell_from():
    """ORMP, FOSL: a push launched on the Phase C tip itself, with no push before it, has no high printed since
    the tip; it is read against the line peak the dip fell from, never cleared by default."""
    line = [(8, P, 14.0, 9), (12, V, 9.0, 13)]           # the dip from 14.0 to the tip on bar 12
    th = [_push(12, 25, 13.0), _push(30, 34, 13.1)]
    assert _pick(th, after=12, line=line)["top_bar"] == 34, "13.0 clears nothing over 14.0: the last push"
    assert _pick([_push(12, 25, 14.6), _push(30, 34, 13.1)], after=12, line=line)["top_bar"] == 25, \
        "14.6 clears the 14.0 peak by more than the area"


def test_the_sos_launches_after_the_phase_c_tip_and_tops_before_the_lps_low():
    th = [_push(15, 25, 13.0), _push(26, 34, 14.0)]
    assert _pick(th, lps_low=30)["top_bar"] == 25, "the day-34 top is past the LPS low"
    assert _pick(th, after=20)["top_bar"] == 34, "the day-15 launch is before a day-20 tip"
    assert _pick(th, lps_low=30, after=20) is None, "nothing launched after the tip tops before the LPS"
    assert _pick([_push(20, 25, 13.0)], after=20)["top_bar"] == 25, "a push launched from the Phase C tip itself"
    assert _pick([_push(22, 30, 13.0)], lps_low=30)["top_bar"] == 30, \
        "a push topping on the LPS low's own day (one wide day carries both, SILC)"


def test_with_no_lps_the_sos_is_read_the_same_way_in_progress():
    th = [_push(22, 25, 13.0), _push(22, 30, 13.3)]
    live = _pick(th, lps_low=None)
    assert (live["top_bar"], live["in_progress"]) == (25, True)
    assert _pick(th)["in_progress"] is False
    assert _pick([], lps_low=None) is None


# ── THE upthrust (his words, Tue 15/09 and his tweaks, Wed 16/09/2026) ───────
# "an Event that belongs in Phase B, it is kind of a 'Reverse' Spring where price climbs quickly out of the
# structure then crashes back into the trading range", and: "not every small false breach of Resistance is one or a
# candidate for one. and only the swinged that actually breached gets to be marked (just like a spring) not the
# entire run up from support with all of the Dips combined, and usually only one UT is present. and it's the most
# major/devolped one rather then tiny hiccups in resistance."
# R 14, S 10, the rail area 0.5, the poke floor 1.25: out of the structure is a top over 15.25, back in the range
# is a valley under 13.5.

def _ut_line(top=16.0, back=11.0):
    return [(0, V, 10.0, 1), (3, P, top, 4), (4, V, back, 5), (8, P, 12.0, None)]


def _ut(line, u=1.0, pc=None, read_bar=20):
    return W.the_upthrust(W.thrusts(line, 0, 14.0 * u, u), line, 14.0 * u, u, pc, 0, read_bar)


@UNITS
def test_an_upthrust_climbs_out_of_the_box_and_crashes_back_into_the_range(u):
    ut = _ut(_s(_ut_line(), u), u)
    assert (ut["swing_bar"], ut["top_bar"], ut["back_bar"], ut["days"]) == (0, 3, 4, 1)
    assert (ut["top_price"], ut["back_price"], ut["poke_ranges"]) == (16.0 * u, 11.0 * u, 2.0)


@UNITS
@pytest.mark.parametrize("back, named", [(13.6, False), (13.5, False), (13.4, True)])
def test_a_fall_that_holds_the_resistance_area_is_no_upthrust(back, named, u):
    assert (_ut(_s(_ut_line(back=back), u), u) is not None) is named, "it must crash back under the R area"


@UNITS
@pytest.mark.parametrize("top, named", [(15.2, False), (15.25, False), (15.3, True)])
def test_a_small_false_breach_of_resistance_is_no_upthrust(top, named, u):
    """HIS, Wed 16/09/2026: "not every small false breach of Resistance is one or a candidate for one ... rather
    then tiny hiccups in resistance." The poke floor, not the rail area: a top 0.6 of a range over R crashing back
    is a hiccup (the breach he crossed out on his UNF, Fri 05/06/2026, was 0.94 over his resistance)."""
    assert (_ut(_s(_ut_line(top=top), u), u) is not None) is named, "it must climb well out of the structure"


@UNITS
def test_only_the_swing_that_breached_is_marked_never_the_whole_run(u):
    """HIS, Wed 16/09/2026: "only the swinged that actually breached gets to be marked (just like a spring) not the
    entire run up from support with all of the Dips combined." The push runs from 10.0 on bar 0 through a 1.2-range
    pause on bar 3, so the thrust launches on bar 0; the upthrust is marked from the pause it broke out of."""
    line = _s([(0, V, 10.0, 1), (2, P, 13.0, 3), (3, V, 11.8, 4), (6, P, 16.0, 7), (7, V, 11.0, 8),
               (10, P, 12.0, None)], u)
    (t,) = [x for x in W.thrusts(line, 0, 14.0 * u, u) if x["top_bar"] == 6]
    assert t["launch_bar"] == 0, "the run itself begins at support"
    ut = _ut(line, u)
    assert (ut["swing_bar"], ut["swing_price"]) == (3, 11.8 * u), "marked from the last swing, not the launch"
    assert (ut["launch_bar"], ut["launch_price"]) == (0, 10.0 * u), "the run it broke out of stays as data"
    assert (ut["top_bar"], ut["back_bar"], ut["candidates"]) == (6, 7, 1)


@UNITS
@pytest.mark.parametrize("tops, named", [((15.6, 16.5), 7), ((16.5, 15.6), 3), ((16.0, 16.0), 3)])
def test_only_the_most_developed_upthrust_is_named(tops, named, u):
    """HIS, Wed 16/09/2026: "usually only one UT is present. and it's the most major/devolped one." Two pushes
    climb out of the box in Phase B and crash back; the one that climbed furthest out is named, first or last, and
    the earlier one when the two climb the same (my default, his word owed). Both are counted."""
    first, second = tops
    line = _s([(0, V, 10.0, 1), (3, P, first, 4), (4, V, 11.0, 5), (7, P, second, 8), (8, V, 11.0, 9),
               (12, P, 12.0, None)], u)
    ut = _ut(line, u)
    assert (ut["top_bar"], ut["candidates"]) == (named, 2)


def test_the_upthrust_belongs_in_phase_b():
    """Before the Phase C tip when the box has one; else at or before the middle of the box."""
    line = _ut_line()
    assert _ut(line, pc={"tip_bar": 4}), "the spring comes after it"
    assert _ut(line, pc={"tip_bar": 3}) is None, "a push topping on or after the spring tip is no upthrust"
    assert _ut(line, read_bar=6), "no spring: the top on bar 3 is at the middle of a 6-day box"
    assert _ut(line, read_bar=5) is None, "no spring: the top on bar 3 is past the middle of a 5-day box"


def test_the_upthrust_needs_the_fall_to_have_printed():
    line = _ut_line()[:2]
    assert _ut(line) is None, "the top is the last turn: nothing has crashed back yet"


def test_an_upthrust_can_crash_back_on_its_own_top_day():
    """One wide day carries the top and the fall back into the range (the line puts the peak first, then the
    valley): the word is dated on that day and becomes knowable when that valley commits."""
    line = [(0, V, 10.0, 1), (3, P, 16.0, 3), (3, V, 11.0, 4), (6, P, 12.0, None)]
    ut = _ut(line)
    assert (ut["top_bar"], ut["back_bar"], ut["days"], ut["knowable_bar"]) == (3, 3, 0, 4)


# ── the last supper (point 15; his BMRN ruling, Tue 15/09/2026) ──────────────
# "a deep correction after the breach of resistance in phase D". Here R 13 (the top at 14.5 clears the area at
# 13.5), no Phase C, a frame read on bar 9 (the middle is 4.5), so the top on bar 5 sits in Phase D.

_SUPPER_HIGHS = np.array([10, 11, 12, 13, 14, 14.5, 14, 13.4, 13.2, 13.0, 12.6, 12.4], dtype=float)


def _suppers(th, lows, u, lps_start, R=13.0, pc=None, read_bar=9):
    return W.last_suppers(th, lows, u, lps_start, R=R * u, pc=pc, start=0, read_bar=read_bar)


@UNITS
def test_a_last_supper_digs_at_least_one_and_a_half_ranges_within_four_trading_days(u):
    th = [{"top_bar": 5, "launch_bar": 0, "top_price": 14.5 * u}]
    lows = (_SUPPER_HIGHS - 0.4) * u
    (s,) = _suppers(th, lows, u, lps_start=11)
    assert (s["top_bar"], s["low_bar"], s["dig_ranges"], s["days"]) == (5, 9, 1.9, 4)
    slow = np.array([9.6, 10.6, 11.6, 12.6, 13.6, 14.1, 14.0, 13.8, 13.6, 13.4, 12.6, 12.4]) * u
    assert _suppers(th, slow, u, lps_start=11) == [], \
        "a 1.1-range dig inside 4 days is not one, even when price goes lower on day 5"


def test_a_last_supper_is_hindsight_and_never_shares_a_day_with_the_lps():
    th = [{"top_bar": 5, "launch_bar": 0, "top_price": 14.5}]
    lows = _SUPPER_HIGHS - 0.4
    assert _suppers(th, lows, 1.0, lps_start=None) == [], "no later LPS yet: no last supper"
    assert _suppers(th, lows, 1.0, lps_start=6) == [], "a drop straight into the LPS is that LPS"
    (s,) = _suppers(th, lows, 1.0, lps_start=9)
    assert (s["low_bar"], s["dig_ranges"]) == (8, 1.7), "the drop is sought only before the LPS opens (MRK)"


@UNITS
@pytest.mark.parametrize("R, named", [(14.6, False), (14.5, False), (14.4, True)])
def test_a_last_supper_follows_a_breach_of_resistance(R, named, u):
    """HIS, Sat 19/09/2026: "every poke over resistance is a breach even small ones count" (his BMRN push tops 0.29 of
    a range over his R, inside the rail area): a top 0.1 of a range over R is a breach."""
    th = [{"top_bar": 5, "launch_bar": 0, "top_price": 14.5 * u}]
    assert bool(_suppers(th, (_SUPPER_HIGHS - 0.4) * u, u, lps_start=11, R=R)) is named, \
        "the top must poke over the resistance"


def test_a_last_supper_sits_in_phase_d():
    th = [{"top_bar": 5, "launch_bar": 0, "top_price": 14.5}]
    lows = _SUPPER_HIGHS - 0.4
    assert _suppers(th, lows, 1.0, lps_start=11, read_bar=10) == [], "the top on bar 5 is the middle of a 10-day box"
    assert _suppers(th, lows, 1.0, lps_start=11, pc={"tip_bar": 5}) == [], "not after the Phase C tip"
    assert _suppers(th, lows, 1.0, lps_start=11, pc={"tip_bar": 4}), "after the tip and after the middle"


# ── the Phase C and the spring test (points 8 and 14) ────────────────────────

@UNITS
def test_phase_c_is_the_deepest_dip_recovered_by_the_swing(u):
    line = _s([(0, P, 11.0, 1), (1, V, 9.0, 2), (2, P, 10.2, 3), (3, V, 9.5, 4),   # 1.0 under S, recovered
               (4, P, 10.6, 5), (5, V, 8.0, 6), (6, P, 10.1, 7), (7, V, 9.2, 8),   # 2.0 under S, recovered
               (8, P, 11.0, None)], u)
    pc = W.phase_c(line, HI * u, 0, 10.0 * u, unit=u, R=12.0 * u, lps_start=None, read_bar=8)
    assert (pc["tip_bar"], pc["depth_ranges"], pc["state"], pc["start_bar"]) == (5, 2.0, "recovered", 4)


def test_a_deeper_dip_that_has_not_recovered_is_not_the_phase_c():
    line = [(0, P, 11.0, 1), (1, V, 9.0, 2), (2, P, 10.2, 3), (3, V, 9.5, 4),
            (4, P, 10.6, 5), (5, V, 7.0, 6), (6, P, 9.0, None)]            # 3.0 under, short of S - 0.5
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0, R=12.0, lps_start=None, read_bar=6)["tip_bar"] == 1, \
        "the deepest RECOVERED dip"


def test_a_deeper_dip_whose_answer_is_still_forming_is_not_the_phase_c():
    line = [(0, P, 11.0, 1), (1, V, 9.0, 2), (2, P, 10.2, 3), (3, V, 9.5, 4),
            (4, P, 10.6, 5), (5, V, 7.0, 6), (6, P, 9.8, 7), (7, V, 8.0, None)]  # its higher low is still forming
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0, R=12.0, lps_start=None, read_bar=7)["tip_bar"] == 1, \
        "recovering is not recovered"


@UNITS
def test_a_dip_inside_the_support_area_is_never_a_phase_c_candidate(u):
    line = _s([(0, P, 11.0, 1), (1, V, 9.6, 2), (2, P, 10.8, 3), (3, V, 10.0, 4), (4, P, 11.0, None)], u)
    assert W.dips(line, HI * u, 0, 10.0 * u, unit=u) == [], "0.4 ranges under S sits inside the 0.5 area"


def test_a_dip_before_the_box_is_not_the_box_s_phase_c():
    line = [(0, P, 11.0, 1), (1, V, 8.0, 2), (2, P, 10.2, 3), (3, V, 9.0, 4),
            (4, P, 10.6, 5), (5, V, 9.2, 6), (6, P, 11.0, None)]
    kw = dict(unit=1.0, R=12.0, lps_start=None, read_bar=6)
    assert W.phase_c(line, HI, 0, 10.0, **kw)["tip_bar"] == 1
    assert W.phase_c(line, HI, 2, 10.0, **kw)["tip_bar"] == 3, "the box opens on bar 2"


# His context going forward (Mon 14/09/2026): "Place also matters a lot and context going forward also plays a
# major part". A dip after which the box went back to R and under the support area again before the right side
# opened was still Phase B (NKTR, ORMP). R 14, S 10, the rail area 0.5, the box midpoint 12.

def test_a_deep_dip_the_range_ran_on_from_is_phase_b_and_the_later_dip_is_the_phase_c():
    line = [(0, P, 14.0, 1), (2, V, 8.0, 3), (4, P, 13.8, 5), (6, V, 9.2, 7), (8, P, 13.6, 9), (10, V, 12.6, 11),
            (12, P, 14.2, None)]
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0, R=14.0, lps_start=None, read_bar=12)["tip_bar"] == 6, \
        "back at R on 4, under the support area on 6: the deeper dip on 2 was Phase B"


@pytest.mark.parametrize("top, back, read_bar, spring",
                         [(15.6, 11.0, 10, None), (15.2, 11.0, 10, 2), (15.6, 11.0, 6, 2), (15.6, 13.8, 10, 2)])
def test_a_dip_before_an_upthrust_is_phase_b(top, back, read_bar, spring):
    """HIS VIK (Sat 19/09/2026): "No for the spring" on the dip of Wed 29/04/2026, before his upthrust of Thu
    14/05/2026, which "belongs in Phase B". The dip on 2 recovers; the top on 4 climbs 1.6 over R and crashes back
    under the R area before the right side opens (on 6): the range was still running. A 1.2 climb is no upthrust,
    a top past the middle of the box (read on bar 6, the middle is 3) is a push in Phase D, and a top whose next
    low holds the R area (13.8) never crashed back: neither is an upthrust."""
    line = [(0, P, 14.0, 1), (2, V, 9.0, 3), (4, P, top, 5), (6, V, back, 7), (8, P, 13.0, None)]
    pc = W.phase_c(line, HI, 0, 10.0, unit=1.0, R=14.0, lps_start=None, read_bar=read_bar)
    assert (pc["tip_bar"] if pc else None) == spring


def test_a_return_after_the_right_side_opened_leaves_the_phase_c_alone():
    line = [(0, P, 14.0, 1), (2, V, 8.0, 3), (4, P, 13.8, 5), (6, V, 10.2, 7), (8, P, 13.7, 9), (10, V, 9.0, 11),
            (11, P, 13.0, None)]
    kw = dict(unit=1.0, R=14.0, lps_start=None)
    assert W.phase_c(line, HI, 0, 10.0, read_bar=11, **kw)["tip_bar"] == 2, \
        "the round trip on 6 sits after the middle of an 11-day box: the right side opened before the return"
    assert W.phase_c(line, HI, 0, 10.0, read_bar=14, **kw) is None, \
        "on a 14-day box that round trip sits before the middle and opens nothing, so the return voids the dip"


def test_a_staircase_before_the_middle_opens_nothing_so_a_later_return_still_voids_the_dip():
    line = [(0, P, 14.0, 1), (2, V, 8.0, 3), (4, P, 13.8, 5), (6, V, 12.5, 7), (8, P, 13.7, 9), (10, V, 12.8, 11),
            (12, P, 13.9, 13), (14, V, 9.0, 15), (16, P, 13.6, 17), (18, V, 12.9, 19), (20, P, 14.0, None)]
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0, R=14.0, lps_start=None, read_bar=22)["tip_bar"] == 14,         "the staircase on 10 sits before the middle of a 22-day box, so the return (13.9, then 9.0) voids the dip on 2"


def test_a_test_right_after_the_dip_before_the_box_gets_back_to_r_never_replaces_it():
    line = [(0, P, 14.0, 1), (2, V, 8.0, 3), (4, P, 10.2, 5), (6, V, 9.0, 7), (8, P, 13.8, 9), (10, V, 12.8, 11),
            (12, P, 14.2, None)]
    assert W.phase_c(line, HI, 0, 10.0, unit=1.0, R=14.0, lps_start=None, read_bar=12)["tip_bar"] == 2


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
    assert (pdr["open_bar"], pdr["opener"], pdr["position"], pdr["before_middle"]) == (6, "round trip", 0.6, [])
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


def test_phase_d_opens_at_the_earliest_of_its_openings_after_the_middle():
    line = _RT_LINE[:4] + [(8, P, 12.5, None)]
    sos = {"launch_bar": 5, "swing_bar": 5, "in_progress": False}
    pdr = W.phase_d(line, 0, 14.0, 10.0, 1.0, _RT_PC, sos, 7, 8)
    assert (pdr["open_bar"], pdr["opener"], pdr["position"]) == (5, "SOS", 0.625)
    assert pdr["openings"] == {"round trip": 6, "SOS": 5, "LPS": 7}
    live = {"launch_bar": 3, "swing_bar": 3, "in_progress": True}
    assert W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, None, live, 9, 10)["openings"] == {"LPS": 9}, \
        "an SOS with no LPS after it opens nothing; the LPS is the fail-safe"


def test_phase_d_must_open_after_the_middle_of_the_box():
    """His ruling Mon 14/09/2026 on 'after the middle': "Yes its a must". An opening at or before the middle stays
    listed and opens nothing."""
    sos = {"launch_bar": 3, "swing_bar": 3, "in_progress": False}
    pdr = W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, _RT_PC, sos, 9, 10)
    assert (pdr["open_bar"], pdr["opener"], pdr["before_middle"]) == (6, "round trip", ["SOS"]), \
        "the SOS launches at 3 of 10: before the middle"
    assert W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, _RT_PC, None, None, 14) is None, "the round trip at 6 of 14"
    pdr = W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, _RT_PC, None, 9, 14)
    assert (pdr["open_bar"], pdr["opener"], pdr["before_middle"]) == (9, "LPS", ["round trip"])
    assert W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, _RT_PC, None, None, 12) is None, \
        "exactly the middle is not after it"


def test_the_sos_opens_phase_d_at_its_last_swing_not_where_the_whole_push_began():
    """His SYRE answer puts Phase D "after the spring and after the price recovers", and his SOS is "a single
    Swing with out dips": a push whose leg is walked back to the spring's own low opens Phase D where its last
    swing starts."""
    sos = {"launch_bar": 2, "swing_bar": 7, "in_progress": False}
    pdr = W.phase_d(_RT_LINE, 0, 14.0, 10.0, 1.0, None, sos, 9, 12)
    assert (pdr["open_bar"], pdr["opener"]) == (7, "SOS"), "not the day-2 launch, on the spring low"


def test_the_staircase_that_opens_phase_d_is_the_first_after_the_middle():
    line = [(0, P, 14.0, 1), (2, V, 12.5, 3), (4, P, 13.7, 5), (6, V, 12.8, 7), (8, P, 13.9, 9),
            (10, V, 12.9, 11), (12, P, 13.8, 13), (14, V, 13.1, 15), (16, P, 14.2, None)]
    pdr = W.phase_d(line, 0, 14.0, 10.0, 1.0, None, None, None, 16)
    assert (pdr["open_bar"], pdr["opener"], pdr["position"]) == (10, "staircase", 0.625), \
        "the staircases complete on 6, 10 and 14; the middle is 8"


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
    assert rec["last_suppers"] == [], "the bar-36 top (15.7) breaches R (15.5) but sits before the middle"
    assert rec["the_upthrust"] is None, "the same top: it never climbs out of the structure"
    assert (rec["phase_c"]["tip_bar"], rec["phase_c"]["state"], rec["phase_c"]["depth_ranges"]) == (30, "recovered", 0.7)
    assert [t["tip_bar"] for t in rec["spring_tests"]] == [42]
    assert rec["phase_d"]["openings"] == {"round trip": 42, "SOS": 42, "LPS": 47}
    assert (rec["phase_d"]["opener"], rec["phase_d"]["position"]) == ("round trip", round(22 / 39, 3))
    assert rec["mini"]["lps_reads_against"] == "parent"
    assert rec["basis"] == {"unit_atr": 1.0, "area_atr": 0.5, "read_bar": 59}


def test_the_reader_names_no_sos_that_launched_before_the_phase_c():
    """His Q11: the SOS sits after the V tip, "either by after Phase C". A late spring, so only the launch floor can
    drop the push before it. Bars 0.4 ranges wide, box from bar 0, R 14, S 10, read on bar 28 (the middle is 14).
    Hand-read: a push from 9.6 on bar 4 climbs out of the box to 16.2 on bar 15, after the middle, and crashes into
    the spring, 8.8 on bar 17; the spring recovers (12.7 on bar 19, a higher low 11.0 on bar 21); the SOS climbs from
    bar 21 to 15.7 on bar 24 and the LPS recedes to 14.4 on bar 26 (its window opens on bar 25). The bar-15 push is
    his upthrust before the spring, never the SOS and never a last supper."""
    path = np.interp(np.arange(29), [0, 4, 15, 17, 19, 21, 24, 26, 28],
                     [12.0, 9.8, 16.0, 9.0, 12.5, 11.2, 15.5, 14.6, 15.3])
    rec = W.read_line_words(_frame(path + 0.2, path - 0.2), _Box(start_bar=0, R=14.0, S=10.0), 1.0,
                            lps=SimpleNamespace(start_bar=25, low_bar=26, low=14.4))
    assert rec["phase_c"]["tip_bar"] == 17
    assert [(t["launch_bar"], t["top_bar"]) for t in rec["thrusts"]] == [(4, 15), (21, 24)]
    assert (rec["the_sos"]["launch_bar"], rec["the_sos"]["top_bar"]) == (21, 24), "the push before the tip is out"
    assert (rec["the_upthrust"]["top_bar"], rec["the_upthrust"]["back_bar"]) == (15, 17)
    assert rec["last_suppers"] == [], "its crash is the spring: before the tip, no last supper"


def test_the_reader_names_the_push_before_the_last_supper_the_sos():
    """His SILC and WTS shape, end to end. Bars 0.4 ranges wide, box from bar 0, R 14, S 10, read on bar 27 (the
    middle is 13.5). Hand-read: the climax high 16.5 on bar 0 sits above R; the spring digs to 8.8 on bar 4 and
    recovers (13.2 on bar 8, a higher low 11.3 on bar 11); the SOS climbs from bar 11 to 16.2 on bar 16, three ranges
    clear of every high since the spring (read from the box start, the climax would block it); the last supper drops
    to 13.0 on bar 18; a push climbs out of it to 15.2 on bar 22, under the SOS top, and the LPS recedes to 14.0 on
    bar 25 (its window opens on bar 23). The old pick, the last push before the LPS, named bar 22."""
    path = np.interp(np.arange(28), [0, 4, 8, 11, 16, 18, 22, 25, 27],
                     [16.3, 9.0, 13.0, 11.5, 16.0, 13.2, 15.0, 14.2, 15.4])
    rec = W.read_line_words(_frame(path + 0.2, path - 0.2), _Box(start_bar=0, R=14.0, S=10.0), 1.0,
                            lps=SimpleNamespace(start_bar=23, low_bar=25, low=14.0))
    assert rec["phase_c"]["tip_bar"] == 4
    assert [(t["launch_bar"], t["top_bar"]) for t in rec["thrusts"]] == [(11, 16), (18, 22), (18, 27)], \
        "the push out of the supper carries on through the LPS to the forming top on bar 27"
    assert (rec["the_sos"]["launch_bar"], rec["the_sos"]["top_bar"]) == (11, 16), "not the push out of the supper"
    assert [(s["top_bar"], s["low_bar"]) for s in rec["last_suppers"]] == [(16, 18)]
    assert rec["the_upthrust"] is None, "both pushes come after the spring: Phase D, no upthrust"


def test_the_reader_names_his_upthrust_before_the_spring():
    """His UNF, end to end, with the run he crossed out. Bars 0.4 ranges wide, box from bar 0, R 14, S 10.5, read on
    bar 26 (the middle is 13). Hand-read: a run leaves support (9.8 on bar 0), pauses at 13.2 on bar 4 and dips to
    11.8 on bar 6 (1.4 ranges, a pause the thrust walks through), then the swing that breaches climbs to 16.2 on bar
    9 and crashes back to 10.8 on bar 11; after a bounce to 12.7 on bar 12 the spring digs to 8.3 on bar 15 and
    recovers (12.9 on bar 19, itself a push off the tip, then a higher low 11.1 on bar 22); the last push climbs to
    15.2 on bar 26, after the spring. The upthrust is marked from the dip on bar 6, not from the run's own start on bar 0."""
    path = np.interp(np.arange(27), [0, 4, 6, 9, 11, 12, 15, 19, 22, 26],
                     [10.0, 13.0, 12.0, 16.0, 11.0, 12.5, 8.5, 12.7, 11.3, 15.0])
    rec = W.read_line_words(_frame(path + 0.2, path - 0.2), _Box(start_bar=0, R=14.0, S=10.5), 1.0)
    assert rec["phase_c"]["tip_bar"] == 15
    assert [(t["launch_bar"], t["swing_bar"], t["top_bar"]) for t in rec["thrusts"]] == [(0, 6, 9), (15, 15, 19), (22, 22, 26)]
    ut = rec["the_upthrust"]
    assert (ut["swing_bar"], ut["top_bar"], ut["back_bar"], ut["days"]) == (6, 9, 11, 2),         "the swing that breached, never the run from support with its dips"
    assert ut["poke_ranges"] == 2.2


def test_the_reader_passes_each_word_its_own_box_day_and_range():
    """Wiring, end to end: a box that opens on bar 6, no Phase C, a daily range of 2. In ranges, R 14, S 10, read on
    bar 39 (the middle is 22.5): a push from bar 6 (10.4) climbs out of the box to 15.6 on bar 21 and crashes back to
    10.8 on bar 23 (his upthrust shape, just in the first half, 1.6 ranges clear of R); the SOS climbs from bar 23 to
    16.4 on bar 27, 0.3 of a range clear of that high's area; the last supper digs to 13.2 on bar 29 (3.2 ranges); a
    push out of it tops at 15.0 on bar 32, and the LPS recedes to 13.3 on bar 34 (its window opens on bar 33). A
    reader handed the wrong box start, read day or daily range names a different set."""
    u = 2.0
    path = np.interp(np.arange(40), [0, 3, 6, 21, 23, 27, 29, 32, 34, 39],
                     [12.0, 15.0, 10.6, 15.4, 11.0, 16.2, 13.4, 14.8, 13.5, 14.6]) * u
    rec = W.read_line_words(_frame(path + 0.2 * u, path - 0.2 * u, atr=u),
                            _Box(start_bar=6, R=14.0 * u, S=10.0 * u), u,
                            lps=SimpleNamespace(start_bar=33, low_bar=34, low=13.3 * u))
    assert rec["phase_c"] is None
    assert [(t["launch_bar"], t["top_bar"]) for t in rec["thrusts"]] == [(6, 21), (23, 27), (29, 32)]
    assert (rec["the_upthrust"]["top_bar"], rec["the_upthrust"]["back_bar"]) == (21, 23)
    assert (rec["the_sos"]["swing_bar"], rec["the_sos"]["top_bar"]) == (23, 27)
    assert [(s["top_bar"], s["low_bar"]) for s in rec["last_suppers"]] == [(27, 29)]
    assert (rec["phase_d"]["opener"], rec["phase_d"]["open_bar"]) == ("SOS", 23)


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
