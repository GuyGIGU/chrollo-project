"""
Wyckoff consolidation detection — identifies structural equilibrium bases
following macro trend exhaustion using zigzag-based S/R anchoring.

Two public entry points:

  ``find_consolidation(df)`` — hierarchical detector used by the live
  screener. Finds the outer BC→AR box, then probes the recent half for a
  tighter inner sub-box (Phase D launchpad / VCP mini-consolidation). When
  an inner exists and is meaningfully tighter, it wins; otherwise the outer
  is returned unchanged.

  ``find_outer_box(df)`` — anchor-enumeration only (no inner refinement).
  Used by the seed-archive curator where we want the textbook outer box,
  not a Phase-D launchpad.

Phase B uses a zigzag structural approach:
  1. Start from Wyckoff BC (Buying Climax) and AR (Automatic Reaction) anchors
  2. Build a zigzag from alternating pivot peaks and valleys
  3. Propose R/S candidates from consecutive zigzag limbs (peak→valley pairs)
  4. Validate candidates with boundary respect, touch density + midline quality
  5. Select the best candidate by weighted combined score
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import settings


# Hierarchical-detection tunables (inner sub-box gating).
# Inner box must be at most this fraction of the outer's box width.
# 0.75 = inner is at least 25% tighter than outer.
_INNER_TIGHTNESS_RATIO = 0.75

# Inner search starts at this fraction of the outer base. 0.5 = look at the
# second half of the outer consolidation for the tightening.
_INNER_SEARCH_FRACTION = 0.5

# Minimum bars an inner sub-box must span. The inner can be shorter than
# MIN_BASE_DAYS because it sits inside an already-validated outer base, but
# we still require enough bars to score touches/oscillation meaningfully.
_INNER_MIN_DAYS = 15


# ---------------------------------------------------------------------------
# Helper: Pivot Detection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helper: ATR-Buffered Boundary Respect Check
# ---------------------------------------------------------------------------

def _is_boundary_respected(highs, lows, R_val, S_val, atr_val):
    """
    Check if price action respects R/S boundaries using ATR-buffered zones.

    Uses the full daily range (highs vs R+buffer, lows vs S-buffer) — wicks
    that pierce the buffered zone count as breaches. Aligns with the
    "bars not candles" rule: structural logic is anchored to the full
    range, not to where the bar happened to close.

    Vectorized with NumPy for speed — avoids per-bar Python loop.

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
        # Pad with False on both ends to detect edges
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


# ---------------------------------------------------------------------------
# Helper: Touch Density & Midline Cross Validation
# ---------------------------------------------------------------------------

def _validate_base_quality(eq_df, R_val, S_val, atr_val):
    """
    Validate a candidate R/S pair using structural quality checks.

    Checks:
      - Box width within limits
      - Crash filter (no catastrophic wick below support)
      - Touch density (>= 2 touches on each boundary)
      - Midline oscillation (>= MIN_MIDLINE_CROSSES crosses, ATR-buffered)

    Returns:
        (r_touches, s_touches, crosses, is_valid)
    """
    box_width = (R_val - S_val) / S_val
    if box_width > settings.MAX_BOX_WIDTH or box_width <= 0:
        return 0, 0, 0, False

    if eq_df['Low'].min() < S_val * settings.CRASH_FILTER_MULT:
        return 0, 0, 0, False

    # Count S/R boundary touches within ATR-normalized tolerance
    # ATR-based tolerance ensures a "touch" means the same structural event
    # regardless of price level ($10 stock vs $500 stock).
    touch_band = settings.TOUCH_TOLERANCE_ATR * atr_val
    r_touches = int(((eq_df['High'] - R_val).abs() <= touch_band).sum())
    s_touches = int(((eq_df['Low'] - S_val).abs() <= touch_band).sum())

    if r_touches < 2 or s_touches < 2:
        return r_touches, s_touches, 0, False

    # Midline crosses — our tunnel-killer (ATR-buffered to eliminate whipsaw)
    # Price must travel at least MIDLINE_ATR_BUFFER × ATR away from the midline
    # before a subsequent return counts as a valid new cross.
    midline = (R_val + S_val) / 2
    buffer = settings.MIDLINE_ATR_BUFFER * atr_val
    close_vals = eq_df['Close'].values
    crosses = 0
    if len(close_vals) > 1:
        # Vectorized committed-cross counting:
        # A cross counts only after price "committed" to one side (moved >= buffer away).
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


# ---------------------------------------------------------------------------
# Phase B: shared zigzag-based S/R anchoring (used by find_outer_box)
# ---------------------------------------------------------------------------

