"""Stage 7, the grade: the letter from his dead space and whether the base held (integrity), the clarity facts
(clean swings, rails, right-side contraction) and the traits that place the score within the letter.
"""
from __future__ import annotations

import numpy as np
from engine_alpha import numbers as M
from engine_alpha.record import LAST_SUPPER, SOS, SPRING, SPRING_TEST, UPTHRUST, Grade, Step
from engine_alpha.state import side
from engine_alpha.record import SPRING, UPTHRUST
from engine_alpha.record import height_in_ranges
from dataclasses import replace
import math


STAGE = "grade"
#: The named events whose own swing is story, never empty; Phase D is a day and forgives nothing.
FORGIVEN = (SPRING, SPRING_TEST, UPTHRUST, LAST_SUPPER, SOS)

def ending_sos(events, days: list, opening_bar: int):
    """THE SOS that ends the base: the story's first SOS, when its push begins after the box opened; else None."""
    sos = next((e for e in events if e.kind == SOS and e.first_day is not None), None)
    if sos is None or sos.first_day not in days:
        return None
    return sos if days.index(sos.first_day) > opening_bar else None

def own_swings(events, turn_days: list, first_day, read_day) -> list:
    """Each named event's span narrowed to its own swing on the line: from the last committed turn before the
    event's day to the first after it (the legs into and out of its extreme); with none, the frame's edge."""
    out = []
    for e in events:
        if e.kind not in FORGIVEN:
            continue
        before = max((t for t in turn_days if t < e.day), default=first_day)
        after = min((t for t in turn_days if t > e.day), default=read_day)
        out.append((max(e.first_day or e.day, before), min(e.last_day or e.day, after)))
    return out

def letter(score: float) -> str:
    return "S" if score >= M.GRADE_S else "A" if score >= M.GRADE_A else "B" if score >= M.GRADE_B else "C"

def whole_points(raw: float) -> float:
    """The score read to the whole point, half up: the one number every surface shows and the letter is cut on."""
    return float(np.floor(raw + 0.5))

def read(high, low, days, turns, events, *, R: float, S: float, unit: float, opening_bar: int,
         read_bar: int) -> Grade:
    """The grade of the box shown (R, S, its frozen daily range ``unit``, its opening day ``opening_bar``) as of
    ``read_bar``. ``turns`` are the line's committed turns; ``events`` the story the reader named on this box."""
    days = list(days)
    area = M.LINE_WORD_AREA_ATR * unit
    sos = ending_sos(events, days, opening_bar)
    end = days.index(sos.first_day) - 1 if sos is not None else read_bar
    swings = own_swings(events, [t.day for t in turns], days[0], days[read_bar])
    empty = sum(1 for i in range(opening_bar, end + 1)
                if side(high[i], low[i], R, S, area) is not None            # beyond the line's area: not a hair
                and not any(a <= days[i] <= b for a, b in swings))          # outside every own swing: not story
    base = end - opening_bar + 1
    holds = True
    if sos is not None and sos.day in days and days.index(sos.day) < read_bar:
        lowest = float(np.min(low[days.index(sos.day) + 1:read_bar + 1]))
        floor = float(np.min(low[opening_bar:end + 1]))
        holds = lowest >= S - area or lowest >= floor                       # not beyond the area, or not lower
    raw = 0.0 if not holds else 100.0 * min(1.0, max(0.0, 1.0 - empty / base / M.GRADE_EMPTY_ZERO))
    score = whole_points(raw)
    return Grade(score=score, letter=letter(score), empty_days=empty, base_days=base, holds=holds)

def record(grade: Grade) -> tuple:
    """The grade's one step on the trail."""
    held = ("the base holds" if grade.holds else
            "the base does not hold: after THE SOS's top the price fell under the whole base")
    return (Step(STAGE, f"the grade: {grade.letter} ({grade.score:.0f}): {grade.empty_days} of the base's "
                        f"{grade.base_days} days empty; {held}"),)

def could_not_be_read(exc: BaseException) -> tuple:
    """The step a grade that fell over leaves: the read stands, the grade is missing, and the trail says why."""
    return (Step(STAGE, f"the grade could not be read ({type(exc).__name__}: {exc}); the read stands without it"),)


