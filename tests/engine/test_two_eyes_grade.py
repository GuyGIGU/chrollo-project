"""Stage 7 of the two-eyes reader: the grade (build task 14).

His words (Mon 05/10/2026): *"FRPH is total junk because the box is mostly dead space with no visible base
insight"*; *"all of the 40 calibrated should be S tier in my book"*. On COLM (Thu 08/10/2026): *"base dosen't hold
and dosen't answer for an LPS anywhere"*. On the story's pardon (Fri 09/10/2026): *"I'd forgive only that swing,"
correct*; and FRPH's box *"failed long ago"*.

The first law of this file, as of the story's: A GRADE NEVER COSTS A FIRE.
"""
from __future__ import annotations

import datetime as dt
import functools
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from core.calibration.replay import fixture_frame, load_sealed_fixture
from engine_alpha import two_eyes
from engine_alpha.two_eyes import record
from engine_alpha.two_eyes import method_numbers as M


def _stage():
    """The grade stage, imported where it is used, so a reader without it fails each test on what it lacks."""
    from engine_alpha.two_eyes import grade
    return grade
from tools.regression.marks_corpus import load_corpus, setup_key


# --------------------------------------------------------------------------- #
# The rules, on bars made for them                                            #
# --------------------------------------------------------------------------- #
def _grade(bars, *events, turns=(), opening=0, R=11.0, S=10.0, unit=1.0):
    """The grade of a box R / S (daily range ``unit``) over ``bars`` (high, low), read on the last bar."""
    days = [d.date() for d in pd.bdate_range("2026-01-05", periods=len(bars))]
    high = np.array([h for h, _ in bars], dtype=float)
    low = np.array([lo for _, lo in bars], dtype=float)
    line = [SimpleNamespace(day=days[b]) for b in turns]
    return _stage().read(high, low, days, line, [e(days) for e in events], R=R, S=S, unit=unit, opening_bar=opening,
                      read_bar=len(bars) - 1), days


def _event(kind, first, last=None, day=None):
    def make(days):
        swing = kind != record.PHASE_D
        return record.Event(kind=kind, day=days[first if day is None else day], price=10.0,
                            first_day=days[first] if swing else None,
                            last_day=days[first if last is None else last] if swing else None)
    return make


INSIDE = (10.8, 10.2)


def test_a_hair_beyond_a_line_is_respect_and_a_named_swing_is_story_but_phase_d_forgives_nothing():
    """His 30/08/2026 respect and 13/09/2026 story: a day is empty only when its bar misses the box by more than half
    a daily range, outside every named event's own swing. Phase D is a day, not a swing."""
    bars = [INSIDE, (9.7, 9.4), (9.4, 9.0), (11.8, 11.4), (12.0, 11.6), (9.2, 8.8), INSIDE, (9.3, 9.0), INSIDE,
            INSIDE]
    g, _ = _grade(bars, _event(record.SPRING, 5), _event(record.PHASE_D, 7))
    assert (g.empty_days, g.base_days, g.holds) == (3, 10, True), "days 2, 4 and 7 are empty"
    assert g.score == pytest.approx(100 * (1 - 0.3 / 0.5)) and g.letter == "B"


def test_a_named_events_span_forgives_only_its_own_swing_on_the_line():
    """His ruling (Fri 09/10/2026): a two-month stay under the box is no spring's swing. A span of ten days under
    the box, the line turning inside it: only the line's legs into and out of the spring's tip are forgiven."""
    bars = [INSIDE] * 5 + [(9.3, 8.5)] * 10 + [INSIDE] * 5
    spring = _event(record.SPRING, 5, 14, day=9)
    assert _grade(bars, spring)[0].empty_days == 0, "with no turn on the line, the span is the swing"
    assert _grade(bars, spring, turns=(7, 8, 9, 11, 13))[0].empty_days == 6, "8 to 11 forgiven, 5-7 and 12-14 not"
    assert _grade(bars, spring, turns=(7,))[0].empty_days == 2, "no turn after the tip: the swing runs to the read day"


def _with_sos(right_lows, *, base_low=10.2, push_low=10.4, events=()):
    """A box 11 / 10 whose base (days 0 to 7) has its lowest low ``base_low``, THE SOS pushing from day 8 to its top
    on day 10, and the right side's lows after it."""
    highs = [10.8] * 8 + [10.9, 11.5, 12.0] + [11.2] * len(right_lows)
    lows = [10.2, 10.2, base_low] + [10.2] * 5 + [push_low, 10.8, 11.3] + list(right_lows)
    return _grade(list(zip(highs, lows)), _event(record.SOS, 8, 10, day=10), *events)[0]


