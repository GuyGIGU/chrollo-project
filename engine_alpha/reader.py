"""The one door to the chart reader.

Every caller reads a chart through here: the nightly scan (:func:`scan_read`), the archive seed and the
chart-state page (:func:`run_eval_chain`), the ratchets and the calibration workbench
(:func:`evaluate_ticker`), and the instruments that want the reader's own record rather than a fire
(:func:`read_record`). The old engine retired on Sat 31/10/2026 (the operator's word the night before:
"retire the old engine, from now on we focus on the new one"); the reader behind this door is the alpha
reader, ``engine_alpha.two_eyes``, spoken in the scan's result shape by ``engine_alpha.two_eyes_adapter``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


class ReadFailed(ValueError):
    """The reader refused a chart: a failed read, which is never "no setup".

    A ValueError, so every caller that already skips a date on a crash keeps
    doing so; one that must SAY why (the manual add, the seed's count) catches
    this first (council review 2026-10-09, finding 3)."""


@dataclass(frozen=True)
class NotRead:
    """A chart the reader would not read: its frame broke the frame contract (a trading day missing from the
    middle, the same day twice, ...), named, with the rule and the whole reason.

    Never a crash and never "no setup": a halted stock's gap is real, so the chart is not repaired, and the night
    lists it apart from the crashes, which alert. Only the scan's worker (:func:`scan_read`) answers with it; every
    other entry point keeps its own three answers."""
    ticker: str
    rule: str
    reason: str


def evaluate_ticker(ticker: str, df: pd.DataFrame,
                    spy_6m_return: float = 0.0,
                    breadth_pct: Optional[float] = None,
                    *, watch: Optional[dict] = None):
    """One ticker, the whole chain, under the standard skip guard.

    Returns a result dict, ``None`` (filtered out, or no setup) or ``EVAL_ERROR`` (the read failed; counted,
    never raised). The two market arguments are the pool's fixed call shape; the reader reads neither.
    """
    from engine_alpha.sentinels import EVAL_ERROR

    result = _two_eyes(ticker, df, watch)[1]
    return EVAL_ERROR if isinstance(result, NotRead) else result


def scan_read(ticker: str, df: pd.DataFrame,
              spy_6m_return: float = 0.0,
              breadth_pct: Optional[float] = None):
    """The reader's worker for the nightly scan's pool.

    :func:`evaluate_ticker`'s three answers, and a fourth only the scan takes: a chart whose frame the reader would
    not read comes back as :class:`NotRead`, by name and reason, so the night lists it apart from the crashes
    (``EVAL_ERROR``, which still alert). Module-level, so the pool pickles it by name.
    """
    return _two_eyes(ticker, df, None)[1]


def _two_eyes(ticker: str, df, watch: Optional[dict]):
    """The reader, through its adapter — the ONE place it is called.

    The universe door stands BEFORE the read, and it is the one door
    (``engine_alpha/universe_door.py``, one implementation of a ruled judgment): a chart it refuses is "not
    scanned", with the leg named, and is never read. It is one of the few
    hard things in his method, and a fire that ignored it would not be a fire
    the scan could ever show. The frame contract comes before the door: a
    frame that is not a chart is a failed read, never "not scanned" — and
    it is a refusal, not a crash: the result is then a :class:`NotRead`,
    which :func:`evaluate_ticker` answers as the counted failure and the scan
    lists apart. A fire carries the stock's trend template, read on the frame
    the door admitted
    (``two_eyes_adapter.to_result``'s ``frame``).
    Returns ``(read, result)``; both None when the door refused.
    """
    from engine_alpha import two_eyes, two_eyes_adapter, universe_door

    refused = None
    try:
        two_eyes.check_frame(df)
        admitted, reason = universe_door.apply_baseline_filters_with_reason(df)
    except two_eyes.FrameRefused as refusal:
        refused, admitted = refusal, None   # not a chart: the read below refuses it by name
    except Exception as exc:            # a chart the door cannot ask about: a counted failure too
        read = two_eyes.crashed(ticker, None, "the universe door could not read the frame: "
                                              f"{type(exc).__name__}: {exc}")
        two_eyes_adapter.fill_watch(read, watch)
        return read, two_eyes_adapter.to_result(read)
    if admitted is None and refused is None:
        if watch is not None:
            watch.update(two_eyes=True, state="not scanned", why=reason[0])
        return None, None
    read = two_eyes_adapter.graded_read(two_eyes.read(ticker, df),
                                        frame=None if admitted is None else admitted[0])
    two_eyes_adapter.fill_watch(read, watch)
    if refused is not None and read.failed:
        return read, NotRead(ticker, refused.rule or str(refused), read.refusal or str(refused))
    return read, two_eyes_adapter.to_result(read, frame=None if admitted is None else admitted[0])


def run_eval_chain(ticker: str, df: pd.DataFrame,
                   spy_6m_return: float = 0.0,
                   breadth_pct: Optional[float] = None,
                   *, watch: Optional[dict] = None):
    """The chain WITHOUT the skip guard — it raises, and the caller decides.

    The seed and the chart-state page use this: the seed skips the date on a
    crash, the page says the read failed. Both want the exception
    (:class:`ReadFailed`), not a sentinel.
    """
    read, result = _two_eyes(ticker, df, watch)
    if read is not None and read.failed:
        raise ReadFailed(f"two-eyes reader refused {ticker}: {read.refusal}")
    return result


def read_record(ticker: str, df: pd.DataFrame, *, watch: Optional[dict] = None):
    """The reader's own record of a chart: its boxes and its trail, for a
    caller that wants the reasons, not a fire (the workbench's "why did this
    mark miss", the health board, word recall).

    The read goes through the same path as the scan's (the frame contract,
    then the universe door, then the reader). Returns the ``Read`` — a failed
    one says so (``failed``, ``refusal``) — or ``None`` when the universe door
    refused the chart, which the reader then never read; the leg is in
    ``watch["why"]``.
    """
    read, _ = _two_eyes(ticker, df, watch)
    return read
