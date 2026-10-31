"""The ends and the pairs (stages 2 and 3 of the walk): his eye for a rail (``rail_of``, ``bar_respects``,
``came_back``), the swings' end points (``swing_ends``), the end of the trend on the far view (``trend_ends``,
``first_foot``) and every pair of ends a swing connects, measured as a box candidate (``Pair``, ``measure``,
``pairs_from``). Pure functions of the bars' highs and lows, the line and each day's range; no close is read.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine_alpha import numbers as M


def _cmp(t, i):
    """Sign of turn ``i`` against the previous turn of its own kind (``i - 2`` on an alternating line)."""
    d = t[i][2] - t[i - 2][2]
    return 1 if d > 0 else (-1 if d < 0 else 0)


#: Why a listed pair can never be a box.
UNFIT_TALL = "under one daily range tall"


UNFIT_WHOLE_MOVE = "the counter move took back the whole move before it"


RESISTANCE, SUPPORT = "R", "S"


_BOTH = frozenset((RESISTANCE, SUPPORT))


def known_by(turns, bar: int) -> list:
    """The turns committed by ``bar``'s close: what a reader standing on that day has."""
    return [t for t in turns if t.knowable_bar is not None and t.knowable_bar <= bar]


# --------------------------------------------------------------------------- #
# Respect: his eye                                                            #
# --------------------------------------------------------------------------- #
def rail_of(price: float, R: float, S: float, area: float) -> Optional[str]:
    """The rail one end of a bar respects: the closer one, within the area of it on either side (a poke counts)."""
    to_r, to_s = abs(float(price) - float(R)), abs(float(price) - float(S))
    if min(to_r, to_s) > float(area):
        return None
    return RESISTANCE if to_r <= to_s else SUPPORT


def bar_respects(high: float, low: float, R: float, S: float, area: float) -> frozenset:
    """The rails a bar respects: each end counts for the rail it is closest to, within the area (his picture, Sat
    26/09/2026)."""
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
    """The first bar back at each rail after both anchors, ``(resistance, support)``: the rail the pair opened on
    first, the other by the first bar that respects it on that day or after (resting is respect; his SILC, DRTS)."""
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
    """The committed turns that are a swing's end: the bar on neither side beats the turn's bar. The other end of
    one wide bar counts only when the bar's first end is a swing's end (his PBT ruling); known the day after."""
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
            if before is None or before.bar != bar or before.kind == turn.kind or not M.WIDE_ENDS:
                continue
            if not M.GAP_BAR_LOW_IS_REACTION and turn.kind == "valley" and low[bar] > high[bar - 1]:
                continue                # a gap bar's own low is where the rise landed, not the reaction
            wide = True
        out.append(End(index=index, bar=bar, kind=turn.kind, price=float(turn.price),
                       known_bar=max(int(turn.knowable_bar), bar + 1), wide=wide))
    return out


# --------------------------------------------------------------------------- #
# Stage 2: the end of the trend                                               #
# --------------------------------------------------------------------------- #
def trend_ends(far_turns) -> list:
    """Every run of the far view that has ended, oldest first: two peaks and two valleys each above the last (the
    mirror for a decline), ended by the first swing that fails to continue it; its climax, start and day known."""
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
    """Where a trend end's walk starts, as an index into ``ends``: the first swing end at the climax's level in its
    run (his PBT: a later poke over the top does not move his line); None when none stands there."""
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
    """A swing connects the two ends: between their bars the top is the highest high and the low the lowest low."""
    top, bottom = (first, second) if first.kind == "peak" else (second, first)
    span = slice(first.bar, second.bar + 1)
    return bool(high[span].max() <= top.price and low[span].min() >= bottom.price)


def move_began(high, low, end: End, before: Optional[int] = None) -> float:
    """Where the move into a swing's end began, by bars alone: for a top the lowest low since the price was last
    above it, for a low the mirror. ``before`` reads the move up to that bar only (one wide bar's other end out)."""
    stop = end.bar + 1 if before is None else int(before)
    if stop <= 0:
        return float(end.price)
    if end.kind == "peak":
        beyond = np.flatnonzero(high[:stop] > end.price)
        return float(low[(int(beyond[-1]) + 1 if len(beyond) else 0):stop].min(initial=end.price))
    beyond = np.flatnonzero(low[:stop] < end.price)
    return float(high[(int(beyond[-1]) + 1 if len(beyond) else 0):stop].max(initial=end.price))


def _a_part_only(high, low, first: End, second: End) -> Optional[tuple]:
    """``(top_first, began)`` when the second end took back a part only of the move before the first, else None;
    one wide bar is read in either order."""
    orders = [(first, second)]
    if first.bar == second.bar:
        orders.append((second, first))
    for one, other in orders:
        began = move_began(high, low, one, before=one.bar if one.bar == other.bar else None)
        if (other.price > began) if one.kind == "peak" else (other.price < began):
            return one.kind == "peak", began
    return None


def measure(high, low, ranges, first: End, second: End, joined: int, read_bar: int) -> Pair:
    """One pair a swing connects, measured in its second anchor's daily range: unfit under one range tall or when
    the counter move took back the whole move; a box on the later of both come-backs, its fifteenth day, its listing."""
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
    """Every pair a swing connects, from the first trend end's first foot on, in the order they open: each end with
    the ends of the other kind after it while it stays the extreme on its side; listed no sooner than a trend end."""
    walked = [(t["foot_bar"], t["known_bar"]) for t in trends if t.get("foot_bar") is not None]
    climaxes = {int(t["climax_bar"]) for t in trends}
    out = []
    for a, first in enumerate(ends):
        known = min((k for foot_bar, k in walked if foot_bar <= first.bar), default=None)
        if known is None:
            continue                    # before every trend end: nothing has ended yet
        span = slice(first.bar, read_bar + 1)
        if first.kind == "peak":
            past = np.flatnonzero(high[span] > first.price)
            lows = low[span]
            if not M.GAP_BAR_LOW_IS_REACTION and first.bar > 0 and low[first.bar] > high[first.bar - 1]:
                lows = np.concatenate(([np.inf], lows[1:]))      # the gap bar's own low is not the reaction's
            running = np.minimum.accumulate(lows)
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
            if second.bar == first.bar and not M.ONE_BAR_PAIR:
                continue                # an end never pairs with the other end of its own bar
            if second.bar == first.bar and first.bar in climaxes and not M.CLIMAX_BAR_OWN_REACTION:
                continue                # a trend end's climax bar is never its own reaction
            joined = max(first.known_bar, second.known_bar, int(known))
            out.append(measure(high, low, ranges, first, second, joined, read_bar))
    return out