def test_the_base_does_not_hold_only_when_the_fall_after_the_top_is_beyond_the_area_and_under_the_whole_base():
    """His COLM (Thu 08/10/2026): the base does not hold, it *"reaches a lower level"*. His JAZZ: his own LPS pokes
    under the support, *"on the Support rather then Under it"* (Sun 13/09/2026), and stays over its base's low."""
    assert _with_sos([10.6, 9.4, 10.2], base_low=9.0).holds, "beyond the area, over the spring's tip: holds"
    assert _with_sos([10.6, 9.7, 10.2], base_low=9.8).holds, "under the base's low by a hair, inside the area: holds"
    broke = _with_sos([10.6, 8.9, 10.2], base_low=9.0)
    assert not broke.holds and (broke.score, broke.letter) == (0.0, "C"), "beyond the area and under the whole base"
    assert not _with_sos([10.6, 8.9, 10.2], base_low=9.0,
                         events=(_event(record.LAST_SUPPER, 10, 12, day=10),)).holds, "a named last supper or not"
    assert _with_sos([10.6, 10.2, 10.2], base_low=9.0, push_low=8.0).holds, "the push's days before its top: not read"
    assert _with_sos([], base_low=9.0).holds, "the read day on the top: no right side yet"


def test_the_lines_are_crossed_strictly_a_bar_exactly_half_a_range_out_and_a_low_exactly_on_the_area_are_respect():
    """Respect is a hair up to and including half a daily range (his 30/08/2026): a bar whose low sits exactly half a
    range over the resistance, or whose high sits exactly half a range under the support, is not empty; a fall after
    the top to exactly the support's area does not break the base, nor does the top day's own low (the right side
    starts the day after the top). Values chosen exact in binary (unit 1, area 0.5)."""
    exact = [INSIDE, (12.0, 11.5), (9.5, 9.0), INSIDE]
    assert _grade(exact)[0].empty_days == 0
    assert _grade([INSIDE, (12.0, 11.5 + 2 ** -10), INSIDE])[0].empty_days == 1, "a hair past half a range is empty"
    assert _with_sos([10.6, 9.5, 10.2], base_low=9.75).holds, "a low exactly on the area's edge holds"
    highs = [10.8] * 8 + [10.9, 11.5, 12.0, 11.2]
    lows = [10.2, 10.2, 9.75] + [10.2] * 5 + [10.4, 10.8, 8.0, 10.6]
    top_day_low, _ = _grade(list(zip(highs, lows)), _event(record.SOS, 8, 10, day=10))
    assert top_day_low.holds, "the top day's own low is the push's, not the right side's"


def test_a_named_sos_from_before_the_box_is_story_in_a_base_that_runs_to_the_read_day():
    """His 13/09/2026: a named event's swing is never docked; THE SOS too. A push that began before the box opened ends
    no base, so its days fall inside the base, and those beyond the box are its own swing: forgiven."""
    bars = [INSIDE] * 3 + [(12.0, 11.6)] * 3 + [INSIDE] * 4
    plain, _ = _grade(bars, opening=2)
    named, _ = _grade(bars, _event(record.SOS, 1, 5, day=5), opening=2)
    assert (plain.empty_days, named.empty_days, named.base_days) == (3, 0, 8)


def test_only_an_sos_whose_push_began_after_the_box_opened_ends_the_base():
    """A push that began before the box opened is no SOS of this box: the base runs to the read day and there is no
    right side to fall from."""
    bars = [(10.8, 10.2)] * 8 + [(10.9, 10.4), (11.5, 10.8), (12.0, 11.3), (11.2, 10.6), (11.2, 8.9)]
    after, _ = _grade(bars, _event(record.SOS, 8, 10, day=10))
    before, _ = _grade(bars, _event(record.SOS, 1, 10, day=10), opening=2)
    assert (after.base_days, after.holds) == (8, False)
    assert (before.base_days, before.holds) == (11, True), "the base runs from day 2 to the read day"


