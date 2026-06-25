"""Perceptually Important Points (PIP) — a multi-resolution swing skeleton.

MEASURE-ONLY (Phase 1). A scale-free, top-down alternative to the fixed-``order``
rolling-window pivots in ``pivots.py``. Instead of one ``order`` that either
over-fragments (order 1) or smooths real turns away (order 2), PIP ranks turning
points by IMPORTANCE — the max distance to the chord between already-chosen
points (Douglas-Peucker for price) — and returns them most-important-first.

Any top-K prefix is therefore a coarser skeleton of the SAME chart, so the engine
can read it coarse->fine: top-5 = the macro trend -> climax, top-15 = the box,
top-40 = the inner structure — nested resolutions of one skeleton, which is the
"trend -> climax -> earliest tightest box recursively -> inner structure" read.

It emits the SAME shape as ``pivots._build_zigzag`` — ``list[(bar, 'peak'|
'valley', price)]`` — and reuses that helper for High/Low snapping and strict
alternation, so PIP is a drop-in-comparable skeleton (and a clean future swap
point). NOTHING in the live path imports this yet: it exists to be rendered and
eyeballed (``tools/pip_preview.py``) before any integration. The measure-first
discipline mirrors how the segmentation layer was added — see
``docs/segmentation_research.md``.
"""
from __future__ import annotations

import bisect
from typing import Optional

import numpy as np

from core.structure.pivots import _build_zigzag


def _series(highs: np.ndarray, lows: np.ndarray, mode: str) -> np.ndarray:
    """The 1-D series PIP ranks importance on. ``hl2`` (bar midpoint) is the
    default — less jittery than close for turning points; turns then snap to the
    actual High/Low. ``high``/``low``/``close`` available as knobs."""
    if mode == "high":
        return highs
    if mode == "low":
        return lows
    return (highs + lows) / 2.0  # hl2 (and the fallback)


def _chord_value(left_i: int, left_p: float, right_i: int, right_p: float, i: int) -> float:
    if right_i == left_i:
        return left_p
    t = (i - left_i) / (right_i - left_i)
    return left_p + (right_p - left_p) * t


def _distance(P: np.ndarray, left_i: int, right_i: int, i: int,
              metric: str, price_scale: float) -> float:
    """Distance from bar ``i`` to the chord spanning its bracketing PIPs."""
    chord = _chord_value(left_i, P[left_i], right_i, P[right_i], i)
    vertical = abs(float(P[i]) - chord)
    if metric != "perpendicular":
        return vertical
    # Perpendicular needs the time axis in price units, or it is meaningless
    # across mismatched axes: treat 1 bar == ``price_scale`` price units.
    dx = (right_i - left_i) * price_scale
    dy = float(P[right_i] - P[left_i])
    denom = float(np.hypot(dx, dy))
    if denom == 0.0:
        return vertical
    num = abs(dy * (i - left_i) * price_scale - dx * (float(P[i]) - float(P[left_i])))
    return num / denom


def pip_indices(P, *, n_points: Optional[int] = None, dist_min: Optional[float] = None,
                metric: str = "vertical") -> list[int]:
    """Bar indices in IMPORTANCE order: endpoints first, then by descending
    distance to the running chord.

    Strictly nested by construction: the greedy pick each round is the global
    max-distance bar, independent of the stopping target, so ``pip_indices(P,
    n_points=K)`` is exactly ``pip_indices(P, n_points=K+1)[:K]`` — the
    multi-resolution guarantee.

    ``dist_min`` is a fraction of the series price range (scale-free): selection
    stops once the most-important remaining bar deviates by less than that.
    """
    P = np.asarray(P, dtype=float)
    n = len(P)
    if n < 3:
        return list(range(n))
    price_range = float(np.nanmax(P) - np.nanmin(P))
    if price_range <= 0:
        return []  # flat window: no salient turns
    price_scale = price_range / n
    floor = (float(dist_min) * price_range) if dist_min is not None else 0.0
    target = n if n_points is None else max(2, min(int(n_points), n))

    order = [0, n - 1]
    selected_sorted = [0, n - 1]
    while len(order) < target:
        best_i, best_d = -1, -1.0
        for s in range(len(selected_sorted) - 1):
            left_i, right_i = selected_sorted[s], selected_sorted[s + 1]
            for i in range(left_i + 1, right_i):
                d = _distance(P, left_i, right_i, i, metric, price_scale)
                if d > best_d:
                    best_d, best_i = d, i
        if best_i < 0 or best_d <= 0.0 or best_d < floor:
            break
        order.append(best_i)
        bisect.insort(selected_sorted, best_i)
    return order


def pip_pivots(highs, lows, *, n_points: Optional[int] = None,
               dist_min: Optional[float] = None, metric: str = "vertical",
               series: str = "hl2") -> list:
    """PIP skeleton as ``[(bar, 'peak'|'valley', price)]``.

    Classifies each elected PIP as a peak or valley vs its PIP-neighbours, then
    routes through ``_build_zigzag`` so snapping (peak->High, valley->Low) and
    strict alternation are byte-for-byte the same as the rest of the engine.
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = len(highs)
    if n < 3 or len(lows) != n:
        return []
    P = _series(highs, lows, series)
    idx = pip_indices(P, n_points=n_points, dist_min=dist_min, metric=metric)
    if len(idx) < 2:
        return []

    idx_sorted = sorted(idx)
    peaks: list[int] = []
    valleys: list[int] = []
    for pos, i in enumerate(idx_sorted):
        neighbours = []
        if pos > 0:
            neighbours.append(P[idx_sorted[pos - 1]])
        if pos < len(idx_sorted) - 1:
            neighbours.append(P[idx_sorted[pos + 1]])
        ref = float(np.mean(neighbours)) if neighbours else float(P[i])
        if float(P[i]) >= ref:
            peaks.append(i)
        else:
            valleys.append(i)

    return _build_zigzag(peaks, valleys, highs, lows)


def pip_skeleton(df, levels=(5, 15, 40), *, metric: str = "vertical",
                 series: str = "hl2") -> dict:
    """Skeletons at several resolutions for the coarse->fine recursive read.

    Returns ``{n_points: [(bar, kind, price), ...]}``. df-positional bar indices.
    """
    if df is None or len(df) < 3 or not ({"High", "Low"} <= set(df.columns)):
        return {}
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    return {
        int(k): pip_pivots(highs, lows, n_points=int(k), metric=metric, series=series)
        for k in levels
    }
