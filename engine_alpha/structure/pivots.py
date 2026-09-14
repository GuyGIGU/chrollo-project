"""Pivot and zigzag helpers shared by structure detectors."""
from __future__ import annotations

import numpy as np

from config import settings


def _pivot_order(n_bars):
    """The calibrated pivot half-window for a window of ``n_bars`` — ONE rule
    for every detector (LONG at/above the threshold, SHORT below). Settings are
    read at call time so the HTF preset overrides keep propagating."""
    if n_bars >= settings.PIVOT_ORDER_THRESHOLD:
        return settings.PIVOT_ORDER_LONG
    return settings.PIVOT_ORDER_SHORT


# ---------------------------------------------------------------------------
# The one turn line (final method point 1, build step 4) — flag-gated at its
# call sites, never here: this is a pure primitive.
# ---------------------------------------------------------------------------

def turn_line_floors(df, atr_val, mult=None):
    """The per-bar floor for :func:`turn_line`: ``mult`` daily ranges measured in the range of each bar's OWN
    day, falling back to the one scalar range the caller already holds wherever the frame carries no ATR
    column (the unit tests' bare OHLC frames, and any bar before the ATR warms up).

    His unit is "the daily range", and over a two-year frame that is not one number: measured on his 35 drawn
    marks, the line lands on 186 of his 186 named turns with the per-bar range and 183 with a single range
    taken from the read day (build step 4, 2026-09-13). At the line's density that one-day recall is mostly
    chance (his day moved three trading days still lands 173 of 186), so it places the floor and does not prove
    the line (review, Mon 14/09/2026)."""
    mult = settings.TURN_LINE_FLOOR_ATR if mult is None else float(mult)
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
        out = [(0, "valley" if rose_first else "peak", float(lows[0] if rose_first else highs[0]), 0)]
        tail = ((i_hi, "peak", float(highs[i_hi])) if rose_first else (i_lo, "valley", float(lows[i_lo])))
        if (tail[0], tail[1]) != (out[0][0], out[0][1]):
            out.append((tail[0], tail[1], tail[2], None))
        return out

    # The opening turn is the older running extreme (bar 0 when bar 0 is it, a turn by its shape); the first leg's
    # own extreme so far is the other one. Nothing commits before the bar on which that leg covered its floor.
    up, first, i_lo, i_hi = opening
    if up:
        turns = [(i_lo, "valley", float(lows[i_lo]), 0 if i_lo == 0 else first)]
        ext_i, ext_p = i_hi, float(highs[i_hi])
    else:
        turns = [(i_hi, "peak", float(highs[i_hi]), 0 if i_hi == 0 else first)]
        ext_i, ext_p = i_lo, float(lows[i_lo])
    for i in range(first, n):
        f = float(floors[i])
        readable = bool(np.isfinite(f)) and f > 0
        # The extreme tracks every bar; only the COMMIT test needs a readable floor.
        if up:
            if float(highs[i]) > ext_p:
                ext_p, ext_i = float(highs[i]), i
            if readable and ext_p - float(lows[i]) >= f:
                turns.append((ext_i, "peak", ext_p, i))
                up = False
                ext_p, ext_i = float(lows[i]), i
        else:
            if float(lows[i]) < ext_p:
                ext_p, ext_i = float(lows[i]), i
            if readable and float(highs[i]) - ext_p >= f:
                turns.append((ext_i, "valley", ext_p, i))
                up = True
                ext_p, ext_i = float(highs[i]), i
    kind = "peak" if up else "valley"
    if (turns[-1][0], turns[-1][1]) != (ext_i, kind):
        turns.append((ext_i, kind, ext_p, None))
    return turns


def turn_line_views(turns, start):
    """The line split at the box-start seam exactly where today's pivot walk splits — every turn at or left of
    ``start`` is the pre-box view, every turn right of it is the in-box view, re-based to ``start`` — plus the
    commit stamp keyed ``(bar, kind)``.

    The line is handed on as ``(bar, kind, price)`` triples for the staircase to LABEL, never as pivot indices
    to rebuild: ``_build_zigzag`` concatenates every peak before every valley and stable-sorts by bar, so a bar
    carrying BOTH a peak and a valley (his ruling: a bar whose own range covers the floor) would come back
    inverted, alternation would break, and the same-type merge would eat the neighbours — measured, a six-turn
    line down to four. A contiguous slice of an alternating list is alternating, so each view needs no rebuild
    and no second collapse: the floor has already been applied, once, by the line."""
    start = int(start)
    pre = [(int(b), k, float(p)) for (b, k, p, _) in turns if int(b) <= start]
    box = [(int(b) - start, k, float(p)) for (b, k, p, _) in turns if int(b) >= start + 1]
    commits = {(int(b), k): know for (b, k, _, know) in turns}
    return pre, box, commits


