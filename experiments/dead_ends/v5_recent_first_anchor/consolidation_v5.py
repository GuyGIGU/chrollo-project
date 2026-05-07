"""DEAD END — v5 recent-first anchor preference (failed experiment).

==============================================================================
STATUS: NEGATIVE RESULT — DO NOT IMPORT FROM LIVE PATH
==============================================================================

Hypothesis (from v4 docstring, "NOT YET HANDLED" section):
    The watchlist v4 misses NBR / GXO / VLO / SHEL fail because v3's
    oldest-first anchor preference picks an old quiet zone instead of the
    structurally relevant recent chop. A recent-first iteration over the
    `anchors` list should fix all four.

Test:
    Cloned v3 with the iteration order flipped (drop `reversed()` on the
    anchors loop), wrapped it in the same hierarchical inner-box probe as
    v4, and re-ran the watchlist harness with identical LPS-scaling rules.

Result: 31/44 hits (70.5%) — IDENTICAL to v4 baseline. No tickers recovered,
no tickers lost. Same 13 misses: SILC, SKYT, KEYS, BRZU, RRBI, NBR, NE, SNDX,
VLO, SHEL, GXO, ST, TRS. See watchlist_backtest_v5.csv in this folder for
the full per-ticker output.

Why the hypothesis was wrong:
    v5 IS picking different (more recent) outer anchors for GXO / VLO / SHEL
    — the mechanism works as designed. But the downstream LPS detector
    rejects at the same gates regardless of which outer is chosen:

      * GXO: v3 outer base=128 (Aug 4), v5 outer base=80 (Oct 10) — both
             fail LPS with zone_gate=12, spread_quantile=11
      * VLO: v3 outer base=90, v5 outer base=59 — same R/S anchors
             (190.833 / 159.992), same LPS failure (zone_gate=24)
      * SHEL: v3 outer base=160 (deep), v5 outer base=54 (recent) — both
              fail LPS at zone_gate=24
      * NBR: both v3 and v5 return EMPTY at offset -7; both find the same
             non-target base at other offsets, same LPS failure

    Conclusion: anchor preference is not the root cause. The recent action
    itself doesn't satisfy the LPS detector — the price doesn't sit in the
    breakout-retest zone with sufficient volume contraction. These four are
    LPS-detector limits, same bucket as ST / RRBI / SNDX / TRS.

Why this file is preserved (not deleted):
    Future-us may notice the same four misses and re-form the same
    "anchor mis-detection" hypothesis. This file is the proof that the
    hypothesis was tested and proved false. Re-test only if the LPS
    detector itself is rewritten — anchor preference alone won't help.

Module is self-contained — imports only stable helpers from core.consolidation
(_build_zigzag, _find_pivots, _is_boundary_respected, _validate_base_quality,
_phase_b_zigzag). The recent-first detector is inlined so this file works
even after find_consolidation_v5 is removed from core/consolidation.py.
"""
from __future__ import annotations

import numpy as np

from config import settings
from core.consolidation import (
    _build_zigzag,
    _find_pivots,
    _is_boundary_respected,
    _phase_b_zigzag,
    _validate_base_quality,
)


_INNER_TIGHTNESS_RATIO = 0.75
_INNER_SEARCH_FRACTION = 0.5
_INNER_MIN_DAYS = 15


