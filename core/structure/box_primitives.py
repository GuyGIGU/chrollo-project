"""Shared calibrated box primitives.

The live chronological bricks and the diagnostic standalone detectors in
``consolidation`` both compose these measurement helpers.

A candidate is a Resistance-anchor / Support-anchor pair drawn from the zigzag
(``BC``/``AR`` are the Phase-A trend climax/rally — the place the search begins,
not the rails). A pair is only a REAL trading range if price respects, touches,
and zigzags through both rails CONSTANTLY with no dead space — enforced by
``_is_boundary_respected`` (respect) + ``_validate_base_quality`` (constant
two-sided touch + close-residence dwell/coverage). Selection keeps the EARLIEST pair that passes
every constraint; if none passes, the box is rejected.
"""
from __future__ import annotations

import numpy as np

from config import settings
from core.structure.metrics import measure_traversal
from core.structure.pivots import _build_zigzag, _find_pivots


INNER_MIN_DAYS = 15   # min length of an inner CANDIDATE box. NOTE: inner_zigzag
                      # separately requires the search WINDOW to be >= MIN_BASE_DAYS
                      # (the binding floor); the room-checks that use this constant
                      # are only a looser pre-filter.
EMPTY_BOX = (0, 0, 0, 1.0, 0, 0, 0, 0, 0)

__all__ = [
    "INNER_MIN_DAYS",
    "EMPTY_BOX",
    "collect_root_anchors",
    "inner_box_at",
    "collect_zigzag_candidates",
    "select_phase_b_candidate",
    "detect_inner_root_swing",
    "select_inner_box",
    "phase_b_zigzag",
    "inner_zigzag",
    "_detect_inner_phase_b_start",
    "_validate_base_quality",
    "_worked_window_end",
]


def collect_root_anchors(eval_df: "pd.DataFrame", min_days: int) -> list[tuple[str, int, int, float, float]]:
    """Return qualifying Phase-A climax -> reaction anchors, most-recent first."""
    if len(eval_df) < min_days + 15:
        return []

    closes = eval_df['Close'].values
    highs = eval_df['High'].values
    lows = eval_df['Low'].values
    sma200 = eval_df['Close'].rolling(settings.ROOT_TREND_SMA).mean().values
    end = len(eval_df) - 1

    if np.isnan(sma200[end]) or closes[end] <= sma200[end]:
        return []

    min_move = settings.TREND_MIN_GAIN_PCT
    min_move_bars = settings.TREND_MIN_MOVE_BARS
    prior_lookback = settings.TREND_PRIOR_LOOKBACK
    local_peak_bars = settings.LOCAL_PEAK_BARS

    scan_lo = min_move_bars + 5
    scan_hi = end - min_days
    if scan_hi <= scan_lo:
        return []

    anchors: list[tuple[str, int, int, float, float]] = []

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
                        anchors.append(('BC', i, ar_low_bar, float(highs[i]), float(ar_low_val)))

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
                        anchors.append(('SC', i, bounce_high_bar, float(bounce_high_val), float(lows[i])))

    return anchors


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


def _worked_window_end(highs, lows, R_val, S_val, atr_val):
    """Index where the worked range ends, trimming a trailing SOS breakout tail.

    A range whose right side has already broken out above R and HELD above
    support — a creek-jump then back-up (SOS -> BUEC) — should be validated over
    its worked CAUSE, not penalised for the breakout. We trim the earliest
    trailing run of ``>= SOS_TRIM_MIN_RUN`` consecutive above-(R+buffer) bars
    that (a) begins past the worked prefix (``>= SOS_TRIM_MIN_PREFIX_FRAC`` of the
    window) and (b) holds support to the end (no Low dips below S-buffer after
    it). Returns ``len(highs)`` when there is no such tail — the no-op case:
    price never broke out and held, so every ordinary in-range framing (and every
    downside breakdown) is unaffected.

    Pure / None-safe. Buffer mirrors ``_is_boundary_respected`` (bars, not
    candles) so the trim and the respect gate speak the same geometry.
    """
    n = len(highs)
    if not settings.SOS_TRIM_ENABLED or n == 0:
        return n
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    buffer = settings.BOUNDARY_ATR_BUFFER * atr_val
    r_ceiling = R_val + buffer
    s_floor = S_val - buffer
    above = highs > r_ceiling
    min_prefix = settings.SOS_TRIM_MIN_PREFIX_FRAC * n
    i = 0
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            if (j - i) >= settings.SOS_TRIM_MIN_RUN and i >= min_prefix \
                    and float(lows[i:].min()) >= s_floor:
                return i
            i = j
        else:
            i += 1
    return n


