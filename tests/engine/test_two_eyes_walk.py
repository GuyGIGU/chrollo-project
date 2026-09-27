"""Stages 2, 3 and 4 of the two-eyes reader (tasks 10 and 11): the end of the trend, the two-legs walk, answered
his way, the election, and the box's life — his picture first, then the rules on hand-built lines, then his 35
drawings.

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
  respected!" — "Lets go with 15 days";
* the box's life (Sat 12/09/2026, Sat 19/09/2026): "if the price continues to Rise/Fall with out recovering we can
  deduce that either that the consolidating structure we measured ended and the price began to trend"; "the child
  box inherit the parent as its cause + its tricky to define it with Close value we need to deduce it Swings as
  well"; and his two dead-space drawings (BMRN, OHI): a box the price left and never came back to is no candidate.
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

#: Stage 4's line: the same rise into the box 80 / 70 (born on bar 22), an upthrust to 83 that comes straight back
#: (bars 26 to 32), then the breakout: a run to 94 with every pullback holding above the old resistance's area,
#: and the new base 94 / 88 answered on both lines, a box on its fifteenth day (bar 56). The far view sees the
#: box's own legs too — the trend ends inside a box are real at this scale — so the fold, not the far view, has
#: to tell a leg from a hand-over.
_BOX_THEN_BREAKOUT = [
    _turn(0, "valley", 50), _turn(2, "peak", 60), _turn(4, "valley", 55), _turn(6, "peak", 70),
    _turn(7, "valley", 66), _turn(8, "peak", 80),                        # the climax
    _turn(11, "valley", 70),                                             # the reaction low
    _turn(13, "peak", 79),                                               # resistance answered
    _turn(16, "valley", 70.6),                                           # support answered; the reaction decided
    _turn(18, "peak", 78.5), _turn(20, "valley", 71), _turn(22, "peak", 79.2), _turn(24, "valley", 70.8),
    _turn(26, "peak", 83), _turn(28, "valley", 72),                      # an upthrust: beyond the area, back inside
    _turn(30, "peak", 79), _turn(32, "valley", 71.5),                    # the box's last turn inside before it left
    _turn(34, "peak", 84), _turn(36, "valley", 81.5), _turn(38, "peak", 90), _turn(40, "valley", 85),
    _turn(42, "peak", 94),                                               # the breakout run's climax
    _turn(44, "valley", 88),                                             # the new base's low
    _turn(46, "peak", 93), _turn(48, "valley", 88.5), _turn(50, "peak", 92), _turn(52, "valley", 89),
    _turn(54, "peak", 91.5, know=False),
]
_BREAKOUT_FAR_BARS = (0, 2, 4, 6, 7, 8, 11, 13, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48,
                      50, 52)
_BREAKOUT_FAR = _far(_BOX_THEN_BREAKOUT, _BREAKOUT_FAR_BARS)


def _with_turns(line: list, *replacements) -> list:
    """The same line with the turns on the given bars replaced (a turn per ``(bar, kind, price[, know])``)."""
    by_bar = {r[0]: _turn(*r) for r in replacements}
    return [by_bar.get(t.bar, t) for t in line if t.bar in by_bar or t.bar not in by_bar]


#: The breakout whose base is a box by his rules on bar 56 — but the swing of bar 52 crashed back into the old
#: box (78, under the old resistance's area) before that birth: the old box goes on.
_BREAKOUT_THAT_CAME_BACK = _with_turns(_BOX_THEN_BREAKOUT, (52, "valley", 78))

#: The same crash printed on bar 55 and committed only on bar 57, the day AFTER the new box was born on 56.
_BREAKOUT_COME_BACK_KNOWN_LATE = [t for t in _BOX_THEN_BREAKOUT if t.bar < 54] + [
    _turn(54, "peak", 91, know=55), _turn(55, "valley", 78, know=57), _turn(57, "peak", 90, know=False)]


def _mirror(turns: list) -> list:
    """The same line upside down: a decline where the original rose, every peak a valley at 160 minus the price."""
    return [Turn(bar=t.bar, day=t.day, kind=("peak" if t.kind == "valley" else "valley"), price=160.0 - t.price,
                 knowable_bar=t.knowable_bar, knowable_day=t.knowable_day, size_ranges=t.size_ranges) for t in turns]


def _feet(pair) -> tuple:
    return (pair.r_index, pair.s_index)


def _shown_day_by_day(line: list, far: list, ranges, last_day: int) -> list:
    """Every change of the shown box, read day by day with no memory: ``(feet, the day, the trend end's climax
    bar)`` — and a box that vanishes is a failure."""
    from engine_alpha.two_eyes import walk

    shown = []
    for day in range(0, last_day + 1):
        got = walk.elect(walk.known_by(line, day), walk.known_by(far, day), ranges, read_bar=day).winner
        if got is None:
            assert not shown, f"the box vanished on bar {day}"
            continue
        if not shown or _feet(got) != shown[-1][0]:
            shown.append((_feet(got), day, got.end_climax_bar))
    return shown


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


def test_the_first_respected_pair_is_the_box_and_a_pair_born_later_inside_or_overlapping_it_never_replaces_it():
    """"were looking for the first instance that a consolidation is respected!": a trend end's box is the first
    of its pairs born; a pair born later inside or overlapping it — inner, or wider after a swing through a
    line — never replaces it."""
    from engine_alpha.two_eyes import walk

    def pair(feet, birth, parent, ran_through, R, S):
        return walk.Pair(r_index=feet[0], s_index=feet[1], R=R, S=S, opening_bar=8, second_bar=11, unit=2.0,
                         joined_bar=17, position=0 if parent is None else 1, end_kind="BC", parent=parent,
                         reason="", r_answer=1, s_answer=2, r_known=birth, s_known=birth, fifteenth=22,
                         birth_bar=birth, unfit=None, ran_through=ran_through, end_climax_bar=8)

    root = pair((5, 8), 23, None, False, 80.0, 70.0)
    wider = pair((5, 12), 30, (5, 8), True, 80.0, 67.0)             # support run through, rested at 67: an event
    inner = pair((7, 8), 24, (5, 8), False, 77.0, 70.0)             # a short miss: an inner pair
    assert walk.box_of([root, wider, inner]) is root
    assert walk.box_of([wider, inner]) is inner
    assert walk.box_of([]) is None


# --------------------------------------------------------------------------- #
# Stage 4: the box's life — the hand-over to a new box, and never back        #
# --------------------------------------------------------------------------- #
def _pair(feet, birth, R, S, climax_bar, kind="BC"):
    from engine_alpha.two_eyes import walk

    return walk.Pair(r_index=feet[0], s_index=feet[1], R=R, S=S, opening_bar=climax_bar + 2,
                     second_bar=climax_bar + 4, unit=2.0, joined_bar=climax_bar + 6, position=0, end_kind=kind,
                     parent=None, reason="", r_answer=1, s_answer=2, r_known=birth, s_known=birth,
                     fifteenth=climax_bar + 16, birth_bar=birth, unfit=None, end_climax_bar=climax_bar)


def _end(climax_bar, climax_price, kind="BC"):
    return {"kind": kind, "climax_bar": climax_bar, "climax_price": climax_price, "end_bar": climax_bar + 3,
            "known_bar": climax_bar + 4}


def test_a_later_box_takes_over_only_beyond_the_shown_box_from_a_newer_trend_end_once_the_price_left_and_stayed_out():
    """Stage 4's one rule, on hand-made pairs and turns. His point 26 places the child: "the first swing whose
    valley holds in or above the parent's R area is the child's root candidate", and the mirror under support;
    his Q6 ends the box: "if the price continues to Rise/Fall with out recovering ... the consolidating
    structure we measured ended". So a later box takes over the shown one only when its trend end is newer,
    it sits beyond the shown box (its support in or above the shown resistance's area, or its resistance in or
    below the shown support's area), and the price, having left the shown box on that side, did not come back
    into it before the new box was born — a valley back under the resistance's area, a peak back over the
    support's. Judged on the swings known by the new box's birth, so a line once shown never moves back."""
    from engine_alpha.two_eyes import walk

    shown = _pair((5, 8), 23, 80.0, 70.0, 8)                          # the box 80 / 70; the area is one point
    # Where a later box sits against the shown one.
    assert walk.side_of(_pair((30, 31), 50, 95.0, 81.0, 30), shown) == "above"
    assert walk.side_of(_pair((30, 31), 50, 95.0, 79.0, 30), shown) == "above"      # 79 is still in R's area
    assert walk.side_of(_pair((30, 31), 50, 95.0, 78.9, 30), shown) is None         # dips under it: a mini, or a leg
    assert walk.side_of(_pair((30, 31), 50, 71.0, 60.0, 30), shown) == "below"      # 71 is still in S's area
    assert walk.side_of(_pair((30, 31), 50, 72.5, 62.0, 30), shown) is None         # rises over it: overlapping
    assert walk.side_of(_pair((30, 31), 50, 78.0, 71.0, 30), shown) is None         # inside
    assert walk.side_of(_pair((30, 31), 50, 80.5, 67.0, 30), shown) is None         # wider, overlapping
    # The price leaves above on bar 30 and stays out: the box above takes over on its birth.
    up_and_out = [_turn(28, "valley", 74), _turn(30, "peak", 96), _turn(33, "valley", 82), _turn(36, "peak", 95),
                  _turn(40, "valley", 83)]
    above = _pair((30, 31), 50, 95.0, 82.0, 30)
    assert walk.takes_over(above, _end(30, 96.0), shown, _end(8, 80.0), up_and_out)
    # An OLDER trend end's box, however clean and however far beyond, never takes over.
    assert not walk.takes_over(above, _end(2, 96.0), shown, _end(8, 80.0), up_and_out)
    # A pair inside or overlapping the shown box never takes over, however clean the run.
    assert not walk.takes_over(_pair((30, 31), 50, 95.0, 78.9, 30), _end(30, 96.0), shown, _end(8, 80.0), up_and_out)
    # The come-back: a valley back under the resistance's area before the birth keeps the shown box.
    came_back = up_and_out + [_turn(44, "valley", 78.5, know=45)]
    assert not walk.takes_over(above, _end(30, 96.0), shown, _end(8, 80.0), came_back)
    assert walk.came_back(came_back, shown, "above", 30, 50).bar == 44
    assert walk.came_back(up_and_out, shown, "above", 30, 50) is None
    # The same come-back committed only after the birth does not count: the shown line has moved on.
    late = up_and_out + [_turn(44, "valley", 78.5, know=51)]
    assert walk.takes_over(above, _end(30, 96.0), shown, _end(8, 80.0), late)
    # The price never left the box on that side: nothing to hand over to.
    assert walk.departure(up_and_out, shown, "above", 30, 50) == 30
    stayed_in = [_turn(28, "valley", 79.5), _turn(33, "peak", 80.5), _turn(36, "valley", 79.2)]
    assert walk.departure(stayed_in, shown, "above", 30, 50) is None
    assert not walk.takes_over(above, _end(30, 96.0), shown, _end(8, 80.0), stayed_in)
    # The climax itself is the departure when it is the one swing beyond the box.
    only_climax_out = [_turn(28, "valley", 74), _turn(30, "peak", 96), _turn(33, "valley", 80.8),
                       _turn(36, "peak", 80.9), _turn(40, "valley", 80.5)]
    assert walk.departure(only_climax_out, shown, "above", 30, 50) == 30
    assert walk.takes_over(above, _end(30, 96.0), shown, _end(8, 80.0), only_climax_out)
    # The come-back is looked for from the day the price LEFT on the new box's side, not from the climax: a
    # decline that ended inside the box, whose reaction then ran up through it and based above.
    through = [_turn(26, "valley", 60), _turn(27, "peak", 75), _turn(28, "valley", 72), _turn(30, "peak", 96),
               _turn(33, "valley", 82), _turn(36, "peak", 95), _turn(40, "valley", 83)]
    assert walk.takes_over(above, _end(26, 60.0, "SC"), shown, _end(8, 80.0), through)
    # The mirror: a decline below.
    down_and_out = [_turn(28, "peak", 76), _turn(30, "valley", 60), _turn(33, "peak", 68), _turn(36, "valley", 61),
                    _turn(40, "peak", 67)]
    below = _pair((31, 30), 50, 68.0, 61.0, 30, kind="SC")
    assert walk.takes_over(below, _end(30, 60.0, "SC"), shown, _end(8, 80.0), down_and_out)
    assert not walk.takes_over(below, _end(30, 60.0, "SC"), shown, _end(8, 80.0),
                               down_and_out + [_turn(44, "peak", 71.5, know=45)])
    # The fold: the boxes in birth order, the first stands, each later one taken over by the rule; the box that
    # was handed over keeps its last turn inside its lines before the price left, and the side it left on.
    lives = walk.lives([shown, above], (_end(8, 80.0), _end(30, 96.0)), up_and_out)
    assert [life.pair.feet for life in lives] == [(5, 8), (30, 31)]
    assert lives[0].ended.bar == 28 and lives[0].left == "above"
    assert lives[1].ended is None and lives[1].left is None
    # The box ended on its last turn INSIDE its lines before the price left — not on the last turn of any kind.
    dipped_first = [_turn(26, "valley", 72), _turn(28, "valley", 60), _turn(30, "peak", 96), _turn(33, "valley", 82),
                    _turn(40, "valley", 83)]
    assert walk.lives([shown, above], (_end(8, 80.0), _end(30, 96.0)), dipped_first)[0].ended.bar == 26
    assert walk.winner([shown, above], (_end(8, 80.0), _end(30, 96.0)), up_and_out) is above
    assert walk.winner([shown, above], (_end(8, 80.0), _end(30, 96.0)), came_back) is shown
    assert walk.lives([], (), ()) == () and walk.winner([], (), ()) is None


def test_a_box_ends_only_into_a_new_box_beyond_it_once_the_price_left_and_did_not_come_back():
    """On the hand-built line: the box 80 / 70 from bar 22; the upthrust to 83 that came back is the box's own
    event (its pair is inside the box); the breakout to 94 with every pullback holding over the old
    resistance's area hands over to the base 94 / 88 on bar 56, the day that base is a box by his rules. The
    record keeps the earlier box, ended at its last turn inside its lines before the price left."""
    from engine_alpha.two_eyes import walk, record

    ranges = _ranges(60)
    assert _shown_day_by_day(_BOX_THEN_BREAKOUT, _BREAKOUT_FAR, ranges, 58) == [((5, 6), 22, 8), ((21, 22), 56, 42)]
    result = walk.elect(_BOX_THEN_BREAKOUT, [t for t in _BREAKOUT_FAR if t.committed], ranges,
                        days=tuple(_day(i) for i in range(60)), read_bar=58)
    first, second = result.lives
    assert first.pair.feet == (5, 6) and first.left == "above" and first.ended.bar == 32
    assert second.pair.feet == (21, 22) and second.ended is None and second.left is None
    assert result.winner is second.pair
    boxes, trail, state = walk.record(result)
    earlier, parent = boxes
    assert earlier.role == record.ROLE_EARLIER
    assert (earlier.resistance.price, earlier.support.price) == (80.0, 70.0)
    assert earlier.opened_day == _day(8) and earlier.end_day == _day(32) and earlier.daily_range == 2.0
    assert parent.role == record.ROLE_PARENT and (parent.resistance.price, parent.support.price) == (94.0, 88.0)
    assert parent.opened_day == _day(42) and parent.end_day is None
    assert trail[0].stage == "hand-over"
    assert "80.00" in trail[0].saying and "94.00" in trail[0].saying and "above" in trail[0].saying
    assert f"{_day(32):%a %d/%m/%Y}" in trail[0].saying and f"{_day(56):%a %d/%m/%Y}" in trail[0].saying
    assert [s.stage for s in trail[1:]] == ["trend end", "box"]
    assert state == "lines, no LPS yet"
    # Keep listing adds words only, here too.
    more_boxes, more_trail, more_state = walk.record(result, keep_listing=True)
    assert (more_boxes, more_state) == (boxes, state) and more_trail[:len(trail)] == trail


def test_the_mirror_a_decline_out_of_the_box_hands_over_to_a_new_box_below():
    from engine_alpha.two_eyes import walk

    line, far = _mirror(_BOX_THEN_BREAKOUT), _mirror(_BREAKOUT_FAR)
    ranges = _ranges(60)
    assert _shown_day_by_day(line, far, ranges, 58) == [((6, 5), 22, 8), ((22, 21), 56, 42)]
    result = walk.elect(line, [t for t in far if t.committed], ranges, read_bar=58)
    assert result.lives[0].left == "below" and result.lives[0].ended.bar == 32
    earlier, parent = walk.record(result)[0]
    assert (earlier.resistance.price, earlier.support.price) == (90.0, 80.0) and earlier.end_day == _day(32)
    assert (parent.resistance.price, parent.support.price) == (72.0, 66.0) and parent.end_day is None


def test_a_swing_back_into_the_box_before_the_new_box_is_born_keeps_the_box():
    """The base 94 / 88 is a box by his rules on bar 56 all the same — but the swing of bar 52 crashed to 78,
    back under the old resistance's area, before that day: the old box goes on, the new one is its own event."""
    from engine_alpha.two_eyes import walk

    line, far = _BREAKOUT_THAT_CAME_BACK, _far(_BREAKOUT_THAT_CAME_BACK, _BREAKOUT_FAR_BARS)
    ranges = _ranges(60)
    assert _shown_day_by_day(line, far, ranges, 58) == [((5, 6), 22, 8)]
    result = walk.elect(line, [t for t in far if t.committed], ranges, read_bar=58)
    assert result.pairs[(21, 22)].birth_bar == 56
    assert walk.came_back(line, result.winner, "above", 42, 56).bar == 52
    assert len(result.lives) == 1 and result.lives[0].ended is None and result.lives[0].left is None
    assert len(walk.record(result)[0]) == 1


def test_a_come_back_known_only_after_the_new_box_was_born_never_moves_the_shown_line_back():
    """The crash of bar 55 is committed on bar 57, the day after the base 94 / 88 became the box. A reader with
    no memory, read on 57, must still show 94 / 88: the come-back is judged on the swings known by the birth."""
    from engine_alpha.two_eyes import walk

    line = _BREAKOUT_COME_BACK_KNOWN_LATE
    far = _far(line, _BREAKOUT_FAR_BARS + (54, 55))
    ranges = _ranges(62)
    assert _shown_day_by_day(line, far, ranges, 60) == [((5, 6), 22, 8), ((21, 22), 56, 42)]
    on_57 = walk.elect(walk.known_by(line, 57), walk.known_by(far, 57), ranges, read_bar=57)
    assert on_57.winner.feet == (21, 22)
    old = on_57.lives[0].pair
    assert walk.came_back(walk.known_by(line, 57), old, "above", 42, 57).bar == 55      # known by 57: yes
    assert walk.came_back(walk.known_by(line, 57), old, "above", 42, 56) is None         # known by the birth: no


def test_a_later_box_is_placed_against_the_shown_boxes_own_area():
    """Stage 4's area is the SHOWN box's: half of the daily range IT was measured in. A later, tighter box whose
    support holds inside that area sits above the box, though it is further from the line than the tighter
    box's own area would reach; a later, wider box reaches no further than the shown box's area either."""
    from dataclasses import replace
    from engine_alpha.two_eyes import walk

    shown = _pair((5, 8), 23, 80.0, 70.0, 8)                          # measured in two points: the area is one

    def later(R, S, unit):
        return replace(_pair((30, 31), 50, R, S, 30), unit=unit)

    assert walk.side_of(later(95.0, 79.2, 0.5), shown) == "above"     # its own area would be a quarter point
    assert walk.side_of(later(70.8, 60.0, 0.5), shown) == "below"
    assert walk.side_of(later(95.0, 78.9, 0.5), shown) is None
    assert walk.side_of(later(95.0, 78.5, 6.0), shown) is None        # its own area would be three points
    assert walk.side_of(later(71.5, 60.0, 6.0), shown) is None


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
    """From its birth on bar 23 the box 80 / 70 is shown unchanged to the end. The dip to 67 on bar 20 reads as a
    trend end at this scale, and the pair its walk reached (79.50 / 70.50) became a box on bar 36 — but that
    pair lies inside the shown box, and the dip came straight back (a spring, by his eye): the box's own event,
    never a hand-over. Task 10 pinned the take-over on bar 36 as the reader's known failure mode; stage 4
    removes it."""
    from engine_alpha.two_eyes import walk

    assert _shown_day_by_day(_RISE_THEN_BOX, _RISE_FAR, _ranges(46), 44) == [((5, 8), 23, 8)]


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
    """The read is the walk's record, then stage 6 on the box it shows: the LPS, its step after the walk's trail,
    and the state word (task 12a)."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, lps, walk, method_numbers as M
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    key, raw = next(iter(frames.items()))
    read = two_eyes.read(key, raw)
    assert read.failed is False
    prepared = frame_module.prepare(raw)
    line = line_module.build(prepared)
    ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
    days = tuple(d.date() for d in prepared.index)
    result = walk.elect(line.committed, [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES) if t.committed], ranges,
                        days=days, read_bar=len(prepared) - 1)
    boxes, trail, state = walk.record(result)
    assert state == "lines, no LPS yet"
    won = result.winner
    pullback = lps.read(prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float), ranges,
                        line.committed, R=won.R, S=won.S, box_unit=won.unit, born_bar=won.birth_bar)
    the_lps, said, word = lps.record(pullback, days, read_bar=len(prepared) - 1)
    assert (read.boxes, read.lps, read.trail, read.state) == (boxes, the_lps, trail + said, word)
    assert read.parent is not None and len(said) == 1 and word in (lps.FIRED, lps.CROSSED, lps.LINES_NO_LPS)


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
        # His buy day (every one of his 35 buys the trading day after his last receding day), the read on it,
        # and his own pair measured by the reader's rules on it.
        buy = min(days.index(dt.date.fromisoformat(str(setup["trigger"])[:10])) if setup.get("trigger") else last,
                  len(days) - 1)
        known_by_buy = walk.known_by(turns, buy)
        on_buy = walk.elect(known_by_buy, walk.known_by(far, buy), ranges, read_bar=buy)
        his_pair = None
        if his["R"] is not None and his["S"] is not None:
            joined = max(int(turns[his["R"]].knowable_bar), int(turns[his["S"]].knowable_bar))
            his_pair = walk.measure(known_by_buy, ranges, his["R"], his["S"], joined, 0, "BC", None, "his pair", buy)
        out.append({"setup": setup, "key": setup_key(setup), "turns": turns, "far": far, "ranges": ranges,
                    "days": days, "first_bar": min(r_bar, s_bar), "last_bar": last, "his": his,
                    "result": result, "prepared": prepared,
                    "buy_bar": buy, "on_buy": on_buy, "his_pair": his_pair})
    assert len(out) == 35
    return out


#: The plan's named charts among his 35, by drawing: the engine's box on his last receding day is his pair, to
#: the cent. Those the reader still misses are pinned as expected failures, strictly, each with its reason, so
#: the day one passes it is a red test and the pin moves. (Task 10 pinned SYRE as the reader's failure mode —
#: a spring's pair took over; stage 4 reads it.)
_NAMED = ("VIK:2026-06-11", "SYRE:2026-02-19", "EWTX:2026-03-31", "NGL:2026-04-20", "VLO:2026-07-08",
          pytest.param("ALB:2026-04-13", marks=pytest.mark.xfail(strict=True, reason=(
              "the same box re-anchored on the transition end's pair: the reader keeps 173.38 / 156.04, within half "
              "a range of his 173.00 / 157.27 (a shown line never moves)"))),
          pytest.param("FOSL:2026-02-18", marks=pytest.mark.xfail(strict=True, reason=(
              "his box is a pair inside the reader's earlier, wider box (4.13 / 3.34), both his anchors on one wide "
              "bar (his sitting)"))),
          pytest.param("MSGS:2026-05-22", marks=pytest.mark.xfail(strict=True, reason=(
              "his support is the climax bar's own low; the walk's roots leave it out (his sitting)"))),
          pytest.param("ROIV:2026-06-17", marks=pytest.mark.xfail(strict=True, reason=(
              "an inner pair is respected first; his resistance is the higher top (his sitting)"))))


@pytest.mark.parametrize("key", _NAMED)
def test_the_named_charts_read_his_pair_to_the_cent(his_reads, key):
    row = next(r for r in his_reads if r["key"] == key)
    rails, winner = row["setup"]["rails_drawn"], row["result"].winner
    assert winner is not None, f"{key}: no box on his last receding day"
    assert (round(winner.R, 2), round(winner.S, 2)) == (round(rails["R"], 2), round(rails["S"], 2)), \
        f"{key}: the engine's box is {winner.R:.2f} / {winner.S:.2f}, his {rails['R']:.2f} / {rails['S']:.2f}"


@pytest.mark.xfail(strict=True, reason="a junk chart the plan names with the lines 57.76 / 53.89; the reader's box on "
                                       "the frame's last day is within half a range of them, on the walk's own anchors")
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


def test_the_plans_openings_clause_is_refuted_by_his_own_drawings(his_reads):
    """The plan asked that "openings running with the price are 0 of 35", from his rule of Mon 14/09/2026, "we
    cannot start the anchor in the same direction the price is going". It is NOT met, and it is no rule of the
    reader: his own drawings do what the clause forbids. Three of the boxes the reader reads as HIS pair, to
    the cent, open with the trend — after a rise on the low, after a decline on the high — so a reader that
    refused such an opening would lose his own boxes (the core's blind check, Sun 27/09/2026)."""
    for key in ("AVT:2026-04-08", "JAZZ:2026-02-24", "NGL:2026-04-20"):
        row = next(r for r in his_reads if r["key"] == key)
        box, rails = row["result"].winner, row["setup"]["rails_drawn"]
        assert (round(box.R, 2), round(box.S, 2)) == (round(rails["R"], 2), round(rails["S"], 2)), key
        assert not box.opens_against_the_trend, f"{key}: his own box opens with the trend"
    with_the_trend = sorted(r["key"] for r in his_reads if not r["result"].winner.opens_against_the_trend)
    assert len(with_the_trend) == 9, with_the_trend


def test_every_line_of_every_box_sits_on_a_bars_own_extreme_on_his_35(his_reads):
    """The shape of the result, not a rule: an anchor is a turn the price made, resistance a bar's own high and
    support a bar's own low. It holds by construction (a foot is a turn of the line, and a peak's price is its
    bar's high), so no rule can be taken away to make it fail; it guards only against a line's price ever being
    taken from somewhere else. The plan's openings clause is the test above."""
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
    """Read day by day with no memory, the shown box changes only forward — to a box born LATER that takes it
    over by stage 4's rule (a newer trend end, a box beyond the shown one, the price left on that side and did
    not come back before the birth) — and the reader never goes back."""
    from engine_alpha.two_eyes import walk

    def on(row, day):
        return walk.elect(walk.known_by(row["turns"], day), walk.known_by(row["far"], day), row["ranges"],
                          read_bar=day).winner

    def end_of(row, box):
        return next(e for e in row["result"].ends
                    if e["climax_bar"] == box.end_climax_bar and e["kind"] == box.end_kind)

    for row in his_reads:
        shown, last_day = None, None
        for day in range(max(0, row["first_bar"] - 10), row["last_bar"] + 1, 3):
            got = on(row, day)
            if got is None:
                assert shown is None, f"{row['key']}: the box vanished on {row['days'][day]:%a %d/%m/%Y}"
                continue
            if shown is not None and _feet(got) != _feet(shown):
                # Every day between the two samples, link by link: never back, and only by a hand-over.
                for between in range(last_day + 1, day + 1):
                    now = on(row, between)
                    if _feet(now) == _feet(shown):
                        continue
                    when = f"{row['days'][between]:%a %d/%m/%Y}"
                    assert now.birth_bar > shown.birth_bar, f"{row['key']}: the shown line moved back on {when}"
                    assert walk.takes_over(now, end_of(row, now), shown, end_of(row, shown),
                                           walk.known_by(row["turns"], between)), \
                        f"{row['key']}: the shown line moved on {when} without a hand-over"
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


def test_none_of_his_35_boxes_ends_before_his_buy_day(his_reads):
    """The plan's stop for stage 4: his own box, measured by the reader's rules, is never taken over by any box
    born by his buy day. The first build ended his boxes from inside four times; task 10's provisional rule,
    measured on the same drawings, fifteen."""
    from engine_alpha.two_eyes import walk

    checked = 0
    for row in his_reads:
        his = row["his_pair"]
        if his is None:
            continue
        on_buy, known = row["on_buy"], walk.known_by(row["turns"], row["buy_bar"])
        by_end = {}
        for pair in on_buy.pairs.values():
            by_end.setdefault((pair.end_kind, pair.end_climax_bar), []).append(pair)
        his_end = {"climax_bar": row["first_bar"]}
        for end in on_buy.ends:
            box = walk.box_of(by_end.get((end["kind"], end["climax_bar"]), ()))
            if box is None or box.feet == his.feet:
                continue
            assert not walk.takes_over(box, end, his, his_end, known), \
                (f"{row['key']}: his box would end on {row['days'][box.birth_bar]:%a %d/%m/%Y}, taken over by "
                 f"{box.R:.2f} / {box.S:.2f}")
            checked += 1
    assert checked > 100, "too few boxes were tried against his; the guard would be thin"


def test_every_one_of_his_35_shows_lines_on_his_buy_day_st_nok_and_msgs_among_them(his_reads):
    """The plan names ST, NOK and MSGS — the three the first build had "handed over with no child box yet" on his
    buy day. Here every one of his 35 shows a box on his buy day: a box stays until a new one is born."""
    for row in his_reads:
        assert row["on_buy"].winner is not None, f"{row['key']}: no lines on his buy day"
    assert {r["setup"]["ticker"] for r in his_reads} >= {"ST", "NOK", "MSGS"}


def test_ewtx_and_ngl_read_as_box_breakout_new_box_with_the_earlier_box_kept(his_reads):
    """"EWTX Should Fire on my mark!" (Wed 09/09/2026): the plan's two "box, breakout, new box" drawings. On his
    last receding day the record holds his box as the parent, and the box the price broke out of below it as an
    earlier box, ended; the trail opens with the hand-over. On NGL the earlier box is his January drawing's
    level (10.29 / 9.38)."""
    from engine_alpha.two_eyes import walk, record

    for key, january in (("EWTX:2026-03-31", None), ("NGL:2026-04-20", (10.29, 9.38))):
        row = next(r for r in his_reads if r["key"] == key)
        boxes, trail, _ = walk.record(row["result"])
        parent = next(b for b in boxes if b.role == record.ROLE_PARENT)
        rails = row["setup"]["rails_drawn"]
        assert (round(parent.resistance.price, 2), round(parent.support.price, 2)) == \
            (round(rails["R"], 2), round(rails["S"], 2)), key
        earlier = [b for b in boxes if b.role == record.ROLE_EARLIER]
        assert earlier, f"{key}: no earlier box kept"
        assert all(b.end_day is not None and b.end_day <= row["days"][row["last_bar"]] for b in earlier), key
        assert any(b.resistance.price <= parent.support.price + 0.5 * parent.daily_range for b in earlier), \
            f"{key}: no earlier box below the parent"
        assert trail[0].stage == "hand-over", key
        if january is not None:
            assert any(abs(b.resistance.price - january[0]) <= b.daily_range
                       and abs(b.support.price - january[1]) <= b.daily_range for b in earlier), \
                f"{key}: his January box is not among the earlier boxes"


def test_a_range_price_left_long_ago_is_no_candidate_on_bmrn_and_ohi():
    """His dead-space drawings (Sat 19/09/2026): on BMRN the old engine's box (60.93 / 58.00) sat over eight
    months of price under it; on OHI (44.88 / 42.90) under four months of price above it. The hand-over follows
    the price: on the frame's last day the box shown is where the price trades, within a daily range of its
    lines, never the dead-space box, and the boxes the price left are in the record as earlier boxes, ended."""
    from engine_alpha import two_eyes
    from tools.regression import negative_corpus

    frames, _ = negative_corpus._load_fixture()
    for key, dead in (("BMRN", (60.93, 58.00)), ("OHI", (44.88, 42.90))):
        raw = frames[key]
        read = two_eyes.read(key, raw)
        box = read.parent
        assert box is not None, key
        high, low = float(raw["High"].iloc[-1]), float(raw["Low"].iloc[-1])
        assert low <= box.resistance.price + box.daily_range and high >= box.support.price - box.daily_range, \
            (f"{key}: the box shown ({box.resistance.price:.2f} / {box.support.price:.2f}) is not where the price "
             f"trades ({high:.2f} / {low:.2f})")
        assert (round(box.resistance.price, 2), round(box.support.price, 2)) != dead, f"{key}: dead space is shown"
        earlier = [b for b in read.boxes if b.role == two_eyes.ROLE_EARLIER]
        assert earlier and all(b.end_day is not None and b.end_day <= read.as_of for b in earlier), key


def test_the_read_equals_the_knowable_order_replay_at_every_hand_over_on_every_chart(prepared_frames):
    """A reader with no memory: the boxes the last day's read records as handed over are the boxes a reader
    watching every day would have shown. At each of the last two hand-overs on every chart, the day before the
    new box's birth shows the earlier box and the birth day shows the new one; every earlier box in the record
    ended before the box after it was born, and only the last box is the parent."""
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, walk, record, method_numbers as M

    hand_overs = 0
    for key, prepared in prepared_frames.items():
        line = line_module.build(prepared)
        far = [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES) if t.committed]
        ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
        result = walk.elect(line.committed, far, ranges, read_bar=len(prepared) - 1)
        boxes, _, _ = walk.record(result)
        assert [b.role for b in boxes[:-1]] == [record.ROLE_EARLIER] * (len(boxes) - 1), key
        assert all(b.end_day is not None for b in boxes[:-1]), key
        assert not boxes or (boxes[-1].role == record.ROLE_PARENT and boxes[-1].end_day is None), key
        for earlier, later in list(zip(result.lives, result.lives[1:]))[-2:]:
            birth = later.pair.birth_bar
            assert earlier.ended is not None and earlier.ended.bar < birth, key
            before = walk.elect(walk.known_by(line.committed, birth - 1), walk.known_by(far, birth - 1), ranges,
                                read_bar=birth - 1).winner
            after = walk.elect(walk.known_by(line.committed, birth), walk.known_by(far, birth), ranges,
                               read_bar=birth).winner
            assert before is not None and before.feet == earlier.pair.feet, \
                f"{key}: the day before the hand-over the reader showed {before and before.feet}, not {earlier.pair.feet}"
            assert after.feet == later.pair.feet, \
                f"{key}: on the hand-over's day the reader showed {after.feet}, not {later.pair.feet}"
            hand_overs += 1
    assert hand_overs >= 60, f"only {hand_overs} hand-overs were replayed; the guard would be thin"


# --------------------------------------------------------------------------- #
# Read as the scan reads: a new two-year window every night                   #
# --------------------------------------------------------------------------- #
def _as_the_scan_reads(raw, night) -> tuple:
    """One night as the scan reads it: the long frame cut at the night and prepared afresh, so the window's
    left edge is a day later every night. The walk's result and that window's own days."""
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, walk, method_numbers as M

    prepared = frame_module.prepare(raw.loc[:night])
    line = line_module.build(prepared)
    ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
    far = [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES) if t.committed]
    found = walk.elect(line.committed, far, ranges, read_bar=len(prepared) - 1)
    return found, [d.date() for d in prepared.index]


