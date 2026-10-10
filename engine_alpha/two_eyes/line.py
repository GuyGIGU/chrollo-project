"""Stage 1 of the two-eyes reader: the swing line, and the far view that is the same line seen from further back.

Task 8 of the two-eyes-reader build. Everything after this stage inherits the line's dates — the end of the
trend, the two lines, the box's life, the story, the LPS — so the line is built ONCE per read, from bars that
are already a chart (``frame.prepare``), and it is causal by construction: nothing a later day prints can move
a turn that an earlier day committed. The plan's four properties are proved on every fixture chart in
``tests/engine/test_two_eyes_line.py``, each seen red once.

His words that place the rules, and where they came from:

* *"the bars themselves (The entire bar from High to Low) tells me everything I need to know"* (Thu
  10/09/2026): the unit is the whole bar, wick to wick; a turn commits when price backs off its running
  extreme by 0.75 of that bar's OWN daily range (the copied primitive ``swing_line.turn_line``, the floor placed
  by his 186 named turns).
* *"even with out "Future" Information we can deduct them as turns by their current state swing shape"* (Sat
  12/09/2026): the first bar and the last bar are turns by their shape; the last one rides as FORMING until a
  later bar commits it.
* The far view is this line with its small swings folded away, never a second line (ours, task 1): a FOLD of
  the fine line (``_far_on_bars``). Its extremes are the fine line's own committed turns, and a far turn
  commits when a bar backs off that extreme by the far floor in the bar's own range — the fine rule at a
  bigger floor, with the bar's ends read in the fine line's order. So every far turn IS a fine turn and
  becomes knowable no earlier than it, by construction. Two other constructions were built and rejected on
  the fixtures: the bar rule in the far view's own direction falls out of phase with the fine line on
  every wide bar (about twelve far turns a chart at 1.5 ranges sat on bars the fine line has no turn on;
  UNF, 08/01/2025), and a bar rule in the fine line's order still takes a print the fine line judged as
  noise when the day's range jumps (a higher high whose rise is short of that day's larger floor). Its
  floor is placed by the listing gate (task 9); here it is a parameter, and each far view is built once and
  kept.

Ours, recorded as ours in the decisions record (Sat 26/09/2026):

* ONE rule for the order inside a bar: the line enters a bar in a direction, and the bar's extreme in that
  direction is read first, then the other one. A bar that carries both a peak and a valley lists the turn
  that ends the leg it was entered on first and the new leg's extreme second; a bar commits at most one
  turn, on its close, and the turn it carries for the new leg is committed by a later bar.
* A turn's SIZE is the leg into it — the price travelled from the turn before — in the daily range of the day
  the turn printed; the opening turn ends no leg and has no size.
* A turn's KNOWABLE day is the close that committed it (the confirming bar's day); the forming turn has none;
  the opening turn's is the day its first leg covered the floor, even when it sits on the chart's first bar.
* Cutting the frame on the right changes nothing already committed. What it may change is the closed list
  ``FORMING_ONLY``, and nothing else.
* A missing number fails loud, by name and by day: a high or low that is not a number, a daily range that is
  not a number after the range has warmed up. The warm-up bars at the very left (no previous close yet) have
  no readable floor and commit nothing; that is the one gap the line tolerates, and it is named here.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from engine_alpha import two_eyes_numbers as M
from engine_alpha.two_eyes import swing_line
from engine_alpha.two_eyes.frame import DAILY_RANGE

#: The closed list of what cutting the frame on the right may change. Everything else the line says on the
#: shorter frame it says on the longer one, word for word.
FORMING_ONLY = (
    "the forming turn at the right edge: its bar and its price, until a later bar commits it",
    "before the line has opened (no leg has covered its floor yet): its opening turn too, whose kind is not"
    " yet known — both turns of such a line are forming",
)


@dataclass(frozen=True)
class Turn:
    """One turn of the line, and what the reader knows about it."""
    bar: int
    day: dt.date
    kind: str                            # "peak" | "valley"
    price: float
    knowable_bar: Optional[int]          # the bar whose close committed it; None while forming
    knowable_day: Optional[dt.date]
    size_ranges: Optional[float]         # the leg into it, in the daily range of its own day; None for the opening

    @property
    def committed(self) -> bool:
        return self.knowable_bar is not None


@dataclass(frozen=True)
class SwingLine:
    """The fine line, built once, and the far views built from the same bars on demand."""
    floor_ranges: float
    turns: tuple
    _highs: np.ndarray = field(repr=False, compare=False)
    _lows: np.ndarray = field(repr=False, compare=False)
    _ranges: np.ndarray = field(repr=False, compare=False)     # each bar's daily range, NaN before it warms up
    _days: tuple = field(repr=False, compare=False)
    _direction: list = field(repr=False, compare=False)        # how the fine line came into each bar
    _far: dict = field(default_factory=dict, repr=False, compare=False)

    def far(self, floor_ranges: float) -> tuple:
        """The same line seen from further back: swings smaller than ``floor_ranges`` daily ranges folded
        away. Built once per floor and kept."""
        floor = float(floor_ranges)
        if not np.isfinite(floor) or floor < self.floor_ranges:
            raise ValueError(f"the far view folds swings away; its floor ({floor_ranges!r}) cannot be under "
                             f"the line's own ({self.floor_ranges})")
        if floor not in self._far:
            raw = _far_on_bars(self.turns, self._highs, self._lows, self._ranges, self._direction, floor)
            self._far[floor] = _stamped(raw, self._ranges, self._days)
        return self._far[floor]

    @property
    def committed(self) -> tuple:
        return tuple(t for t in self.turns if t.committed)


def build(prepared, floor_ranges: Optional[float] = None) -> SwingLine:
    """The line of a PREPARED frame (``frame.prepare``: the contract, the daily range, the window)."""
    if DAILY_RANGE not in getattr(prepared, "columns", ()):
        raise ValueError(f"the frame carries no {DAILY_RANGE} column: prepare it first (frame.prepare)")
    highs = np.asarray(prepared["High"].to_numpy(), dtype=float)
    lows = np.asarray(prepared["Low"].to_numpy(), dtype=float)
    ranges = np.asarray(prepared[DAILY_RANGE].to_numpy(), dtype=float)
    days = tuple(d.date() for d in prepared.index)
    _refuse_missing(highs, lows, ranges, days)
    floor = float(M.TURN_LINE_FLOOR_ATR if floor_ranges is None else floor_ranges)
    # No scalar fallback: the unit is each day's own range, or nothing. A bar with no readable range (the
    # warm-up at the very left) tracks the running extreme and commits nothing — the primitive's own rule,
    # `turn_line_floors` with no scalar to fall back on.
    floors = swing_line.turn_line_floors(prepared, None, floor)
    turns = _stamped(swing_line.turn_line(highs, lows, floors), ranges, days)
    return SwingLine(floor_ranges=floor, turns=turns, _highs=highs, _lows=lows, _ranges=ranges, _days=days,
                     _direction=_fine_direction(turns, len(highs)))


def _refuse_missing(highs, lows, ranges, days) -> None:
    for name, values in (("High", highs), ("Low", lows)):
        bad = np.flatnonzero(~np.isfinite(values))
        if len(bad):
            raise ValueError(f"{name} is not a number on {days[bad[0]]}: a bar is a fact or it is refused")
    readable = np.isfinite(ranges) & (ranges > 0)
    if readable.any():
        first = int(np.argmax(readable))
        hole = np.flatnonzero(~readable[first:])
        if len(hole):
            raise ValueError(f"the daily range is not a number on {days[first + hole[0]]}, after it had "
                             "warmed up: a hole in the middle of a chart is refused, never read around")


def _readable(ranges, bar: int) -> bool:
    unit = float(ranges[bar])
    return bool(np.isfinite(unit)) and unit > 0


def _fine_direction(turns, n: int) -> list:
    """For each bar, the direction the fine line came into it: True rising, False falling, None before the
    line has opened. It is the kind of the last turn committed BEFORE the bar (knowable on an earlier bar):
    after a committed valley the line is rising, after a committed peak it is falling. The turn a bar
    itself commits does not count — that reversal is only known at the bar's close."""
    out = [None] * n
    committed = sorted(((t.knowable_bar, t.kind) for t in turns if t.knowable_bar is not None),
                       key=lambda x: x[0])
    k = 0
    last = None
    for i in range(n):
        while k < len(committed) and committed[k][0] <= i - 1:
            last = committed[k][1]
            k += 1
        out[i] = None if last is None else (last == "valley")
    return out


