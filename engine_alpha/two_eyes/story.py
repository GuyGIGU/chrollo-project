"""Stage 5 of the two-eyes reader: the story — the words the drawing printed against the box shown.

His sentence (Sat 26/09/2026): *"the rest is how we interpret the inner price action in the box that leads us to
the rest of the "events" & and the way we treat the box rails ... construct them into swings -> construct swings
into a drawing and then we see how it fares against our box and we can interpret said drawing to visual patterns
we can recognize aka: spring, up thrust, sos, lps, mini consolidation and so on depending on the chronological
"phase" of said setup."* And the sentence that bounds it (Sat 19/09/2026): *"we just got to nail down our core for
detecting consolidations and an LPS. the rest is a nice little bonus."*

So this stage only NAMES. It reads the read's own line (the forming turn at the right edge included: that turn is
what makes a word provisional), the box SHOWN and no earlier box, and the pullback the LPS stage measured; it
calls the pure word rules in ``line_words`` and turns what they name into ``record.Event``s dated by days. It
decides nothing: the fire is settled before it runs, ``Read.fired`` reads no event, and a story that cannot be
read is an empty story and a step on the trail, never a failed read.

The order is LPS first, then the story, because three words lean on the pullback (THE SOS tops at or before its
low, a last supper is sought before its window opens, it is one of the ways the right side opens). The dependency
runs one way: the story reads the pullback, the LPS never reads the story.

Committed or provisional (ours): an event is committed when the swing it stands on, and the swing that answers
it, have committed on the line by the read day; until then it is provisional and may still be taken back.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from engine_alpha.two_eyes import line_words as LW
from engine_alpha.two_eyes import method_numbers as M
from engine_alpha.two_eyes.record import (LAST_SUPPER, PHASE_D, SOS, SPRING, SPRING_TEST, UPTHRUST, Event, Step)

__all__ = ["read", "record", "could_not_be_read", "STAGE"]

#: The stage name of the story's one step on the trail.
STAGE = "story"


def _lps_days(pullback, low) -> tuple:
    """The first day and the low's day of the pullback the words lean on: the one the LPS stage measured, when it
    stood on its last day (none of his sentences refused it and the box was a box), whether it has since been
    bought or not. ``(None, None)`` otherwise."""
    if pullback is None or not pullback.stood:
        return None, None
    start, end = int(pullback.start_bar), int(pullback.end_bar)
    return start, start + int(np.argmin(low[start:end + 1]))


def read(turns, high, low, days, *, start_bar: int, R: float, S: float, unit: float, read_bar: int,
         pullback=None, trend_end_bar: Optional[int] = None) -> tuple:
    """The events of the box shown, oldest first. ``turns`` is the read's own line, forming turn included;
    ``start_bar`` the day the box opened; ``unit`` the one daily range the words are measured in; ``pullback``
    what the LPS stage measured, or None; ``trend_end_bar`` the top (or low) of the trend the box took its place
    from, when it took it from a box anchored inside that trend.

    "The trend still ending": a push that tops within fourteen trading days of the END OF THE TREND is no
    upthrust. The trend's end is the box's first line, or the earlier ``trend_end_bar`` when there is one: his ALB
    (Thu 01/10/2026), "even a later pair could work if that movement in 20/1 -> 27/1 and the crash afterwards
    could be treated as the place where the trend ends" and "there is a later [upthrust] on 25/02/2026". On the
    reader's own, later ALB box (it opens Thu 05/02/2026) the trend ended on Tue 27/01/2026, so the push of Wed
    25/02 is his upthrust there too; counted from the box's own first line it would be one day short."""
    line = [(int(t.bar), t.kind, float(t.price), None if t.knowable_bar is None else int(t.knowable_bar))
            for t in turns]
    start, read_bar, unit = int(start_bar), int(read_bar), float(unit)
    ended = start if trend_end_bar is None else min(start, int(trend_end_bar))
    fifteenth = ended + M.BOX_DAYS - 1
    lps_start, lps_low_bar = _lps_days(pullback, low)
    at = {(bar, kind): know for bar, kind, _, know in line}

    def day(bar: Optional[int]):
        return None if bar is None else days[int(bar)]

    pushes = LW.thrusts(line, start, R, unit)
    spring = LW.phase_c(line, high, start, S, unit, R, lps_start, read_bar, fifteenth=fifteenth)
    sos = LW.pick_the_sos(pushes, lps_low_bar, after=spring["tip_bar"] if spring is not None else None,
                          line=line, highs=high, start=start, read_bar=read_bar, unit=unit)
    out = []
    if spring is not None:
        out.append(Event(kind=SPRING, day=day(spring["tip_bar"]), price=spring["tip_price"],
                         first_day=day(spring["start_bar"]), last_day=day(spring["confirm_bar"]),
                         size=spring["depth_ranges"], committed=spring["knowable_bar"] is not None,
                         known_day=day(spring["knowable_bar"])))
    for test in LW.spring_tests(line, spring, S, unit):
        out.append(Event(kind=SPRING_TEST, day=day(test["tip_bar"]), price=test["tip_price"],
                         committed=test["knowable_bar"] is not None, known_day=day(test["knowable_bar"])))
    up = LW.the_upthrust(pushes, line, R, unit, spring, start, read_bar, fifteenth=fifteenth)
    if up is not None:
        out.append(Event(kind=UPTHRUST, day=day(up["top_bar"]), price=up["top_price"],
                         first_day=day(up["swing_bar"]), last_day=day(up["back_bar"]), size=up["poke_ranges"],
                         committed=up["knowable_bar"] is not None, known_day=day(up["knowable_bar"])))
    sos_settled = sos is not None and sos["knowable_bar"] is not None and not sos["in_progress"]
    if sos is not None:
        settled = sos_settled
        out.append(Event(kind=SOS, day=day(sos["top_bar"]), price=sos["top_price"], first_day=day(sos["swing_bar"]),
                         last_day=day(sos["top_bar"]), size=sos["ground_ranges"], committed=settled,
                         known_day=day(sos["knowable_bar"]) if settled else None,
                         note="" if not sos["in_progress"] else "no LPS follows it yet"))
    tops = {t["top_bar"]: t["top_price"] for t in pushes}
    for supper in LW.last_suppers(pushes, low, unit, lps_start, R=R, pc=spring, start=start, read_bar=read_bar):
        out.append(Event(kind=LAST_SUPPER, day=day(supper["top_bar"]), price=tops[supper["top_bar"]],
                         first_day=day(supper["top_bar"]), last_day=day(supper["low_bar"]),
                         size=supper["dig_ranges"], committed=True, known_day=day(supper["low_bar"])))
    opens = LW.phase_d(line, start, R, S, unit, spring, sos, lps_start, read_bar)
    if opens is not None:
        bar, opener = int(opens["open_bar"]), opens["opener"]
        # The right side's opening is as settled as what opened it: a low of the line that has committed (the
        # round trip, the staircase); THE SOS once THE SOS is itself settled; the LPS once it has been bought
        # (until then the pullback is only the read day's own, and tomorrow's read may measure another).
        low_known = at.get((bar, "valley"))
        bought = None if pullback is None else pullback.crossed_bar
        known = {"round trip": low_known, "staircase": low_known,
                 "SOS": sos["knowable_bar"] if sos_settled else None, "LPS": bought}[opener]
        out.append(Event(kind=PHASE_D, day=day(bar), price=float(low[bar]), committed=known is not None,
                         known_day=None if known is None else day(max(int(known), bar)), note=opener))
    return tuple(sorted(out, key=lambda e: (e.day, e.kind)))


def _said(event: Event) -> str:
    words = {SPRING: "the spring's tip", SPRING_TEST: "the spring's test", UPTHRUST: "THE upthrust tops",
             SOS: "THE SOS tops", LAST_SUPPER: "a last supper tops", PHASE_D: "Phase D opens"}[event.kind]
    price = "" if event.kind == PHASE_D else f" at {event.price:.2f}"
    note = f" ({event.note})" if event.note else ""
    return f"{words} {event.day:%a %d/%m/%Y}{price}{note}{'' if event.committed else ', provisional'}"


def record(events) -> tuple:
    """The story's one step on the trail: the words, in the order of their days."""
    if not events:
        return (Step(STAGE, "the story: no word is named on this box yet"),)
    return (Step(STAGE, "the story: " + "; ".join(_said(e) for e in events)),)


def could_not_be_read(exc: BaseException) -> tuple:
    """The step a story that fell over leaves: the read stands, the words are missing, and the trail says why."""
    return (Step(STAGE, f"the story could not be read ({type(exc).__name__}: {exc}); the read stands without it"),)
