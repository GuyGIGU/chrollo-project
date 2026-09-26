"""The listing gate (task 9 of the two-eyes-reader build): the measurements are pure functions of the line,
so each rule can be reasoned about on a hand-built line before it is trusted on his 35.

What a test here pins, in his words: the candidates are the swings after the end of the trend, walked one foot
at a time; a line is answered when a later swing reached its area and turned back, however far it poked, and a
spring answers at support; a pair became a box on the later of its answering being complete and its fifteenth
trading day from the first anchor; and the two election orders (the day the pair BECAME a box, or the earliest
opening) disagree exactly on a wider pair that opened earlier and was answered later.
"""
from __future__ import annotations
from _paths import REPO_ROOT

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from engine_alpha.two_eyes.line import Turn

_ROOT = str(REPO_ROOT)
_DAY0 = dt.date(2026, 1, 5)


def _day(bar: int) -> dt.date:
    return (pd.Timestamp(_DAY0) + pd.tseries.offsets.BDay(bar)).date()


def _turn(bar: int, kind: str, price: float, know=None) -> Turn:
    know = bar + 1 if know is None else know
    return Turn(bar=bar, day=_day(bar), kind=kind, price=float(price), knowable_bar=know,
                knowable_day=_day(know), size_ranges=1.0)


#: An up run that ends: two rising peaks and valleys, a climax at bar 8, a reaction low at bar 11, then a box.
_RUN_THEN_BOX = [
    _turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 70),
    _turn(7, "valley", 66), _turn(8, "peak", 80),            # the climax
    _turn(9, "valley", 74), _turn(10, "peak", 77), _turn(11, "valley", 70),   # the reaction: its low at bar 11
    _turn(14, "peak", 78),                                   # the first higher low follows, the reaction is decided
    _turn(16, "valley", 71), _turn(20, "peak", 79.6), _turn(24, "valley", 70.3), _turn(28, "peak", 76),
    _turn(30, "valley", 72),
]


def _ranges(n: int, unit: float = 2.0) -> np.ndarray:
    return np.full(n, unit, dtype=float)


# --------------------------------------------------------------------------- #
# The end of the trend, and what sits inside his box                          #
# --------------------------------------------------------------------------- #
def test_the_trend_ends_are_the_runs_of_the_far_view_with_their_reaction_decided():
    from tools.calibration import listing_gate

    ends = listing_gate.trend_ends(_RUN_THEN_BOX)
    # The up run into bar 8 with its reaction low at bar 11; then, at THIS scale, the box's own zigzag reads
    # as two more runs (two lower peaks and valleys down to bar 11, two higher ones up to bar 20) — which is
    # exactly what "a trend end inside his box" looks like when the far floor is too fine.
    assert [(e["kind"], e["climax_bar"], e["ar_bar"]) for e in ends] == \
        [("BC", 8, 11), ("SC", 11, 20), ("BC", 20, 24)]
    # A run whose reaction is not decided by the day it is read is not a trend end that day.
    assert listing_gate.trend_ends(listing_gate.known_by(_RUN_THEN_BOX, 12)) == []


def test_trend_ends_inside_his_box_are_counted_by_their_climax_day():
    from tools.calibration import listing_gate

    ends = [{"kind": "BC", "climax_bar": 8, "ar_bar": 11}, {"kind": "SC", "climax_bar": 20, "ar_bar": 23},
            {"kind": "BC", "climax_bar": 40, "ar_bar": 44}]
    assert listing_gate.split_by_his_box(ends, first_anchor_bar=8, last_bar=30) == {
        "before": [ends[0]], "at": [ends[0]], "inside": [ends[1]], "after": [ends[2]]}


# --------------------------------------------------------------------------- #
# His anchors on the line, and the walk that lists them                       #
# --------------------------------------------------------------------------- #
def test_his_anchors_are_turns_of_the_line_to_the_cent_or_the_miss_is_named():
    from tools.calibration import listing_gate

    got = listing_gate.anchor_turns(_RUN_THEN_BOX, r_bar=14, s_bar=16, r_price=78, s_price=71, unit=2.0)
    assert (got["R"], got["S"]) == (9, 10) and got["why"] is None
    assert (got["r_match"], got["s_match"]) == ("exact", "exact")
    # The same low printed a day later (his click on the second of two equal lows): his LINE is the turn's price
    # to the cent, so the turn is his anchor and the day's difference is named.
    got = listing_gate.anchor_turns(_RUN_THEN_BOX, r_bar=14, s_bar=17, r_price=78, s_price=71, unit=2.0)
    assert got["S"] == 10 and got["s_match"] == "price" and "71.00" in got["why"]
    # A turn near his price but not at it (within a tenth of a range) is a NEAR anchor: reported, never counted
    # as his line; further than that it is no anchor at all, and the line's own turn is named.
    got = listing_gate.anchor_turns(_RUN_THEN_BOX, r_bar=14, s_bar=16, r_price=78.1, s_price=71, unit=2.0)
    assert got["R"] == 9 and got["r_match"] == "near" and "78.00" in got["why"]
    got = listing_gate.anchor_turns(_RUN_THEN_BOX, r_bar=14, s_bar=16, r_price=78.5, s_price=71, unit=2.0)
    assert got["R"] is None and got["r_match"] is None and "78.00" in got["why"]