def find_consolidation_v5(df, min_days=None):
    """Recent-first anchor preference. v3 clone with iteration order flipped.

    Identical to find_consolidation_v3 in every gate, scoring rule, and
    return shape. Only difference: when multiple qualifying anchors exist,
    v3 prefers the EARLIEST valid one (oldest-first); v5 prefers the MOST
    RECENT valid one. The loop body is unchanged.
    """
    if min_days is None:
        min_days = settings.MIN_BASE_DAYS
    EMPTY = (0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0, 0)

    eval_df = df.iloc[:-5] if len(df) > 5 else df
    if len(eval_df) < min_days + 15:
        return EMPTY

    closes = eval_df['Close'].values
    highs = eval_df['High'].values
    lows = eval_df['Low'].values

    sma200 = eval_df['Close'].rolling(200).mean().values
    end = len(eval_df) - 1

    if 'ATR_10' in eval_df.columns:
        atr_snapshot = float(eval_df['ATR_10'].iloc[-1])
        if np.isnan(atr_snapshot) or atr_snapshot <= 0:
            atr_snapshot = None
    else:
        atr_snapshot = None

    if np.isnan(sma200[end]) or closes[end] <= sma200[end]:
        return EMPTY

    min_move = settings.TREND_MIN_GAIN_PCT
    min_move_bars = settings.TREND_MIN_MOVE_BARS
    prior_lookback = settings.TREND_PRIOR_LOOKBACK
    local_peak_bars = settings.LOCAL_PEAK_BARS

    scan_lo = min_move_bars + 5
    scan_hi = end - min_days
    if scan_hi <= scan_lo:
        return EMPTY

    anchors: list[tuple[str, int, int]] = []

    for i in range(scan_hi, scan_lo - 1, -1):
        prior_start = max(0, i - prior_lookback)
        local_start = max(0, i - local_peak_bars)

        if highs[i] >= np.max(highs[local_start:i + 1]):
            prior_lows = lows[prior_start:i]
            if len(prior_lows) >= min_move_bars:
                trough_k = int(np.argmin(prior_lows))
                trough_low = float(prior_lows[trough_k])
                trough_bar = prior_start + trough_k
                if trough_low > 0 \
                        and highs[i] / trough_low - 1.0 >= min_move \
                        and (i - trough_bar) >= min_move_bars:
                    ar_thr = highs[i] * (1.0 - settings.AR_MIN_DROP_PCT)
                    ar_end = min(len(eval_df), i + settings.AR_MAX_BARS + 1)
                    ar_completed = False
                    ar_low_bar = -1
                    ar_low_val = np.inf
                    for j in range(i + 1, ar_end):
                        if closes[j] <= ar_thr:
                            ar_completed = True
                        if lows[j] < ar_low_val:
                            ar_low_val = lows[j]
                            ar_low_bar = j
                    if ar_completed and ar_low_bar != -1 \
                            and (len(eval_df) - ar_low_bar) >= min_days:
                        anchors.append(('BC', i, ar_low_bar))

        if lows[i] <= np.min(lows[local_start:i + 1]):
            prior_highs = highs[prior_start:i]
            if len(prior_highs) >= min_move_bars:
                peak_k = int(np.argmax(prior_highs))
                peak_high = float(prior_highs[peak_k])
                peak_bar = prior_start + peak_k
                if peak_high > 0 \
                        and 1.0 - lows[i] / peak_high >= min_move \
                        and (i - peak_bar) >= min_move_bars:
                    bounce_thr = lows[i] * (1.0 + settings.AR_MIN_DROP_PCT)
                    bounce_end = min(len(eval_df), i + settings.AR_MAX_BARS + 1)
                    bounce_completed = False
                    bounce_high_bar = -1
                    bounce_high_val = -np.inf
                    for j in range(i + 1, bounce_end):
                        if closes[j] >= bounce_thr:
                            bounce_completed = True
                        if highs[j] > bounce_high_val:
                            bounce_high_val = highs[j]
                            bounce_high_bar = j
                    if bounce_completed and bounce_high_bar != -1 \
                            and (len(eval_df) - bounce_high_bar) >= min_days:
                        anchors.append(('SC', i, bounce_high_bar))

    if not anchors:
        return EMPTY

    # v5 difference: iterate `anchors` directly (most-recent-first) instead
    # of reversed (oldest-first). First valid Phase B wins, so the most
    # recent qualifying climax / SC is preferred.
    for _atype, _abar, phase_b_start in anchors:
        base_length = len(df) - phase_b_start
        result = _phase_b_zigzag(
            eval_df, phase_b_start, base_length, atr_override=atr_snapshot,
        )
        if result[0] != 0:
            effective_phase_b_start = len(df) - result[0]
            return result + (_abar, effective_phase_b_start)

    return EMPTY


