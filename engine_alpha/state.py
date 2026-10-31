"""The state word: the ONE word a chart carries on the screen, decided last (build task 12b, step 7).

The ten words are one closed table (``record.STATE_WORDS``). Who says which:

  not scanned                 the door, before any read (his "lets go with not scanned")
  fired, crossed              the LPS stage, and they are FINAL: nothing here may retype them. An LPS over
                              resistance fires (his ANRO: "its an LPS above Resistance that fires"), so the right
                              edge is read only when there is no fire and no cross
  lines, no LPS yet           a box is shown and the last bars still trade at it
  beyond R, undetermined      a box is shown and the last bars sit WHOLLY over its resistance area
  under S, undetermined       ... wholly under its support area. His sentence for the open right edge: "The bars
                              after wards determine the meaning" (Sun 30/08/2026)
  forming N of 15             no box is shown, and a pair of lines the bars have already come back to is
                              younger than his fifteen days ("Lets go with 15 days"); N rides beside the word
  no lines                    none of the above
  root candidate, unconfirmed
  broke down                  on the table and never said by this reader: both were typed off a box-end reader
                              that is gone; a box now ends only into a newer box

All of it is OURS but the sentences quoted. The word is derived from the read; nothing that decides a fire reads
it, and ``read`` runs this inside its own guard: a state that cannot be decided leaves the LPS's word standing.
"""
from __future__ import annotations

from typing import Optional

from engine_alpha.record import (BEYOND_R, CROSSED, FIRED, FORMING, LINES_NO_LPS, NO_LINES, UNDER_S, Step)

__all__ = ["decide", "side", "could_not_be_decided", "STAGE"]

STAGE = "state"


def side(high: float, low: float, R: float, S: float, area: float) -> Optional[str]:
    """Where ONE day's bar sits against a box: ``BEYOND_R`` when its low is over the resistance area, ``UNDER_S``
    when its high is under the support area, None while any of it still reaches the box or its areas. The one
    judgment of "the price has run on past the box"; the boards read it too."""
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
