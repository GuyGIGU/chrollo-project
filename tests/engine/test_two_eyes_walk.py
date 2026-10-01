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
# Sentences 6, 7 and 8: coming back, and the day the pair is a box            #
# --------------------------------------------------------------------------- #
def test_back_means_back_a_bar_comes_back_to_a_rail_after_a_bar_that_left_it():
    from engine_alpha.two_eyes.walk import came_back

    #                  0      1      2      3      4      5      6
    high = np.array([100.0, 97.0, 93.0, 99.4, 97.0, 96.0, 101.2])
    low = np.array([98.0, 90.0, 90.5, 96.0, 94.0, 89.4, 99.3])
    # Resistance 100 (bar 0), support 90 (bar 1), the area one point. Bar 2 rests on support the day after the
    # low: the price has not left it, so it is no come-back. Bar 3's high is back at resistance: the price left
    # it on bar 1. Bar 5's low, six tenths under support, is back at support: poking out counts.
    assert came_back(high, low, 100.0, 90.0, 1.0, 0, 1, read_bar=6) == (3, 5)
    # What the reader knows on an earlier day.
    assert came_back(high, low, 100.0, 90.0, 1.0, 0, 1, read_bar=4) == (3, None)
    assert came_back(high, low, 100.0, 90.0, 1.0, 0, 1, read_bar=2) == (None, None)
    # A come-back is later than BOTH anchors: with support anchored on bar 4 (94), bar 3 is no come-back to
    # resistance, and bar 6 — its low resting on resistance from above — is.
    assert came_back(high, low, 100.0, 94.0, 1.0, 0, 4, read_bar=6) == (6, None)
    # Nothing after the anchors: nothing came back.
    assert came_back(high, low, 100.0, 99.3, 1.0, 0, 6, read_bar=6) == (None, None)


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
    assert (slow.r_back, slow.s_back, slow.fifteenth, slow.birth_bar) == (29, 18, 25, 29)
    assert _box(_elect(late, read_bar=28)) is None and _box(_elect(late, read_bar=29)) == (80.0, 70.0)
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
def test_the_first_pair_to_become_a_box_is_shown_and_a_pair_inside_or_across_it_never_takes_its_place():
    """"were looking for the first instance that a consolidation is respected!", and sentence 9: "Once a box, it
    stays a box through dips under support and pokes over resistance that come back"."""
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
    assert poke.birth_bar == 49 and poke.opening_bar > found.winner.opening_bar
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
    # rails, so on the day the pair above is a box (bar 49) the box stands, however clean the pair above.
    failed = _chart(_BREAKOUT_THAT_CAME_BACK)
    high, low, last = failed["high"], failed["low"], failed["n"] - 1
    box, above = _pair(_elect(failed), 80.0, 70.0), _pair(_elect(failed), 94.0, 88.0)
    assert above.birth_bar == 49 and above.S >= box.R - box.area
    assert _box(_elect(failed, read_bar=49)) == _box(_elect(failed, read_bar=57)) == (80.0, 70.0)
    assert walk.left_for_good(box, above, high, low, 0, 57) is None
    # Judged on every day, not once: the price went back up and for fifteen days the bars hung on the rails
    # above — the last bar at the old support is bar 43, and bar 58 is the fifteenth day after it. That day the
    # price has left the box, and the pair above takes its place.
    assert walk.left_for_good(box, above, high, low, 0, last) == 58
    assert walk.left_for_good(box, above, high, low, 60, last) == 60        # never before the day asked from
    assert _shown_day_by_day(failed) == [(80.0, 70.0, 25), (94.0, 88.0, 58)]
    # Beyond means resting on the old rail's area or further: with its support at 78.9, a tenth of a point under
    # the old resistance's area, the pair above lies across the box and never takes its place.
    high, low, last = chart["high"], chart["low"], chart["n"] - 1
    assert walk.left_for_good(old.pair, new.pair, high, low, 0, last) == 49     # never before it is a box
    from dataclasses import replace
    assert walk.left_for_good(old.pair, replace(new.pair, S=79.0), high, low, 0, last) == 49
    assert walk.left_for_good(old.pair, replace(new.pair, S=78.9), high, low, 0, last) is None
    # ... and only a pair that opened LATER: the old box never takes the new one's place back.
    assert walk.left_for_good(new.pair, old.pair, high, low, 0, last) is None
    # A read day before the newer pair is a box: no day yet.
    assert walk.left_for_good(old.pair, new.pair, high, low, 0, 48) is None


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


