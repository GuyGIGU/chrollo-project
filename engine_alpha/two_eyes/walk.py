"""Stages 2, 3 and 4 of the two-eyes reader: the end of the trend, the rule of the pair, and the box's life.

Rebuilt on Thu 01/10/2026 on the rule he settled at the core sitting (ten sentences typed out to him on Wed
30/09/2026, his answer to each the day after; both in the build run's request file and in the decisions record).
Pure functions of the bars' highs and lows, the line (stage 1) and each day's range: no close is read, nothing is
graded, and the only numbers are the four in ``two_eyes_numbers``. Everything is computed from what is known on the
read day, and the box shown changes only forward, so a reader with no memory gives the same answer as one that
watched every day (``tests/engine/test_two_eyes_walk.py`` proves it on his drawings, on the fixture charts and on
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
   pair; the day the bars are back at both rails of the box it gave up, that box takes its place back
   (``came_back_to``). His ROIV picture (Thu 01/10/2026: a red dash on each bar that meets one of his two lines,
   none on the days under the support nor on the two days over the resistance) and his word on the boxes the
   reader never went back to: *"go ahead with the five earlier boxes I think as long as the engine understand
   that there is a setup there I'm happy"*.
10. *The box gives way to a newer pair only when the price left it and did not come back: the bars now hang on
    the newer rails and no longer come back to the old ones* — ``left_for_good``, judged on every day from the
    day the newer pair is a box, both halves: over the last fifteen trading days the bars came back to both
    rails of the newer pair, and not to both rails of the shown box.

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
birth; "beyond" as resting on the shown rail's area or further; how long "no longer" is (his fifteen days); that
a shown line moves back only to the box it gave up, and only after a DIP (when the price left a box upward and a
box above took its place, a fall back into the old box is the newer box's own dip: his ST, where the spring under
his box is at both rails of the box under it); the unit of a pair (the range of its second anchor's day); the day
a handed-over box's lines stop (the newer pair's opening).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine_alpha import two_eyes_numbers as M
from engine_alpha.two_eyes.record import LINES_NO_LPS, NO_LINES, ROLE_EARLIER, ROLE_PARENT, Box, Line, Step
from engine_alpha.two_eyes.runs import _cmp

__all__ = ["End", "Life", "Pair", "Walk", "bar_respects", "came_back", "came_back_to", "connects", "elect",
           "first_foot", "inside_a_live_trend", "known_by", "left_for_good", "lies_beyond", "lives", "measure",
           "move_began",
           "pairs_from", "rail_of", "record", "swing_ends", "trend_ends", "CAME_BACK", "FIRST_BOX", "LEFT_FOR_GOOD", "TRIED_FIRST",
           "LIVE_TREND", "LINES_NO_LPS", "UNFIT_TALL", "UNFIT_WHOLE_MOVE"]

#: Why a listed pair can never be a box.
UNFIT_TALL = "under one daily range tall"
UNFIT_WHOLE_MOVE = "the counter move took back the whole move before it"

#: Why a box is shown.
FIRST_BOX = "the first pair to become a box"
#: His GFR (Thu 16/10/2026): a pair off the SAME opening anchor with an EARLIER second anchor — the climax and its
#: reaction before the pair one swing to its right — was tried first (sentence 5) and takes the place the day it is
#: a box. A pair that opened on another anchor never comes back this way (the Tested-DEAD rows of 2026-10-01).
TRIED_FIRST = "the pair tried before it became a box"
LIVE_TREND = "the box before it was anchored inside a live trend"
LEFT_FOR_GOOD = "the price left the box before it and the bars no longer came back to both its rails"
CAME_BACK = "the dip came back: the bars are back at both rails of the box it had given up"

RESISTANCE, SUPPORT = "R", "S"
_BOTH = frozenset((RESISTANCE, SUPPORT))


def known_by(turns, bar: int) -> list:
    """The turns committed by ``bar``'s close: what a reader standing on that day has."""
    return [t for t in turns if t.knowable_bar is not None and t.knowable_bar <= bar]


