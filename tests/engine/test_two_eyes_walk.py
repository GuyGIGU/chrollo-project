"""Stages 2 and 3 of the two-eyes reader (task 10): the end of the trend, the two-legs walk, answered his way,
and the election — his picture first, then the rules on a hand-built line, then his 35 drawings.

His words that these pin:

* respect (Sat 26/09/2026, with a screenshot of one of his boxes): "one way to find out whenever a bar is
  respecting support resistance or both is to look at their High and Low values" — a bar whose H and L touch
  both lines respects both; small bars low in the box with H and L close to support, "whenever they are slightly
  poking out or not does not matter one bit", are "respecting support and in fact resting on it"; bars whose H is
  close to resistance respect it, "and even the single bar between them that his L value is close to the
  resistance counts as respect";
* the undercut (same day, on MDT): a low under the anchored support is respected when the bar is close to the
  line and "the entire continues swing structure ... is still wrapped within the anchored box";
* the walk (Sun 20/09/2026): "I move one pair right until I find it, not only a single time. -> one line can stay
  on its anchor while the other moves, but they are connected like 2 lets placing one in front of the other";
* the box (Sun 06/09/2026, Sat 12/09/2026): "were looking for the first instance that a consolidation is
  respected!" — "Lets go with 15 days".
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
    """A turn committed on the next bar's close unless said otherwise; ``know=False`` is the forming turn."""
    know = bar + 1 if know is None else (None if know is False else know)
    return Turn(bar=bar, day=_day(bar), kind=kind, price=float(price), knowable_bar=know,
                knowable_day=None if know is None else _day(know), size_ranges=1.0)


def _ranges(n: int, unit: float = 2.0) -> np.ndarray:
    return np.full(n, unit, dtype=float)


def _far(fine: list, bars: tuple) -> list:
    """The far view is a fold of the fine line: the fine turns on these bars, nothing else."""
    return [t for t in fine if t.bar in bars]


#: A rise into a climax at bar 8 (80), the reaction low at bar 11 (70), then the box — with a short high (78)
#: before resistance is answered, a deep low (67) after the reaction was decided, and a deep low (66) after the
#: box was born. The area is one point (half of a two-point daily range).
_RISE_THEN_BOX = [
    _turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 70),
    _turn(7, "valley", 66), _turn(8, "peak", 80),                       # the climax
    _turn(9, "valley", 74), _turn(10, "peak", 77), _turn(11, "valley", 70),   # the reaction low
    _turn(13, "peak", 78),                                              # short of resistance's area
    _turn(16, "valley", 71),                                            # the higher low: the reaction is decided; support answered
    _turn(18, "peak", 75),
    _turn(20, "valley", 67),                                            # beyond support's area before the box is born
    _turn(22, "peak", 79.5),                                            # resistance answered
    _turn(24, "valley", 70.5), _turn(26, "peak", 78.8), _turn(28, "valley", 69.6), _turn(31, "peak", 79.2),
    _turn(33, "valley", 70.4), _turn(36, "peak", 78),
    _turn(40, "valley", 66),                                            # beyond support's area AFTER the box is born
    _turn(42, "peak", 77), _turn(44, "valley", 72, know=False),
]
_RISE_FAR = _far(_RISE_THEN_BOX, (0, 2, 4, 6, 7, 8, 11, 13, 20, 22, 28, 31, 40, 42))

#: A rise into a climax at bar 8 (80) and its reaction low at bar 11 (70), with a one-and-a-half-point bounce
#: (71.5) right after the low: resistance is missed (75) before it is answered (79.5), so the walk lists the
#: tiny pair 71.5 / 70 on its way.
_RISE_WITH_A_TINY_BOUNCE = [
    _turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 70),
    _turn(7, "valley", 66), _turn(8, "peak", 80), _turn(11, "valley", 70),
    _turn(13, "peak", 71.5), _turn(15, "valley", 70.8), _turn(18, "peak", 75), _turn(20, "valley", 72),
    _turn(22, "peak", 79.5), _turn(26, "valley", 70.5), _turn(29, "peak", 79.2), _turn(32, "valley", 71),
    _turn(35, "peak", 78.8, know=False),
]
_TINY_FAR = _far(_RISE_WITH_A_TINY_BOUNCE, (0, 2, 4, 6, 7, 8, 11, 18, 20, 22, 26, 29, 32))


