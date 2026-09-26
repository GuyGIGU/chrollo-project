"""Stages 2 and 3 of the two-eyes reader: the end of the trend, the two-legs walk, answered his way, and the
election of the box.

Task 10 of the two-eyes-reader build. Pure functions of the line (stage 1) and each day's range: they read no
bars, apply no setting but the four numbers in ``method_numbers``, gate nothing and grade nothing. Everything is
computed from the turns known on the read day, so a reader with no memory gives the same answer as one that
watched every day (``tests/engine/test_two_eyes_walk.py`` proves it on his 35 and on a hand-built line).

His words that place the rules, and where they came from:

* **Respect.** *"one way to find out whenever a bar is respecting support resistance or both is to look at
  their High and Low values ... whenever they are slightly poking out or not does not matter one bit"* (Sat
  26/09/2026, with a screenshot of one of his boxes). A bar respects a line when its high or its low is close
  to the line, on either side — within the rail area, half a daily range. A swing answers a line the same way:
  its turn (a bar's high or low) is within the line's area. Never "inside versus outside the box".
* **The undercut.** A later low under the anchored support is respected when the bar is close to the line and
  *"the entire continues swing structure ... is still wrapped within the anchored box"* (same day, on MDT).
  So the reaction low stays where it first printed when a later low undercuts it by less than the area, and a
  pair whose span holds a swing beyond a line's area is not wrapped and is never a box.
* **The end of the trend.** *"the swings for BC and AR are needed to be decided before the Root Swing,
  because said root swing can either be them, or a swing later"* (Sat 19/09/2026); *"Trend end is a single
  mark before the beginning of the consolidation's base ... the transition between the two"* (Sat 26/09/2026).
  A trend end is a run of the far view that has ended; its pair is the climax and the reaction read on the
  LINE (point 4's rule on the fine turns, the climax bar's own other end left out). Every trend end known on
  the read day walks; the one that produced the elected box is the base's one trend end.
* **The walk.** *"I move one pair right until I find it, not only a single time. -> one line can stay on its
  anchor while the other moves, but they are connected like 2 lets placing one in front of the other"* (Sun
  20/09/2026). A foot moves one turn of its own kind to the right when the swings after the pair do not
  respect its line before the pair is a box: the first swing that falls short of the line's area while the
  line is unanswered, or the first that goes beyond it before the box is born. The pair it stepped from stays
  listed, so a poke that comes back can still be answered later.
* **The box.** *"were looking for the first instance that a consolidation is respected!"* (Sun 06/09/2026);
  *"Lets go with 15 days"* (Sat 12/09/2026). A pair became a box on the later of: both lines answered, its
  fifteenth trading day from the first anchor, and the day the walk listed it. The election is by that day
  first, then the earlier opening, then the walk's order (fewer moves), then the tighter pair; the order of
  the tie-breaks is OURS (placed at the listing gate, task 9). A shown line never moves: every pair is listed
  no earlier than the day the reader could see it, so nothing born later can be born earlier.

Ours, recorded as ours in the decisions record (task 10, Sat 26/09/2026): the far floor (1.5 daily ranges),
the tall floor (a pair under one of its own daily ranges is listed and never a box), the two step triggers
(short of the area while unanswered; beyond the area before birth), and each pair's unit — the range of its
second anchor's day, never the read day's.
"""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from typing import Optional

from engine_alpha.two_eyes import method_numbers as M
from engine_alpha.two_eyes.record import NO_LINES, ROLE_PARENT, Box, Line, Step
from engine_alpha.two_eyes.runs import _cmp

__all__ = ["Pair", "Walk", "bar_respects", "beyond", "box_of", "elect", "end_pair", "known_by", "left_the_box",
           "measure", "record", "respects", "trend_ends", "winner", "LINES_NO_LPS"]

#: The screen's word for a chart with a box and no LPS yet (his ten-word table; the LPS is stage 6).
LINES_NO_LPS = "lines, no LPS yet"

#: Why a listed pair can never be a box.
UNFIT_TALL = "under one daily range tall"
UNFIT_NOT_WRAPPED = "a swing beyond a line between its anchors"


def known_by(turns, bar: int) -> list:
    """The turns committed by ``bar``'s close: what a reader standing on that day has."""
    return [t for t in turns if t.knowable_bar is not None and t.knowable_bar <= bar]


