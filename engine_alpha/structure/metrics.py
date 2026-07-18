"""Pure structure measurements derived from an already-detected base."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.pivots import (_collapse_swings, _find_pivots,
                                           _pivot_order, _swing_skeleton)

# L2 Wyckoff event reader — relocated to engine_alpha.structure.box_events. Re-exported
# here so every existing ``from engine_alpha.structure.metrics import ...`` site keeps
# working unchanged (pure module peel, byte-identical behavior). box_events imports
# ``_collapse_swings`` from pivots (its conceptual home, shared with measure_equilibrium
# below), so there is no metrics <-> box_events cycle.
from engine_alpha.structure.box_events import (  # noqa: F401  (re-export for import compatibility)
    _DETECT,
    _box_events_with_meta,
    _deepest_valley_bar,
    assemble_box_narrative,
    measure_resistance_events,
    measure_support_tests,
    read_box_events,
    read_box_staircase,
)


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
# Shared base-window swing skeleton
# ---------------------------------------------------------------------------

def base_swing_skeleton(base_df, order=None):
    """The calibrated swing skeleton for a base window — ``(peaks, valleys,
    zigzag)``, or ``None`` when the window is too short to pivot.

    ``measure_contractions`` and ``measure_support_slope`` read the SAME
    (window, order) skeleton; a caller invoking both computes it once here and
    hands it to each via their ``skeleton`` argument instead of restating the
    election twice. Lives in THIS module so ``tools/substrate_ab.py``'s
    per-module ``_find_pivots`` patching keeps its exact granularity."""
    highs = base_df["High"].values
    lows = base_df["Low"].values
    n = len(highs)
    if order is None:
        order = _pivot_order(n)
    if n < 2 * order + 1:
        return None
    return _swing_skeleton(highs, lows, order, _find_pivots)


# ---------------------------------------------------------------------------
# VCP progressive-contraction footprint
# ---------------------------------------------------------------------------

def _non_rising_fraction(seq):
    """Share of consecutive steps that do not RISE (5% tolerance so a tiny
    uptick isn't punished). Precondition: ``len(seq) >= 2`` — callers own their
    short-sequence branches. Shared by the volume drying-up read and the depth
    progressive-tightening read below (one tolerance, one expression)."""
    non_rising = sum(1 for i in range(1, len(seq)) if seq[i] <= seq[i - 1] * 1.05)
    return non_rising / (len(seq) - 1)


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
    # (tolerance shared with the depth progressive-tightening read below).
    progressive = _non_rising_fraction(vols)
    # Final-is-lightest — where the final contraction's volume sits between the
    # lightest and heaviest contraction (1.0 = it IS the lightest, 0.0 = heaviest).
    vmax, vmin = max(vols), min(vols)
    final_lightest = (vmax - vols[-1]) / (vmax - vmin) if vmax > vmin else 0.5
    return round(0.5 * progressive + 0.5 * final_lightest, 4)


def measure_contractions(base_df, order=None, skeleton=None):
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
        order = _pivot_order(n)
    if n < 2 * order + 1:
        return empty

    if skeleton is None:
        skeleton = _swing_skeleton(highs, lows, order, _find_pivots)
    peaks, valleys, zigzag = skeleton
    if not peaks or not valleys:
        return empty
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
        progressive = _non_rising_fraction(depths)
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

def measure_support_slope(base_df, atr_val, order=None, skeleton=None):
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
        order = _pivot_order(n)
    if n < 2 * order + 1:
        return empty

    if skeleton is None:
        skeleton = _swing_skeleton(highs, lows, order, _find_pivots)
    peaks, valleys, zigzag = skeleton
    if not peaks or not valleys:
        return empty

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

def _rail_touch_thirds(highs, lows, R, S, atr_val):
    """Rail-touch masks (|price − rail| within TOUCH_TOLERANCE_ATR × ATR) plus
    how many time-thirds each rail's touches span — THE touch predicate, shared
    by the touch-volume read, the equilibrium read, and the election-side close
    residence. Deliberately guard-free: callers own ATR/window validity, and the
    unguarded sites rely on NaN comparisons routing to False."""
    tb = settings.TOUCH_TOLERANCE_ATR * atr_val
    r_mask = np.abs(highs - R) <= tb
    s_mask = np.abs(lows - S) <= tb
    thirds = np.array_split(np.arange(len(highs)), 3)
    r_touch_thirds = sum(1 for t in thirds if len(t) and r_mask[t].any())
    s_touch_thirds = sum(1 for t in thirds if len(t) and s_mask[t].any())
    return r_mask, s_mask, r_touch_thirds, s_touch_thirds


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
    r_touch_mask, s_touch_mask, _, _ = _rail_touch_thirds(
        base_df['High'].values.astype(float),
        base_df['Low'].values.astype(float),
        res_avg, sup_avg, atr_val,
    )
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

def measure_gate_margins(base_df, R, S, atr_val):
    """The elected box re-measured through the ACTUAL worked-equilibrium
    gates' own statistics — boundary respect (buffered band, wicks count) and
    the close-residence dwell the dead-space gate judges — so the archive can
    see how close a fired box lived to each calibrated floor/cap. The dwell
    twins in ``measure_dwell_balance`` are range-occupancy (a bar's [Low, High]
    intersecting a third); the GATE reads close residence, and margin
    telemetry against a gate must measure the gate's own statistic.

    One implementation, re-reported (EC-3): both numbers come from the same
    ``box_primitives`` helpers the election gate calls. Measure-only — never
    gates, never penalizes; degenerate windows return None values.

    Returns dict: respect_frac, close_lower_dwell, close_mid_dwell,
    close_upper_dwell (all nullable floats).
    """
    empty = {"respect_frac": None, "close_lower_dwell": None,
             "close_mid_dwell": None, "close_upper_dwell": None}
    if (base_df is None or len(base_df) == 0 or R is None or S is None
            or R <= S or atr_val is None or atr_val <= 0
            or not np.isfinite(atr_val)):
        return empty
    from engine_alpha.structure.box_primitives import (  # noqa: PLC0415 — sibling, lazy vs cycles
        _is_boundary_respected,
        _measure_close_residence,
    )
    _, _, _, _, respect_share = _is_boundary_respected(
        base_df["High"].to_numpy(dtype=float),
        base_df["Low"].to_numpy(dtype=float), R, S, atr_val)
    eq = _measure_close_residence(base_df, R, S, atr_val)
    return {
        "respect_frac": respect_share,
        "close_lower_dwell": float(eq["lower_dwell"]),
        "close_mid_dwell": float(eq["mid_dwell"]),
        "close_upper_dwell": float(eq["upper_dwell"]),
    }


def measure_dwell_balance(base_df, R, S, atr_val):
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
    ``box_primitives._validate_base_quality`` and the Scoring Engine decide what
    the numbers are worth.

    Returns dict (safe defaults on a degenerate window so it reads as invalid):
        r_touches, s_touches            touches within TOUCH_TOLERANCE_ATR of each rail
        r_touch_thirds, s_touch_thirds  of 3 equal time-thirds, how many contain a touch
                                        (constant contact vs. clustered at the start)
        lower_dwell, mid_dwell, upper_dwell
                                        fraction of bars whose [Low, High] range intersects
                                        the lower / middle / upper third of the box; the two
                                        halves being worked is what rules out dead space
        coverage                        fraction of EQ_COVERAGE_BINS box-height bins holding
                                        >= EQ_COVERAGE_MIN_FRAC of bars (starved-band detector)
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
    n = len(highs)

    r_mask, s_mask, r_touch_thirds, s_touch_thirds = _rail_touch_thirds(
        highs, lows, R, S, atr_val)

    # Range occupancy: a bar works a third/bin if its full [Low, High] range
    # intersects it. Closes are a residence concept; Phase-B rail work is a
    # High/Low geometry concept.
    low_pos = np.clip((lows - S) / box, 0.0, 1.0)
    high_pos = np.clip((highs - S) / box, 0.0, 1.0)
    lo = np.minimum(low_pos, high_pos)
    hi = np.maximum(low_pos, high_pos)
    lower_dwell = float(np.mean((hi >= 0.0) & (lo <= 1.0 / 3.0)))
    mid_dwell = float(np.mean((hi >= 1.0 / 3.0) & (lo <= 2.0 / 3.0)))
    upper_dwell = float(np.mean((hi >= 2.0 / 3.0) & (lo <= 1.0)))

    nb = settings.EQ_COVERAGE_BINS
    counts = np.zeros(nb, dtype=int)
    start_bins = np.clip((lo * nb).astype(int), 0, nb - 1)
    end_bins = np.clip(np.ceil(hi * nb).astype(int) - 1, 0, nb - 1)
    for start_bin, end_bin in zip(start_bins, end_bins):
        counts[start_bin:end_bin + 1] += 1
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


# ---------------------------------------------------------------------------
# Limb traversal — do the swing LIMBS travel rail-to-rail, or is there dead space?
# ---------------------------------------------------------------------------

def measure_equilibrium(base_df, R, S, atr_val):
    """Do the swing LIMBS travel rail-to-rail, or does price hang off one rail?

    ``measure_dwell_balance`` asks which vertical bands the bars occupy. This asks
    the complementary, swing-structural question a chart reader actually uses: do
    the up/down limbs of the chop genuinely run from Support to Resistance and
    back, or does price hang off one rail, nick the middle, and tap the far rail
    only a couple of times? Persistent dead space at a rail is the tell that R/S
    were marked too wide.

    Deliberately a REACH measure — peaks use High, valleys use Low (a swing that
    *reaches* a rail counts), unlike settled close / CoG measures. Swing
    significance is judged as a FRACTION OF BOX HEIGHT (``TRAVERSAL_NOISE_FRAC``),
    not a bar count, so the read adapts: tight boxes have short limbs, wide boxes
    long ones — which is the whole point. ``atr_val`` is accepted for contract
    symmetry with the sibling measures and to reject degenerate windows; the swing
    math itself is box-relative by design.

    Pure measurement, no gates and no points (v1). The pool-aware validity gate in
    ``box_primitives`` (v2) and the archive decide what the numbers are worth.

    Returns dict (safe defaults on a degenerate window):
        n_full_traversals  limbs spanning >= TRAVERSAL_FULL_FRAC of the box that
                           connect the low zone (<= TRAVERSAL_LOW_ZONE) to the high
                           zone (>= TRAVERSAL_HIGH_ZONE); direction-agnostic, so a
                           round-trip S->R->S counts as 2
        n_swings           significant swings left after amplitude filtering
        top_dead_space     1 - 75th-pct of peak positions: how far below R the
                           swings habitually turn (0 = peaks reach R; large = dead top)
        bottom_dead_space  25th-pct of valley positions: how far above S they turn
        rail_reaches_high  swing peaks reaching the high zone
        rail_reaches_low   swing valleys reaching the low zone
        max_swing_frac     largest single limb as a fraction of box height
    """
    empty = {
        "n_full_traversals": 0, "n_swings": 0,
        "top_dead_space": None, "bottom_dead_space": None,
        "rail_reaches_high": 0, "rail_reaches_low": 0,
        "max_swing_frac": None,
        "last_support_time_pos": None, "low_position_in_box": None,
    }
    if base_df is None or len(base_df) == 0:
        return empty
    box = R - S
    if box <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return empty

    highs = base_df["High"].values.astype(float)
    lows = base_df["Low"].values.astype(float)
    n = len(highs)

    # Sensitive (order-1) zigzag so tight-box swings aren't missed; the amplitude
    # filter below removes the resulting noise.
    peaks, valleys, zz = _swing_skeleton(highs, lows, 1, _find_pivots)
    if not peaks or not valleys:
        return empty
    if len(zz) < 3:
        return empty

    min_amp = settings.TRAVERSAL_NOISE_FRAC * box
    swings = _collapse_swings(zz, min_amp)
    if not swings:
        return empty

    # Soft endpoints: order-1 pivots exclude the first/last bar, so a leading or
    # trailing (in-progress) limb is invisible. Add each only when it forms a real
    # (>= min_amp) limb of the opposite type — different bar + opposite type means
    # no zero-width or noise limb is introduced, and alternation is preserved.
    # Done BEFORE the 2-pivot floor, so a single collapsed extreme plus its
    # leading/trailing limbs can still form a measurable swing.
    first = swings[0]
    if first[0] > 0:
        kind = 'valley' if first[1] == 'peak' else 'peak'
        price = lows[0] if kind == 'valley' else highs[0]
        if abs(price - first[2]) >= min_amp:
            swings.insert(0, (0, kind, price))
    last = swings[-1]
    if last[0] < n - 1:
        kind = 'valley' if last[1] == 'peak' else 'peak'
        price = lows[n - 1] if kind == 'valley' else highs[n - 1]
        if abs(price - last[2]) >= min_amp:
            swings.append((n - 1, kind, price))

    if len(swings) < 2:
        return empty

    # Position as a fraction of box (0 = S, 1 = R). NOT clipped for the traversal
    # / reach test — an overshoot through a rail is *more* than a reach.
    pos = [(p[2] - S) / box for p in swings]

    full = 0
    max_span = 0.0
    for i in range(len(swings) - 1):
        a, b = pos[i], pos[i + 1]
        span = abs(a - b)
        if span > max_span:
            max_span = span
        if (span >= settings.TRAVERSAL_FULL_FRAC
                and min(a, b) <= settings.TRAVERSAL_LOW_ZONE
                and max(a, b) >= settings.TRAVERSAL_HIGH_ZONE):
            full += 1

    peak_pos = [p for p, sw in zip(pos, swings) if sw[1] == "peak"]
    valley_pos = [p for p, sw in zip(pos, swings) if sw[1] == "valley"]
    rail_reaches_high = sum(1 for p in peak_pos if p >= settings.TRAVERSAL_HIGH_ZONE)
    rail_reaches_low = sum(1 for p in valley_pos if p <= settings.TRAVERSAL_LOW_ZONE)

    # Dead-space cluster: the rail-side quartile of the CLIPPED positions asks
    # "does a meaningful share of swings reach the rail?" — the median understates
    # an occasionally-tagged rail, the extreme is fooled by a lone wick.
    top_dead = (round(1.0 - float(np.quantile(np.clip(peak_pos, 0.0, 1.0), 0.75)), 4)
                if peak_pos else None)
    bottom_dead = (round(float(np.quantile(np.clip(valley_pos, 0.0, 1.0), 0.25)), 4)
                   if valley_pos else None)

    # Late-support work (descent-tail tell; shadow-only v1, no gate/points). A box
    # that touches S only early then floats up (a one-sided rising coil) reads as a
    # descent tail, not a worked range — unlike a range that re-tests S throughout.
    # last_support_time_pos = time-position (0..1) of the last support touch; low = S
    # abandoned early. low_position_in_box = box-position of the lowest Low AFTER that
    # touch (0=S, 1=R); high = a real dead band beneath the late coil.
    s_band = settings.TOUCH_TOLERANCE_ATR * atr_val
    touch_bars = np.where(lows <= S + s_band)[0]
    if len(touch_bars):
        last_support_time_pos = round(float(touch_bars[-1]) / max(1, n - 1), 4)
        after = lows[touch_bars[-1] + 1:]
        low_position_in_box = round(float((np.min(after) - S) / box), 4) if len(after) else None
    else:
        last_support_time_pos, low_position_in_box = None, None

    return {
        "n_full_traversals": int(full),
        "n_swings": int(len(swings)),
        "top_dead_space": top_dead,
        "bottom_dead_space": bottom_dead,
        "rail_reaches_high": int(rail_reaches_high),
        "rail_reaches_low": int(rail_reaches_low),
        "max_swing_frac": round(float(max_span), 4),
        "last_support_time_pos": last_support_time_pos,
        "low_position_in_box": low_position_in_box,
    }


def descent_tail_rejects(last_support_time_pos, low_position_in_box, box_width) -> bool:
    """True = the box ABANDONED its support rail EARLY into dead space — a
    mis-anchored / dead-space framing the descent-tail gate drops (CHCT, DGII).

    ``last_support_time_pos`` (time-position 0..1 of the last support touch) is
    ``<= DESCENT_TAIL_LSF_MAX`` AND ``low_position_in_box`` (box-position of the lowest
    Low after that touch) is ``>= DESCENT_TAIL_CFP_MIN`` — i.e. price left the low
    rail early and then coiled in dead space above it. Both inputs come from
    ``measure_equilibrium``; pass the ACTIVE box's fields (inner if the LPS
    re-anchored there, else parent).

    Width-aware: TIGHT boxes (``box_width <= BASE_AGE_DEADSPACE_WIDTH``) are EXEMPT
    — their dead band is small in absolute terms so the tell is a false positive
    (saves the EQIX winner). No-op unless ``settings.DESCENT_TAIL_GATE_ENABLED``.
    """
    if not settings.DESCENT_TAIL_GATE_ENABLED:
        return False
    if box_width is None or box_width <= settings.BASE_AGE_DEADSPACE_WIDTH:
        return False
    if last_support_time_pos is None or low_position_in_box is None:
        return False
    return (last_support_time_pos <= settings.DESCENT_TAIL_LSF_MAX
            and low_position_in_box >= settings.DESCENT_TAIL_CFP_MIN)