def test_the_score_runs_from_no_empty_day_to_half_the_base_and_the_letters_follow():
    """His end: one half, *"mostly dead space"* (FRPH, Mon 05/10/2026); the plan's straight line and cuts."""
    assert (M.GRADE_EMPTY_ZERO, M.GRADE_S, M.GRADE_A, M.GRADE_B) == (0.5, 75.0, 50.0, 25.0)
    under = (9.3, 9.0)
    for n, (score, letter) in {0: (100.0, "S"), 1: (90.0, "S"), 2: (80.0, "S"), 3: (70.0, "A"), 5: (50.0, "A"),
                               6: (40.0, "B"), 8: (20.0, "C"), 10: (0.0, "C"), 15: (0.0, "C")}.items():
        g, _ = _grade([under] * n + [INSIDE] * (20 - n))
        assert (g.score, g.letter) == (pytest.approx(score), letter), n
    assert [_stage().letter(s) for s in (75.0, 74.99, 50.0, 49.99, 25.0, 24.99)] == ["S", "A", "A", "B", "B", "C"]
    with pytest.raises(ValueError):
        record.Grade(score=50.0, letter="D", empty_days=1, base_days=2, holds=True)
    with pytest.raises(ValueError):
        record.Grade(score=101.0, letter="S", empty_days=0, base_days=2, holds=True)


# --------------------------------------------------------------------------- #
# His marked bars                                                             #
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=None)
def _his(key: str) -> record.Read:
    frames, _ = load_sealed_fixture()
    from tools.calibration.yardstick import his_last_lps_day

    setup = next(s for s in load_corpus() if setup_key(s) == key)
    raw = fixture_frame(frames, key, setup["ticker"])
    return two_eyes.read(setup["ticker"], raw.loc[:pd.Timestamp(his_last_lps_day(setup))])


@functools.lru_cache(maxsize=None)
def _junk_fires(ticker: str) -> tuple:
    from tools.calibration import core_board
    from tools.regression import negative_corpus

    frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c.get("key", c["ticker"]) == ticker)
    return tuple(f["read"] for f in core_board.junk_row(case, frames[ticker])["fires"])


def test_his_colm_base_does_not_hold_so_it_grades_c_on_both_fire_days():
    reads = _junk_fires("COLM")
    assert [r.as_of for r in reads] == [dt.date(2026, 6, 22), dt.date(2026, 6, 23)]
    assert all(r.grade.letter == "C" and not r.grade.holds for r in reads)
    assert all(r.fired for r in reads), "the grade decides no fire"


def test_his_frph_box_failed_so_it_grades_under_a_on_every_fire_day():
    reads = _junk_fires("FRPH")
    assert len(reads) == 6 and all(r.grade.letter in ("B", "C") for r in reads)


@pytest.mark.parametrize("key", ["UNF:2026-07-10", "JAZZ:2026-02-24", "MTLS:2026-09-04", "ST:2026-04-17",
                                 "ROIV:2026-06-17", "VLO:2026-07-08", "DRTS:2026-04-15"])
def test_his_setups_grade_s(key):
    """His word: all 40 at S. These seven are the ones an earlier reading of the grade marked down: a box as tall as
    its bars (UNF), an LPS on the support (JAZZ), a dip after a push that stayed over its spring (DRTS), one or two
    days just beyond a line (MTLS, ST, ROIV, VLO)."""
    g = _his(key).grade
    assert g is not None and g.letter == "S" and g.holds, (key, g)


# --------------------------------------------------------------------------- #
# A grade never costs a fire                                                  #
# --------------------------------------------------------------------------- #
def test_a_grade_that_falls_over_leaves_the_read_firing_and_says_why(monkeypatch):
    grade = _stage()
    before = _his("UNF:2026-07-10")
    assert before.fired and before.grade is not None
    frames, _ = load_sealed_fixture()
    raw = fixture_frame(frames, "UNF:2026-07-10", "UNF").loc[:pd.Timestamp(before.as_of)]

    def broken(*args, **kwargs):
        raise RuntimeError("a grade rule fell over")

    monkeypatch.setattr(grade, "read", broken)
    after = two_eyes.read("UNF", raw)
    assert after.fired and after.grade is None
    assert (after.boxes, after.lps, after.state, after.events) == (before.boxes, before.lps, before.state,
                                                                   before.events)
    assert [s for s in after.trail if s.stage != grade.STAGE] == [s for s in before.trail if s.stage != grade.STAGE]
    assert [s.saying for s in after.trail if s.stage == grade.STAGE] == [
        "the grade could not be read (RuntimeError: a grade rule fell over); the read stands without it"]


def test_a_chart_with_no_lines_carries_no_grade():
    days = pd.bdate_range("2026-01-05", periods=5)
    frame = pd.DataFrame({"Open": 10.0, "High": 10.5, "Low": 9.5, "Close": 10.0, "Volume": 1e6}, index=days)
    read = two_eyes.read("T", frame)
    assert read.parent is None and read.grade is None