# --------------------------------------------------------------------------- #
# Respect: his eye                                                            #
# --------------------------------------------------------------------------- #
def respects(price: float, line: float, area: float) -> bool:
    """A price (a bar's high or low, a turn of the line) respects a line when it is within the area of it, on
    either side. Poking out is the same distance as stopping short."""
    return abs(float(price) - float(line)) <= float(area)


def bar_respects(high: float, low: float, line: float, area: float) -> bool:
    """A bar respects a line when its high or its low is close to it — his picture of Sat 26/09/2026."""
    return respects(high, line, area) or respects(low, line, area)


# --------------------------------------------------------------------------- #
# Stage 2: the end of the trend                                               #
# --------------------------------------------------------------------------- #
def trend_ends(far_turns) -> list:
    """Every run of the far view that has ended, oldest first: at least two peaks and two valleys each above the
    last (the mirror for a decline), ended by the first swing that fails to continue it. The run reader's own
    scan (``runs.runs_on_the_line``), without its demand that the far view's reaction be decided: the reaction
    is read on the LINE here (``end_pair``). Each end carries its climax and the day the end was known — the
    close that committed the swing that ended the run."""
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
        out.append({"kind": "BC" if direction > 0 else "SC", "climax_bar": t[climax][0],
                    "climax_price": t[climax][2], "end_bar": t[i][0], "known_bar": int(t[i][3])})
        direction, start = 0, None
        i += 1
    return out


def _reaction_within_area(tup, climax: int, direction: int, area: float) -> Optional[tuple]:
    """Point 4's reaction rule with his rail area: after a buying climax, walk the valleys; a later low under
    the running reaction low by MORE than the area moves the reaction low to it, one under by less is the same
    low (respected, the structure still wrapped), and the first higher low decides the reaction. The mirror
    for a selling climax. Returns ``(reaction, decider)`` as indices, or None while undecided."""
    want = "valley" if direction > 0 else "peak"
    cand = None
    for j in range(climax + 1, len(tup)):
        if tup[j][1] != want:
            continue
        if tup[j][3] is None:
            return None                                   # the forming turn decides nothing yet
        if cand is None:
            cand = j
            continue
        beyond = tup[cand][2] - tup[j][2] if direction > 0 else tup[j][2] - tup[cand][2]
        if beyond > area:
            cand = j
        else:
            return cand, j
    return None


def end_pair(turns, ranges, end: dict) -> Optional[tuple]:
    """The trend end's pair read on the line: ``(r_index, s_index, joined_bar)`` — the climax and its reaction
    low for a buying climax (the reaction high and the climax for a selling one), the reaction by point 4's
    rule on the fine turns with the climax bar's own other end left out and undercuts inside the area read as
    the same low; ``joined_bar`` is the day the reader had both, the later of the run's end and the reaction's
    decision. None while the reaction is undecided, or when the climax is not a turn of this line."""
    kind = "peak" if end["kind"] == "BC" else "valley"
    climax = next((i for i, t in enumerate(turns) if t.bar == end["climax_bar"] and t.kind == kind), None)
    if climax is None:
        return None
    tup = [(t.bar, t.kind, t.price, t.knowable_bar) for t in turns]
    dropped = None
    if climax + 1 < len(tup) and tup[climax + 1][0] == tup[climax][0]:
        dropped = climax + 1                              # the climax bar's own other end: never the reaction
        tup = tup[:dropped] + tup[dropped + 1:]
    direction = 1 if end["kind"] == "BC" else -1
    area = float(M.LINE_WORD_AREA_ATR) * float(ranges[end["climax_bar"]])
    got = _reaction_within_area(tup, climax, direction, area)
    if got is None:
        return None
    reaction, decider = (k + 1 if dropped is not None and k >= dropped else k for k in got)
    joined = max(int(end["known_bar"]), int(turns[decider].knowable_bar))
    return (climax, reaction, joined) if direction > 0 else (reaction, climax, joined)