def _feet(pair) -> tuple:
    return (pair.r_index, pair.s_index)


# --------------------------------------------------------------------------- #
# His picture: respect is the nearness of a bar's high or low to a line       #
# --------------------------------------------------------------------------- #
def test_his_picture_a_bar_respects_a_line_when_its_high_or_low_is_close_to_it_on_either_side():
    """The bars he marked on Sat 26/09/2026, on a box 100 / 90 with a two-point daily range (the area is one)."""
    from engine_alpha.two_eyes.walk import bar_respects

    R, S, area = 100.0, 90.0, 1.0
    # Red: the anchor bar, its high on resistance and its low on support — it respects both.
    assert bar_respects(100.0, 90.0, R, area) and bar_respects(100.0, 90.0, S, area)
    # Blue: small bars dwelling low in the box, high and low both close to support, the low poking under —
    # "whenever they are slightly poking out or not does not matter one bit": resting on support.
    for high, low in ((91.2, 89.4), (90.8, 90.1), (90.3, 89.7)):
        assert bar_respects(high, low, S, area) and not bar_respects(high, low, R, area)
    # Green: bars whose high is close to resistance, from under it or poking over it.
    for high, low in ((99.6, 96.0), (100.7, 97.0)):
        assert bar_respects(high, low, R, area) and not bar_respects(high, low, S, area)
    # "even the single bar between them that his L value is close to the resistance counts as respect": a bar
    # sitting above resistance, resting on it from above.
    assert bar_respects(103.0, 100.6, R, area)
    # A bar in the middle of the box respects neither line; a bar well under support has left the box.
    assert not bar_respects(96.0, 94.0, R, area) and not bar_respects(96.0, 94.0, S, area)
    assert not bar_respects(88.5, 86.0, S, area)
    # Either side is the same distance: poking out is not different from stopping short.
    from engine_alpha.two_eyes.walk import respects
    assert respects(89.4, S, area) == respects(90.6, S, area) is True
    assert respects(88.9, S, area) == respects(91.1, S, area) is False


# --------------------------------------------------------------------------- #
# Stage 2: the end of the trend, its pair read on the line                    #
# --------------------------------------------------------------------------- #
def test_the_trend_end_is_a_run_of_the_far_view_that_ended_and_its_pair_is_read_on_the_fine_line():
    from engine_alpha.two_eyes import walk

    ends = walk.trend_ends(_RISE_FAR)
    # The rise into bar 8; then, at this scale, the box's own legs read as runs too (down to 67, up to 79.5) —
    # the listing gate's finding at a fine far floor. Every end walks; the election has to survive them.
    assert [(e["kind"], e["climax_bar"]) for e in ends] == [("BC", 8), ("SC", 20), ("BC", 22)]
    # The run ended when the far view printed a lower high (bar 13), known on its close (bar 14).
    assert ends[0]["end_bar"] == 13 and ends[0]["known_bar"] == 14
    # Its pair on the LINE: the climax, and point 4's reaction low read on the fine turns — the lowest low
    # before the first higher low (bar 16, known bar 17), so the pair is listed on bar 17. The far view's own
    # reaction low (67, bar 20) is NOT the foot: its folded swings overshoot his support (task 9).
    r, s, joined = walk.end_pair(_RISE_THEN_BOX, _ranges(46), ends[0])
    assert (_RISE_THEN_BOX[r].bar, _RISE_THEN_BOX[s].bar) == (8, 11) and joined == 17
    # A run whose end is not yet known is no trend end that day.
    assert walk.trend_ends(walk.known_by(_RISE_FAR, 13)) == []


