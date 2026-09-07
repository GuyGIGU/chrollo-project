"""Per-leg gate margins in native quanta (near-miss lane Task 3).

The measurement core the refusal-telemetry lane is built on: for each leg in
``box_gates.GATE_LEGS``, a SIGNED margin in the leg's own quantum (bars,
touches, thirds, bins, traversals; fractions/ratios only where the gate
itself judges a float), computed from RAW integer numerators at measurement
time — never re-derived from the 4dp-rounded fractions the gate reports, and
never parsed from prose.

Sign convention: ``margin >= 0`` means the leg PASSES; negative is the
deficit. Every margin self-checks that its sign reproduces the gate's actual
verdict on the same window — a mismatch raises (voids loudly, the rail
program's pattern generalized): a margin that disagrees with the gate is
measurement drift, not a shrug. The known tripwire is the 4dp quantization
edge (the gate judges ``round(count/n, 4)`` while the count math judges the
raw count); when it ever fires on real data, that is a finding for the
ruling record, never something to paper over.

The cascade short-circuits, so "which legs failed" is unknowable at a kill
site — ``complete_leg_vector`` is the post-hoc FULL-VECTOR completion that
runs the gates' own pure helpers over a given judged window (the
``gate_stats`` pattern, engine-side). The judged basis is NOT derivable from
the framing alone (strict judges the full candidate window, rescued the
SOS-trimmed cause, band the excision-masked bars under its own width cap
with traversal on the contiguous slice) — the recorder's ``Refusal`` tuple
carries the coordinates and the deferred caller threads the electing pool's
own laws in via ``width_max``/``traversal_df`` (review 2026-07-26 finding 4).

MEASURE-ONLY: nothing here gates, scores, or moves a rail. No live path
imports this module; the lane's collector (flag-gated) and the census
instruments are its only consumers.
"""
from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

from config import settings
from engine_alpha.structure.box_gates import (
    _measure_close_residence,
    _respect_stats,
    leg_threshold,
)
from engine_alpha.structure.metrics import measure_equilibrium

__all__ = [
    "NEAR_MISS_RULESET",
    "OCCUPANCY_FAMILY",
    "count_needed",
    "count_allowed",
    "outside_allowed",
    "complete_leg_vector",
    "coarse_failing_legs",
    "ruled_near_miss",
]

_EPS = 1e-9


# --- the count math: fraction thresholds as integer quanta (ONE home) -------

def count_needed(floor_frac: float, n: int) -> int:
    """Units required to pass a ``>=`` fraction floor over ``n`` units:
    measured/n >= floor  <=>  measured >= ceil(floor*n)."""
    return math.ceil(floor_frac * n - _EPS)


def count_allowed(cap_frac: float, n: int) -> int:
    """Units allowed under a ``<=`` fraction cap over ``n`` units:
    measured/n <= cap  <=>  measured <= floor(cap*n)."""
    return math.floor(cap_frac * n + _EPS)


def outside_allowed(rate: float, n: int) -> int:
    """Outside bars allowed by the respect share: 1 - outside/n >= rate
    <=> outside <= floor((1-rate)*n)."""
    return math.floor((1.0 - rate) * n + _EPS)


# --- the full-vector completion ---------------------------------------------

def _leg_row(leg, measured, threshold, margin, passed):
    if (margin >= 0) != bool(passed):
        raise ValueError(
            f"gate_margins self-check: margin sign contradicts the gate "
            f"verdict on leg {leg!r} (measured={measured!r}, "
            f"threshold={threshold!r}, margin={margin!r}, passed={passed}) — "
            f"measurement drift; this vector is VOID")
    return {"leg": leg, "measured": measured, "threshold": threshold,
            "margin": margin, "passed": bool(passed)}