def _phase_b_zigzag(eval_df, start_idx, base_length, atr_override=None):
    """Shared Phase B: zigzag S/R anchoring over eval_df.iloc[start_idx:].

    Returns the same 9-tuple shape as find_outer_box (EMPTY if no valid
    candidate found).

    ``atr_override``: when supplied, used as the ATR reference for boundary
    respect, touch density, and midline buffer — letting the engine align
    Phase B's volatility frame with the evaluation snapshot at bar -6 (the
    same ATR used for LPS zone tolerance). When None, falls back to the
    base-window median.
    """
    EMPTY = (0, 0, 0, 1.0, 0, 0, 0, 0, 0)

    eq_df = eval_df.iloc[start_idx:]
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
            atr_val = np.nanmedian(recent_atr)
        else:
            atr_val = (np.median(eq_highs[-win:] - eq_lows[-win:])
                       if len(eq_df) >= win else np.median(eq_highs - eq_lows))
        if atr_val <= 0 or np.isnan(atr_val):
            atr_val = np.median(eq_highs - eq_lows)

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

        # Both boundary and validation run over the candidate's own bar
        # window — from the earlier of the two anchor bars onward. The
        # bars before cand_start are part of Phase B's reaction
        # (markup-into-AR / AR itself) but they are not part of THIS
        # candidate's box. Including them inflates touch counts for
        # longer-window candidates over recent tighter ones, and
        # conflates pre-consolidation volatility with chop quality on
        # the boundary check.
        cand_start = min(r_anchor_bar, s_anchor_bar)
        cand_highs = eq_highs[cand_start:]
        cand_lows = eq_lows[cand_start:]
        cand_eq_df = eq_df.iloc[cand_start:]

        respected, _r_broken, _s_broken, total_outside = _is_boundary_respected(
            cand_highs, cand_lows, R_val, S_val, atr_val
        )
        if not respected:
            continue

        r_touches, s_touches, crosses, is_valid = _validate_base_quality(
            cand_eq_df, R_val, S_val, atr_val
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
    # Trim base_length to the candidate's window so downstream LPS sizing,
    # base_df spread quantiles, and effective_phase_b_start in
    # find_outer_box all reflect the actual box, not the entire Phase B
    # window from the AR low.
    effective_base_length = base_length - best_cand_start
    new_r_anchor = best_r_bar - best_cand_start
    new_s_anchor = best_s_bar - best_cand_start
    return (effective_base_length, best_R, best_S, best_bw, best_rt, best_st,
            best_breach, new_r_anchor, new_s_anchor)


# ---------------------------------------------------------------------------
# Inner-stage zigzag (used by find_consolidation hierarchical refinement)
# ---------------------------------------------------------------------------

def _inner_zigzag(eval_df, start_idx, base_length, atr_override=None):
    """Inner-stage zigzag detector — scores each candidate over ITS OWN
    bar range, not the full inner window.

    This is the critical difference from `_phase_b_zigzag` (the outer-stage
    detector). Inside an outer box's recent half, the bars span both the
    pre-formation period (when the inner box did not yet exist — price was
    still in the older zone) AND the inner box's active period. Scoring
    boundary-respect over the full window unfairly penalizes pre-formation
    bars; we score from the earlier of the two anchors onward instead.

    Returns the same 9-tuple shape as _phase_b_zigzag (EMPTY on no-match).
    The first element is the candidate's effective bar count (in df-frame,
    which includes the trim-edge bars).
    """
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

        # Per-candidate range — the box only "exists" from the earlier
        # anchor onward. Bars before that were forming a different
        # structure and don't count for boundary-respect.
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

    # Effective base_length = bars from earlier-anchor to end-of-df (includes
    # the 5 trimmed-edge bars). Anchors remapped relative to the new range so
    # downstream max(r_anchor, s_anchor) gives the swing-complete index.
    effective_base_length = base_length - best_cand_start
    new_r_anchor = best_r_bar - best_cand_start
    new_s_anchor = best_s_bar - best_cand_start
    return (effective_base_length, best_R, best_S, best_bw, best_rt, best_st,
            best_breach, new_r_anchor, new_s_anchor)


# ---------------------------------------------------------------------------
# Public: outer-box anchor-enumeration (no inner refinement)
# ---------------------------------------------------------------------------

def find_outer_box(df: "pd.DataFrame", min_days: int | None = None) -> tuple:
    """Extreme-anchored consolidation detection (BC or SC).

    Anchor qualification (a bar `i` is a candidate anchor if):
      - BC: highs[i] is the max over the last LOCAL_PEAK_BARS bars AND the
            stock rose >= TREND_MIN_GAIN_PCT from a prior low within the
            last PRIOR_LOOKBACK bars, over >= MIN_MOVE_BARS. Validated by an
            Automatic Reaction (>= AR_MIN_DROP_PCT drop within AR_MAX_BARS).
            Phase B starts at the AR *low* (skips the descent).
      - SC: lows[i] is the min over the last LOCAL_PEAK_BARS bars AND fell
            >= TREND_MIN_GAIN_PCT from a prior high. Validated by a bounce
            (>= AR_MIN_DROP_PCT rise within AR_MAX_BARS). Phase B starts at
            the bounce *high* (skips the ascent).

    Every qualifying anchor is tried — the Phase B that yields the tightest
    / best-touched box wins. That prevents an old anchor with a loose window
    from shadowing a recent anchor whose Phase B is actually structural.

    Macro gate: stock must be in a bullish context (above SMA200 OR has a
    qualifying markup run somewhere in the window).

    Returns a 12-tuple:
        (base_length, R, S, box_width, r_touches, s_touches, breach_days,
         r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar,
         is_inner)
    is_inner is always False here (this function never refines to an inner
    sub-box). The hierarchical detector ``find_consolidation`` sets it True
    when a Phase D launchpad replaces the outer box. All zeros on failure.
    """
    if min_days is None:
        min_days = settings.MIN_BASE_DAYS
    # 12-tuple: original 9 fields + bc_anchor_bar + phase_b_start_bar (both
    # df-positional) + is_inner (always False from this function).
    # eval_df = df.iloc[:-5] so eval_df-positional indices for [0..len(eval_df)-1]
    # align with df-positional indices in the same range.
    EMPTY = (0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0, 0, False)

    eval_df = df.iloc[:-5] if len(df) > 5 else df
    if len(eval_df) < min_days + 15:
        return EMPTY

    closes = eval_df['Close'].values
    highs = eval_df['High'].values
    lows = eval_df['Low'].values

    sma200 = eval_df['Close'].rolling(200).mean().values

    end = len(eval_df) - 1

    # Engine-aligned ATR snapshot — same bar (df[-6] == eval_df[-1]) used
    # downstream for LPS zone tolerance, so Phase B and the LPS detector
    # share one volatility frame.
    if 'ATR_10' in eval_df.columns:
        atr_snapshot = float(eval_df['ATR_10'].iloc[-1])
        if np.isnan(atr_snapshot) or atr_snapshot <= 0:
            atr_snapshot = None
    else:
        atr_snapshot = None

    # --- MACRO GATE: bullish context required ---
    # Baseline already filters Close < SMA_200 at bar -1; this re-asserts the
    # condition at the evaluation bar (-6) so the function stays self-contained
    # if called outside the standard pipeline.
    if np.isnan(sma200[end]) or closes[end] <= sma200[end]:
        return EMPTY

    # --- ANCHOR DISCOVERY: enumerate every qualifying extreme ---
    min_move = settings.TREND_MIN_GAIN_PCT
    min_move_bars = settings.TREND_MIN_MOVE_BARS
    prior_lookback = settings.TREND_PRIOR_LOOKBACK
    local_peak_bars = settings.LOCAL_PEAK_BARS

    scan_lo = min_move_bars + 5
    scan_hi = end - min_days
    if scan_hi <= scan_lo:
        return EMPTY

    # Each entry: (anchor_type, anchor_bar, phase_b_start)
    anchors: list[tuple[str, int, int]] = []

    for i in range(scan_hi, scan_lo - 1, -1):
        prior_start = max(0, i - prior_lookback)
        local_start = max(0, i - local_peak_bars)

        # BC: highs[i] is the local peak over the prior local window.
        if highs[i] >= np.max(highs[local_start:i + 1]):
            prior_lows = lows[prior_start:i]
            if len(prior_lows) >= min_move_bars:
                trough_k = int(np.argmin(prior_lows))
                trough_low = float(prior_lows[trough_k])
                trough_bar = prior_start + trough_k
                if trough_low > 0 \
                        and highs[i] / trough_low - 1.0 >= min_move \
                        and (i - trough_bar) >= min_move_bars:
                    # AR: confirm >=5% drop, then anchor Phase B at AR LOW.
                    # Starting at the AR low (not the first threshold cross)
                    # skips the reaction descent so the Phase B window doesn't
                    # include mid-fall bars that would break boundary respect.
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

        # SC: lows[i] is the local trough over the prior local window.
        if lows[i] <= np.min(lows[local_start:i + 1]):
            prior_highs = highs[prior_start:i]
            if len(prior_highs) >= min_move_bars:
                peak_k = int(np.argmax(prior_highs))
                peak_high = float(prior_highs[peak_k])
                peak_bar = prior_start + peak_k
                if peak_high > 0 \
                        and 1.0 - lows[i] / peak_high >= min_move \
                        and (i - peak_bar) >= min_move_bars:
                    # Bounce: confirm >=5% rise, anchor Phase B at bounce HIGH.
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

    # --- PHASE B: pick the EARLIEST anchor whose Phase B passes quality gates ---
    # `anchors` is built most-recent-first (line above scans range(scan_hi, scan_lo-1, -1)),
    # so reversed() gives oldest-first. _phase_b_zigzag already enforces all
    # quality checks (box width, boundary respect, touch density, midline crosses);
    # any non-EMPTY return is a valid Phase B. Preferring the earliest valid anchor
    # maximizes Wyckoff "cause" (base age) and resists the truncation failure where
    # a mid-base upthrust is selected over the true climax because its shorter
    # window mechanically yields a tighter box.
    for _atype, _abar, phase_b_start in reversed(anchors):
        base_length = len(df) - phase_b_start
        result = _phase_b_zigzag(
            eval_df, phase_b_start, base_length, atr_override=atr_snapshot,
        )
        if result[0] != 0:
            # Effective phase_b_start = original AR-low anchor + the
            # cand_start offset baked into result[0]. Mirrors the
            # downstream computation `phase_b_start = len(df) - base_len`.
            effective_phase_b_start = len(df) - result[0]
            return result + (_abar, effective_phase_b_start, False)

    return EMPTY


# ---------------------------------------------------------------------------
# Public: hierarchical detector (live entry point)
# ---------------------------------------------------------------------------

def find_consolidation(df, min_days=None):
    """Hierarchical detection: try inner sub-box, fall back to outer.

    Strategy:
      1. Find the standard "outer" box via find_outer_box.
      2. Probe the most recent portion of that box for a *tighter* sub-box
         (the user's "Phase D mini-consolidation" / VCP launchpad pattern):
         "Smaller/tighter consolidation zones within an existing
         consolidation typically forming after Phase C before breakout".
      3. If a valid inner box exists AND is meaningfully tighter than the
         outer, return the inner. Otherwise fall back to the outer.

    This preserves all single-base detections (outer always wins when no
    inner exists) and adds true Phase D detection (inner ⊂ outer in time,
    not necessarily in price space).

    The matching LPS-scaling adaptations live in core/screener_v2.py
    (_detect_lps zone-tolerance floor and _evaluate_ticker base_range_threshold
    floor). Both self-gate on tight boxes and leave wide-outer detections
    untouched.

    REMAINING MISSES — NBR / GXO / VLO / SHEL plus ST / RRBI / SNDX / TRS are
    LPS-detector limits, not anchor-detection limits. The recent-first-anchor
    hypothesis (v5) was tested and falsified: see
    experiments/dead_ends/v5_recent_first_anchor/. v5 picks different (more
    recent) outer anchors but the LPS detector still rejects at the same gates
    (zone_gate, spread_quantile). Re-test only if the LPS detector itself is
    rewritten — anchor preference alone won't help.

    Returns same 12-tuple shape as find_outer_box:
        (base_length, R, S, box_width, r_touches, s_touches, breach_days,
         r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar,
         is_inner)
    is_inner is True when the inner sub-box (Phase D launchpad) replaced the
    outer detection, False when the outer box is returned unchanged.
    """
    if min_days is None:
        min_days = settings.MIN_BASE_DAYS

    outer = find_outer_box(df, min_days=min_days)
    if outer[0] == 0:
        return outer

    (outer_base_len, R_outer, S_outer, bw_outer,
     _rt, _st, _br, _ra, _sa, bc_anchor, outer_phase_b_start,
     _outer_is_inner) = outer

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

    # Inner must be meaningfully tighter than the outer. No price-containment
    # check: inner can sit inside, above, or below outer in price space — as
    # long as it's *temporally* inside outer's time window. Outer's
    # boundary-respect gate already filters out wild outliers, so an inner
    # found in outer's recent half is structurally adjacent regardless of
    # whether its R/S sit inside outer's bounds.
    if bw_inner >= bw_outer * _INNER_TIGHTNESS_RATIO:
        return outer

    return inner_result + (bc_anchor, inner_phase_b_start, True)