# --------------------------------------------------------------------------- #
# Stage 3: the pairs, answered his way                                        #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Pair:
    """One pair the walk listed: its two feet, its lines, its own unit, how it was reached, how it was
    answered, and the day it became a box (None until it is one, or never when ``unfit``)."""
    r_index: int
    s_index: int
    R: float
    S: float
    opening_bar: int
    second_bar: int
    unit: float
    joined_bar: int                 # the day the walk listed it: never before the reader could see it
    position: int                   # moves of the two legs from the trend end's pair
    end_kind: str                   # "BC" | "SC": the trend end it walked from
    parent: Optional[tuple]         # the feet it stepped from
    reason: str                     # why it was listed, in words
    r_answer: Optional[int]         # the turn that answered each line, and the close that committed it
    s_answer: Optional[int]
    r_known: Optional[int]
    s_known: Optional[int]
    fifteenth: int                  # its fifteenth trading day from the first anchor
    birth_bar: Optional[int]
    unfit: Optional[str]
    r_step: Optional[tuple] = None  # (known_bar, why, ran_through) when a foot must move, else None
    s_step: Optional[tuple] = None
    r_bar: Optional[int] = None
    s_bar: Optional[int] = None
    end_climax_bar: Optional[int] = None
    ran_through: bool = False       # reached because a swing went BEYOND the parent's line, not short of it

    @property
    def feet(self) -> tuple:
        return (self.r_index, self.s_index)

    @property
    def height(self) -> float:
        return self.R - self.S

    @property
    def opens_against_the_trend(self) -> bool:
        """After a rise the box opens on a high, after a decline on a low — his *"we cannot start the anchor in
        the same direction the price is going"* (Mon 14/09/2026), checked on the result, never a filter."""
        if self.r_bar is None or self.s_bar is None:
            return True
        return self.r_bar <= self.s_bar if self.end_kind == "BC" else self.s_bar <= self.r_bar


def measure(turns, ranges, r: int, s: int, joined: int, position: int, end_kind: str, parent, reason: str,
            read_bar: int, ran_through: bool = False) -> Pair:
    """One pair, answered his way. Its unit is the range of its second anchor's day (never the read day's); a
    line is answered by the first later committed swing of its kind within its area; a swing of a line's kind
    that falls short of the area while the line is unanswered, or goes beyond it before the box is born, makes
    that foot step (``r_step`` / ``s_step``: the day, and why). Unfit pairs — under one daily range tall, or a
    swing beyond a line's area between the anchors — are listed and never a box. A birth after the read day
    (a pair answered before its fifteenth day) is not a birth yet."""
    R, S = float(turns[r].price), float(turns[s].price)
    r_bar, s_bar = int(turns[r].bar), int(turns[s].bar)
    opening, second = min(r_bar, s_bar), max(r_bar, s_bar)
    unit = float(ranges[second])
    area = float(M.LINE_WORD_AREA_ATR) * unit
    fifteenth = opening + int(M.BOX_DAYS) - 1
    unfit = None
    if R - S < float(M.BOX_MIN_HEIGHT_RANGES) * unit:
        unfit = UNFIT_TALL
    elif any((t.kind == "peak" and t.price > R + area) or (t.kind == "valley" and t.price < S - area)
             for t in turns[min(r, s) + 1:max(r, s)]):
        unfit = UNFIT_NOT_WRAPPED
    answer = {"peak": None, "valley": None}
    known = {"peak": None, "valley": None}
    short = {"peak": None, "valley": None}
    beyond = {"peak": [], "valley": []}
    for i in range(max(r, s) + 1, len(turns)):
        t = turns[i]
        if t.knowable_bar is None:
            break                                         # the forming turn has not turned back yet
        line = R if t.kind == "peak" else S
        if respects(t.price, line, area):
            if answer[t.kind] is None:
                answer[t.kind], known[t.kind] = i, int(t.knowable_bar)
        elif (t.price > line + area) if t.kind == "peak" else (t.price < line - area):
            beyond[t.kind].append((int(t.knowable_bar), t.day))
        elif answer[t.kind] is None and short[t.kind] is None:
            short[t.kind] = (int(t.knowable_bar), t.day)
    birth = None
    if unfit is None and answer["peak"] is not None and answer["valley"] is not None:
        birth = max(known["peak"], known["valley"], fifteenth, int(joined))
        if birth > int(read_bar):
            birth = None

    def step(kind: str, name: str, line: float):
        when = [(k, f"{name} stepped right: the swing of {day:%a %d/%m/%Y} went beyond {line:.2f}", True)
                for k, day in beyond[kind] if birth is None or k < birth]
        if short[kind] is not None:
            k, day = short[kind]
            when.append((k, f"{name} stepped right: the swing of {day:%a %d/%m/%Y} fell short of {line:.2f}", False))
        return min(when) if when else None

    return Pair(r_index=r, s_index=s, R=R, S=S, opening_bar=opening, second_bar=second, unit=unit,
                joined_bar=int(joined), position=int(position), end_kind=end_kind, parent=parent, reason=reason,
                r_answer=answer["peak"], s_answer=answer["valley"], r_known=known["peak"], s_known=known["valley"],
                fifteenth=fifteenth, birth_bar=birth, unfit=unfit,
                r_step=step("peak", "resistance", R), s_step=step("valley", "support", S),
                r_bar=r_bar, s_bar=s_bar, ran_through=bool(ran_through))


