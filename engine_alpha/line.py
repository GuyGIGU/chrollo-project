"""Stage 1, the line: where price turned (``turn_line`` and its floors, each bar's own daily range) and the
swing line built from those turns once per read — the committed turns and the far view every later stage reads.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from engine_alpha import numbers as M
from engine_alpha.chart import DAILY_RANGE


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
    floors = turn_line_floors(prepared, None, floor)
    turns = _stamped(turn_line(highs, lows, floors), ranges, days)
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


def turn_line_floors(df, atr_val, mult=None):
    """The per-bar floor for :func:`turn_line`: ``mult`` daily ranges measured in the range of each bar's OWN
    day, falling back to the one scalar range the caller already holds wherever the frame carries no ATR
    column (the unit tests' bare OHLC frames, and any bar before the ATR warms up).

    His unit is "the daily range", and over a two-year frame that is not one number: measured on his 35 drawn
    marks, the line lands on 186 of his 186 named turns with the per-bar range and 183 with a single range
    taken from the read day (build step 4, 2026-09-13). At the line's density that one-day recall is mostly
    chance (his day moved three trading days still lands 173 of 186), so it places the floor and does not prove
    the line (review, Mon 14/09/2026)."""
    mult = M.TURN_LINE_FLOOR_ATR if mult is None else float(mult)
    scalar = float(atr_val) if atr_val is not None and np.isfinite(atr_val) and float(atr_val) > 0 else np.nan
    n = len(df) if df is not None else 0
    if n == 0:
        return np.zeros(0, dtype=float)
    # Duck-typed on purpose: this module is a leaf primitive and must not grow a pandas import.
    cols = getattr(df, "columns", None)
    if cols is not None and "ATR_10" in cols:
        col = np.asarray(df["ATR_10"].values, dtype=float)
    else:
        col = np.full(n, np.nan, dtype=float)
    floors = mult * np.where(np.isfinite(col) & (col > 0), col, scalar)
    return floors

def _opening_direction(highs, lows, floors):
    """How the line leaves the start of the chart, or None when the chart never covers the floor (no leg is
    committed anywhere). Returns ``(up, bar, low_bar, high_bar)``: ``up`` True when it rose first, the bar on which
    the first leg covered its floor, and the bars of the running low and high at that moment.

    Read it as "which move covered the floor first": the running high and low track EVERY bar, and on the first
    bar with a readable floor where they sit a floor apart, the OLDER of the two owns the opening leg and is the
    opening turn (a tie on one bar opens upward). The opening turn is bar 0 only when bar 0 is that extreme: the
    line used to open on bar 0 whatever followed, and a rise whose top printed on a bar with no readable floor
    went unseen (review findings F3 and TG-8, Mon 14/09/2026)."""
    run_hi, run_lo = float(highs[0]), float(lows[0])
    i_hi = i_lo = 0
    for i in range(1, len(highs)):
        if float(highs[i]) > run_hi:
            run_hi, i_hi = float(highs[i]), i
        if float(lows[i]) < run_lo:
            run_lo, i_lo = float(lows[i]), i
        f = float(floors[i])
        if not np.isfinite(f) or f <= 0:
            continue
        if run_hi - run_lo >= f:
            return i_lo <= i_hi, i, i_lo, i_hi
    return None

def _extreme_since(values, turn_bar: int, confirming_bar: int, *, lowest: bool, turn_read_first: bool) -> int:
    """The bar of the most extreme value from the turn to the confirming bar — the new leg's extreme so far,
    read on the day the old leg's turn was confirmed. The turn bar's own other end counts only when the turn
    was that bar's FIRST-read end (the bar was entered in the old leg's direction, so its other end came
    after the turn and belongs to the new leg); read before the turn, it belongs to the leg before and was
    that leg's business. Ties go to the earlier bar, as the running extreme always did."""
    start = turn_bar if turn_read_first else turn_bar + 1
    if start > confirming_bar:
        return confirming_bar
    window = np.asarray(values[start:confirming_bar + 1], dtype=float)
    return start + int(np.argmin(window) if lowest else np.argmax(window))

