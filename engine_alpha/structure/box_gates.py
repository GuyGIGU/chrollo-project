"""Gate application for the box election cascade.

The validity judges every candidate R/S pair must pass before it can be
elected: boundary respect (ATR-buffered containment), the SOS worked-window
trim, close-residence dwell/coverage, the worked-equilibrium occupancy rule,
and the rail-to-rail traversal floor. Gates MEASURE and judge a given pair;
election policy (which pair wins) stays in ``box_primitives``, and both narrate
through ``box_trace``.

Split out of ``box_primitives`` 2026-07-18 (Purity task 8) as a pure
structural move — every function verbatim.
"""
from __future__ import annotations

import numpy as np

from config import settings
from engine_alpha.structure.box_trace import _trace_find
from engine_alpha.structure.metrics import _rail_touch_thirds, measure_equilibrium

__all__ = [
    "_buffered_rails",
    "_rail_outside_masks",
    "_engagement_hang_masks",
    "_max_excursion_atr",
    "_is_boundary_respected",
    "_worked_window_end",
    "_measure_close_residence",
    "_dwell_bar_basis",
    "_validate_base_quality",
    "_occupancy_failures",
    "_apply_traversal_gate",
]


def _buffered_rails(R_val, S_val, atr_val):
    """The ATR-buffered rail levels (R + buffer, S − buffer) every outside /
    containment judgment measures against. Levels ONLY — each caller keeps its
    own comparison form verbatim (strict vs inclusive is NaN routing, never
    restyle; fold-safety dossier)."""
    buffer = settings.BOUNDARY_ATR_BUFFER * atr_val
    return R_val + buffer, S_val - buffer


def _rail_outside_masks(highs, lows, R_val, S_val, atr_val):
    """The ONE per-bar rail classification against the buffered box envelope.

    Whole-bar basis — highs vs R+buffer, lows vs S−buffer (operator ruling
    2026-07-24: "the HIGH and the LOW Values are the ones that matters most
    since Visually we use the entire bar in Technical analysis ALWAYS").
    Every consumer of "is this bar outside a rail?" — the respect gate, the
    SOS worked-window trim, and any graded engagement read layered on top —
    derives from THESE masks, so the physics can never fork per call site.

    Returns ``(above_r, below_s, r_ceiling, s_floor)``. The mask comparisons
    are strict (NaN → False = inside on both sides — the established NaN
    route); callers keep any FURTHER comparison of their own verbatim.
    Pure; assumes float ndarrays (callers coerce).
    """
    r_ceiling, s_floor = _buffered_rails(R_val, S_val, atr_val)
    above_r = highs > r_ceiling
    below_s = lows < s_floor
    return above_r, below_s, r_ceiling, s_floor


def _engagement_hang_masks(above_r, below_s, highs, lows, closes,
                           r_ceiling, s_floor, atr_val):
    """The engagement form of Move 1 (operator ruling 2026-07-24): an outside
    bar HANGS on its rail — reads as respect — when its excursion beyond the
    buffered level stays within ``ENGAGEMENT_MAX_EXCURSION_ATR`` × ATR AND its
    close came back inside the buffered band (bar-basis primary; the close is
    supplementary evidence only). A close-out or a deeper excursion stays a
    full outside day — the upthrust defense. Returns ``(hang_r, hang_s)``
    masks (subsets of ``above_r`` / ``below_s``).

    Declared NaN/degenerate routes: a NaN close or NaN excursion compares
    False → the bar does NOT hang (stays outside — conservative); a NaN or
    zero ATR yields no hangs at all → identical to the flag-off read
    (fail-safe). ONE ATR basis: the same ``atr_val`` `_buffered_rails`
    consumed. Pure arithmetic on the already-loaded arrays — no second pass.
    """
    bound = settings.ENGAGEMENT_MAX_EXCURSION_ATR * atr_val
    hang_r = above_r & ((highs - r_ceiling) <= bound) & (closes <= r_ceiling)
    hang_s = below_s & ((s_floor - lows) <= bound) & (closes >= s_floor)
    return hang_r, hang_s


def _max_excursion_atr(above_r, below_s, highs, lows, r_ceiling, s_floor,
                       atr_val):
    """Deepest single-bar excursion beyond the buffered rails, in ATR — the
    Move 1 dark measure's yardstick. 0.0 when no bar is outside (a real
    measured value, never a NULL stand-in); None on a non-finite/zero ATR."""
    try:
        if atr_val is None or not np.isfinite(atr_val) or atr_val <= 0:
            return None
    except TypeError:
        return None
    over_r = np.where(above_r, highs - r_ceiling, 0.0)
    under_s = np.where(below_s, s_floor - lows, 0.0)
    worst = max(float(np.nanmax(over_r, initial=0.0)),
                float(np.nanmax(under_s, initial=0.0)))
    return worst / float(atr_val)


