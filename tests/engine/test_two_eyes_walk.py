"""Stages 2, 3 and 4 of the two-eyes reader: the end of the trend, the rule of the pair and the box's life — his
picture first, then each of his sentences on hand-built bars, then his own drawings (the population follows
what he draws) and the fixture charts.

The rule is his, settled at the core sitting. On Wed 30/09/2026 it was typed out to him in ten sentences; on Thu
01/10/2026 he answered each (both in the build run's request file and in the decisions record):

1.  a rail sits only on the end point of a swing — "correct";
2.  a box's two rails are the two ends of one counter move, after a swing up the top first — "correct";
3.  the two ends can be one wide bar's own high and low — "correct";
4.  the counter move is smaller than the move it comes off — "correct most Automatic rallies (AR) cover only part
    of the previous move if a counter move is bigger it contributes already to a new counter trend!";
5.  the first pair tried is the climax and its reaction; if the bars do not come back to both rails, one pair to
    the right; one rail may stay while the other moves — "correct but ... only if a swing connects between them,
    we cannot allow for dismemberd anchor paring";
6.  "come back" is a later bar's high within half a daily range of resistance, a later bar's low within half a
    daily range of support — "if by "Come back" to be counted as respect to the respective rail that bar is
    closest too then yes";
7.  the pair is a box on its fifteenth day, or later if the bars take longer — "Correct we have to account for
    the bases eventual recovery when scanning and detecting, its looking at the base structure as whole rather
    and seeing that it fits rather then rejecting it out right";
8.  a run past a rail never unmakes a pair by itself — "Regarding ALB it can be a little confusing that breach is
    not an upthrust in fact there is a later on 25/02/2026 its just that those pairs could be used to fit the
    box, even a later pair could work if that movement in 20/1 -> 27/1 and the crash afterwards could be treated
    as the place where the trend ends";
9.  once a box, it stays a box through dips under support and pokes over resistance that come back — "correct";
10. the box gives way to a newer pair only when the price left it and did not come back: the bars now hang on
    the newer rails and no longer come back to the old ones — "correct".

On the pictures of the rebuilt reader (Thu 01/10/2026) he redrew ROIV ("Sorry Roiv was wrong": 30.33 / 27.92) and
said of sentence 6: "Silc supposed to work due the much respect of the support" — bars resting on a rail respect
it — and "why would DRTS move away as it almost perfectly respect both boundaries" — a reaction low the base never
returns to is no respected rail.

His earlier words these still pin: respect is read on a bar's High and Low, "whenever they are slightly poking out
or not does not matter one bit" (Sat 26/09/2026); "were looking for the first instance that a consolidation is
respected!" (Sun 06/09/2026); "Lets go with 15 days" (Sat 12/09/2026); "We can't start the anchor from the
opposite direction of the trend if we are still inside that trend" (Mon 27/07/2026); and his ruling on the
reader's PBT box, "we only start to anchor from the end point of previous swings" (Mon 28/09/2026).
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


def _chart(points, tail: int = 3, spread: float = 0.2, unit: float = 2.0) -> dict:
    """Bars and a line from a hand-written zigzag ``[(bar, price), ...]``: each point is a swing's end, and the
    bars between two points walk straight from one to the other. A top's bar has its high on the price, a low's
    bar its low; every bar is 0.4 tall, and the daily range is two points, so a rail's area is one point."""
    kinds = []
    for i, (_, price) in enumerate(points):
        other = points[i + 1][1] if i + 1 < len(points) else points[i - 1][1]
        kinds.append("peak" if price > other else "valley")
    n = points[-1][0] + 1 + tail
    mid = np.interp(np.arange(n), [b for b, _ in points],
                    [p - spread if k == "peak" else p + spread for (_, p), k in zip(points, kinds)])
    high, low = mid + spread, mid - spread
    turns = [_turn(b, k, p) for (b, p), k in zip(points, kinds)]
    for t in turns:
        (high if t.kind == "peak" else low)[t.bar] = t.price
    return {"turns": turns, "high": high, "low": low, "ranges": np.full(n, unit), "n": n}


def _elect(chart: dict, far_bars=None, read_bar=None):
    """The walk on a hand-built chart as a reader standing on ``read_bar`` has it; the far view is the line's
    own turns on ``far_bars`` (every turn by default)."""
    from engine_alpha.two_eyes import walk

    turns = chart["turns"]
    far = [t for t in turns if far_bars is None or t.bar in far_bars]
    if read_bar is not None:
        turns, far = walk.known_by(turns, read_bar), walk.known_by(far, read_bar)
    return walk.elect(turns, far, chart["ranges"], chart["high"], chart["low"], read_bar=read_bar,
                      days=tuple(_day(i) for i in range(chart["n"])))


def _box(found) -> tuple:
    return None if found.winner is None else (found.winner.R, found.winner.S)


def _pair(found, R: float, S: float):
    return next(p for p in found.pairs.values() if (p.R, p.S) == (R, S))


def _shown_day_by_day(chart: dict, far_bars=None, last_day=None) -> list:
    """Every change of the shown box, read day by day with no memory: ``(R, S, the day)`` — and a box that
    vanishes is a failure."""
    shown = []
    for day in range(0, (chart["n"] - 1 if last_day is None else last_day) + 1):
        got = _box(_elect(chart, far_bars, read_bar=day))
        if got is None:
            assert not shown, f"the box vanished on bar {day}"
            continue
        if not shown or got != shown[-1][:2]:
            shown.append((*got, day))
    return shown


#: A decline that ended (the first trend end: nothing is listed before one), then a rise into a climax at bar 11
#: (80) and its reaction low at bar 14 (70).
_PREFIX = [(0, 58), (1, 52), (2, 56), (3, 50)]
_RISE = _PREFIX + [(5, 60), (6, 55), (8, 70), (9, 66), (11, 80), (14, 70)]

#: The rise, then the box: the bars come back to resistance on bar 17 and to support on bar 20.
_BOX = _RISE + [(17, 79.5), (20, 70.6), (23, 78.8), (26, 70.4), (29, 79.2), (32, 71), (35, 78.5)]

#: The rise, then a run to 86 on bar 16 — three daily ranges over the 80 / 70 pair, eleven days before it is a box
#: — the crash back to 70.5, and the base on the old two rails. His ALB.
_RUN_PAST_THE_RAIL = _RISE + [(16, 86), (19, 70.5), (22, 79.5), (25, 70.6), (28, 79), (31, 70.8), (34, 79.3),
                              (37, 71), (40, 78.6)]

#: The box, then the breakout: a run to 94 and a new base 94 / 88 whose bars never come back to the old rails.
_BOX_THEN_BREAKOUT = _BOX[:-1] + [(35, 94), (38, 88), (41, 93.5), (44, 88.4), (47, 93), (50, 88.8), (53, 92.6),
                                  (56, 89)]

#: The box, then the same run to 94 and its reaction to 88 — and the crash back into the box, to its support (bar
#: 43) and its resistance (bar 46), before the pair above is a box: a breakout that failed. Then the price goes
#: back up and hangs on the rails above.
_BREAKOUT_THAT_CAME_BACK = _BOX[:-1] + [(35, 94), (38, 88), (40, 92), (43, 70.8), (46, 79.4), (49, 93.5),
                                        (52, 88.4), (55, 93), (58, 88.6)]

#: The box, then a poke to 84 that comes back, a dip, a second poke: his upthrust, twice. The pair the poke makes
#: (84 / 72) lies across the box's resistance.
_BOX_WITH_POKES = _BOX[:-1] + [(35, 84), (38, 72), (41, 79), (44, 70.8), (47, 83.6), (50, 72.4), (53, 79.3),
                               (56, 71)]

#: A pause INSIDE a rise: 70 / 66 holds for ten days and is a box on bar 22; the rise goes on to 80 on bar 24,
#: reacts to 68.5 — back inside the pause box — and the base forms on 80 / 68.5. The far view does not turn on the
#: pause (its swings are too small for it): the rise ended at 80. His VLO.
_PAUSE_INSIDE_A_RISE = _PREFIX + [(5, 60), (6, 55), (8, 70), (10, 66), (12, 70.4), (14, 66.3), (16, 70.2),
                                  (18, 66.5), (24, 80), (27, 68.5), (30, 79.5), (33, 68.9), (36, 79), (39, 66.8),
                                  (42, 78.6), (45, 69)]
_PAUSE_FAR = {0, 1, 2, 3, 5, 6, 24, 27, 30, 33, 36, 39, 42}

#: A box "a swing later": the climax 80 and its reaction 70, then the box 77 / 72 on the next top and its low.
#: Then a spring to 68, under the reaction low, and back up into the box. The far view here turns only on the
#: climax, its reaction, the box's top and the spring: to it the spring ends a DECLINE that began on the climax,
#: before the box opened.
_SPRING_UNDER_A_LATER_BOX = _RISE + [(17, 77), (20, 72), (23, 76.6), (26, 72.4), (29, 76.8), (32, 72.2), (35, 68),
                                     (38, 76.4), (41, 72.6), (44, 76.6), (47, 72.3), (50, 76.2), (53, 72.5)]
_SPRING_FAR = {0, 1, 2, 3, 5, 6, 8, 9, 11, 14, 17, 35, 38, 41, 44}

#: The rise and its reaction low (80 / 70), then a base that for three weeks turns under 76, and only on bar 40
#: a rally back to the climax's level. The reaction low with the first bounce (76 / 70, opening on support on
#: bar 14) is a box on bar 28; the climax and its reaction (80 / 70, opening on bar 11) only on bar 40, the day
#: the bars came back to its resistance. His ROIV.
_OUTER_PAIR_RESPECTED_LATE = _RISE + [(17, 76), (20, 70.5), (23, 75.6), (26, 70.8), (29, 75.8), (32, 71), (35, 75.5),
                                      (37, 72), (40, 79.6), (43, 71.2), (46, 79.2), (49, 71)]

#: His GFR (Thu 16/10/2026): the climax 80 (bar 11) and its reaction low 70 (bar 14), a bounce to 76 and a SECOND
#: swing down to 65.6 (bar 20): "the AR ended where I marked it ... the entire wave going down is already 2 swings
#: and it's not part of the AR". The bars come back to the climax's level on bar 26, to 66's area on bar 29 (so
#: 80 / 65.6 is a box first) and only on bar 30 to the reaction low's area: the climax and its reaction, the pair
#: tried first, is a box on bar 30.
_REACTION_ANSWERED_AFTER_A_LOWER_SIBLING = _RISE + [(17, 76), (20, 65.6), (23, 74), (26, 79.5), (28, 66.2),
                                                    (31, 70.4), (34, 79.2), (37, 70.6), (40, 79), (43, 70.8)]

#: The box, then a dip: a fall to 62 and three weeks on a lower pair, 68 / 62, whose resistance rests on the old
#: support's area; on bar 49 it is a box and no bar has been back at the old rails: the reader follows the price
#: down. Then the price comes back: at the old support on bar 55, at the old resistance on bar 57. His ROIV.
_DIP_THAT_CAME_BACK = _BOX[:-2] + [(35, 62), (38, 68), (41, 62.4), (44, 67.6), (47, 62.6), (50, 67.8), (53, 62.8),
                                   (57, 79.4), (60, 70.6), (63, 79.2), (66, 70.8), (69, 79.0)]

#: The dip that came back, with a shelf on the way up: after the dip the price sits for three weeks on a pair
#: above the dip pair and inside the old box (76 / 72, a box on bar 70) — and on that very day the bars are back
#: at both rails of the old box (its support on bar 69, its resistance on bar 70).
_DIP_BACK_THE_DAY_A_PAIR_ABOVE_IS_A_BOX = _BOX[:-2] + [(35, 62), (38, 68), (41, 62.4), (44, 67.6), (47, 62.6),
                                                       (50, 67.8), (53, 62.8), (56, 76), (58, 72), (60, 75.8),
                                                       (62, 72.2), (64, 75.6), (66, 72.4), (68, 75.8), (69, 70.4),
                                                       (70, 79.6), (73, 70.8), (76, 79.2)]

#: His STGW (Fri 23/10/2026): the box 80 / 70 left downward to the dip pair 68 / 62 (a box on bar 49, as on the dip
#: chart) - then the price runs out of the dip pair THROUGH the pair above in one swing (84 on bar 56), rests just
#: under that pair's support (69.6 on bar 59, 1.6 over the dip pair's resistance) and turns inside it from bar 62.
#: The bars are back at both rails of the old pair by bar 59 (its resistance on bar 57, on the way down from the
#: run) while the dip pair's support (bar 53) is still in the fifteen-day window until bar 68.
_RUN_THROUGH_THE_PAIR_ABOVE = _BOX[:-2] + [(35, 62), (38, 68), (41, 62.4), (44, 67.6), (47, 62.6), (50, 67.8),
                                         (53, 62.8), (56, 84), (59, 69.6), (62, 79.6), (65, 70.4), (68, 79.4),
                                         (71, 70.6), (74, 79.2)]

#: The box, a run to 94 and its reaction to 88, the bars back at both of those rails by bar 42 — and the price
#: falls back into the box (its support on bar 45, its resistance on bar 48) and then sinks under it, turning
#: between 66 and 68.6. From bar 63 no bar of fifteen days has been back at the box's resistance; the pair above
#: is a box by the rule since bar 49, and no bar has been near it since bar 42. His MTLS.
_RUN_ABOVE_THEN_UNDER_THE_BOX = _BOX[:-1] + [(35, 94), (38, 88), (41, 93.5), (45, 70.6), (48, 79.6), (51, 66),
                                             (54, 68.6), (57, 65.6), (60, 68.4), (63, 65.8), (66, 68.2), (69, 66)]

#: The box, the breakout and the new base above it (94 / 88, a box on bar 49) — then a fall back into the old box,
#: at its resistance on bar 56 and its support on bar 58, and straight back up to the rails above. His ST: the
#: spring under his box is at both rails of the box under it.
_SPRING_INTO_THE_BOX_UNDER_IT = _BOX[:-1] + [(35, 94), (38, 88), (41, 93.5), (44, 88.4), (47, 93), (50, 88.8),
                                             (53, 92.6), (58, 70.6), (62, 93.2), (65, 88.4), (68, 93), (71, 88.6)]

#: His EXPD (drawn Sat 17/10/2026): the box 80 / 70 is a box on bar 25. On bar 41 the price pokes to 82.2, a range
#: over the resistance, and is back at the support on bar 44; the base goes on inside the box, and a push back to
#: the poke's level on bar 53 (his SOS) makes 82.2 / 70.6 a box on bar 56. The far view folds the box's own swings
#: away: to it ONE rise runs from the prefix's low to 82.2, and the box's top sits inside that rise.
_POKE_OVER_A_BORN_BOX = _BOX + [(38, 71), (41, 82.2), (44, 70.6), (47, 79.4), (50, 70.8), (53, 81.6), (56, 71),
                                (59, 79), (62, 70.9), (65, 79.2)]
_POKE_FAR = {0, 1, 2, 3, 5, 6, 41, 44, 47, 50, 53, 56, 59, 62, 65}

#: His HCA (fixed on the lens Fri 16/10/2026, read Sat 24/10/2026): the ALB chart with a history. Before the decline
#: into the rise the bars turned at 80 and 70 (tops on bars 2 and 6, lows on bars 4 and 8), so the pair 80 / 70 that
#: opens on the rise's top (bar 23) and its reaction (bar 26) is not new. The run to 86 on bar 28, two days after its
#: second anchor and nine before it is a box, comes back into it, and the base goes on on its rails.
_RUN_PAST_A_PAIR_THE_BARS_KNEW = [(0, 72), (2, 79.8), (4, 70.2), (6, 80.1), (8, 70.1), (10, 76)] + \
    [(bar + 12, price) for bar, price in _RUN_PAST_THE_RAIL]

#: His DSGX (drawn Sat 18/10/2026): the rise pauses at 71 / 66 on bars 8 and 9 (a pair under the box, its top a
#: range under the box's support), then the box 80 / 70, a box on bar 25. On bar 38 a spring dips to 66, under the
#: support, and touches that lower pair's own support; the price recovers in two days and from then consolidates
#: HIGHER: its highs keep coming back to the box's resistance, its lows hold 76, and one dip to 71.9 on bar 44 rests
#: on the lower pair's top without reaching the box's support area. The step 79.3 / 76.2 is the base's own extension
#: (his mini), never a new base.
_RISE_WITH_A_PAUSE = _PREFIX + [(5, 60), (6, 55), (8, 71), (9, 66), (11, 80), (14, 70)]
_SPRING_THEN_A_STEP_UP = _RISE_WITH_A_PAUSE + _BOX[len(_RISE):] + [
    (38, 66), (40, 79.5), (44, 71.9), (47, 79.3), (50, 76.2), (53, 79.4), (56, 76.1), (59, 79.6), (62, 76.3),
    (65, 79.2), (68, 76.4), (71, 79.5)]


# --------------------------------------------------------------------------- #
# His picture: respect is the nearness of a bar's high or low to a rail       #
# --------------------------------------------------------------------------- #
def test_his_picture_each_end_of_a_bar_counts_for_the_rail_it_is_closest_to():
    """The bars he marked on Sat 26/09/2026, on a box 100 / 90 with a two-point daily range (the area is one), and
    his answer to sentence 6: a bar's come-back counts "as respect to the respective rail that bar is closest
    too"."""
    from engine_alpha.two_eyes.walk import bar_respects, rail_of

    R, S, area = 100.0, 90.0, 1.0
    # Red: the anchor bar, its high on resistance and its low on support — it respects both.
    assert bar_respects(100.0, 90.0, R, S, area) == {"R", "S"}
    # Blue: small bars dwelling low in the box, high and low both close to support, the low poking under —
    # "whenever they are slightly poking out or not does not matter one bit": resting on support.
    for high, low in ((90.9, 89.4), (90.8, 90.1), (90.3, 89.7)):
        assert bar_respects(high, low, R, S, area) == {"S"}
    # Green: bars whose high is close to resistance, from under it or poking over it.
    for high, low in ((99.6, 96.0), (100.7, 97.0)):
        assert bar_respects(high, low, R, S, area) == {"R"}
    # "even the single bar between them that his L value is close to the resistance counts as respect": a bar
    # sitting above resistance, resting on it from above.
    assert bar_respects(103.0, 100.6, R, S, area) == {"R"}
    # A bar in the middle of the box respects neither rail; a bar well under support has left the box.
    assert bar_respects(96.0, 94.0, R, S, area) == set()
    assert bar_respects(88.5, 86.0, R, S, area) == set()
    # Either side is the same distance: poking out is not different from stopping short.
    assert rail_of(89.4, R, S, area) == rail_of(90.6, R, S, area) == "S"
    assert rail_of(88.9, R, S, area) is rail_of(91.1, R, S, area) is None
    # The rail a bar's end is CLOSEST to: in a box one daily range tall the two areas meet, and an end that is
    # within the area of both counts for the nearer one only.
    assert rail_of(95.6, 96.0, 94.0, area) == "R" and rail_of(94.3, 96.0, 94.0, area) == "S"
    assert bar_respects(94.9, 94.2, 96.0, 94.0, area) == {"S"}       # its high is 1.1 from resistance, 0.9 from support
    assert bar_respects(95.6, 94.4, 96.0, 94.0, area) == {"R", "S"}
    # The walk reads whole arrays of bars: bar for bar the same picture, on the wide box and on the one-range box.
    from engine_alpha.two_eyes import walk
    bars = [(100.0, 90.0), (90.9, 89.4), (90.8, 90.1), (90.3, 89.7), (99.6, 96.0), (100.7, 97.0), (103.0, 100.6),
            (96.0, 94.0), (88.5, 86.0), (94.9, 94.2), (95.6, 94.4), (95.0, 95.0), (97.5, 92.5)]
    highs, lows = np.array([h for h, _ in bars]), np.array([l for _, l in bars])
    for top, bottom in ((100.0, 90.0), (96.0, 94.0)):
        on_r, on_s = walk._respects(highs, lows, top, bottom, area)
        for (high, low), r, s in zip(bars, on_r, on_s):
            assert {rail for rail, hit in (("R", r), ("S", s)) if hit} == bar_respects(high, low, top, bottom, area), \
                (high, low, top, bottom)


