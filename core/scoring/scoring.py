"""
The Scoring Engine — "what makes a stock pop".

This is the opinion layer. The Structure Engine hands it a pile of *measured
facts* about a setup (how tight the box is, how many touches, how the volume
dried up, how far below the 52-week high, how broad the market tape is, the
VCP contraction footprint, ...). This module turns those facts into points.

Every knob lives in ``config/settings.py`` (the SCORE_* and tier constants),
so tuning the strategy means editing numbers there — never touching the
measurement code. ``score_setup`` returns the total plus each sub-score so the
archive can later tell us which ingredients actually predicted winners.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from config import settings


def _clamp(value: float, cap: float) -> float:
    """Clamp ``value`` into ``[0, cap]``. Used consistently across the scorer."""
    return max(0.0, min(cap, value))


def score_setup(box_width: float, r_touches: int, s_touches: int,
                res_avg: float, sup_avg: float, base_df: pd.DataFrame,
                atr_ratio: float, tightness_ratio: float,
                vol_contraction: float, base_len: int,
                yearly_return: float, excess_return: float = 0.0,
                dist_52w_high_pct: Optional[float] = None,
                breadth_pct: Optional[float] = None,
                contraction_quality: float = 0.0,
                support_quality: float = 0.0,
                adr_quality: float = 0.0,
                traversal_density: float = 0.0,
                max_swing_frac: float = 1.0,
                dwell_asymmetry: float = 0.0) -> dict:
    """
    Calculate a composite quality score from structural metrics.

    Returns a dict with the total score and each sub-score component,
    enabling downstream regression analysis in the setup archive.

    excess_return: stock 6m return − SPY 6m return. Drives the soft RS bonus.
    dist_52w_high_pct: negative number (e.g. -0.07 = 7% below 52w high) used
    to award the 52w-high proximity bonus.
    breadth_pct: % of universe with Close > SMA_50 on scan_date. Same value
    across every setup in a run; rewards setups forming in a broad tape.
    traversal_density / max_swing_frac / dwell_asymmetry: box-relative swing facts
    (measure_traversal + measure_equilibrium) grading genuine two-sided rail-working
    vs dead space; drives the traversal-quality term that replaced oscillation.
    """
    touches = r_touches + s_touches

    # Box tightness — flat linear scale, removing exponential penalty for wider boxes
    box_tightness_ratio = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
    s_box = _clamp(box_tightness_ratio * settings.SCORE_BOX_TIGHTNESS,
                    settings.SCORE_BOX_TIGHTNESS)

    # Touch density
    base_touch_max = settings.SCORE_TOUCH_DENSITY - settings.TOUCH_BONUS_POINTS
    touch_score = _clamp(touches * 2.0, base_touch_max)
    if (r_touches >= settings.TOUCH_BONUS_INDIVIDUAL and s_touches >= settings.TOUCH_BONUS_INDIVIDUAL) \
       or (touches >= settings.TOUCH_BONUS_TOTAL):
        touch_score += settings.TOUCH_BONUS_POINTS
    s_touch = touch_score

    # Traversal quality — does the chop genuinely WORK BOTH RAILS, or hang off one?
    # Graded reward on rail-to-rail density (true round-trips per significant swing),
    # docked for one-sided dwell (lower-vs-upper-third residence asymmetry) and a
    # single oversized limb (max_swing_frac > 1 = a one-off spike defining a rail).
    # Replaces the retired, rail-blind oscillation term. The dock can only erode the
    # reward toward 0 — it is never negative, so a dead-space box simply earns
    # nothing here rather than being penalized below its other merits.
    density_reward = _clamp(
        (traversal_density / settings.TRAVERSAL_QUALITY_DENSITY_FULL) * settings.SCORE_TRAVERSAL_QUALITY,
        settings.SCORE_TRAVERSAL_QUALITY,
    )
    dead_space = max(0.0, max_swing_frac - 1.0) + dwell_asymmetry
    dead_space_penalty = _clamp(dead_space * settings.TRAVERSAL_QUALITY_DWELL_PENALTY,
                                settings.TRAVERSAL_QUALITY_DWELL_PENALTY)
    s_traversal = max(0.0, density_reward - dead_space_penalty)

    # Oscillation retired (rail-blind). Kept at 0 for payload/archive key continuity.
    s_osc = 0.0

    # ATR squeeze
    s_atr = _clamp((1.0 - atr_ratio) * settings.SCORE_ATR_SQUEEZE,
                    settings.SCORE_ATR_SQUEEZE)

    # LPS candle tightness
    s_lps = _clamp((1 - tightness_ratio) * (settings.SCORE_LPS_TIGHTNESS * 2),
                    settings.SCORE_LPS_TIGHTNESS)

    # Volume contraction
    s_vol = _clamp(vol_contraction * (settings.SCORE_VOL_CONTRACTION * 2),
                    settings.SCORE_VOL_CONTRACTION)

    # Base age — Wyckoff "cause" reward. Sqrt-scaled so very long bases still
    # earn incremental credit past the saturation point without dominating the
    # total: a 30d base earns ~50% of cap, a 60d base ~71%, a 120d base 100%.
    s_age = 0.0
    if base_len > settings.MIN_BASE_DAYS:
        age_factor = math.sqrt(base_len / settings.BASE_AGE_CAP_DAYS)
        s_age = _clamp(age_factor * settings.SCORE_BASE_AGE, settings.SCORE_BASE_AGE)
        # Dead-space dock: "cause" only counts if a long base actually worked
        # rail-to-rail. A WIDE base with low traversal density is dead space, not
        # cause, so scale its age credit by the density shortfall. Tight boxes are
        # exempt (low density there is a small-box / spring artifact, e.g. PRA) —
        # so only gate once box_width clears BASE_AGE_DEADSPACE_WIDTH.
        if (box_width > settings.BASE_AGE_DEADSPACE_WIDTH
                and traversal_density < settings.TRAVERSAL_QUALITY_DENSITY_FULL):
            s_age *= _clamp(traversal_density / settings.TRAVERSAL_QUALITY_DENSITY_FULL, 1.0)

    # Strong-uptrend bonus — re-accumulation in an established uptrend
    # breaks out more reliably than the same structure on a flat YoY chart.
    # Linear ramp from MIN_STRONG_YEARLY_RETURN to MAX_STRONG_YEARLY_RETURN.
    if yearly_return >= settings.MIN_STRONG_YEARLY_RETURN:
        span = settings.MAX_STRONG_YEARLY_RETURN - settings.MIN_STRONG_YEARLY_RETURN
        progress = min(1.0, (yearly_return - settings.MIN_STRONG_YEARLY_RETURN) / span)
        s_uptrend = progress * settings.SCORE_UPTREND_BONUS
    else:
        s_uptrend = 0.0

    # Soft RS bonus — additive points for outperforming SPY over 6 months.
    # No filter, just leadership reward; saturates at RS_MAX_EXCESS_RETURN.
    if excess_return > 0:
        rs_progress = min(1.0, excess_return / settings.RS_MAX_EXCESS_RETURN)
        s_rs = rs_progress * settings.SCORE_RS_BONUS
    else:
        s_rs = 0.0

    # 52-week high proximity — bases near recent highs hold breakouts more
    # reliably. Linear ramp; null distance contributes zero (e.g. tickers
    # without sufficient history).
    s_high = 0.0
    if dist_52w_high_pct is not None:
        full = settings.HIGH_PROXIMITY_FULL_PCT
        zero = settings.HIGH_PROXIMITY_ZERO_PCT
        if dist_52w_high_pct >= full:
            s_high = float(settings.SCORE_52W_HIGH_PROXIMITY)
        elif dist_52w_high_pct <= zero:
            s_high = 0.0
        else:
            progress = (dist_52w_high_pct - zero) / (full - zero)
            s_high = progress * settings.SCORE_52W_HIGH_PROXIMITY

    # Market-breadth bonus — linear ramp on % of universe above SMA_50.
    # Same value for every setup in a run; rewards a friendly tape regardless
    # of which ticker we're scoring.
    s_breadth = 0.0
    if breadth_pct is not None:
        b_full = settings.BREADTH_FULL_PCT
        b_zero = settings.BREADTH_ZERO_PCT
        if breadth_pct >= b_full:
            s_breadth = float(settings.SCORE_BREADTH_BONUS)
        elif breadth_pct <= b_zero:
            s_breadth = 0.0
        else:
            b_progress = (breadth_pct - b_zero) / (b_full - b_zero)
            s_breadth = b_progress * settings.SCORE_BREADTH_BONUS

    # VCP progressive-contraction footprint — the *process* of tightening
    # (count + progressive-shrink + tight final contraction), as opposed to
    # box_tightness/atr_squeeze which only see static tightness. quality is
    # already a [0,1] composite from measure_contractions().
    s_contraction = _clamp(contraction_quality * settings.SCORE_CONTRACTION,
                           settings.SCORE_CONTRACTION)

    # Ascending support / higher lows — rewards a base whose swing lows are
    # stair-stepping up (rising demand). Bonus-only; flat/sagging floor = 0.
    s_ascending = _clamp(support_quality * settings.SCORE_ASCENDING_SUPPORT,
                         settings.SCORE_ASCENDING_SUPPORT)

    # ADR% absolute volatility — rewards stocks that move enough each day to
    # be worth trading. Bonus-only; quiet names simply earn zero here.
    s_adr = _clamp(adr_quality * settings.SCORE_ADR, settings.SCORE_ADR)

    total = round(s_box + s_touch + s_traversal + s_atr + s_lps + s_vol + s_age
                  + s_uptrend + s_rs + s_high + s_breadth + s_contraction
                  + s_ascending + s_adr, 1)

    return {
        'total': total,
        'box_tightness': round(s_box, 2),
        'touch_density': round(s_touch, 2),
        'oscillation': round(s_osc, 2),
        'traversal_quality': round(s_traversal, 2),
        'atr_squeeze': round(s_atr, 2),
        'lps_tightness': round(s_lps, 2),
        'vol_contraction': round(s_vol, 2),
        'base_age': round(s_age, 2),
        'uptrend_bonus': round(s_uptrend, 2),
        'rs_bonus': round(s_rs, 2),
        'high_proximity': round(s_high, 2),
        'breadth_bonus': round(s_breadth, 2),
        'contraction': round(s_contraction, 2),
        'ascending_support': round(s_ascending, 2),
        'adr': round(s_adr, 2),
    }


def calculate_tier(score: float, box_width: Optional[float] = None) -> str:
    """Map a numeric score to a letter tier grade.

    ``box_width`` (optional) applies the S-tier width cap: a base wider than
    ``S_MAX_BOX_WIDTH`` cannot be S no matter how high it scores — a wide range,
    however long or well-touched, is not an elite setup. It still earns A on
    merit. Callers that don't have a width on hand omit it (no cap applied).
    """
    if score >= settings.TIER_S:
        tier = 'S'
    elif score >= settings.TIER_A:
        tier = 'A'
    elif score >= settings.TIER_B:
        tier = 'B'
    elif score >= settings.TIER_C:
        tier = 'C'
    else:
        tier = 'D'

    if tier == 'S' and box_width is not None and box_width > settings.S_MAX_BOX_WIDTH:
        tier = 'A'
    return tier
