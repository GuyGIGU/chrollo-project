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
from core.structure.box_candidates import (
    INNER_MIN_DAYS,
    _inner_zigzag,
    _phase_b_zigzag,
    _select_phase_b_candidate,
)
from core.structure.metrics import (
    measure_bar_compression,
    measure_contractions,
    measure_support_slope,
    measure_touch_volume,
)


# Hierarchical-detection tunables (inner sub-box gating).
# Inner box must be at most this fraction of the outer's box width.
# 0.75 = inner is at least 25% tighter than outer.
_INNER_TIGHTNESS_RATIO = 0.75

# Inner search starts at this fraction of the outer base. 0.5 = look at the
# second half of the outer consolidation for the tightening.
_INNER_SEARCH_FRACTION = 0.5


# ---------------------------------------------------------------------------
# Public: outer-box anchor-enumeration (no inner refinement)
# ---------------------------------------------------------------------------

def find_outer_box(df: "pd.DataFrame", min_days: int | None = None,
                   select: str = "earliest") -> tuple:
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
        if select == "debug":
            # Diagnostic: return the candidate landscape for the first anchor
            # that yields a valid Phase B (the one the live engine would use).
            probe = _phase_b_zigzag(
                eval_df, phase_b_start, base_length, atr_override=atr_snapshot,
                select="best",
            )
            if probe[0] != 0:
                return _phase_b_zigzag(
                    eval_df, phase_b_start, base_length,
                    atr_override=atr_snapshot, select="debug",
                )
            continue
        result = _phase_b_zigzag(
            eval_df, phase_b_start, base_length, atr_override=atr_snapshot,
            select=select,
        )
        if result[0] != 0:
            # Effective phase_b_start = original AR-low anchor + the
            # cand_start offset baked into result[0]. Mirrors the
            # downstream computation `phase_b_start = len(df) - base_len`.
            effective_phase_b_start = len(df) - result[0]
            return result + (_abar, effective_phase_b_start, False)

    return [] if select == "debug" else EMPTY


# ---------------------------------------------------------------------------
# Public: hierarchical detector (live entry point)
# ---------------------------------------------------------------------------

def find_consolidation(df, min_days=None, select="earliest"):
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

    The matching LPS-scaling adaptations live in core/structure/lps.py
    (detect_lps zone-tolerance floor) and core/pipeline/screener.py
    (_evaluate_ticker base_range_threshold floor). Both self-gate on tight
    boxes and leave wide-outer detections untouched.

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

    # `select` steers ONLY the outer box's candidate-pair choice (earliest
    # range start vs global-best). The inner stage stays best-score: its whole
    # job is to find the tighter recent launchpad, so it should chase tightness.
    outer = find_outer_box(df, min_days=min_days, select=select)
    if outer[0] == 0:
        return outer

    (outer_base_len, R_outer, S_outer, bw_outer,
     _rt, _st, _br, _ra, _sa, bc_anchor, outer_phase_b_start,
     _outer_is_inner) = outer

    inner_phase_b_start = outer_phase_b_start + int(outer_base_len * _INNER_SEARCH_FRACTION)
    if (len(df) - inner_phase_b_start) < INNER_MIN_DAYS:
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