def _lines(pair, days) -> tuple:
    """A box by its two lines and their anchor days: the same box in whatever window it is read."""
    return (round(pair.R, 4), days[pair.r_bar], round(pair.S, 4), days[pair.s_bar])


#: Four of his drawings with hand-overs in their last 45 nights, and nights among them on which the record of
#: earlier boxes was told differently (the blind check's replay, Sun 27/09/2026).
_REPLAYED = ("EGBN:2026-01-15", "MSGS:2026-05-22", "YPF:2026-05-18", "MRK:2026-08-10")


def test_read_night_after_night_as_the_scan_reads_the_shown_box_moves_only_the_night_a_new_box_is_born():
    """The two proofs above read ONE prepared window and filter its turns by the day they were known. The scan
    cuts a new window every night. Read that way, night after night, the box shown changes only on the night
    the new box is born, and the box shown the night before is the one that night's read hands over."""
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    hand_overs = 0
    for key in _REPLAYED:
        raw = fixture_frame(frames, key, key.split(":")[0])
        before = None
        for night in raw.index[-45:]:
            found, days = _as_the_scan_reads(raw, night)
            when = f"{night:%a %d/%m/%Y}"
            assert found.winner is not None, f"{key}: no box on {when}"
            now = _lines(found.winner, days)
            if before is not None and now != before:
                assert days[found.winner.birth_bar] == night.date(), \
                    f"{key}: the shown box moved on {when}, a night no box was born"
                assert len(found.lives) >= 2 and _lines(found.lives[-2].pair, days) == before, \
                    f"{key}: on {when} the box shown the night before is not the box handed over"
                hand_overs += 1
            before = now
    assert hand_overs >= 4, f"only {hand_overs} hand-overs were replayed; the guard would be thin"