def test_the_walk_from_a_trend_end_lists_a_pair_by_moving_one_foot_at_a_time():
    from tools.calibration import listing_gate

    end = {"kind": "BC", "climax_bar": 8, "ar_bar": 11}
    # His R is the second peak after the climax, his S the first valley after the reaction low: three moves.
    got = listing_gate.walk_to(_RUN_THEN_BOX, end, r_index=9, s_index=10)
    assert got == {"r_moves": 2, "s_moves": 1, "steps": 3}
    # The pair AT the trend end is listed with no move at all.
    assert listing_gate.walk_to(_RUN_THEN_BOX, end, r_index=5, s_index=8)["steps"] == 0
    # A foot behind the trend end cannot be reached: the feet only move right.
    assert listing_gate.walk_to(_RUN_THEN_BOX, end, r_index=3, s_index=10) is None


def test_the_trend_ends_reaction_is_read_on_the_fine_line_with_or_without_the_climax_bars_own_low():
    from tools.calibration import listing_gate

    end = {"kind": "BC", "climax_bar": 8, "ar_bar": 11}
    # On this line the reaction from the climax (bar 8) is the lowest valley before the first higher low: bar 11.
    assert listing_gate.reaction_on_the_line(_RUN_THEN_BOX, end) == 8
    assert listing_gate.end_pair_on_the_line(_RUN_THEN_BOX, end) == (5, 8)
    # A wide climax bar carrying its own low: that low IS the reaction when the next valley is higher ...
    wide = [_turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 70),
            _turn(7, "valley", 66), _turn(8, "peak", 80), _turn(8, "valley", 72, know=9),
            _turn(10, "peak", 78), _turn(12, "valley", 73), _turn(14, "peak", 79), _turn(16, "valley", 74)]
    assert listing_gate.reaction_on_the_line(wide, end) == 6, "the climax bar's own low, bar 8"
    # ... unless the climax bar's own end is left out, and the reaction starts on the bars after it.
    assert listing_gate.reaction_on_the_line(wide, end, own_end_left_out=True) == 8, "bar 12"
    assert listing_gate.end_pair_on_the_line(wide, end, own_end_left_out=True) == (5, 8)
    # A selling climax mirrors: the reaction is the highest peak before the first lower high, and it is the R foot.
    sc = {"kind": "SC", "climax_bar": 11, "ar_bar": 20}
    assert listing_gate.end_pair_on_the_line(_RUN_THEN_BOX, sc) == (11, 8)


def test_an_undercut_inside_the_area_is_the_same_low_and_one_beyond_it_moves_the_reaction():
    from tools.calibration import listing_gate

    end = {"kind": "BC", "climax_bar": 8, "ar_bar": 11}
    # After the climax (80): lows 74, then 73.6 (0.4 under, inside an area of 1.0), then 78 higher: the
    # reaction is the FIRST low; by the plain rule it would be the lower 73.6.
    line = [_turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 70),
            _turn(7, "valley", 66), _turn(8, "peak", 80), _turn(9, "valley", 74), _turn(10, "peak", 77),
            _turn(11, "valley", 73.6), _turn(14, "peak", 78), _turn(16, "valley", 75)]
    assert listing_gate.reaction_on_the_line(line, end) == 8
    assert listing_gate.reaction_on_the_line(line, end, area=1.0) == 6
    # A second low beyond the area moves the reaction to it.
    deeper = line[:8] + [_turn(11, "valley", 72.5), _turn(14, "peak", 78), _turn(16, "valley", 75)]
    assert listing_gate.reaction_on_the_line(deeper, end, area=1.0) == 8


