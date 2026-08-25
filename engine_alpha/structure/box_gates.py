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

from typing import NamedTuple

import numpy as np

from config import settings
from engine_alpha.structure.box_trace import _trace_find
from engine_alpha.structure.metrics import _rail_touch_thirds, measure_equilibrium

__all__ = [
    "GateLeg",
    "GATE_LEGS",
    "GATE_LEG_INDEX",
    "leg_threshold",
    "_leg_record",
    "_buffered_rails",
    "_rail_outside_masks",
    "_engagement_hang_masks",
    "_max_excursion_atr",
    "_respect_stats",
    "_is_boundary_respected",
    "_worked_window_end",
    "_measure_close_residence",
    "_dwell_bar_basis",
    "_validate_base_quality",
    "_occupancy_leg_failures",
    "_occupancy_failures",
    "_apply_traversal_gate",
]


class GateLeg(NamedTuple):
    """One leg of the box-election validity judgment — the machine-readable
    vocabulary every narration/census/telemetry surface derives from
    (near-miss lane Task 1). The leg id is a cohort key downstream: renaming
    one is a re-measurement seam, never a cleanup."""
    leg: str          # canonical identifier (frozen wire vocabulary)
    stage: str        # the cascade stage that reports it
    stat: str         # the statistic the leg reads, in the gate's own terms
    setting: str      # settings attribute bound as the threshold (read lazily,
                      # AP-3); "" = caller-bound (the window floor arrives as an
                      # argument: INNER_MIN_DAYS inner, pre-gated by
                      # MIN_BASE_DAYS at the outer consultation seam)
    quantum: str      # native unit: fraction | bars | touches | thirds |
                      # traversals | ratio | price_ratio
    op: str           # exact PASS comparison: measured <op> threshold


# Finest-grain leg taxonomy (15). The band pool judges the width leg against
# BAND_MAX_BOX_WIDTH (the deep-event class allowance) — the registry binds the
# default law; a stage-local override is context, not a second leg.
GATE_LEGS = (
    GateLeg("width", "width", "box_width", "MAX_BOX_WIDTH", "fraction", "<="),
    GateLeg("window", "window", "judged_window_bars", "", "bars", ">="),
    GateLeg("respect_share", "respect", "respect_share",
            "MIN_BOUNDARY_RESPECT_PCT", "fraction", ">="),
    GateLeg("respect_run", "respect", "max_consecutive_outside",
            "MAX_CONSECUTIVE_OUTSIDE_DAYS", "bars", "<="),
    GateLeg("crash", "occupancy", "min_low_over_s", "CRASH_FILTER_MULT",
            "price_ratio", ">="),
    GateLeg("r_touches", "occupancy", "r_touches", "EQ_MIN_TOUCHES_PER_RAIL",
            "touches", ">="),
    GateLeg("s_touches", "occupancy", "s_touches", "EQ_MIN_TOUCHES_PER_RAIL",
            "touches", ">="),
    GateLeg("r_touch_thirds", "occupancy", "r_touch_thirds",
            "EQ_MIN_TOUCH_THIRDS", "thirds", ">="),
    GateLeg("s_touch_thirds", "occupancy", "s_touch_thirds",
            "EQ_MIN_TOUCH_THIRDS", "thirds", ">="),
    GateLeg("lower_dwell", "occupancy", "lower_dwell", "EQ_MIN_HALF_DWELL",
            "fraction", ">="),
    GateLeg("upper_dwell", "occupancy", "upper_dwell", "EQ_MIN_HALF_DWELL",
            "fraction", ">="),
    GateLeg("mid_dwell", "occupancy", "mid_dwell", "EQ_MAX_MID_DWELL",
            "fraction", "<="),
    GateLeg("coverage", "occupancy", "coverage", "EQ_MIN_COVERAGE",
            "fraction", ">="),
    GateLeg("traversal_count", "traversal", "n_full_traversals",
            "TRAVERSAL_MIN", "traversals", ">="),
    GateLeg("traversal_density", "traversal", "full_per_swing",
            "TRAVERSAL_MIN_DENSITY", "ratio", ">="),
)

GATE_LEG_INDEX = {spec.leg: spec for spec in GATE_LEGS}


def leg_threshold(leg: str):
    """The leg's live threshold, read lazily from settings (AP-3). Raises on
    a caller-bound leg (``window``) — its floor arrives as an argument."""
    spec = GATE_LEG_INDEX[leg]
    if not spec.setting:
        raise ValueError(f"leg {leg!r} is caller-bound; no settings threshold")
    return getattr(settings, spec.setting)