def _measure_close_residence(eq_df, R_val, S_val, atr_val):
    """Legacy close-residence occupancy for box-of-record selection.

    Public ``measure_equilibrium`` now reports High/Low range occupancy for
    analysis, but selecting the parent box still uses closes as the residence
    concept. This preserves calibrated Phase-B rails while rail touches and
    boundary respect continue to use High/Low geometry.
    """
    empty = {
        "r_touches": 0, "s_touches": 0,
        "r_touch_thirds": 0, "s_touch_thirds": 0,
        "lower_dwell": 0.0, "mid_dwell": 1.0, "upper_dwell": 0.0,
        "coverage": 0.0,
    }
    if eq_df is None or len(eq_df) == 0:
        return empty
    box = R_val - S_val
    if box <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return empty

    highs = eq_df["High"].values.astype(float)
    lows = eq_df["Low"].values.astype(float)
    closes = eq_df["Close"].values.astype(float)
    n = len(closes)

    tb = settings.TOUCH_TOLERANCE_ATR * atr_val
    r_mask = np.abs(highs - R_val) <= tb
    s_mask = np.abs(lows - S_val) <= tb

    thirds = np.array_split(np.arange(n), 3)
    r_touch_thirds = sum(1 for t in thirds if len(t) and r_mask[t].any())
    s_touch_thirds = sum(1 for t in thirds if len(t) and s_mask[t].any())

    pos = np.clip((closes - S_val) / box, 0.0, 1.0)
    lower_dwell = float(np.mean(pos <= 1.0 / 3.0))
    mid_dwell = float(np.mean((pos > 1.0 / 3.0) & (pos < 2.0 / 3.0)))
    upper_dwell = float(np.mean(pos >= 2.0 / 3.0))

    nb = settings.EQ_COVERAGE_BINS
    bins = np.minimum((pos * nb).astype(int), nb - 1)
    counts = np.bincount(bins, minlength=nb)
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


def _validate_base_quality(eq_df, R_val, S_val, atr_val):
    """
    Worked-equilibrium validity: a candidate Resistance/Support-anchor pair is a
    REAL trading range only if price respects, touches, and zigzags through BOTH
    rails CONSTANTLY, with no dead space.

    Boundary respect is enforced separately by the caller
    (``_is_boundary_respected``) before this is called; here we add the
    close-residence occupancy half of the test:
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
        (r_touches, s_touches, eq, is_valid)  where eq is the close-residence
        dict (None when rejected on width/crash before measuring).
    """
    box_width = (R_val - S_val) / S_val
    if box_width > settings.MAX_BOX_WIDTH or box_width <= 0:
        return 0, 0, None, False

    if eq_df['Low'].min() < S_val * settings.CRASH_FILTER_MULT:
        return 0, 0, None, False

    eq = _measure_close_residence(eq_df, R_val, S_val, atr_val)
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