# --------------------------------------------------------------------------- #
# Respect: his eye                                                            #
# --------------------------------------------------------------------------- #
def rail_of(price: float, R: float, S: float, area: float) -> Optional[str]:
    """The rail one end of a bar respects: the one it is closest to, when it is within the area of it, on either
    side of it. Poking out is the same distance as stopping short."""
    to_r, to_s = abs(float(price) - float(R)), abs(float(price) - float(S))
    if min(to_r, to_s) > float(area):
        return None
    return RESISTANCE if to_r <= to_s else SUPPORT


def bar_respects(high: float, low: float, R: float, S: float, area: float) -> frozenset:
    """The rails a bar respects — his picture of Sat 26/09/2026 and his answer to sentence 6: each end of the bar
    counts for the rail it is closest to. A bar whose high touches resistance and whose low touches support
    respects both; small bars low in the box rest on support; a bar above resistance whose low is close to it
    respects resistance."""
    return frozenset(rail for rail in (rail_of(high, R, S, area), rail_of(low, R, S, area)) if rail is not None)


def _respects(high, low, R: float, S: float, area: float) -> tuple:
    """``bar_respects`` over whole arrays: for each bar, does it respect resistance, does it respect support."""
    out = []
    for own, other in ((R, S), (S, R)):
        hits = np.zeros(len(high), dtype=bool)
        for values in (high, low):
            near, far = np.abs(values - own), np.abs(values - other)
            hits |= (near <= area) & ((near <= far) if own == R else (near < far))
        out.append(hits)
    return out[0], out[1]


def came_back(high, low, R: float, S: float, area: float, r_bar: int, s_bar: int, read_bar: int,
              top_first: bool) -> tuple:
    """The first bar that came back to each rail, later than both anchors: ``(resistance, support)``, each a bar
    or None. A bar comes back to a rail when it respects it — resting on it is respect, the price need not have
    left it first (his SILC: the bars rest on support for weeks). The rail the pair opened on is come back to
    first; the other rail by the first bar that respects it on that day or after: the price has been at the
    other rail in between, so the day after a reaction low, still resting on it, is no come-back by itself
    (his DRTS: the climax 7.89 and its reaction 6.23, a low the base never returned to)."""
    second = max(r_bar, s_bar)
    if second + 1 > read_bar:
        return None, None
    on_r, on_s = _respects(high[second + 1:read_bar + 1], low[second + 1:read_bar + 1], R, S, area)
    lead, follow = (on_r, on_s) if top_first else (on_s, on_r)
    first = np.flatnonzero(lead)
    if not len(first):
        return None, None
    lead_back = second + 1 + int(first[0])
    then = np.flatnonzero(follow[int(first[0]):])
    follow_back = lead_back + int(then[0]) if len(then) else None
    return (lead_back, follow_back) if top_first else (follow_back, lead_back)


# --------------------------------------------------------------------------- #
# Sentences 1 and 3: the swings' end points                                   #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class End:
    """A swing's end point: a turn of the line whose bar the bar on neither side beats."""
    index: int                      # its turn, in the turns the walk was given
    bar: int
    kind: str                       # "peak" | "valley"
    price: float
    known_bar: int                  # the close after its bar, never before the line committed it
    wide: bool = False              # the other end of one wide bar whose first end is a swing's end


def swing_ends(turns, high, low, read_bar: int) -> list:
    """The line's committed turns that are a swing's END by the bars: the high of the bar on neither side is
    higher (the mirror for a low). A turn the line made out of one wide bar's own high and low, inside a move
    still running, is not one — his PBT ruling. The other end of one wide bar counts when the bar's first end
    is itself a swing's end and the bar after does not beat it (sentence 3). An end is known the day after its
    bar: the next bar has to be seen."""
    out = []
    for index, turn in enumerate(turns):
        bar = int(turn.bar)
        if turn.knowable_bar is None or turn.knowable_bar > read_bar or bar + 1 > read_bar:
            continue
        values, sign = (high, 1.0) if turn.kind == "peak" else (low, -1.0)
        if sign * values[bar + 1] > sign * values[bar]:
            continue
        wide = False
        if bar > 0 and sign * values[bar - 1] > sign * values[bar]:
            before = out[-1] if out else None
            if before is None or before.bar != bar or before.kind == turn.kind:
                continue
            wide = True
        out.append(End(index=index, bar=bar, kind=turn.kind, price=float(turn.price),
                       known_bar=max(int(turn.knowable_bar), bar + 1), wide=wide))
    return out