def test_a_pairs_two_lines_are_the_extremes_of_the_turns_between_its_anchors():
    from tools.calibration import listing_gate

    # (9, 10): R 78 at bar 14, S 71 at bar 16, nothing between: extremes. (7, 10): R 77 at bar 10 with the
    # peak 78 (bar 14) between it and S: not the extreme.
    assert listing_gate.extremes_between(_RUN_THEN_BOX, 9, 10) is True
    assert listing_gate.extremes_between(_RUN_THEN_BOX, 7, 10) is False
    # (9, 12): R 78 at bar 14, S 70.3 at bar 24, and between them only a HIGHER peak (79.6): not the extreme.
    assert listing_gate.extremes_between(_RUN_THEN_BOX, 9, 12) is False
    # The order of the two anchors does not matter: S first (70 at bar 11), then R (79.6 at bar 20), with only
    # a higher valley (71) and a lower peak (78) between: extremes. S 74 at bar 9 with the valley 70 between: not.
    assert listing_gate.extremes_between(_RUN_THEN_BOX, 11, 8) is True
    assert listing_gate.extremes_between(_RUN_THEN_BOX, 11, 6) is False


def test_the_walks_order_breaks_a_tie_before_the_tighter_pair():
    from tools.calibration import listing_gate

    outer = listing_gate.Pair(name="outer", r_index=5, s_index=8, R=80.0, S=70.0, opening_bar=8, second_bar=11,
                              unit=2.0, birth_bar=22, r_known=15, s_known=17, position=0)
    inner = listing_gate.Pair(name="inner", r_index=7, s_index=8, R=77.0, S=70.0, opening_bar=8, second_bar=11,
                              unit=2.0, birth_bar=22, r_known=15, s_known=17, position=1)
    assert listing_gate.winner([outer, inner], 22, "became") is inner, "tighter wins the tie"
    assert listing_gate.winner([outer, inner], 22, "walk") is outer, "the walk's first instance wins the tie"
    with pytest.raises(ValueError):
        listing_gate.winner([outer], 22, "sideways")


def test_pairs_under_a_range_tall_are_set_aside_but_never_his():
    from tools.calibration import listing_gate

    his = _pair("his", opening=5, birth=20, height=0.8)
    tiny = _pair("tiny", opening=0, birth=15, height=0.5)
    tall = _pair("tall", opening=0, birth=25, height=3)
    got = listing_gate.won_by_day([his, tiny, tall], his, bars=range(5, 31), unit=1.0)
    assert got["became"]["on_last"] is False and got["boxes"] == 3
    got = listing_gate.won_by_day([his, tiny, tall], his, bars=range(5, 31), unit=1.0, min_height_ranges=1.0)
    assert got["became"]["on_last"] is True and got["boxes"] == 2, "tiny set aside; his 0.8-range pair kept"


def test_a_trend_end_carrying_its_pair_read_on_the_line_walks_from_that_pair():
    from tools.calibration import listing_gate

    end = {"kind": "BC", "climax_bar": 8, "ar_bar": 11}
    # The far view's reaction low is at bar 11 (index 8); read on the line with undercuts inside the area
    # (2.0 × 0.5 = 1.0) as the same low, the reaction is the FIRST low, bar 9 (index 6): 74 → 70 is beyond
    # the area here, so both readings agree on this line ...
    carried = listing_gate.with_line_feet(end, _RUN_THEN_BOX, _ranges(40))
    assert carried["line_feet"] == (5, 8)
    # ... and on a line whose second low undercuts by less than the area, the walk starts from the first low.
    shallow = _RUN_THEN_BOX[:8] + [_turn(11, "valley", 73.6), _turn(14, "peak", 78), _turn(16, "valley", 71),
                                   _turn(20, "peak", 79.6)]
    carried = listing_gate.with_line_feet(end, shallow, _ranges(40))
    assert carried["line_feet"] == (5, 6)
    assert listing_gate.walk_to(shallow, carried, r_index=5, s_index=6) == {"r_moves": 0, "s_moves": 0, "steps": 0}
    assert listing_gate.walk_to(shallow, end, r_index=5, s_index=6) is None, "the far feet would sit past it"


def test_the_listing_names_the_latest_trend_end_whose_walk_reaches_his_pair():
    from tools.calibration import listing_gate

    ends = [{"kind": "BC", "climax_bar": 2, "ar_bar": 4}, {"kind": "BC", "climax_bar": 8, "ar_bar": 11},
            {"kind": "BC", "climax_bar": 20, "ar_bar": 24}]
    got = listing_gate.listing(_RUN_THEN_BOX, ends, r_index=9, s_index=10)
    assert got["by"] is ends[1] and got["steps"] == 3 and got["by_latest"] is False
    got = listing_gate.listing(_RUN_THEN_BOX, ends, r_index=11, s_index=12)
    assert got["by"] is ends[2] and got["by_latest"] is True
    assert listing_gate.listing(_RUN_THEN_BOX, ends[1:], r_index=1, s_index=2)["by"] is None