def test_the_reaction_leaves_the_climax_bars_own_low_out_and_reads_an_undercut_inside_the_area_as_the_same_low():
    from engine_alpha.two_eyes import walk

    # A wide climax bar carries its own low (79); the first low after it is higher (79.3), so a plain reading
    # would end the reaction on the climax bar itself. His support is never the climax bar's own end.
    wide = [_turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 70),
            _turn(7, "valley", 66), _turn(8, "peak", 80), _turn(8, "valley", 79, know=9),
            _turn(10, "peak", 79.8), _turn(10, "valley", 79.3, know=11), _turn(12, "peak", 79.6),
            _turn(12, "valley", 76, know=13), _turn(14, "peak", 78), _turn(14, "valley", 77, know=15),
            _turn(16, "peak", 79)]
    end = {"kind": "BC", "climax_bar": 8, "climax_price": 80.0, "end_bar": 14, "known_bar": 15}
    r, s, _ = walk.end_pair(wide, _ranges(20), end)
    assert (wide[r].bar, wide[s].bar) == (8, 12)
    # MDT, his ruling: a later low under the reaction low by less than the area is the same low — respected,
    # the swing structure still wrapped — so support stays on the first reaction low.
    undercut = list(_RISE_THEN_BOX)
    undercut[10] = _turn(16, "valley", 69.5)
    end = walk.trend_ends(_RISE_FAR)[0]
    r, s, _ = walk.end_pair(undercut, _ranges(46), end)
    assert (undercut[r].bar, undercut[s].bar) == (8, 11)


# --------------------------------------------------------------------------- #
# Stage 3: answered his way, the walk, the election                           #
# --------------------------------------------------------------------------- #
def test_a_line_is_answered_by_the_first_later_swing_within_its_area_and_the_pair_is_a_box_on_the_later_of_three_days():
    from engine_alpha.two_eyes import walk

    result = walk.elect(_RISE_THEN_BOX, _RISE_FAR, _ranges(46))
    root = result.pairs[(5, 8)]
    assert (root.R, root.S) == (80.0, 70.0) and root.position == 0
    # Support answered by the higher low at 71 (bar 16), resistance by 79.5 (bar 22): each known on the close
    # that committed the turn. The short high at 78 answered nothing.
    assert (root.s_answer, root.s_known) == (10, 17) and (root.r_answer, root.r_known) == (13, 23)
    # Born on the later of: both answered (23), its fifteenth trading day from the first anchor (22), and the
    # day the walk listed it (17).
    assert root.fifteenth == 22 and root.joined_bar == 17 and root.birth_bar == 23
    # The box of the trend end into bar 8 is this pair; on bar 34 the read shows it.
    assert _feet(walk.box_of(p for p in result.pairs.values() if p.end_climax_bar == 8)) == (5, 8)
    on_34 = walk.elect(walk.known_by(_RISE_THEN_BOX, 34), walk.known_by(_RISE_FAR, 34), _ranges(46), read_bar=34)
    assert _feet(on_34.winner) == (5, 8)


def test_an_undercut_inside_the_area_answers_support_and_the_swing_beyond_it_does_not():
    from engine_alpha.two_eyes import walk

    undercut = list(_RISE_THEN_BOX)
    undercut[10] = _turn(16, "valley", 69.5)               # a quarter of a range under support: resting on it
    root = walk.elect(undercut, _RISE_FAR, _ranges(46)).pairs[(5, 8)]
    assert root.s_answer == 10
    # The low at 67 (bar 20) is beyond support's area: not an answer — support was already answered, and it
    # steps a foot instead (below).
    assert root.s_answer != 12


def test_the_walk_moves_one_foot_one_turn_right_when_a_line_is_missed_or_left_before_the_pair_is_a_box():
    from engine_alpha.two_eyes import walk

    result = walk.elect(_RISE_THEN_BOX, _RISE_FAR, _ranges(46))
    # Resistance was missed by the 78 high (bar 13) while unanswered: resistance steps to the first peak IN FRONT
    # of the other foot — past the reaction's small swing (77, bar 10) to the base's own first high (78, bar 13)
    # — and support stays; listed on the day the miss was known, never before the trend end.
    assert (7, 8) not in result.pairs
    stepped_r = result.pairs[(9, 8)]
    assert (stepped_r.R, stepped_r.S) == (78.0, 70.0) and stepped_r.position == 1
    assert stepped_r.parent == (5, 8) and stepped_r.joined_bar == 17 and "resistance" in stepped_r.reason
    # Support was left by the 67 low (bar 20, known 21) before the pair was born (23): support steps to the next
    # valley right of the reaction low (71, bar 16), resistance stays.
    stepped_s = result.pairs[(5, 10)]
    assert (stepped_s.R, stepped_s.S) == (80.0, 71.0) and stepped_s.position == 1
    assert stepped_s.parent == (5, 8) and stepped_s.joined_bar == 21 and "support" in stepped_s.reason
    # The 66 low (bar 40) came after the box was born: the box's life (stage 4), never a step of the walk.
    assert all(_RISE_THEN_BOX[feet[1]].bar != 40 for feet in result.pairs)
    # Every pair is listed no earlier than the pair it stepped from, and the trail is finite.
    for pair in result.pairs.values():
        if pair.parent is not None:
            assert pair.joined_bar >= result.pairs[pair.parent].joined_bar
            assert pair.position == result.pairs[pair.parent].position + 1


