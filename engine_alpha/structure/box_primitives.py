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
from engine_alpha.structure.metrics import measure_traversal
from engine_alpha.structure.pivots import _build_zigzag, _find_pivots, _pivot_order


EMPTY_BOX = (0, 0, 0, 1.0, 0, 0, 0, 0, 0)

__all__ = [
    "EMPTY_BOX",
    "backext_shared_rail",
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


def _validate_base_quality(eq_df, R_val, S_val, atr_val, max_width=None):
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
    # ``max_width`` widens the cap ONLY for the deep-event pool (a pair
    # carrying a qualified terminal-shakeout event, BAND_MAX_BOX_WIDTH);
    # every ordinary caller leaves it None = the unchanged MAX_BOX_WIDTH.
    if box_width > (settings.MAX_BOX_WIDTH if max_width is None else max_width) \
            or box_width <= 0:
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


def _trace_pair(trace, verdict, stage, detail, R_val, S_val, box_width,
                r_anchor_bar, s_anchor_bar, cand_start, rescued=False):
    """Record one pair-cascade entry (the election narrating itself).

    No-op when ``trace`` is None — the live path never pays for it. Bars are
    window-relative here; ``validate_equilibrium`` rebases them df-positional.
    """
    if trace is None:
        return
    trace.append({
        "r_anchor_bar": int(r_anchor_bar),
        "s_anchor_bar": int(s_anchor_bar),
        "cand_start": int(cand_start),
        "R": round(float(R_val), 4),
        "S": round(float(S_val), 4),
        "box_width": round(float(box_width), 4),
        "verdict": verdict,        # "rejected" | "valid" | "elected"
        "stage": stage,            # width|window|respect|occupancy|traversal|rescue_unused|selection
        "detail": detail,
        "rescued": bool(rescued),
        "traversal": None,
    })


def _trace_find(trace, cand):
    """The 'valid' cascade record belonging to candidate tuple ``cand``."""
    key = (int(cand[7]), int(cand[8]), int(cand[9]))
    for rec in trace:
        if rec["verdict"] == "valid" \
                and (rec["r_anchor_bar"], rec["s_anchor_bar"], rec["cand_start"]) == key:
            return rec
    return None


def _occupancy_failures(eq, r_touches, s_touches):
    """Trace-only: name the worked-equilibrium occupancy checks a framing failed."""
    s = settings
    checks = [
        (r_touches < s.EQ_MIN_TOUCHES_PER_RAIL,
         f"r_touches {r_touches}<{s.EQ_MIN_TOUCHES_PER_RAIL}"),
        (s_touches < s.EQ_MIN_TOUCHES_PER_RAIL,
         f"s_touches {s_touches}<{s.EQ_MIN_TOUCHES_PER_RAIL}"),
        (eq["r_touch_thirds"] < s.EQ_MIN_TOUCH_THIRDS,
         f"r_touch_thirds {eq['r_touch_thirds']}<{s.EQ_MIN_TOUCH_THIRDS} (clustered)"),
        (eq["s_touch_thirds"] < s.EQ_MIN_TOUCH_THIRDS,
         f"s_touch_thirds {eq['s_touch_thirds']}<{s.EQ_MIN_TOUCH_THIRDS} (clustered)"),
        (eq["lower_dwell"] < s.EQ_MIN_HALF_DWELL,
         f"dead space low (lower_dwell {eq['lower_dwell']}<{s.EQ_MIN_HALF_DWELL})"),
        (eq["upper_dwell"] < s.EQ_MIN_HALF_DWELL,
         f"dead space high (upper_dwell {eq['upper_dwell']}<{s.EQ_MIN_HALF_DWELL})"),
        (eq["mid_dwell"] > s.EQ_MAX_MID_DWELL,
         f"mid churn (mid_dwell {eq['mid_dwell']}>{s.EQ_MAX_MID_DWELL})"),
        (eq["coverage"] < s.EQ_MIN_COVERAGE,
         f"coverage {eq['coverage']}<{s.EQ_MIN_COVERAGE}"),
    ]
    return [msg for failed, msg in checks if failed]


def _score_candidate(box_width, r_touches, s_touches, coverage):
    """Combined quality of a (valid) candidate framing — drives "best"/debug
    selection and breaks "earliest" ties. All inputs already passed validity."""
    tightness_score = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
    touch_score = min(1.0, (r_touches + s_touches) / 10.0)
    coverage_score = coverage
    return 0.4 * tightness_score + 0.4 * touch_score + 0.2 * coverage_score


def _apply_traversal_gate(eq_df, valid_candidates, atr_val, enforce_traversal,
                          trace=None):
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
        ok = (nf >= settings.TRAVERSAL_MIN
              and ns > 0 and nf / ns >= settings.TRAVERSAL_MIN_DENSITY)
        if trace is not None:
            rec = _trace_find(trace, c)
            if rec is not None:
                density = (nf / ns) if ns > 0 else 0.0
                rec["traversal"] = {"full": int(nf), "swings": int(ns),
                                    "density": round(density, 3)}
                if not ok:
                    rec["verdict"] = "rejected"
                    rec["stage"] = "traversal"
                    rec["detail"] = (
                        f"full={nf} density={density:.3f} (floors "
                        f"{settings.TRAVERSAL_MIN}/{settings.TRAVERSAL_MIN_DENSITY})")
        return ok

    return [c for c in valid_candidates if _passes(c)]


def _build_candidate(highs, lows, sub_df, R_val, S_val, box_width,
                     r_anchor_bar, s_anchor_bar, cand_start, atr_val,
                     trace=None, rescued=False, max_width=None):
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
        if trace is not None:
            # Name the sub-condition that actually fired: respect fails on the
            # outside SHARE or on a too-long consecutive RUN. When the share
            # passed, the run cap is — by elimination — the killer.
            n = len(highs)
            share = 1.0 - (total_outside / n) if n else 0.0
            if share < settings.MIN_BOUNDARY_RESPECT_PCT:
                detail = (f"{total_outside}/{n} bars outside the buffered rails "
                          f"(respect {share:.2f} < {settings.MIN_BOUNDARY_RESPECT_PCT})")
            else:
                detail = ("an outside run exceeded MAX_CONSECUTIVE_OUTSIDE_DAYS "
                          f"{settings.MAX_CONSECUTIVE_OUTSIDE_DAYS} "
                          f"({total_outside}/{n} bars outside in total)")
            _trace_pair(trace, "rejected", "respect", detail, R_val, S_val,
                        box_width, r_anchor_bar, s_anchor_bar, cand_start, rescued)
        return None
    r_touches, s_touches, eq, is_valid = _validate_base_quality(
        sub_df, R_val, S_val, atr_val, max_width=max_width,
    )
    if not is_valid:
        if trace is not None:
            detail = ("crash filter: min Low < S x CRASH_FILTER_MULT" if eq is None
                      else "; ".join(_occupancy_failures(eq, r_touches, s_touches)))
            _trace_pair(trace, "rejected", "occupancy", detail, R_val, S_val,
                        box_width, r_anchor_bar, s_anchor_bar, cand_start, rescued)
        return None
    combined = _score_candidate(box_width, r_touches, s_touches, eq["coverage"])
    _trace_pair(trace, "valid", None, None, R_val, S_val, box_width,
                r_anchor_bar, s_anchor_bar, cand_start, rescued)
    # Last slot = the JUDGED window length (= len(highs), relative to cand_start):
    # the full candidate window for a strict framing, or its trimmed worked cause
    # for a rescued one. The traversal gate measures over the SAME window, so a
    # rescued SOS tail can't be ignored for respect/occupancy yet counted here.
    return (combined, R_val, S_val, box_width, r_touches, s_touches, total_outside,
            r_anchor_bar, s_anchor_bar, cand_start, len(highs))


def collect_zigzag_candidates(eq_df, base_length, atr_val, min_candidate_days=0,
                              enforce_traversal=False, trace=None):
    """Build valid R/S candidates from consecutive zigzag limbs.

    ``trace``: optional list; when given, every pair examined is recorded with
    its verdict and (on rejection) the gate that killed it — the Root-Swing
    cascade narrating itself (see strategy_v2.md "The explainability rule").
    ``None`` (the live default) records nothing and changes nothing. The list
    must be scoped to a single call (pass a fresh one, as
    ``validate_equilibrium`` does): the rescue bookkeeping and the traversal
    gate match records across the WHOLE list they are handed.
    """
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
            _trace_pair(trace, "rejected", "width",
                        f"box_width {box_width:.3f} > MAX_BOX_WIDTH {settings.MAX_BOX_WIDTH}",
                        R_val, S_val, box_width, r_anchor_bar, s_anchor_bar,
                        min(r_anchor_bar, s_anchor_bar))
            continue

        cand_start = min(r_anchor_bar, s_anchor_bar)
        cand_eq_df = eq_df.iloc[cand_start:]
        if len(cand_eq_df) < min_candidate_days:
            _trace_pair(trace, "rejected", "window",
                        f"window {len(cand_eq_df)} < min_candidate_days {min_candidate_days}",
                        R_val, S_val, box_width, r_anchor_bar, s_anchor_bar,
                        cand_start)
            continue

        cand_highs = eq_highs[cand_start:]
        cand_lows = eq_lows[cand_start:]
        tup = _build_candidate(cand_highs, cand_lows, cand_eq_df, R_val, S_val,
                               box_width, r_anchor_bar, s_anchor_bar, cand_start,
                               atr_val, trace=trace)
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
                    trace=trace, rescued=True,
                )
                if tup is not None:
                    rescued.append(tup)

    pool = strict if strict else rescued
    # NOTE (solve-the-engine task 13b, 2026-07-16): a rescued-pool
    # ARBITRATION lever (let a fully-valid rescued framing that predates
    # every strict candidate compete) was built and REJECTED here — on the
    # sealed corpus it kills VIK's pinned hit (the admitted early framing
    # wins earliest-of-valid, then fails to complete an LPS, and an
    # elect-then-fail kills the whole root), and no clean currency rule
    # separates that case from the MOV framing it was meant to save — the
    # reverted shelf-R lesson at election scope. Do not re-attempt without
    # new corpus evidence; MOV's fire is already covered by the
    # holding-shelf form.

    # DARK (ELECTION_DETHRONE_ENABLED — solve-the-engine task 13a): a
    # rescue-propped framing whose buffered R the tape has left FULLY behind
    # for the trailing ELECTION_DETHRONE_SESSIONS sessions has stopped being
    # the operative structure (MATX: stale spring boxes blind the fresh
    # shelf). Dethroned only IN FAVOR OF a later valid framing — never into
    # an emptier read. One trailing pass over the already-loaded window;
    # pure function of the frame, no cross-session state.
    if settings.ELECTION_DETHRONE_ENABLED and len(pool) > 1:
        buf = settings.BOUNDARY_ATR_BUFFER * atr_val
        k = settings.ELECTION_DETHRONE_SESSIONS
        rescued_ids = {id(c) for c in rescued}
        stale = [c for c in pool
                 if id(c) in rescued_ids and len(eq_lows) >= k
                 and bool((eq_lows[-k:] > c[1] + buf).all())]
        if stale:
            survivor_starts = [c[9] for c in pool if id(c) not in {id(s) for s in stale}]
            dropped = [c for c in stale
                       if any(s > c[9] for s in survivor_starts)]
            if dropped:
                dropped_ids = {id(c) for c in dropped}
                pool = [c for c in pool if id(c) not in dropped_ids]
                if trace is not None:
                    for cand in dropped:
                        rec = _trace_find(trace, cand)
                        if rec is not None:
                            rec["verdict"] = "rejected"
                            rec["stage"] = "dethroned"
                            rec["detail"] = (
                                f"rescue-propped pair fully above R+buffer for "
                                f"the last {k} sessions; a later valid framing "
                                f"is the operative structure")

    # LAST-RESORT worked-band pool (BAND_RAILS_ENABLED, dark; outer Phase B
    # only): consulted ONLY when both extreme-anchored pools are empty, so an
    # ordinary election can never move. Rails at the max-dwell close band;
    # qualified excursions (reclaim/fail-back + hold) are excised from the
    # judged window; every gate below runs UNCHANGED on the judged bars.
    if not pool and enforce_traversal and settings.BAND_RAILS_ENABLED:
        pool = _band_rail_candidates(eq_df, eq_highs, eq_lows, zigzag, atr_val,
                                     trace=trace)

    if trace is not None and strict and rescued:
        for rec in trace:
            if rec["verdict"] == "valid" and rec["rescued"]:
                rec["verdict"] = "rejected"
                rec["stage"] = "rescue_unused"
                rec["detail"] = "strict framings exist; the rescued pool is discarded"
    return _apply_traversal_gate(eq_df, pool, atr_val, enforce_traversal, trace=trace)