def _apply_traversal_gate(eq_df, valid_candidates, atr_val, enforce_traversal):
    """Limb-traversal quality gate (v2): keep only framings whose swing limbs
    genuinely travel rail-to-rail, so the earliest-valid selection re-anchors R/S
    to the real swing envelope instead of a dead-space climax framing.

    A framing must clear BOTH floors:
      - COUNT  (``TRAVERSAL_MIN``): >= N genuine rail-to-rail swings.
      - DENSITY (``TRAVERSAL_MIN_DENSITY``): those swings are a real SHARE of the
        action. A long base racks up a few full trips amid a sea of interior chop
        (BMRN 5/111 = 0.045) and clears the count alone; winners run dense (seed
        floor ~0.14). Low density = the box is too wide / mis-anchored.

    Sub-threshold framings are dropped with NO legacy fallback: when an anchor
    yields no qualifying framing, ``find_outer_box`` falls through to its other
    BC/SC anchors (deeper re-anchoring), and a stock whose every framing is sparse
    simply doesn't fire — that's the point, it isn't a worked range. Recall-safety
    rides on the thresholds sitting well below the validated winner floor (count:
    every seed winner >= 2; density: winner floor ~0.14 vs gate 0.08), policed by
    the seed-recall guard — not on keeping a bad box.

    No-op unless ``settings.TRAVERSAL_GATE_ENABLED`` and ``enforce_traversal`` (the
    outer Phase-B path only — inner boxes are short and tight by design, where
    rail-to-rail traversal is naturally rare, so they are measured but never gated).
    """
    if not (settings.TRAVERSAL_GATE_ENABLED and enforce_traversal):
        return valid_candidates

    # c[9]=cand_start, c[10]=judged-window length, c[1]=R_val, c[2]=S_val — measure
    # traversal on the SAME window the framing was respect/occupancy-validated over
    # (its trimmed worked cause when SOS-rescued; the full window when strict, where
    # c[10] spans to the edge so this is byte-identical to the legacy full slice).
    def _passes(c):
        trav = measure_traversal(eq_df.iloc[c[9]:c[9] + c[10]], c[1], c[2], atr_val)
        nf, ns = trav["n_full_traversals"], trav["n_swings"]
        return (nf >= settings.TRAVERSAL_MIN
                and ns > 0 and nf / ns >= settings.TRAVERSAL_MIN_DENSITY)

    return [c for c in valid_candidates if _passes(c)]


def _build_candidate(highs, lows, sub_df, R_val, S_val, box_width,
                     r_anchor_bar, s_anchor_bar, cand_start, atr_val):
    """Respect + occupancy over one window; return the candidate tuple or None.

    ``highs``/``lows``/``sub_df`` describe the window the framing is JUDGED on
    (the full candidate window for a strict framing, or its trimmed worked cause
    for a rescued one). R/S/anchors/cand_start are always the framing's true
    full-base coordinates — only the measurement window narrows.
    """
    respected, _r_broken, _s_broken, total_outside = _is_boundary_respected(
        highs, lows, R_val, S_val, atr_val,
    )
    if not respected:
        return None
    r_touches, s_touches, eq, is_valid = _validate_base_quality(
        sub_df, R_val, S_val, atr_val,
    )
    if not is_valid:
        return None
    combined = _score_candidate(box_width, r_touches, s_touches, eq["coverage"])
    # Last slot = the JUDGED window length (= len(highs), relative to cand_start):
    # the full candidate window for a strict framing, or its trimmed worked cause
    # for a rescued one. The traversal gate measures over the SAME window, so a
    # rescued SOS tail can't be ignored for respect/occupancy yet counted here.
    return (combined, R_val, S_val, box_width, r_touches, s_touches, total_outside,
            r_anchor_bar, s_anchor_bar, cand_start, len(highs))


