"""Experimental technical clarity grade: measured facts in, points out."""
from __future__ import annotations

from dataclasses import replace
import math

from config import settings


def compose_grade(integrity, facts: dict):
    """Award clarity points; the existing integrity grade remains the ceiling.

    Unmeasured components are excluded from the available budget, not treated as
    observed failures. With no measured clarity, retain the integrity grade.
    """
    from engine_alpha.two_eyes.grade import letter, whole_points

    share, error = facts["main_swing_share"], facts["rail_alignment_error"]
    swing_fraction = None if share is None else share / settings.CLARITY_SWING_FULL_SHARE
    rail_fraction = None if error is None else (
        settings.CLARITY_RAIL_ZERO_ERROR - error
    ) / (settings.CLARITY_RAIL_ZERO_ERROR - settings.CLARITY_RAIL_FULL_ERROR)
    components = []
    for key, label, weight, value in (
        ("swings", "Main zigzag", settings.SCORE_CLARITY_SWINGS, swing_fraction),
        ("rails", "Rail definition", settings.SCORE_CLARITY_RAILS, rail_fraction),
    ):
        fraction = None if value is None or not math.isfinite(value) else min(1.0, max(0.0, value))
        components.append({"key": key, "label": label, "fraction": fraction,
                           "points": None if fraction is None else round(weight * fraction, 2),
                           "max_points": weight})
    components[0]["explanation"] = ("No completed main swing yet" if share is None else
        f"{share:.0%} of measured travel belongs to the main zigzag; full credit at the reference benchmark of {settings.CLARITY_SWING_FULL_SHARE:.0%}")
    components[1]["explanation"] = ("Not enough opposing major turns to measure rail definition" if error is None else
        f"Major turns average {error:.2f} box heights from their rail; named spring/upthrust excursions keep their context")
    budget = sum(c["max_points"] for c in components if c["points"] is not None)
    raw = sum(c["max_points"] * c["fraction"] for c in components if c["points"] is not None)
    clarity_score = 100.0 * raw / budget if budget else None
    score = integrity.score if clarity_score is None else whole_points(min(integrity.score, clarity_score))
    detail = {"method": "clarity-v1", "experimental": True,
              "integrity_score": integrity.score, "clarity_score": clarity_score,
              "available_points": budget, "components": components, "facts": facts}
    detail["summary"] = ("Experimental clarity · main zigzag and rail definition · "
                         f"base integrity {integrity.score:.0f}/100")
    if clarity_score is None:
        detail["summary"] = f"Clarity not yet measured · base integrity {integrity.score:.0f}/100 retained"
    return replace(integrity, score=score, letter=letter(score), clarity=detail)
