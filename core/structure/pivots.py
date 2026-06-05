"""Pivot and zigzag helpers shared by structure detectors."""
from __future__ import annotations

import numpy as np


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
