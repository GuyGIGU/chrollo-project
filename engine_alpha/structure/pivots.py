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
        elif len(out) >= 2:
            # Sub-threshold counter-swing: drop the small reversal's start and let
            # the prior same-type extreme (out[-2]) absorb this pivot.
            out.pop()
            prev = out[-1]
            if ((piv[1] == 'peak' and piv[2] >= prev[2]) or
                    (piv[1] == 'valley' and piv[2] <= prev[2])):
                out[-1] = piv
        # else: a sub-threshold move off the very first pivot — skip it; the
        # anchor stays until a real reversal arrives.
    return out