# --------------------------------------------------------------------------- #
# Sentences 1 and 3: a rail sits only on the end point of a swing             #
# --------------------------------------------------------------------------- #
def test_a_rail_sits_only_on_a_swings_end_and_one_wide_bar_gives_two():
    """His ruling on the reader's PBT box: "we only start to anchor from the end point of previous swings ... your
    Pick came from the middle of a swing in the direction of the trend". A turn of the line is a swing's end when
    the bar on neither side beats it; the other end of one wide bar counts when the bar's first end is one."""
    from engine_alpha.two_eyes.walk import swing_ends

    high = np.array([10.0, 11.0, 12.0, 11.4, 11.0, 12.6, 13.0, 12.2, 11.8, 12.0, 11.9])
    low = np.array([9.0, 10.2, 11.2, 10.4, 10.0, 10.8, 11.0, 11.5, 11.0, 11.4, 11.2])
    turns = [
        _turn(2, "peak", 12.0),             # the bar on neither side is higher: a swing's end
        _turn(4, "valley", 10.0),           # the bar on neither side is lower: a swing's end
        _turn(5, "peak", 12.6, know=5),     # a wide bar's high inside a rise still running: the next bar is higher
        _turn(5, "valley", 10.8, know=6),   # that bar's own low, the day after the real low: PBT's support
        _turn(6, "peak", 13.0, know=6),     # the top: a swing's end
        _turn(6, "valley", 11.0, know=8),   # the top bar's own low, the end of the move off it: one wide bar
        _turn(8, "valley", 11.0, know=9),   # level with it, the bar on neither side lower: a swing's end
        _turn(9, "peak", 12.0, know=False),  # the forming turn decides nothing
    ]
    ends = swing_ends(turns, high, low, read_bar=10)
    assert [(e.bar, e.kind, e.price, e.wide) for e in ends] == [
        (2, "peak", 12.0, False), (4, "valley", 10.0, False), (6, "peak", 13.0, False), (6, "valley", 11.0, True),
        (8, "valley", 11.0, False)]
    # An end is known the day after its bar — the next bar has to be seen — and never before the line committed it.
    assert [e.known_bar for e in ends] == [3, 5, 7, 8, 9]
    assert [e.index for e in ends] == [0, 1, 4, 5, 6]
    # On the top's own day the reader cannot know it is a top yet.
    assert all(e.bar != 6 for e in swing_ends(turns, high, low, read_bar=6))
    assert any(e.bar == 6 and e.kind == "peak" for e in swing_ends(turns, high, low, read_bar=7))
    # The wide bar's other end waits for the line to commit it (bar 8), not for the bar after it.
    assert not any(e.wide for e in swing_ends(turns, high, low, read_bar=7))


# --------------------------------------------------------------------------- #
# Stage 2: the end of the trend                                               #
# --------------------------------------------------------------------------- #
def test_the_trend_end_is_a_run_of_the_far_view_that_ended_and_its_walk_starts_on_the_first_end_of_its_level():
    from engine_alpha.two_eyes import walk

    chart = _chart(_BOX)
    found = _elect(chart)
    # The decline 58 / 52 / 56 / 50 ended when the far view printed a higher high (60 on bar 5, known on bar 6);
    # the rise into 80 ended when it printed a lower high (79.5 on bar 17, known on bar 18). At this scale the
    # box's own legs read as runs too (down to 70.4, up to 79.2): every one is a trend end, and the box's life
    # has to survive them.
    assert [(t["kind"], t["climax_price"], t["climax_bar"], t["known_bar"]) for t in found.ends] == [
        ("SC", 50.0, 3, 6), ("BC", 80.0, 11, 18), ("SC", 70.4, 26, 30), ("BC", 79.2, 29, 36)]
    # A run began on the low a rise came off, on the high a decline came off.
    assert [t["start_bar"] for t in found.ends] == [0, 3, 17, 26]
    # The decline inside the box ran 79.5 / 70.6 / 78.8 / 70.4: its walk starts on the FIRST low of the last
    # one's level, 70.6 on bar 20.
    assert [t["foot_bar"] for t in found.ends] == [3, 11, 20, 29]
    # A run whose end is not yet known is no trend end that day, and nothing is listed before the first one.
    assert _elect(chart, read_bar=5).ends == () and _elect(chart, read_bar=5).pairs == {}
    assert [t["climax_bar"] for t in _elect(chart, read_bar=17).ends] == [3]
    # The walk's first foot is the FIRST swing end of the climax's level in its run: "a later high that pokes a
    # little over his top does not move his line" (PBT: 22.71 five days after his 22.65). Here 80.6 on bar 14
    # pokes over the 80 of bar 11; the far view's climax is the 80.6, the walk starts on the 80.
    poked = _chart(_PREFIX + [(5, 60), (6, 55), (8, 70), (9, 66), (11, 80), (12, 78.6), (14, 80.6), (17, 70),
                              (20, 79.5), (23, 70.6), (26, 78.8), (29, 70.4)])
    far = {0, 1, 2, 3, 5, 6, 8, 9, 14, 17, 20, 23, 26}
    rise = _elect(poked, far).ends[1]
    assert (rise["kind"], rise["climax_price"], rise["climax_bar"], rise["foot_bar"]) == ("BC", 80.6, 14, 11)
    # The level is the rail area around the climax, one point here: with the climax at 81.2 the 80 of bar 11 is
    # no longer of its level and the walk starts on the climax's own bar; and a climax that is no swing's end
    # (nothing of its run within the area) starts no walk.
    ends = walk.swing_ends(poked["turns"], poked["high"], poked["low"], poked["n"] - 1)
    assert ends[walk.first_foot(ends, rise, poked["ranges"])].bar == 11
    assert ends[walk.first_foot(ends, dict(rise, climax_price=81.2), poked["ranges"])].bar == 14
    assert walk.first_foot(ends, dict(rise, climax_price=82.5), poked["ranges"]) is None
    # ... and only swing ends of its own run: a run that began after bar 11 does not reach back to it.
    assert ends[walk.first_foot(ends, dict(rise, start_bar=12), poked["ranges"])].bar == 14


# --------------------------------------------------------------------------- #
# Sentences 2, 4 and 5: the pair                                              #
# --------------------------------------------------------------------------- #
def test_a_pair_is_two_swing_ends_a_swing_connects_and_a_dismembered_pairing_is_never_listed():
    """Sentence 5 and his answer: "One rail may stay while the other moves" — "only if a swing connects between
    them, we cannot allow for dismemberd anchor paring". From the first bar to the second the top is the highest
    high and the low the lowest low."""
    from engine_alpha.two_eyes import walk

    # The climax 80 (bar 11), its reaction low 70 (bar 14), a lower high 76 (bar 17), a LOWER low 68 (bar 20), a
    # lower high 75 (bar 23) and a HIGHER low 71 (bar 26).
    chart = _chart(_RISE + [(17, 76), (20, 68), (23, 75), (26, 71), (29, 74)])
    found = _elect(chart)
    listed = {(p.R, p.r_bar, p.S, p.s_bar) for p in found.pairs.values()}
    # The climax and its reaction; resistance stays on the climax while support moves to the lower low, the
    # swing from 80 down to 68 connecting them.
    assert (80.0, 11, 70.0, 14) in listed and (80.0, 11, 68.0, 20) in listed
    # The climax with the HIGHER low of bar 26: the swing down off the climax ended at 68, so no swing connects
    # them. Never listed.
    assert not any(p.r_bar == 11 and p.s_bar == 26 for p in found.pairs.values())
    # One pair to the right: the next top with its own low, and the low with the next top (one foot in front of
    # the other).
    assert (76.0, 17, 68.0, 20) in listed and (76.0, 17, 70.0, 14) in listed and (75.0, 23, 68.0, 20) in listed
    # A top is paired with no low printed after a bar went over it: 76 with nothing after the 80... and the 80
    # with nothing before it. Every listed pair is connected, by bars.
    ends = {(e.bar, e.kind): e for e in found.swing_ends}
    for p in found.pairs.values():
        first, second = sorted((ends[(p.r_bar, "peak")], ends[(p.s_bar, "valley")]), key=lambda e: (e.bar, e.index))
        assert walk.connects(chart["high"], chart["low"], first, second), (p.R, p.S)
    assert not walk.connects(chart["high"], chart["low"], ends[(11, "peak")], ends[(26, "valley")])
    # The pairs open in order: no pair opens before the one listed before it.
    opens = [p.opening_bar for p in found.pairs.values()]
    assert opens == sorted(opens)
    # A run past the top dismembers it too: the climax 80, its reaction 70, a run to 86 and a crash to a LOWER
    # low, 69. The 80 is paired with its own reaction and never with the 69 — the 86 stands between them; the
    # 86 and the 69 are a pair.
    run = _chart(_RISE + [(16, 86), (19, 69), (22, 79), (25, 70), (28, 78.6)])
    listed = {(p.R, p.r_bar, p.S, p.s_bar) for p in _elect(run).pairs.values()}
    assert (80.0, 11, 70.0, 14) in listed and (86.0, 16, 69.0, 19) in listed
    assert not any(r_bar == 11 and s_bar == 19 for _, r_bar, _, s_bar in listed)


def test_a_counter_move_that_took_back_the_whole_move_before_it_is_listed_and_never_a_box():
    """Sentence 4 and his answer: "if a counter move is bigger it contributes already to a new counter trend!"
    The move before a top began at the lowest low since the price was last above it (for a low, the highest high
    since the price was last below it), by bars alone."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_BOX)
    found = _elect(chart)
    ends = {(e.bar, e.kind): e for e in found.swing_ends}
    # The move into the climax began at the decline's low, 50; the move into the reaction low 70 began at the
    # climax, 80 — the price was last below 70 before bar 11.
    assert walk.move_began(chart["high"], chart["low"], ends[(11, "peak")]) == 50.0
    assert walk.move_began(chart["high"], chart["low"], ends[(14, "valley")]) == 80.0
    # The climax and its reaction: the counter move took back ten of thirty points. A pair.
    root = _pair(found, 80.0, 70.0)
    assert root.unfit is None and root.top_first and root.began == 50.0
    # The low 50 with the high 60 after it: the move into that low began at 58; 60 is over it. The counter move
    # took back the whole decline: the rise had begun, and the pair is never a box.
    turned = _pair(found, 60.0, 50.0)
    assert not turned.top_first and turned.began == 58.0
    assert turned.unfit == walk.UNFIT_WHOLE_MOVE and turned.birth_bar is None
    # Inside the box: the low 70.6 with the top 78.8 after it took back a part of the fall from 79.5; the low
    # 70.4 after the top 78.8 took back the whole rise from 70.6.
    assert _pair(found, 78.8, 70.6).unfit is None
    assert _pair(found, 78.8, 70.4).unfit == walk.UNFIT_WHOLE_MOVE


def test_a_pair_under_one_daily_range_tall_is_listed_but_never_a_box_and_each_pair_has_its_own_unit():
    from engine_alpha.two_eyes import walk

    # After the reaction low a one-and-a-half-point bounce (71.5), then the base.
    chart = _chart(_RISE + [(16, 71.5), (18, 70.2), (21, 79.5), (24, 70.5), (27, 79.2), (30, 71), (33, 78.8)])
    chart["ranges"][14] = 2.5               # the root pair's second anchor day
    chart["ranges"][-1] = 6.0               # the read day is wide; no pair measures in it
    found = _elect(chart)
    tiny = _pair(found, 71.5, 70.0)
    assert tiny.unfit == walk.UNFIT_TALL and tiny.birth_bar is None
    root = _pair(found, 80.0, 70.0)
    assert root.unit == 2.5 and root.area == 1.25 and root.birth_bar is not None
    assert _box(found) == (80.0, 70.0) and all(p.unit != 6.0 for p in found.pairs.values())


def test_one_wide_bar_is_a_pair_read_in_whichever_order_makes_it_a_counter_move():
    """Sentence 3: "The two ends can be one wide bar's own high and low" (DRTS, FOSL, MSGS, MTLS). The daily bars
    do not say which end of the bar printed first, and the line's order inside a bar is a convention of ours; the
    pair is read in whichever order makes its second end a counter move."""
    from engine_alpha.two_eyes import walk

    # The climax bar itself: four points tall, its own low the end of the move off the top (MSGS, FOSL). The low
    # is no swing's end by the bar before it — that bar is lower, the rise came through it — and counts as the
    # other end of one wide bar.
    chart = _chart(_RISE[:-1] + [(14, 77.2), (17, 79.6), (20, 76.4), (23, 79.4), (26, 76.6)])
    high, low, ranges = chart["high"], chart["low"], chart["ranges"]
    low[11] = 76.0
    turns = [*chart["turns"][:9], _turn(11, "valley", 76.0, know=13), *chart["turns"][9:]]
    found = walk.elect(turns, turns, ranges, high, low, read_bar=chart["n"] - 1)
    assert [(e.bar, e.kind, e.wide) for e in found.swing_ends if e.bar == 11] == [(11, "peak", False),
                                                                                 (11, "valley", True)]
    pair = next(p for p in found.pairs.values() if (p.r_bar, p.s_bar) == (11, 11))
    assert (pair.R, pair.S, pair.top_first, pair.began, pair.unfit) == (80.0, 76.0, True, 50.0, None)
    assert pair.birth_bar == 25 and _box(found) == (80.0, 76.0)
    # A wide bar "a swing later" (DRTS, MTLS): after the climax 80 and its reaction 70, a lower high 77, then one
    # bar from 79 down to 72. The line came into that bar falling and lists its low first; read low first, the
    # bar's high would be a counter move bigger than the fall before it (79 over the 77 it fell from). Read top
    # first it is the end of the rise from 70 and its counter move: that is the pair.
    later = _chart(_RISE + [(17, 77), (19, 72), (22, 78.6), (25, 72.4), (28, 78.8), (31, 72.6)])
    later["high"][19] = 79.0
    turns = [*later["turns"][:12], _turn(19, "peak", 79.0, know=21), *later["turns"][12:]]
    assert [(t.bar, t.kind) for t in turns[11:13]] == [(19, "valley"), (19, "peak")]
    found = walk.elect(turns, turns, later["ranges"], later["high"], later["low"], read_bar=later["n"] - 1)
    pair = next(p for p in found.pairs.values() if (p.r_bar, p.s_bar) == (19, 19))
    assert (pair.R, pair.S, pair.top_first, pair.began, pair.unfit) == (79.0, 72.0, True, 70.0, None)
    assert pair.opening_bar == pair.second_bar == 19 and pair.birth_bar == 33


# --------------------------------------------------------------------------- #
# The walk's switches: his candidate rules, each a named switch; as built = on #
# --------------------------------------------------------------------------- #
def _gap_climax_chart() -> tuple:
    """The climax bar as one wide bar (the first chart of the one-wide-bar test above), and it GAPPED: its low 76
    sits over the bar before's high (73.2, the rise walking from 66 to 80). His EHC and ANF gap bars."""
    chart = _chart(_RISE[:-1] + [(14, 77.2), (17, 79.6), (20, 76.4), (23, 79.4), (26, 76.6)])
    chart["low"][11] = 76.0
    turns = [*chart["turns"][:9], _turn(11, "valley", 76.0, know=13), *chart["turns"][9:]]
    assert chart["high"][10] < chart["low"][11], "the climax bar gaps clear of the bar before"
    return chart, turns


def _wide_bar_later_chart() -> tuple:
    """A wide bar a swing later (the second chart of that test): 79 / 72 on bar 19, no gap."""
    later = _chart(_RISE + [(17, 77), (19, 72), (22, 78.6), (25, 72.4), (28, 78.8), (31, 72.6)])
    later["high"][19] = 79.0
    turns = [*later["turns"][:12], _turn(19, "peak", 79.0, know=21), *later["turns"][12:]]
    assert later["low"][19] < later["high"][18], "no gap"
    return later, turns


def _switched(monkeypatch, **switches):
    from engine_alpha import two_eyes_numbers as M

    for name, value in switches.items():
        assert isinstance(getattr(M, name), bool), f"{name} is not a switch"
        monkeypatch.setattr(M, name, value)