def _band_rail_candidates(eq_df, eq_highs, eq_lows, zigzag, atr_val, trace=None):
    """Build the deep-event candidate pool for a window (possibly empty).

    Re-judges the SAME chronological zigzag pairs the strict pool enumerated —
    the operator's rail rule ("anchor R/S from the swings in chronological
    order, wick to wick") — with each pair's qualified excursion events excised
    from the judged window (``band_rails.qualify_pair_events``: every
    band-leaving span must reclaim/fail-back and HOLD, and at least one deep
    below-rail event must exist, or the pair is refused). Judged windows run
    the unchanged ``_build_candidate`` gates — the SOS-trim narrowed-
    measurement convention — except that a pair carrying a qualified deep
    event may measure up to ``BAND_MAX_BOX_WIDTH`` wick-to-wick (the class
    allowance; it exists only when the event does).
    """
    from engine_alpha.structure.band_rails import qualify_pair_events

    pool = []
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
        if box_width > settings.BAND_MAX_BOX_WIDTH:
            continue

        cand_start = min(r_anchor_bar, s_anchor_bar)
        read = qualify_pair_events(eq_df.iloc[cand_start:], S_val, R_val, atr_val)
        if read is None:
            continue
        mask = read["judged"]
        tup = _build_candidate(
            eq_highs[cand_start:][mask], eq_lows[cand_start:][mask],
            eq_df.iloc[cand_start:][mask], R_val, S_val, box_width,
            r_anchor_bar, s_anchor_bar, cand_start, atr_val,
            trace=trace, rescued=True, max_width=settings.BAND_MAX_BOX_WIDTH,
        )
        if tup is None:
            continue
        if trace is not None:
            rec = _trace_find(trace, tup)
            if rec is not None:
                rec["detail"] = (f"chronological pair with {len(read['excursions'])} "
                                 "qualified excursion event(s) excised from the "
                                 "judged window")
        pool.append(tup)
    return pool


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


