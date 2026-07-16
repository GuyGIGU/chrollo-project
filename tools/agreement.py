"""Pure agreement metrics + the closed outcome taxonomy (Task 8).

Grades ONE operator mark against ONE engine read — no file access, no
settings mutation, no rendering, no DataFrames: callers hand in dates and
floats only (bar anchors are df-positional and do not survive a frame shift;
the harness translates them first). Every graded mark resolves to EXACTLY ONE
outcome from the closed set, so a None from the engine or a missing field can
never leak into a mean or silently shrink a denominator.

Outcome precedence (documented and pinned): basis_mismatch (the data under
the mark moved — nothing else is meaningful) > edge_uncertain (the engine
cannot form a complete view at the asserted session: the drawn span's left
edge is off its 2y frame, or the eval prep refuses every candidate session)
> the verdict-specific outcomes.

Tolerances are INSTRUMENT parameters (scale-free: fractions of the drawn box
height, calendar-overlap fractions), passed in and stamped into every report
by the harness — never engine knobs, never firing decisions.

Known v1 limit (deliberate, logged): an "engine_wrong" mark carries no
geometry, so its replay can only ask "does the engine still elect HERE?" —
a rule variant that produces a different-but-correct read still grades
negative_violated. Capturing the engine-read snapshot at marking time
(Task 12's overlay) is the v2 that sharpens it.
"""
from __future__ import annotations

import math
from datetime import date

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

configure_path()

from engine_alpha.election_identity import DEFAULT_RAIL_TOL_BOX_FRAC, rails_match

OUTCOMES = ("match", "disagree", "engine_no_read", "edge_uncertain",
            "basis_mismatch", "negative_upheld", "negative_violated")

DEFAULT_SPAN_OVERLAP_MIN = 0.5   # calendar-Jaccard floor for "the same box span"


def ungraded(outcome: str, detail: str) -> dict:
    """A row for a mark that could not be scored (missing basis, refused
    prep). Routing these through the taxonomy keeps the closed set closed by
    construction — a typo'd literal fails HERE, not as a KeyError in tally."""
    if outcome not in OUTCOMES:
        raise ValueError(f"agreement: {outcome!r} is not in the closed outcome set")
    return {"outcome": outcome, "detail": detail}


def _d(value, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"agreement: {field} is not YYYY-MM-DD: {value!r}")


def span_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> float:
    """Calendar-day Jaccard of two date spans (deterministic, session-free)."""
    a0, a1 = _d(a_start, "a_start"), _d(a_end, "a_end")
    b0, b1 = _d(b_start, "b_start"), _d(b_end, "b_end")
    if a0 > a1 or b0 > b1:
        raise ValueError("agreement: inverted span")
    inter = (min(a1, b1) - max(a0, b0)).days + 1
    if inter <= 0:
        return 0.0
    union = (max(a1, b1) - min(a0, b0)).days + 1
    return inter / union


def rail_distances(mark_r: float, mark_s: float, read_r: float, read_s: float) -> dict:
    """Per-rail distances as fractions of the DRAWN box height (scale-free)."""
    values = (mark_r, mark_s, read_r, read_s)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError(f"agreement: non-finite rail in {values!r}")
    height = mark_r - mark_s
    if height <= 0:
        raise ValueError(f"agreement: drawn rails inverted ({mark_r}, {mark_s})")
    return {"r_frac": abs(mark_r - read_r) / height,
            "s_frac": abs(mark_s - read_s) / height}


def fired_inside_window(fire_date: str | None, knowable_from: str | None,
                        as_of: str) -> bool:
    """Hindsight marks never penalize the point-in-time read: a fire counts
    only from the session the mark declares fairly knowable (default: any
    fire at/before as-of)."""
    if fire_date is None:
        return False
    fired = _d(fire_date, "fire_date")
    lo = _d(knowable_from, "knowable_from") if knowable_from else date.min
    return lo <= fired <= _d(as_of, "as_of")


def grade_mark(mark: dict, read: dict | None, *,
               basis_ok: bool = True,
               frame_start: str | None = None,
               rail_tol_box_frac: float = DEFAULT_RAIL_TOL_BOX_FRAC,
               span_overlap_min: float = DEFAULT_SPAN_OVERLAP_MIN) -> dict:
    """One mark, one outcome (+ details).

    ``mark``: the model-shaped dict (verdict, rails, span dates, as_of_date).
    ``read``: the engine's date-keyed projection {"R","S","box_start_date",
    "box_end_date"} or None. ``basis_ok``: the caller's digest verification.
    ``frame_start``: the prepared frame's first session — a drawn span
    beginning before it is not a disagreement, the engine cannot see it.
    """
    verdict = mark["verdict"]
    if not basis_ok:
        return {"outcome": "basis_mismatch"}
    if (verdict == "box" and frame_start is not None
            and _d(mark["box_start_date"], "box_start_date") < _d(frame_start, "frame_start")):
        return {"outcome": "edge_uncertain",
                "detail": f"drawn span starts before the frame's left edge {frame_start}"}

    if verdict == "no_structure":
        return {"outcome": "negative_upheld" if read is None else "negative_violated"}
    if verdict == "engine_wrong":
        # v1 semantics — see the module docstring's known limit.
        return {"outcome": "negative_upheld" if read is None else "negative_violated"}

    # verdict == "box"
    if read is None:
        return {"outcome": "engine_no_read"}
    distances = rail_distances(mark["resistance"], mark["support"],
                               read["R"], read["S"])
    overlap = span_overlap(mark["box_start_date"], mark["box_end_date"],
                           read["box_start_date"], read["box_end_date"])
    agree_rails = rails_match(mark["resistance"], mark["support"],
                              read["R"], read["S"],
                              tol_box_frac=rail_tol_box_frac)
    outcome = "match" if (agree_rails and overlap >= span_overlap_min) else "disagree"
    return {"outcome": outcome, "rail_distances": distances,
            "span_overlap": round(overlap, 4), "rails_within_tol": agree_rails}


def tally(graded: list[dict]) -> dict:
    """Report cells for a batch: every outcome counted explicitly (a category
    with zero marks still appears — an unstated denominator makes two reports
    incomparable), plus the M each ratio is over."""
    counts = {o: 0 for o in OUTCOMES}
    for g in graded:
        counts[g["outcome"]] += 1  # KeyError on an unknown outcome = loud
    scored = counts["match"] + counts["disagree"] + counts["engine_no_read"]
    negatives = counts["negative_upheld"] + counts["negative_violated"]
    # The HEADLINE is concordance, not replication (operator doctrine,
    # 2026-07-11): "the engine reads a setup at my pick" — match OR disagree —
    # is what he calibrates toward; rail/span closeness is the diagnostic
    # tier that explains a divergence, never the pass bar. (Surfacing at
    # election is necessary, not sufficient, for popping up live — the
    # fired-in-window grade is the planned sharper criterion.)
    surfaced = counts["match"] + counts["disagree"]
    return {
        "counts": counts,
        "n_marks": len(graded),
        "n_scored_boxes": scored,
        "n_negatives": negatives,
        "surfaced_over_scored": (surfaced / scored) if scored else None,
        "match_over_scored": (counts["match"] / scored) if scored else None,
        "upheld_over_negatives": (counts["negative_upheld"] / negatives) if negatives else None,
        "n_excluded": counts["basis_mismatch"] + counts["edge_uncertain"],
    }