def test_a_pair_under_one_daily_range_tall_is_listed_but_never_a_box_and_each_pair_has_its_own_unit():
    from engine_alpha.two_eyes import walk

    ranges = _ranges(40)
    ranges[11] = 2.5                                        # the root pair's second anchor day
    ranges[-1] = 6.0                                        # the read day is wide; no pair measures in it
    result = walk.elect(_RISE_WITH_A_TINY_BOUNCE, _TINY_FAR, ranges)
    tiny = result.pairs[(7, 6)]
    assert (tiny.R, tiny.S) == (71.5, 70.0) and tiny.birth_bar is None
    assert tiny.unfit == "under one daily range tall"
    root = result.pairs[(5, 6)]
    assert root.unit == 2.5 and root.birth_bar == 23
    assert _feet(result.winner) == (5, 6) and result.winner.unit == 2.5
    assert all(p.unit != 6.0 for p in result.pairs.values())


def test_a_pair_with_a_swing_beyond_a_line_between_its_anchors_is_not_wrapped_and_never_a_box():
    from engine_alpha.two_eyes import walk, method_numbers as M

    turns = list(_RISE_THEN_BOX)
    pair = walk.measure(turns, _ranges(46), 5, 12, joined=21, position=2, end_kind="BC", parent=(5, 10),
                        reason="test", read_bar=45)
    # 80 / 67 spans the 70 and 71 lows, both inside its area — wrapped. 80 / 71 spans the 70 low: inside too.
    assert pair.unfit is None
    # A pair whose span holds a low beyond its support's area is not wrapped: 80 / 74 (the first reaction low)
    # over the 70 low.
    assert walk.measure(turns, _ranges(46), 5, 8, joined=17, position=0, end_kind="BC", parent=None,
                        reason="test", read_bar=45).unfit is None
    loose = walk.measure(turns, _ranges(46), 5, 6, joined=17, position=0, end_kind="BC", parent=None,
                         reason="test", read_bar=45)
    assert loose.unfit is None                                  # nothing between adjacent anchors
    spanning = walk.measure(turns, _ranges(46), 9, 6, joined=17, position=0, end_kind="BC", parent=None,
                            reason="test", read_bar=45)         # 78 (bar 13) / 74 (bar 9): the 70 low in between
    assert spanning.unfit == "a swing beyond a line between its anchors"
    assert M.LINE_WORD_AREA_ATR == 0.5