def test_a_one_bar_climax_box_the_bars_never_came_back_to_gives_way_to_the_tighter_pair_inside_that_wraps_them():
    """His AMTB (Wed 28/10/2026), "rather than this abomination": the climax bar's own high and low (80 / 72, one
    bar eight points tall) is a box by the rule on its fifteenth day, because in its OWN range (area four points)
    every bar under its top "respects" both rails. The bars live between 77.5 and 74.5 and never come back to 80 or
    to 72. His word (Thu 29/10/2026): the box must wrap the actual price action. The pair inside them, meaningfully
    tighter and opened while the one-bar pair was forming, takes its place the day it is a box (``WRAPS``): his two
    pictures, the BC / AR box first, then the box found later. Only a ONE-BAR box gives way this way: a box of two
    bars, the climax and its reaction, keeps its place whatever sits inside it (his SILC, 21.70 / 19.35, whose top
    the bars came back to only loosely). Read day by day with no memory, told the same on every later day."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_RISE[:-1] + [(14, 74.5), (17, 77.5), (20, 74.6), (23, 77.3), (26, 74.4), (29, 77.4), (32, 74.7),
                                 (35, 77.2), (38, 74.5), (41, 77.3), (44, 74.6)])
    chart["low"][11], chart["ranges"][11] = 72.0, 8.0
    chart["turns"] = [*chart["turns"][:9], _turn(11, "valley", 72.0, know=13), *chart["turns"][9:]]
    found = _elect(chart)
    one_bar = _pair(found, 80.0, 72.0)
    assert (one_bar.r_bar, one_bar.s_bar, one_bar.unit, one_bar.birth_bar) == (11, 11, 8.0, 25)
    first, then = found.lives[0], found.lives[-1]
    assert (first.pair.R, first.pair.S, first.shown_bar, first.why) == (80.0, 72.0, 25, walk.FIRST_BOX)
    assert then.why == walk.WRAPS and then.pair.R == 77.5 and 74.4 <= then.pair.S <= 74.6, then
    assert then.pair.opening_bar <= one_bar.birth_bar and then.pair.height < one_bar.height
    assert then.shown_bar == then.pair.birth_bar and first.ended_bar == then.pair.opening_bar
    assert walk.wraps(one_bar, then.pair, chart["high"], chart["low"], 25, chart["n"] - 1) == then.shown_bar
    assert walk.wraps(one_bar, then.pair, chart["high"], chart["low"], 25, then.shown_bar - 1) is None
    # Told the same on every later day: the hand-over is dated on what its own day knew.
    shown = _shown_day_by_day(chart)
    assert shown[0] == (80.0, 72.0, 25) and shown[1][:2] == (then.pair.R, then.pair.S) and len(shown) == 2
    boxes, trail, _ = walk.record(found)
    assert trail[0].stage == "hand-over" and "never came back to one of its rails" in trail[0].saying
    assert "80.00 / 72.00" in trail[0].saying and f"{then.pair.R:.2f} / {then.pair.S:.2f}" in trail[0].saying
    # With the switch off the one-bar box stands, as the rule was built before Thu 29/10/2026.
    with pytest.MonkeyPatch.context() as mp:
        _switched(mp, WRAP_TAKES_OVER=False)
        assert _box(_elect(chart)) == (80.0, 72.0) and len(_elect(chart).lives) == 1
    # The box whose rails the bars DO come back to (the one-wide-bar test above: 80 / 76 over bars between 79.6
    # and 76.4) keeps its place: its legs inside it are its own.
    kept, turns = _gap_climax_chart()
    found = walk.elect(turns, turns, kept["ranges"], kept["high"], kept["low"], read_bar=kept["n"] - 1)
    assert _box(found) == (80.0, 76.0) and len(found.lives) == 1


def test_the_switches_default_to_the_rule_as_built():
    """Every switch is on: the walk reads exactly as it did before the switches were named (Wed 28/10/2026), so
    the as-built path is the default and a measurement flips ONE of them."""
    from engine_alpha import two_eyes_numbers as M

    assert (M.ONE_BAR_PAIR, M.GAP_BAR_LOW_IS_REACTION, M.WIDE_ENDS, M.CLIMAX_BAR_OWN_REACTION,
            M.WRAP_TAKES_OVER) == (True,) * 5
    # His direction of Fri 30/10/2026, each a switch that defaults to the reader as built: the election by respect is
    # off and the mini stage is on until the board says otherwise.
    assert (M.RESPECT_ELECTS, M.MINI_ENABLED) == (False, False)


def _shelf_chart() -> dict:
    """A rise into a spike at 80 (bar 11), its reaction 70 (bar 14), the bars back at 80 (17) and 70 (20): the wide
    box 80 / 70 is born on bar 25. From bar 23 on the bars settle on a shelf 76 / 73 and live there: his ANET, VTMX,
    CLOV and CBLL of Fri 30/10/2026, where the reader hung a rail on the spike and he drew the shelf."""
    shelf = [(23, 76.0), (26, 73.0), (29, 76.2), (32, 73.1), (35, 75.9), (38, 73.0), (41, 76.1), (44, 72.9),
             (47, 76.0), (50, 73.1), (53, 75.8), (56, 73.2)]
    return _chart(_RISE + [(17, 79.6), (20, 70.4)] + shelf)


def test_respect_marks_count_a_touch_for_a_pair_and_a_bar_wholly_beyond_a_rail_against_it():
    """His close-enough (Fri 30/10/2026), each bar in its OWN daily range: a rail 10 / 8, every bar's range 1 (an area
    of half a point). An end within the area of the rail it is closest to is a touch (+1); a bar wholly beyond a rail
    by more than the area counts against the pair (-1); a bar inside, or short of the area, counts nothing."""
    from engine_alpha.two_eyes import walk

    high = [10.2, 9.0, 11.0, 7.0, 8.4, 10.6]
    low = [9.9, 8.6, 10.6, 6.5, 7.6, 9.2]
    on_r, on_s = walk.respect_marks(high, low, np.ones(6), 10.0, 8.0)
    assert on_r.tolist() == [1, 0, -1, 0, 0, 0]       # at R; inside; wholly over R; under S; at S; a poke past the area
    assert on_s.tolist() == [0, 0, 0, -1, 1, 0]
    # The area is the bar's OWN range: the same bars read in a range of two touch where they stopped short before.
    wide_r, wide_s = walk.respect_marks(high, low, np.full(6, 2.0), 10.0, 8.0)
    assert wide_r.tolist() == [1, 1, 1, 0, 0, 1] and wide_s.tolist() == [0, 1, 0, 1, 1, 0]
    cum = walk.respect_cum(high, low, np.ones(6), 10.0, 8.0)
    assert cum.tolist() == [0, 1, 1, 0, -1, 0, 0] and cum[6] - cum[0] == 0 and cum[2] - cum[0] == 1


def test_under_the_election_by_respect_the_shelf_the_bars_live_on_takes_the_spike_boxs_place(monkeypatch):
    """His direction of Fri 30/10/2026: *"Still on High/LOW values only but with out being hung on extremes"*. As
    built the wide box 80 / 70 is shown for good: its spike rail is a swing's end the bars came back to once, and
    the shelf inside it, 76 / 73, is only its mini. Under ``RESPECT_ELECTS`` the shelf is the box: over the days
    since it opened the bars touch its two rails and never the spike's, so it leads by the margin on the day it is a
    box (bar 37, its fifteenth) and takes the place; the hand-over is dated on what its own day knew, told the same
    on every later day, and said in the trail. The margin is the incumbent's: raised out of reach, the wide box
    stands."""
    from engine_alpha import two_eyes_numbers as M
    from engine_alpha.two_eyes import walk

    chart = _shelf_chart()
    as_built = _elect(chart)
    assert _box(as_built) == (80.0, 70.0) and len(as_built.lives) == 1 and _pair(as_built, 76.0, 73.0).birth_bar == 37
    _switched(monkeypatch, RESPECT_ELECTS=True)
    found = _elect(chart)
    first, then = found.lives
    assert (first.pair.R, first.pair.S, first.shown_bar, first.why, first.ended_bar) == (80.0, 70.0, 25, walk.FIRST_BOX, 23)
    assert (then.pair.R, then.pair.S, then.shown_bar, then.why) == (76.0, 73.0, 44, walk.RESPECTED)
    assert then.lead is not None and then.lead >= M.RESPECT_MARGIN
    wide, tight = first.pair, then.pair
    cum_wide = walk.respect_cum(chart["high"], chart["low"], chart["ranges"], wide.R, wide.S)
    cum_tight = walk.respect_cum(chart["high"], chart["low"], chart["ranges"], tight.R, tight.S)
    n = chart["n"]
    assert cum_wide[n] - cum_wide[23] == 0, "the bars never touch the spike or the reaction low after the shelf opens"
    assert walk.out_respected(wide, tight, cum_wide, cum_tight, 25, n - 1) == (44, then.lead)
    assert walk.out_respected(wide, tight, cum_wide, cum_tight, 25, 43) is None, "not before the spike box's own touches fell under the margin"
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (76.0, 73.0, 44)]
    boxes, trail, _ = walk.record(found)
    assert trail[0].stage == "hand-over" and "the bars respect 76.00 / 73.00 more" in trail[0].saying
    assert f"{then.lead} touches ahead" in trail[0].saying and "80.00 / 70.00" in trail[0].saying
    assert boxes[0].end_day is not None and boxes[-1].resistance.price == 76.0
    # The margin is the incumbent's.
    monkeypatch.setattr(M, "RESPECT_MARGIN", 1000)
    assert _box(_elect(chart)) == (80.0, 70.0) and len(_elect(chart).lives) == 1
    monkeypatch.setattr(M, "RESPECT_MARGIN", 3)
    # The election reads each bar's own range: the walk refuses to run it without one.
    with pytest.raises(ValueError, match="own daily range"):
        walk.lives(found.pairs.values(), [], chart["high"], chart["low"], n - 1)
    # The box whose rails the bars DO come back to keeps its place: a box of a climax and its reaction the bars keep
    # touching is not out-respected by any pair inside it (the one-wide-bar chart: 80 / 76 over bars at 79.6 and 76.4).
    kept, turns = _gap_climax_chart()
    found = walk.elect(turns, turns, kept["ranges"], kept["high"], kept["low"], read_bar=kept["n"] - 1)
    assert _box(found) == (80.0, 76.0) and len(found.lives) == 1


def test_the_climax_bar_switch_off_never_takes_both_anchors_from_a_trend_ends_climax_bar(monkeypatch):
    """``CLIMAX_BAR_OWN_REACTION`` off: a pair whose first anchor is a trend end's CLIMAX bar never takes its second
    anchor from that same bar (his words, Wed 28/10/2026: "a climax and its reaction are never on one bar as in a
    true climax's end and its reaction, but when choosing a box, a single bar can represent the climax and the
    reaction for that box's root swing" — the switch names the first half; on by default, the second). A one-bar
    pair on any other bar is still listed; ``ONE_BAR_PAIR`` is the switch for all of them."""
    from engine_alpha.two_eyes import walk

    chart, turns = _gap_climax_chart()
    high, low, ranges = chart["high"], chart["low"], chart["ranges"]
    as_built = walk.elect(turns, turns, ranges, high, low, read_bar=chart["n"] - 1)
    assert [t["climax_bar"] for t in as_built.ends if t["kind"] == "BC"] == [11], "bar 11 is the rise's climax"
    assert (11, 11) in {(p.r_bar, p.s_bar) for p in as_built.pairs.values()}
    _switched(monkeypatch, CLIMAX_BAR_OWN_REACTION=False)
    found = walk.elect(turns, turns, ranges, high, low, read_bar=chart["n"] - 1)
    assert (11, 11) not in {(p.r_bar, p.s_bar) for p in found.pairs.values()}
    assert found.swing_ends == as_built.swing_ends and _box(found) != (80.0, 76.0)
    assert set(found.pairs) == {k for k, p in as_built.pairs.items() if (p.r_bar, p.s_bar) != (11, 11)}
    # The wide bar a swing later is no climax: its one-bar pair stays.
    later, turns = _wide_bar_later_chart()
    found = walk.elect(turns, turns, later["ranges"], later["high"], later["low"], read_bar=later["n"] - 1)
    assert (19, 19) in {(p.r_bar, p.s_bar) for p in found.pairs.values()}
    assert 19 not in {t["climax_bar"] for t in found.ends}


def test_the_one_bar_pair_switch_off_never_pairs_an_end_with_the_other_end_of_its_own_bar(monkeypatch):
    """``ONE_BAR_PAIR`` off: sentence 3's pair is not listed (his AMTB, Wed 28/10/2026: "rather than this
    abomination" of the climax bar's own high and low). The wide end itself is still a swing's end and may pair
    with ends on other bars; only the pairing with its own bar's other end is refused, in ``pairs_from``."""
    from engine_alpha.two_eyes import walk

    for chart, turns in (_gap_climax_chart(), _wide_bar_later_chart()):
        high, low, ranges = chart["high"], chart["low"], chart["ranges"]
        as_built = walk.elect(turns, turns, ranges, high, low, read_bar=chart["n"] - 1)
        assert any(p.r_bar == p.s_bar for p in as_built.pairs.values())
        _switched(monkeypatch, ONE_BAR_PAIR=False)
        found = walk.elect(turns, turns, ranges, high, low, read_bar=chart["n"] - 1)
        monkeypatch.undo()
        assert not any(p.r_bar == p.s_bar for p in found.pairs.values()), "a one-bar pair was listed"
        assert found.swing_ends == as_built.swing_ends, "the ends are the same ends"
        assert _box(found) != _box(as_built), "the one-bar box stood"
        # Every other pair is the same pair.
        assert set(found.pairs) == {k for k, p in as_built.pairs.items() if p.r_bar != p.s_bar}


def test_the_gap_bar_switch_off_reads_a_gap_bars_own_low_as_where_the_rise_landed(monkeypatch):
    """``GAP_BAR_LOW_IS_REACTION`` off (his EHC and ANF, Sat 24/10/2026; the parked GU2 reading): a bar that gapped
    clear of the bar before (its low over that bar's high) gives no wide valley end, and from its top the running
    low leaves the bar's own low out, so a later low can be the reaction. A wide bar that did not gap is read as
    built."""
    from engine_alpha.two_eyes import walk

    chart, turns = _gap_climax_chart()
    high, low, ranges = chart["high"], chart["low"], chart["ranges"]
    as_built = walk.elect(turns, turns, ranges, high, low, read_bar=chart["n"] - 1)
    assert (11, 11) in {(p.r_bar, p.s_bar) for p in as_built.pairs.values()}
    assert (80.0, 77.2) not in {(p.R, p.S) for p in as_built.pairs.values()}, "the gap bar's low hid the 77.2 low"
    _switched(monkeypatch, GAP_BAR_LOW_IS_REACTION=False)
    found = walk.elect(turns, turns, ranges, high, low, read_bar=chart["n"] - 1)
    assert [(e.bar, e.kind, e.wide) for e in found.swing_ends if e.bar == 11] == [(11, "peak", False)]
    listed = {(p.R, p.S) for p in found.pairs.values()}
    assert (80.0, 76.0) not in listed and (80.0, 77.2) in listed and (80.0, 76.4) in listed
    assert _box(found) != (80.0, 76.0)
    # No gap, no change: the wide bar a swing later reads as built.
    later, turns = _wide_bar_later_chart()
    high, low, ranges = later["high"], later["low"], later["ranges"]
    found = walk.elect(turns, turns, ranges, high, low, read_bar=later["n"] - 1)
    monkeypatch.undo()
    same = walk.elect(turns, turns, ranges, high, low, read_bar=later["n"] - 1)
    assert found.pairs == same.pairs and found.swing_ends == same.swing_ends


def test_the_wide_ends_switch_off_lists_no_other_end_of_a_wide_bar(monkeypatch):
    """``WIDE_ENDS`` off: sentence 3 is off whole — the other end of one wide bar is no swing's end at all, so it
    pairs with nothing, on its own bar or any other (the W reading of Sat 24/10/2026, for scale)."""
    from engine_alpha.two_eyes import walk

    high = np.array([10.0, 11.0, 12.0, 11.4, 11.0, 12.6, 13.0, 12.2, 11.8, 12.0, 11.9])
    low = np.array([9.0, 10.2, 11.2, 10.4, 10.0, 10.8, 11.0, 11.5, 11.0, 11.4, 11.2])
    turns = [_turn(2, "peak", 12.0), _turn(4, "valley", 10.0), _turn(5, "peak", 12.6, know=5),
             _turn(5, "valley", 10.8, know=6), _turn(6, "peak", 13.0, know=6), _turn(6, "valley", 11.0, know=8),
             _turn(8, "valley", 11.0, know=9), _turn(9, "peak", 12.0, know=False)]
    as_built = walk.swing_ends(turns, high, low, read_bar=10)
    assert [(e.bar, e.kind, e.wide) for e in as_built] == [(2, "peak", False), (4, "valley", False),
                                                             (6, "peak", False), (6, "valley", True),
                                                             (8, "valley", False)]
    _switched(monkeypatch, WIDE_ENDS=False)
    assert [(e.bar, e.kind, e.wide) for e in walk.swing_ends(turns, high, low, read_bar=10)] == [
        (2, "peak", False), (4, "valley", False), (6, "peak", False), (8, "valley", False)]
    chart, turns = _gap_climax_chart()
    found = walk.elect(turns, turns, chart["ranges"], chart["high"], chart["low"], read_bar=chart["n"] - 1)
    assert not any(e.wide for e in found.swing_ends)
    assert not any(11 in (p.r_bar, p.s_bar) and p.S == 76.0 for p in found.pairs.values())


# --------------------------------------------------------------------------- #
# Sentences 6, 7 and 8: coming back, and the day the pair is a box            #
# --------------------------------------------------------------------------- #
def test_the_bars_come_back_to_the_rail_the_pair_opened_on_and_then_to_the_other():
    """Sentence 6 as he showed it on the pictures (Thu 01/10/2026). A bar comes back to a rail when it respects
    it, and resting on it is respect: "Silc supposed to work due the much respect of the support". The rail the
    pair opened on comes first; the other rail counts from that day on, so the price has been at the other rail in
    between: a reaction low the base never returns to is no respected rail ("why would DRTS move away")."""
    from engine_alpha.two_eyes.walk import came_back

    #                  0      1      2      3      4      5      6
    high = np.array([100.0, 97.0, 93.0, 99.4, 97.0, 96.0, 101.2])
    low = np.array([98.0, 90.0, 90.5, 96.0, 94.0, 89.4, 99.3])
    # Resistance 100 (bar 0), support 90 (bar 1), the area one point, the pair opening on resistance. Bar 3's
    # high is back at resistance. Bar 5's low, six tenths under support, is back at support: poking out counts.
    # Bar 2 rests on support the day after the low — respect, but before the bars were back at resistance.
    assert came_back(high, low, 100.0, 90.0, 1.0, 0, 1, 6, top_first=True) == (3, 5)
    # What the reader knows on an earlier day.
    assert came_back(high, low, 100.0, 90.0, 1.0, 0, 1, 4, top_first=True) == (3, None)
    assert came_back(high, low, 100.0, 90.0, 1.0, 0, 1, 2, top_first=True) == (None, None)
    # His DRTS: the bars go back to resistance and never return to the reaction low. The day after the low,
    # still resting on it, does not make the low a respected rail.
    assert came_back(high[:5], low[:5], 100.0, 90.0, 1.0, 0, 1, 4, top_first=True) == (3, None)
    # The same bars read as a pair that opened on SUPPORT: support comes first (bar 2, resting on it the day
    # after), then resistance on that day or after (bar 3).
    assert came_back(high, low, 100.0, 90.0, 1.0, 1, 0, 6, top_first=False) == (3, 2)
    # A come-back is later than BOTH anchors: with support anchored on bar 4 (94), bar 3 is no come-back to
    # resistance, and bar 6 — its low resting on resistance from above — is.
    assert came_back(high, low, 100.0, 94.0, 1.0, 0, 4, 6, top_first=True) == (6, None)
    # Nothing after the anchors: nothing came back.
    assert came_back(high, low, 100.0, 99.3, 1.0, 0, 6, 6, top_first=True) == (None, None)
    # His SILC: a box barely over one daily range tall, where every bar sits within the area of support. The bars
    # never LEAVE support, they rest on it; bar 3, whose high is back at resistance, rests on support too, and
    # both rails are come back to that day.
    #                 0     1     2     3     4
    high = np.array([96.0, 95.2, 94.9, 95.6, 94.8])
    low = np.array([95.0, 94.0, 94.2, 94.4, 94.1])
    assert came_back(high, low, 96.0, 94.0, 1.0, 0, 1, 4, top_first=True) == (3, 3)
    assert came_back(high, low, 96.0, 94.0, 1.0, 0, 1, 2, top_first=True) == (None, None)


def test_a_pair_is_a_box_on_the_later_of_both_come_backs_its_fifteenth_day_and_its_listing_day():
    """Sentence 7: "Lets go with 15 days"; "or later if the bars take longer to come back"."""
    chart = _chart(_BOX)
    root = _pair(_elect(chart), 80.0, 70.0)
    # Listed the day both ends were known (bar 15); the bars back at resistance on bar 17 (79.5) and at support
    # on bar 20 (70.6); the fifteenth trading day from the first anchor is bar 25, and it binds.
    assert (root.joined_bar, root.r_back, root.s_back, root.fifteenth, root.birth_bar) == (15, 17, 20, 25, 25)
    # A birth after the read day is not a birth yet: no box on bar 24, the box on bar 25.
    assert _box(_elect(chart, read_bar=24)) is None and _pair(_elect(chart, read_bar=24), 80.0, 70.0).birth_bar is None
    assert _box(_elect(chart, read_bar=25)) == (80.0, 70.0)
    # The bars take longer to come back: the price rests on support for two weeks and resistance is first
    # revisited on bar 29. The box waits for it — and is the box that day, however late: "account for the bases
    # eventual recovery ... rather then rejecting it out right".
    late = _chart(_RISE + [(17, 71.6), (20, 70.5), (23, 71.8), (26, 70.4), (29, 79.6), (32, 71), (35, 79)])
    slow = _pair(_elect(late), 80.0, 70.0)
    # ... and then back at support, on bar 32: resistance first, support on that day or after.
    assert (slow.r_back, slow.s_back, slow.fifteenth, slow.birth_bar) == (29, 32, 25, 32)
    assert _box(_elect(late, read_bar=31)) is None and _box(_elect(late, read_bar=32)) == (80.0, 70.0)
    # The listing day binds when the trend end before the pair is known late: with a far view that sees the
    # first decline end only on bar 27, nothing is listed before it and the pair is a box that day.
    known_late = _elect(chart, far_bars={0, 1, 2, 3, 26, 29, 32})
    assert [t["known_bar"] for t in known_late.ends] == [27]
    assert _pair(known_late, 80.0, 70.0).joined_bar == 27 and _pair(known_late, 80.0, 70.0).birth_bar == 27


def test_a_run_past_a_rail_never_unmakes_a_pair_by_itself():
    """Sentence 8, and his word on ALB: "that breach is not an upthrust ... its just that those pairs could be
    used to fit the box, even a later pair could work if that movement in 20/1 -> 27/1 and the crash afterwards
    could be treated as the place where the trend ends". Five days after the pair opens the price stands three
    daily ranges over its resistance; the bars come back to both rails, and on its fifteenth day it is the box.
    Then the later pair, the first after the run's own top that the bars come back to, is a box too, and the far
    view by then says the rise ended on that top: the later pair takes its place — his other reading."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_RUN_PAST_THE_RAIL)
    found = _elect(chart)
    early = _pair(found, 80.0, 70.0)
    assert float(chart["high"][16]) == 86.0 and (86.0 - early.R) / early.unit == 3.0
    assert (early.r_back, early.s_back, early.birth_bar, early.unfit) == (17, 19, 25, None)
    assert _box(_elect(chart, read_bar=25)) == _box(_elect(chart, read_bar=32)) == (80.0, 70.0)
    # The run's own pair: the bars never come back to 86. Listed, and no box.
    assert _pair(found, 86.0, 70.5).r_back is None and _pair(found, 86.0, 70.5).birth_bar is None
    # The far view: the rise ended at 86 (known on bar 23), and its run had begun at 50 — before the early pair.
    rise = found.ends[1]
    assert (rise["kind"], rise["climax_price"], rise["start_bar"], rise["known_bar"]) == ("BC", 86.0, 3, 23)
    first, later = found.lives
    assert (first.pair.R, first.pair.S, first.shown_bar, first.why) == (80.0, 70.0, 25, walk.FIRST_BOX)
    assert (later.pair.R, later.pair.S, later.shown_bar, later.why) == (79.5, 70.5, 33, walk.LIVE_TREND)
    assert later.trend_end["climax_price"] == 86.0
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (79.5, 70.5, 33)]


# --------------------------------------------------------------------------- #
# Stage 4: the box's life                                                     #
# --------------------------------------------------------------------------- #
def test_the_first_pair_to_become_a_box_is_shown_and_its_own_legs_inside_it_never_take_its_place():
    """"were looking for the first instance that a consolidation is respected!", and sentence 9: "Once a box, it
    stays a box through dips under support and pokes over resistance that come back". The box's own legs inside it
    never take its place (from Thu 29/10/2026 one box gives way inside: a box that is ONE bar's own high and low, to the
    pair inside it the bars live in — the test after the switches' tests)."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_BOX)
    found = _elect(chart)
    assert _box(found) == (80.0, 70.0) and len(found.lives) == 1 and found.lives[0].why == walk.FIRST_BOX
    # Pairs born later inside it — the box's own legs — never take its place.
    inside = [p for p in found.pairs.values() if p.birth_bar is not None and (p.R, p.S) != (80.0, 70.0)]
    assert len(inside) >= 4 and all(p.birth_bar > 25 and p.R <= 80.0 and p.S >= 70.0 for p in inside)
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25)]
    # Two pokes to 84, two daily ranges over resistance, each coming back. The pair the poke makes, 84 / 72, is
    # a box by the rules on bar 49 and lies ACROSS the box's resistance: the box's own event, never a new box.
    pokes = _chart(_BOX_WITH_POKES)
    found = _elect(pokes)
    poke = _pair(found, 84.0, 72.0)
    assert poke.birth_bar == 50 and poke.opening_bar > found.winner.opening_bar
    assert walk.left_for_good(found.winner, poke, pokes["high"], pokes["low"], 0, pokes["n"] - 1) is None
    assert _shown_day_by_day(pokes) == [(80.0, 70.0, 25)]


