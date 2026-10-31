"""The walk (stages 2 to 4 of the alpha reader): the swings' end points and the trend ends, every pair a swing
connects from the first trend end on, and the box's life (``elect`` -> ``Walk``); then its record — the boxes, the
trail in words and the state word (``record``). Pure functions of the bars' highs and lows, the line and each day's
range, computed from what is known on the read day; the box shown changes only forward.
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
    """What the walk found on one read: the trend ends, every pair listed (keyed by feet, in opening order), the box
    shown or None, the turns, the days, the box's life as this read tells it (``lives``) and the swing ends."""
    ends: tuple                     # the trend ends
    pairs: dict
    winner: Optional[Pair]
    turns: tuple
    days: Optional[tuple] = None
    lives: tuple = ()
    swing_ends: tuple = ()


def elect(turns, far_turns, ranges, high, low, days=None, read_bar: Optional[int] = None) -> Walk:
    """Stages 2 to 4 on what is known on ``read_bar`` (by default the last day any turn was known): the swing ends,
    the trend ends with their first feet, every pair from the first foot on, and the box's life."""
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
    """The read's record from the walk, ``(boxes, trail, state)``: every box handed over (``ROLE_EARLIER``, ended),
    then the box shown (``ROLE_PARENT``); the trail in words, with ``keep_listing`` every other pair listed too."""
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
