"""Stages 2, 3 and 4 of the two-eyes reader: the end of the trend, the rule of the pair, and the box's life.

Rebuilt on Thu 01/10/2026 on the rule he settled at the core sitting (ten sentences typed out to him on Wed
30/09/2026, his answer to each the day after; both in the build run's request file and in the decisions record).
Pure functions of the bars' highs and lows, the line (stage 1) and each day's range: no close is read, nothing is
graded, and the only numbers are the seven in ``two_eyes_numbers``. Everything is computed from what is known on the
read day, and the box shown changes only forward, so a reader with no memory gives the same answer as one that
watched every day (``tests/engine/test_walk.py`` proves it on his drawings, on the fixture charts and on
hand-built bars).

His sentences, and where each lives:

1. *A rail sits only on the end point of a swing* — ``swing_ends``: a turn of the line whose bar the bar on
   neither side beats. His words of Mon 28/09/2026 on the reader's PBT box: *"we only start to anchor from the
   end point of previous swings ... your Pick came from the middle of a swing in the direction of the trend with
   out there being a counter move to begin with"*.
2. *A box's two rails are the two ends of one counter move; after a swing up the top comes first* — a pair is two
   swing ends in the order they printed (``measure``).
3. *The two ends can be one wide bar's own high and low* — the other end of a bar whose first end is a swing's
   end is one too, and a one-bar pair is read in whichever order makes it a counter move.
4. *The counter move is smaller than the move it comes off*; his answer: *"most Automatic rallies (AR) cover only
   part of the previous move if a counter move is bigger it contributes already to a new counter trend!"* — a
   pair whose second end takes back the whole move before its first is listed and never a box
   (``UNFIT_WHOLE_MOVE``; the move before is read on the bars, ``move_began``).
5. *The first pair tried is the climax and its reaction; if the bars do not come back to both rails, one pair to
   the right*; his answer: *"only if a swing connects between them, we cannot allow for dismemberd anchor
   paring"* — every pair is two ends a swing connects: from the first to the second bar the top is the highest
   high and the low the lowest low. ``pairs_from`` holds to it as it lists (an end is paired only while no bar
   has gone past it, and only with the running extreme of the other side); ``connects`` says the same of one
   pair, and the tests hold the list to it. The pairs are listed in the order they open, from the first trend
   end on.
6. *Come back*; his answer: *"if by "Come back" to be counted as respect to the respective rail that bar is
   closest too then yes"* — each end of a bar counts for the rail it is closest to, within the rail's area
   (``rail_of``, ``bar_respects``). On the pictures (Thu 01/10/2026): *"Silc supposed to work due the much
   respect of the support"* — bars RESTING on a rail respect it, they need not have left it first — and
   *"why would DRTS move away as it almost perfectly respect both boundaries"* — a reaction low the bars
   never return to is no respected rail (``came_back``).
7. *A box on its fifteenth day, or later if the bars take longer*; his answer: *"we have to account for the bases
   eventual recovery ... looking at the base structure as whole rather and seeing that it fits rather then
   rejecting it out right"* — the birth is the later of both come-backs, the fifteenth day and the listing day,
   however late (``measure``).
8. *A run past a rail never unmakes a pair by itself* — nothing here drops a pair for a bar beyond a rail. On
   ALB's breach of Tue 27/01/2026 he said: *"that breach is not an upthrust in fact there is a later on
   25/02/2026 its just that those pairs could be used to fit the box, even a later pair could work if that
   movement in 20/1 -> 27/1 and the crash afterwards could be treated as the place where the trend ends"*.
9. *Once a box, it stays a box through dips and pokes that come back* — a later pair inside or across the shown
   box never takes its place (``left_for_good`` asks that it lie beyond). And a dip that comes back LATE: the
   reader reads day by day, so when the price left the box downward for fifteen days it followed it to the lower
   pair; the day the bars are back at both rails of the box it gave up and no longer come back to the lower
   pair's support, that box takes its place back (``came_back_to``; his STGW, Fri 23/10/2026). His ROIV picture (Thu 01/10/2026: a red dash on each bar that meets one of his two lines,
   none on the days under the support nor on the two days over the resistance) and his word on the boxes the
   reader never went back to: *"go ahead with the five earlier boxes I think as long as the engine understand
   that there is a setup there I'm happy"*.
10. *The box gives way to a newer pair only when the price left it and did not come back: the bars now hang on
    the newer rails and no longer come back to the old ones* — ``left_for_good``, judged on every day from the
    day the newer pair is a box, both halves: over the last fifteen trading days the bars came back to both
    rails of the newer pair, and not to the shown box's FAR rail, the one the price would have to cross coming
    back: its support when the newer pair lies above, its resistance when it lies below (his DSGX, Sat
    18/10/2026: a spring that touched a lower pair's rails while the bars still came back to the box's
    resistance had the box "left downward" fifteen days later, with the price over its top).

His earlier words that still place the rest: *"usually when a trend ends it reaches some sort of climax ->
counter move -> consolidation ... so were looking for the first instance that a consolidation is respected!"*
(Sun 06/09/2026: the first pair to become a box is shown); *"Trend end is a single mark before the beginning of
the consolidation's base"* (Sat 26/09/2026: the far view's ended runs, ``trend_ends``); *"We can't start the
anchor from the opposite direction of the trend if we are still inside that trend"* (Mon 27/07/2026:
``inside_a_live_trend``); *"Lets go with 15 days"* (Sat 12/09/2026); *"one way to find out whenever a bar is
respecting support resistance or both is to look at their High and Low values ... whenever they are slightly
poking out or not does not matter one bit"* (Sat 26/09/2026).

Ours, recorded as ours in the decisions record (Thu 01/10/2026): the order of the two come-backs — the rail the
pair opened on first, the other rail on that day or after, so the price has been at the other rail in between
and the day after a reaction low, still resting on it, is no come-back by itself; the move before read by bars
alone (for a top, the lowest
low since the price was last above it); the first foot of a trend end's walk (the first swing end of the climax's
level in its run: a later poke does not move his line); the live-trend rule as a hand-over at the newer box's
birth, and that a rise whose climax printed after the shown box was born swallows it only when the bars did
not come back to both its rails within the fifteen days from that top, judged on the last of them (his EXPD,
Sat 18/10/2026: a poke a range over a box already born that came back is the box's own; the mirror for a fall
is not built, his WTS), and the same for a rise that topped after a pair's second anchor and before it was a box
when the bars knew the pair's rails before it opened and the price stayed in it (his HCA, Sat 24/10/2026; how many
bars, how far back and how near are ours, ``KNOWN_RAILS_*``); "beyond" as resting on the shown rail's area or further; how long "no longer" is (his fifteen days); which
old rail "no longer come back" is read on (the far one; the "not both" it was until his DSGX, Sat 18/10/2026, let a
box be left downward while the bars sat on its resistance); that
a shown line moves back only to the box it gave up, and only after a DIP (when the price left a box upward and a
box above took its place, a fall back into the old box is the newer box's own dip: his ST, where the spring under
his box is at both rails of the box under it); the unit of a pair (the range of its second anchor's day); the day
a handed-over box's lines stop (the newer pair's opening).

The switches (Wed 28/10/2026; his word: *"we've got to write the engine in a certain way that will allow us to
easily tune it in the right direction"*): four readings of his that were tried as monkeypatches are named switches
in ``two_eyes_numbers``, each read where the walk decides and each ON by default, so the walk reads as built —
``ONE_BAR_PAIR`` (``pairs_from``: an end may pair with the other end of its own bar), ``GAP_BAR_LOW_IS_REACTION``
(``swing_ends`` and ``pairs_from``: a gap bar's own low may be the reaction), ``WIDE_ENDS`` (``swing_ends``:
the other end of one wide bar is listed) and ``CLIMAX_BAR_OWN_REACTION`` (``pairs_from``: a pair opening on a
trend end's climax bar may take its second anchor from that bar). A reading is measured as one switch off plus one run of
``tools.calibration.fires_board`` on his live drawings; none is ruled on.

The election by respect (Fri 30/10/2026; ``RESPECT_ELECTS``, off by default): his direction after the mini stage,
*"Still on High/LOW values only but with out being hung on extremes"* and *"we should have some sort 'Close Enough'
approach to count touches"*. Among the pairs that are boxes the one the bars respect most is shown: each bar, in its
own daily range, counts for a pair when an end of it touches a rail and against it when the whole bar sits beyond
one (``respect_marks``), and a pair takes the shown box's place on the first day it leads by the margin over the days
since the later of the two opened (``out_respected``). Under it the left-for-good, way-back and wraps hand-overs are
not asked; the live-trend and tried-first hand-overs stay. The window, the margin and the area are OURS.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine_alpha import numbers as M
from engine_alpha.box.handover import (CAME_BACK, LIVE_TREND, RESPECTED, TRIED_FIRST, WRAPS, Life, lives)
from engine_alpha.box.pairs import Pair, first_foot, pairs_from, swing_ends, trend_ends
from engine_alpha.record import LINES_NO_LPS, NO_LINES, ROLE_EARLIER, ROLE_PARENT, Box, Line, Step


@dataclass(frozen=True)
class Walk:
    """What the walk found on one read: the trend ends, the swings' end points, every pair it listed (in the
    order they open, keyed by feet), the box shown or None, the turns, and the box's life as THIS read tells it
    (``lives``): the box shown, and before it the boxes this read's own window says were handed over, each ended.
    The reader keeps no memory, so the earlier ones are not a record of what an earlier night showed."""
    ends: tuple                     # the trend ends
    pairs: dict
    winner: Optional[Pair]
    turns: tuple
    days: Optional[tuple] = None
    lives: tuple = ()
    swing_ends: tuple = ()


def elect(turns, far_turns, ranges, high, low, days=None, read_bar: Optional[int] = None) -> Walk:
    """Stages 2 to 4 on what is known on the read day (``read_bar``: by default the last day any turn was
    known). The swings' end points; the trend ends and the first foot of each; every pair a swing connects from
    the first trend end's first foot on; and the box's life."""
    turns = list(turns)
    if read_bar is None:
        read_bar = max((t.knowable_bar for t in turns if t.knowable_bar is not None), default=0)
    read_bar = int(read_bar)
    high, low = np.asarray(high, dtype=float), np.asarray(low, dtype=float)
    ends = swing_ends(turns, high, low, read_bar)
    trends = []
    for trend in trend_ends(far_turns):
        if trend["known_bar"] > read_bar:
            continue
        foot = first_foot(ends, trend, ranges)
        trends.append({**trend, "foot": foot, "foot_bar": None if foot is None else ends[foot].bar})
    walked = [t for t in trends if t["foot"] is not None]
    pairs = {}
    for pair in pairs_from(ends, walked, high, low, ranges, read_bar):
        pairs.setdefault(pair.feet, pair)
    history = lives(pairs.values(), walked, high, low, read_bar, ranges=ranges)
    return Walk(ends=tuple(trends), pairs=pairs, winner=history[-1].pair if history else None, turns=tuple(turns),
                days=None if days is None else tuple(days), lives=history, swing_ends=tuple(ends))


# --------------------------------------------------------------------------- #
# The record: the box, the trail, the state word                              #
# --------------------------------------------------------------------------- #
def _when(walk: Walk, bar: Optional[int]) -> str:
    if bar is None:
        return "not yet"
    if walk.days is not None and 0 <= bar < len(walk.days):
        return f"{walk.days[bar]:%a %d/%m/%Y}"
    return f"bar {bar}"


def _end_words(walk: Walk, trend: dict) -> str:
    what = "a rise" if trend["kind"] == "BC" else "a decline"
    return (f"the end of {what}: its climax {trend['climax_price']:.2f} on {_when(walk, trend['climax_bar'])}, "
            f"known {_when(walk, trend['known_bar'])}")


def _pair_words(walk: Walk, pair: Pair) -> str:
    r, s = walk.turns[pair.r_index], walk.turns[pair.s_index]
    opens = "opens on resistance" if pair.top_first else "opens on support"
    words = (f"R {pair.R:.2f} ({r.day:%a %d/%m/%Y}) / S {pair.S:.2f} ({s.day:%a %d/%m/%Y}), {opens}, measured in "
             f"a {pair.unit:.2f} daily range, listed {_when(walk, pair.joined_bar)}")
    if pair.unfit is not None:
        return words + f"; never a box: {pair.unfit}"
    back = (f"the bars came back to resistance {_when(walk, pair.r_back)} and to support "
            f"{_when(walk, pair.s_back)}")
    if pair.birth_bar is not None:
        why = " (its fifteenth day)" if pair.birth_bar == pair.fifteenth else ""
        return words + f"; {back}; a box on {_when(walk, pair.birth_bar)}{why}"
    if pair.r_back is None or pair.s_back is None:
        return words + f"; not a box yet: {back}"
    return words + f"; {back}; not a box yet: its fifteenth day is {_when(walk, pair.fifteenth)}"


def _hand_over_words(walk: Walk, life: Life, new: Life) -> str:
    old, pair = life.pair, new.pair
    if new.why == LIVE_TREND:
        trend = new.trend_end
        what = "rise" if trend["kind"] == "BC" else "decline"
        why = (f"it was anchored inside a {what} that had not ended (its climax {trend['climax_price']:.2f} on "
               f"{_when(walk, trend['climax_bar'])}, known {_when(walk, trend['known_bar'])})")
    elif new.why == CAME_BACK:
        return (f"the box {old.R:.2f} / {old.S:.2f} ended {_when(walk, life.ended_bar)}: the dip came back, the "
                f"bars came back to both rails of the box before it, and {pair.R:.2f} / {pair.S:.2f} took its "
                f"place again on {_when(walk, new.shown_bar)}")
    elif new.why == WRAPS:
        return (f"the box {old.R:.2f} / {old.S:.2f} ended {_when(walk, life.ended_bar)}: one bar's own high and low, "
                f"and the bars never came back to one of its rails; {pair.R:.2f} / {pair.S:.2f}, the pair inside them "
                f"they do come back to, took its place on {_when(walk, new.shown_bar)}")
    elif new.why == RESPECTED:
        since = _when(walk, max(old.opening_bar, pair.opening_bar))
        return (f"the box {old.R:.2f} / {old.S:.2f} ended {_when(walk, life.ended_bar)}: since {since} the bars respect "
                f"{pair.R:.2f} / {pair.S:.2f} more, {new.lead} touches ahead (an end of a bar within "
                f"{float(M.RESPECT_AREA_RANGES):g} of its day's range of a rail counts for the pair, a bar wholly beyond a "
                f"rail against it), and it took its place on {_when(walk, new.shown_bar)}")
    elif new.why == TRIED_FIRST:
        which = "the earlier reaction low" if pair.top_first else "the earlier reaction high"
        return (f"the box {old.R:.2f} / {old.S:.2f} ended {_when(walk, life.ended_bar)}: {pair.R:.2f} / "
                f"{pair.S:.2f}, the same anchor and {which}, was tried before it and became a box on "
                f"{_when(walk, new.shown_bar)}, and took its place")
    else:
        side = "above" if pair.S >= old.R - old.area else "below"
        why = f"the price left it {side} and the bars no longer came back to both its rails"
    return (f"the box {old.R:.2f} / {old.S:.2f} ended {_when(walk, life.ended_bar)}: {why}, and {pair.R:.2f} / "
            f"{pair.S:.2f} took its place on {_when(walk, new.shown_bar)}")


def _box_record(walk: Walk, pair: Pair, role: str, end_day=None) -> Box:
    r, s = walk.turns[pair.r_index], walk.turns[pair.s_index]
    return Box(resistance=Line(pair.R, r.day), support=Line(pair.S, s.day), opened_day=min(r.day, s.day),
               end_day=end_day, role=role, daily_range=pair.unit)


def _trend_before(walk: Walk, pair: Pair) -> Optional[dict]:
    """The trend end the box follows: the last one whose walk starts on or before the box's first anchor."""
    before = [t for t in walk.ends if t.get("foot_bar") is not None and t["foot_bar"] <= pair.opening_bar]
    return max(before, key=lambda t: t["foot_bar"]) if before else None