def _far_on_bars(turns, highs, lows, ranges, direction, floor: float) -> list:
    """The fine line folded at a bigger floor.

    The far view's extremes are the fine line's own COMMITTED turns — never a bar's high or low on its own —
    and a far turn commits when a bar backs off that extreme by ``floor`` daily ranges, the range being that
    bar's own (the fine line's commit rule, at a bigger floor). So every far turn is a turn of the fine line,
    by construction, and it is knowable no earlier than the fine turn it is: at each bar the pool holds the
    fine turns knowable by that bar, and only they can be extremes. Reading the bar's two ends in the fine
    line's order (its direction into the bar, that end first) keeps both views on one rule inside a bar.

    Why not the bars' own extremes at a bigger floor: with each day's own range as the unit, a day whose
    range jumps can print a higher high the fine line never turns on (its rise off the running low is short
    of THAT day's larger floor), and a far view reading bars would take it as its extreme — a far turn on a
    bar the fine line has no turn on. The fine line's turns are what the far view folds; a print the fine
    line judged as noise is not a swing at any distance.

    Returns ``[(bar, kind, price, knowable_bar)]`` like the fine primitive; ``[]`` until the far view has
    opened (the older of its two running extremes when they first sit a far floor apart, knowable then).
    """
    n = len(highs)
    fine = list(turns)                                            # bar order == knowable order
    pool = []                                                     # committed fine turns, as they become knowable
    k = 0

    def clears(bar: int, gap: float) -> bool:
        unit = float(ranges[bar])
        return bool(np.isfinite(unit)) and unit > 0 and gap >= floor * unit

    def beats(idx: int, best, kind: str) -> bool:
        if pool[idx].kind != kind:
            return False
        if best is None:
            return True
        return pool[idx].price > pool[best].price if kind == "peak" else pool[idx].price < pool[best].price

    def most_extreme(kind: str, after: int):
        """The pool's most extreme turn of ``kind`` after list index ``after`` (ties to the earlier)."""
        best = None
        for idx in range(after + 1, len(pool)):
            if beats(idx, best, kind):
                best = idx
        return best

    up = None                                                     # the far direction, None until opened
    ext = None                                                    # pool index of the far leg's extreme so far
    start = -1                                                    # pool index of the last far turn
    hi = lo = None                                                # the opening's running extremes
    out = []
    for i in range(n):
        first_new = len(pool)
        while k < len(fine) and fine[k].knowable_bar is not None and fine[k].knowable_bar <= i:
            pool.append(fine[k])
            k += 1
        if up is None:
            for idx in range(first_new, len(pool)):
                if beats(idx, hi, "peak"):
                    hi = idx
                if beats(idx, lo, "valley"):
                    lo = idx
            if hi is None or lo is None or not clears(i, pool[hi].price - pool[lo].price):
                continue
            up = lo < hi                                          # the older extreme owns the opening
            start, ext = (lo, hi) if up else (hi, lo)
            out.append((pool[start].bar, pool[start].kind, pool[start].price, i))
        else:
            for idx in range(max(first_new, start + 1), len(pool)):
                if beats(idx, ext, "peak" if up else "valley"):
                    ext = idx
        if ext is None:                                           # the far leg has no committed extreme yet
            continue
        # The bar's two ends in the fine line's order into it; the end against the far direction tests the
        # back-off, and a flip lets the bar's other end test the new leg (two far turns on one wide bar).
        ends = ((True, float(highs[i])), (False, float(lows[i])))
        if direction[i] is False:
            ends = ends[::-1]
        for is_high, price in ends:
            if up and not is_high and clears(i, pool[ext].price - price):
                out.append((pool[ext].bar, "peak", pool[ext].price, i))
                up, start = False, ext
                ext = most_extreme("valley", start)
            elif not up and is_high and clears(i, price - pool[ext].price):
                out.append((pool[ext].bar, "valley", pool[ext].price, i))
                up, start = True, ext
                ext = most_extreme("peak", start)
            if ext is None:
                break
    if up is not None and ext is not None and ext != start:
        out.append((pool[ext].bar, "peak" if up else "valley", pool[ext].price, None))
    return out


def _stamped(raw_turns, ranges, days) -> tuple:
    """``(bar, kind, price, knowable_bar)`` from the primitive -> ``Turn`` with its day, its knowable day and
    its size in the daily range of its own day."""
    out = []
    previous_price = None
    for bar, kind, price, know in raw_turns:
        bar = int(bar)
        unit = float(ranges[bar])
        size = None
        if previous_price is not None and np.isfinite(unit) and unit > 0:
            size = abs(float(price) - previous_price) / unit
        out.append(Turn(bar=bar, day=days[bar], kind=str(kind), price=float(price),
                        knowable_bar=None if know is None else int(know),
                        knowable_day=None if know is None else days[int(know)],
                        size_ranges=size))
        previous_price = float(price)
    return tuple(out)