# --------------------------------------------------------------------------- #
# Stage 2: the end of the trend                                               #
# --------------------------------------------------------------------------- #
def trend_ends(far_turns) -> list:
    """Every run of the far view that has ended, oldest first: at least two peaks and two valleys each above the
    last (the mirror for a decline), ended by the first swing that fails to continue it. Each carries its
    climax, the bar its run began on (the low a rise came off, the high a decline came off) and the day the end
    was known — the close that committed the swing that ended the run."""
    t = [(int(tr.bar), tr.kind, float(tr.price), tr.knowable_bar) for tr in far_turns if tr.knowable_bar is not None]
    out = []
    direction, start = 0, None
    i = 3
    while i < len(t):
        if direction == 0:
            first, second = _cmp(t, i - 1), _cmp(t, i)
            if first != 0 and first == second:
                direction, start = first, i - 3
            i += 1
            continue
        if _cmp(t, i) == direction:
            i += 1
            continue
        want = "peak" if direction > 0 else "valley"
        climax = max(k for k in range(start, i) if t[k][1] == want)
        began = min(k for k in range(start, i) if t[k][1] != want)
        out.append({"kind": "BC" if direction > 0 else "SC", "climax_bar": t[climax][0],
                    "climax_price": t[climax][2], "start_bar": t[began][0], "end_bar": t[i][0],
                    "known_bar": int(t[i][3])})
        direction, start = 0, None
        i += 1
    return out


def first_foot(ends, trend_end: dict, ranges) -> Optional[int]:
    """Where a trend end's walk starts, as an index into ``ends``: the first swing end of the climax's level in
    its run — a later high that pokes a little over his top does not move his line (PBT: 22.71 over his 22.65).
    The level is the rail area around the climax, in the range of the climax's day. None when no swing end of
    the run stands there (the climax itself is no swing's end)."""
    kind = "peak" if trend_end["kind"] == "BC" else "valley"
    area = float(M.LINE_WORD_AREA_ATR) * float(ranges[trend_end["climax_bar"]])
    for i, end in enumerate(ends):
        if end.bar > trend_end["climax_bar"]:
            break
        if end.kind == kind and end.bar >= trend_end["start_bar"] and \
                abs(end.price - trend_end["climax_price"]) <= area:
            return i
    return None


# --------------------------------------------------------------------------- #
# Stage 3: the rule of the pair                                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Pair:
    """One pair the walk listed: two swing ends a swing connects, its rails, its own unit, when the bars came
    back to each rail, and the day it became a box (None until it is one, or never when ``unfit``)."""
    r_index: int                    # the turns its two rails sit on
    s_index: int
    R: float
    S: float
    r_bar: int
    s_bar: int
    opening_bar: int
    second_bar: int
    top_first: bool                 # it opens on resistance, after a swing up; else on support
    unit: float                     # the daily range of its second anchor's day, never the read day's
    joined_bar: int                 # the day the reader could list it
    began: float                    # where the move before its first rail began
    r_back: Optional[int]           # the first bar that came back to each rail
    s_back: Optional[int]
    fifteenth: int                  # its fifteenth trading day from the first anchor
    birth_bar: Optional[int]
    unfit: Optional[str]

    @property
    def feet(self) -> tuple:
        return (self.r_index, self.s_index)

    @property
    def height(self) -> float:
        return self.R - self.S

    @property
    def area(self) -> float:
        return float(M.LINE_WORD_AREA_ATR) * self.unit


def connects(high, low, first: End, second: End) -> bool:
    """A swing connects the two ends: from the first bar to the second the top is the highest high and the low
    the lowest low — his *"we cannot allow for dismemberd anchor paring"*. The rule said of ONE pair: the reader
    lists by ``pairs_from``, which walks the same rule, and the tests hold its list to this."""
    top, bottom = (first, second) if first.kind == "peak" else (second, first)
    span = slice(first.bar, second.bar + 1)
    return bool(high[span].max() <= top.price and low[span].min() >= bottom.price)


