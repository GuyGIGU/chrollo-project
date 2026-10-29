"""The technical grade's trait table: measured facts in, the order within the letter out.

The letter is the integrity grade's (his dead space and whether the base held, `engine_alpha/two_eyes/grade.py`):
his sealed 40 keep their letters (his ruling 3, Thu 29/10/2026). WITHIN the letter his traits order the setups
(his words, Sat 18/10/2026 and Thu 29/10/2026): a tight box, clean swings, right-side contraction, no dead space,
rails the turns sit on, and the stock's stage on its weekly chart. Each trait is a 0..1 fraction of like
quantities in a named unit, weighted by `two_eyes_numbers.TRAIT_WEIGHTS`; the score runs from the letter's floor
to its ceiling by the weighted fractions, so an S with every trait full reads 100 and a wide, choppy S reads 75.
A trait that is not measured leaves the budget. Scoring judges; it reads no chart.
"""
from __future__ import annotations

from dataclasses import replace
import math

from config import settings
from engine_alpha import two_eyes_numbers as M


def _fraction(value):
    return None if value is None or not math.isfinite(value) else min(1.0, max(0.0, value))


def _line(value, full: float, zero: float):
    """A straight line from full marks at ``full`` to none at ``zero`` (either way round), None when unmeasured."""
    if value is None or not math.isfinite(value) or full == zero:
        return None
    return _fraction((zero - value) / (zero - full))


def trait_rows(integrity, facts: dict, stage=None) -> list:
    """Every trait as a row: key, label, fraction (None when not measured), points, max points, explanation."""
    height = facts.get("height_in_ranges")
    share = facts.get("main_swing_share")
    error = facts.get("rail_alignment_error")
    ratio = facts.get("contraction")
    base = integrity.base_days or 0
    empty_share = None if base <= 0 else integrity.empty_days / base
    stage_fraction = None if stage is None else M.TRAIT_STAGE_FRACTION.get(int(stage))
    rows = [
        ("tightness", "Tight box", _line(height, M.TRAIT_TIGHT_FULL_RANGES, M.TRAIT_TIGHT_ZERO_RANGES),
         "the box's height in its own daily ranges is not measured" if height is None else
         f"{height:.1f} of its own daily ranges tall; full marks at {M.TRAIT_TIGHT_FULL_RANGES:.1f}, none at "
         f"{M.TRAIT_TIGHT_ZERO_RANGES:.1f}"),
        ("swings", "Clean swings", None if share is None else _fraction(share / settings.CLARITY_SWING_FULL_SHARE),
         "no completed main swing yet" if share is None else
         f"{share:.0%} of the line's travel is the main zigzag; full marks at {settings.CLARITY_SWING_FULL_SHARE:.0%}"),
        ("dead_space", "No dead space", _line(empty_share, 0.0, M.GRADE_EMPTY_ZERO),
         "the base has no days yet" if empty_share is None else
         f"{integrity.empty_days} of {base} base days empty, the bars off the box; none at half the base"),
        ("contraction", "Right-side contraction",
         _line(ratio, M.TRAIT_CONTRACTION_FULL_RATIO, M.TRAIT_CONTRACTION_ZERO_RATIO),
         "the base is too short to compare its right side with its start" if ratio is None else
         f"the last third's daily ranges are {ratio:.0%} of the earlier ones; full marks at "
         f"{M.TRAIT_CONTRACTION_FULL_RATIO:.0%}, none at {M.TRAIT_CONTRACTION_ZERO_RATIO:.0%}"),
        ("rails", "Rails the turns sit on",
         _line(error, settings.CLARITY_RAIL_FULL_ERROR, settings.CLARITY_RAIL_ZERO_ERROR),
         "not enough opposing major turns to measure" if error is None else
         f"the major turns average {error:.2f} box heights from their rail; named spring and upthrust turns keep "
         "their context"),
        ("stage", "Weekly stage", stage_fraction,
         "the weekly stage is not read" if stage is None else
         f"stage {int(stage)} on the weekly chart; stage 2, the advance, earns full marks"),
    ]
    out = []
    for key, label, fraction, explanation in rows:
        weight = float(M.TRAIT_WEIGHTS[key])
        out.append({"key": key, "label": label, "fraction": fraction,
                    "points": None if fraction is None else round(weight * fraction, 2),
                    "max_points": weight, "explanation": explanation})
    return out


def compose_grade(integrity, facts: dict, stage=None):
    """The letter is the integrity grade's; the traits place the score inside the letter's band.

    A base that did not hold stays at 0. With no measured trait the integrity score stands.
    """
    from engine_alpha.two_eyes.grade import whole_points

    components = trait_rows(integrity, facts, stage)
    budget = sum(c["max_points"] for c in components if c["fraction"] is not None)
    raw = sum(c["max_points"] * c["fraction"] for c in components if c["fraction"] is not None)
    traits = None if budget <= 0 else raw / budget
    floor, width = M.TRAIT_BANDS[integrity.letter]
    if not integrity.holds or integrity.score <= 0 or traits is None:
        score = integrity.score
    else:
        score = whole_points(floor + width * traits)
    said = "not measured" if traits is None else f"{100 * traits:.0f}/100"
    detail = {"method": "traits-v1", "integrity_score": integrity.score,
              "trait_score": None if traits is None else round(100.0 * traits, 1),
              "available_points": budget, "components": components, "facts": facts,
              "summary": f"{integrity.letter}: the letter from the dead space and the hold; traits {said} place it "
                         f"in the letter · base {integrity.score:.0f}/100"}
    return replace(integrity, score=score, letter=integrity.letter, clarity=detail)
