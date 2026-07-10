"""Cross-frame election identity (Calibration at Scale, Task 8).

Are two elected structures THE SAME reading? Both the agreement harness
(engine-vs-operator, tools/agreement.py) and the stability grade
(election-at-D vs election-at-D-j, Task 14) need this one predicate — two
definitions would let an epsilon wobble count as flicker in one place and
as persistence in the other.

Determinism convention (specs/event-map-causality-contract.md): identity
settles on CALENDAR DATES and integer/categorical keys — never df-positional
bar indices (two frames of different trim start make positions
incomparable) — and floats compare only within an explicit tolerance in
scale-free units (fractions of the box height), never absolute dollars and
never exact equality.
"""
from __future__ import annotations

import math

# Rails within this fraction of the (reference) box height are the same rail.
# An instrument default, stamped into every report that uses it — not an
# engine knob and never a firing decision.
DEFAULT_RAIL_TOL_BOX_FRAC = 0.10


def rails_match(r_a: float, s_a: float, r_b: float, s_b: float,
                *, tol_box_frac: float = DEFAULT_RAIL_TOL_BOX_FRAC) -> bool:
    """True when both rails agree within ``tol_box_frac`` of the FIRST pair's
    box height (the reference reading). Non-finite inputs are a programmer
    error — loud, never a silent False that skews a denominator."""
    values = (r_a, s_a, r_b, s_b)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError(f"rails_match: non-finite rail in {values!r}")
    height = r_a - s_a
    if height <= 0:
        raise ValueError(f"rails_match: reference rails inverted ({r_a}, {s_a})")
    tol = tol_box_frac * height
    return abs(r_a - r_b) <= tol and abs(s_a - s_b) <= tol


def same_election(read_a: dict, read_b: dict,
                  *, tol_box_frac: float = DEFAULT_RAIL_TOL_BOX_FRAC) -> bool:
    """One reading, seen from two frames? ``read_*`` are date-keyed
    projections: {"R": float, "S": float, "box_start_date": "YYYY-MM-DD"}.
    Callers translate bar anchors to dates BEFORE calling (positions do not
    survive a frame shift); the box-start date is an exact categorical key.
    """
    if read_a.get("box_start_date") != read_b.get("box_start_date"):
        return False
    return rails_match(read_a["R"], read_a["S"], read_b["R"], read_b["S"],
                       tol_box_frac=tol_box_frac)