def complete_leg_vector(judged_df, R, S, atr_val, *, min_candidate_days=None,
                        width_max=None, traversal_df=None, judged_mask=None):
    """The complete signed-margin vector over ONE judged window, through the
    gates' own helpers. Returns ``{leg: row}`` with every consulted leg's
    measured statistic, threshold, native-quantum margin, and pass verdict —
    or ``None`` on a degenerate basis (empty window, inverted rails, unusable
    ATR: mirror of ``measure_gate_margins``'s refusal contract).

    The ``window`` leg is included only when ``min_candidate_days`` is given
    (its floor is caller-bound: INNER_MIN_DAYS inner, pre-gated by
    MIN_BASE_DAYS at the outer consultation seam — passing None means the
    floor was not consulted for this window).

    The electing pool's own laws thread in explicitly (review 2026-07-26
    finding 4): ``width_max`` overrides the strict cap (band candidates
    legally measure up to BAND_MAX_BOX_WIDTH — judging them by the strict
    law manufactures a phantom failing leg), and ``traversal_df`` overrides
    the traversal pair's window (the live band gate judges traversal on the
    CONTIGUOUS slice, not the masked build window). ``judged_mask`` carries the
    band pool's excision mask so the touch-THIRDS leg is cut on the original
    span, mirroring the gate's own read of it rather than the compacted
    array's (council review 2026-09-07, finding 6); the respect-run leg needs
    no mask because the gate itself counts that run on the compacted array
    (``box_gates._respect_stats`` carries the reasoning and the measurement).
    Defaults reproduce the strict law on ``judged_df`` byte-identically.
    """
    if (judged_df is None or len(judged_df) == 0 or R is None or S is None
            or R <= S or S <= 0 or atr_val is None or atr_val <= 0
            or not np.isfinite(atr_val)):
        return None

    highs = judged_df["High"].to_numpy(dtype=float)
    lows = judged_df["Low"].to_numpy(dtype=float)
    n = len(judged_df)
    rows: dict[str, dict] = {}

    # width — the gate compares the raw ratio to the electing pool's cap.
    box_width = (R - S) / S
    width_max = (leg_threshold("width") if width_max is None
                 else float(width_max))
    rows["width"] = _leg_row("width", float(box_width), float(width_max),
                             float(width_max - box_width),
                             not (box_width > width_max))

    if min_candidate_days is not None:
        rows["window"] = _leg_row("window", n, int(min_candidate_days),
                                  n - int(min_candidate_days),
                                  not (n < min_candidate_days))

    # respect — share margin in OUTSIDE BARS (the native numerator), run
    # margin in bars, both from the gate's single pass.
    (_respected, _rb, _sb, total_outside, share,
     max_consec, _rmax, _smax) = _respect_stats(highs, lows, R, S, atr_val)
    share_min = leg_threshold("respect_share")
    rows["respect_share"] = _leg_row(
        "respect_share", int(total_outside),
        outside_allowed(share_min, n),
        outside_allowed(share_min, n) - int(total_outside),
        share >= share_min)
    run_max = leg_threshold("respect_run")
    rows["respect_run"] = _leg_row("respect_run", int(max_consec), int(run_max),
                                   int(run_max) - int(max_consec),
                                   not (max_consec > run_max))

    # crash — the gate's exact comparison is min(Low) < S * mult. Margin and
    # verdict derive from the SAME subtraction (min_low - S*mult, sign
    # preserved by the positive-S division) so an ulp at the threshold can
    # never split them and trip the self-check on legitimate data — the one
    # leg where the two forms could diverge (review 2026-07-26 finding 2).
    # nanmin, NOT min: the live gate reads the pandas skipna min, and a
    # plain np.min would NaN-poison this mirror where the gate skips.
    crash_mult = leg_threshold("crash")
    min_low = float(np.nanmin(lows))
    crash_gap = min_low - S * float(crash_mult)
    rows["crash"] = _leg_row("crash", min_low / S, float(crash_mult),
                             crash_gap / S,
                             not (min_low < S * crash_mult))

    # occupancy family — integer numerators from the gate's own read.
    eq = _measure_close_residence(judged_df, R, S, atr_val,
                                  judged_mask=judged_mask)
    touches_min = leg_threshold("r_touches")
    thirds_min = leg_threshold("r_touch_thirds")
    for leg, count in (("r_touches", eq["r_touches"]),
                       ("s_touches", eq["s_touches"])):
        rows[leg] = _leg_row(leg, int(count), int(touches_min),
                             int(count) - int(touches_min),
                             count >= touches_min)
    for leg, count in (("r_touch_thirds", eq["r_touch_thirds"]),
                       ("s_touch_thirds", eq["s_touch_thirds"])):
        rows[leg] = _leg_row(leg, int(count), int(thirds_min),
                             int(count) - int(thirds_min),
                             count >= thirds_min)
    dwell_min = leg_threshold("lower_dwell")
    for leg, count, frac in (("lower_dwell", eq["lower_count"], eq["lower_dwell"]),
                             ("upper_dwell", eq["upper_count"], eq["upper_dwell"])):
        rows[leg] = _leg_row(leg, int(count), count_needed(dwell_min, n),
                             int(count) - count_needed(dwell_min, n),
                             frac >= dwell_min)
    mid_max = leg_threshold("mid_dwell")
    rows["mid_dwell"] = _leg_row(
        "mid_dwell", int(eq["mid_count"]), count_allowed(mid_max, n),
        count_allowed(mid_max, n) - int(eq["mid_count"]),
        not (eq["mid_dwell"] > mid_max))
    cov_min = leg_threshold("coverage")
    nb = int(eq["coverage_bins"])
    rows["coverage"] = _leg_row(
        "coverage", int(eq["coverage_occupied"]), count_needed(cov_min, nb),
        int(eq["coverage_occupied"]) - count_needed(cov_min, nb),
        eq["coverage"] >= cov_min)

    # traversal — the pool-aware gate's two floors, on the window form the
    # live gate actually judges (contiguous for band; the judged window
    # itself for strict/rescued, where the two coincide).
    trav = measure_equilibrium(
        judged_df if traversal_df is None else traversal_df, R, S, atr_val)
    nf, ns = int(trav["n_full_traversals"]), int(trav["n_swings"])
    count_min = leg_threshold("traversal_count")
    rows["traversal_count"] = _leg_row("traversal_count", nf, int(count_min),
                                       nf - int(count_min), nf >= count_min)
    density_min = leg_threshold("traversal_density")
    density = (nf / ns) if ns > 0 else 0.0
    rows["traversal_density"] = _leg_row(
        "traversal_density", float(density), float(density_min),
        float(density - density_min),
        ns > 0 and density >= density_min)

    return rows