def _children(turns, pair: Pair) -> list:
    """The pairs one step right of this one: each foot that must move lands on the first committed turn of its
    kind IN FRONT of the other foot — *"connected like 2 lets placing one in front of the other"* — so a foot
    left behind (the climax, with the reaction's small swings between it and the reaction low) steps past
    them to the base's own swings; a foot already in front takes the next turn of its kind. The other foot
    stays. Listed on the day of the step, never before the pair it stepped from; a pair whose resistance is
    not above its support is no pair."""
    out = []
    for kind, foot, step in (("peak", pair.r_index, pair.r_step), ("valley", pair.s_index, pair.s_step)):
        if step is None:
            continue
        nxt = next((j for j in range(max(pair.r_index, pair.s_index) + 1, len(turns))
                    if turns[j].kind == kind and turns[j].knowable_bar is not None), None)
        if nxt is None:
            continue
        r, s = (nxt, pair.s_index) if kind == "peak" else (pair.r_index, nxt)
        if turns[r].price <= turns[s].price:
            continue
        out.append((max(step[0], pair.joined_bar), pair.position + 1, r, s, step[1], step[2]))
    return out


def _key(pair: Pair) -> tuple:
    """The election: the day the pair became a box, then the earlier opening, then the walk's order, then the
    tighter; the feet last, so equal pairs never tie."""
    return (pair.birth_bar, pair.opening_bar, pair.position, pair.height, pair.r_index, pair.s_index)


def beyond(new: Pair, shown: Pair) -> bool:
    """A box beyond the shown box's lines: its support at or above the shown resistance's area, or its
    resistance at or below the shown support's area — a new consolidation at a new level, never one inside
    or overlapping the shown one (the box's own legs, or a mini)."""
    area = float(M.LINE_WORD_AREA_ATR) * shown.unit
    return new.S >= shown.R - area or new.R <= shown.S + area


def box_of(pairs) -> Optional[Pair]:
    """One trend end's box: the first of its pairs that became a box, by the election key — *"were looking for
    the first instance that a consolidation is respected!"* A pair born later inside or overlapping it never
    replaces it: a swing through a line is an event on the box, never a wider box (widening to the run-through
    pair was measured on his 35, Sat 26/09/2026, and lost six of eleven exact hits from the transition end;
    not applied). None while no pair is a box."""
    born = [p for p in pairs if p.birth_bar is not None]
    return min(born, key=_key) if born else None


def left_the_box(climax_price: float, shown: Pair) -> bool:
    """A trend end's climax beyond the shown box's lines: the trend left the box before it ended."""
    area = float(M.LINE_WORD_AREA_ATR) * shown.unit
    return float(climax_price) > shown.R + area or float(climax_price) < shown.S - area


def winner(pairs, ends) -> Optional[Pair]:
    """The box the read shows. Each trend end has its own box (``box_of``). Taken in the order the boxes were
    born, the first stands, and a trend end's box born later takes over only when that trend's climax LEFT
    the shown box's lines — the plan's stage-4 rule for the box's life (*"a newer trend end takes over only
    when one of ITS pairs is a box by your rules"*, and the theory's *"A new consolidation beyond a line
    takes over only when it is itself a box by his rules"*). A trend end whose climax lies inside the shown
    box is the box's own leg: it never moves the box. Read day by day, the shown box therefore changes only
    to a box born later, never back. This is the provisional stage-4 seam, OURS (measured against three
    other readings on his 35, Sat 26/09/2026): the ends by swings, the come-back checked to the read day and
    the earlier box kept in the record are task 11's. None while no pair is a box."""
    by_end = {}
    for pair in pairs:
        by_end.setdefault((pair.end_kind, pair.end_climax_bar), []).append(pair)
    boxes = []
    for end in ends:
        box = box_of(by_end.get((end["kind"], end["climax_bar"]), ()))
        if box is not None:
            boxes.append((box, end))
    shown = None
    for box, end in sorted(boxes, key=lambda be: _key(be[0])):
        if shown is None or left_the_box(end["climax_price"], shown):
            shown = box
    return shown