def test_the_box_gives_way_only_when_the_price_left_it_and_the_bars_no_longer_come_back_to_both_its_rails():
    """Sentence 10: "the bars now hang on the newer rails and no longer come back to the old ones". The base
    94 / 88 lies beyond the box 80 / 70 — its support over the box's resistance area — and from the day it opened
    the bars never came back to both rails of the old box: on the day it is a box by his rules, it takes the old
    box's place. The old box stays in the record, its lines stopping where the new one opens."""
    from engine_alpha.two_eyes import walk, record

    chart = _chart(_BOX_THEN_BREAKOUT)
    found = _elect(chart)
    old, new = found.lives
    assert (old.pair.R, old.pair.S, old.shown_bar, old.ended_bar) == (80.0, 70.0, 25, 35)
    assert (new.pair.R, new.pair.S, new.shown_bar, new.why) == (94.0, 88.0, 49, walk.LEFT_FOR_GOOD)
    assert new.pair.birth_bar == 49 and new.ended_bar is None
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (94.0, 88.0, 49)]
    boxes, trail, state = walk.record(found)
    earlier, parent = boxes
    assert earlier.role == record.ROLE_EARLIER and parent.role == record.ROLE_PARENT
    assert (earlier.resistance.price, earlier.support.price) == (80.0, 70.0)
    assert earlier.opened_day == _day(11) and earlier.end_day == _day(35) and earlier.daily_range == 2.0
    assert (parent.resistance.price, parent.support.price, parent.opened_day, parent.end_day) == \
        (94.0, 88.0, _day(35), None)
    assert [s.stage for s in trail] == ["hand-over", "trend end", "box"] and state == "lines, no LPS yet"
    assert "80.00 / 70.00" in trail[0].saying and "94.00 / 88.00" in trail[0].saying and "above" in trail[0].saying
    assert f"{_day(35):%a %d/%m/%Y}" in trail[0].saying and f"{_day(49):%a %d/%m/%Y}" in trail[0].saying
    # The same run and the same pair above — but the price crashed back to the box's support (bar 43) and its
    # resistance (bar 46) before the pair above was a box: a breakout that failed. The bars came back to both
    # rails, so on the day the pair above is a box (bar 52) the box stands, however clean the pair above.
    failed = _chart(_BREAKOUT_THAT_CAME_BACK)
    high, low, last = failed["high"], failed["low"], failed["n"] - 1
    box, above = _pair(_elect(failed), 80.0, 70.0), _pair(_elect(failed), 94.0, 88.0)
    assert above.birth_bar == 52 and above.S >= box.R - box.area
    assert _box(_elect(failed, read_bar=52)) == _box(_elect(failed, read_bar=57)) == (80.0, 70.0)
    assert walk.left_for_good(box, above, high, low, 0, 57) is None
    # Judged on every day, not once: the price went back up and for fifteen days the bars hung on the rails
    # above — the last bar at the old support is bar 43, and bar 58 is the fifteenth day after it. That day the
    # price has left the box, and the pair above takes its place.
    assert walk.left_for_good(box, above, high, low, 0, last) == 58
    assert walk.left_for_good(box, above, high, low, 60, last) == 60        # never before the day asked from
    assert _shown_day_by_day(failed) == [(80.0, 70.0, 25), (94.0, 88.0, 58)]
    # Beyond means resting on the old rail's area or further: were the old resistance at 89, the base above
    # (support 88) would rest on its area; at 89.1, a tenth of a point more, it lies across the box and never
    # takes its place.
    high, low, last = chart["high"], chart["low"], chart["n"] - 1
    assert walk.left_for_good(old.pair, new.pair, high, low, 0, last) == 49     # never before it is a box
    from dataclasses import replace
    assert walk.left_for_good(replace(old.pair, R=89.0), new.pair, high, low, 0, last) == 49
    assert walk.left_for_good(replace(old.pair, R=89.1), new.pair, high, low, 0, last) is None
    # ... and only a pair that opened LATER: the old box never takes the new one's place back.
    assert walk.left_for_good(new.pair, old.pair, high, low, 0, last) is None
    # A read day before the newer pair is a box: no day yet.
    assert walk.left_for_good(old.pair, new.pair, high, low, 0, 48) is None


def test_a_box_never_gives_way_to_rails_the_bars_have_left():
    """Sentence 10 in its own words, both halves: "the bars now hang on the newer rails and no longer come back
    to the old ones". The pair above (94 / 88) is a box by the rule on bar 49 and lies beyond the box; the bars
    were back at both rails of the box on bars 45 and 48, so it stands. From bar 63 no bar of fifteen days has
    been back at the box's resistance — and none has been near the pair above since bar 42: the price is under
    the box. The box does not give way to rails the bars have left. It gives way on bar 65 to the pair the bars
    do hang on, under it."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_RUN_ABOVE_THEN_UNDER_THE_BOX)
    high, low, last = chart["high"], chart["low"], chart["n"] - 1
    found = _elect(chart)
    box, above, under = _pair(found, 80.0, 70.0), _pair(found, 94.0, 88.0), _pair(found, 68.6, 66.0)
    assert (above.r_back, above.s_back, above.birth_bar) == (41, 42, 49) and above.S >= box.R - box.area
    on_r, on_s = walk._respects(high, low, 80.0, 70.0, box.area)
    assert on_s[45] and on_r[48] and not on_r[49:].any()             # the last bar at the box's resistance: 48
    hang_r, hang_s = walk._respects(high, low, 94.0, 88.0, above.area)
    assert not hang_r[42:].any() and not hang_s[43:].any()            # no bar at the pair above after bar 42
    assert walk.left_for_good(box, above, high, low, 0, last) is None
    assert (under.birth_bar, under.R <= box.S + box.area) == (65, True)
    assert walk.left_for_good(box, under, high, low, 0, last) == 65
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (68.6, 66.0, 65)]
    assert [(life.pair.R, life.pair.S) for life in found.lives] == [(80.0, 70.0), (68.6, 66.0)]


def test_the_mirror_a_decline_out_of_the_box_hands_over_to_a_new_box_below():
    from engine_alpha.two_eyes import walk

    mirrored = [(bar, 160.0 - price) for bar, price in _BOX_THEN_BREAKOUT]
    chart = _chart(mirrored)
    found = _elect(chart)
    assert _shown_day_by_day(chart) == [(90.0, 80.0, 25), (72.0, 66.0, 49)]
    old, new = found.lives
    assert not old.pair.top_first and not new.pair.top_first        # each opens on support, after a decline
    assert new.why == walk.LEFT_FOR_GOOD and old.ended_bar == 35
    assert "below" in walk.record(found)[1][0].saying


def test_a_box_anchored_inside_a_live_trend_gives_way_to_the_trend_ends_own_box():
    """His anchor rule: "We can't start the anchor from the opposite direction of the trend if we are still inside
    that trend" (Mon 27/07/2026), and sentence 5: the first pair is "the end of the move before the box". The
    pause 70 / 66 is a box by the rules on bar 22. The rise goes on to 80 and the base forms on 80 / 68.5, whose
    support is back inside the pause box: the price never left it for good. Once the far view says the rise ended
    at 80, and 80 / 68.5 is a box, it takes the pause's place."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_PAUSE_INSIDE_A_RISE)
    found = _elect(chart, _PAUSE_FAR)
    rise = found.ends[1]
    assert (rise["kind"], rise["climax_price"], rise["start_bar"], rise["foot_bar"], rise["known_bar"]) == \
        ("BC", 80.0, 3, 24, 31)
    pause, base = found.lives
    assert (pause.pair.R, pause.pair.S, pause.shown_bar, pause.ended_bar) == (70.0, 66.0, 22, 24)
    assert (base.pair.R, base.pair.S, base.pair.birth_bar, base.shown_bar, base.why) == \
        (80.0, 68.5, 38, 38, walk.LIVE_TREND)
    assert base.trend_end["climax_bar"] == 24
    # Not by the other rule: the base's support is inside the pause box, a point and a half under its resistance.
    assert walk.left_for_good(pause.pair, base.pair, chart["high"], chart["low"], 0, chart["n"] - 1) is None
    assert walk.inside_a_live_trend(pause.pair, base.pair, found.ends, 38) is rise
    assert _shown_day_by_day(chart, _PAUSE_FAR) == [(70.0, 66.0, 22), (80.0, 68.5, 38)]
    assert "a rise that had not ended" in walk.record(found)[1][0].saying
    # Judged once the trend end is KNOWN: a far view that sees the rise end only on bar 43 keeps the pause box
    # until that day, though 80 / 68.5 is a box from bar 38.
    late = _PAUSE_FAR - {30, 33, 36, 39}
    assert _elect(chart, late).ends[1]["known_bar"] == 43
    assert walk.inside_a_live_trend(pause.pair, base.pair, _elect(chart, late).ends, 42) is None
    assert _shown_day_by_day(chart, late) == [(70.0, 66.0, 22), (80.0, 68.5, 43)]
    # A rise swallows a pair that opened on a TOP inside it; the box 80 / 70 of the first chart opened on the
    # rise's own end, and the decline that follows it inside the box began after it: it swallows nothing.
    box = _elect(_chart(_BOX))
    assert box.ends[2]["kind"] == "SC" and box.ends[2]["start_bar"] > box.winner.opening_bar
    assert all(walk.inside_a_live_trend(box.winner, p, box.ends, 99) is None
               for p in box.pairs.values() if p.birth_bar is not None and p.opening_bar > box.winner.opening_bar)


def test_a_spring_under_a_box_that_opened_on_a_top_does_not_unmake_it():
    """Sentence 9, and the other half of his anchor rule. The box 77 / 72 opened on a top, a swing later than the
    climax. A spring to 68 goes under the reaction low and comes back; seen from far it ends a decline that began
    on the climax, before the box opened. A fall says nothing of a pair that opened on a TOP — the top claims the
    rise had ended, and no fall refutes that — so the box stands through the spring, though a pair that opens
    after it is a box by the rules too. The same fall does swallow a pair that opened on a LOW inside it: that
    low claimed the fall had ended."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_SPRING_UNDER_A_LATER_BOX)
    found = _elect(chart, _SPRING_FAR)
    fall = found.ends[2]
    assert (fall["kind"], fall["climax_price"], fall["start_bar"], fall["foot_bar"], fall["known_bar"]) == \
        ("SC", 68.0, 11, 35, 42)
    box, later = found.winner, _pair(found, 76.4, 72.6)
    assert (box.R, box.S, box.top_first, box.opening_bar, box.birth_bar) == (77.0, 72.0, True, 17, 31)
    assert fall["start_bar"] < box.opening_bar < fall["foot_bar"] <= later.opening_bar and later.birth_bar == 52
    assert walk.inside_a_live_trend(box, later, found.ends, chart["n"] - 1) is None
    assert _shown_day_by_day(chart, _SPRING_FAR) == [(77.0, 72.0, 31)]
    low_first = _pair(found, 77.0, 70.0)
    assert not low_first.top_first and fall["start_bar"] < low_first.opening_bar < fall["foot_bar"]
    assert walk.inside_a_live_trend(low_first, later, found.ends, chart["n"] - 1) is fall


def test_a_poke_over_a_box_already_born_does_not_put_it_inside_a_live_trend():
    """His EXPD (drawn Sat 17/10/2026, read Sat 18/10/2026): the box 189.99 / 185.02 (Mon 17/08 and Thu 20/08) was
    a box on Fri 04/09; the poke to 194.59 on Tue 15/09, a range over the top, was back at the support on Fri 18/09,
    and he kept the box through his SOS (Thu 01/10 to Mon 05/10) and his LPS (Tue 06/10 to Thu 08/10). The reader
    hopped to 194.59 / 186.72 on Mon 05/10: the far view called the poke the end of a rise begun on Thu 30/07, before
    the box opened, so the box read as "anchored inside a live trend". Sentences 8 and 9: a run past a rail never
    unmakes a pair, and once a box it stays a box through pokes that come back. A rise whose climax printed AFTER
    the box was born swallows nothing: the box was a box before the price ran past its top. The mirror is NOT
    built: on his WTS the base he drew came after such a fall, and the hand-over to the fall's end is what reaches
    it (measured Sat 18/10/2026: 26 / 10 / 4 on his sealed 40 with the rise side alone, WTS lost with both)."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_POKE_OVER_A_BORN_BOX)
    found = _elect(chart, _POKE_FAR)
    rise = found.ends[1]
    box, poke = _pair(found, 80.0, 70.0), _pair(found, 82.2, 70.6)
    # The far view's rise ends on the poke and began before the box opened; the poke's pair is a box on bar 56.
    assert (rise["kind"], rise["climax_price"], rise["climax_bar"], rise["start_bar"], rise["known_bar"]) == \
        ("BC", 82.2, 41, 3, 48)
    assert (box.opening_bar, box.birth_bar, poke.opening_bar, poke.birth_bar) == (11, 25, 41, 56)
    assert rise["start_bar"] < box.opening_bar < rise["foot_bar"] <= poke.opening_bar and rise["climax_bar"] > box.birth_bar
    # Not by the other rule either: the poke's pair lies across the box, not beyond it.
    assert walk.left_for_good(box, poke, chart["high"], chart["low"], 0, chart["n"] - 1) is None
    # The poke came back: within the fifteen days from its top the bars were back at the box's resistance (bar 43,
    # on the way down) and at its support (bar 44). Judged once, on the last of those days; not before.
    high, low = chart["high"], chart["low"]
    assert walk.poke_came_back(box, high, low, 41, 54) is None
    assert walk.poke_came_back(box, high, low, 41, 55) is True
    # So the box stands: by the bars' geometry alone the rise swallows it, with the bars read it does not.
    assert walk.inside_a_live_trend(box, poke, found.ends, chart["n"] - 1) is rise
    assert walk.inside_a_live_trend(box, poke, found.ends, chart["n"] - 1, high, low) is None
    assert _box(found) == (80.0, 70.0) and len(found.lives) == 1
    assert _shown_day_by_day(chart, _POKE_FAR) == [(80.0, 70.0, 25)]
    # A run that did NOT come back is the rise going on: the pause chart (his VLO) hands over as before, and no
    # sooner than the last of the fifteen days from its top (bar 24 + 14 = 38, the day 80 / 68.5 is a box).
    pause = _chart(_PAUSE_INSIDE_A_RISE)
    found_pause = _elect(pause, _PAUSE_FAR)
    assert walk.poke_came_back(_pair(found_pause, 70.0, 66.0), pause["high"], pause["low"], 24, 38) is False
    assert _shown_day_by_day(pause, _PAUSE_FAR) == [(70.0, 66.0, 22), (80.0, 68.5, 38)]
    # The mirror: the same chart upside down, the box opening on a low after a decline, the "poke" a dip under its
    # support that the far view calls the decline's end. The fall still swallows it (his WTS).
    mirrored = _chart([(bar, 160.0 - price) for bar, price in _POKE_OVER_A_BORN_BOX])
    down = _elect(mirrored, _POKE_FAR)
    low_box, dip = _pair(down, 90.0, 80.0), _pair(down, 89.4, 77.8)
    fall = down.ends[1]
    assert not low_box.top_first and fall["kind"] == "SC" and fall["climax_bar"] > low_box.birth_bar
    assert walk.inside_a_live_trend(low_box, dip, down.ends, mirrored["n"] - 1, mirrored["high"], mirrored["low"]) is fall
    assert _box(down) == (89.4, 77.8) and down.lives[-1].why == walk.LIVE_TREND


