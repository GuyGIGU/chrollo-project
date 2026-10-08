"""Stage 7 of the two-eyes reader: the grade — his dead space, and whether the base held.

Task 14 of the two-eyes-reader build. His words that place it:

* *"FRPH is total junk because the box is mostly dead space with no visible base insight"*, and a box about as tall
  as its bars *"is completely fine"* (Mon 05/10/2026). The box's SHAPE (its height, its tall bars, its zigzag, its
  spread profile, its story count) was measured first and separates nothing (the Tested-DEAD row of that day).
* Holding just below the support or resting just above the resistance is respect (Sun 30/08/2026).
* *"a named event's swing is never docked, an unnamed lunge beyond a rail is"* (Sun 13/09/2026), and only that
  swing: *"I'd forgive only that swing," correct* (Fri 09/10/2026).
* COLM: *"base dosen't hold and dosen't answer for an LPS anywhere"*; after the box *"reaches a lower level"*
  (Thu 08/10/2026).
* *"all of the 40 calibrated should be S tier in my book"* (Mon 05/10/2026).

The rules, each measured on his 40 and the 14 junk fires before it was built (the decisions rows of Fri
09/10/2026, the grade probe's fifth reading):

1. The box is the setup's box, the parent, whatever box the LPS was read against.
2. The base runs from the box's opening day to the day before THE SOS's push (the story's first SOS whose push
   begins after the box opened), else to the read day. From the push on is the right side.
3. A day of the base is empty when its bar misses the box by more than the line's area (half the box's daily
   range) and lies outside every named event's own swing: the reader's span for the event, narrowed to the line's
   legs into and out of its extreme (from the line's last committed turn before the event's day to its first
   after it, else the read day). Phase D is a day, not a swing: it forgives nothing.
4. The base holds unless, after THE SOS's top, a low falls beyond the support's area AND under the base's own
   lowest low: a lower level than the base ever made.
5. The grade is 100 with no empty day and 0 when half the base is empty, a straight line between; 0 when the base
   did not hold, whatever its days. S from 75, A from 50, B from 25, C under.

It reads the bars' highs and lows, never a close. It decides nothing: a fire is settled before it runs and
``Read.fired`` reads no grade; a grade that cannot be read is a missing grade and a step on the trail, never a
failed read.
"""
from __future__ import annotations

import numpy as np

from engine_alpha.two_eyes import method_numbers as M
from engine_alpha.two_eyes.record import LAST_SUPPER, SOS, SPRING, SPRING_TEST, UPTHRUST, Grade, Step

STAGE = "grade"
#: The named events whose own swing is story, never empty (his 13/09/2026). Phase D is a day: it forgives nothing.
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
                if (low[i] > R + area or high[i] < S - area)                # beyond the line's area: not a hair
                and not any(a <= days[i] <= b for a, b in swings))          # outside every own swing: not story
    base = end - opening_bar + 1
    holds = True
    if sos is not None and sos.day in days and days.index(sos.day) < read_bar:
        lowest = float(np.min(low[days.index(sos.day) + 1:read_bar + 1]))
        floor = float(np.min(low[opening_bar:end + 1]))
        holds = lowest >= S - area or lowest >= floor                       # not beyond the area, or not lower
    score = 0.0 if not holds else 100.0 * min(1.0, max(0.0, 1.0 - empty / base / M.GRADE_EMPTY_ZERO))
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