def test_a_shown_line_never_moves_back_read_day_by_day_with_no_memory():
    """Every hand-over goes to a pair that opened later, and each is judged on what its own day knew: a reader
    with no memory, standing on any day, tells the same history up to that day as one standing later — also
    when the trend end that takes a box's place is known only after the newer pair is a box (the pause chart
    with the far view that sees the rise end late)."""
    for points, far in ((_BOX, None), (_RUN_PAST_THE_RAIL, None), (_BOX_THEN_BREAKOUT, None),
                        (_BREAKOUT_THAT_CAME_BACK, None), (_BOX_WITH_POKES, None), (_PAUSE_INSIDE_A_RISE, _PAUSE_FAR),
                        (_PAUSE_INSIDE_A_RISE, _PAUSE_FAR - {30, 33, 36, 39}),
                        (_SPRING_UNDER_A_LATER_BOX, _SPRING_FAR), (_OUTER_PAIR_RESPECTED_LATE, None)):
        chart = _chart(points)
        last = _elect(chart, far)
        told = [(life.pair.feet, life.shown_bar) for life in last.lives]
        for day in range(chart["n"]):
            on_day = _elect(chart, far, read_bar=day)
            assert [(life.pair.feet, life.shown_bar) for life in on_day.lives] == [t for t in told if t[1] <= day], day
            opens = [life.pair.opening_bar for life in on_day.lives]
            assert opens == sorted(set(opens)), f"the shown line moved back by bar {day}"


def test_an_earlier_pair_that_becomes_a_box_later_never_takes_the_shown_boxs_place():
    """OURS, not his, and asked of him at the core sitting (Thu 01/10/2026): the shown line never moves back to a
    pair that opened earlier. The climax and its reaction (80 / 70) is a box only on bar 40, when the bars at last
    come back to its resistance; by then the reader has shown the pair to its right (76 / 70) for twelve days, and
    it stays. Three ways of going back to the earlier pair were measured on his 37 drawings and each read fewer of
    his boxes to the cent (13 to 19, against 20); on his ROIV this rule costs his box."""
    chart = _chart(_OUTER_PAIR_RESPECTED_LATE)
    found = _elect(chart)
    outer, shown = _pair(found, 80.0, 70.0), found.winner
    assert (outer.opening_bar, outer.r_back, outer.s_back, outer.birth_bar, outer.unfit) == (11, 40, 20, 40, None)
    assert (shown.R, shown.S, shown.opening_bar, shown.top_first, shown.birth_bar) == (76.0, 70.0, 14, False, 28)
    assert len(found.lives) == 1
    assert _shown_day_by_day(chart) == [(76.0, 70.0, 28)]
    # The day before the outer pair is a box, and the day it is one: the same box shown.
    assert _box(_elect(chart, read_bar=39)) == _box(_elect(chart, read_bar=40)) == (76.0, 70.0)
    assert _pair(_elect(chart, read_bar=39), 80.0, 70.0).birth_bar is None


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
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    days = tuple(d.date() for d in prepared.index)
    result = walk.elect(line.committed, [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES) if t.committed], ranges,
                        high, low, days=days, read_bar=len(prepared) - 1)
    boxes, trail, state = walk.record(result)
    assert state == "lines, no LPS yet"
    won = result.winner
    pullback = lps.read(high, low, ranges, line.committed, R=won.R, S=won.S, box_unit=won.unit,
                        born_bar=won.birth_bar)
    the_lps, said, word = lps.record(pullback, days, read_bar=len(prepared) - 1)
    assert (read.boxes, read.lps, read.trail, read.state) == (boxes, the_lps, trail + said, word)
    assert read.parent is not None and len(said) == 1 and word in (lps.FIRED, lps.CROSSED, lps.LINES_NO_LPS)


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
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, walk, method_numbers as M

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
        buy = min(days.index(dt.date.fromisoformat(str(setup["trigger"])[:10])) if setup.get("trigger") else last,
                  len(days) - 1)
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
    assert len(out) == 37      # the population follows his drawings (his ruling, Tue 08/09/2026)
    return out