def _leg_record(leg, measured, threshold, **extras):
    """One structured seam entry: leg id + the measured statistic + the
    threshold as NUMBERS (the sentence beside it is derived from the same
    values — prose can never be the only carrier again). ``measured`` may be
    None when the gate does not have the number in hand at the kill site
    (crash's min-low ratio, respect's run maximum) — the lane's post-hoc
    completion primitive fills those, never a re-parse of prose. ``extras``
    carry the native-quantum numerators a sentence needs (outside, n)."""
    if leg not in GATE_LEG_INDEX:
        raise ValueError(f"unknown gate leg {leg!r}")
    rec = {"leg": leg, "measured": measured, "threshold": threshold}
    rec.update(extras)
    return rec


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


def _respect_stats(highs, lows, R_val, S_val, atr_val):
    """The respect gate's full statistics in ONE pass — the legacy verdict
    tuple plus the consecutive-run maxima it always computed and used to
    discard (near-miss lane Task 3: the run maximum is the respect_run leg's
    measured statistic; margin telemetry reads it from here instead of a
    second O(n) pass).

    Returns:
        (respected, r_broken, s_broken, total_outside_days, respect_share,
         max_consec, r_consec_max, s_consec_max)
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = len(highs)
    if n == 0:
        return False, False, False, 0, 0.0, 0, 0, 0

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

    return (respected, r_broken, s_broken, total_outside, respect_pct,
            max_consec, r_consec_max, s_consec_max)


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
    return _respect_stats(highs, lows, R_val, S_val, atr_val)[:5]


def _worked_window_end(highs, lows, R_val, S_val, atr_val):
    """Index where the worked range ends, trimming a trailing SOS breakout tail.

    A range whose right side has already broken out above R and HELD above
    support — a break above R then a rest back on it (SOS -> LPS above R) — should be validated over
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
        "n": 0, "lower_count": 0, "mid_count": 0, "upper_count": 0,
        "coverage_bins": 0, "coverage_occupied": 0,
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

    # Counts are the ground truth; the judged fractions derive from them
    # (count/n is the identical float64 np.mean produced — byte-parity), so
    # margin telemetry reads raw integer numerators, never a re-derivation
    # from the 4dp-rounded fractions (near-miss lane Task 3).
    pos = np.clip((closes - S_val) / box, 0.0, 1.0)
    lower_count = int(np.sum(pos <= 1.0 / 3.0))
    mid_count = int(np.sum((pos > 1.0 / 3.0) & (pos < 2.0 / 3.0)))
    upper_count = int(np.sum(pos >= 2.0 / 3.0))
    lower_dwell = lower_count / n
    mid_dwell = mid_count / n
    upper_dwell = upper_count / n

    nb = settings.EQ_COVERAGE_BINS
    # A NaN close lands in NO coverage bin — the dwell counts' own NaN route
    # (comparisons are False). Unmasked, NaN survives np.clip, the int cast
    # turns it into a large negative index, and np.bincount raises.
    finite_pos = pos[np.isfinite(pos)]
    bins = np.minimum((finite_pos * nb).astype(int), nb - 1)
    counts = np.bincount(bins, minlength=nb)
    min_count = max(1.0, settings.EQ_COVERAGE_MIN_FRAC * n)
    occupied = int(np.sum(counts >= min_count))
    coverage = occupied / nb

    return {
        "r_touches": int(r_mask.sum()),
        "s_touches": int(s_mask.sum()),
        "r_touch_thirds": int(r_touch_thirds),
        "s_touch_thirds": int(s_touch_thirds),
        "lower_dwell": round(lower_dwell, 4),
        "mid_dwell": round(mid_dwell, 4),
        "upper_dwell": round(upper_dwell, 4),
        "coverage": round(coverage, 4),
        "n": n,
        "lower_count": lower_count,
        "mid_count": mid_count,
        "upper_count": upper_count,
        "coverage_bins": int(nb),
        "coverage_occupied": occupied,
    }