def test_a_run_past_the_top_of_a_pair_the_bars_knew_does_not_put_it_inside_a_live_trend():
    """His HCA (the fix of Fri 16/10/2026; his words Sat 24/10/2026: *"hca simply has an earlier pair that provides
    a tighter box leading to more context overall (not that too much was going on in the first place)"*, and of his
    MSGS, where he drew the run's pair: *"it seems almost identical to mine"*). His box 436.14 / 423.43 opened on Fri
    18/09; the run to 446.36 on Wed 23/09, two days after its second anchor and before it was a box, came back, and
    the base went on on his rails to the breakout of Fri 09/10. The reader handed the box to 446.36 / 420.00 as
    "anchored inside a live trend". What sets it apart from the charts where he drew the run's pair (MSGS, ANRO, VLO,
    NOK) or the run's top (ORMP): the bars knew his rails before the pair opened (the August top at 436, the
    September lows at 423), and in the fifteen days from the run's top the bars lived in his box, not over it.
    His "tighter" is true of HCA but separates nothing: on every chart where he drew the run's pair the old box was
    tighter too (measured Sat 24/10/2026), and asking it costs his ACCO."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_RUN_PAST_A_PAIR_THE_BARS_KNEW)
    high, low = chart["high"], chart["low"]
    found = _elect(chart)
    # The box stands through the run, day by day.
    assert _box(found) == (80.0, 70.0) and len(found.lives) == 1
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 37)]
    rise = found.ends[1]
    box, later = _pair(found, 80.0, 70.0), _pair(found, 79.5, 70.5)
    assert (rise["kind"], rise["climax_price"], rise["climax_bar"], rise["start_bar"]) == ("BC", 86.0, 28, 15)
    assert (box.opening_bar, box.second_bar, box.birth_bar, later.opening_bar, later.birth_bar) == (23, 26, 37, 31, 45)
    assert rise["start_bar"] < box.opening_bar < rise["foot_bar"] <= later.opening_bar
    assert box.second_bar < rise["climax_bar"] < box.birth_bar
    # The bars knew its rails: in the thirty days before it opened, a high at its resistance on two bars and a low at
    # its support on three, each within a quarter of a daily range.
    assert walk.knew_the_rails(box, high, low)
    # The run came back to both rails, and the bars' middles sat in the box more often than over it: judged once, on
    # the last of the fifteen days from the run's top (bar 28 + 14).
    assert walk.poke_stayed_in(box, high, low, 28, 41) is None
    assert walk.poke_stayed_in(box, high, low, 28, 42) is True
    # By the bars' geometry alone the rise swallows it; with the bars read it does not.
    assert walk.inside_a_live_trend(box, later, found.ends, chart["n"] - 1) is rise
    assert walk.inside_a_live_trend(box, later, found.ends, chart["n"] - 1, high, low) is None
    # Bars that touch both rails but LIVE over the box (his MSGS): the rise goes on, and takes the place.
    over_high, over_low = high.copy(), low.copy()
    over_high[29:43], over_low[29:43] = 82.0, 80.5
    over_high[35], over_low[35] = 80.0, 70.2
    assert walk.poke_came_back(box, over_high, over_low, 28, 42) is True
    assert walk.poke_stayed_in(box, over_high, over_low, 28, 42) is False
    assert walk.inside_a_live_trend(box, later, found.ends, chart["n"] - 1, over_high, over_low) is rise
    # Bars that stay in the box but never come back to its support: not the box's own poke either.
    shy_high, shy_low = high.copy(), low.copy()
    shy_high[28:43], shy_low[28:43] = 79.0, 72.5
    shy_high[28] = 86.0
    assert walk.poke_came_back(box, shy_high, shy_low, 28, 42) is False
    assert walk.poke_stayed_in(box, shy_high, shy_low, 28, 42) is False
    # Judged on the fifteenth day from the run's top, so the rise takes the place no sooner: a pair that opened on
    # the run's way up (after the rise's foot) and is a box on bar 38 takes it on bar 42, and a reader standing on
    # bar 41 still shows the box (else a later reader would date the hand-over on a day that showed the box).
    from dataclasses import replace
    walked = [t for t in found.ends if t.get("foot_bar") is not None]
    early = replace(later, opening_bar=29, birth_bar=38)
    assert rise["foot_bar"] <= early.opening_bar
    told = walk.lives([box, early], walked, over_high, over_low, chart["n"] - 1)
    assert [(life.pair.R, life.shown_bar) for life in told] == [(80.0, 37), (79.5, 42)]
    assert [life.shown_bar for life in walk.lives([box, early], walked, over_high, over_low, 41)] == [37]
    # The mirror, a fall under a pair the bars knew that came back, is not built (his WTS): the fall swallows it.
    mirrored = _chart([(bar, 160.0 - price) for bar, price in _RUN_PAST_A_PAIR_THE_BARS_KNEW])
    down = _elect(mirrored)
    assert walk.knew_the_rails(_pair(down, 90.0, 80.0), mirrored["high"], mirrored["low"])
    assert down.lives[-1].why == walk.LIVE_TREND and down.lives[-1].trend_end["kind"] == "SC"
    # The same run past a NEW pair (his ALB; his ORMP, where he drew the run's top): the rise takes the place.
    alb = _chart(_RUN_PAST_THE_RAIL)
    assert not walk.knew_the_rails(_pair(_elect(alb), 80.0, 70.0), alb["high"], alb["low"])
    assert _shown_day_by_day(alb) == [(80.0, 70.0, 25), (79.5, 70.5, 33)]


def test_a_box_is_left_only_through_its_far_rail_so_a_spring_that_came_back_never_leaves_it_downward():
    """His DSGX (Sat 18/10/2026), sentences 9 and 10 read together. The box 80 / 70; a spring to 66 on bar 38 touches
    the support of a pair UNDER the box (71 / 66) and comes back in two days; the price then consolidates a step
    higher, 79.3 / 76.2, its highs still at the box's resistance, and one dip (bar 44, 71.9) rests on the lower
    pair's top without reaching the box's support area. On bar 52 the last fifteen days hold both rails of the lower
    pair (38, 44) and no bar at the box's support (the last was bar 37) — and "the bars no longer come back to both
    old rails" said the price had left the box DOWNWARD for good, with the bars at its resistance all the while (bars
    40 and 47). On his DSGX the June box went to a pair below it on Thu 01/10/2026 on exactly this reading, while the
    price stood at 83, over its resistance, and the step pair took the parent's place the next day. Sentence 10 is
    read through the rail the price would have to cross coming back: a box is left UPWARD when the bars no longer
    come back to its support, DOWNWARD when they no longer come back to its resistance. A dip that touched a lower
    pair's rails while the bars still come back to the box's resistance is the box's own dip (sentence 9), and the
    step is the base's own extension (his words: "the price simply continued to consolidate at a higher price ...
    it serves as an extension of the original")."""
    from dataclasses import replace

    from engine_alpha.two_eyes import walk

    chart = _chart(_SPRING_THEN_A_STEP_UP)
    high, low, last = chart["high"], chart["low"], chart["n"] - 1
    found = _elect(chart)
    box, pause = _pair(found, 80.0, 70.0), _pair(found, 71.0, 66.0)
    assert box.birth_bar == 25 and pause.birth_bar == 38
    # The pause pair opened before the box (bar 8), so sentence 10's "newer pair" never means it. His DSGX's lower
    # pair opened eleven days after the box did (12/06 to the box's 01/06): read the pause as if it had, a day after.
    below = replace(pause, opening_bar=12)
    assert walk.lies_beyond(below, box) and below.R <= box.S + box.area and not (below.S >= box.R - box.area)
    # Bar 52: both of the lower pair's rails in the window, the box's support not, its resistance yes.
    window = np.array([52])
    assert walk._back_at_both(below, high, low, 12, window)[0] and not walk._back_at_both(box, high, low, 12, window)[0]
    assert walk._respects(high[38:53], low[38:53], box.R, box.S, box.area)[0].any()
    # The far rail for a pair below is the resistance, which the bars keep coming back to: never left downward.
    assert walk.left_for_good(box, below, high, low, 0, last) is None
    # The mirror, upside down: a box 90 / 80 after a decline, a poke to 94 that touches a pair ABOVE it (94 / 89),
    # then the price steps down with its lows still at the box's support. The far rail for a pair above is the
    # support, which the bars keep coming back to: never left upward.
    mirrored = _chart([(bar, 160.0 - price) for bar, price in _SPRING_THEN_A_STEP_UP])
    down = _elect(mirrored)
    low_box, above = _pair(down, 90.0, 80.0), replace(_pair(down, 94.0, 89.0), opening_bar=12)
    assert walk.lies_beyond(above, low_box) and above.S >= low_box.R - low_box.area
    assert walk.left_for_good(low_box, above, mirrored["high"], mirrored["low"], 0, mirrored["n"] - 1) is None
    # The chart itself: the box stands, read day by day with no memory.
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25)]
    # A box the price really left upward is still left: the breakout chart hands over on bar 49 as before, because
    # the bars no longer come back to the old support, the far rail; and a breakout that came back hands over on bar
    # 58 as before.
    assert _shown_day_by_day(_chart(_BOX_THEN_BREAKOUT)) == [(80.0, 70.0, 25), (94.0, 88.0, 49)]
    assert _shown_day_by_day(_chart(_BREAKOUT_THAT_CAME_BACK)) == [(80.0, 70.0, 25), (94.0, 88.0, 58)]


def test_a_shown_line_moves_back_only_when_a_dip_came_back_read_day_by_day_with_no_memory():
    """Every hand-over goes to a pair that opened later — but the one that gives a box its place back after a dip
    — and each is judged on what its own day knew: a reader with no memory, standing on any day, tells the same
    history up to that day as one standing later — also when the trend end that takes a box's place is known
    only after the newer pair is a box (the pause chart with the far view that sees the rise end late)."""
    from engine_alpha.two_eyes import walk

    came_back = 0
    for points, far in ((_BOX, None), (_RUN_PAST_THE_RAIL, None), (_BOX_THEN_BREAKOUT, None),
                        (_BREAKOUT_THAT_CAME_BACK, None), (_BOX_WITH_POKES, None), (_PAUSE_INSIDE_A_RISE, _PAUSE_FAR),
                        (_PAUSE_INSIDE_A_RISE, _PAUSE_FAR - {30, 33, 36, 39}),
                        (_SPRING_UNDER_A_LATER_BOX, _SPRING_FAR), (_OUTER_PAIR_RESPECTED_LATE, None),
                        (_DIP_THAT_CAME_BACK, None), (_SPRING_INTO_THE_BOX_UNDER_IT, None),
                        (_RUN_ABOVE_THEN_UNDER_THE_BOX, None), (_RUN_PAST_A_PAIR_THE_BARS_KNEW, None)):
        chart = _chart(points)
        last = _elect(chart, far)
        told = [(life.pair.feet, life.shown_bar) for life in last.lives]
        came_back += sum(1 for life in last.lives if life.why == walk.CAME_BACK)
        for day in range(chart["n"]):
            on_day = _elect(chart, far, read_bar=day)
            assert [(life.pair.feet, life.shown_bar) for life in on_day.lives] == [t for t in told if t[1] <= day], day
            opens = [life.pair.opening_bar for life in on_day.lives if life.why != walk.CAME_BACK]
            assert opens == sorted(set(opens)), f"the shown line moved back by bar {day}"
    assert came_back == 1       # the dip chart, once: no other chart of these gives a place back


def test_an_earlier_pair_that_becomes_a_box_later_never_takes_the_shown_boxs_place():
    """OURS, not his: a pair that opened earlier does not take the shown box's place on the day it becomes a box.
    The climax and its reaction (80 / 70) is a box only on bar 49, when the bars are at last back at its
    resistance (bar 40) and then at its support; by then the reader has shown the pair to its right (76 / 70) for
    three weeks, and it stays. Measured on his 37 on Thu 01/10/2026, taking the earlier pair that day (in three
    forms) put old wide pairs in the place of his own box on EGBN, NTCT and ST, or moved DRTS to the first
    reaction low; the one way back that is built gives a box its place back after a dip (the test below)."""
    chart = _chart(_OUTER_PAIR_RESPECTED_LATE)
    found = _elect(chart)
    outer, shown = _pair(found, 80.0, 70.0), found.winner
    assert (outer.opening_bar, outer.r_back, outer.s_back, outer.birth_bar, outer.unfit) == (11, 40, 49, 49, None)
    assert (shown.R, shown.S, shown.opening_bar, shown.top_first, shown.birth_bar) == (76.0, 70.0, 14, False, 28)
    assert len(found.lives) == 1
    assert _shown_day_by_day(chart) == [(76.0, 70.0, 28)]
    # The day before the outer pair is a box, and the day it is one: the same box shown.
    assert _box(_elect(chart, read_bar=48)) == _box(_elect(chart, read_bar=49)) == (76.0, 70.0)
    assert _pair(_elect(chart, read_bar=48), 80.0, 70.0).birth_bar is None


def test_the_climax_and_its_reaction_take_the_place_of_a_lower_sibling_shown_before_them():
    """His GFR (Thu 16/10/2026): "the AR ended where I marked it (the red swing) the entire wave going down is
    already 2 swings and it's not part of the AR". Sentence 5: the first pair tried is the climax and its
    reaction; one pair to the right only if the bars do not come back to both rails. Two pairs off the SAME
    opening anchor: the lower sibling (80 / 65.6) is a box first, on bar 28, and is shown; on bar 30 the bars are
    back at the reaction low too, the climax and its reaction (80 / 70) is a box, and it takes the place: it was
    tried before the pair to its right. Read day by day with no memory. A pair that opened on ANOTHER anchor
    still never comes back (the test below: his ROIV)."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_REACTION_ANSWERED_AFTER_A_LOWER_SIBLING)
    found = _elect(chart)
    lower, reaction = _pair(found, 80.0, 65.6), _pair(found, 80.0, 70.0)
    assert (lower.opening_bar, lower.birth_bar) == (11, 28) and (reaction.opening_bar, reaction.birth_bar) == (11, 30)
    assert _box(found) == (80.0, 70.0)
    assert found.lives[-1].why == walk.TRIED_FIRST and found.lives[-2].pair.feet == lower.feet
    assert _shown_day_by_day(chart)[-2:] == [(80.0, 65.6, 28), (80.0, 70.0, 30)]
    # The record says why, and the lower sibling stays in it as an earlier box.
    boxes, trail, _ = walk.record(found)
    assert [(b.resistance.price, b.support.price, b.role) for b in boxes[-2:]] == [(80.0, 65.6, "earlier"), (80.0, 70.0, "parent")]
    assert any("tried before it" in step.saying for step in trail if step.stage == "hand-over")


def test_a_dip_that_comes_back_gives_the_box_its_place_back():
    """Sentence 9 — "Once a box, it stays a box through dips under support ... that come back" — and his word on
    the five boxes the reader never went back to (Thu 01/10/2026): "go ahead with the five earlier boxes I think
    as long as the engine understand that there is a setup there I'm happy". The reader reads day by day: on
    bar 49 the lower pair is a box and no bar has been back at the old rails, so it follows the price down. By
    bar 57 the bars since that day have been back at both rails of the box it gave up, and on bar 68 the last
    fifteen days hold no bar at the dip pair's support any more (its last was bar 53): the dip came back, and the
    box takes its place back that day - the way back is a hand-over, judged by both halves of his sentence 10
    (his STGW, Fri 23/10/2026). Read with no memory, every day tells the same history."""
    from engine_alpha.two_eyes import walk, record

    chart = _chart(_DIP_THAT_CAME_BACK)
    high, low, last = chart["high"], chart["low"], chart["n"] - 1
    found = _elect(chart)
    box, dip, again = found.lives
    assert (box.pair.R, box.pair.S, box.shown_bar, box.ended_bar) == (80.0, 70.0, 25, 35)
    assert (dip.pair.R, dip.pair.S, dip.shown_bar, dip.why) == (68.0, 62.0, 49, walk.LEFT_FOR_GOOD)
    assert dip.pair.R <= box.pair.S + box.pair.area                      # it rests on the old support's area
    assert (again.pair.feet, again.shown_bar, again.why, again.ended_bar) == (box.pair.feet, 68, walk.CAME_BACK, None)
    assert dip.ended_bar == dip.pair.second_bar == 38                    # its lines never ran on
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (68.0, 62.0, 49), (80.0, 70.0, 68)]
    # The day itself: the first on which the bars SINCE the box was given up, and of the last fifteen days, were
    # back at both its rails — at its support on bar 55, at its resistance on bar 57 — and no longer at the dip
    # pair's support (bar 53, out of the fifteen-day window on bar 68).
    assert walk.came_back_to(box.pair, dip.pair, high, low, 49, last) == 68
    assert walk.came_back_to(box.pair, dip.pair, high, low, 49, 67) is None
    on_r, on_s = walk._respects(high, low, 80.0, 70.0, box.pair.area)
    assert not on_r[36:57].any() and on_r[57] and not on_s[33:55].any() and on_s[55]
    at_dip_s = walk._respects(high, low, 68.0, 62.0, dip.pair.area)[1]
    assert at_dip_s[53] and not at_dip_s[54:].any()
    # Only the bars AFTER the day asked from count, on both halves: asked from bar 54, the bar at the dip pair's
    # support on bar 53 is not the price still there, and the box is back on bar 57; asked from bar 55, the bar at
    # the support that day is not the price coming back, and the next one at the support is bar 60.
    assert walk.came_back_to(box.pair, dip.pair, high, low, 54, last) == 57
    assert walk.came_back_to(box.pair, dip.pair, high, low, 55, last) == 60
    # ... and both rails within fifteen days of each other: on quiet bars in the middle of the box, one at the
    # resistance on bar 2 and one at the support on bar 20 are no come-back; with the next bar at the resistance,
    # bar 22, they are.
    quiet_high, quiet_low = np.full(30, 75.2), np.full(30, 74.8)
    quiet_high[[2, 22]], quiet_low[20] = (79.5, 79.6), 70.4
    assert walk.came_back_to(box.pair, dip.pair, quiet_high, quiet_low, 0, 29) == 22
    # The record keeps what each night showed, and says why: the dip pair as an earlier box whose lines never ran
    # on, the box again as the parent.
    boxes, trail, _ = walk.record(found)
    assert [(b.resistance.price, b.support.price, b.role) for b in boxes] == [
        (80.0, 70.0, record.ROLE_EARLIER), (68.0, 62.0, record.ROLE_EARLIER), (80.0, 70.0, record.ROLE_PARENT)]
    assert [s.stage for s in trail[:2]] == ["hand-over", "hand-over"]
    assert "below" in trail[0].saying and "came back to both rails" in trail[1].saying
    assert "80.00 / 70.00 took its place again" in trail[1].saying and f"{_day(68):%a %d/%m/%Y}" in trail[1].saying
    # No memory: every day tells the history the last day tells of it.
    told = [(life.pair.feet, life.shown_bar) for life in found.lives]
    for day in range(chart["n"]):
        assert [(life.pair.feet, life.shown_bar) for life in _elect(chart, read_bar=day).lives] == \
            [t for t in told if t[1] <= day], day


def test_the_box_given_up_takes_its_place_back_only_as_it_was_lost_so_a_run_through_the_pair_above_leaves_the_box_standing():
    """His STGW (Fri 23/10/2026): the box 8.96 / 8.47 from the selling climax to the automatic rally; the pair
    above it, 9.40 / 8.93 of early August, had been left downward. The breakout of Tue 13/10 ran to 9.64 through
    that old pair, and the next day the reader gave the old pair the box's place back ("the dip came back") off that
    one run, with the bars resting on the box's top: his six-day LPS on the box's resistance read as "lines, no LPS
    yet" against rails 9.40 / 8.93. OURS: the way back is a hand-over, judged as every hand-over is, by both halves of
    his sentence 10 - the bars are back at both rails of the box given up AND no longer come back to the shown
    pair's far rail (its support, the box lying above it; ``far_rail``). Here the dip pair's support was touched on
    bar 53: the box stands through the run and the rest, and takes its place back on bar 68, the first day fifteen
    days hold no bar at that support. The dip chart, whose dip pair's support was last touched on bar 53 too,
    tells the same: the box is back on bar 68, not 57. Read with no memory, every day tells the same history."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_RUN_THROUGH_THE_PAIR_ABOVE)
    high, low, last = chart["high"], chart["low"], chart["n"] - 1
    found = _elect(chart)
    box, dip, again = found.lives
    assert (box.pair.R, box.pair.S, box.shown_bar, box.ended_bar) == (80.0, 70.0, 25, 35)
    assert (dip.pair.R, dip.pair.S, dip.shown_bar, dip.why) == (68.0, 62.0, 49, walk.LEFT_FOR_GOOD)
    assert (again.pair.feet, again.shown_bar, again.why) == (box.pair.feet, 68, walk.CAME_BACK)
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (68.0, 62.0, 49), (80.0, 70.0, 68)]
    # The bars are back at both rails of the old pair by bar 59 - and the dip pair's support is still in the window.
    on_r, on_s = walk._respects(high, low, 80.0, 70.0, box.pair.area)
    assert on_r[57] and on_s[59] and not on_r[50:57].any()
    at_dip_s = walk._respects(high, low, 68.0, 62.0, dip.pair.area)[1]
    assert at_dip_s[53] and not at_dip_s[54:].any()
    assert walk.far_rail(box.pair, dip.pair) == walk.SUPPORT
    for day in range(59, 68):
        assert walk.came_back_to(box.pair, dip.pair, high, low, 49, day) is None, day
    assert walk.came_back_to(box.pair, dip.pair, high, low, 49, 68) == 68
    assert walk.came_back_to(box.pair, dip.pair, high, low, 49, last) == 68
    # No memory: every day tells the history the last day tells of it.
    told = [(life.pair.feet, life.shown_bar) for life in found.lives]
    for day in range(chart["n"]):
        assert [(life.pair.feet, life.shown_bar) for life in _elect(chart, read_bar=day).lives] == \
            [t for t in told if t[1] <= day], day


