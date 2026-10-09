"""The ONE door to the chart reader.

Task 4 of the two-eyes-reader build. Two readers exist side by side —
today's engine and the new one written in his order — and the only way
that can be safe is if every caller asks the same door which reader answered.

**Why a door at all.** The reader has three entry points, not one, and they are
reached from ten places outside the engine: the nightly scan and the archive
seed (production), the chart-state page, the single archive row's re-read and
the calibration workbench's "why did this mark miss" (the backend), the marks
ratchet, the junk corpus, the fleet shadow and the agreement harness (the
gates), and the replay seam they share. The reader pin is NOT among them — it
reads the engine's event vocabulary straight out of the bricks and never asks
for a chart read — so a switch here does not reach it. A switch behind the
scan's entry point would have
reached the scan and nothing else — the page you use to see why a mark missed
would have kept reading the old engine while the board read the new one, and
nobody would have been told.

**What the door does NOT do.** It does not change a single byte of what the
engine returns. With the switch off every function here forwards to today's
engine, and the flag-off output is the same object it always was. The reader's NAME
rides out of band, through an optional ``stamp`` dict — the sink idiom this
codebase already uses for ``watch`` and ``near_miss`` — so "which reader
answered" can be printed on a board or asserted in a test without appearing in
a result dict, an archive row or a wire payload.

**The switch is read in ONE function**, :func:`which_reader`, and nowhere else.

**A read only one reader can give refuses the other by name** (:class:`NotThisReader`): the old
reader's box read, :func:`read_box`, under the new reader; the new reader's record,
:func:`read_record` (the workbench's "why did this mark miss", go-live plan task 5), under the old.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from config import settings

#: What :func:`which_reader` can answer. ``OLD`` is today's engine; ``NEW`` is
#: the two-eyes reader (every stage built, dark), behind
#: ``TWO_EYES_READER_ENABLED``.
READER_OLD = "old"
READER_NEW = "new"


def which_reader() -> str:
    """The one place the reader switch is read.

    Everything else in the codebase asks this. ``getattr`` with a default keeps
    the door working against a settings module that predates the switch (the
    manifest is a hand-curated allow-list, so a new key is simply absent until
    it is added).
    """
    if getattr(settings, "TWO_EYES_READER_ENABLED", False):
        return READER_NEW
    return READER_OLD


class ReadFailed(ValueError):
    """The new reader refused a chart: a failed read, which is never "no setup".

    A ValueError, so every caller that already skips a date on a crash keeps
    doing so; one that must SAY why (the manual add, the seed's count) catches
    this first (council review 2026-10-09, finding 3)."""


class NotThisReader(NotImplementedError):
    """A read the reader that is switched on cannot give: refused by name, never answered "no box".

    The old reader's box-only read (its box and its trace, :func:`read_box`) and the replay seam's knob
    variants (they set the old reader's settings) have no answer under the new reader; the new reader's
    record (:func:`read_record`) has none under the old. A NotImplementedError, so a caller that already
    refused the gap keeps doing so (go-live plan, task 5)."""


def _stamp(stamp: Optional[dict], reader: str) -> None:
    """Name the reader that answered, out of band."""
    if stamp is not None:
        stamp["reader"] = reader


def _only_given(**lanes) -> dict:
    """The optional lane sinks the caller actually passed, and no others.

    The door must make the SAME call the caller used to make. Passing
    ``watch=None`` where the old call site passed nothing is not a behaviour
    change for the real chain — the default is ``None`` — but it is a change to
    the call, and this codebase's tests and instruments substitute the chain
    with narrower doubles on purpose (one of them exists to pin the production
    argument order). Three of them broke on the first version of this door.
    """
    return {name: value for name, value in lanes.items() if value is not None}


def evaluate_ticker(ticker: str, df: pd.DataFrame,
                    spy_6m_return: float = 0.0,
                    breadth_pct: Optional[float] = None,
                    *, watch: Optional[dict] = None,
                    stamp: Optional[dict] = None):
    """One ticker, the whole chain, under the standard skip guard.

    Returns the result dict, ``None`` (filtered out) or ``EVAL_ERROR`` — the
    same three answers ``evaluation._evaluate_ticker`` has always given, because
    today it IS that function.

    There is no near-miss argument here: the lane is not a sink on this call,
    it is a different return shape, and the scan gets it from
    :func:`scan_worker`. A first draft of this door had a ``near_miss=``
    branch that could never have run — the twin it forwarded to has no such
    parameter.
    """
    from engine_alpha import evaluation  # local: the chain is pandas/scipy-heavy

    answering = which_reader()
    _stamp(stamp, answering)
    if answering == READER_NEW:
        return _two_eyes(ticker, df, watch)[1]
    return evaluation._evaluate_ticker(ticker, df, spy_6m_return, breadth_pct,
                                       **_only_given(watch=watch))


def _two_eyes(ticker: str, df, watch: Optional[dict]):
    """The new reader, through its adapter — the ONE place it is called.

    Imported inside the function so that the old reader's path never pays for
    a package it does not use, and so a broken new reader cannot stop the old
    one from loading.

    The universe door stands BEFORE the read, and it is the old engine's own
    (one implementation of a ruled judgment): a chart it refuses is "not
    scanned", with the leg named, and is never read. It is one of the few
    hard things in his method, and a fire that ignored it would not be a fire
    the scan could ever show. The frame contract comes before the door: a
    frame that is not a chart is a counted failure, never "not scanned".
    Returns ``(read, result)``; both None when the door refused.
    """
    from engine_alpha import evaluation, two_eyes, two_eyes_adapter

    try:
        two_eyes.check_frame(df)
        admitted, reason = evaluation.apply_baseline_filters_with_reason(df)
    except two_eyes.FrameRefused:
        admitted = True                 # not a chart: the read below refuses it by name, a counted failure
    except Exception as exc:            # a chart the door cannot ask about: a counted failure too
        read = two_eyes.crashed(ticker, None, "the universe door could not read the frame: "
                                              f"{type(exc).__name__}: {exc}")
        two_eyes_adapter.fill_watch(read, watch)
        return read, two_eyes_adapter.to_result(read)
    if admitted is None:
        if watch is not None:
            watch.update(two_eyes=True, state="not scanned", why=reason[0])
        return None, None
    read = two_eyes.read(ticker, df)
    two_eyes_adapter.fill_watch(read, watch)
    return read, two_eyes_adapter.to_result(read)


def run_eval_chain(ticker: str, df: pd.DataFrame,
                   spy_6m_return: float = 0.0,
                   breadth_pct: Optional[float] = None,
                   *, near_miss=None, watch: Optional[dict] = None,
                   stamp: Optional[dict] = None):
    """The chain WITHOUT the skip guard — it raises, and the caller decides.

    The seed and the chart-state page use this: the seed skips the date on a
    crash, the page says the read failed. Both want the exception, not a
    sentinel.
    """
    from engine_alpha import evaluation

    answering = which_reader()
    _stamp(stamp, answering)
    if answering == READER_NEW:
        # This entry point's contract is that it RAISES; the caller decides.
        read, result = _two_eyes(ticker, df, watch)
        if read is not None and read.failed:
            raise ReadFailed(f"two-eyes reader refused {ticker}: {read.refusal}")
        return result
    return evaluation._run_eval_chain(ticker, df, spy_6m_return, breadth_pct,
                                      **_only_given(near_miss=near_miss, watch=watch))


class LaneRefused(RuntimeError):
    """A scan lane that reads the OLD engine was asked for under the new reader.

    Raised at the start of the scan, by name, never answered by a silent
    old-engine read beside a night stamped "new" (go-live plan, task 2)."""


#: Why each of the scan's lanes cannot ride the new reader, in plain words.
_OLD_ENGINE_LANES = {
    "near_miss_lane": (
        "the near-miss lane (NEAR_MISS_LANE_ENABLED) records the OLD reader's "
        "refusals; the scan turns it off under the new reader"),
    "watch_lane": (
        "the watch lane (LPS_LEAVES_ELECTION_ENABLED) builds its row from the "
        "OLD reader's frame, unit, box and forming read, which the new "
        "reader's watch does not give"),
    "rescue_lane": (
        "the rescue lanes (CONTRACTION_RESCUE_ENABLED / "
        "BAR_POSTURE_RESCUE_ENABLED) re-read the OLD reader's refusals with "
        "the old engine"),
}


def refuse_old_engine_lanes(*, near_miss_lane: bool = False,
                            watch_lane: bool = False,
                            rescue_lane: bool = False) -> None:
    """Raise :class:`LaneRefused`, naming every lane asked for, under the new reader.

    Each lane beside the scan's read is a twin of the OLD engine's chain: it
    reaches the old engine directly and takes no inner worker, so composing
    it under the new reader would hand the pool the old engine while the night
    says "new" (the split brain this door exists to prevent). The scan asks
    this before a price is fetched, and :func:`scan_worker` asks it again.
    """
    asked = {"near_miss_lane": near_miss_lane, "watch_lane": watch_lane,
             "rescue_lane": rescue_lane}
    named = [_OLD_ENGINE_LANES[lane] for lane, on in asked.items() if on]
    if named:
        raise LaneRefused(
            "the scan reads with the two-eyes reader tonight, and "
            + "; ".join(named)
            + ". Switch the lane off, or switch TWO_EYES_READER_ENABLED off.")


def scan_worker(*, near_miss_lane: bool, watch_lane: bool, rescue_lane: bool = False):
    """The one worker the nightly scan hands to its process pool.

    Under the old reader the scan composes three lanes around the read — the
    near-miss cohort, the watch-lane recorder and the rescue lanes' cost twin
    (the outermost rung, so the scan's unwrap stays deterministic) — and all
    are engine twins of the same chain, not second readers. Composing them
    HERE keeps the scan's call site one line and keeps the reader's identity
    in one module. The result is picklable (module-level functions and a
    ``partial`` of one), which the ``ProcessPoolExecutor`` requires.

    Under the new reader the worker is this door's own :func:`evaluate_ticker`
    and no lane rides (go-live plan, task 2): every lane is an old-engine
    twin, so a lane asked for is refused by name
    (:func:`refuse_old_engine_lanes`). The scan turns the live near-miss lane
    off itself and says so; the dark watch and rescue lanes refuse the scan.
    """
    from functools import partial

    from engine_alpha import evaluation

    if which_reader() == READER_NEW:
        refuse_old_engine_lanes(near_miss_lane=near_miss_lane,
                                watch_lane=watch_lane, rescue_lane=rescue_lane)
        return evaluate_ticker
    worker = evaluation.evaluate_ticker_with_near_miss if near_miss_lane else evaluate_ticker
    if watch_lane:
        worker = partial(evaluation.evaluate_ticker_with_watch, inner=worker)
    if rescue_lane:
        worker = partial(evaluation.evaluate_ticker_with_rescue_stats, inner=worker)
    return worker


def read_box(df: pd.DataFrame, atr: float, *, bricks=None, trace=None,
             near_miss=None, stamp: Optional[dict] = None):
    """The OLD reader's box read alone: no pullback, no score, no verdict.

    The calibration workbench's grading (the concordance chip and the engine
    overlay, through the replay seam), the yardstick's old arm and word
    recall's engine basis read a chart this way — they want the old reader's
    box shape and its trace, not a fire. (The doctrine audit reads the old
    engine directly, not through here.) The workbench's "why did this mark
    miss" reads the new reader's own record instead, :func:`read_record`.
    """
    from engine_alpha.structure.narrative import read_structure

    answering = which_reader()
    _stamp(stamp, answering)
    if answering == READER_NEW:
        # Refused by name. This door used to read the chart with the new
        # reader, throw the read away and answer None — "no box" — for every
        # chart, which looks like a real answer (council review 2026-10-09,
        # finding 2). The new reader's box is not this shape: a caller that
        # wants it in the new reader's words asks read_record.
        raise NotThisReader(
            "the box-only read is the OLD reader's (its box shape and its "
            "trace); the new reader is switched on and answers with its own "
            "record (reader.read_record), never with this shape.")
    return read_structure(df, atr, **_only_given(bricks=bricks, trace=trace,
                                                 near_miss=near_miss))


def read_record(ticker: str, df: pd.DataFrame, *, watch: Optional[dict] = None,
                stamp: Optional[dict] = None):
    """The NEW reader's own record of a chart: its boxes and its trail, for a
    caller that wants the reasons, not a fire (the workbench's "why did this
    mark miss", go-live plan task 5).

    The read goes through the same path as the scan's (the frame contract,
    then the universe door, then the reader). Returns the ``Read`` — a failed
    one says so (``failed``, ``refusal``) — or ``None`` when the universe door
    refused the chart, which the reader then never read; the leg is in
    ``watch["why"]``. Under the old reader it refuses by name: the old reader
    has no such record, its box read is :func:`read_box`.
    """
    answering = which_reader()
    _stamp(stamp, answering)
    if answering == READER_OLD:
        raise NotThisReader(
            "the reader's own record (its boxes and its trail) is the new "
            "reader's; the old reader is switched on, and its box read is "
            "reader.read_box.")
    read, _ = _two_eyes(ticker, df, watch)
    return read