def move_began(high, low, end: End, before: Optional[int] = None) -> float:
    """Where the move into a swing's end began, by bars alone: for a top, the lowest low since the price was last
    above it; for a low, the highest high since the price was last below it. ``before`` reads the move up to
    that bar only (one wide bar: the move into the bar, its own other end left out)."""
    stop = end.bar + 1 if before is None else int(before)
    if stop <= 0:
        return float(end.price)
    if end.kind == "peak":
        beyond = np.flatnonzero(high[:stop] > end.price)
        return float(low[(int(beyond[-1]) + 1 if len(beyond) else 0):stop].min(initial=end.price))
    beyond = np.flatnonzero(low[:stop] < end.price)
    return float(high[(int(beyond[-1]) + 1 if len(beyond) else 0):stop].max(initial=end.price))


def _a_part_only(high, low, first: End, second: End) -> Optional[tuple]:
    """Sentence 4 on one pair: ``(top_first, began)`` when the second end took back a part only of the move
    before the first; None when it took back all of it. One wide bar is read in either order."""
    orders = [(first, second)]
    if first.bar == second.bar:
        orders.append((second, first))
    for one, other in orders:
        began = move_began(high, low, one, before=one.bar if one.bar == other.bar else None)
        if (other.price > began) if one.kind == "peak" else (other.price < began):
            return one.kind == "peak", began
    return None


def measure(high, low, ranges, first: End, second: End, joined: int, read_bar: int) -> Pair:
    """One pair of swing ends a swing connects, read his way. Its unit is the range of its second anchor's day;
    under one of those tall, or with a counter move that took back the whole move before it, it is listed and
    never a box. It is a box on the later of: the bars back on both rails, its fifteenth trading day from the
    first anchor, and the day the reader could list it — however late, and whatever ran past a rail meanwhile.
    A birth after the read day is not a birth yet."""
    top, bottom = (first, second) if first.kind == "peak" else (second, first)
    unit = float(ranges[second.bar])
    area = float(M.LINE_WORD_AREA_ATR) * unit
    part = _a_part_only(high, low, first, second)
    unfit = None
    if top.price - bottom.price < float(M.BOX_MIN_HEIGHT_RANGES) * unit:
        unfit = UNFIT_TALL
    elif part is None:
        unfit = UNFIT_WHOLE_MOVE
    top_first, began = part if part is not None else (first.kind == "peak", move_began(high, low, first))
    r_back, s_back = came_back(high, low, top.price, bottom.price, area, top.bar, bottom.bar, read_bar,
                               bool(top_first))
    fifteenth = first.bar + int(M.BOX_DAYS) - 1
    birth = None
    if unfit is None and r_back is not None and s_back is not None:
        birth = max(r_back, s_back, fifteenth, int(joined))
        if birth > int(read_bar):
            birth = None
    return Pair(r_index=top.index, s_index=bottom.index, R=top.price, S=bottom.price, r_bar=top.bar,
                s_bar=bottom.bar, opening_bar=first.bar, second_bar=second.bar, top_first=bool(top_first),
                unit=unit, joined_bar=int(joined), began=float(began), r_back=r_back, s_back=s_back,
                fifteenth=fifteenth, birth_bar=birth, unfit=unfit)


def pairs_from(ends, trends, high, low, ranges, read_bar: int) -> list:
    """Every pair of swing ends a swing connects, from the first trend end's first foot on, in the order they
    open: each end with the ends of the other kind after it, for as long as it stays the extreme on its side (a
    top with each lower low after it until a bar goes over the top: one rail stays while the other moves). A
    pair is listed no sooner than the day a trend end before it was known."""
    walked = [(t["foot_bar"], t["known_bar"]) for t in trends if t.get("foot_bar") is not None]
    out = []
    for a, first in enumerate(ends):
        known = min((k for foot_bar, k in walked if foot_bar <= first.bar), default=None)
        if known is None:
            continue                    # before every trend end: nothing has ended yet
        span = slice(first.bar, read_bar + 1)
        if first.kind == "peak":
            past = np.flatnonzero(high[span] > first.price)
            running = np.minimum.accumulate(low[span])
        else:
            past = np.flatnonzero(low[span] < first.price)
            running = np.maximum.accumulate(high[span])
        limit = first.bar + (int(past[0]) if len(past) else read_bar + 1 - first.bar)
        for b in range(a + 1, len(ends)):
            second = ends[b]
            if second.bar >= limit:
                break
            if second.kind == first.kind or running[second.bar - first.bar] != second.price:
                continue
            joined = max(first.known_bar, second.known_bar, int(known))
            out.append(measure(high, low, ranges, first, second, joined, read_bar))
    return out