def backext_shared_rail(eq_df, R_val, S_val, cand_start, atr_val):
    """Shared-rail back-extension of an ELECTED framing's start (gap #3).

    Candidate starts are pinned to their anchor pair (``cand_start =
    min(r_anchor, s_anchor)``), so the earliest-valid election can never reach
    an earlier start its own gates would bless (AGCO: the dissection proved
    the elected rails valid from 03-25, but the anchor pair proposes only
    04-02). When ``BOX_BACKEXT_ENABLED``, walk the elected start LEFT to the
    EARLIEST zigzag pivot that re-touches an elected rail within touch
    tolerance (peak ~ R or valley ~ S) with every intervening bar inside the
    buffered band [S - buf, R + buf]. On AGCO that lands on the 03-30
    S-touching valley — 3 bars shy of full validity, because the 03-25 peak
    never re-touches R. Anchoring the extension to a rail re-touch is what
    separates worked cause from drift (a descent leg or mid-band chop never
    qualifies, however band-conforming).

    POST-election refinement: rails, the respect/occupancy verdicts and the
    election itself are untouched, and the extended span is conforming-by-
    construction so boundary respect can only improve. But the start moves,
    so every read anchored to it re-measures: the base-window suite
    (base-age, traversal, contractions, support slope, dwell, touch-volume,
    bar compression), the spring / inner-box / LPS windows, bin evidence,
    the event puzzle. Returns the (possibly unchanged) window-relative start.
    """
    if not settings.BOX_BACKEXT_ENABLED or cand_start <= 0:
        return cand_start
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values
    peaks_idx, valleys_idx = _find_pivots(eq_highs, eq_lows, _pivot_order(len(eq_df)))
    zigzag = _build_zigzag(peaks_idx, valleys_idx, eq_highs, eq_lows)
    tol = settings.TOUCH_TOLERANCE_ATR * atr_val
    buf = settings.BOUNDARY_ATR_BUFFER * atr_val
    for bar, kind, price in zigzag:                     # oldest pivot first
        if bar >= cand_start:
            break
        touches_rail = (abs(price - R_val) <= tol if kind == 'peak'
                        else abs(price - S_val) <= tol)
        if not touches_rail:
            continue
        if float(eq_highs[bar:cand_start].max()) <= R_val + buf \
                and float(eq_lows[bar:cand_start].min()) >= S_val - buf:
            return int(bar)
    return cand_start


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
    # The diagnostic mirror applies the same flag-gated shared-rail
    # back-extension as the live reader (bricks.validate_equilibrium), so
    # detect_boxes-based tools frame the SAME box as production. No-op when
    # the flag is off or nothing extends.
    ext_start = backext_shared_rail(eq_df, selected[1], selected[2],
                                    int(selected[9]), atr_val)
    if ext_start != selected[9]:
        selected = selected[:9] + (int(ext_start),) + selected[10:]
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
        eq_df, base_length, atr_val, min_candidate_days=settings.INNER_MIN_DAYS,
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
    if n < settings.INNER_MIN_DAYS + 2:
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
        if (n - ar_bar) >= settings.INNER_MIN_DAYS:
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
    low still leaves >= settings.INNER_MIN_DAYS bars for an inner base to form. That low is
    the inner AR — the root swing the inner R/S is born from.

    Returns the inner AR-low bar as a 0-based OFFSET into ``eq_df``, or None when
    no clean inner climax exists (the caller falls back to its own heuristic).
    Pure measurement — reads price only, reuses existing tunables, decides nothing
    about scoring or eligibility.
    """
    root = detect_inner_root_swing(eq_df)
    return root["ar_bar"] if root is not None else None