def _is_boundary_respected(highs, lows, R_val, S_val, atr_val):
    """
    Check if price action respects R/S boundaries using ATR-buffered zones.

    Uses the full daily range (highs vs R+buffer, lows vs S-buffer). Wicks
    that pierce the buffered zone count as breaches, matching the engine's
    "bars not candles" rule. An engagement-form ELECTION variant of this gate
    (bounded close-back-inside excursions re-read as hangs) was built and
    REJECTED 2026-07-24: the negative corpus admitted FLG+BBVA at every
    excursion bound >= 0.5 ATR while converting zero Guided List misses —
    this wick-basis read IS the junk defense. The engagement read survives as
    the archived MEASURE only (``_engagement_hang_masks`` via
    ``measure_gate_margins``); never re-wire it into the gate on anecdote.

    Returns:
        (respected, r_broken, s_broken, total_outside_days, respect_share)
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = len(highs)
    if n == 0:
        return False, False, False, 0, 0.0

    above_r, below_s, _r_ceiling, _s_floor = _rail_outside_masks(
        highs, lows, R_val, S_val, atr_val)
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

    return respected, r_broken, s_broken, total_outside, respect_pct


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
    if n == 0:
        return n
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    above, _below_s, _r_ceiling, s_floor = _rail_outside_masks(
        highs, lows, R_val, S_val, atr_val)
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


def _measure_close_residence(eq_df, R_val, S_val, atr_val, rail_touches=None):
    """Legacy close-residence occupancy for box-of-record selection.

    Public ``measure_dwell_balance`` now reports High/Low range occupancy for
    analysis, but selecting the parent box still uses closes as the residence
    concept. This preserves calibrated Phase-B rails while rail touches and
    boundary respect continue to use High/Low geometry.

    ``rail_touches`` optionally carries an already-computed
    ``_rail_touch_thirds`` result for this exact (window, rails, ATR) — the
    measurement-side caller (``measure_gate_margins``) shares it with its
    sibling reads; every election-side caller leaves it None.
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

    if rail_touches is None:
        rail_touches = _rail_touch_thirds(highs, lows, R_val, S_val, atr_val)
    r_mask, s_mask, r_touch_thirds, s_touch_thirds = rail_touches

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


def _dwell_bar_basis(eq_df, R_val, S_val):
    """The occupancy dwell trio measured BAR-AS-UNIT (operator ruling
    2026-07-25, third statement of the bar-as-unit doctrine): a bar whose Low
    reaches the lower box third has worked it, a bar whose High reaches the
    upper third has worked it, and a bar living entirely interior (touching
    neither end zone) is mid-RESIDENT churn. Same thirds, same window, same
    4dp rounding as the close-residence read it substitutes; positions are
    clipped so out-of-box extremes count toward the end they exceed (mirrors
    the close ``pos`` clip). NaN extremes compare False -> the bar lands in
    no bucket (the established NaN route on both bases).

    Returns ``(lower_dwell, mid_dwell, upper_dwell)`` fractions.
    """
    box = R_val - S_val
    lows = eq_df["Low"].values.astype(float)
    highs = eq_df["High"].values.astype(float)
    lo = np.clip((lows - S_val) / box, 0.0, 1.0)
    hi = np.clip((highs - S_val) / box, 0.0, 1.0)
    eng_l = lo <= 1.0 / 3.0
    eng_u = hi >= 2.0 / 3.0
    mid_res = (lo > 1.0 / 3.0) & (hi < 2.0 / 3.0)
    return (round(float(np.mean(eng_l)), 4),
            round(float(np.mean(mid_res)), 4),
            round(float(np.mean(eng_u)), 4))


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
    if settings.EQ_DWELL_BAR_BASIS:
        # The bar-as-unit basis switch (docs/bar_dwell_protocol_2026-07.md):
        # the judged dwell trio — and therefore the trace narration and every
        # downstream reader of this eq — becomes engagement/residency. The
        # gate-margin telemetry keeps its own close-basis call untouched.
        (eq["lower_dwell"], eq["mid_dwell"],
         eq["upper_dwell"]) = _dwell_bar_basis(eq_df, R_val, S_val)
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

    No-op unless ``enforce_traversal`` (the
    outer Phase-B path only — inner boxes are short and tight by design, where
    rail-to-rail traversal is naturally rare, so they are measured but never gated).
    """
    if not enforce_traversal:
        return valid_candidates

    # c[9]=cand_start, c[10]=judged-window length, c[1]=R_val, c[2]=S_val — measure
    # traversal on the SAME window the framing was respect/occupancy-validated over
    # (its trimmed worked cause when SOS-rescued; the full window when strict, where
    # c[10] spans to the edge so this is byte-identical to the legacy full slice).
    def _passes(c):
        trav = measure_equilibrium(eq_df.iloc[c[9]:c[9] + c[10]], c[1], c[2], atr_val)
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
