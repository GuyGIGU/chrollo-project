"""The two-eyes chart reader.

Build one shared swing line, walk the parent and mini boxes, read the LPS and
its trigger, then add the story, grade and state word to the read record.

Clarity facts are measured beside the integrity read. The adapter's scoring
seam composes the technical grade for scan, archive and screen.
"""
from __future__ import annotations

from dataclasses import replace

from engine_alpha import grade as grade_stage
from engine_alpha import lps
from engine_alpha.box import mini
from engine_alpha import state as state_word
from engine_alpha import story
from engine_alpha import numbers as M
from engine_alpha.box import walk
from engine_alpha.chart import DAILY_RANGE, FrameRefused, check as check_frame, prepare
from engine_alpha.line import SwingLine, Turn, build as build_line
from engine_alpha.record import _as_day
from engine_alpha.record import (
    EVENT_KINDS,
    LPS_HOW,
    NO_LINES,
    READ_FAILED,
    ROLE_EARLIER,
    ROLE_MINI,
    ROLE_PARENT,
    STATE_WORDS,
    Box,
    Event,
    Line,
    Lps,
    Read,
    Step,
    crashed,
)

__all__ = ["read", "Read", "Box", "Event", "Line", "Lps", "Step", "crashed", "STATE_WORDS", "EVENT_KINDS", "LPS_HOW",
           "FrameRefused", "check_frame", "prepare", "build_line", "SwingLine", "Turn",
           "NO_LINES", "READ_FAILED",
           "ROLE_PARENT", "ROLE_MINI", "ROLE_EARLIER"]