def test_the_box_given_up_comes_before_a_pair_that_would_take_the_place_the_same_day():
    """OURS, and it matters on his charts (eleven of the 53 have such a day in their two years: PBT, RGR, SILC,
    SYRE, UNF among them). On bar 70 the pair above the dip pair (76 / 72) is a box, the bars hang on it and have
    not been back at the dip pair: it would take the dip pair's place. The same day the bars are back at both
    rails of the box the reader gave up. The dip came back: the box takes its place back first, and the pair
    inside it is its own leg."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_DIP_BACK_THE_DAY_A_PAIR_ABOVE_IS_A_BOX)
    high, low, last = chart["high"], chart["low"], chart["n"] - 1
    found = _elect(chart)
    box, dip, shelf = _pair(found, 80.0, 70.0), _pair(found, 68.0, 62.0), _pair(found, 76.0, 72.0)
    assert shelf.birth_bar == 70 and shelf.S >= dip.R - dip.area and shelf.R < box.R and shelf.S > box.S
    assert walk.left_for_good(dip, shelf, high, low, 49, last) == 70 == walk.came_back_to(box, dip, high, low, 49, last)
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (68.0, 62.0, 49), (80.0, 70.0, 70)]
    assert found.lives[-1].why == walk.CAME_BACK and len(found.lives) == 3


def test_a_fall_back_into_the_box_under_it_is_the_newer_boxs_own_dip():
    """OURS, measured on his drawings: the place is given back only after a DIP. When the price left a box upward
    and a box above took its place, a fall back into the old box is the newer box's own dip — his ST, where the
    spring under his box is at both rails of the box under it (giving the place back there loses his box and
    silences the fire on his day). The bars are back at both rails of the old box on bar 58, and the box above
    stands."""
    from engine_alpha.two_eyes import walk

    chart = _chart(_SPRING_INTO_THE_BOX_UNDER_IT)
    found = _elect(chart)
    old, above = found.lives
    assert (old.pair.R, old.pair.S) == (80.0, 70.0) and (above.pair.R, above.pair.S, above.shown_bar) == (94.0, 88.0, 49)
    assert above.why == walk.LEFT_FOR_GOOD and above.pair.S >= old.pair.R - old.pair.area
    assert walk.came_back_to(old.pair, above.pair, chart["high"], chart["low"], 49, chart["n"] - 1) == 58
    assert _shown_day_by_day(chart) == [(80.0, 70.0, 25), (94.0, 88.0, 49)]


def test_the_record_carries_the_box_its_trail_and_the_state_and_keep_listing_adds_words_only():
    from engine_alpha.two_eyes import walk, record

    chart = _chart(_BOX)
    found = _elect(chart, read_bar=34)
    boxes, trail, state = walk.record(found)
    assert state == "lines, no LPS yet"
    box = boxes[0]
    assert (box.resistance.price, box.support.price) == (80.0, 70.0)
    assert (box.resistance.anchor_day, box.support.anchor_day) == (_day(11), _day(14))
    assert box.opened_day == _day(11) and box.daily_range == 2.0 and box.role == record.ROLE_PARENT
    assert box.end_day is None
    # The trail to the box: the trend end it follows, then the pair, in words a page can print.
    assert [s.stage for s in trail] == ["trend end", "box"]
    assert "the end of a rise: its climax 80.00" in trail[0].saying
    for words in ("R 80.00", "S 70.00", "opens on resistance", "a box on", "its fifteenth day",
                  f"came back to resistance {_day(17):%a %d/%m/%Y}", f"to support {_day(20):%a %d/%m/%Y}"):
        assert words in trail[1].saying, words
    # Keep listing: every other pair listed from that trend end on, added after the trail; nothing else changes.
    more_boxes, more_trail, more_state = walk.record(found, keep_listing=True)
    assert (more_boxes, more_state) == (boxes, state) and more_trail[:len(trail)] == trail
    others = [p for p in found.pairs.values() if p.opening_bar >= 11 and p.feet != found.winner.feet]
    assert [s.stage for s in more_trail[len(trail):]] == ["listed"] * len(others) and len(others) >= 5
    assert any("never a box: the counter move took back the whole move before it" in s.saying for s in more_trail)
    assert any("not a box yet" in s.saying for s in more_trail)
    # No trend end at all: no lines. A trend end and no box yet: no lines, the trend end on the trail.
    assert walk.record(_elect(chart, read_bar=5)) == ((), (), record.NO_LINES)
    boxes, trail, state = walk.record(_elect(chart, read_bar=24))
    assert (boxes, state) == ((), record.NO_LINES) and [s.stage for s in trail] == ["trend end"]


def test_read_fills_the_record_from_the_walk():
    """The read is the walk's record, then the mini (a second box inside the parent's right side, LAST in the
    boxes, its one step: task 13), then stage 6 on the box it shows (the LPS, its step after the walk's trail,
    and the state word: task 12a), then the story's one step and its events (stage 5, task 12b), then the grade's
    one step and the grade (stage 7, task 14), which change neither the boxes, the LPS nor the state word."""
    from engine_alpha import two_eyes
    from engine_alpha import two_eyes_numbers as M
    from engine_alpha.two_eyes import (frame as frame_module, grade, line as line_module, lps, mini, story, walk)
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    # The first frame: the loader sorts the setups, so it is the same one on every run (it came out of a set
    # before, and the chain below, which reads the LPS against the parent alone, met NKTR's mini-after-pullback
    # read one CI run in twenty, Fri 17/10/2026; that branch is pinned by name at the end).
    key, raw = next(iter(frames.items()))
    assert key == sorted(frames)[0]
    read = two_eyes.read(key, raw)
    assert read.failed is False
    prepared = frame_module.prepare(raw)
    line = line_module.build(prepared)
    ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    days = tuple(d.date() for d in prepared.index)
    result = walk.elect(line.committed, [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES) if t.committed], ranges,
                        high, low, days=days, read_bar=len(prepared) - 1)
    boxes, trail, state = walk.record(result)
    assert state == "lines, no LPS yet"
    won = result.winner
    inner = mini.find(result, high, low, len(prepared) - 1, ranges=ranges) if M.MINI_ENABLED else ()
    if inner:
        mini_box, mini_step = mini.record(result, inner)
        boxes, trail = boxes + (mini_box,), trail + (mini_step,)
    pullback = lps.read(high, low, ranges, line.committed, R=won.R, S=won.S, box_unit=won.unit,
                        born_bar=won.birth_bar)
    the_lps, said, word = lps.record(pullback, days, read_bar=len(prepared) - 1)
    events = story.read(line.turns, high, low, days, start_bar=won.opening_bar, R=won.R, S=won.S, unit=won.unit,
                        read_bar=len(prepared) - 1, pullback=pullback,
                        trend_end_bar=(result.lives[-1].trend_end or {}).get("climax_bar"))
    told = story.record(events)
    graded = grade.read(high, low, days, line.committed, events, R=won.R, S=won.S, unit=won.unit,
                        opening_bar=won.opening_bar, read_bar=len(prepared) - 1)
    from engine_alpha.two_eyes import state as state_word
    final, beside = state_word.decide(result, word, high, low, len(prepared) - 1)
    assert (read.boxes, read.lps, read.trail, read.state) == \
        (boxes, the_lps, trail + said + told + grade.record(graded), final)
    from dataclasses import replace

    assert read.state_days == beside and replace(read.grade, clarity=None) == graded
    assert read.grade.clarity["facts"]["base_start"] == days[won.opening_bar].isoformat()
    assert read.events == events and [s.stage for s in told] == [story.STAGE]
    assert read.parent is not None and len(said) == 1 and word in (lps.FIRED, lps.CROSSED, lps.LINES_NO_LPS)
    # The LPS against the mini (task 13) when the mini became a box only after the pullback ended: the read says
    # so in a step of its own and reads the LPS against the parent. The chain above does not model it; NKTR does.
    # (Its LPS record is None on this day: the parent's read is what stands, the step is the pin.)
    # Pinned only with the mini on: with the stage sunset (MINI_ENABLED off) there is no such step.
    nktr = next((k for k in frames if k.startswith("NKTR:")), None)
    if nktr is not None and M.MINI_ENABLED:
        later = two_eyes.read(nktr, frames[nktr])
        assert later.failed is False
        assert any(s.stage == "LPS" and "became a box only" in s.saying for s in later.trail), later.trail


# --------------------------------------------------------------------------- #
# His drawings and the fixture charts                                         #
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


def _walk_on(prepared, read_bar=None):
    """The walk on a prepared frame as a reader standing on ``read_bar`` has it (the last bar by default), and
    the same read for any earlier day."""
    from engine_alpha import two_eyes_numbers as M
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, walk

    line = line_module.build(prepared)
    ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    far = line.far(M.FAR_VIEW_FLOOR_RANGES)

    def on(day: int):
        return walk.elect(walk.known_by(line.turns, day), walk.known_by(far, day), ranges, high, low, read_bar=day)

    return on(len(prepared) - 1 if read_bar is None else read_bar), on


@pytest.fixture(scope="module")
def his_reads() -> list:
    """Each of his drawings read on his last receding day and on his buy day, with his own pair as the reader
    measures a pair (None when his two anchors are not two swing ends a swing connects)."""
    from engine_alpha.two_eyes import frame as frame_module
    from tools.calibration.yardstick import his_last_lps_day
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    out = []
    for setup in load_corpus():
        raw = fixture_frame(frames, setup_key(setup), setup["ticker"])
        prepared = frame_module.prepare(raw.loc[:pd.Timestamp(setup["as_of"])])
        days = [d.date() for d in prepared.index]
        r_bar = days.index(dt.date.fromisoformat(setup["anchors"]["R"]))
        s_bar = days.index(dt.date.fromisoformat(setup["anchors"]["S"]))
        last = days.index(his_last_lps_day(setup))
        # His buy day: every one of his drawings buys the trading day after his last receding day.
        # A mark drawn on its last receding day is frozen on a frame that ends there: its buy is past the frame.
        buy_day = dt.date.fromisoformat(str(setup["trigger"])[:10]) if setup.get("trigger") else None
        buy = min(days.index(buy_day) if buy_day in days else len(days) - 1, len(days) - 1)
        _, on = _walk_on(prepared)
        result, on_buy = on(last), on(buy)
        rails = setup["rails_drawn"]
        his_pair = next((p for p in on_buy.pairs.values() if (p.r_bar, p.s_bar) == (r_bar, s_bar)
                         and abs(p.R - rails["R"]) < 0.005 and abs(p.S - rails["S"]) < 0.005), None)
        out.append({"setup": setup, "key": setup_key(setup), "days": days, "prepared": prepared, "on": on,
                    "high": prepared["High"].to_numpy(dtype=float), "low": prepared["Low"].to_numpy(dtype=float),
                    "ranges": prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float),
                    "r_bar": r_bar, "s_bar": s_bar, "first_bar": min(r_bar, s_bar), "last_bar": last,
                    "buy_bar": buy, "result": result, "on_buy": on_buy, "his_pair": his_pair})
    assert len(out) == 52      # the population follows his drawings (his ruling, Tue 08/09/2026)
    return out


#: The plan's named charts among his drawings, and PBT, whose box he ruled on at the core sitting: the reader's
#: box on his last receding day is his pair, to the cent. Those it still reads otherwise are pinned as expected
#: failures, strictly, each with its reason, so the day one passes it is a red test and the pin moves.
_NAMED = ("VIK:2026-06-11", "SYRE:2026-02-19", "EWTX:2026-03-31", "NGL:2026-04-20", "VLO:2026-07-08",
          "PBT:2026-05-11",
          # His words on the pictures (Thu 01/10/2026): "Silc supposed to work due the much respect of the
          # support". And ST, the plan's named chart, reads his box with it.
          "SILC:2026-04-13", "ST:2026-04-17",
          pytest.param("ALB:2026-04-13", marks=pytest.mark.xfail(strict=True, reason=(
              "his box is the top of Thu 15/01/2026 and its reaction (179.10 / 160.02), his option 1. The reader "
              "shows it from Wed 04/02/2026 (on 179.14, the high of the day before his, four cents over) and, "
              "from Thu 26/02/2026, 182.80 (Thu 12/02/2026) / 156.04 (Thu 05/02/2026): the low of the crash that "
              "followed the run to 195.69 and the top after it, the far view saying the fall ended on that low. "
              "Both lines are within half a range of his. His word of Thu 01/10/2026: \"even a later pair could "
              "work if that movement in 20/1 -> 27/1 and the crash afterwards could be treated as the place where "
              "the trend ends\""))),
          pytest.param("FOSL:2026-02-18", marks=pytest.mark.xfail(strict=True, reason=(
              "his box is one wide bar three weeks into the base (4.00 / 3.61, Fri 26/12/2025); the reader shows "
              "the pair of the top before it, 4.13 (Fri 05/12/2025) / 3.61 (Mon 08/12/2025), a box that same Fri "
              "26/12/2025: the same support price and a resistance within half a range of his; his bar lies inside "
              "it"))),
          # MSGS as he redrew it on Sat 10/10/2026 (345.48 / 325.27 from Wed 15/04/2026) is the pair the reader shows,
          # to the cent; before the redraw his support was the climax bar's own low and his pair was not listed.
          "MSGS:2026-05-22",
          pytest.param("ROIV:2026-06-17", marks=pytest.mark.xfail(strict=True, reason=(
              "his box as he redrew it on Thu 01/10/2026 is the top of the climb and its reaction (30.33, Wed "
              "11/03/2026 / 27.92, Fri 13/03/2026). The reader shows the pair one swing before it, 30.03 (Thu "
              "05/03/2026) / 28.31 (Fri 06/03/2026), the first the bars came back to: both lines within half a "
              "daily range of his. It gave it up to the dip's own pair on Fri 10/04/2026 and took it back on Tue "
              "14/04/2026, the dip having come back. His own pair is a box by the rule only on Thu 23/04/2026 and "
              "lies around the shown one, so it never takes its place"))))


@pytest.mark.parametrize("key", _NAMED)
def test_the_named_charts_read_his_pair_to_the_cent(his_reads, key):
    row = next(r for r in his_reads if r["key"] == key)
    rails, winner = row["setup"]["rails_drawn"], row["result"].winner
    assert winner is not None, f"{key}: no box on his last receding day"
    assert (round(winner.R, 2), round(winner.S, 2)) == (round(rails["R"], 2), round(rails["S"], 2)), \
        f"{key}: the engine's box is {winner.R:.2f} / {winner.S:.2f}, his {rails['R']:.2f} / {rails['S']:.2f}"


@pytest.mark.xfail(strict=True, reason="a junk chart the plan names with the lines 57.76 / 53.89; the reader's box on "
                                       "the frame's last day is 55.05 / 52.20, the pair before it")
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


def _a_swings_end(values, bar: int, last: int, top: bool) -> bool:
    """His "the High point of a previous swing" (Mon 28/09/2026), by bars alone: a bar's high is the end of a swing
    up when the bar on neither side beats it (the mirror for a low). A bar after the read day is not read."""
    sign = 1.0 if top else -1.0
    if bar > 0 and sign * values[bar - 1] > sign * values[bar]:
        return False
    return not (bar + 1 <= last and sign * values[bar + 1] > sign * values[bar])


def _came_from_beyond(row, first_bar: int, opens_on_resistance: bool, R: float, S: float, days: int = 10) -> bool:
    """The swing before the box ran INTO its first line: within ``days`` trading days before a box that opens
    on its resistance the price was under its support (above its resistance, for one that opens on support)."""
    before = slice(max(0, first_bar - days), first_bar)
    if opens_on_resistance:
        return bool(row["low"][before].min() < S)
    return bool(row["high"][before].max() > R)


#: His one resistance anchor that is no swing's end by the bar on either side, and why.
_HIS_RESISTANCE_NOT_AN_END = {
    "ALB:2026-04-13": "the second of two highs four cents apart: 179.14 on Wed 14/01/2026, 179.10 the day after",
    # His two ANET drawings share the line: the shelf the bars kept coming back to, not the spike the swing ended on.
    "ANET:2026-09-25": "his resistance (198.92, Tue 11/08/2026) is a top inside the fall from the spike of Wed "
                       "05/08/2026 (214.89); the swing ended on the spike",
    "ANET:2026-10-02": "the same line as his drawing of Fri 25/09/2026",
}
#: His two support anchors that are no swing's end by the bar on either side, and why (his drawings, to the cent).
#: His one box whose first line the swing before it never ran into (drawn Fri 30/10/2026): DDI's first, one wide
#: bar (Thu 04/06/2026, 11.86 / 11.32) opening on its support; the rise before it ended inside the bar, over the line.
_HIS_BOX_NOT_FROM_BEYOND = ("DDI:2026-08-10",)
_HIS_SUPPORT_NOT_AN_END = {
    # MSGS left this list with his redraw of Sat 10/10/2026 (its support 325.27, Thu 16/04/2026, is a swing's end).
    "PKE:2026-04-07": "the first of two lows ten cents apart: 26.30 on Fri 06/03/2026, 26.20 the day after",
    "DDI:2026-09-30": "his box is one wide bar (Fri 14/08/2026, 13.05 / 12.58) and the move off its top ran on to "
                      "12.41 the next day, so the bar's own low is no swing's end",
}


def test_his_own_drawings_keep_his_rule_of_the_end_points(his_reads):
    """His ruling of Mon 28/09/2026, measured on his own drawings by bars alone, no reader in the way: each of
    his lines sits on a swing's end (every resistance anchor but the one named; every support anchor but the
    two named), and every one of his boxes opens on the END of the swing before it, the other line on the counter
    move — 37 on resistance after a rise, 3 on support after a fall."""
    opens_on_support = []
    for row in his_reads:
        setup, days, highs, lows = row["setup"], row["days"], row["high"], row["low"]
        R, S = float(setup["rails_drawn"]["R"]), float(setup["rails_drawn"]["S"])
        r_bar, s_bar = row["r_bar"], row["s_bar"]
        assert abs(highs[r_bar] - R) < 0.005 and abs(lows[s_bar] - S) < 0.005, f"{row['key']}: not a bar's own end"
        assert _a_swings_end(highs, r_bar, len(days) - 1, top=True) == \
            (row["key"] not in _HIS_RESISTANCE_NOT_AN_END), f"{row['key']}: his resistance"
        assert _a_swings_end(lows, s_bar, len(days) - 1, top=False) == (row["key"] not in _HIS_SUPPORT_NOT_AN_END), \
            f"{row['key']}: his support"
        assert _came_from_beyond(row, min(r_bar, s_bar), r_bar <= s_bar, R, S) == \
            (row["key"] not in _HIS_BOX_NOT_FROM_BEYOND), \
            f"{row['key']}: the swing before his box did not run into his first line"
        if s_bar < r_bar:
            opens_on_support.append(row["key"])
    # His 52 (Fri 30/10/2026): ANET (both drawings), CLOV and VTMX open on the support too; TWLO's top
    # (Fri 28/08/2026) comes before its low (Wed 02/09/2026).
    assert sorted(opens_on_support) == ["ANET:2026-09-25", "ANET:2026-10-02", "AVT:2026-04-08", "CLOV:2026-10-27",
                                        "JAZZ:2026-02-24", "SKYT:2026-04-13", "VTMX:2026-10-02"]


#: His root swings that took longer than four trading days: none, since he redrew ROIV on Thu 01/10/2026 (its
#: support had been the second low after his top, seven days on; "Sorry Roiv was wrong"). Before the redraw:
#: ROIV's support is the second low
#: after his top ("one line can stay on its anchor while the other moves", Sun 20/09/2026).
_HIS_SLOW_COUNTER_MOVE = {}
#: His one box under the reader's floor of one daily range (drawn Fri 30/10/2026): VTMX, 34.77 / 33.79, is 0.98 points
#: in a 1.18 daily range. No pair on his lines can be a box for the reader there; the box it shows is 35.02 / 32.01.
_HIS_BOX_UNDER_A_RANGE = {"VTMX:2026-10-02": 0.83}
#: His box the price went on past (its first line, by more than the area) BEFORE the bars were back on both lines,
#: and his boxes the price stood well over (1.25 daily ranges and more) in their first fifteen days, in daily
#: ranges. He kept all of them: a run past a rail never unmakes a pair by itself (sentence 8). On ALB he said the
#: breach "is not an upthrust in fact there is a later on 25/02/2026 its just that those pairs could be used to fit
#: the box" (Thu 01/10/2026). NET, drawn by him that evening, is the third: the price ran on over his resistance of
#: Wed 05/08/2026 (305.00) for seven days, to 332.22 on Thu 13/08/2026, before a bar came back to either line.
#: VTMX (Fri 30/10/2026) is the fourth: the price went on under his support (33.79) before the bars were back on both.
_HIS_FIRST_LINE_PASSED_FIRST = ("ALB:2026-04-13", "NET:2026-09-15", "VTMX:2026-10-02")
_HIS_EARLY_RUN_PAST_RESISTANCE = {"ALB:2026-04-13": 2.04, "MTLS:2026-09-04": 2.20, "NET:2026-09-15": 1.80,
                                  "DDI:2026-08-10": 1.26}     # his first DDI (Fri 30/10/2026): the July run


def _first_bar(values, line: float, area: float, start: int, stop: int, how: str):
    """The first bar from ``start`` to ``stop`` whose high (low) is ``how`` against a line: "near" within the
    line's area on either side, "over" beyond the area upward, "under" beyond it downward. None when none is."""
    for bar in range(start, stop + 1):
        gap = float(values[bar]) - line
        if (how == "near" and abs(gap) <= area) or (how == "over" and gap > area) or (how == "under" and gap < -area):
            return bar
    return None


def test_his_own_drawings_say_how_the_root_swing_behaves(his_reads):
    """What his drawings say of the root swing and of the days after it, by bars alone, no reader in the way
    (measured Tue 29/09/2026 on his words "check all of the calibrated Setups and maybe see what I chose"). The
    counter move is quick and at least a daily range tall: its end is within four trading days of the first
    anchor on every drawing. The bars come back to BOTH his lines (a bar's high within the area
    of his resistance, a bar's low within the area of his support) on every one. They do so before the price goes
    on past his FIRST line on 38 of 40, and in the box's first fifteen days the price is 1.25 ranges or more over
    his resistance on 3: both are TENDENCIES with his own exceptions named, never a rule that drops a pair. Under
    his support it dips more than a full range on eleven (VTMX, drawn Fri 30/10/2026, the eleventh), and he kept
    the line."""
    from engine_alpha import two_eyes_numbers as M

    slow, deep, passed_first, ran_past = {}, [], [], {}
    for row in his_reads:
        setup, days, key, highs, lows = row["setup"], row["days"], row["key"], row["high"], row["low"]
        R, S = float(setup["rails_drawn"]["R"]), float(setup["rails_drawn"]["S"])
        r_bar, s_bar = row["r_bar"], row["s_bar"]
        first, second, last = min(r_bar, s_bar), max(r_bar, s_bar), len(days) - 1
        unit = float(row["ranges"][second])
        area = float(M.LINE_WORD_AREA_ATR) * unit
        if second - first > 4:
            slow[key] = second - first
        if key in _HIS_BOX_UNDER_A_RANGE:
            assert (R - S) / unit == pytest.approx(_HIS_BOX_UNDER_A_RANGE[key], abs=0.01)
            assert (R - S) / unit < float(M.BOX_MIN_HEIGHT_RANGES)
        else:
            assert float(M.BOX_MIN_HEIGHT_RANGES) <= (R - S) / unit <= 3.5, f"{key}: {(R - S) / unit:.2f} ranges tall"
        r_back = _first_bar(highs, R, area, second + 1, last, "near")
        s_back = _first_bar(lows, S, area, second + 1, last, "near")
        assert r_back is not None and s_back is not None, f"{key}: the bars never came back to both his lines"
        past = (_first_bar(highs, R, area, second + 1, last, "over") if r_bar <= s_bar else
                _first_bar(lows, S, area, second + 1, last, "under"))
        if past is not None and max(r_back, s_back) > past:
            passed_first.append(key)
        young = slice(second + 1, first + int(M.BOX_DAYS))
        over = (float(highs[young].max()) - R) / unit
        if over >= 1.25:
            ran_past[key] = round(over, 2)
        if (S - float(lows[young].min())) / unit > 1.0:
            deep.append(key)
    assert slow == _HIS_SLOW_COUNTER_MOVE
    assert tuple(passed_first) == _HIS_FIRST_LINE_PASSED_FIRST
    assert ran_past == _HIS_EARLY_RUN_PAST_RESISTANCE
    assert len(deep) == 11, deep


