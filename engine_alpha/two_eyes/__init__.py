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

Built so far: stages 1 to 4 and stage 6 — the core, the box and the LPS, which
his ruling of Sat 26/09/2026 put first. The story (stage 5) and the grade
(stage 7) follow his core sitting.

Reading order for the next session: `record.py` is the shape everything is
built against; `frame.py` is what a chart must be before it is read.
"""
from __future__ import annotations

from engine_alpha.two_eyes import lps
from engine_alpha.two_eyes import method_numbers as M
from engine_alpha.two_eyes import walk
from engine_alpha.two_eyes.frame import DAILY_RANGE, FrameRefused, check as check_frame, prepare
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


def read(ticker: str, df, *, as_of=None, keep_listing: bool = False) -> Read:
    """Read one chart. The ONE public way in.

    Refuse a frame that is not a chart; else build the line (stage 1), walk
    from every end of a trend to the box and follow the box's life (stages 2
    to 4, `walk`), read the LPS and its trigger against that box (stage 6,
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
        # Stage 1 (task 8): the contract, each day's range on the long frame,
        # the cut to the reading window, and the ONE line every later stage
        # reads. Built here, once per read, and handed down; a stage that
        # rebuilt it could read a different line from the same bars.
        prepared = prepare(df)
        line = build_line(prepared)
        # Stages 2 to 4 (tasks 10 and 11): every end of a trend the far view
        # shows, its pair on the line, the two-legs walk and the election, and
        # the box's life — a newer box takes over only beyond the shown one,
        # once the price left and did not come back — on the committed turns
        # only: the forming turn at the edge decides nothing.
        far = line.far(M.FAR_VIEW_FLOOR_RANGES)
        ranges = prepared[DAILY_RANGE].to_numpy(dtype=float)
        days = tuple(d.date() for d in prepared.index)
        found = walk.elect(line.committed, [t for t in far if t.committed], ranges,
                           days=days, read_bar=len(prepared) - 1)
        boxes, trail, state = walk.record(found, keep_listing=keep_listing)
        # Stage 6 (task 12a): the last run of receding days against the box
        # shown, its trigger at the last day's high, refused only by his four
        # sentences. Read on the bars' highs and lows: no close decides it.
        pullback = None
        if found.winner is not None:
            pullback = lps.read(prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float),
                                ranges, line.committed, R=found.winner.R, S=found.winner.S,
                                box_unit=found.winner.unit, born_bar=found.winner.birth_bar)
        the_lps, said, word = lps.record(pullback, days, read_bar=len(prepared) - 1)
        trail, state = trail + said, word or state
    except FrameRefused as refusal:
        return crashed(ticker, as_of, str(refusal))
    except Exception as exc:                      # a broken frame, not a chart
        return crashed(ticker, as_of, f"{type(exc).__name__}: {exc}")

    # Stages 5 and 7 fill in the rest (the story, the grade). Empty is the
    # honest answer until they do. The close is a fact of the read day, not
    # of a stage: the frame contract has just proved the last bar is whole.
    return Read(ticker=ticker, as_of=as_of, boxes=boxes, lps=the_lps, trail=trail,
                state=state, close=float(prepared["Close"].iloc[-1]))