def read(ticker: str, df, *, as_of=None, keep_listing: bool = False) -> Read:
    """Read one chart. The ONE public way in.

    Refuse a frame that is not a chart; else build the line (stage 1), find
    the pair of swing ends that became the box and follow the box's life
    (stages 2 to 4, `walk`), read the LPS and its trigger against that box (stage 6,
    `lps`) and fill the record: the box, every box it took over from, the
    LPS, the trail to them, the state word. A crashed read comes
    back as a counted failure with its reason — never as the words "no
    lines", which is what the screen says when a chart genuinely has no lines
    and must not be what it says when the engine fell over. `keep_listing`
    adds every other pair the walk listed to the trail, words only: the box
    and the state are pinned identical with and without it.
    """
    # Inside the try: reading the last day off the index is itself a thing
    # that can fail — a string-date index raises here — and a crash before the
    # contract runs escapes as an uncaught exception instead of a counted
    # failure, which is the one thing this function promises not to do.
    try:
        if as_of is None and df is not None and len(df):
            as_of = df.index[-1].date()
        # A day the caller named is a day or it is refused HERE, inside the
        # guard: the record cuts every day on the way in and raises on
        # anything else, and that raise must arrive as a counted failure.
        as_of = _as_day(as_of)
        # Stage 1: the contract, each day's range on the long frame,
        # the cut to the reading window, and the ONE line every later stage
        # reads. Built here, once per read, and handed down; a stage that
        # rebuilt it could read a different line from the same bars.
        prepared = prepare(df)
        line = build_line(prepared)
        # Stages 2 to 4: the swings' end points, every end of a trend the far view
        # shows, every pair of ends a swing connects, the first to become a
        # box, and the box's life — it gives way only to a pair that opened
        # later, when it was anchored inside a live trend or the price left
        # it for good — on the committed turns only: the forming turn at the
        # edge decides nothing.
        far = line.far(M.FAR_VIEW_FLOOR_RANGES)
        ranges = prepared[DAILY_RANGE].to_numpy(dtype=float)
        high = prepared["High"].to_numpy(dtype=float)
        low = prepared["Low"].to_numpy(dtype=float)
        days = tuple(d.date() for d in prepared.index)
        found = walk.elect(line.committed, [t for t in far if t.committed], ranges, high, low,
                           days=days, read_bar=len(prepared) - 1)
        boxes, trail, state = walk.record(found, keep_listing=keep_listing)
        # The mini (off, ``MINI_ENABLED``; his word of Fri 30/10/2026: "sun set, mini consolidation detection"): a
        # second box inside the parent's right side, on the record after the walk's boxes. Its faults are its own:
        # the parent-only read stands with a step that says why, because the LPS may be read against the mini.
        mini_pair = None
        if found.winner is not None and M.MINI_ENABLED:
            mini_box, mini_pair, steps = mini.read(found, high, low, ranges, len(prepared) - 1)
            boxes, trail = boxes + (() if mini_box is None else (mini_box,)), trail + steps
        # Stage 6: the last run of receding days against the box shown, its trigger at the last day's high, refused
        # only by his four sentences. Read on the bars' highs and lows: no close decides it.
        pullback = None
        if found.winner is not None:
            pullback = lps.read(high, low, ranges, line.committed, R=found.winner.R, S=found.winner.S,
                                box_unit=found.winner.unit, born_bar=found.winner.birth_bar)
        the_lps, said, word = lps.record(pullback, days, read_bar=len(prepared) - 1)
        if pullback is not None and mini_pair is not None:
            # A pullback whose low is in, on or near the mini is read against the mini's lines (his condition); any
            # fault on the mini's side leaves the parent's read, with a sentence.
            the_lps, said, word, pullback = mini.read_lps(pullback, mini_pair, high, low, ranges, line.committed,
                                                          days, len(prepared) - 1, boxes)
        trail, state = trail + said, word or state
        # Stage 5: the story, the words the drawing printed against the box shown. It runs AFTER the
        # fire is decided and inside its own guard: a word never costs a fire, a bug in a word rule included.
        # It reads the whole line (the forming turn is what makes a word provisional), the box shown and no
        # earlier box, and the pullback stage 6 measured.
        events = ()
        if found.winner is not None:
            try:
                events = story.read(line.turns, high, low, days, start_bar=found.winner.opening_bar,
                                    R=found.winner.R, S=found.winner.S, unit=found.winner.unit,
                                    read_bar=len(prepared) - 1, pullback=pullback,
                                    trend_end_bar=(found.lives[-1].trend_end or {}).get("climax_bar"))
                trail = trail + story.record(events)
            except Exception as exc:                  # the read stands; the words are missing; the trail says why
                events, trail = (), trail + story.could_not_be_read(exc)
        # Stage 7: the grade — his dead space on the setup's box (the parent) and whether the base held.
        # After the story, because the swings it forgives are the story's own events, and in its own guard: a grade
        # never costs a fire, a bug in a grade rule included.
        the_grade = None
        if found.winner is not None:
            try:
                the_grade = grade_stage.read(high, low, days, line.committed, events, R=found.winner.R,
                                             S=found.winner.S, unit=found.winner.unit,
                                             opening_bar=found.winner.opening_bar, read_bar=len(prepared) - 1)
                trail = trail + grade_stage.record(the_grade)
            except Exception as exc:                  # the read stands; the grade is missing; the trail says why
                the_grade, trail = None, trail + grade_stage.could_not_be_read(exc)
        # The clarity facts, in their own guard: a fault here leaves the integrity grade standing.
        if the_grade is not None:
            try:
                from engine_alpha.grade import measure

                facts = measure(line, events, days, R=found.winner.R, S=found.winner.S,
                                opening_bar=found.winner.opening_bar, read_bar=len(prepared) - 1,
                                high=high, low=low, unit=found.winner.unit)
                the_grade = replace(the_grade, clarity={"facts": facts})
            except Exception as exc:
                trail = trail + (Step(grade_stage.STAGE, f"the clarity facts could not be measured "
                                                         f"({type(exc).__name__}: {exc}); the integrity grade stands"),)
        # The state word, decided LAST and in its own guard: `fired` and `crossed` are final; with no
        # fire and no cross the right edge is read (bars wholly past a line's area), and with no box a young pair
        # the bars came back to is `forming N of 15`. A decision that falls over leaves the word above standing.
        state_days = None
        try:
            state, state_days = state_word.decide(found, state, high, low, len(prepared) - 1)
        except Exception as exc:
            trail = trail + state_word.could_not_be_decided(exc)
    except FrameRefused as refusal:
        return crashed(ticker, as_of, str(refusal))
    except Exception as exc:                      # a broken frame, not a chart
        return crashed(ticker, as_of, f"{type(exc).__name__}: {exc}")

    # The close is a fact of the read day, not of a stage: the frame contract
    # has just proved the last bar is whole.
    return Read(ticker=ticker, as_of=as_of, boxes=boxes, lps=the_lps, trail=trail,
                state=state, close=float(prepared["Close"].iloc[-1]), events=events, state_days=state_days,
                grade=the_grade)
