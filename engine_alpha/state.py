"""The state word: the ONE word a chart carries on the screen, decided last and in its own guard.

The ten words are one closed table (``record.STATE_WORDS``); ``not scanned`` is the gate's, ``fired`` and ``crossed``
the LPS stage's and FINAL. With a box the right edge is read: ``lines, no LPS yet`` while the last bar still trades
at it, ``beyond R`` / ``under S`` once it sits wholly past a rail's area, the run's length beside the word. With no
box a young pair the bars came back to is ``forming N of 15``, else ``no lines``; two words of the ten are never said.
"""
from __future__ import annotations

from typing import Optional

from engine_alpha.record import (BEYOND_R, CROSSED, FIRED, FORMING, LINES_NO_LPS, NO_LINES, UNDER_S, Step)

__all__ = ["decide", "side", "could_not_be_decided", "STAGE"]

STAGE = "state"


def side(high: float, low: float, R: float, S: float, area: float) -> Optional[str]:
    """Where ONE day's bar sits against a box: ``BEYOND_R`` when its low is over the resistance area, ``UNDER_S``
    when its high is under the support area, None while any of it still reaches the box or its areas."""
    if low > R + area:
        return BEYOND_R
    if high < S - area:
        return UNDER_S
    return None


def _run_back(test, read_bar: int, first_bar: int) -> int:
    """How many days in a row, counted back from the read day and no further than ``first_bar``, pass ``test``."""
    run, bar = 0, int(read_bar)
    while bar >= first_bar and test(bar):
        run, bar = run + 1, bar - 1
    return run


def decide(found, word: str, high, low, read_bar: int) -> tuple:
    """``(state word, the number that rides beside it or None)``. ``found`` is the walk's result, ``word`` the
    state after the LPS stage (the walk's word, or the LPS's when it read a pullback)."""
    if word in (FIRED, CROSSED):
        return word, None
    box = found.winner
    if box is None:
        young = [p for p in found.pairs.values()
                 if p.unfit is None and p.birth_bar is None and p.r_back is not None and p.s_back is not None
                 and read_bar < p.fifteenth]
        if not young:
            return NO_LINES, None
        oldest = min(young, key=lambda p: (p.opening_bar, p.second_bar))
        return FORMING, int(read_bar) - int(oldest.opening_bar) + 1
    today = side(high[read_bar], low[read_bar], box.R, box.S, box.area)
    if today is None:
        return LINES_NO_LPS, None
    run = _run_back(lambda bar: side(high[bar], low[bar], box.R, box.S, box.area) == today, read_bar,
                    int(box.birth_bar))
    return today, run


def could_not_be_decided(exc: BaseException) -> tuple:
    """The step a state decision that fell over leaves: the word the LPS stage gave stands."""
    return (Step(STAGE, f"the state word could not be decided ({type(exc).__name__}: {exc}); the word before it stands"),)