def contraction(high, low, opening_bar: int, end: int, read_bar: int):
    """The right side's contraction: the mean daily range of the bars after the base (``end`` its last day) against the
    base's; with no right side of three days yet, the base's last third against its first two. None under six bars."""
    ranges = np.asarray(high, dtype=float) - np.asarray(low, dtype=float)
    if read_bar - end >= 3:
        early, late = ranges[opening_bar:end + 1], ranges[end + 1:read_bar + 1]
    else:
        span = end - opening_bar + 1
        if span < 6:
            return None
        cut = end + 1 - max(2, span // 3)
        early, late = ranges[opening_bar:cut], ranges[cut:end + 1]
    if len(early) < 3 or not len(late) or not np.isfinite(early).all() or not np.isfinite(late).all():
        return None
    base = float(np.mean(early))
    return None if base <= 0 else float(np.mean(late)) / base

def measure(line, events, days, *, R: float, S: float, opening_bar: int, read_bar: int, high=None, low=None,
            unit=None) -> dict:
    """Facts only, on the grade's base and the built swing line: travel on identical fine-line endpoints, rail distances
    in box heights (a named spring or upthrust turn excused within its own swing), the height in ranges, the contraction."""
    days = list(days)
    sos = ending_sos(events, days, opening_bar)
    end = days.index(sos.first_day) - 1 if sos is not None else read_bar
    known = [e for e in events if e.committed and (e.known_day is None or e.known_day <= days[read_bar])]
    fine = [t for t in line.committed if opening_bar <= t.bar <= end]
    far = [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES)
           if t.committed and opening_bar <= t.bar <= end]
    # Far turns are fine turns; their common endpoints keep the travel ratio bounded.
    positions = {(t.bar, t.kind): i for i, t in enumerate(fine)}
    far = [t for t in far if (t.bar, t.kind) in positions]
    main_travel = fine_travel = 0.0
    fine_legs = 0
    for a, b in zip(far, far[1:]):
        first, last = positions[a.bar, a.kind], positions[b.bar, b.kind]
        legs = list(zip(fine[first:last], fine[first + 1:last + 1]))
        main_travel += abs(b.price - a.price)
        fine_travel += sum(abs(y.price - x.price) for x, y in legs)
        fine_legs += len(legs)
    errors = []
    explained = 0
    turn_days = [t.day for t in line.committed]
    spans = {kind: own_swings([e for e in known if e.kind == kind], turn_days, days[0], days[read_bar])
             for kind in (UPTHRUST, SPRING)}
    for turn in far:
        rail = R if turn.kind == "peak" else S
        kind = UPTHRUST if turn.kind == "peak" else SPRING
        outside = turn.price > R if turn.kind == "peak" else turn.price < S
        named = outside and any(a <= turn.day <= b for a, b in spans[kind])
        explained += int(named)
        if not named:
            errors.append(abs(turn.price - rail) / (R - S))
    return {
        "base_start": days[opening_bar].isoformat(),
        "base_end": days[end].isoformat(),
        "main_legs": max(0, len(far) - 1),
        "fine_legs": fine_legs,
        "main_travel": main_travel,
        "fine_travel": fine_travel,
        "main_swing_share": main_travel / fine_travel if fine_travel > 0 else None,
        "rail_alignment_error": (sum(errors) / len(errors)
                                 if errors and {t.kind for t in far} == {"peak", "valley"} else None),
        "rail_turns": len(errors),
        "event_turns": explained,
        "height_in_ranges": height_in_ranges(R, S, unit),
        "contraction": None if high is None or low is None else contraction(high, low, opening_bar, end, read_bar),
    }


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
        ("swings", "Clean swings", None if share is None else _fraction(share / M.CLARITY_SWING_FULL_SHARE),
         "no completed main swing yet" if share is None else
         f"{share:.0%} of the line's travel is the main zigzag; full marks at {M.CLARITY_SWING_FULL_SHARE:.0%}"),
        ("dead_space", "No dead space", _line(empty_share, 0.0, M.GRADE_EMPTY_ZERO),
         "the base has no days yet" if empty_share is None else
         f"{integrity.empty_days} of {base} base days empty, the bars off the box; none at half the base"),
        ("contraction", "Right-side contraction",
         _line(ratio, M.TRAIT_CONTRACTION_FULL_RATIO, M.TRAIT_CONTRACTION_ZERO_RATIO),
         "the base is too short to compare its right side with its start" if ratio is None else
         f"the last third's daily ranges are {ratio:.0%} of the earlier ones; full marks at "
         f"{M.TRAIT_CONTRACTION_FULL_RATIO:.0%}, none at {M.TRAIT_CONTRACTION_ZERO_RATIO:.0%}"),
        ("rails", "Rails the turns sit on",
         _line(error, M.CLARITY_RAIL_FULL_ERROR, M.CLARITY_RAIL_ZERO_ERROR),
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
    """The letter is the integrity grade's; the traits place the score in its band; a base that did not hold stays at 0."""

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
