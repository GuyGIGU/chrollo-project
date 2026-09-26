"""COPIED from engine_alpha/structure/metrics/pivots.py and engine_alpha/structure/events/market_structure.py at cd87fcc (two-eyes-reader task 7): the ONE turn line and its labels — `turn_line_floors`, `_opening_direction`, `turn_line`, `turns_at_rails` from pivots.py, and `_empty`, `label_market_structure` from market_structure.py.

Copied verbatim but for the one number it reads (TURN_LINE_FLOOR_ATR, from the new reader's own `method_numbers`
instead of the SHARED settings, same value), then CHANGED ON PURPOSE at task 8 (Sat 26/09/2026), the line's own
task, in three places the original still has: (1) after a turn commits, the new leg's extreme is the true extreme
since that turn over every bar to the confirming one, where the original starts the new leg at the confirming
bar and skips a lower low (higher high) printed in between (UNF, 08/01/2025); (2) a first bar wide enough to
open the line on its own is read once, where the original read it again and carried its valley twice (six of
the 88 fixture frames); (3) the opening turn is knowable on the bar its first leg covered the floor, even on the
chart's first bar, and a chart that never covers the floor has no committed turn at all (the original stamped
bar 0 in both cases). The original stays in the old engine, frozen; the pins that held this copy equal to it
were deleted in the same commit, as the plan says; `tests/engine/test_two_eyes_line.py` is its guard now.

The original's own documentation, unchanged:

Pivot and zigzag helpers shared by structure detectors.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from engine_alpha.two_eyes import method_numbers as M


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


def turns_at_rails(turns, start, R, S, area):
    """How many COMMITTED turns of the line, at or after ``start``, sit inside each rail's area: peaks within
    ``area`` of ``R`` and valleys within ``area`` of ``S``. His display floor for the watch lane (final method
    point 22, build step 8: two turns at each rail). A peak beyond R plus the area is a thrust, not a turn at R,
    and counts for neither rail; the forming turn at the right edge (``knowable_bar`` None) is not yet a turn.
    Returns ``(at_r, at_s)``."""
    at_r = at_s = 0
    for bar, kind, price, know in turns:
        if know is None or int(bar) < int(start):
            continue
        if kind == "peak" and abs(float(price) - float(R)) <= area:
            at_r += 1
        elif kind == "valley" and abs(float(price) - float(S)) <= area:
            at_s += 1
    return at_r, at_s


def _empty() -> dict:
    return {
        "points": [],
        "events": [],
        "trend_state": "range",
        "n_points": 0,
        "last_event": None,
    }


def label_market_structure(zigzag) -> dict:
    """Label an alternating ``[(bar, 'peak'|'valley', price)]`` zigzag.

    Peaks are graded against the prior peak (HH / LH), valleys against the prior
    valley (HL / LL). A HH that takes OUT the prior swing high is a bullish break;
    a LL that takes out the prior swing low is a bearish break. A break that
    continues the trend is a ``BOS``; the first break that flips it is a
    ``reversal`` (a mechanical flip — NOT the operator's Wyckoff CHoCH; see the
    module docstring).
    An equal extreme (double top / bottom) holds the level — it is labelled with
    the trend-friendly tag but is NOT a structural break.
    """
    if not zigzag or len(zigzag) < 2:
        return _empty()

    points: list[dict] = []
    events: list[dict] = []
    prev_peak: Optional[float] = None
    prev_valley: Optional[float] = None
    trend = "range"
    last_event: Optional[dict] = None

    for bar, kind, price in zigzag:
        bar = int(bar)
        price = float(price)
        label = "first"

        if kind == "peak":
            if prev_peak is not None:
                if price > prev_peak:
                    label = "HH"
                    etype = "BOS" if trend == "up" else "reversal"
                    event = {"bar": bar, "type": etype, "direction": 1,
                             "broke": round(prev_peak, 4)}
                    events.append(event)
                    last_event = event
                    trend = "up"
                elif price < prev_peak:
                    label = "LH"
                else:
                    label = "HH"          # double top — held, no break
            prev_peak = price

        elif kind == "valley":
            if prev_valley is not None:
                if price < prev_valley:
                    label = "LL"
                    etype = "BOS" if trend == "down" else "reversal"
                    event = {"bar": bar, "type": etype, "direction": -1,
                             "broke": round(prev_valley, 4)}
                    events.append(event)
                    last_event = event
                    trend = "down"
                elif price > prev_valley:
                    label = "HL"
                else:
                    label = "HL"          # double bottom — held, no break
            prev_valley = price

        points.append({"bar": bar, "kind": kind, "price": round(price, 4),
                       "label": label, "trend": trend})

    return {
        "points": points,
        "events": events,
        "trend_state": trend,
        "n_points": len(points),
        "last_event": last_event,
    }
