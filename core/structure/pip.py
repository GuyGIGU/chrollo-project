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
point). One flag-gated wire remains, default-off, feeding ONLY the Phase-A
overlay via ``segment_swings`` (never R/S/score/tier):

  * ``PIP_MACRO_PHASE_A_ENABLED`` — the MACRO read (``macro_bridge_zigzag``):
    coarse->fine over top-K prefixes, stopping at the SMALLEST skeleton that
    holds a confirmed climax->AR bridge. At the stop-K only macro turns exist,
    so late range retests and noise dips are not in the skeleton to steal the
    climax or the AR.

(The earlier FLAT wire — ``PIP_PIVOTS_ENABLED``, one ``dist_min`` threshold as
a drop-in ``segment_swings`` substrate — was eyeball-gated OFF as a wash
(commit d43e7fd: fixes some inverted climax->AR overlays, creates others —
GBTG/PLSE/CGNX) and deleted 2026-07-03; see docs/flag_ledger.md. ``pip_pivots``
itself stays: it is the substrate the macro read refines, and the direct API
for tools/tests.)

The measure-first discipline mirrors how the segmentation layer was added — see
``docs/segmentation_research.md``.
"""
from __future__ import annotations

import bisect
from typing import Optional

import numpy as np

from config import settings
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
    return _zigzag_from_indices(sorted(idx), P, highs, lows)


def _zigzag_from_indices(idx_sorted: list[int], P: np.ndarray,
                         highs: np.ndarray, lows: np.ndarray) -> list:
    """Classify already-elected PIP bars as peaks/valleys vs their PIP
    neighbours, then route through ``_build_zigzag`` for High/Low snapping and
    strict alternation — the shared tail of every PIP->zigzag conversion."""
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


def _validated_bridge(zigzag: list, last_bar: int,
                      highs: np.ndarray, lows: np.ndarray,
                      max_post_excess: float = 0.25,
                      min_base_bars: int = 10,
                      floor_frac: float = 0.5,
                      osc_frac: float = 0.3):
    """The CONFIRMED, VALIDATED macro climax->AR bridge in this skeleton —
    ``(climax_i, ar_i)`` zigzag indices, or ``None``.

    Mirrors ``segmentation._find_root_swing``'s conventions: dominant direction
    from the zigzag's net displacement; climax = the extreme pivot in that
    direction (leftmost on ties — the pivot that BIRTHS the range). Confirmed
    means a pivot exists after the climax AND it is INTERIOR (bar < last_bar):
    the right edge is "now", an unconfirmed extreme, never an AR.

    A bridge is a TRUE Phase-A root swing only if it LEADS TO AN ACTUAL
    EQUILIBRIUM (operator rule, 2026-07-02): the read stays linear — find
    where the trend ends first — but the trend-end claim is validated by what
    follows it. Guards, in order (BC form; SC mirrored):

    * AR EXTREMITY — the AR must be the extreme of its own reaction leg. A
      bridge whose leg contains a deeper low (BC roots) / higher high (SC
      roots) than its AR endpoint is glued ACROSS other structure — the TNC
      class, where the "reaction" spanned an entire crash and recovery.
    * BASE EXISTS IN TIME — at least ``min_base_bars`` bars after the AR;
      a reaction with no room for a base yet is a claim, not a story.
    * CLIMAX TERMINALITY — after the AR, price may exceed the climax by at
      most ``max_post_excess`` x the bridge height. A "climax" that is
      taken out was a pause in an ongoing trend, not the swing that birthed
      a range — the ATI/AXTA "setups with no base" class. Honest range pokes
      (BYD +0.20x, GOOD +0.13x) pass; trend continuation (ATI +0.93x) fails.
    * FLOOR HOLDS — post-AR lows may undercut the AR by at most
      ``floor_frac`` x the bridge height (spring-tolerant). Deeper = the
      "AR" was a waypoint in a continuing markdown, no equilibrium.
    * IT OSCILLATES — after the AR, price must rally >= ``osc_frac`` x the
      bridge height off the AR AND subsequently give back the same amount:
      one real two-sided traversal, the minimal signature of a worked
      equilibrium. A V that runs straight back up never based.
    """
    if len(zigzag) < 2:
        return None
    net = float(zigzag[-1][2]) - float(zigzag[0][2])
    if net == 0.0:
        return None
    if net > 0:
        # Climax CANDIDATES by descending extremity — not just the argmax. An
        # unconfirmable extreme (a fresh right-edge higher-high with no held
        # reaction after it) must not kill the read when the next-most-extreme
        # peak has a validated bridge; the terminality guard still bounds how
        # far any later high may exceed the chosen climax (the BYD case).
        cands = sorted((i for i, (_b, k, _p) in enumerate(zigzag) if k == "peak"),
                       key=lambda i: -zigzag[i][2])
    else:
        cands = sorted((i for i, (_b, k, _p) in enumerate(zigzag) if k == "valley"),
                       key=lambda i: zigzag[i][2])

    for climax_i in cands:
        if climax_i + 1 >= len(zigzag):
            continue
        ar_bar = int(zigzag[climax_i + 1][0])
        if ar_bar >= int(last_bar):
            continue
        # Base exists in time: room for an equilibrium after the AR.
        if int(last_bar) - ar_bar < int(min_base_bars):
            continue
        cb = int(zigzag[climax_i][0])
        if net > 0:
            # AR extremity: no deeper low inside the leg than the AR itself.
            if float(np.min(lows[cb:ar_bar + 1])) < float(lows[ar_bar]) - 1e-9:
                continue
            bridge_h = float(highs[cb]) - float(lows[ar_bar])
            if bridge_h <= 0:
                continue
            post_hi = highs[ar_bar + 1:]
            post_lo = lows[ar_bar + 1:]
            # Climax terminality: post-AR highs bounded vs bridge height.
            if post_hi.size and float(np.max(post_hi)) > float(highs[cb]) + max_post_excess * bridge_h:
                continue
            # Floor holds: the equilibrium may not break down below the AR.
            if post_lo.size and float(np.min(post_lo)) < float(lows[ar_bar]) - floor_frac * bridge_h:
                continue
            if not _oscillates_up(post_hi, post_lo, float(lows[ar_bar]),
                                  osc_frac * bridge_h):
                continue
        else:
            # SC-root mirror of every guard.
            if float(np.max(highs[cb:ar_bar + 1])) > float(highs[ar_bar]) + 1e-9:
                continue
            bridge_h = float(highs[ar_bar]) - float(lows[cb])
            if bridge_h <= 0:
                continue
            post_hi = highs[ar_bar + 1:]
            post_lo = lows[ar_bar + 1:]
            if post_lo.size and float(np.min(post_lo)) < float(lows[cb]) - max_post_excess * bridge_h:
                continue
            if post_hi.size and float(np.max(post_hi)) > float(highs[ar_bar]) + floor_frac * bridge_h:
                continue
            if not _oscillates_down(post_hi, post_lo, float(highs[ar_bar]),
                                    osc_frac * bridge_h):
                continue
        return climax_i, climax_i + 1
    return None


def _oscillates_up(post_hi: np.ndarray, post_lo: np.ndarray,
                   ar_low: float, amp: float) -> bool:
    """One two-sided traversal after a BC->AR: price rallies >= ``amp`` off
    the AR low, then gives back >= ``amp`` from the running high. O(n)."""
    if post_hi.size == 0:
        return False
    run_max = -np.inf
    for h, low in zip(post_hi, post_lo):
        run_max = max(run_max, float(h))
        if run_max - ar_low >= amp and run_max - float(low) >= amp:
            return True
    return False


def _oscillates_down(post_hi: np.ndarray, post_lo: np.ndarray,
                     ar_high: float, amp: float) -> bool:
    """SC mirror: price reacts >= ``amp`` down off the AR high, then recovers
    >= ``amp`` from the running low."""
    if post_lo.size == 0:
        return False
    run_min = np.inf
    for h, low in zip(post_hi, post_lo):
        run_min = min(run_min, float(low))
        if ar_high - run_min >= amp and float(h) - run_min >= amp:
            return True
    return False


def macro_bridge_zigzag(highs, lows, *, k_start: int = 4, k_max: int = 24,
                        metric: str = "vertical", series: str = "hl2",
                        with_k: bool = False):
    """The coarse->fine MACRO Phase-A read: the zigzag at the SMALLEST top-K
    importance prefix that holds a confirmed climax->AR bridge.

    Because ``pip_indices`` is strictly nested, the ranking is computed ONCE at
    ``k_max`` and every coarser skeleton is a free prefix. Walking K upward and
    stopping at the first confirmed bridge is the theft protection: at the
    stop-K the skeleton contains only the macro turns elected SO FAR, so a late
    range retest a few cents above the true climax — or a shallow first dip in
    front of the real AR — is simply not in the skeleton to be chosen. (The
    flat ``dist_min`` read admits every above-threshold turn at once, which is
    exactly how it created the GBTG/PLSE/CGNX inversions.)

    No VALIDATED bridge by ``k_max`` (a fresh climax whose reaction hasn't
    held, a trend still making highs, a leg glued across other structure) is
    an ABSTENTION: return ``[]`` and let the caller use the calibrated order-N
    read instead. The macro read speaks only when it has a validated story —
    that is the merge contract with the shipped engine (chart-jury decision,
    2026-07-02).

    Returns the zigzag (``[]`` on abstention), or ``(zigzag, k)`` when
    ``with_k`` (``k`` is ``None`` on abstention) for tools/tests.
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = len(highs)
    if n < 3 or len(lows) != n:
        return ([], None) if with_k else []
    P = _series(highs, lows, series)
    order = pip_indices(P, n_points=k_max, metric=metric)
    if len(order) < 2:
        return ([], None) if with_k else []

    last_bar = n - 1
    excess = float(getattr(settings, "PIP_MACRO_MAX_POST_EXCESS", 0.25))
    min_base = int(getattr(settings, "PIP_MACRO_MIN_BASE_BARS", 10))
    floor_frac = float(getattr(settings, "PIP_MACRO_EQ_FLOOR_FRAC", 0.5))
    osc_frac = float(getattr(settings, "PIP_MACRO_EQ_OSC_FRAC", 0.3))
    for k in range(min(max(k_start, 2), len(order)), len(order) + 1):
        zigzag = _zigzag_from_indices(sorted(order[:k]), P, highs, lows)
        if len(zigzag) < 2:
            continue
        bridge = _validated_bridge(zigzag, last_bar, highs, lows, excess,
                                   min_base, floor_frac, osc_frac)
        if bridge is not None:
            # BINDING validation: hand downstream ONLY the validated story —
            # the approach legs up to the climax, ending at the AR. Every
            # downstream read (the resolve_phase_a bridge search over swings,
            # or _find_root_swing's climax->next-pivot) can then only ever
            # draw the guarded bridge, never an unvalidated sibling swing.
            _climax_i, ar_i = bridge
            out = zigzag[:ar_i + 1]
            return (out, k) if with_k else out
    return ([], None) if with_k else []


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