def _flg_on_two_nights() -> list:
    """FLG, the junk fixture, read on Mon 09/03/2026 and on Tue 10/03/2026: no box is born on either night. The
    first night's window still holds the trend end of Wed 06/03/2024 and its wide box 12.09 / 9.57; the second
    night's has lost it."""
    from tools.regression import negative_corpus

    frames, _ = negative_corpus._load_fixture()
    told = []
    for night in (pd.Timestamp("2026-03-09"), pd.Timestamp("2026-03-10")):
        found, days = _as_the_scan_reads(frames["FLG"], night)
        told.append([_lines(life.pair, days) for life in found.lives])
    return told


def test_flg_shows_the_same_box_the_night_after_its_window_lost_its_first_trend_end():
    monday, tuesday = _flg_on_two_nights()
    assert monday[-1] == tuesday[-1] and monday[-1][0] == 13.15 and monday[-1][2] == 12.57
    assert monday[0][:3:2] == (12.09, 9.57) and tuesday[0][:3:2] != (12.09, 9.57)


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN LIMIT, found by the core's blind check on Sun 27/09/2026. The reader has no memory: it folds the boxes "
    "from the left edge of its two-year window, and that edge moves a day a night. So the boxes it records as "
    "handed over are the ones TODAY'S window tells, and they change on nights with no hand-over (345 of 3,500 "
    "replayed nights on his 35; 393 of 4,850 on the junk). The box SHOWN moved on none of those nights but a "
    "birth night. The earlier boxes are the story's (task 12b): they are made independent of the window's edge "
    "before the story reads them, and that day this mark comes off deliberately."))
def test_the_boxes_recorded_as_handed_over_are_the_same_boxes_the_night_after():
    monday, tuesday = _flg_on_two_nights()
    assert monday[-4:-1] == tuesday[-4:-1], \
        f"the three boxes handed over last: {monday[-4:-1]} on Monday, {tuesday[-4:-1]} on Tuesday"