# --------------------------------------------------------------------------- #
# Answered his way, and the day the pair became a box                         #
# --------------------------------------------------------------------------- #
def _pair_line():
    # R at bar 10 (100), S at bar 12 (90); the unit is 2.0, so the area is 1.0 either side of a line.
    return [_turn(10, "peak", 100), _turn(12, "valley", 90)]


def test_a_line_is_answered_by_a_swing_that_reached_its_area_and_turned_back():
    from tools.calibration import listing_gate

    short = _pair_line() + [_turn(14, "peak", 98.5, know=15), _turn(16, "valley", 91.5, know=17)]
    got = listing_gate.answered(short, _ranges(40), r_index=0, s_index=1)
    assert got["R"] is None and got["S"] is None
    reached = _pair_line() + [_turn(14, "peak", 99.2, know=15), _turn(16, "valley", 90.9, know=18)]
    got = listing_gate.answered(reached, _ranges(40), r_index=0, s_index=1)
    assert (got["R"], got["S"]) == (2, 3) and (got["r_known"], got["s_known"]) == (15, 18)


def test_a_poke_over_resistance_and_a_spring_under_support_answer_however_far_they_went():
    from tools.calibration import listing_gate

    poked = _pair_line() + [_turn(14, "peak", 104, know=15), _turn(16, "valley", 86, know=17)]
    got = listing_gate.answered(poked, _ranges(40), r_index=0, s_index=1)
    assert (got["R"], got["S"]) == (2, 3)


def test_the_pair_became_a_box_on_the_later_of_its_answering_and_its_fifteenth_day():
    from tools.calibration import listing_gate

    early = _pair_line() + [_turn(14, "peak", 99.5, know=15), _turn(16, "valley", 90.5, know=17)]
    got = listing_gate.answered(early, _ranges(60), r_index=0, s_index=1)
    assert got["complete"] == 17 and got["fifteenth"] == 10 + listing_gate.BOX_DAYS - 1 == 24
    assert got["birth"] == 24, "answered before day fifteen: the clock decides"
    late = _pair_line() + [_turn(14, "peak", 99.5, know=15), _turn(30, "valley", 90.5, know=33)]
    got = listing_gate.answered(late, _ranges(60), r_index=0, s_index=1)
    assert got["complete"] == 33 and got["birth"] == 33, "answered after day fifteen: the answer decides"
    never = _pair_line() + [_turn(14, "peak", 99.5, know=15)]
    assert listing_gate.answered(never, _ranges(60), r_index=0, s_index=1)["birth"] is None


# --------------------------------------------------------------------------- #
# The two election orders                                                     #
# --------------------------------------------------------------------------- #
def _pair(name, opening, birth, height):
    return listing_gate_pair(name, opening, birth, height)


def listing_gate_pair(name, opening, birth, height):
    from tools.calibration.listing_gate import Pair

    return Pair(name=name, r_index=0, s_index=1, R=100.0 + height, S=100.0, opening_bar=opening,
                second_bar=opening + 1, unit=1.0, birth_bar=birth, r_known=birth, s_known=birth)


def test_the_two_orders_disagree_only_on_a_wider_pair_that_opened_earlier_and_was_answered_later():
    from tools.calibration import listing_gate

    wide = _pair("wide", opening=0, birth=30, height=10)
    tight = _pair("tight", opening=5, birth=20, height=4)
    cands = [wide, tight]
    assert listing_gate.winner(cands, 19, "became") is None
    assert listing_gate.winner(cands, 25, "became") is tight
    assert listing_gate.winner(cands, 25, "opening") is tight
    assert listing_gate.winner(cands, 30, "became") is tight, "the pair that became a box first stands"
    assert listing_gate.winner(cands, 30, "opening") is wide, "the earliest opening re-widens the box"


def test_a_tie_on_the_day_the_pair_became_a_box_goes_to_the_earlier_opening_then_the_tighter():
    from tools.calibration import listing_gate

    a = _pair("a", opening=3, birth=20, height=6)
    b = _pair("b", opening=1, birth=20, height=6)
    c = _pair("c", opening=1, birth=20, height=5)
    assert listing_gate.winner([a, b, c], 20, "became") is c