def test_the_first_respected_pair_is_the_box_and_a_newer_trend_end_takes_over_only_after_leaving_it():
    """"were looking for the first instance that a consolidation is respected!": a trend end's box is the first
    of its pairs born; a pair born later inside or overlapping it — inner, or wider after a swing through a
    line — never replaces it. A newer trend end takes over only when its climax left the shown box's lines
    and one of its pairs is a box; one whose climax lies inside the box is the box's own leg."""
    from engine_alpha.two_eyes import walk

    def pair(feet, birth, parent, ran_through, R, S, end=8):
        return walk.Pair(r_index=feet[0], s_index=feet[1], R=R, S=S, opening_bar=8, second_bar=11, unit=2.0,
                         joined_bar=17, position=0 if parent is None else 1, end_kind="BC", parent=parent,
                         reason="", r_answer=1, s_answer=2, r_known=birth, s_known=birth, fifteenth=22,
                         birth_bar=birth, unfit=None, ran_through=ran_through, end_climax_bar=end)

    def end(climax_bar, climax_price):
        return {"kind": "BC", "climax_bar": climax_bar, "climax_price": climax_price, "end_bar": climax_bar + 3,
                "known_bar": climax_bar + 4}

    ends = (end(8, 80.0), end(30, 96.0), end(40, 78.5), end(50, 62.0))
    root = pair((5, 8), 23, None, False, 80.0, 70.0)
    wider = pair((5, 12), 30, (5, 8), True, 80.0, 67.0)             # support run through, rested at 67: an event
    inner = pair((7, 8), 24, (5, 8), False, 77.0, 70.0)             # a short miss: an inner pair
    assert walk.box_of([root, wider, inner]) is root
    assert walk.winner([root, inner], ends) is root
    assert walk.winner([root, wider, inner], ends) is root
    above = pair((30, 31), 50, None, False, 95.0, 81.0, end=30)    # a trend that left the box over the top
    leg = pair((40, 43), 50, None, False, 78.0, 71.0, end=40)      # a run end inside the box: its own leg
    below = pair((50, 53), 60, None, False, 61.0, 55.0, end=50)    # a decline that left the box under it
    assert walk.winner([root, wider, above], ends) is above
    assert walk.winner([root, wider, leg], ends) is root
    assert walk.winner([root, below], ends) is below
    assert walk.winner([root, above, below], ends) is below         # in the order the boxes were born
    late = pair((2, 3), 70, None, False, 80.5, 69.5, end=0)        # an OLDER trend end whose box is born last
    ends_with_older = (end(0, 81.0),) + ends
    assert walk.winner([root, late], ends_with_older) is root      # never back to an older end's box
    assert walk.left_the_box(96.0, root) and walk.left_the_box(62.0, root) and not walk.left_the_box(78.5, root)
    assert walk.winner([], ends) is None


def test_the_edges_of_the_answering_the_birth_and_the_steps():
    from engine_alpha.two_eyes import walk

    turns = list(_RISE_THEN_BOX)
    ranges = _ranges(46)
    # A swing beyond the line is no answer: resistance is answered by the first later peak WITHIN its area.
    poked = [_turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 80),
             _turn(8, "valley", 70), _turn(10, "peak", 84), _turn(12, "valley", 71), _turn(14, "peak", 79.5),
             _turn(16, "valley", 70.5)]
    pair = walk.measure(poked, _ranges(20), 3, 4, joined=9, position=0, end_kind="BC", parent=None, reason="",
                        read_bar=19)
    assert pair.r_answer == 7 and pair.s_answer == 6
    # The fifteenth day binds when both lines are answered sooner; the listing day binds when it is later; and
    # a birth after the read day is not a birth yet.
    quick = walk.measure(poked, _ranges(20), 3, 4, joined=9, position=0, end_kind="BC", parent=None, reason="",
                         read_bar=19)
    assert (quick.r_known, quick.s_known, quick.fifteenth) == (15, 13, 20) and quick.birth_bar is None
    assert walk.measure(poked, _ranges(30), 3, 4, joined=9, position=0, end_kind="BC", parent=None, reason="",
                        read_bar=25).birth_bar == 20
    assert walk.measure(poked, _ranges(30), 3, 4, joined=24, position=0, end_kind="BC", parent=None, reason="",
                        read_bar=25).birth_bar == 24
    # A swing short of a line AFTER the line was answered moves no foot; the walk from one trend end goes no
    # further right than the next trend end's climax.
    result = walk.elect(turns, _RISE_FAR, ranges)
    late_box = result.pairs[(13, 14)]                       # 79.5 / 70.5: resistance answered by 78.8, then 78 short
    assert late_box.r_answer == 15 and late_box.r_step is None
    # The 66 low (bar 40) went beyond its support AFTER it was born (bar 36): the box's life, no step.
    assert late_box.birth_bar == 36 and late_box.s_step is None and (13, 16) not in result.pairs
    assert (5, 14) not in result.pairs and all(min(r, s) <= 12 or r >= 13 for r, s in result.pairs)


