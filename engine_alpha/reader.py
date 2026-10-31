"""The alpha reader: one chart in, one ``Read`` out.

``read`` builds the line, walks the boxes, reads the LPS and its trigger, then adds the story, the grade and
the state word to one record of measured facts and dated words. A read that falls over comes back as a
counted failure, never as "no lines".
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
    """Read one chart as of a day: the ONE public way in; a crashed read is a counted failure, never "no lines".
    ``keep_listing`` adds every other pair the walk listed to the trail, words only."""
    # the day is read and cut inside the guard: a string-date index or a bad day must arrive as a counted failure
    try:
        if as_of is None and df is not None and len(df):
            as_of = df.index[-1].date()
        as_of = _as_day(as_of)
        # stage 1: the frame and the ONE line every later stage reads
        prepared = prepare(df)
        line = build_line(prepared)
        # stages 2 to 4: the walk, on the committed turns only; the forming turn at the edge decides nothing
        far = line.far(M.FAR_VIEW_FLOOR_RANGES)
        ranges = prepared[DAILY_RANGE].to_numpy(dtype=float)
        high = prepared["High"].to_numpy(dtype=float)
        low = prepared["Low"].to_numpy(dtype=float)
        days = tuple(d.date() for d in prepared.index)
        found = walk.elect(line.committed, [t for t in far if t.committed], ranges, high, low,
                           days=days, read_bar=len(prepared) - 1)
        boxes, trail, state = walk.record(found, keep_listing=keep_listing)
        # the mini (off, MINI_ENABLED): a second box inside the parent's right side; its faults leave the parent's read
        mini_pair = None
        if found.winner is not None and M.MINI_ENABLED:
            mini_box, mini_pair, steps = mini.read(found, high, low, ranges, len(prepared) - 1)
            boxes, trail = boxes + (() if mini_box is None else (mini_box,)), trail + steps
        # stage 6: the LPS and its trigger, on the bars' highs and lows; no close decides it
        pullback = None
        if found.winner is not None:
            pullback = lps.read(high, low, ranges, line.committed, R=found.winner.R, S=found.winner.S,
                                box_unit=found.winner.unit, born_bar=found.winner.birth_bar)
        the_lps, said, word = lps.record(pullback, days, read_bar=len(prepared) - 1)
        if pullback is not None and mini_pair is not None:
            # a pullback whose low is in, on or near the mini is read against the mini; a fault there leaves the parent's
            the_lps, said, word, pullback = mini.read_lps(pullback, mini_pair, high, low, ranges, line.committed,
                                                          days, len(prepared) - 1, boxes)
        trail, state = trail + said, word or state
        # stage 5, AFTER the fire is decided and in its own guard: a word never costs a fire, a bug in a word rule included
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
        # stage 7, after the story (the swings it forgives are the story's events) and in its own guard: a grade never costs a fire
        the_grade = None
        if found.winner is not None:
            try:
                the_grade = grade_stage.read(high, low, days, line.committed, events, R=found.winner.R,
                                             S=found.winner.S, unit=found.winner.unit,
                                             opening_bar=found.winner.opening_bar, read_bar=len(prepared) - 1)
                trail = trail + grade_stage.record(the_grade)
            except Exception as exc:                  # the read stands; the grade is missing; the trail says why
                the_grade, trail = None, trail + grade_stage.could_not_be_read(exc)
        # the clarity facts, in their own guard: a fault here leaves the integrity grade standing
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
        # the state word, LAST and in its own guard: a decision that falls over leaves the word above standing
        state_days = None
        try:
            state, state_days = state_word.decide(found, state, high, low, len(prepared) - 1)
        except Exception as exc:
            trail = trail + state_word.could_not_be_decided(exc)
    except FrameRefused as refusal:
        return crashed(ticker, as_of, str(refusal))
    except Exception as exc:                      # a broken frame, not a chart
        return crashed(ticker, as_of, f"{type(exc).__name__}: {exc}")

    return Read(ticker=ticker, as_of=as_of, boxes=boxes, lps=the_lps, trail=trail,
                state=state, close=float(prepared["Close"].iloc[-1]), events=events, state_days=state_days,
                grade=the_grade)