def turn_line(highs, lows, floors):
    """THE turn line (operator ruling, final method point 1): one line over the whole chart, one floor, wick to
    wick, no retracement ratio.

    A turn COMMITS on the bar where price backs off the running extreme by that bar's floor; the confirming bar
    carries the next leg's extreme, so a bar whose own range covers the floor holds both a peak and a valley.
    The opening turn is the older running extreme when the first leg covers its floor (bar 0 when bar 0 is it, a
    turn by its shape), and the running extreme at the right edge rides as a FORMING turn: the line has no edge
    mask, which is what the order-1 walk's ``peak_mask[n - order:]`` reserve costs it (his 25 of 37
    pullbacks bottom within two days of the edge).

    Returns ``[(bar, kind, price, knowable_bar)]``, oldest first and strictly alternating. ``knowable_bar`` is
    the bar at whose close the turn was irreversibly committed (the causality contract's stamp, which the line
    knows by construction instead of reconstructing); it is ``None`` for the forming turn at the right edge.
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = len(highs)
    if n == 0 or n != len(lows):
        return []
    floors = np.asarray(floors, dtype=float)
    if floors.ndim == 0:
        floors = np.full(n, float(floors))
    if len(floors) != n or not np.any(np.isfinite(floors) & (floors > 0)):
        return []

    opening = _opening_direction(highs, lows, floors) if n > 1 else None
    if opening is None:
        # The chart never covers the floor: the opening turn and one forming extreme, no committed leg.
        i_hi, i_lo = int(np.argmax(highs)), int(np.argmin(lows))
        rose_first = i_hi >= i_lo
        # Nothing is knowable yet, not even which kind the first bar is: both turns ride as forming (task 8;
        # the original stamped the opening on bar 0).
        out = [(0, "valley" if rose_first else "peak", float(lows[0] if rose_first else highs[0]), None)]
        tail = ((i_hi, "peak", float(highs[i_hi])) if rose_first else (i_lo, "valley", float(lows[i_lo])))
        if (tail[0], tail[1]) != (out[0][0], out[0][1]):
            out.append((tail[0], tail[1], tail[2], None))
        return out

    # The opening turn is the older running extreme (bar 0 when bar 0 is it, a turn by its shape); the first leg's
    # own extreme so far is the other one. Nothing commits before the bar on which that leg covered its floor —
    # and that bar is the opening turn's knowable day too, even on bar 0: the bar is a turn by its shape, but
    # WHICH kind is known only when the first leg has covered its floor (task 8; the original stamped 0).
    up, first, i_lo, i_hi = opening
    if up:
        turns = [(i_lo, "valley", float(lows[i_lo]), first)]
        ext_i, ext_p = i_hi, float(highs[i_hi])
    else:
        turns = [(i_hi, "peak", float(highs[i_hi]), first)]
        ext_i, ext_p = i_lo, float(lows[i_lo])
    # Whether the running extreme was its bar's FIRST-read end. The one rule inside a bar: a bar is read in
    # the direction the line came into it, that end first. An extreme set while the line was already
    # running its way was read first and its bar's other end came after it; an extreme found on the
    # confirming bar of the turn before (or on the opening's tie bar) was read second. The opening's
    # extreme on a bar of its own is taken as read first (two-eyes-reader task 8).
    ext_first = i_hi != i_lo
    # A bar wide enough to open the line on its own (both running extremes on the deciding bar, the tie that
    # opens upward) has been read once already; reading it again would carry its low a second time as a
    # back-off from its own high (two-eyes-reader task 8).
    start = first + 1 if i_lo == i_hi == first else first
    for i in range(start, n):
        f = float(floors[i])
        readable = bool(np.isfinite(f)) and f > 0
        # The extreme tracks every bar; only the COMMIT test needs a readable floor.
        if up:
            if float(highs[i]) > ext_p:
                ext_p, ext_i, ext_first = float(highs[i]), i, True
            if readable and ext_p - float(lows[i]) >= f:
                turns.append((ext_i, "peak", ext_p, i))
                up = False
                # The new leg's extreme is the lowest low since the peak, over every bar from the peak's
                # to this one — not this bar's alone, which skipped a lower low printed in between when
                # the confirmation took more than one bar (two-eyes-reader task 8). Every bar in that
                # stretch was entered rising, so its low is its second-read end: read after the peak.
                ext_i = _extreme_since(lows, ext_i, i, lowest=True, turn_read_first=ext_first)
                ext_p, ext_first = float(lows[ext_i]), False
        else:
            if float(lows[i]) < ext_p:
                ext_p, ext_i, ext_first = float(lows[i]), i, True
            if readable and float(highs[i]) - ext_p >= f:
                turns.append((ext_i, "valley", ext_p, i))
                up = True
                ext_i = _extreme_since(highs, ext_i, i, lowest=False, turn_read_first=ext_first)
                ext_p, ext_first = float(highs[ext_i]), False
    kind = "peak" if up else "valley"
    if (turns[-1][0], turns[-1][1]) != (ext_i, kind):
        turns.append((ext_i, kind, ext_p, None))
    return turns