def record(walk: Walk, keep_listing: bool = False) -> tuple:
    """The read's record from the walk: ``(boxes, trail, state)``. The boxes are every box the read handed over,
    in order, each ended on the day its lines stop (``ROLE_EARLIER``), then the box shown (``ROLE_PARENT``). The
    trail opens with each hand-over in words, then the trend end the shown box follows, then the box; with
    ``keep_listing`` every other pair the walk listed from that trend end on follows, in the order they open —
    words only, the boxes and the state identical."""
    walked = [t for t in walk.ends if t.get("foot_bar") is not None]
    if not walked:
        return (), (), NO_LINES
    won = walk.winner
    if won is None:
        steps = [Step("trend end", _end_words(walk, walked[-1]))]
        if keep_listing:
            steps.extend(Step("listed", _pair_words(walk, p)) for p in walk.pairs.values())
        return (), tuple(steps), NO_LINES
    steps = [Step("hand-over", _hand_over_words(walk, life, new)) for life, new in zip(walk.lives, walk.lives[1:])]
    trend = _trend_before(walk, won)
    if trend is not None:
        steps.append(Step("trend end", _end_words(walk, trend)))
    steps.append(Step("box", _pair_words(walk, won)))
    if keep_listing:
        since = trend["foot_bar"] if trend is not None else won.opening_bar
        steps.extend(Step("listed", _pair_words(walk, p)) for p in walk.pairs.values()
                     if p.opening_bar >= since and p.feet != won.feet)
    day_of = {t.bar: t.day for t in walk.turns}     # a box's lines stop on a turn's bar: its day is the turn's
    boxes = [_box_record(walk, life.pair, ROLE_EARLIER, day_of[life.ended_bar]) for life in walk.lives[:-1]]
    boxes.append(_box_record(walk, won, ROLE_PARENT))
    return tuple(boxes), tuple(steps), LINES_NO_LPS