def _find_pivots(highs, lows, order):
    """Detect pivot peaks and valleys using a rolling window of given order.

    Vectorized: builds boolean masks for all left/right comparisons at once
    rather than looping per-bar in Python.

    Inequality is asymmetric (>= left, > right for peaks; mirror for valleys)
    so flat tops/bottoms still pivot — for a plateau of N equal highs, only
    the rightmost bar qualifies, which is the structurally meaningful one
    (last touch). Strict > on both sides would silently drop double-tops
    with identical highs.
    """
    n = len(highs)
    if n < 2 * order + 1:
        return [], []

    peak_mask = np.ones(n, dtype=bool)
    valley_mask = np.ones(n, dtype=bool)
    peak_mask[:order] = False
    peak_mask[n - order:] = False
    valley_mask[:order] = False
    valley_mask[n - order:] = False

    for j in range(1, order + 1):
        peak_mask[order:n - order] &= (highs[order:n - order] >= highs[order - j:n - order - j])
        peak_mask[order:n - order] &= (highs[order:n - order] > highs[order + j:n - order + j])
        valley_mask[order:n - order] &= (lows[order:n - order] <= lows[order - j:n - order - j])
        valley_mask[order:n - order] &= (lows[order:n - order] < lows[order + j:n - order + j])

    peaks = np.flatnonzero(peak_mask).tolist()
    valleys = np.flatnonzero(valley_mask).tolist()
    return peaks, valleys


# ---------------------------------------------------------------------------
# Helper: Build Zigzag from Pivots
# ---------------------------------------------------------------------------

def _build_zigzag(peaks_idx, valleys_idx, highs, lows):
    """
    Build a chronologically ordered zigzag from detected pivot points.

    Merges peaks and valleys into a single timeline, enforcing strict
    alternation (peak→valley→peak→...).  When consecutive pivots share
    the same type, the more extreme value is kept (higher peak or lower
    valley).

    Returns:
        list of (bar_index, 'peak'|'valley', price_value)
    """
    pivots = [(p, 'peak', highs[p]) for p in peaks_idx] + \
             [(v, 'valley', lows[v]) for v in valleys_idx]
    pivots.sort(key=lambda x: x[0])

    if not pivots:
        return []

    zigzag = [pivots[0]]
    for pv in pivots[1:]:
        if pv[1] != zigzag[-1][1]:
            # Different type → extend the zigzag
            zigzag.append(pv)
        else:
            # Same type → keep the more extreme
            if pv[1] == 'peak' and pv[2] > zigzag[-1][2]:
                zigzag[-1] = pv
            elif pv[1] == 'valley' and pv[2] < zigzag[-1][2]:
                zigzag[-1] = pv

    return zigzag


# ---------------------------------------------------------------------------
# Helper: Build the swing skeleton for a window (find -> build, composed)
# ---------------------------------------------------------------------------

def _swing_skeleton(highs, lows, order, find_pivots):
    """Build the swing skeleton for a window: the pivot election chained into
    the alternation walk (``find_pivots`` -> ``_build_zigzag``) — THE one
    composition every calibrated detector restates. Returns
    ``(peaks, valleys, zigzag)`` so call sites keep their own guards (empty
    pivot pools, zigzag length floors) verbatim; ``_build_zigzag`` is total on
    empty/one-sided pivot lists, so building before the caller's guard is safe.

    ``find_pivots`` is passed explicitly — each caller hands its OWN
    module-global ``_find_pivots`` — so per-module patching (tests and A/B
    probes pin or swap one caller's substrate without touching the others)
    keeps its exact granularity.
    """
    peaks, valleys = find_pivots(highs, lows, order)
    return peaks, valleys, _build_zigzag(peaks, valleys, highs, lows)


# ---------------------------------------------------------------------------
# Helper: Amplitude-collapse a zigzag to its significant swings
# ---------------------------------------------------------------------------

def _collapse_swings(zigzag, min_amp):
    """Amplitude-filter an alternating zigzag down to its significant swings.

    A percentage/ATR-style zigzag built ON TOP of ``_build_zigzag``: walk the raw
    alternating pivots left-to-right and absorb any reversal smaller than
    ``min_amp`` into the running directional extreme, so only swings that move a
    meaningful fraction of the box survive. This is what makes the traversal read
    adaptive — in a tight box a small absolute move is still a real swing; in a
    wide box the same absolute move is noise — because ``min_amp`` scales with box
    height at the call site.

    Single O(n) left-to-right pass (no fixed-point deletion). The input alternates
    peak/valley, and every branch preserves that alternation, so the output is a
    clean alternating list of ``(bar_index, 'peak'|'valley', price)`` tuples.
    """
    if not zigzag:
        return []
    out = [zigzag[0]]
    for piv in zigzag[1:]:
        last = out[-1]
        if piv[1] == last[1]:
            # Same type (post-merge can produce this): keep the more extreme.
            if ((piv[1] == 'peak' and piv[2] >= last[2]) or
                    (piv[1] == 'valley' and piv[2] <= last[2])):
                out[-1] = piv
        elif abs(piv[2] - last[2]) >= min_amp:
            out.append(piv)                       # a genuine reversal — commit it
        # else: a sub-threshold counter-swing — ABSORB it: the committed
        # extreme stays and the small counter-pivot vanishes (a later deeper
        # same-type extreme extends through the merge branch above). The old
        # pop-and-reanchor form deleted the committed swing instead — its
        # "absorb into out[-2]" leg was unreachable (a committed swing's
        # amplitude guarantees the counter-pivot cannot be more extreme than
        # the older anchor), so a committed swing followed by any small
        # pullback was erased, permanently so at the window tail
        # (2026-08-25 sweep, EC-48 correction).
    return out