# --- the operator-RULED near-miss form (Task 6 ruling, 2026-07-26) -----------
# THE one implementation of the ruled judgment (EC-18): every consumer (the
# lane collector, the census, the review report) DELEGATES here or pins
# equivalence in its check battery — never a re-typed twin. A re-ruling edits
# THIS function + the NEAR_MISS_* settings (manifest-listed: the rotation is
# the new lane seam) and re-runs the census; ruling record:
# docs/near_miss_lane_2026-07.md §5.

NEAR_MISS_RULESET = "2026-07-26.A"

OCCUPANCY_FAMILY = ("r_touches", "s_touches", "r_touch_thirds",
                    "s_touch_thirds", "lower_dwell", "upper_dwell",
                    "mid_dwell", "coverage")

_FLOAT_DEFICIT_SETTINGS = {
    "width": "NEAR_MISS_WIDTH_DEFICIT_MAX",
    "crash": "NEAR_MISS_CRASH_DEFICIT_MAX",
    "traversal_density": "NEAR_MISS_DENSITY_DEFICIT_MAX",
}


def coarse_failing_legs(vector) -> list:
    """The failing set at the RULED taxonomy (T-COARSE-8): the eight
    occupancy checks collapse to ONE concept; width / window / the respect
    pair / crash / the traversal pair stay themselves. Order follows the
    vector's own leg order with `occupancy` appended last when any family
    member fails."""
    out, occ = [], False
    for leg, row in vector.items():
        if row["passed"]:
            continue
        if leg in OCCUPANCY_FAMILY:
            occ = True
        else:
            out.append(leg)
    if occ:
        out.append("occupancy")
    return out


def ruled_near_miss(vector) -> bool:
    """The RULED one-leg-narrow predicate over one complete leg vector:
    exactly ONE coarse leg fails, and every failing fine leg is NARROW —
    integer-quantum margins within NEAR_MISS_MAX_QUANTA, float-quantum legs
    (width / crash / traversal_density) within their junk-calibrated decile
    deficits. Crash is IN as its own leg. A vector that passes everything is
    not a near-miss (it is a refusal of some later stage, not of these
    gates)."""
    if vector is None or len(coarse_failing_legs(vector)) != 1:
        return False
    max_quanta = settings.NEAR_MISS_MAX_QUANTA
    for leg, row in vector.items():
        if row["passed"]:
            continue
        margin = row["margin"]
        setting = _FLOAT_DEFICIT_SETTINGS.get(leg)
        if setting is not None:
            if -margin > getattr(settings, setting):
                return False
        elif margin < -max_quanta:
            return False
    return True
