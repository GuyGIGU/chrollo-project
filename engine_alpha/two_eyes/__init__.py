"""The two-eyes reader — his method, read in his order, beside the old engine.

Task 5 of the two-eyes-reader build: the walking skeleton. Today this answers
"no lines" for every chart in the world, and that is the whole point. It
travels the entire route the old reader's answer travels — the door, the
adapter, the archive row, the wire, the screen and the board — so that when
stages 1 to 7 fill it in, nothing downstream changes shape again.

**It is a leaf.** This package imports nothing from the old chart reader
(`engine_alpha.evaluation`, `engine_alpha.structure`, `engine_alpha.scoring`),
and a test proves it. The proven pieces arrive later by COPY (task 7), with
their own tests, and the originals freeze. Growing the new inside the old is
how the last three attempts ended up measuring the old engine wearing a new
name.

The order the stages will fill in is his, not the old engine's:

    the bars -> one swing line -> the end of the trend -> the two lines,
    found by walking right like two legs -> the box's life -> the story left
    to right -> the LPS and its trigger -> the grade and the state word

Reading order for the next session: `record.py` is the shape everything is
built against; `frame.py` is what a chart must be before it is read.
"""
from __future__ import annotations

from engine_alpha.two_eyes.frame import FrameRefused, check as check_frame, prepare
from engine_alpha.two_eyes.line import SwingLine, Turn, build as build_line
from engine_alpha.two_eyes.record import _as_day
from engine_alpha.two_eyes.record import (
    NO_LINES,
    READ_FAILED,
    ROLE_EARLIER,
    ROLE_MINI,
    ROLE_PARENT,
    Box,
    Line,
    Lps,
    Read,
    Step,
    crashed,
)

__all__ = ["read", "Read", "Box", "Line", "Lps", "Step", "crashed",
           "FrameRefused", "check_frame", "prepare", "build_line", "SwingLine", "Turn",
           "NO_LINES", "READ_FAILED",
           "ROLE_PARENT", "ROLE_MINI", "ROLE_EARLIER"]


def read(ticker: str, df, *, as_of=None) -> Read:
    """Read one chart. The ONE public way in.

    Today: refuse a frame that is not a chart, and otherwise answer "no lines"
    with an empty record. A crashed read comes back as a counted failure with
    its reason — never as the words "no lines", which is what the screen says
    when a chart genuinely has no lines and must not be what it says when the
    engine fell over.
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
        # Stage 1 (task 8): the contract, each day's range on the long frame,
        # the cut to the reading window, and the ONE line every later stage
        # reads. Built here, once per read, and handed down; a stage that
        # rebuilt it could read a different line from the same bars.
        prepared = prepare(df)
        line = build_line(prepared)
    except FrameRefused as refusal:
        return crashed(ticker, as_of, str(refusal))
    except Exception as exc:                      # a broken frame, not a chart
        return crashed(ticker, as_of, f"{type(exc).__name__}: {exc}")

    # Stages 2 to 7 fill this in from `line`. Empty is the honest answer until
    # they do. The close is a fact of the read day, not of a stage: the frame
    # contract has just proved the last bar is whole.
    del line
    return Read(ticker=ticker, as_of=as_of, boxes=(), lps=None, trail=(),
                state=NO_LINES, close=float(prepared["Close"].iloc[-1]))