#: The plan's named charts among his drawings, and PBT, whose box he ruled on at the core sitting: the reader's
#: box on his last receding day is his pair, to the cent. Those it still reads otherwise are pinned as expected
#: failures, strictly, each with its reason, so the day one passes it is a red test and the pin moves.
_NAMED = ("VIK:2026-06-11", "SYRE:2026-02-19", "EWTX:2026-03-31", "NGL:2026-04-20", "VLO:2026-07-08",
          "PBT:2026-05-11",
          pytest.param("ALB:2026-04-13", marks=pytest.mark.xfail(strict=True, reason=(
              "his box is the top of Thu 15/01/2026 and its reaction (179.10 / 160.02), his option 1. The reader "
              "shows it from Wed 04/02/2026 (on 179.14, the high of the day before his, four cents over) and, "
              "from Wed 25/02/2026, the day the bars came back to the run's own top, the pair of that top: 195.69 "
              "(Tue 27/01/2026) / 164.15. His word of Thu 01/10/2026: \"even a later pair could work if that "
              "movement in 20/1 -> 27/1 and the crash afterwards could be treated as the place where the trend "
              "ends\""))),
          pytest.param("FOSL:2026-02-18", marks=pytest.mark.xfail(strict=True, reason=(
              "his box is one wide bar three weeks into the base (4.00 / 3.61, Fri 26/12/2025); the reader shows "
              "the pair of the top before it, 4.13 (Fri 05/12/2025) / 3.61 (Mon 08/12/2025), a box that same Fri "
              "26/12/2025: the same support price and a resistance within half a range of his; his bar lies inside "
              "it"))),
          pytest.param("MSGS:2026-05-22", marks=pytest.mark.xfail(strict=True, reason=(
              "his support is the climax bar's own low (Wed 18/02/2026); the line reads that bar's low before its "
              "high, so it is no end of the move off the top, and his pair is not listed. The reader shows "
              "345.48 / 325.27, within half a range of his 345.46 / 320.70"))),
          pytest.param("ROIV:2026-06-17", marks=pytest.mark.xfail(strict=True, reason=(
              "the bars came back to his resistance (30.33, Wed 11/03/2026) only on Fri 17/04/2026; by then the "
              "reader showed a pair that opened later, inside his, and a shown line never moves back to an "
              "earlier pair (ours)"))))


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
}
#: His two support anchors that are no swing's end by the bar on either side, and why (his drawings, to the cent).
_HIS_SUPPORT_NOT_AN_END = {
    "MSGS:2026-05-22": "his support is the climax bar's own low: the bar gapped up, the day before is far under it",
    "PKE:2026-04-07": "the first of two lows ten cents apart: 26.30 on Fri 06/03/2026, 26.20 the day after",
}


def test_his_own_drawings_keep_his_rule_of_the_end_points(his_reads):
    """His ruling of Mon 28/09/2026, measured on his own drawings by bars alone, no reader in the way: each of
    his lines sits on a swing's end (every resistance anchor but the one named; every support anchor but the
    two named), and every one of his boxes opens on the END of the swing before it, the other line on the counter
    move — 34 on resistance after a rise, 3 on support after a fall."""
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
        assert _came_from_beyond(row, min(r_bar, s_bar), r_bar <= s_bar, R, S), \
            f"{row['key']}: the swing before his box did not run into his first line"
        if s_bar < r_bar:
            opens_on_support.append(row["key"])
    assert opens_on_support == ["AVT:2026-04-08", "JAZZ:2026-02-24", "SKYT:2026-04-13"]


