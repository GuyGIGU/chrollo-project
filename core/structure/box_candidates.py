"""Zigzag candidate selection for consolidation boxes."""
from __future__ import annotations

import numpy as np

from config import settings
from core.structure.pivots import _build_zigzag, _find_pivots


INNER_MIN_DAYS = 15
EMPTY_BOX = (0, 0, 0, 1.0, 0, 0, 0, 0, 0)


def _is_boundary_respected(highs, lows, R_val, S_val, atr_val):
    """
    Check if price action respects R/S boundaries using ATR-buffered zones.

    Uses the full daily range (highs vs R+buffer, lows vs S-buffer). Wicks
    that pierce the buffered zone count as breaches, matching the engine's
    "bars not candles" rule.

    Returns:
        (respected, r_broken, s_broken, total_outside_days)
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = len(highs)
    if n == 0:
        return False, False, False, 0

    buffer = settings.BOUNDARY_ATR_BUFFER * atr_val
    r_ceiling = R_val + buffer
    s_floor = S_val - buffer

    above_r = highs > r_ceiling
    below_s = lows < s_floor
    outside = above_r | below_s
    total_outside = int(outside.sum())

    def _max_consecutive(mask):
        """Max run length of True values in a boolean array."""
        if not mask.any():
            return 0
        d = np.diff(np.concatenate(([False], mask, [False])).astype(int))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        return int((ends - starts).max()) if len(starts) > 0 else 0

    max_consec = _max_consecutive(outside)
    r_consec_max = _max_consecutive(above_r)
    s_consec_max = _max_consecutive(below_s)

    respect_pct = 1.0 - (total_outside / n)
    max_outside = settings.MAX_CONSECUTIVE_OUTSIDE_DAYS
    respected = (max_consec <= max_outside and
                 respect_pct >= settings.MIN_BOUNDARY_RESPECT_PCT)
    r_broken = r_consec_max > max_outside
    s_broken = s_consec_max > max_outside

    return respected, r_broken, s_broken, total_outside


def _validate_base_quality(eq_df, R_val, S_val, atr_val):
    """
    Validate a candidate R/S pair using structural quality checks.

    Checks:
      - Box width within limits
      - Crash filter: no catastrophic wick below support
      - Touch density: at least two touches on each boundary
      - Midline oscillation: enough committed crosses, ATR-buffered

    Returns:
        (r_touches, s_touches, crosses, is_valid)
    """
    box_width = (R_val - S_val) / S_val
    if box_width > settings.MAX_BOX_WIDTH or box_width <= 0:
        return 0, 0, 0, False

    if eq_df['Low'].min() < S_val * settings.CRASH_FILTER_MULT:
        return 0, 0, 0, False

    touch_band = settings.TOUCH_TOLERANCE_ATR * atr_val
    r_touches = int(((eq_df['High'] - R_val).abs() <= touch_band).sum())
    s_touches = int(((eq_df['Low'] - S_val).abs() <= touch_band).sum())

    if r_touches < 2 or s_touches < 2:
        return r_touches, s_touches, 0, False

    midline = (R_val + S_val) / 2
    buffer = settings.MIDLINE_ATR_BUFFER * atr_val
    close_vals = eq_df['Close'].values
    crosses = 0
    if len(close_vals) > 1:
        above = close_vals > midline
        distances = np.abs(close_vals - midline)
        prev_above = above[0]
        committed = True
        for i in range(1, len(close_vals)):
            if above[i] != prev_above:
                if committed:
                    crosses += 1
                    prev_above = above[i]
                    committed = False
            else:
                if distances[i] >= buffer:
                    committed = True

    min_crosses_needed = max(settings.MIN_MIDLINE_CROSSES, len(eq_df) // 15)
    if crosses < min_crosses_needed:
        return r_touches, s_touches, crosses, False

    return r_touches, s_touches, crosses, True


def _candidate_atr(eq_df, eq_highs, eq_lows, atr_override=None):
    """Return the ATR reference used for candidate boundary and quality checks."""
    if atr_override is not None and atr_override > 0 and not np.isnan(atr_override):
        return float(atr_override)

    win = settings.PHASE_B_ATR_WINDOW
    if 'ATR_10' in eq_df.columns:
        recent_atr = eq_df['ATR_10'].values[-win:] if len(eq_df) >= win else eq_df['ATR_10'].values
        atr_val = float(np.nanmedian(recent_atr))
    else:
        atr_val = (float(np.median(eq_highs[-win:] - eq_lows[-win:]))
                   if len(eq_df) >= win else float(np.median(eq_highs - eq_lows)))

    if atr_val <= 0 or np.isnan(atr_val):
        atr_val = float(np.median(eq_highs - eq_lows))
    return atr_val


def _pivot_order(n_bars):
    if n_bars >= settings.PIVOT_ORDER_THRESHOLD:
        return settings.PIVOT_ORDER_LONG
    return settings.PIVOT_ORDER_SHORT


def _score_candidate(box_width, r_touches, s_touches, crosses):
    tightness_score = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
    touch_score = min(1.0, (r_touches + s_touches) / 10.0)
    midline_score = min(1.0, crosses / 8.0)
    return 0.4 * tightness_score + 0.4 * touch_score + 0.2 * midline_score


def _collect_zigzag_candidates(eq_df, base_length, atr_val, min_candidate_days=0):
    """Build valid R/S candidates from consecutive zigzag limbs."""
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    peaks_idx, valleys_idx = _find_pivots(eq_highs, eq_lows, _pivot_order(len(eq_df)))
    if not peaks_idx or not valleys_idx:
        return []

    zigzag = _build_zigzag(peaks_idx, valleys_idx, eq_highs, eq_lows)
    if len(zigzag) < 2:
        return []

    valid_candidates = []
    for i in range(len(zigzag) - 1):
        zi, zj = zigzag[i], zigzag[i + 1]
        if zi[1] == 'peak' and zj[1] == 'valley':
            R_val, S_val = zi[2], zj[2]
            r_anchor_bar, s_anchor_bar = zi[0], zj[0]
        elif zi[1] == 'valley' and zj[1] == 'peak':
            R_val, S_val = zj[2], zi[2]
            r_anchor_bar, s_anchor_bar = zj[0], zi[0]
        else:
            continue
        if R_val <= S_val:
            continue

        box_width = (R_val - S_val) / S_val
        if box_width > settings.MAX_BOX_WIDTH:
            continue

        cand_start = min(r_anchor_bar, s_anchor_bar)
        cand_eq_df = eq_df.iloc[cand_start:]
        if len(cand_eq_df) < min_candidate_days:
            continue

        respected, _r_broken, _s_broken, total_outside = _is_boundary_respected(
            eq_highs[cand_start:], eq_lows[cand_start:], R_val, S_val, atr_val,
        )
        if not respected:
            continue

        r_touches, s_touches, crosses, is_valid = _validate_base_quality(
            cand_eq_df, R_val, S_val, atr_val,
        )
        if not is_valid:
            continue

        combined = _score_candidate(box_width, r_touches, s_touches, crosses)
        valid_candidates.append((
            combined, R_val, S_val, box_width,
            r_touches, s_touches, total_outside,
            r_anchor_bar, s_anchor_bar, cand_start,
        ))

    return valid_candidates


def _select_phase_b_candidate(valid_candidates, select):
    """Pick one candidate framing from the valid gate-passing set."""
    if select == "earliest":
        best_combined = max(c[0] for c in valid_candidates)
        floor = settings.PHASE_B_REACH_QUALITY_FLOOR * best_combined
        pool = [c for c in valid_candidates if c[0] >= floor]
        return min(pool, key=lambda x: (x[9], -x[0]))
    return max(valid_candidates, key=lambda x: x[0])


def _debug_candidates(valid_candidates, base_length):
    return [
        {
            "cand_start": int(c[9]),
            "base_len": int(base_length - c[9]),
            "box_width": round(float(c[3]), 4),
            "r_touches": int(c[4]),
            "s_touches": int(c[5]),
            "combined": round(float(c[0]), 4),
            "R": round(float(c[1]), 4),
            "S": round(float(c[2]), 4),
        }
        for c in sorted(valid_candidates, key=lambda x: x[9])
    ]


def _rebase_selected_candidate(candidate, base_length):
    _, best_R, best_S, best_bw, best_rt, best_st, best_breach, \
        best_r_bar, best_s_bar, best_cand_start = candidate

    effective_base_length = base_length - best_cand_start
    new_r_anchor = best_r_bar - best_cand_start
    new_s_anchor = best_s_bar - best_cand_start
    return (effective_base_length, best_R, best_S, best_bw, best_rt, best_st,
            best_breach, new_r_anchor, new_s_anchor)


def _phase_b_zigzag(eval_df, start_idx, base_length, atr_override=None,
                    select="earliest"):
    """Shared Phase B: zigzag S/R anchoring over eval_df.iloc[start_idx:]."""
    eq_df = eval_df.iloc[start_idx:]
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    atr_val = _candidate_atr(eq_df, eq_highs, eq_lows, atr_override)
    valid_candidates = _collect_zigzag_candidates(eq_df, base_length, atr_val)

    if not valid_candidates:
        return [] if select == "debug" else EMPTY_BOX

    if select == "debug":
        return _debug_candidates(valid_candidates, base_length)

    selected = _select_phase_b_candidate(valid_candidates, select)
    return _rebase_selected_candidate(selected, base_length)


def _inner_zigzag(eval_df, start_idx, base_length, atr_override=None):
    """Inner-stage zigzag detector scored over each candidate's own bar range."""
    eq_df = eval_df.iloc[start_idx:]
    if len(eq_df) < settings.MIN_BASE_DAYS:
        return EMPTY_BOX

    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    atr_val = _candidate_atr(eq_df, eq_highs, eq_lows, atr_override)
    valid_candidates = _collect_zigzag_candidates(
        eq_df, base_length, atr_val, min_candidate_days=INNER_MIN_DAYS,
    )
    if not valid_candidates:
        return EMPTY_BOX

    selected = max(valid_candidates, key=lambda x: x[0])
    return _rebase_selected_candidate(selected, base_length)