def collect_zigzag_candidates(eq_df, base_length, atr_val, min_candidate_days=0,
                              enforce_traversal=False):
    """Build valid R/S candidates from consecutive zigzag limbs."""
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    peaks_idx, valleys_idx = _find_pivots(eq_highs, eq_lows, _pivot_order(len(eq_df)))
    if not peaks_idx or not valleys_idx:
        return []

    zigzag = _build_zigzag(peaks_idx, valleys_idx, eq_highs, eq_lows)
    if len(zigzag) < 2:
        return []

    # Two pools: STRICT framings pass respect + occupancy over the full window
    # (the legacy rule, byte-identical); RESCUED framings only pass once a
    # trailing SOS breakout tail is trimmed (see ``_worked_window_end``). Rescued
    # framings are used ONLY when a window yields no strict one, so an ordinary
    # in-range setup is never re-framed — the trim can only save a box that would
    # otherwise be rejected outright (NMM's SOS -> BUEC).
    strict, rescued = [], []
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

        cand_highs = eq_highs[cand_start:]
        cand_lows = eq_lows[cand_start:]
        tup = _build_candidate(cand_highs, cand_lows, cand_eq_df, R_val, S_val,
                               box_width, r_anchor_bar, s_anchor_bar, cand_start,
                               atr_val)
        if tup is not None:
            strict.append(tup)
            continue

        # Rescue the SOS -> BUEC case: the worked cause is a clean range, only the
        # already-broken-out right side tripped the gates. Outer Phase-B only, and
        # only while price is still BACKING UP to the box (not extended away from
        # it): an old range price has since blown past is stale, not a setup — the
        # same extension semantics the firing filter uses, applied here so a stale
        # rescued box can't pre-empt the ticker's real recent box in backtracking.
        if enforce_traversal and settings.SOS_TRIM_ENABLED:
            work_end = _worked_window_end(cand_highs, cand_lows, R_val, S_val, atr_val)
            last_close = float(cand_eq_df['Close'].iloc[-1])
            if work_end < len(cand_highs) \
                    and last_close <= R_val * settings.EXTENSION_FILTER_MULT:
                tup = _build_candidate(
                    cand_highs[:work_end], cand_lows[:work_end],
                    cand_eq_df.iloc[:work_end], R_val, S_val, box_width,
                    r_anchor_bar, s_anchor_bar, cand_start, atr_val,
                )
                if tup is not None:
                    rescued.append(tup)

    pool = strict if strict else rescued
    return _apply_traversal_gate(eq_df, pool, atr_val, enforce_traversal)


def select_phase_b_candidate(valid_candidates, select):
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
    # Trailing *_ absorbs the judged-window length (slot 10), which is internal to
    # candidate selection / the traversal gate and not part of the rebased box.
    _, best_R, best_S, best_bw, best_rt, best_st, best_breach, \
        best_r_bar, best_s_bar, best_cand_start, *_ = candidate

    effective_base_length = base_length - best_cand_start
    new_r_anchor = best_r_bar - best_cand_start
    new_s_anchor = best_s_bar - best_cand_start
    return (effective_base_length, best_R, best_S, best_bw, best_rt, best_st,
            best_breach, new_r_anchor, new_s_anchor)


def phase_b_zigzag(eval_df, start_idx, base_length, atr_override=None,
                   select="earliest"):
    """Shared Phase B: zigzag S/R anchoring over eval_df.iloc[start_idx:]."""
    eq_df = eval_df.iloc[start_idx:]
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    atr_val = _candidate_atr(eq_df, eq_highs, eq_lows, atr_override)
    valid_candidates = collect_zigzag_candidates(
        eq_df, base_length, atr_val, enforce_traversal=True)

    if not valid_candidates:
        return [] if select == "debug" else EMPTY_BOX

    if select == "debug":
        return _debug_candidates(valid_candidates, base_length)

    selected = select_phase_b_candidate(valid_candidates, select)
    return _rebase_selected_candidate(selected, base_length)


def inner_zigzag(eval_df, start_idx, base_length, atr_override=None):
    """Inner-stage zigzag detector scored over each candidate's own bar range."""
    eq_df = eval_df.iloc[start_idx:]
    if len(eq_df) < settings.MIN_BASE_DAYS:
        return EMPTY_BOX

    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    atr_val = _candidate_atr(eq_df, eq_highs, eq_lows, atr_override)
    valid_candidates = collect_zigzag_candidates(
        eq_df, base_length, atr_val, min_candidate_days=INNER_MIN_DAYS,
    )
    if not valid_candidates:
        return EMPTY_BOX

    selected = max(valid_candidates, key=lambda x: x[0])
    return _rebase_selected_candidate(selected, base_length)


