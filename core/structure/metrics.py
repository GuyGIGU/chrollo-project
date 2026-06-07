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

def _vol_trend_from_contractions(contraction_vols):
    """Score volume drying up ACROSS a contraction sequence (the Minervini VCP
    nuance: each pullback should trade lighter, the final coil the quietest).

    Pure measurement, bonus-only convention — never negative; returns None when
    there are fewer than two measurable contractions (a trend needs two points).
    Composite in [0,1]: 0.5 * progressive-decline fraction + 0.5 * final-is-lightest.
    """
    vols = [v for v in (contraction_vols or []) if v is not None and np.isfinite(v)]
    if len(vols) < 2:
        return None
    # Progressive decline — share of consecutive steps where volume does not RISE
    # (5% tolerance, mirroring the depth progressive-tightening tolerance below).
    non_rising = sum(1 for i in range(1, len(vols)) if vols[i] <= vols[i - 1] * 1.05)
    progressive = non_rising / (len(vols) - 1)
    # Final-is-lightest — where the final contraction's volume sits between the
    # lightest and heaviest contraction (1.0 = it IS the lightest, 0.0 = heaviest).
    vmax, vmin = max(vols), min(vols)
    final_lightest = (vmax - vols[-1]) / (vmax - vmin) if vmax > vmin else 0.5
    return round(0.5 * progressive + 0.5 * final_lightest, 4)


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
        vol_trend:       float|None  [0,1] volume drying up across the contractions,
                         lightest at the final coil (the VCP volume nuance); None with
                         <2 contractions. Measured only — NOT part of `quality`.
    """
    empty = {"n_contractions": 0, "depths": [], "final_depth": None,
             "quality": 0.0, "vol_trend": None}
    highs = base_df["High"].values
    lows = base_df["Low"].values
    volumes = base_df["Volume"].values if "Volume" in base_df.columns else None
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
    # Capture the mean volume across each contraction's bars in the same pass —
    # the VCP nuance is that volume should dry up step by step, lightest at the
    # final coil. Volume is measured but NOT folded into `quality` (which stays
    # price-only), so the contraction sub-score and the VCP-Coil tag are unchanged;
    # the volume read is archived raw to validate before it is allowed to matter.
    depths = []
    contraction_vols = []
    for i in range(len(zigzag) - 1):
        a, b = zigzag[i], zigzag[i + 1]
        if a[1] == "peak" and b[1] == "valley":
            peak_p, val_p = a[2], b[2]
            if peak_p > 0 and val_p < peak_p:
                depths.append((peak_p - val_p) / peak_p)
                if volumes is not None:
                    seg = volumes[a[0]:b[0] + 1]
                    contraction_vols.append(
                        float(np.nanmean(seg)) if len(seg) else float("nan")
                    )
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
        "vol_trend": _vol_trend_from_contractions(contraction_vols),
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


# ---------------------------------------------------------------------------
# Worked-equilibrium occupancy — is this candidate range a REAL trading range?
# ---------------------------------------------------------------------------

def measure_equilibrium(base_df, R, S, atr_val):
    """How genuinely *worked* is the candidate range ``[S, R]`` over its window?

    The Phase-B question, in the user's terms: does price RESPECT, TOUCH, and
    ZIGZAG THROUGH both rails CONSTANTLY, with no dead space? A real trading
    range fills its box and re-tests both rails across the whole span. A
    mis-anchored box leaves a *starved band* — dead space — where a one-time
    climax / Automatic-Rally low sits far below where price actually trades, or
    it churns the middle without ever working the rails.

    ``R`` / ``S`` are the candidate's RAIL LEVELS (the Resistance / Support
    anchors), not the window's extremes — that's what makes dead space visible:
    a one-time low pins ``S`` while price dwells higher, leaving the lower bins
    starved.

    Pure measurement, no gates and no points — the validity rule in
    ``box_candidates._validate_base_quality`` and the Scoring Engine decide what
    the numbers are worth.

    Returns dict (safe defaults on a degenerate window so it reads as invalid):
        r_touches, s_touches            touches within TOUCH_TOLERANCE_ATR of each rail
        r_touch_thirds, s_touch_thirds  of 3 equal time-thirds, how many contain a touch
                                        (constant contact vs. clustered at the start)
        lower_dwell, mid_dwell, upper_dwell
                                        fraction of closes in the lower / middle / upper
                                        third of the box (closes beyond a rail count toward
                                        the nearest third); the two halves being worked is
                                        what rules out dead space
        coverage                        fraction of EQ_COVERAGE_BINS box-height bins holding
                                        >= EQ_COVERAGE_MIN_FRAC of closes (starved-band detector)
    """
    empty = {
        "r_touches": 0, "s_touches": 0,
        "r_touch_thirds": 0, "s_touch_thirds": 0,
        "lower_dwell": 0.0, "mid_dwell": 1.0, "upper_dwell": 0.0,
        "coverage": 0.0,
    }
    if base_df is None or len(base_df) == 0:
        return empty
    box = R - S
    if box <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return empty

    highs = base_df["High"].values.astype(float)
    lows = base_df["Low"].values.astype(float)
    closes = base_df["Close"].values.astype(float)
    n = len(closes)

    tb = settings.TOUCH_TOLERANCE_ATR * atr_val
    r_mask = np.abs(highs - R) <= tb
    s_mask = np.abs(lows - S) <= tb

    thirds = np.array_split(np.arange(n), 3)
    r_touch_thirds = sum(1 for t in thirds if len(t) and r_mask[t].any())
    s_touch_thirds = sum(1 for t in thirds if len(t) and s_mask[t].any())

    # Close position in the box: 0 at S, 1 at R. May fall outside [0,1] on
    # excursions; those count toward the nearest third / clamped coverage bin.
    pos = (closes - S) / box
    lower_dwell = float(np.mean(pos < 1.0 / 3.0))
    upper_dwell = float(np.mean(pos > 2.0 / 3.0))
    mid_dwell = float(np.mean((pos >= 1.0 / 3.0) & (pos <= 2.0 / 3.0)))

    nb = settings.EQ_COVERAGE_BINS
    bin_idx = np.clip((np.clip(pos, 0.0, 1.0) * nb).astype(int), 0, nb - 1)
    counts = np.bincount(bin_idx, minlength=nb)
    min_count = max(1.0, settings.EQ_COVERAGE_MIN_FRAC * n)
    coverage = float(np.mean(counts >= min_count))

    return {
        "r_touches": int(r_mask.sum()),
        "s_touches": int(s_mask.sum()),
        "r_touch_thirds": int(r_touch_thirds),
        "s_touch_thirds": int(s_touch_thirds),
        "lower_dwell": round(lower_dwell, 4),
        "mid_dwell": round(mid_dwell, 4),
        "upper_dwell": round(upper_dwell, 4),
        "coverage": round(coverage, 4),
    }