@dataclass(frozen=True)
class Walk:
    """What the walk found on one read: the trend ends, every pair it listed (in the order it listed them,
    keyed by feet), and the box, or None."""
    ends: tuple
    pairs: dict
    winner: Optional[Pair]
    turns: tuple
    days: Optional[tuple] = None


def _climax_index(turns, end: dict) -> Optional[int]:
    kind = "peak" if end["kind"] == "BC" else "valley"
    return next((i for i, t in enumerate(turns) if t.bar == end["climax_bar"] and t.kind == kind), None)


def _walk_from(turns, ranges, end: dict, root: tuple, last_index: int, last_known: int, read_bar: int) -> list:
    """The walk from one trend end: its pair, then one foot at a time, in the order the pairs were listed (the
    day, then the moves). From the day the next trend end is known (``last_known``) it goes no further right
    than that end's climax (``last_index``) — *"Trend end is a single mark before the beginning of the
    consolidation's base"*, so what lies past the next mark is the next walk's — while a pair listed before
    that day stays listed, so nothing the reader showed is cut back by a run that ended later. It stops
    listing once its box is born: *"I move one pair right until I find it"*. A pair reached twice is listed
    once, on the earlier day and by the shorter walk."""
    r, s, joined = root
    what = "the climax and its reaction low" if end["kind"] == "BC" else "the reaction high and the climax"
    heap, tick, seen, out = [], count(), set(), []
    heappush(heap, (joined, 0, r, s, next(tick), None, f"the trend end's own pair: {what}", False))
    born = None
    while heap:
        joined, position, r, s, _, parent, reason, ran_through = heappop(heap)
        if (r, s) in seen or (born is not None and joined > born):
            continue
        seen.add((r, s))
        pair = measure(turns, ranges, r, s, joined, position, end["kind"], parent, reason, read_bar, ran_through)
        pair = Pair(**{**pair.__dict__, "end_climax_bar": end["climax_bar"]})
        out.append(pair)
        if pair.birth_bar is not None and (born is None or pair.birth_bar < born):
            born = pair.birth_bar
        for child_joined, child_position, cr, cs, why, through in _children(turns, pair):
            if max(cr, cs) <= last_index or child_joined < last_known:
                heappush(heap, (child_joined, child_position, cr, cs, next(tick), (r, s), why, through))
    return out


def elect(turns, far_turns, ranges, days=None, read_bar: Optional[int] = None) -> Walk:
    """Stages 2 and 3 on the turns known on the read day (``read_bar``: by default the last day any of them
    was known). Every trend end walks (``_walk_from``); a pair two walks reach is kept from the walk that
    listed it first; the box is ``winner`` over every trend end's pairs."""
    turns = list(turns)
    if read_bar is None:
        read_bar = max((t.knowable_bar for t in turns if t.knowable_bar is not None), default=0)
    ends = []
    for end in trend_ends(far_turns):
        got = end_pair(turns, ranges, end)
        ends.append({**end, "pair": None if got is None else (got[0], got[1]),
                     "joined": None if got is None else got[2]})
    pairs = {}
    for k, end in enumerate(ends):
        if end["pair"] is None:
            continue
        later = [(i, e["known_bar"]) for e in ends[k + 1:] for i in (_climax_index(turns, e),) if i is not None]
        last_index, last_known = later[0] if later else (len(turns) - 1, len(turns) + int(read_bar))
        for pair in _walk_from(turns, ranges, end, (*end["pair"], end["joined"]), last_index, last_known,
                               int(read_bar)):
            have = pairs.get(pair.feet)
            if have is None or (pair.joined_bar, pair.position) < (have.joined_bar, have.position):
                pairs[pair.feet] = pair
    pairs = dict(sorted(pairs.items(), key=lambda kv: (kv[1].joined_bar, kv[1].position, kv[0])))
    return Walk(ends=tuple(ends), pairs=pairs, winner=winner(pairs.values(), ends), turns=tuple(turns),
                days=None if days is None else tuple(days))