def _dwell_bar_basis(eq_df, R_val, S_val):
    """The occupancy dwell trio measured BAR-AS-UNIT (operator ruling
    2026-07-25, third statement of the bar-as-unit doctrine): a bar whose Low
    reaches the lower box third has worked it, a bar whose High reaches the
    upper third has worked it, and a bar living entirely interior (touching
    neither end zone) is mid-RESIDENT churn. Same thirds, same window, same
    4dp rounding as the close-residence read; positions are clipped so
    out-of-box extremes count toward the end they exceed (mirrors the close
    ``pos`` clip). NaN extremes compare False -> the bar lands in no bucket.

    MEASURE-ONLY. A GATE form of this read (EQ_DWELL_BAR_BASIS swapping the
    judged trio) was built and REJECTED 2026-07-25 by the sealed fire A/B
    (docs/bar_dwell_protocol_2026-07.md §8): it converts EGBN at the
    operator's exact rails, but 10/26 hit elections break (MATX lost, five
    displaced winners) and junk DGII+FLG fire — close residence is
    load-bearing for ELECTION STABILITY. Never re-wire this into the gate.

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


def _occupancy_leg_failures(eq, r_touches, s_touches):
    """Structured occupancy-family failures: ``(leg_record, sentence)`` per
    failing check, thresholds resolved through the leg registry and the
    sentence derived from the same numbers the record carries (byte-identical
    to the legacy ``_occupancy_failures`` prose)."""
    touches_min = leg_threshold("r_touches")
    thirds_min = leg_threshold("r_touch_thirds")
    dwell_min = leg_threshold("lower_dwell")
    mid_max = leg_threshold("mid_dwell")
    cov_min = leg_threshold("coverage")
    checks = [
        ("r_touches", r_touches, touches_min, r_touches < touches_min,
         f"r_touches {r_touches}<{touches_min}"),
        ("s_touches", s_touches, touches_min, s_touches < touches_min,
         f"s_touches {s_touches}<{touches_min}"),
        ("r_touch_thirds", eq["r_touch_thirds"], thirds_min,
         eq["r_touch_thirds"] < thirds_min,
         f"r_touch_thirds {eq['r_touch_thirds']}<{thirds_min} (clustered)"),
        ("s_touch_thirds", eq["s_touch_thirds"], thirds_min,
         eq["s_touch_thirds"] < thirds_min,
         f"s_touch_thirds {eq['s_touch_thirds']}<{thirds_min} (clustered)"),
        ("lower_dwell", eq["lower_dwell"], dwell_min,
         eq["lower_dwell"] < dwell_min,
         f"dead space low (lower_dwell {eq['lower_dwell']}<{dwell_min})"),
        ("upper_dwell", eq["upper_dwell"], dwell_min,
         eq["upper_dwell"] < dwell_min,
         f"dead space high (upper_dwell {eq['upper_dwell']}<{dwell_min})"),
        ("mid_dwell", eq["mid_dwell"], mid_max, eq["mid_dwell"] > mid_max,
         f"mid churn (mid_dwell {eq['mid_dwell']}>{mid_max})"),
        ("coverage", eq["coverage"], cov_min, eq["coverage"] < cov_min,
         f"coverage {eq['coverage']}<{cov_min}"),
    ]
    return [(_leg_record(leg, measured, threshold), msg)
            for leg, measured, threshold, failed, msg in checks if failed]


def _occupancy_failures(eq, r_touches, s_touches):
    """Trace-only: name the worked-equilibrium occupancy checks a framing failed."""
    return [msg for _rec, msg in _occupancy_leg_failures(eq, r_touches, s_touches)]


def _apply_traversal_gate(eq_df, valid_candidates, atr_val, enforce_traversal,
                          trace=None, recorder=None):
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
    # BAND candidates are the third basis: c[10] is the excision-mask COUNT, so
    # the slice is contiguous from cand_start, ends short of the right edge by
    # the excised-bar count, and includes excised bars respect/occupancy never
    # judged — the ratified contiguous law (review 2026-07-26 finding 4; the
    # basis-drift counter in gate_margins/near_miss exists because the bases
    # differ). "Fixing" band toward the masked window would silently move
    # elections.
    def _passes(c):
        trav = measure_equilibrium(eq_df.iloc[c[9]:c[9] + c[10]], c[1], c[2], atr_val)
        nf, ns = trav["n_full_traversals"], trav["n_swings"]
        ok = (nf >= settings.TRAVERSAL_MIN
              and ns > 0 and nf / ns >= settings.TRAVERSAL_MIN_DENSITY)
        if not ok and recorder is not None:
            leg = ("traversal_count" if nf < settings.TRAVERSAL_MIN
                   else "traversal_density")
            recorder.refusal(leg, c[11], c[7], c[8], c[9], c[1], c[2], c[10],
                             nf, ns)
        if trace is not None:
            rec = _trace_find(trace, c)
            if rec is not None:
                density = (nf / ns) if ns > 0 else 0.0
                rec["traversal"] = {"full": int(nf), "swings": int(ns),
                                    "density": round(density, 3)}
                if not ok:
                    count_min = leg_threshold("traversal_count")
                    density_min = leg_threshold("traversal_density")
                    legs = []
                    if nf < count_min:
                        legs.append(_leg_record("traversal_count", int(nf),
                                                count_min, swings=int(ns)))
                    if not (ns > 0 and density >= density_min):
                        legs.append(_leg_record("traversal_density",
                                                float(density), density_min,
                                                full=int(nf), swings=int(ns)))
                    rec["verdict"] = "rejected"
                    rec["stage"] = "traversal"
                    rec["legs"] = legs
                    rec["detail"] = (
                        f"full={nf} density={density:.3f} (floors "
                        f"{count_min}/{density_min})")
        return ok

    return [c for c in valid_candidates if _passes(c)]
