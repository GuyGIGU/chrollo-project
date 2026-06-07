"""Zigzag candidate generation + worked-equilibrium validity for consolidation boxes.

A candidate is a Resistance-anchor / Support-anchor pair drawn from the zigzag
(``BC``/``AR`` are the Phase-A trend climax/rally — the place the search begins,
not the rails). A pair is only a REAL trading range if price respects, touches,
and zigzags through both rails CONSTANTLY with no dead space — enforced by
``_is_boundary_respected`` (respect) + ``_validate_base_quality`` (constant
two-sided touch + both-halves dwell + coverage, via
``metrics.measure_equilibrium``). Selection keeps the EARLIEST pair that passes
every constraint; if none passes, the box is rejected.
"""
from __future__ import annotations

import numpy as np

from config import settings
from core.structure.metrics import measure_equilibrium
from core.structure.pivots import _build_zigzag, _find_pivots


INNER_MIN_DAYS = 15   # min length of an inner CANDIDATE box. NOTE: _inner_zigzag
                      # separately requires the search WINDOW to be >= MIN_BASE_DAYS
                      # (the binding floor); the room-checks that use this constant
                      # are only a looser pre-filter.
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
    Worked-equilibrium validity: a candidate Resistance/Support-anchor pair is a
    REAL trading range only if price respects, touches, and zigzags through BOTH
    rails CONSTANTLY, with no dead space.

    Boundary respect is enforced separately by the caller
    (``_is_boundary_respected``) before this is called; here we add the
    occupancy half of the test via ``measure_equilibrium``:
      - Box width within limits
      - Crash filter: no catastrophic wick below support
      - Constant two-sided touch: >= EQ_MIN_TOUCHES_PER_RAIL on each rail, each
        touched across >= EQ_MIN_TOUCH_THIRDS of 3 time-thirds (not clustered)
      - No dead space: closes dwell in BOTH the lower and upper box third
        (>= EQ_MIN_HALF_DWELL each) and the box-height coverage is not starved
        (>= EQ_MIN_COVERAGE)
      - Not mid-box churn: middle-third dwell <= EQ_MAX_MID_DWELL

    The old "2 touches/side + N midline crosses" gate is retired — it let the
    widest BC->AR framing win (a wide box mechanically racks up crosses while a
    one-time AR low leaves dead space beneath the real range).

    Returns:
        (r_touches, s_touches, eq, is_valid)  where eq is the measure_equilibrium
        dict (None when rejected on width/crash before measuring).
    """
    box_width = (R_val - S_val) / S_val
    if box_width > settings.MAX_BOX_WIDTH or box_width <= 0:
        return 0, 0, None, False

    if eq_df['Low'].min() < S_val * settings.CRASH_FILTER_MULT:
        return 0, 0, None, False

    eq = measure_equilibrium(eq_df, R_val, S_val, atr_val)
    r_touches, s_touches = eq["r_touches"], eq["s_touches"]

    is_valid = (
        r_touches >= settings.EQ_MIN_TOUCHES_PER_RAIL
        and s_touches >= settings.EQ_MIN_TOUCHES_PER_RAIL
        and eq["r_touch_thirds"] >= settings.EQ_MIN_TOUCH_THIRDS
        and eq["s_touch_thirds"] >= settings.EQ_MIN_TOUCH_THIRDS
        and eq["lower_dwell"] >= settings.EQ_MIN_HALF_DWELL
        and eq["upper_dwell"] >= settings.EQ_MIN_HALF_DWELL
        and eq["mid_dwell"] <= settings.EQ_MAX_MID_DWELL
        and eq["coverage"] >= settings.EQ_MIN_COVERAGE
    )
    return r_touches, s_touches, eq, is_valid


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


def _score_candidate(box_width, r_touches, s_touches, coverage):
    """Combined quality of a (valid) candidate framing — drives "best"/debug
    selection and breaks "earliest" ties. All inputs already passed validity."""
    tightness_score = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
    touch_score = min(1.0, (r_touches + s_touches) / 10.0)
    coverage_score = coverage
    return 0.4 * tightness_score + 0.4 * touch_score + 0.2 * coverage_score


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

        r_touches, s_touches, eq, is_valid = _validate_base_quality(
            cand_eq_df, R_val, S_val, atr_val,
        )
        if not is_valid:
            continue

        combined = _score_candidate(box_width, r_touches, s_touches, eq["coverage"])
        valid_candidates.append((
            combined, R_val, S_val, box_width,
            r_touches, s_touches, total_outside,
            r_anchor_bar, s_anchor_bar, cand_start,
        ))

    return valid_candidates


def _select_phase_b_candidate(valid_candidates, select):
    """Pick one framing from the valid set.

    Every candidate here already passed the worked-equilibrium validity rule, so
    "earliest" is simply the earliest-starting valid range (longest Wyckoff
    cause), ties broken by higher combined quality. This is the user's "earliest
    OF the ones that qualify" — there is no longer a best-vs-earliest tension or
    a reach-quality floor, because a sparse/dead-space framing can no longer be
    valid in the first place. "best" stays for diagnostics.
    """
    if select == "earliest":
        return min(valid_candidates, key=lambda x: (x[9], -x[0]))
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


def _detect_inner_phase_b_start(eq_df):
    """Locate the inner Phase B start from a detected inner climax.

    The inner instance of the outer BC->AR anchoring, one scale down and
    direction-agnostic (an inner base can sit inside a flat outer box, so there
    is no 'dominant trend' to lean on). Within the outer-base window ``eq_df`` it
    scans zigzag peak->valley limbs from the most RECENT end backward and returns
    the first that is a genuine reaction: a drop >= AR_MIN_DROP_PCT (the same
    'what counts as a reaction' threshold the outer climax uses) whose reaction
    low still leaves >= INNER_MIN_DAYS bars for an inner base to form. That low is
    the inner AR — the root swing the inner R/S is born from.

    Returns the inner AR-low bar as a 0-based OFFSET into ``eq_df``, or None when
    no clean inner climax exists (the caller falls back to its own heuristic).
    Pure measurement — reads price only, reuses existing tunables, decides nothing
    about scoring or eligibility.
    """
    n = len(eq_df)
    if n < INNER_MIN_DAYS + 2:
        return None

    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values
    peaks_idx, valleys_idx = _find_pivots(eq_highs, eq_lows, _pivot_order(n))
    if not peaks_idx or not valleys_idx:
        return None
    zigzag = _build_zigzag(peaks_idx, valleys_idx, eq_highs, eq_lows)
    if len(zigzag) < 2:
        return None

    # Most-recent qualifying inner climax: scan peak->valley limbs newest-first.
    for i in range(len(zigzag) - 2, -1, -1):
        zi, zj = zigzag[i], zigzag[i + 1]
        if zi[1] != 'peak' or zj[1] != 'valley':
            continue
        peak_p, val_p = zi[2], zj[2]
        if peak_p <= 0 or val_p >= peak_p:
            continue
        if (peak_p - val_p) / peak_p < settings.AR_MIN_DROP_PCT:
            continue
        ar_bar = int(zj[0])                     # offset into eq_df of the inner AR
        if (n - ar_bar) >= INNER_MIN_DAYS:
            return ar_bar
    return None