# --------------------------------------------------------------------------- #
# Stage 4: the box's life                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Life:
    """One box in the read's history: the pair, the day the reader began to show it and why, and — once a newer
    box took its place — the day its lines stop."""
    pair: Pair
    shown_bar: int
    why: str
    ended_bar: Optional[int] = None
    trend_end: Optional[dict] = None    # the trend end whose rise or fall swallowed the box before it


def inside_a_live_trend(shown: Pair, new: Pair, trends, day: int) -> Optional[dict]:
    """The shown pair opened on a top inside a rise that had not ended (on a low inside a fall): a trend end
    known by ``day`` whose run began before that anchor and whose walk starts after it, the newer pair opening
    on or after that first foot. His anchor rule — *"We can't start the anchor from the opposite direction of
    the trend if we are still inside that trend"*. Returns that trend end, or None."""
    found = None
    for trend in trends:
        if trend["known_bar"] > day or trend.get("foot_bar") is None or trend["foot_bar"] > new.opening_bar:
            continue
        if (trend["kind"] == "BC") != shown.top_first:
            continue                    # a rise swallows a pair that opened on a top, a fall one on a low
        if trend["start_bar"] < shown.opening_bar < trend["foot_bar"] and \
                (found is None or trend["known_bar"] < found["known_bar"]):
            found = trend               # the one known first
    return found


def _back_at_both(pair: Pair, high, low, first: int, days) -> np.ndarray:
    """For each day of ``days``: over the last fifteen trading days, never before ``first``, a bar was back at
    the pair's resistance and one at its support."""
    last = int(days[-1])
    on_r, on_s = _respects(high[first:last + 1], low[first:last + 1], pair.R, pair.S, pair.area)
    at_r, at_s = np.concatenate(([0], np.cumsum(on_r))), np.concatenate(([0], np.cumsum(on_s)))
    since = np.maximum(first, days - (int(M.BOX_DAYS) - 1))
    return (at_r[days - first + 1] > at_r[since - first]) & (at_s[days - first + 1] > at_s[since - first])


def lies_beyond(new: Pair, shown: Pair) -> bool:
    """The position half of his sentences 9 and 10: the newer pair lies BEYOND the shown box — its support in
    or above the shown resistance's area, or its resistance in or below the shown support's area. A pair that
    does not is inside or across the box: its own leg, a poke, a dip or a mini. The ONE judgment: the walk's
    take-over and the mini's home both ask it (council review 2026-10-09, finding 13)."""
    return new.S >= shown.R - shown.area or new.R <= shown.S + shown.area


def left_for_good(shown: Pair, new: Pair, high, low, since: int, read_bar: int) -> Optional[int]:
    """His sentences 9 and 10, judged on every day: the newer box lies beyond the shown one — its support in or
    above the shown resistance's area, or its resistance in or below the shown support's area — and *"the bars
    now hang on the newer rails and no longer come back to the old ones"*, both halves: over the last fifteen
    trading days, never before the newer pair opened, the bars came back to both rails of the newer pair and not
    to both rails of the shown box. The first such day from ``since`` on, never before the newer pair is a box;
    None when there is none by the read day. A pair inside or across the shown box is its own leg, a poke, a dip
    or a mini, and never takes its place; nor does a pair the bars have left (his MTLS: the pair of the July run,
    a box by the rule on a day the price was already back under it)."""
    if new.opening_bar <= shown.opening_bar:
        return None
    if not lies_beyond(new, shown):
        return None
    first, start = new.opening_bar, max(int(since), int(new.birth_bar))
    if start > read_bar:
        return None
    days = np.arange(start, read_bar + 1)
    left = ~_back_at_both(shown, high, low, first, days)
    if not left.any():
        return None
    gone = np.flatnonzero(left & _back_at_both(new, high, low, first, days))
    return int(days[gone[0]]) if len(gone) else None