#: His one root swing that took longer than four trading days, in trading days: ROIV's support is the second low
#: after his top ("one line can stay on its anchor while the other moves", Sun 20/09/2026).
_HIS_SLOW_COUNTER_MOVE = {"ROIV:2026-06-17": 7}
#: His box the price went on past (its first line, by more than the area) BEFORE the bars were back on both lines,
#: and his boxes the price stood well over (1.25 daily ranges and more) in their first fifteen days, in daily
#: ranges. He kept all of them: a run past a rail never unmakes a pair by itself (sentence 8). On ALB he said the
#: breach "is not an upthrust in fact there is a later on 25/02/2026 its just that those pairs could be used to fit
#: the box" (Thu 01/10/2026).
_HIS_FIRST_LINE_PASSED_FIRST = ("ALB:2026-04-13",)
_HIS_EARLY_RUN_PAST_RESISTANCE = {"ALB:2026-04-13": 2.04, "MTLS:2026-09-04": 2.20}


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
    anchor on every drawing but the one named. The bars come back to BOTH his lines (a bar's high within the area
    of his resistance, a bar's low within the area of his support) on every one. They do so before the price goes
    on past his FIRST line on 36 of 37, and in the box's first fifteen days the price is 1.25 ranges or more over
    his resistance on 2: both are TENDENCIES with his own exceptions named, never a rule that drops a pair. Under
    his support it dips more than a full range on ten, and he kept the line."""
    from engine_alpha.two_eyes import method_numbers as M

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
    assert len(deep) == 10, deep


#: His drawings whose own pair the rule does not list, and why: on each, one of his anchors is not the end of the
#: swing by the reader's line, or no swing connects the two. On all five the reader's box is within half a daily
#: range of his, but ALB's (the test of the named charts).
_HIS_PAIR_NOT_LISTED = {
    "ALB:2026-04-13": "his resistance is the second of two highs four cents apart; the swing ended on the first",
    "MDT:2026-07-24": "his support (79.96, Mon 08/06/2026) is nine cents over the low of the top's own day (79.87): "
                      "the move off the top had ended there, so no swing connects his two anchors",
    "MSGS:2026-05-22": "his support is the climax bar's own low; the line reads that bar's low before its high",
    "PKE:2026-04-07": "his support is the first of two lows ten cents apart; the swing ended on the second",
    "RGR:2026-03-19": "his resistance (38.47, Fri 16/01/2026) is a cent under the high of two days before; the "
                      "line turns on the first",
}
#: His boxes that, by the rule itself, give way by his buy day, and the pair that takes each one's place.
#: BODI: the price fell out of his box in January and for fifteen days and more hung on rails under it; it came
#: back up in March, and he kept his December lines. EWTX: on his buy day the bars had hung for fifteen days on
#: a shelf resting on his resistance, none back at his support. MATX: the same shelf on his resistance, a box on
#: his last receding day.
_HIS_BOX_GIVES_WAY_BEFORE_HIS_BUY = {"BODI:2026-04-21": (10.36, 9.30), "EWTX:2026-03-31": (31.29, 29.46),
                                     "MATX:2026-07-01": (197.63, 190.16)}


def test_his_own_pair_is_a_pair_the_rule_lists_and_a_box_by_it_on_his_drawings(his_reads):
    """His own two anchors, read by the rule he settled: two swing ends a swing connects, a counter move that took
    back a part only, at least a daily range tall, the bars back on both rails and fifteen days by his buy day —
    on every drawing but the five named. And sentences 9 and 10 on his own box: by his buy day no later pair takes
    its place by the reader's two rules, but on the three named."""
    from engine_alpha.two_eyes import walk

    not_listed, gives_way = [], {}
    for row in his_reads:
        pair, key = row["his_pair"], row["key"]
        if pair is None:
            not_listed.append(key)
            continue
        assert pair.unfit is None, f"{key}: {pair.unfit}"
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


#: His drawings on which the reader's box opens on the other rail than his, and why.
_OPENS_ON_THE_OTHER_RAIL = {
    "ROIV:2026-06-17": "the reader shows a later pair inside his box that opens on its low (29.64 / 28.67)",
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
                       "resistance's area by six cents and a box since Mon 09/03/2026, takes his box's place",
}


#: THE BOARD of the core sitting (Thu 01/10/2026), drawing by drawing: the reader's box on his last receding day
#: against his own two lines. Pinned so that a change which loses one of his boxes, or gains one, is a red test
#: and a deliberate edit here. HIS BOX: both lines to the cent.
_READS_HIS_BOX = (
    "ANRO:2026-08-12", "AVT:2026-04-08", "DSGN:2026-03-31", "EGBN:2026-01-15", "EWTX:2026-03-31", "JAZZ:2026-02-24",
    "MRK:2026-08-10", "MS:2026-06-04", "NGL:2026-01-20", "NGL:2026-04-20", "NKTR:2026-04-10", "NOK:2026-02-17",
    "NTCT:2026-03-04", "PBT:2026-05-11", "SKYT:2026-04-13", "SYRE:2026-02-19", "UNF:2026-07-10", "VIK:2026-06-11",
    "VLO:2026-07-08", "WTS:2026-06-12", "YPF:2026-05-18")
#: CLOSE: both lines within half a daily range of his.
_READS_CLOSE_TO_HIS = (
    "BODI:2026-04-21", "BWA:2026-05-05", "DLX:2026-04-13", "DRTS:2026-04-15", "FOSL:2026-02-18", "MDT:2026-07-24",
    "MSGS:2026-05-22", "ORMP:2026-04-13", "PKE:2026-04-07", "RGR:2026-03-19", "SILC:2026-04-13")
#: ANOTHER BOX, and why, each measured on the bars.
_READS_ANOTHER_BOX = {
    "ALB:2026-04-13": "his other reading: the pair of the run's own top, 195.69 (Tue 27/01/2026) / 164.15, shown from "
                      "Wed 25/02/2026, the far view saying the rise ended on that top. Before it the reader showed "
                      "179.14 / 160.02, four cents over his",
    "MATX:2026-07-01": "his pair lies across the resistance of the box shown before it (180.21 / 167.35: his support "
                       "176.99 is under that resistance's area), so it never took its place; on Tue 30/06/2026, his "
                       "last receding day, the shelf on his own resistance (197.63 / 190.16) became a box and did",
    "MTLS:2026-09-04": "the climax bar's own pair (7.00 / 6.60, one wide bar, Mon 01/06/2026) was a box first; his "
                       "pair is one wide bar a swing later (Tue 09/06/2026), across that box's support, and a pair "
                       "inside or across the shown box never takes its place",
    "ROIV:2026-06-17": "the bars came back to his resistance (30.33, Wed 11/03/2026) only on Fri 17/04/2026; by then "
                       "the reader showed a pair that opened later, and a shown line never moves back (ours)",
    "ST:2026-04-17": "the earlier top's pair (36.25, Thu 11/12/2025 / 32.83, Wed 17/12/2025) was a box on Mon "
                     "05/01/2026, the day of his own top; his pair (36.14 / 33.95) lies inside it, and a pair inside "
                     "the shown box never takes its place",
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
    assert sorted(got["HIS"]) == sorted(_READS_HIS_BOX) and len(got["HIS"]) == 21


def test_the_boxes_life_on_his_drawings_moves_only_forward_and_only_by_the_two_rules(his_reads):
    """Read with no memory on days up to his last receding day, the reader tells the same history: what a later
    day tells of the days before is what those days told. Every hand-over goes to a pair that opened later, on or
    after the day that pair became a box, by one of the two rules; and the box shown on his last receding day is
    still the box on his buy day, on every drawing but the one named."""
    from engine_alpha.two_eyes import walk

    hand_overs, changed_on_his_buy_day = 0, []
    for row in his_reads:
        result, key = row["result"], row["key"]
        told = [(life.pair.feet, life.shown_bar) for life in result.lives]
        for day in range(max(0, row["first_bar"] - 12), row["last_bar"], 7):
            on_day = [(life.pair.feet, life.shown_bar) for life in row["on"](day).lives]
            assert on_day == [t for t in told if t[1] <= day], f"{key}: {row['days'][day]:%a %d/%m/%Y} told otherwise"
        for old, new in zip(result.lives, result.lives[1:]):
            assert new.pair.opening_bar > old.pair.opening_bar, f"{key}: the shown line moved back"
            assert new.shown_bar >= new.pair.birth_bar and old.ended_bar is not None
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
#: 2,120 nights — and the box shown moved on 91 of them, every one a night the read itself says the newer box
#: took its place (the decisions record).
_REPLAYED = ("EGBN:2026-01-15", "MSGS:2026-05-22", "YPF:2026-05-18", "MRK:2026-08-10")


def test_read_night_after_night_as_the_scan_reads_the_shown_box_moves_only_the_night_the_newer_box_takes_its_place():
    """The proofs above read ONE prepared window and filter its turns by the day they were known. The scan cuts a
    new window every night. Read that way, night after night: the box shown changes only on the night the read
    itself says the newer box took its place, and the box of the night before is the one it hands over; on every
    other night the last three earlier boxes are told as the night before told them. And the LPS word: a night
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
                assert told[-2] == before[-1], \
                    f"{key}: on {when} the box shown the night before is not the box handed over"
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
    # From the box of October 2024 on — 24 boxes, the shown one last — both nights tell the same history.
    since = (12.49, dt.date(2024, 10, 21), 11.5, dt.date(2024, 10, 22))
    assert thursday[thursday.index(since):] == friday[friday.index(since):]
    assert len(thursday) - thursday.index(since) == 24
    # Before it, the window's first five months: three boxes on Thursday, five other boxes on Friday.
    assert (thursday.index(since), friday.index(since)) == (3, 5)
    assert not set(thursday[:3]) & set(friday[:5])


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN LIMIT, found by the core's blind check on Sun 27/09/2026 and narrowed by the rebuild of Thu 01/10/2026. "
    "The reader has no memory: it reads the boxes from the first trend end its two-year window holds, and the "
    "window's left edge moves a day a night. So the OLDEST boxes it records, those of the window's first months, "
    "are told differently on some nights no box took another's place (118 of 2,120 replayed nights on his 37 and "
    "the junk; before the rebuild 738 of 8,350). The last three earlier boxes were told differently on none of "
    "those nights, and the box SHOWN moved only on a hand-over's own night. The earlier boxes are the story's "
    "(task 12b): they are made independent of the window's edge before the story reads them, and that day this "
    "mark comes off deliberately."))
def test_the_oldest_boxes_of_the_record_are_the_same_boxes_the_night_after():
    thursday, friday = _flg_on_two_nights()
    assert thursday[:-1] == friday[:-1], \
        f"the first boxes of the record: {thursday[:2]} on Thursday, {friday[:2]} on Friday"