def inner_box_at(eval_df, start, n, source="midpoint", root=None):
    """Run the inner-stage zigzag from ``start`` and normalize to an inner-box dict.

    Returns None when the window is too short or no valid inner box forms. The
    returned ``start_bar`` is df-positional (n - effective base length), matching
    the engine's ``phase_b_start = len(df) - base_len`` convention.
    """
    # inner_zigzag itself requires the search window to be >= MIN_BASE_DAYS, so
    # gate on that same (eval_df-relative) floor - INNER_MIN_DAYS is only the min
    # inner CANDIDATE length, not the window floor.
    if start >= len(eval_df) or (len(eval_df) - start) < settings.MIN_BASE_DAYS:
        return None
    r = inner_zigzag(eval_df, start, n - start)
    if r[0] == 0:
        return None
    eff_base_len, R, S, bw, rt, st = r[0], r[1], r[2], r[3], r[4], r[5]
    box = {
        "R": float(R), "S": float(S), "box_width": float(bw),
        "base_len": int(eff_base_len), "start_bar": int(n - eff_base_len),
        "r_touches": int(rt), "s_touches": int(st),
        "r_anchor_bar": int(r[7]), "s_anchor_bar": int(r[8]),
        "source": source,
        "search_start_bar": int(start),
        "climax_bar": None,
        "reaction_bar": None,
        "reaction_pct": None,
        "reaction_bars": None,
    }
    if root is not None:
        box.update({
            "climax_bar": int(root["bc_bar"]),
            "reaction_bar": int(root["ar_bar"]),
            "reaction_pct": float(root["reaction_pct"]),
            "reaction_bars": int(root["reaction_bars"]),
        })
    return box


def detect_inner_root_swing(eq_df):
    """Measure the inner climax -> reaction swing inside an outer base.

    Bars are offsets into ``eq_df``. This is the richer measurement behind
    ``_detect_inner_phase_b_start``; it reports the inner climax, the reaction
    low that can birth an inner range, and the reaction magnitude.
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
        ar_bar = int(zj[0])
        if (n - ar_bar) >= INNER_MIN_DAYS:
            bc_bar = int(zi[0])
            return {
                "bc_bar": bc_bar,
                "ar_bar": ar_bar,
                "reaction_pct": round(float((peak_p - val_p) / peak_p), 4),
                "reaction_bars": int(ar_bar - bc_bar),
            }
    return None


def select_inner_box(eval_df, parent_pbs, base_len, bw_outer, n):
    """Select the tighter Phase-D inner box nested in a parent range.

    Builds the inner-box start candidates (the mechanical midpoint + the detected
    inner climax), validates each via ``inner_box_at``, and returns the TIGHTEST
    that clears the ``INNER_TIGHTNESS_RATIO`` gate (None when no meaningfully-tighter
    inner exists). Shared by the live reader (``bricks.find_inner_box``) and the
    diagnostic detector (``consolidation.detect_boxes``) so the inner-selection rule
    lives in one place; returns the raw inner-box dict from ``inner_box_at`` and each
    caller adapts it (a dataclass for the reader, the dict for diagnostics).
    """
    midpoint_start = parent_pbs + int(base_len * settings.INNER_SEARCH_FRACTION)
    starts = {
        midpoint_start: {"source": "midpoint", "root": None},
    }
    root = detect_inner_root_swing(eval_df.iloc[parent_pbs:])
    if root is not None:
        root_abs = {
            "bc_bar": parent_pbs + int(root["bc_bar"]),
            "ar_bar": parent_pbs + int(root["ar_bar"]),
            "reaction_pct": root["reaction_pct"],
            "reaction_bars": root["reaction_bars"],
        }
        starts[root_abs["ar_bar"]] = {"source": "inner_climax", "root": root_abs}

    candidates = []
    for s, meta in starts.items():
        box = inner_box_at(
            eval_df, s, n,
            source=meta["source"], root=meta["root"],
        )
        if box is not None and box["box_width"] < bw_outer * settings.INNER_TIGHTNESS_RATIO:
            candidates.append(box)
    return min(candidates, key=lambda b: b["box_width"]) if candidates else None


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
    root = detect_inner_root_swing(eq_df)
    return root["ar_bar"] if root is not None else None