def came_back_to(old: Pair, high, low, since: int, read_bar: int) -> Optional[int]:
    """His sentence 9 for a dip that comes back late — *"Once a box, it stays a box through dips under support
    ... that come back"*: the first day after ``since`` (the day the box was given up) on which the bars since
    that day, and of the last fifteen trading days, have come back to both its rails. None when there is none by
    the read day. A bar at a rail on or before ``since`` is not the price coming back."""
    first = int(since) + 1
    if first > read_bar:
        return None
    days = np.arange(first, read_bar + 1)
    back = np.flatnonzero(_back_at_both(old, high, low, first, days))
    return int(days[back[0]]) if len(back) else None


def _key(pair: Pair) -> tuple:
    """The order boxes are tried in: the day the pair became a box, then the earlier opening, then the earlier
    second anchor, then the tighter; the feet last, so equal pairs never tie."""
    return (pair.birth_bar, pair.opening_bar, pair.second_bar, pair.height, pair.r_index, pair.s_index)


def lives(pairs, trends, high, low, read_bar: int) -> tuple:
    """The box's life, read day by day on what each day knew. The first pair to become a box is shown. A pair
    that is a box takes its place when the shown pair was anchored inside a live trend (``inside_a_live_trend``:
    judged once that trend end is known) or on the first day the price has left it for good (``left_for_good``).
    Each of those goes to a pair that opened later. One hand-over goes back: when the price had left a box
    DOWNWARD and a lower pair took its place, the box takes its place back on the first day the bars are back at
    both its rails (``came_back_to``) — a dip that came back. And one goes to a SIBLING: a pair off the shown
    pair's own opening anchor with an earlier second anchor — the climax and its reaction, before the pair one
    swing to its right — was tried first (sentence 5), and takes the place on the day it becomes a box
    (``TRIED_FIRST``; his GFR, Thu 16/10/2026: *"the AR ended where I marked it ... the entire wave going down
    is already 2 swings and it's not part of the AR"*). Every box handed over stays, with the day its lines
    stop; the last one stands."""
    born = sorted((p for p in pairs if p.birth_bar is not None), key=_key)
    if not born:
        return ()
    out = []
    shown, day, why, trend, before = born[0], int(born[0].birth_bar), FIRST_BOX, None, None
    while True:
        best = None
        if why == LEFT_FOR_GOOD and before is not None and shown.S < before.R - before.area:
            # The shown pair lies under the box it took over from: the price had left that box downward.
            back = came_back_to(before, high, low, day, read_bar)
            if back is not None:
                best = ((back, ()), before, CAME_BACK, None)    # the empty key: it comes before a pair of that day
        for pair in born:
            if best is not None and pair.birth_bar > best[0][0]:
                break                   # born after the best day found: no later-born pair can come before it
            if pair.opening_bar == shown.opening_bar and pair.second_bar < shown.second_bar \
                    and int(pair.birth_bar) > day:
                # The sibling tried before the shown pair (sentence 5) is a box: it takes the place on its birth.
                order = (int(pair.birth_bar), _key(pair))
                if best is None or order < best[0]:
                    best = (order, pair, TRIED_FIRST, None)
                continue
            if pair.opening_bar <= shown.opening_bar:
                continue
            # The day this pair would take the shown box's place: the day a trend end that swallowed the shown
            # pair was known (never before the pair is a box), or the first day the price has left for good.
            when = took = by = None
            swallowed = inside_a_live_trend(shown, pair, trends, read_bar)
            if swallowed is not None:
                when, took, by = max(int(pair.birth_bar), int(swallowed["known_bar"])), LIVE_TREND, swallowed
            left = left_for_good(shown, pair, high, low, day, read_bar)
            if left is not None and (when is None or left < when):
                when, took, by = left, LEFT_FOR_GOOD, None
            if when is None:
                continue
            order = (max(when, day), _key(pair))
            if best is None or order < best[0]:
                best = (order, pair, took, by)
        if best is None:
            out.append(Life(shown, shown_bar=day, why=why, trend_end=trend))
            return tuple(out)
        out.append(Life(shown, shown_bar=day, why=why, ended_bar=max(best[1].opening_bar, shown.second_bar),
                        trend_end=trend))
        before = shown
        shown, day, why, trend = best[1], best[0][0], best[2], best[3]


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
    history = lives(pairs.values(), walked, high, low, read_bar)
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