#: His drawings whose own pair the rule does not list, and why: on each, one of his anchors is not the end of the
#: swing by the reader's line, or no swing connects the two. On all five the reader's box is within half a daily
#: range of his, but ALB's (the test of the named charts).
_HIS_PAIR_NOT_LISTED = {
    "ALB:2026-04-13": "his resistance is the second of two highs four cents apart; the swing ended on the first",
    "MDT:2026-07-24": "his support (79.96, Mon 08/06/2026) is nine cents over the low of the top's own day (79.87): "
                      "the move off the top had ended there, so no swing connects his two anchors",
    # MSGS left this list with his redraw of Sat 10/10/2026: his pair is the one the reader shows, to the cent.
    # His drawings of Fri 30/10/2026:
    "ANET:2026-09-25": "his resistance (198.92, Tue 11/08/2026) is no swing's end: the swing ended on the spike of "
                       "Wed 05/08/2026 (214.89)",
    "ANET:2026-10-02": "the same lines as his drawing of Fri 25/09/2026",
    "CBLL:2026-10-28": "his support is the first of two equal lows (23.65 on Mon 24/08 and Tue 25/08/2026), and the "
                       "move off the top ran on to 22.97 on Wed 26/08/2026, where the reader's support sits",
    "DDI:2026-09-30": "his pair is one wide bar (Fri 14/08/2026, 13.05 / 12.58); the move off its top ran on to 12.41 "
                      "the next day, so its low is no swing's end",
    "PKE:2026-04-07": "his support is the first of two lows ten cents apart; the swing ended on the second",
    "RGR:2026-03-19": "his resistance (38.47, Fri 16/01/2026) is a cent under the high of two days before; the "
                      "line turns on the first",
}
#: His boxes that, by the rule itself, give way by his buy day, and the pair that takes each one's place.
#: (BODI stood here until he redrew it on Sat 10/10/2026 from the March lines, 12.65 / 10.30; the pair he keeps
#: now stands by his buy.) EWTX: on his buy day the bars had hung for fifteen days on
#: a shelf resting on his resistance, none back at his support. MATX: the same shelf on his resistance, a box on
#: his last receding day. ROIV (redrawn Thu 01/10/2026): his pair is a box on Thu 23/04/2026; from Tue 21/04/2026
#: to Mon 11/05/2026, fifteen days, no bar came back to his resistance, and the lower box of the March dip takes
#: its place. NET (drawn Thu 01/10/2026): his resistance is the top of Wed 05/08/2026, and the rise ran on to 332.22
#: on Thu 13/08/2026; by his own anchor rule as the reader reads it, a top inside a rise that had not ended, and
#: the pair of the rise's first foot (the top of Fri 07/08/2026 and the low after it) takes its place. EXPD (drawn
#: Fri 30/10/2026): his pair (189.99, Mon 17/08/2026 / 185.02, Thu 20/08/2026) is a box from Fri 04/09/2026 and the
#: reader shows it on his last receding day; on his buy day, Fri 09/10/2026, the rise past his resistance to 194.59
#: (Tue 15/09/2026) reads as a trend whose end is known that day, and the pair of that top and the low after it,
#: 194.59 / 186.72 (Fri 18/09/2026), a box since Mon 05/10/2026, takes its place.
#: His one pair that is no box yet on his buy day (drawn Fri 30/10/2026): TWLO, 243.98 (Fri 28/08/2026) / 222.93 (Wed
#: 02/09/2026), has its fifteenth day after his buy of Mon 21/09/2026, so by the rule it is a box only then. The
#: reader shows the pair of Thu 04/06/2026, 238.48 / 222.62.
_HIS_PAIR_NOT_A_BOX_BY_HIS_BUY = ("TWLO:2026-09-21",)
#: His one pair the rule lists but calls unfit (drawn Fri 30/10/2026): VTMX, under one daily range tall (0.83).
_HIS_PAIR_UNFIT = {"VTMX:2026-10-02": "under one daily range tall"}
_HIS_BOX_GIVES_WAY_BEFORE_HIS_BUY = {"EWTX:2026-03-31": (31.29, 29.46),
                                     "MATX:2026-07-01": (197.63, 190.16), "NET:2026-09-15": (324.73, 290.49),
                                     "ROIV:2026-06-17": (28.39, 27.12),
                                     # His drawings of Fri 30/10/2026, by the same two rules on his own pair; the
                                     # pair that takes each one's place, as the rule reads it on his buy day.
                                     "CLDT:2026-10-09": (12.82, 12.41), "CLOV:2026-10-27": (4.39, 4.12),
                                     "DDI:2026-08-10": (11.43, 10.95), "DSGX:2026-10-08": (82.65, 78.18),
                                     "EXPD:2026-10-09": (194.59, 186.72)}


def test_his_own_pair_is_a_pair_the_rule_lists_and_a_box_by_it_on_his_drawings(his_reads):
    """His own two anchors, read by the rule he settled: two swing ends a swing connects, a counter move that took
    back a part only, at least a daily range tall, the bars back on both rails and fifteen days by his buy day —
    on every drawing but the eight named. And sentences 9 and 10 on his own box: by his buy day no later pair
    takes its place by the reader's two rules, but on the nine named."""
    from engine_alpha.two_eyes import walk

    not_listed, gives_way = [], {}
    for row in his_reads:
        pair, key = row["his_pair"], row["key"]
        if pair is None:
            not_listed.append(key)
            continue
        if key in _HIS_PAIR_UNFIT:
            assert pair.unfit == _HIS_PAIR_UNFIT[key], f"{key}: {pair.unfit}"
            continue
        assert pair.unfit is None, f"{key}: {pair.unfit}"
        if key in _HIS_PAIR_NOT_A_BOX_BY_HIS_BUY:
            assert pair.birth_bar is None and pair.fifteenth > row["buy_bar"], f"{key}: a box by his buy day after all"
            continue
        assert pair.birth_bar is not None and pair.birth_bar <= row["buy_bar"], f"{key}: not a box by his buy day"
        # One wide bar says nothing of which end printed first (DRTS, FOSL, MTLS): only his two-bar boxes are held
        # to the rail they open on.
        assert row["r_bar"] == row["s_bar"] or pair.top_first == (row["r_bar"] < row["s_bar"]), \
            f"{key}: read as opening on the other rail"
        for other in sorted((p for p in row["on_buy"].pairs.values() if p.birth_bar is not None), key=walk._key):
            if other.opening_bar > pair.opening_bar and (
                    walk.left_for_good(pair, other, row["high"], row["low"], pair.birth_bar, row["buy_bar"])
                    is not None
                    or walk.inside_a_live_trend(pair, other, row["on_buy"].ends, row["buy_bar"]) is not None):
                gives_way.setdefault(key, (round(other.R, 2), round(other.S, 2)))
    assert sorted(not_listed) == sorted(_HIS_PAIR_NOT_LISTED)
    assert gives_way == _HIS_BOX_GIVES_WAY_BEFORE_HIS_BUY


#: His one drawing on which the reader's box opens on the other rail than his, and why.
_OPENS_ON_THE_OTHER_RAIL = {
    "ALB:2026-04-13": "the reader shows the low of the crash and the top after it (182.80 / 156.04): it opens on "
                      "the low",
    # Drawn Fri 30/10/2026: his box opens on its support, the reader's on the extreme bar before it.
    "ANET:2026-09-25": "the reader shows the spike of Wed 05/08/2026 (214.89) and the low after it (187.03, his): it "
                       "opens on the spike; his box opens on that low, its top the shelf of Tue 11/08/2026",
    "ANET:2026-10-02": "the same box as his drawing of Fri 25/09/2026",
    "CLOV:2026-10-27": "the reader shows the climax of Thu 11/06/2026 (5.18) and the low after it (4.50): it opens on "
                       "the climax; his box (4.83 / 4.35) opens on the low of Fri 10/07/2026, a month later",
}


def test_the_readers_box_on_his_drawings_his_rule_on_the_result(his_reads):
    """His rule read off the reader's own boxes on his last receding day. Each rail sits on a swing's end by the
    bars — or is the other end of one wide bar (sentence 3) — and is that bar's own high or low; a swing connects
    the two; the box opens on the rail his box opens on, but on the one named."""
    other_rail = []
    for row in his_reads:
        box, key, highs, lows, last = row["result"].winner, row["key"], row["high"], row["low"], row["last_bar"]
        assert box is not None, f"{key}: no box on his last receding day"
        assert highs[box.r_bar] == box.R and lows[box.s_bar] == box.S, f"{key}: a rail is not its bar's own end"
        one_bar = box.r_bar == box.s_bar
        assert _a_swings_end(highs, box.r_bar, last, top=True) or one_bar, \
            f"{key}: resistance {box.R:.2f} is on no swing's end"
        assert _a_swings_end(lows, box.s_bar, last, top=False) or one_bar, \
            f"{key}: support {box.S:.2f} is on no swing's end"
        span = slice(box.opening_bar, box.second_bar + 1)
        assert highs[span].max() == box.R and lows[span].min() == box.S, f"{key}: no swing connects the two rails"
        assert box.unfit is None and box.height >= box.unit
        if box.top_first != (row["r_bar"] <= row["s_bar"]):
            other_rail.append(key)
    assert other_rail == sorted(_OPENS_ON_THE_OTHER_RAIL)


#: His one drawing on which the box shown on his last receding day (his own, to the cent) is not the box shown on
#: his buy day, and why.
_THE_BOX_CHANGES_ON_HIS_BUY_DAY = {
    "EWTX:2026-03-31": "from Wed 11/03/2026 the bars hang at his resistance and over it, none back at his support; "
                       "his buy day is the fifteenth such day, and the shelf 31.29 / 29.46, resting on his "
                       "resistance's area by six cents and a box since Fri 06/03/2026, takes his box's place",
}


#: THE BOARD of the core sitting (Thu 01/10/2026), drawing by drawing: the reader's box on his last receding day
#: against his own two lines. Pinned so that a change which loses one of his boxes, or gains one, is a red test
#: and a deliberate edit here. HIS BOX: both lines to the cent.
_READS_HIS_BOX = (
    "ANRO:2026-08-12", "AVT:2026-04-08", "DSGN:2026-03-31", "EGBN:2026-01-15", "EWTX:2026-03-31", "JAZZ:2026-02-24",
    "MRK:2026-08-10", "MS:2026-06-04", "NGL:2026-01-20", "NGL:2026-04-20", "NKTR:2026-04-10", "NOK:2026-02-17",
    "NTCT:2026-03-04", "PBT:2026-05-11", "SGHT:2026-09-24", "SILC:2026-04-13", "SKYT:2026-04-13", "ST:2026-04-17",
    "SYRE:2026-02-19", "UNF:2026-07-10", "VIK:2026-06-11", "VLO:2026-07-08", "WAT:2026-09-24", "WTS:2026-06-12",
    "YPF:2026-05-18",
    # His drawings since the seal of 40 (the standard of Fri 30/10/2026); MSGS as he redrew it on Sat 10/10/2026.
    "CLDT:2026-10-09", "EXPD:2026-10-09", "MSGS:2026-05-22", "OKTA:2026-09-03")
#: CLOSE: both lines within half a daily range of his.
_READS_CLOSE_TO_HIS = (
    "ALB:2026-04-13", "BWA:2026-05-05", "DLX:2026-04-13", "DRTS:2026-04-15", "FOSL:2026-02-18", "MDT:2026-07-24",
    "ORMP:2026-04-13", "PKE:2026-04-07", "RGR:2026-03-19", "ROIV:2026-06-17",
    # DSGX (Fri 30/10/2026): the reader shows 79.92 / 73.73 for his 79.11 / 75.31, which is its mini to the cent.
    "DSGX:2026-10-08")
#: ANOTHER BOX, and why, each measured on the bars. All but two (DDI's first drawing and VTMX) fire on his day at
#: his trigger (the core board): his bar of Thu 01/10/2026 — "as long as the engine understand that there is a
#: setup there I'm happy".
_READS_ANOTHER_BOX = {
    "BODI:2026-04-21": "the reader shows the first pair of the December base, 12.22 (Mon 08/12/2025) / 11.14 (Tue "
                       "09/12/2025); his, as he redrew it on Sat 10/10/2026, is 12.65 / 10.30 from Tue 17/03/2026, "
                       "a later pair over and under it. The price left the shown pair downward twice and came back "
                       "twice; from Mon 16/03/2026 it stands. (He set BODI aside on Thu 01/10/2026.)",
    # His drawings since the seal of 40 (the standard of Fri 30/10/2026). On every one but DDI's second and TWLO
    # the reader hangs a rail on one extreme bar where he draws the shelf the bars keep coming back to, and on
    # ANET, CLOV and CBLL that shelf is the reader's own mini.
    "ANET:2026-09-25": "the reader shows the spike of Wed 05/08/2026 and the low after it, 214.89 / 187.03: its "
                       "support is his, its resistance 1.4 daily ranges over his 198.92, the shelf of Tue "
                       "11/08/2026 the bars kept coming back to",
    "ANET:2026-10-02": "the same box; on this drawing the reader's mini, 200.68 / 187.89, is his shelf within a "
                       "quarter of a range, and the LPS is read against it",
    "CBLL:2026-10-28": "the reader shows 25.33 / 22.97 (Wed 19/08 and Wed 26/08/2026): its resistance is his, its "
                       "support the low of the 26/08 bar, 0.7 of a daily range under his 23.65",
    "CLOV:2026-10-27": "the reader shows the June climax and the low after it, 5.18 / 4.50 (Thu 11/06 and Mon "
                       "15/06/2026); his 4.83 / 4.35 opens on the low of Fri 10/07/2026 and is the reader's mini, "
                       "4.68 / 4.35, at the support",
    "DDI:2026-08-10": "the reader shows 11.60 / 11.27 (Thu 02/07 and Tue 07/07/2026), a box a daily range under his "
                      "wide bar of Thu 04/06/2026 (11.86 / 11.32). No fire: his rest of Fri 07/08/2026 sits more "
                      "than 1.35 ranges over that box's top",
    "DDI:2026-09-30": "the reader shows 13.28 / 12.65 (Mon 24/08 and Tue 25/08/2026) for his wide bar of Fri "
                      "14/08/2026 (13.05 / 12.58): its resistance 0.65 of a daily range over his",
    "TWLO:2026-09-21": "the reader shows the wide bar of Thu 04/06/2026, 238.48 / 222.62; his pair (243.98, Fri "
                       "28/08 / 222.93, Wed 02/09/2026) is no box yet on his buy day: its fifteenth day comes after",
    "VTMX:2026-10-02": "the reader shows 35.02 / 32.01 (Mon 18/05 and Fri 15/05/2026), the May low under his "
                       "support; his 34.77 / 33.79 is under one daily range tall and can be no box for the reader; "
                       "its mini, 35.23 / 33.47, is near his. No fire: his rest is a slice of a bigger swing down, "
                       "2.79 ranges under the spike of Fri 21/08/2026, over his ceiling of 2.75",
    "MATX:2026-07-01": "on Tue 30/06/2026, his last receding day, the shelf resting on his own resistance (197.63 / "
                       "190.16) became a box and took the place of 187.00 / 179.21, shown from Mon 15/06/2026. His "
                       "own pair lay across the resistance of the box shown when it became a box (180.21 / 167.35) "
                       "and never took its place",
    "MTLS:2026-09-04": "the reader shows the first wide bar of the June base, 7.00 / 6.60 (Mon 01/06/2026); his is "
                       "the wide bar of Tue 09/06/2026 (6.83 / 6.39), 0.6 and 0.74 of a daily range under it, which "
                       "lies across the shown support and never takes its place. Before the rule of the hanging "
                       "bars the reader hopped to the pair of the July run on a day the price was far under it, and "
                       "from there to a pair on his lines (6.78 / 6.36)",
    "NET:2026-09-15": "the reader shows the top of Fri 07/08/2026 and the low after it, 324.73 / 290.49, a box on Thu "
                      "27/08/2026: 1.3 and 0.68 of a daily range over his 305.00 (Wed 05/08/2026) / 280.13 (Thu "
                      "06/08/2026). His own pair is a box by the rule on Tue 25/08/2026, but its support lies 3.5 "
                      "under the resistance area of the July box shown then (291.00 / 261.73), across it, so it never "
                      "takes its place; and his resistance is a top inside the rise that ran on to 332.22 (Thu "
                      "13/08/2026). He kept 305.00: the bars met it on six later days and his support on eight",
}


def test_the_readers_box_against_his_own_on_each_of_his_drawings(his_reads):
    from tools.calibration.yardstick import rails_close

    got = {"HIS": [], "CLOSE": [], "OTHER": []}
    for row in his_reads:
        rails, box = row["setup"]["rails_drawn"], row["result"].winner
        unit = float(row["ranges"][max(row["r_bar"], row["s_bar"])])       # his own box's daily range
        if abs(box.R - rails["R"]) < 0.005 and abs(box.S - rails["S"]) < 0.005:
            got["HIS"].append(row["key"])
        elif rails_close(rails["R"], rails["S"], box.R, box.S, unit):
            got["CLOSE"].append(row["key"])
        else:
            got["OTHER"].append(row["key"])
    assert sorted(got["OTHER"]) == sorted(_READS_ANOTHER_BOX)
    assert sorted(got["CLOSE"]) == sorted(_READS_CLOSE_TO_HIS)
    assert sorted(got["HIS"]) == sorted(_READS_HIS_BOX) and len(got["HIS"]) == 29


def test_silc_and_drts_as_he_said_them_on_the_pictures(his_reads):
    """His words of Thu 01/10/2026, each on his own marked bars. SILC: "Silc supposed to work due the much respect
    of the support" — from the day after his low the bars rest on his support for seven weeks and never leave its
    area; resting is respect, so his pair is a box on its fifteenth day and it is the box shown. DRTS: "why would
    DRTS move away as it almost perfectly respect both boundaries" — the climax and its reaction low (7.89 / 6.23)
    are no box while the base forms, because the bars never return to that low before the spring of March; the
    reader's box stays within half a daily range of his."""
    from engine_alpha.two_eyes import walk
    from tools.calibration.yardstick import rails_close

    silc = next(r for r in his_reads if r["key"] == "SILC:2026-04-13")
    pair, days = silc["his_pair"], silc["days"]
    resting = walk._respects(silc["high"], silc["low"], pair.R, pair.S, pair.area)[1]
    assert resting[pair.s_bar + 1:days.index(dt.date(2026, 3, 23)) + 1].all()      # never off the support's area
    assert (days[pair.r_back], days[pair.s_back]) == (dt.date(2026, 2, 9), dt.date(2026, 2, 9))
    assert pair.birth_bar == pair.fifteenth and days[pair.birth_bar] == dt.date(2026, 2, 25)
    assert silc["result"].winner.feet == pair.feet

    drts = next(r for r in his_reads if r["key"] == "DRTS:2026-04-15")
    days, rails = drts["days"], drts["setup"]["rails_drawn"]
    climax = next(p for p in drts["result"].pairs.values() if (round(p.R, 2), round(p.S, 2)) == (7.89, 6.23))
    assert (days[climax.r_bar], days[climax.s_bar]) == (dt.date(2026, 1, 14), dt.date(2026, 1, 20))
    assert days[climax.r_back] == dt.date(2026, 1, 26) and days[climax.s_back] == dt.date(2026, 3, 4)
    box = drts["result"].winner
    assert days[box.birth_bar] < days[climax.birth_bar] == dt.date(2026, 3, 4)
    assert (round(box.R, 2), round(box.S, 2)) == (7.59, 6.90)
    unit = float(drts["ranges"][max(drts["r_bar"], drts["s_bar"])])
    assert rails_close(rails["R"], rails["S"], box.R, box.S, unit)
    assert drts["his_pair"].birth_bar == drts["his_pair"].fifteenth       # his own pair: a box on its fifteenth day