def test_the_election_is_by_the_day_the_pair_became_a_box_then_the_opening_then_the_walks_order_then_the_tighter():
    from engine_alpha.two_eyes import walk

    def pair(birth, opening, position, height):
        return walk.Pair(r_index=0, s_index=1, R=float(height), S=0.0, opening_bar=opening, second_bar=opening + 1,
                         unit=2.0, joined_bar=0, position=position, end_kind="BC", parent=None, reason="",
                         r_answer=2, s_answer=3, r_known=birth, s_known=birth, fifteenth=opening + 14,
                         birth_bar=birth, unfit=None)

    earlier_birth = pair(20, 10, 3, 9.0)
    assert walk.box_of([pair(21, 8, 0, 5.0), earlier_birth]) is earlier_birth
    earlier_opening = pair(20, 8, 2, 9.0)
    assert walk.box_of([pair(20, 10, 0, 5.0), earlier_opening]) is earlier_opening
    fewer_moves = pair(20, 10, 0, 9.0)                          # the walk's order comes before the tighter
    assert walk.box_of([pair(20, 10, 1, 5.0), fewer_moves]) is fewer_moves
    tighter = pair(20, 10, 1, 5.0)
    assert walk.box_of([pair(20, 10, 1, 9.0), tighter]) is tighter
    assert walk.box_of([pair(None, 10, 0, 9.0)]) is None


def test_a_shown_line_never_moves_read_day_by_day_with_no_memory():
    """From its birth on bar 23 the box 80 / 70 is shown unchanged. On bar 36 the reader hands over to the pair
    79.50 / 70.50 — the run that ended at 67, a decline that left the box under support and, at this scale,
    reads as a trend end, walked one foot from its own pair (79.50 / 67) to it, and it became a box on its
    fifteenth day — the one move the provisional stage-4 rule allows. That the 67 dip came straight back into
    the box (a spring, by his eye) is the come-back stage 4 proper (task 11) checks; until then this is the
    reader's known failure mode, pinned here."""
    from engine_alpha.two_eyes import walk

    ranges = _ranges(46)
    shown = []
    for day in range(0, 45):
        got = walk.elect(walk.known_by(_RISE_THEN_BOX, day), walk.known_by(_RISE_FAR, day), ranges,
                         read_bar=day).winner
        if got is None:
            assert not shown, f"the box vanished on bar {day}"
            continue
        if not shown or _feet(got) != shown[-1][0]:
            shown.append((_feet(got), day, got.end_climax_bar))
    assert shown == [((5, 8), 23, 8), ((13, 14), 36, 20)]


def test_the_record_carries_the_box_its_trail_and_the_state_and_keep_listing_adds_words_only():
    from engine_alpha.two_eyes import walk, record

    result = walk.elect(walk.known_by(_RISE_THEN_BOX, 34), walk.known_by(_RISE_FAR, 34), _ranges(46), read_bar=34)
    boxes, trail, state = walk.record(result)
    assert state == "lines, no LPS yet"
    box = boxes[0]
    assert (box.resistance.price, box.support.price) == (80.0, 70.0)
    assert (box.resistance.anchor_day, box.support.anchor_day) == (_day(8), _day(11))
    assert box.opened_day == _day(8) and box.daily_range == 2.0 and box.role == record.ROLE_PARENT
    assert box.end_day is None
    # The trail to the winner: the trend end, then the pair, in words a page can print.
    assert [s.stage for s in trail] == ["trend end", "box"]
    assert "80.00" in trail[1].saying and "70.00" in trail[1].saying
    # Keep listing: every pair the walk listed, added after the trail to the winner; nothing else changes.
    more_boxes, more_trail, more_state = walk.record(result, keep_listing=True)
    assert (more_boxes, more_state) == (boxes, state)
    assert more_trail[:len(trail)] == trail and len(more_trail) == len(trail) + len(result.pairs) - 1
    # No trend end at all: no lines.
    assert walk.record(walk.elect(_RISE_THEN_BOX[:6], [], _ranges(46))) == ((), (), record.NO_LINES)


def test_read_fills_the_record_from_the_walk():
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, walk, method_numbers as M
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    key, raw = next(iter(frames.items()))
    read = two_eyes.read(key, raw)
    assert read.failed is False
    prepared = frame_module.prepare(raw)
    line = line_module.build(prepared)
    ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
    result = walk.elect(line.committed, [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES) if t.committed], ranges,
                        days=tuple(d.date() for d in prepared.index), read_bar=len(prepared) - 1)
    boxes, trail, state = walk.record(result)
    assert (read.boxes, read.trail, read.state) == (boxes, trail, state)
    assert read.parent is not None and read.state == "lines, no LPS yet"


