"""
Swing segmentation — the "layered split" between trend and consolidation.

This is the descriptive middle layer the engine was missing: between "here are
the swings" (the zigzag) and "find a box" (consolidation detection), it labels
the swing path with ATR-normalized displacement and locates the **root swing** —
the bridge where a directional trend converts into a range via the first big
counter-burst (BC -> AR). See docs/segmentation_research.md.

PURE MEASUREMENT (Phase 1). It:
  - emits raw, descriptive numbers per swing (signed ATR displacement),
  - reports window swing-efficiency (|net| / path length, Kaufman's ratio on
    pivots — the young-base-friendly ADX replacement),
  - flags the candidate root swing (climax pivot -> first big counter-burst).

It bakes in NO trend/range cutoff (case-dependent; calibrated later against the
fidelity set) and it NEVER gates or scores. The live pipeline consumes it only
as a display/scoping aid: when the original BC anchor drifted too far back, the
pipeline may reconnect the Phase-A anchor to a recent root swing for diagnostics
and chart-region labels. R/S, setup eligibility, score, and tier do not consume
the segmentation output.

Reuses the shared zigzag machinery in pivots.py rather than re-implementing
pivot detection.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from config import settings
from core.structure.pivots import _build_zigzag, _find_pivots


def _empty() -> dict:
    return {
        "swings": [],
        "n_swings": 0,
        "net_disp_atr": None,
        "path_atr": None,
        "efficiency": None,
        "dominant_direction": 0,
        "root_swing": None,
    }


def _find_root_swing(zigzag, swings, atr_val, dominant, base_off) -> Optional[dict]:
    """Locate the root swing — the trend->range bridge.

    The climax is the extreme pivot in the dominant direction (highest peak when
    the window trends up, lowest valley when it trends down). The root swing's
    counter-leg is the swing FROM that climax to the next pivot — the AR. Its
    "burst" character is reported as the ratio of its ATR displacement to the
    median of the trend's prior pullbacks (counter-direction legs before the
    climax): a large ratio is the "first big counter-burst" that marks
    exhaustion. The ratio is emitted raw; no threshold is applied here.
    """
    if dominant == 0 or len(zigzag) < 3:
        return None

    # Climax = the extreme pivot in the dominant direction.
    if dominant > 0:
        peak_pivots = [(i, pv[2]) for i, pv in enumerate(zigzag) if pv[1] == "peak"]
        if not peak_pivots:
            return None
        climax_i = max(peak_pivots, key=lambda t: t[1])[0]
    else:
        valley_pivots = [(i, pv[2]) for i, pv in enumerate(zigzag) if pv[1] == "valley"]
        if not valley_pivots:
            return None
        climax_i = min(valley_pivots, key=lambda t: t[1])[0]

    # Need a counter-leg after the climax to form the bridge.
    if climax_i + 1 >= len(zigzag):
        return None

    bc_pivot = zigzag[climax_i]
    ar_pivot = zigzag[climax_i + 1]
    counter_disp = abs(ar_pivot[2] - bc_pivot[2]) / atr_val
    trend_disp = abs(bc_pivot[2] - zigzag[0][2]) / atr_val

    # Prior pullbacks = counter-direction legs that occurred during the trend
    # (swing index < climax_i, direction opposite the dominant trend).
    prior_pullbacks = [
        s["abs_disp_atr"] for s in swings[:climax_i] if s["direction"] == -dominant
    ]
    ref = float(np.median(prior_pullbacks)) if prior_pullbacks else None
    burst_ratio = (counter_disp / ref) if (ref is not None and ref > 0) else None

    return {
        "swing_index": int(climax_i),          # index into `swings` of the AR leg
        "bc_bar": int(base_off + bc_pivot[0]),  # df-positional climax bar
        "ar_bar": int(base_off + ar_pivot[0]),  # df-positional AR bar
        "trend_direction": int(dominant),
        "trend_disp_atr": round(float(trend_disp), 4),
        "counter_disp_atr": round(float(counter_disp), 4),
        "counter_burst_ratio": (round(float(burst_ratio), 4)
                                if burst_ratio is not None else None),
    }


def segment_swings(df, atr_val, *, lookback: Optional[int] = None,
                   order: Optional[int] = None) -> dict:
    """Measure the swing structure of ``df`` and locate the root swing.

    Args:
        df: per-ticker OHLC frame (needs 'High'/'Low'). df-positional bar
            indices in the result line up with this frame.
        atr_val: ATR snapshot used to normalize every displacement. <=0 / NaN
            returns the empty result (we never divide by a bad volatility frame).
        lookback: if given and < len(df), segment only the last ``lookback`` bars
            (emitted bar indices stay df-positional via the base offset). None =
            whole frame.
        order: pivot half-window. None picks PIVOT_ORDER_LONG/SHORT by window
            size, matching the rest of the structure engine.

    Returns a JSON-safe dict (see module docstring / _empty for the shape).
    All measurement, no opinion.
    """
    if atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return _empty()

    n_all = len(df)
    if n_all < 5:
        return _empty()

    if lookback is not None and 0 < lookback < n_all:
        win = df.iloc[n_all - lookback:]
    else:
        win = df
    base_off = n_all - len(win)

    try:
        highs = win["High"].values.astype(float)
        lows = win["Low"].values.astype(float)
    except (KeyError, TypeError, ValueError):
        return _empty()
    n = len(highs)

    if order is None:
        order = (settings.PIVOT_ORDER_LONG if n >= settings.PIVOT_ORDER_THRESHOLD
                 else settings.PIVOT_ORDER_SHORT)

    peaks, valleys = _find_pivots(highs, lows, order)
    if not peaks or not valleys:
        return _empty()

    zigzag = _build_zigzag(peaks, valleys, highs, lows)
    if len(zigzag) < 2:
        return _empty()

    # One swing per consecutive pivot pair; displacement signed + ATR-normalized.
    swings = []
    for i in range(len(zigzag) - 1):
        a, b = zigzag[i], zigzag[i + 1]
        disp = (b[2] - a[2]) / atr_val
        swings.append({
            "start_bar": int(base_off + a[0]),
            "end_bar": int(base_off + b[0]),
            "direction": 1 if disp > 0 else (-1 if disp < 0 else 0),
            "disp_atr": round(float(disp), 4),
            "abs_disp_atr": round(abs(float(disp)), 4),
        })

    net_disp = (zigzag[-1][2] - zigzag[0][2]) / atr_val
    path = float(sum(s["abs_disp_atr"] for s in swings))
    efficiency = (abs(net_disp) / path) if path > 0 else None
    dominant = 1 if net_disp > 0 else (-1 if net_disp < 0 else 0)

    root = _find_root_swing(zigzag, swings, atr_val, dominant, base_off)

    return {
        "swings": swings,
        "n_swings": len(swings),
        "net_disp_atr": round(float(net_disp), 4),
        "path_atr": round(path, 4),
        "efficiency": round(float(efficiency), 4) if efficiency is not None else None,
        "dominant_direction": int(dominant),
        "root_swing": root,
    }