# --------------------------------------------------------------------------- #
# The record: the box, the trail, the state word                              #
# --------------------------------------------------------------------------- #
def _when(walk: Walk, bar: Optional[int]) -> str:
    if bar is None:
        return "not yet"
    if walk.days is not None and 0 <= bar < len(walk.days):
        return f"{walk.days[bar]:%a %d/%m/%Y}"
    return f"bar {bar}"


def _end_words(walk: Walk, end: dict) -> str:
    what = "a rise" if end["kind"] == "BC" else "a decline"
    climax = next((t for t in walk.turns if t.bar == end["climax_bar"]
                   and t.kind == ("peak" if end["kind"] == "BC" else "valley")), None)
    day = f"{climax.day:%a %d/%m/%Y}" if climax is not None else _when(walk, end["climax_bar"])
    return f"the end of {what}: its climax {end['climax_price']:.2f} on {day}, known {_when(walk, end['known_bar'])}"


def _pair_words(walk: Walk, pair: Pair) -> str:
    r, s = walk.turns[pair.r_index], walk.turns[pair.s_index]
    words = (f"R {pair.R:.2f} ({r.day:%a %d/%m/%Y}) / S {pair.S:.2f} ({s.day:%a %d/%m/%Y}), "
             f"measured in a {pair.unit:.2f} daily range, listed {_when(walk, pair.joined_bar)}"
             f"{'' if pair.position == 0 else f' after {pair.position} move(s)'}")
    if pair.birth_bar is not None:
        why = " (its fifteenth day)" if pair.birth_bar == pair.fifteenth else ""
        return words + (f"; both lines answered by {_when(walk, max(pair.r_known, pair.s_known))}; a box on "
                        f"{_when(walk, pair.birth_bar)}{why}")
    if pair.unfit is not None:
        return words + f"; never a box: {pair.unfit}"
    missing = [name for name, got in (("resistance", pair.r_answer), ("support", pair.s_answer)) if got is None]
    return words + (f"; not a box yet: {' and '.join(missing)} unanswered" if missing
                    else f"; not a box yet: its fifteenth day is {_when(walk, pair.fifteenth)}")


def record(walk: Walk, keep_listing: bool = False) -> tuple:
    """The read's record from the walk: ``(boxes, trail, state)``. The trail runs from the winner's trend end
    through each pair the legs stood on to the box; with ``keep_listing`` every other pair the walk listed
    follows, in the order it was listed — words only, the box and the state identical."""
    if not walk.ends:
        return (), (), NO_LINES
    won = walk.winner
    if won is None:
        end = walk.ends[-1]
        steps = [Step("trend end", _end_words(walk, end))]
        if end["pair"] is not None:
            steps.append(Step("pair", _pair_words(walk, walk.pairs[end["pair"]])))
        return (), tuple(steps), NO_LINES
    ancestry = []
    feet = won.feet
    while feet is not None:
        ancestry.append(walk.pairs[feet])
        feet = walk.pairs[feet].parent
    ancestry.reverse()
    end = next(e for e in walk.ends if e["kind"] == won.end_kind and e["climax_bar"] == won.end_climax_bar)
    steps = [Step("trend end", _end_words(walk, end))]
    for pair, child in zip(ancestry[:-1], ancestry[1:]):
        steps.append(Step("pair", _pair_words(walk, pair)))
        steps.append(Step("step", child.reason))
    steps.append(Step("box", _pair_words(walk, won)))
    if keep_listing:
        listed = {p.feet for p in ancestry}
        steps.extend(Step("listed", _pair_words(walk, p)) for p in walk.pairs.values() if p.feet not in listed)
    r, s = walk.turns[won.r_index], walk.turns[won.s_index]
    box = Box(resistance=Line(won.R, r.day), support=Line(won.S, s.day),
              opened_day=min(r.day, s.day), end_day=None, role=ROLE_PARENT, daily_range=won.unit)
    return (box,), tuple(steps), LINES_NO_LPS