def test_the_day_by_day_record_says_when_his_pair_first_won_and_whether_it_held_on_his_day():
    from tools.calibration import listing_gate

    his = _pair("his", opening=5, birth=20, height=4)
    other = _pair("other", opening=0, birth=25, height=10)
    got = listing_gate.won_by_day([his, other], his, bars=range(5, 31), unit=1.0)
    assert got["became"] == {"first": 20, "on_last": True, "chance_on_last": True, "days": 11}
    assert got["opening"] == {"first": 20, "on_last": False, "chance_on_last": False, "days": 5}
    assert got["boxes"] == 2 and got["born_before_his"] == []


def test_a_winner_within_half_a_range_of_his_lines_is_a_chance_win_and_never_the_headline():
    from tools.calibration import listing_gate

    his = _pair("his", opening=5, birth=20, height=4)
    near = listing_gate.Pair(name="near", r_index=2, s_index=3, R=104.3, S=100.4, opening_bar=4,
                             second_bar=6, unit=1.0, birth_bar=18, r_known=18, s_known=18)
    got = listing_gate.won_by_day([his, near], his, bars=range(5, 31), unit=1.0)
    assert got["became"]["on_last"] is False and got["became"]["chance_on_last"] is True


# --------------------------------------------------------------------------- #
# The candidates the walk generates                                           #
# --------------------------------------------------------------------------- #
def test_the_candidates_are_every_pair_of_feet_after_the_trend_end_within_reach_of_each_other():
    from tools.calibration import listing_gate

    end = {"kind": "BC", "climax_bar": 8, "ar_bar": 11}
    cands = listing_gate.candidates(_RUN_THEN_BOX, _ranges(40), end, feet_apart=2)
    feet = {(c.r_index, c.s_index) for c in cands}
    assert (5, 8) in feet, "the pair at the trend end itself, whatever its reaction's length"
    assert (9, 10) in feet and (9, 8) in feet
    assert all(c.r_index >= 5 and c.s_index >= 8 for c in cands), "no foot behind the trend end"
    assert all(abs(c.r_index - c.s_index) <= 2 or (c.r_index, c.s_index) == (5, 8) for c in cands)
    assert all(c.R > c.S for c in cands)
    one = next(c for c in cands if (c.r_index, c.s_index) == (9, 10))
    assert (one.opening_bar, one.second_bar, one.unit) == (14, 16, 2.0)
    assert one.position == 3, "two moves of R, one of S, from the trend end's pair"
    assert next(c for c in cands if (c.r_index, c.s_index) == (5, 8)).position == 0


# --------------------------------------------------------------------------- #
# The page and the board                                                      #
# --------------------------------------------------------------------------- #
def test_the_page_draws_bars_and_never_candles():
    """His standing rule, and the one thing he checks in the first second."""
    import inspect

    from tools.calibration import listing_gate

    source = inspect.getsource(listing_gate)
    assert "candlestick" not in source.lower()
    assert "_draw_bars" in source, "the bar drawer is the fidelity renderer's; a second copy would drift"


def test_the_board_puts_the_unlisted_first():
    from tools.calibration import listing_gate

    rows = [{"key": "AAA", "listed": True}, {"key": "BBB", "listed": False}, {"key": "CCC", "listed": True}]
    assert [r["key"] for r in listing_gate.unlisted_first(rows)] == ["BBB", "AAA", "CCC"]


# --------------------------------------------------------------------------- #
# One of his own, end to end                                                  #
# --------------------------------------------------------------------------- #
def test_alb_is_listed_with_its_support_first_and_its_two_anchors_adjacent():
    """His ALB: support anchored Tue 03/03/2026 at 157.27, resistance the next day at 173.00 — the two turns
    sit side by side on the line, to the cent, so the walk lists them one move apart."""
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.calibration import listing_gate

    setup = next(s for s in load_corpus() if setup_key(s) == "ALB:2026-04-13")
    frames, _ = load_sealed_fixture()
    row = listing_gate.score_setup(setup, fixture_frame(frames, setup_key(setup), setup["ticker"]), (2.5,))
    assert row["anchors"]["why"] is None and row["gap"] == 1
    at = row["floors"][2.5]
    assert at["listed"]["by"] is not None
    assert row["answered"]["birth"] is not None
    assert set(at["won"]) == set(listing_gate.POOLS) and set(at["won"]["all"]) >= set(listing_gate.ORDERS)
