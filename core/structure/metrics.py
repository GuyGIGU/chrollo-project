"""Pure structure measurements derived from an already-detected base."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from config import settings
from core.structure.pivots import _build_zigzag, _find_pivots


def measure_bar_compression(base_df, box_height, atr_val):
    """Measure how quiet/narrow the bars are inside the detected base.

    Box width says how tight the *range* is. This reports the texture inside
    that range: whether most bars are themselves low-spread / low-volatility
    bars. Pure measurement only; no gates, no points.

    Returns dict:
        median_spread_atr      median daily spread divided by ATR snapshot
        p80_spread_atr         80th percentile spread divided by ATR snapshot
        median_spread_pct_box  median daily spread divided by box height
        tight_bar_pct          share of base bars with spread <= ATR snapshot
    """
    empty = {
        "median_spread_atr": None,
        "p80_spread_atr": None,
        "median_spread_pct_box": None,
        "tight_bar_pct": 0.0,
    }
    if base_df is None or len(base_df) == 0:
        return empty
    if atr_val is None or atr_val <= 0 or box_height is None or box_height <= 0:
        return empty

    try:
        if "Spread" in base_df.columns:
            spreads = base_df["Spread"].astype(float)
        else:
            spreads = base_df["High"].astype(float) - base_df["Low"].astype(float)
        spreads = spreads.replace([np.inf, -np.inf], np.nan).dropna()
    except (KeyError, TypeError, ValueError):
        return empty

    if spreads.empty:
        return empty

    median_spread = float(spreads.median())
    p80_spread = float(spreads.quantile(0.80))
    tight_bar_pct = float((spreads <= atr_val).mean())

    return {
        "median_spread_atr": round(median_spread / atr_val, 4),
        "p80_spread_atr": round(p80_spread / atr_val, 4),
        "median_spread_pct_box": round(median_spread / box_height, 4),
        "tight_bar_pct": round(tight_bar_pct, 4),
    }


# ---------------------------------------------------------------------------
# VCP progressive-contraction footprint
# ---------------------------------------------------------------------------

def measure_contractions(base_df, order=None):
    """Measure the VCP progressive-contraction footprint within a base window.

    The defining feature of a Minervini VCP is a sequence of 2-6 pullbacks,
    each TIGHTER than the last (e.g. 18% -> 12% -> 6%), ending in a very tight
    final contraction. The engine already finds a tight *box*; box_width and
    ATR-squeeze are STATIC tightness (how tight is it now). This measures the
    *process* of tightening (is it coiling?) that the static metrics can't see.

    Reuses the Phase B zigzag machinery. Each peak->valley downswing in the
    zigzag is one contraction; depth = (peak - valley) / peak. We measure the
    sequence over the base (consolidation) window only — the initial BC->AR
    descent into the base is deliberately excluded (it's the entry into the
    base, not a contraction within it, and it's the early-chop the cand_start
    trim already removes from boundary/quality measurement).

    Returns dict:
        n_contractions:  int   number of peak->valley downswings
        depths:          list[float] chronological fractional drawdowns
        final_depth:     float|None  depth of the last (rightmost) contraction
        quality:         float in [0,1]  composite:
                         0.40*count + 0.35*progressive_tightening + 0.25*final_tight
    """
    empty = {"n_contractions": 0, "depths": [], "final_depth": None, "quality": 0.0}
    highs = base_df["High"].values
    lows = base_df["Low"].values
    n = len(highs)
    if order is None:
        order = (settings.PIVOT_ORDER_LONG if n >= settings.PIVOT_ORDER_THRESHOLD
                 else settings.PIVOT_ORDER_SHORT)
    if n < 2 * order + 1:
        return empty

    peaks, valleys = _find_pivots(highs, lows, order)
    if not peaks or not valleys:
        return empty
    zigzag = _build_zigzag(peaks, valleys, highs, lows)
    if len(zigzag) < 2:
        return empty

    # Each peak->valley transition is a contraction (a pullback within the base).
    depths = []
    for i in range(len(zigzag) - 1):
        a, b = zigzag[i], zigzag[i + 1]
        if a[1] == "peak" and b[1] == "valley":
            peak_p, val_p = a[2], b[2]
            if peak_p > 0 and val_p < peak_p:
                depths.append((peak_p - val_p) / peak_p)
    if not depths:
        return empty

    n_c = len(depths)
    final_depth = depths[-1]

    # 1) Count score — Minervini's 2-6 contractions, 3-4 typical. Full credit
    #    inside the ideal band; partial for a single contraction or a choppy
    #    over-count (too many swings = not a clean coil).
    lo, hi = settings.CONTRACTION_IDEAL_MIN, settings.CONTRACTION_IDEAL_MAX
    if lo <= n_c <= hi:
        count_score = 1.0
    elif n_c == 1:
        count_score = 0.4
    elif n_c <= hi + 2:
        count_score = 0.6
    else:
        count_score = 0.3

    # 2) Progressive tightening — fraction of consecutive steps that don't
    #    WIDEN (5% tolerance so a tiny uptick isn't punished). 1.0 = each
    #    pullback <= the previous one, the textbook 18->12->6 footprint.
    if n_c >= 2:
        non_widening = sum(1 for i in range(1, n_c) if depths[i] <= depths[i - 1] * 1.05)
        progressive = non_widening / (n_c - 1)
    else:
        progressive = 0.5  # single contraction: neutral, can't judge a trend

    # 3) Final-contraction tightness — the right-most pullback should be the
    #    tightest (max compression, no supply left). Linear ramp.
    full = settings.CONTRACTION_FINAL_TIGHT_PCT
    zero = settings.CONTRACTION_FINAL_LOOSE_PCT
    if final_depth <= full:
        final_score = 1.0
    elif final_depth >= zero:
        final_score = 0.0
    else:
        final_score = (zero - final_depth) / (zero - full)

    quality = 0.40 * count_score + 0.35 * progressive + 0.25 * final_score
    return {
        "n_contractions": n_c,
        "depths": [round(d, 4) for d in depths],
        "final_depth": round(final_depth, 4),
        "quality": round(quality, 4),
    }


# ---------------------------------------------------------------------------
# Ascending support / higher-lows footprint
# ---------------------------------------------------------------------------

def measure_support_slope(base_df, atr_val, order=None):
    """Measure whether the base's swing lows are stair-stepping UP (rising support).

    A flat box with a *rising floor* is a much stronger coil than a flat box with
    a flat/sagging floor — demand is getting more aggressive into each pullback.
    This is the Minervini "tennis-ball action" / Qullamaggie "higher lows" footprint
    that the static box-width and ATR-squeeze metrics cannot see.

    Reuses the same Phase B zigzag as measure_contractions, but reads the VALLEY
    sequence (the swing lows) and fits a line through them. The slope is ATR-
    normalized so it's comparable across price levels and tickers.

    Bonus-only / measure-first: a flat or descending floor returns quality 0 — it
    is never penalized, only rewarded when genuinely ascending.

    Returns dict:
        n_valleys:       int     number of zigzag valley lows used in the fit
        slope_atr:       float|None  rise per bar in ATRs (positive = ascending); None if < 2 valleys
        higher_low_frac: float   fraction of consecutive valley pairs that step up [0,1]
        quality:         float in [0,1]  composite: 0.6*slope_score + 0.4*higher_low_frac
    """
    empty = {"n_valleys": 0, "slope_atr": None, "higher_low_frac": 0.0, "quality": 0.0}
    if atr_val is None or atr_val <= 0:
        return empty
    highs = base_df["High"].values
    lows = base_df["Low"].values
    n = len(highs)
    if order is None:
        order = (settings.PIVOT_ORDER_LONG if n >= settings.PIVOT_ORDER_THRESHOLD
                 else settings.PIVOT_ORDER_SHORT)
    if n < 2 * order + 1:
        return empty

    peaks, valleys = _find_pivots(highs, lows, order)
    if not peaks or not valleys:
        return empty
    zigzag = _build_zigzag(peaks, valleys, highs, lows)

    # Pull the valley points (bar index + low price) in chronological order.
    valley_pts = [(idx, price) for (idx, kind, price) in zigzag if kind == "valley"]
    if len(valley_pts) < 2:
        return empty

    xs = np.array([p[0] for p in valley_pts], dtype=float)
    ys = np.array([p[1] for p in valley_pts], dtype=float)

    # Least-squares slope (price per bar) through the valley lows, then ATR-normalize.
    slope = float(np.polyfit(xs, ys, 1)[0])
    # polyfit can return a non-finite slope on a degenerate / poorly-conditioned
    # fit; bail to neutral rather than propagate a NaN downstream (a single NaN
    # float poisons the JSON the /screener-data/ endpoint serves).
    if not np.isfinite(slope):
        return empty
    slope_atr = slope / atr_val

    # Consistency: fraction of consecutive valleys that actually step up.
    higher = sum(1 for i in range(1, len(ys)) if ys[i] > ys[i - 1])
    higher_low_frac = higher / (len(ys) - 1)

    # Slope score — linear ramp from flat/descending (0) to FULL_SLOPE ATRs/bar (1).
    full = settings.ASCENDING_SUPPORT_FULL_SLOPE
    if slope_atr <= 0:
        slope_score = 0.0
    elif slope_atr >= full:
        slope_score = 1.0
    else:
        slope_score = slope_atr / full

    quality = 0.6 * slope_score + 0.4 * higher_low_frac
    return {
        "n_valleys": len(valley_pts),
        "slope_atr": round(slope_atr, 4),
        "higher_low_frac": round(higher_low_frac, 4),
        "quality": round(quality, 4),
    }


# ---------------------------------------------------------------------------
# Measurement: Volume signature at the R/S touch bars
# ---------------------------------------------------------------------------

def measure_touch_volume(base_df: "pd.DataFrame", res_avg: float, sup_avg: float,
                         atr_val: float) -> tuple[Optional[float], Optional[float]]:
    """
    How heavy was volume when price visited the box's ceiling (R) and floor (S)?

    Returns ``(r_touch_vol_z, s_touch_vol_z)`` — each a z-score of the touch-bar
    volume measured against the base's own volume distribution. Either value is
    ``None`` when there were no touches on that side or volume has no spread.

    This is the Wyckoff supply/demand asymmetry the LPS gate alone can't see:
        r_touch_vol_z < 0  -> "No Supply": price reaches R on quiet volume (bullish)
        r_touch_vol_z > 0  -> heavy selling into R (distribution flavour; a warning)
        s_touch_vol_z > 0  -> "Demand at S": heavy hands defending the floor

    Pure measurement — it reports the numbers and assigns no score. The Scoring
    Engine and the tag chips decide what the numbers are worth.
    """
    touch_band = settings.TOUCH_TOLERANCE_ATR * atr_val
    r_touch_mask = (base_df['High'] - res_avg).abs() <= touch_band
    s_touch_mask = (base_df['Low'] - sup_avg).abs() <= touch_band
    vol_mean_base = float(base_df['Volume'].mean())
    vol_std_base = float(base_df['Volume'].std())

    if vol_std_base > 0 and r_touch_mask.any():
        r_touch_vol_z: Optional[float] = float(
            (base_df.loc[r_touch_mask, 'Volume'].mean() - vol_mean_base) / vol_std_base
        )
    else:
        r_touch_vol_z = None

    if vol_std_base > 0 and s_touch_mask.any():
        s_touch_vol_z: Optional[float] = float(
            (base_df.loc[s_touch_mask, 'Volume'].mean() - vol_mean_base) / vol_std_base
        )
    else:
        s_touch_vol_z = None

    return r_touch_vol_z, s_touch_vol_z