def test_roiv_the_dip_of_late_march_came_back_and_the_box_of_march_stands(his_reads):
    """His ROIV picture (Thu 01/10/2026, "can you manage to see the logic behind the markings?"): a red dash on
    each bar that meets one of his two lines, none on the days under the support at the end of March nor on the
    two days over the resistance in May — a low or a high the price never returns to is a dip or a poke and does
    not end the box. And his word on the boxes the reader never went back to: "as long as the engine understand
    that there is a setup there I'm happy". On his own bars: on Fri 10/04/2026 the reader follows the dip to the
    pair made of its own bars (28.39 / 27.12); on Tue 14/04/2026 the bars are back at both rails of the box it
    gave up (30.03 / 28.31: the top of Thu 05/03 and the low of Fri 06/03, one swing before his, both lines within
    half a daily range of his) and it takes its place back; it stands on his last receding day and on his buy
    day. No pair that is a box sits on the dip's low (25.95) nor on the poke's high (32.79)."""
    from engine_alpha.two_eyes import walk
    from tools.calibration.yardstick import rails_close

    roiv = next(r for r in his_reads if r["key"] == "ROIV:2026-06-17")
    days, on, rails = roiv["days"], roiv["on"], roiv["setup"]["rails_drawn"]

    def shown(found) -> tuple:
        return (round(found.winner.R, 2), round(found.winner.S, 2))

    def night(*ymd):
        return on(days.index(dt.date(*ymd)))

    assert shown(night(2026, 4, 9)) == (30.03, 28.31)
    assert shown(night(2026, 4, 10)) == shown(night(2026, 4, 13)) == (28.39, 27.12)
    back = night(2026, 4, 14)
    assert shown(back) == (30.03, 28.31)
    assert back.lives[-1].why == walk.CAME_BACK and days[back.lives[-1].shown_bar] == dt.date(2026, 4, 14)
    for found in (roiv["result"], roiv["on_buy"]):
        assert shown(found) == (30.03, 28.31) and days[found.lives[-1].shown_bar] == dt.date(2026, 4, 14)
    box = roiv["result"].winner
    assert (days[box.r_bar], days[box.s_bar]) == (dt.date(2026, 3, 5), dt.date(2026, 3, 6))
    unit = float(roiv["ranges"][max(roiv["r_bar"], roiv["s_bar"])])
    assert rails_close(rails["R"], rails["S"], box.R, box.S, unit)
    # The dip's low and the poke's high are on his bars, and no pair that is a box by his buy day sits on either.
    dip, poke = days.index(dt.date(2026, 3, 30)), days.index(dt.date(2026, 5, 20))
    assert (round(float(roiv["low"][dip]), 2), round(float(roiv["high"][poke]), 2)) == (25.95, 32.79)
    boxes = [p for p in roiv["on_buy"].pairs.values() if p.birth_bar is not None]
    assert not any(abs(p.S - 25.95) < 0.005 or abs(p.R - 32.79) < 0.005 for p in boxes)


def test_mtls_the_box_of_june_does_not_give_way_to_the_rails_of_the_july_run(his_reads):
    """Sentence 10, both halves, on his own bars. The reader's box of June is the wide bar of Mon 01/06/2026
    (7.00 / 6.60; his own is the wide bar of Tue 09/06/2026, 6.83 / 6.39, which lies across its support and so
    never takes its place). The run of July made a pair up there (7.50 / 7.01), a box by the rule on Wed
    22/07/2026 — a day the price was already back under it. On Wed 05/08/2026 fifteen days had passed with no bar
    back at the June box's resistance; and no bar had been at the July pair's resistance since Mon 06/07/2026,
    nor would be until the gap of Thu 27/08/2026: the bars do not hang on those rails, and the box does not give
    way to them. It stands on his last receding day and on his buy day, and the lows of his last receding days
    rest on its resistance."""
    from engine_alpha.two_eyes import walk

    mtls = next(r for r in his_reads if r["key"] == "MTLS:2026-09-04")
    days, found, high, low = mtls["days"], mtls["result"], mtls["high"], mtls["low"]

    def bar(*ymd) -> int:
        return days.index(dt.date(*ymd))

    june = found.winner
    assert (round(june.R, 2), round(june.S, 2)) == (7.00, 6.60) and june.r_bar == june.s_bar == bar(2026, 6, 1)
    assert days[found.lives[-1].shown_bar] == dt.date(2026, 6, 22) and mtls["on_buy"].winner.feet == june.feet
    july = next(p for p in found.pairs.values() if (round(p.R, 2), round(p.S, 2)) == (7.50, 7.01))
    assert days[july.birth_bar] == dt.date(2026, 7, 22) and july.S >= june.R - june.area
    at_r, _ = walk._respects(high, low, june.R, june.S, june.area)
    fifth = bar(2026, 8, 5)
    assert at_r[fifth - 15] and not at_r[fifth - 14:fifth + 1].any()     # the June resistance: last on Wed 15/07
    hang_r, _ = walk._respects(high, low, july.R, july.S, july.area)
    assert hang_r[bar(2026, 7, 6)] and not hang_r[bar(2026, 7, 7):bar(2026, 8, 26) + 1].any() and hang_r[bar(2026, 8, 27)]
    assert walk.left_for_good(june, july, high, low, found.lives[-1].shown_bar, mtls["buy_bar"]) is None
    for night in (fifth, bar(2026, 8, 7), bar(2026, 8, 27)):
        assert mtls["on"](night).winner.feet == june.feet, f"{days[night]:%a %d/%m/%Y}"
    receding = low[bar(2026, 8, 28):mtls["last_bar"] + 1]
    assert len(receding) == 5 and (np.abs(receding - june.R) <= june.area).all()


def test_the_boxes_life_on_his_drawings_moves_by_the_three_rules_and_goes_back_only_after_a_dip(his_reads):
    """Read with no memory on days up to his last receding day, the reader tells the same history: what a later
    day tells of the days before is what those days told. Every hand-over is by one of the five rules, on or
    after the day the box that takes the place became a box: to a pair that opened LATER (the box before it was
    anchored inside a live trend; the price left it for good), to the SIBLING tried before it (the same opening
    anchor, the earlier second anchor: his GFR), or BACK to the box given up, when the price had
    left it downward and the bars are back at both its rails. And the box shown on his last receding day is still
    the box on his buy day, on every drawing but the one named."""
    from engine_alpha.two_eyes import walk

    hand_overs, came_back, changed_on_his_buy_day = 0, 0, []
    for row in his_reads:
        result, key = row["result"], row["key"]
        told = [(life.pair.feet, life.shown_bar) for life in result.lives]
        for day in range(max(0, row["first_bar"] - 12), row["last_bar"], 7):
            on_day = [(life.pair.feet, life.shown_bar) for life in row["on"](day).lives]
            assert on_day == [t for t in told if t[1] <= day], f"{key}: {row['days'][day]:%a %d/%m/%Y} told otherwise"
        for i, (old, new) in enumerate(zip(result.lives, result.lives[1:])):
            assert new.shown_bar >= new.pair.birth_bar and old.ended_bar is not None
            if new.why == walk.CAME_BACK:
                # Back to the box the reader gave up to the pair under it, the day the bars were back at both
                # its rails.
                assert i >= 1 and result.lives[i - 1].pair.feet == new.pair.feet and old.why == walk.LEFT_FOR_GOOD, key
                assert old.pair.R <= new.pair.S + new.pair.area, f"{key}: a place given back after a run up"
                assert walk.came_back_to(new.pair, old.pair, row["high"], row["low"], old.shown_bar,
                                         new.shown_bar) == new.shown_bar, key
                came_back += 1
                continue
            if new.why == walk.TRIED_FIRST:
                # A sibling off the same opening anchor with an earlier second anchor, the day it is a box.
                assert new.pair.opening_bar == old.pair.opening_bar and new.pair.second_bar < old.pair.second_bar, key
                assert new.shown_bar == new.pair.birth_bar > old.shown_bar, key
                hand_overs += 1
                continue
            assert new.pair.opening_bar > old.pair.opening_bar, f"{key}: the shown line moved back"
            if new.why == walk.WRAPS:
                # A one-bar box gives way to the tighter pair inside or across it, opened while it was forming, the
                # day the bars hang on its rails and have never come back to one of the box's.
                assert old.pair.r_bar == old.pair.s_bar, key
                assert not walk.lies_beyond(new.pair, old.pair) and new.pair.height < 0.8 * old.pair.height, key
                assert new.pair.opening_bar <= old.pair.birth_bar, key
                assert walk.wraps(old.pair, new.pair, row["high"], row["low"], old.shown_bar,
                                  new.shown_bar) == new.shown_bar, key
                hand_overs += 1
                continue
            if new.why == walk.LEFT_FOR_GOOD:
                assert walk.left_for_good(old.pair, new.pair, row["high"], row["low"], old.shown_bar,
                                          new.shown_bar) == new.shown_bar, key
            else:
                assert new.why == walk.LIVE_TREND and new.trend_end["known_bar"] <= new.shown_bar, key
                assert walk.inside_a_live_trend(old.pair, new.pair, result.ends, new.shown_bar) is not None, key
            hand_overs += 1
        assert row["on_buy"].winner is not None, f"{key}: no lines on his buy day"
        if row["on_buy"].winner.feet != result.winner.feet:
            changed_on_his_buy_day.append(key)
    assert changed_on_his_buy_day == sorted(_THE_BOX_CHANGES_ON_HIS_BUY_DAY)
    assert hand_overs > 300, "too few hand-overs were checked; the guard would be thin"
    assert came_back >= 50, f"only {came_back} places given back were checked; the guard would be thin"
    assert {r["setup"]["ticker"] for r in his_reads} >= {"ST", "NOK", "MSGS"}      # the plan's three


def test_keep_listing_is_pinned_identical_on_every_chart(prepared_frames):
    from engine_alpha.two_eyes import walk

    for key, prepared in prepared_frames.items():
        result, _ = _walk_on(prepared)
        boxes, trail, state = walk.record(result)
        more_boxes, more_trail, more_state = walk.record(result, keep_listing=True)
        assert (more_boxes, more_state) == (boxes, state), key
        assert more_trail[:len(trail)] == trail, key
        assert all(s.stage == "listed" for s in more_trail[len(trail):]), key


def test_ewtx_and_ngl_read_as_box_breakout_new_box_with_the_earlier_box_kept(his_reads):
    """"EWTX Should Fire on my mark!" (Wed 09/09/2026): the plan's two "box, breakout, new box" drawings. On his
    last receding day the record holds his box as the parent, and the box the price broke out of below it as an
    earlier box, ended; the trail opens with the hand-over. On NGL the earlier box is his January drawing's
    level (10.29 / 9.38)."""
    from engine_alpha.two_eyes import walk, record

    for key, january in (("EWTX:2026-03-31", None), ("NGL:2026-04-20", (10.29, 9.38))):
        row = next(r for r in his_reads if r["key"] == key)
        result = row["on"](row["last_bar"])
        result = type(result)(**{**result.__dict__, "days": tuple(row["days"])})
        boxes, trail, _ = walk.record(result)
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
    the price: the box shown on the frame's last day is one the bars were at within the last fifteen trading days
    (a bar's high or low inside the area of one of its rails), never the dead-space box, and the boxes the price
    left are in the record as earlier boxes, ended."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes.walk import bar_respects
    from tools.regression import negative_corpus

    frames, _ = negative_corpus._load_fixture()
    for key, dead in (("BMRN", (60.93, 58.00)), ("OHI", (44.88, 42.90))):
        raw = frames[key]
        read = two_eyes.read(key, raw)
        box = read.parent
        assert box is not None, key
        R, S, area = box.resistance.price, box.support.price, 0.5 * box.daily_range
        recent = raw.iloc[-15:]
        assert any(bar_respects(h, l, R, S, area) for h, l in zip(recent["High"], recent["Low"])), \
            f"{key}: no bar of the last fifteen days was at the box shown ({R:.2f} / {S:.2f})"
        assert (round(R, 2), round(S, 2)) != dead, f"{key}: dead space is shown"
        earlier = [b for b in read.boxes if b.role == two_eyes.ROLE_EARLIER]
        assert earlier and all(b.end_day is not None and b.end_day <= read.as_of for b in earlier), key


def test_the_read_equals_the_knowable_order_replay_at_every_hand_over_on_every_chart(prepared_frames):
    """Within ONE prepared window: the boxes the last day's read records as handed over are the boxes the same
    window shows when it is read day by day, its turns filtered by the day they were known. On each of the last
    two days the shown box changed, on every chart, the day before shows the box the record says stood then and
    that day shows the one it says took its place (two hand-overs can fall on one day: the pair between them is
    in the record and was never the box of a night); and only the last box is the parent. It does NOT read a new
    window every night, as the scan does: the tests at the end of this file do."""
    from engine_alpha.two_eyes import walk, record

    hand_overs = 0
    for key, prepared in prepared_frames.items():
        result, on = _walk_on(prepared)
        result = type(result)(**{**result.__dict__, "days": tuple(d.date() for d in prepared.index)})
        boxes, _, _ = walk.record(result)
        assert [b.role for b in boxes[:-1]] == [record.ROLE_EARLIER] * (len(boxes) - 1), key
        assert all(b.end_day is not None for b in boxes[:-1]), key
        assert not boxes or (boxes[-1].role == record.ROLE_PARENT and boxes[-1].end_day is None), key
        assert all(old.ended_bar is not None and old.ended_bar <= new.shown_bar
                   for old, new in zip(result.lives, result.lives[1:])), key

        def stood(day: int):
            """The box the last day's read says stood on ``day``: the last one shown by then."""
            return next((life.pair.feet for life in reversed(result.lives) if life.shown_bar <= day), None)

        for day in sorted({life.shown_bar for life in result.lives[1:]})[-2:]:
            before, after = on(day - 1).winner, on(day).winner
            assert (before and before.feet) == stood(day - 1), \
                f"{key}: the day before the hand-over the reader showed {before and before.feet}, not {stood(day - 1)}"
            assert after.feet == stood(day) != stood(day - 1), \
                f"{key}: on the hand-over's day the reader showed {after.feet}, not {stood(day)}"
            hand_overs += 1
    assert hand_overs >= 150, f"only {hand_overs} hand-overs were replayed; the guard would be thin"


# --------------------------------------------------------------------------- #
# Read as the scan reads: a new two-year window every night                   #
# --------------------------------------------------------------------------- #
def _as_the_scan_reads(raw, night) -> tuple:
    """One night as the scan reads it: the long frame cut at the night and prepared afresh, so the window's
    left edge is a day later every night. The walk's result, that window's own days, and the night's LPS word
    (None while no day has receded)."""
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, lps

    prepared = frame_module.prepare(raw.loc[:night])
    found, _ = _walk_on(prepared)
    line = line_module.build(prepared)
    ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
    days = [d.date() for d in prepared.index]
    word, won = None, found.winner
    if won is not None:
        pullback = lps.read(prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float), ranges,
                            line.committed, R=won.R, S=won.S, box_unit=won.unit, born_bar=won.birth_bar)
        word = lps.record(pullback, days, read_bar=len(prepared) - 1)[2]
    return found, days, word


def _lines(pair, days) -> tuple:
    """A box by its two lines and their anchor days: the same box in whatever window it is read."""
    return (round(pair.R, 4), days[pair.r_bar], round(pair.S, 4), days[pair.s_bar])


#: Four of his drawings with hand-overs in their last 45 nights. A SAMPLE, sized to run in a test: on Thu
#: 01/10/2026 the whole population was replayed the same way — his 37 and the 16 junk charts, 40 nights each,
#: 2,120 nights — and the box shown moved on 104 of them, every one a night the read itself says the newer box
#: took its place (the decisions record). Replayed again on Fri 02/10/2026, with the dip that comes back and the
#: rails the bars hang on: the box shown moved on 88 nights, 6 of them a place given back, each the night the
#: read says so.
_REPLAYED = ("EGBN:2026-01-15", "MSGS:2026-05-22", "YPF:2026-05-18", "MRK:2026-08-10")


def test_read_night_after_night_as_the_scan_reads_the_shown_box_moves_only_the_night_the_newer_box_takes_its_place():
    """The proofs above read ONE prepared window and filter its turns by the day they were known. The scan cuts a
    new window every night. Read that way, night after night: the box shown changes only on the night the read
    itself says the newer box took its place, and the box of the night before is among the boxes it hands over
    (two hand-overs can fall on one night); on every other night the last three earlier boxes are told as the
    night before told them. And the LPS word: a night
    says ``crossed``, the buy, only when the night before had the trigger on the board."""
    from engine_alpha.two_eyes import lps
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    hand_overs = crossed = 0
    for key in _REPLAYED:
        raw = fixture_frame(frames, key, key.split(":")[0])
        before = word_before = None
        for night in raw.index[-45:]:
            found, days, word = _as_the_scan_reads(raw, night)
            when = f"{night:%a %d/%m/%Y}"
            assert found.winner is not None, f"{key}: no box on {when}"
            told = [_lines(life.pair, days) for life in found.lives]
            if before is not None and told[-1] != before[-1]:
                assert days[found.lives[-1].shown_bar] == night.date(), \
                    f"{key}: the shown box moved on {when}, not the night the read says the newer box took its place"
                assert before[-1] in told[:-1], \
                    f"{key}: on {when} the box shown the night before is not among the boxes handed over"
                hand_overs += 1
            elif before is not None:
                assert told[-4:-1] == before[-4:-1], \
                    f"{key}: {when} tells the last three earlier boxes differently, with no hand-over that night"
                if word == lps.CROSSED:
                    assert word_before == lps.FIRED, \
                        f"{key}: {when} says crossed, and the night before ({word_before}) no trigger was on the board"
                    crossed += 1
            before, word_before = told, word
    assert hand_overs >= 10, f"only {hand_overs} hand-overs were replayed; the guard would be thin"
    assert crossed >= 30, f"only {crossed} buy days were replayed; the guard would be thin"


def _flg_on_two_nights() -> list:
    """FLG, the junk fixture, read on Thu 28/05/2026 and on Fri 29/05/2026: no box takes another's place on
    either night. Thursday's window opens on Thu 23/05/2024 and its first trend end is the low of Mon 10/06/2024;
    Friday's opens a day later and has lost that trend end."""
    from tools.regression import negative_corpus

    frames, _ = negative_corpus._load_fixture()
    told = []
    for night in (pd.Timestamp("2026-05-28"), pd.Timestamp("2026-05-29")):
        found, days, _ = _as_the_scan_reads(frames["FLG"], night)
        told.append([_lines(life.pair, days) for life in found.lives])
    return told


def test_flg_tells_the_same_boxes_the_night_after_its_window_lost_its_first_trend_end_but_the_oldest():
    thursday, friday = _flg_on_two_nights()
    assert thursday[-1] == friday[-1] and (thursday[-1][0], thursday[-1][2]) == (14.37, 13.8)
    assert thursday[-4:-1] == friday[-4:-1]
    # From the box of October 2024 on — 22 boxes, the shown one last — both nights tell the same history. (23 until
    # his HCA, Sat 24/10/2026: the box before the one of Fri 25/07/2025, 11.61 / 10.9, now stands through a run over
    # its top that came back, and that box is no longer told.)
    since = (12.49, dt.date(2024, 10, 21), 11.5, dt.date(2024, 10, 22))
    assert thursday[thursday.index(since):] == friday[friday.index(since):]
    assert len(thursday) - thursday.index(since) == 22
    # Before it, the window's first five months: three boxes on Thursday, five other boxes on Friday.
    assert (thursday.index(since), friday.index(since)) == (3, 5)
    assert not set(thursday[:3]) & set(friday[:5])


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN LIMIT, found by the core's blind check on Sun 27/09/2026 and narrowed by the rebuild of Thu 01/10/2026. "
    "The reader has no memory: it reads the boxes from the first trend end its two-year window holds, and the "
    "window's left edge moves a day a night. So the OLDEST boxes it records, those of the window's first months, "
    "are told differently on some nights no box took another's place (94 of 2,240 replayed nights on his 40 "
    "and the junk, Fri 02/10/2026, beside 98 on which the window had only moved on past the oldest box; before "
    "the rebuild 738 of 8,350 by an older count). The last three earlier boxes were told differently on none of "
    "those nights, and the box SHOWN moved only on a hand-over's own night. Three ways to tell the same earlier "
    "boxes whichever night tells them were measured on Fri 02/10/2026 and none holds on charts nobody chose (the "
    "Tested-DEAD record), so the story (task 12b) reads the box shown and no earlier box. This mark comes off the "
    "day a telling of the earlier boxes holds on every night, deliberately."))
def test_the_oldest_boxes_of_the_record_are_the_same_boxes_the_night_after():
    thursday, friday = _flg_on_two_nights()
    assert thursday[:-1] == friday[:-1], \
        f"the first boxes of the record: {thursday[:2]} on Thursday, {friday[:2]} on Friday"