# --------------------------------------------------------------------------- #
# His 35 drawings and the 88 charts                                           #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def prepared_frames() -> dict:
    from engine_alpha.two_eyes import frame as frame_module
    from tools.regression import negative_corpus, shadow_diff
    from core.calibration.replay import load_sealed_fixture

    frames = {}
    for name, loader in (("marks", load_sealed_fixture), ("fleet", shadow_diff._load_fixture),
                         ("junk", negative_corpus._load_fixture)):
        got, _ = loader()
        assert got, f"the {name} fixture went empty"
        for key, raw in got.items():
            frames[f"{name}:{key}"] = frame_module.prepare(raw)
    assert len(frames) >= 80
    return frames


@pytest.fixture(scope="module")
def his_reads() -> list:
    """Each of his 35 drawings read on his last receding day, with his pair on the line."""
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, walk, method_numbers as M
    from tools.calibration.listing_gate import anchor_turns
    from tools.calibration.yardstick import his_last_lps_day
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    out = []
    for setup in load_corpus():
        raw = fixture_frame(frames, setup_key(setup), setup["ticker"])
        prepared = frame_module.prepare(raw.loc[:pd.Timestamp(setup["as_of"])])
        line = line_module.build(prepared)
        days = [d.date() for d in prepared.index]
        ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
        r_bar = days.index(dt.date.fromisoformat(setup["anchors"]["R"]))
        s_bar = days.index(dt.date.fromisoformat(setup["anchors"]["S"]))
        last = days.index(his_last_lps_day(setup))
        turns = list(line.turns)
        his = anchor_turns(turns, r_bar, s_bar, setup["rails_drawn"]["R"], setup["rails_drawn"]["S"],
                           float(ranges[max(r_bar, s_bar)]))
        far = line.far(M.FAR_VIEW_FLOOR_RANGES)
        result = walk.elect(walk.known_by(turns, last), walk.known_by(far, last), ranges, read_bar=last)
        out.append({"setup": setup, "key": setup_key(setup), "turns": turns, "far": far, "ranges": ranges,
                    "days": days, "first_bar": min(r_bar, s_bar), "last_bar": last, "his": his,
                    "result": result, "prepared": prepared})
    assert len(out) == 35
    return out


#: The plan's named charts among his 35: the engine's box on his last receding day is his pair, to the cent.
#: Those the walk reads right from the transition into his box but the reader's choice of trend end still
#: misses wait on stage 4 (task 11: the box's end and the hand-over); pinned as expected failures, strictly,
#: so the day one passes it is a red test and the pin moves.
_WAITS_ON_STAGE_4 = "waits on stage 4 (task 11): the reader's choice of the current trend end"
_NAMED = ("VIK", "ALB",
          pytest.param("SYRE", marks=pytest.mark.xfail(strict=True, reason="a leg inside his box poked past a line's area "
                                                                           "and its pair took over; the come-back is task 11's")),
          pytest.param("FOSL", marks=pytest.mark.xfail(strict=True, reason=_WAITS_ON_STAGE_4)),
          pytest.param("MSGS", marks=pytest.mark.xfail(strict=True, reason="his support is the climax bar's own low; "
                                                                           "the walk's roots leave it out (his sitting)")),
          pytest.param("ROIV", marks=pytest.mark.xfail(strict=True, reason="an inner pair is respected first; "
                                                                           "his resistance is the higher top (his sitting)")))


@pytest.mark.parametrize("ticker", _NAMED)
def test_the_named_charts_read_his_pair_to_the_cent(his_reads, ticker):
    row = next(r for r in his_reads if r["setup"]["ticker"] == ticker)
    rails, winner = row["setup"]["rails_drawn"], row["result"].winner
    assert winner is not None, f"{ticker}: no box on his last receding day"
    assert (round(winner.R, 2), round(winner.S, 2)) == (round(rails["R"], 2), round(rails["S"], 2)), \
        f"{ticker}: the engine's box is {winner.R:.2f} / {winner.S:.2f}, his {rails['R']:.2f} / {rails['S']:.2f}"


@pytest.mark.xfail(strict=True, reason="a junk chart the plan names; the plan's lines are not the walk's yet (task 11: "
                                       "a range price left long ago is no candidate)")
