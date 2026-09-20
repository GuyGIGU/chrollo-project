"""The ONE door to the chart reader.

Task 4 of the two-eyes-reader build. Two readers are about to exist side by
side — today's engine and the new one written in his order — and the only way
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
engine returns. Today every function here forwards to the reader that exists,
and the flag-off output is the same object it always was. The reader's NAME
rides out of band, through an optional ``stamp`` dict — the sink idiom this
codebase already uses for ``watch`` and ``near_miss`` — so "which reader
answered" can be printed on a board or asserted in a test without appearing in
a result dict, an archive row or a wire payload.

**The switch is read in ONE function**, :func:`which_reader`. When the new
reader lands (task 5) it is added there and nowhere else.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from config import settings

#: What :func:`which_reader` can answer. ``OLD`` is today's engine; ``NEW`` is
#: the two-eyes reader, which does not exist yet — task 5 introduces it behind
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

    _stamp(stamp, which_reader())
    return evaluation._evaluate_ticker(ticker, df, spy_6m_return, breadth_pct,
                                       **_only_given(watch=watch))


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

    _stamp(stamp, which_reader())
    return evaluation._run_eval_chain(ticker, df, spy_6m_return, breadth_pct,
                                      **_only_given(near_miss=near_miss, watch=watch))


def scan_worker(*, near_miss_lane: bool, watch_lane: bool):
    """The one worker the nightly scan hands to its process pool.

    The scan composes two lanes around the read — the near-miss cohort and the
    watch-lane recorder — and both are engine twins of the same chain, not
    second readers. Composing them HERE keeps the scan's call site one line and
    keeps the reader's identity in one module. The result is picklable
    (module-level functions and a ``partial`` of one), which the
    ``ProcessPoolExecutor`` requires.
    """
    from functools import partial

    from engine_alpha import evaluation

    worker = evaluation.evaluate_ticker_with_near_miss if near_miss_lane else evaluate_ticker
    if watch_lane:
        worker = partial(evaluation.evaluate_ticker_with_watch, inner=worker)
    return worker


def read_box(df: pd.DataFrame, atr: float, *, bricks=None, trace=None,
             near_miss=None, stamp: Optional[dict] = None):
    """The box read alone: no pullback, no score, no verdict.

    The calibration workbench, the doctrine audit and the censuses read a chart
    this way — they want the lines and the reasons, not a fire.
    """
    from engine_alpha.structure.narrative import read_structure

    _stamp(stamp, which_reader())
    return read_structure(df, atr, **_only_given(bricks=bricks, trace=trace,
                                                 near_miss=near_miss))