def find_consolidation_v5_hier(df, min_days=None):
    """Hierarchical detection with recent-first outer anchoring.

    Returns same 11-tuple shape as find_consolidation_v3 / v4.
    """
    if min_days is None:
        min_days = settings.MIN_BASE_DAYS

    outer = find_consolidation_v5(df, min_days=min_days)
    if outer[0] == 0:
        return outer

    (outer_base_len, R_outer, S_outer, bw_outer,
     _rt, _st, _br, _ra, _sa, bc_anchor, outer_phase_b_start) = outer

    inner_phase_b_start = outer_phase_b_start + int(outer_base_len * _INNER_SEARCH_FRACTION)
    if (len(df) - inner_phase_b_start) < _INNER_MIN_DAYS:
        return outer

    eval_df = df.iloc[:-5] if len(df) > 5 else df
    if inner_phase_b_start >= len(eval_df):
        return outer
    inner_base_length = len(df) - inner_phase_b_start

    inner_result = _inner_zigzag(
        eval_df, inner_phase_b_start, inner_base_length,
    )
    if inner_result[0] == 0:
        return outer

    bw_inner = inner_result[3]
    if bw_inner >= bw_outer * _INNER_TIGHTNESS_RATIO:
        return outer

    return inner_result + (bc_anchor, inner_phase_b_start)


def _inner_zigzag(eval_df, start_idx, base_length, atr_override=None):
    """Inner-stage zigzag detector — identical to consolidation_v4._inner_zigzag."""
    EMPTY = (0, 0, 0, 1.0, 0, 0, 0, 0, 0)

    eq_df = eval_df.iloc[start_idx:]
    if len(eq_df) < settings.MIN_BASE_DAYS:
        return EMPTY

    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    if len(eq_df) >= settings.PIVOT_ORDER_THRESHOLD:
        ORDER = settings.PIVOT_ORDER_LONG
    else:
        ORDER = settings.PIVOT_ORDER_SHORT
    peaks_idx, valleys_idx = _find_pivots(eq_highs, eq_lows, ORDER)
    if not peaks_idx or not valleys_idx:
        return EMPTY

    if atr_override is not None and atr_override > 0 and not np.isnan(atr_override):
        atr_val = float(atr_override)
    else:
        win = settings.PHASE_B_ATR_WINDOW
        if 'ATR_10' in eq_df.columns:
            recent_atr = eq_df['ATR_10'].values[-win:] if len(eq_df) >= win else eq_df['ATR_10'].values
            atr_val = float(np.nanmedian(recent_atr))
        else:
            atr_val = float(np.median(eq_highs - eq_lows))
        if atr_val <= 0 or np.isnan(atr_val):
            atr_val = float(np.median(eq_highs - eq_lows))

    zigzag = _build_zigzag(peaks_idx, valleys_idx, eq_highs, eq_lows)
    if len(zigzag) < 2:
        return EMPTY

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
        cand_len = len(cand_eq_df)
        if cand_len < _INNER_MIN_DAYS:
            continue
        cand_highs = eq_highs[cand_start:]
        cand_lows = eq_lows[cand_start:]

        respected, _r_broken, _s_broken, total_outside = _is_boundary_respected(
            cand_highs, cand_lows, R_val, S_val, atr_val,
        )
        if not respected:
            continue

        r_touches, s_touches, crosses, is_valid = _validate_base_quality(
            cand_eq_df, R_val, S_val, atr_val,
        )
        if not is_valid:
            continue

        tightness_score = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
        touch_score = min(1.0, (r_touches + s_touches) / 10.0)
        midline_score = min(1.0, crosses / 8.0)
        combined = 0.4 * tightness_score + 0.4 * touch_score + 0.2 * midline_score

        valid_candidates.append((
            combined, R_val, S_val, box_width,
            r_touches, s_touches, total_outside,
            r_anchor_bar, s_anchor_bar, cand_start,
        ))

    if not valid_candidates:
        return EMPTY

    valid_candidates.sort(key=lambda x: x[0], reverse=True)
    _, best_R, best_S, best_bw, best_rt, best_st, best_breach, \
        best_r_bar, best_s_bar, best_cand_start = valid_candidates[0]

    effective_base_length = base_length - best_cand_start
    new_r_anchor = best_r_bar - best_cand_start
    new_s_anchor = best_s_bar - best_cand_start
    return (effective_base_length, best_R, best_S, best_bw, best_rt, best_st,
            best_breach, new_r_anchor, new_s_anchor)