def test_bmrn_the_plans_named_junk_chart_reads_the_box_the_plan_names():
    """The plan names BMRN 57.76 / 53.89; BMRN is a junk-corpus chart (his "huge spread" refusal), so the box
    is read on the negative fixture's frame, on its last day."""
    from engine_alpha import two_eyes
    from tools.regression import negative_corpus

    frames, _ = negative_corpus._load_fixture()
    read = two_eyes.read("BMRN", frames["BMRN"])
    assert read.parent is not None, "BMRN: no box"
    got = (round(read.parent.resistance.price, 2), round(read.parent.support.price, 2))
    assert got == (57.76, 53.89), f"BMRN: the engine's box is {got[0]:.2f} / {got[1]:.2f}"


def test_every_line_of_every_box_sits_on_a_bars_own_extreme_on_his_35(his_reads):
    """His rule of Mon 14/09/2026, "we cannot start the anchor in the same direction the price is going",
    checked on the result the one way his own 35 drawings satisfy it: an anchor is a turn the price made,
    resistance a bar's own high and support a bar's own low, never a bar in the direction of travel. (The
    two other readings — the box opens against the trend's direction; the opening line is never run through
    before the box is born — his drawings refute: 13 and 4 of his 35, Sat 26/09/2026.)"""
    from engine_alpha.two_eyes import frame as frame_module

    for row in his_reads:
        box = row["result"].winner
        if box is None:
            continue
        highs = row["prepared"]["High"].to_numpy(dtype=float)
        lows = row["prepared"]["Low"].to_numpy(dtype=float)
        assert abs(highs[box.r_bar] - box.R) < 1e-9, f"{row['key']}: resistance is not its bar's high"
        assert abs(lows[box.s_bar] - box.S) < 1e-9, f"{row['key']}: support is not its bar's low"
        assert row["turns"][box.r_index].committed and row["turns"][box.s_index].committed


def test_a_shown_line_never_moves_on_his_35_but_by_a_hand_over_beyond_it(his_reads):
    """Read day by day with no memory, the shown box changes only to a box born LATER whose trend end's climax
    left the shown box's lines (a new level; the earlier box's end is stage 4); a trend end inside it never
    moves it, and the reader never goes back."""
    from engine_alpha.two_eyes import walk

    def on(row, day):
        return walk.elect(walk.known_by(row["turns"], day), walk.known_by(row["far"], day), row["ranges"],
                          read_bar=day).winner

    def climax_of(row, box):
        return next(e["climax_price"] for e in row["result"].ends
                    if e["climax_bar"] == box.end_climax_bar and e["kind"] == box.end_kind)

    for row in his_reads:
        shown, last_day = None, None
        for day in range(max(0, row["first_bar"] - 10), row["last_bar"] + 1, 3):
            got = on(row, day)
            if got is None:
                assert shown is None, f"{row['key']}: the box vanished on {row['days'][day]:%a %d/%m/%Y}"
                continue
            if shown is not None and _feet(got) != _feet(shown):
                # Every day between the two samples, link by link: never back, and only past a trend end whose
                # climax left the box shown the day before.
                for between in range(last_day + 1, day + 1):
                    now = on(row, between)
                    if _feet(now) == _feet(shown):
                        continue
                    when = f"{row['days'][between]:%a %d/%m/%Y}"
                    assert now.birth_bar > shown.birth_bar, f"{row['key']}: the shown line moved back on {when}"
                    assert walk.left_the_box(climax_of(row, now), shown), \
                        f"{row['key']}: the shown line moved on {when} to a trend end inside it"
                    shown = now
                assert _feet(shown) == _feet(got)
            shown, last_day = got, day


def test_keep_listing_is_pinned_identical_on_every_chart(prepared_frames):
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, walk, method_numbers as M

    for key, prepared in prepared_frames.items():
        line = line_module.build(prepared)
        ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
        result = walk.elect(line.committed, [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES) if t.committed], ranges)
        boxes, trail, state = walk.record(result)
        more_boxes, more_trail, more_state = walk.record(result, keep_listing=True)
        assert (more_boxes, more_state) == (boxes, state), key
        assert more_trail[:len(trail)] == trail, key
