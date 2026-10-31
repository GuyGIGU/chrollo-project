"""Stage 6 of the two-eyes reader: the LPS and its trigger, read on the reader's own box.

Task 12a of the two-eyes-reader build. Pure functions of the bars' highs and lows, each day's range, the line's
committed turns and the box shown: no close is read, nothing is graded, and nothing refuses a pullback but his
own four sentences. Everything is computed from what is known on the read day.

His words that place the rules, and where they came from:

* **The traits.** *"I generally prefer to define it by the traits I want to see and deem high quality like
  Receding Price move over time, Lowering (and low) spread below average, 2 - 5 bars."* (Tue 08/09/2026).
* **The window.** *"The LPS window ends on the last receding day before the buy"* (Sat 12/09/2026). One window
  per read day: the last run of receding days — a lower high or a lower low than the day before — and the day
  before the run is its top; on where it starts, *"Lets go with the day after"* (Sun 13/09/2026). A pullback is
  read on at most five bars, so of a longer run only the last five are read, from their highest high: *"the blue
  part can be considered an LPS entry because of the moves final bars being pretty shallow and in decline"* (his
  BMRN picture, Mon 14/09/2026).
* **The trigger and the buy.** The trigger is the last receding day's high; the buy is the cross of it, and a
  cross inside the pullback is a buy too: *"Bought on 05/08/26 because that's the day I saw the stock on, the
  prior move on 03/08 - 04/08 seemed like a valid pullback to me"* (MRK, Sun 13/09/2026). The day that crosses
  it, nothing is on the board.
* **His four sentences.** (1) *"3 bars with huge increases in both spread and price changes meaning the pull back
  is increasing with sellers"*; (2) *"you cut the move off and it's a part of a bigger swing downwards that
  reaches support, we cannot ignore that"* (both on AEF, Mon 14/09/2026), and *"its seems like the correction is
  getting to deep"* (Tue 08/09/2026); (3) *"not below the support area"*, read on whole bars: *"the LPS is on the
  Support rather then Under it since most of the move is above it and only small parts of it poke out down"*
  (JAZZ, Sun 13/09/2026); (4) *"Lets go with that ceiling 1.35 I guess...."* (Thu 10/09/2026).

Ours, recorded as ours in the decisions record (task 12a, Sun 27/09/2026): the unit (the daily range five
trading days before the pullback's last day, the unit his numbers were placed in), the form of sentence one (the
old reader's, re-typed: the last three bars widen day by day and fall further day by day, the last fall bigger
than the whole range of the day before), the form of sentence two (the fall from the top of the swing on the
line to the pullback's low, against 2.75 daily ranges), the five-bar reading of a longer run, that a pullback
which ended before the box was a box is not its LPS, and the day that crosses the trigger AND makes a lower low:
the cross is a buy and the pullback goes on, its trigger now that day's high (on five of his 35 that day is his
own last receding day, on five it is his buy day).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

import numpy as np

from engine_alpha import numbers as M
from engine_alpha.record import CROSSED, FIRED, LINES_NO_LPS, ROLE_PARENT, Lps, Step
from engine_alpha.box.pairs import known_by

__all__ = ["Pullback", "read", "record", "recedes", "run_top", "window_top", "sellers_rising", "share_under",
           "swing_top", "SENTENCES", "SELLERS_RISING", "SLICE", "UNDER_SUPPORT", "OVER_RESISTANCE",
           "FIRED", "CROSSED", "LINES_NO_LPS"]

#: The screen's words this stage decides are three of the ten in ``record.STATE_WORDS``: FIRED, CROSSED and
#: LINES_NO_LPS, imported above from their one home.

#: His four sentences, in the order he said them. Nothing else refuses an LPS.
SELLERS_RISING = "the pullback is increasing with sellers"
SLICE = "a slice of a bigger swing down"
UNDER_SUPPORT = "most of it sits under the support area"
OVER_RESISTANCE = f"more than {M.LPS_CEILING_RANGES:g} daily ranges over resistance"
SENTENCES = (SELLERS_RISING, SLICE, UNDER_SUPPORT, OVER_RESISTANCE)


@dataclass(frozen=True)
class Pullback:
    """The last run of receding days as of one read day, measured against the box shown. ``refused`` names
    every one of his sentences that refuses it, in his order; empty, it is an LPS."""
    top_bar: int                    # the day it descends from
    end_bar: int                    # its last receding day
    trigger: float                  # that day's high
    low: float                      # the lowest low of its receding days
    unit: float                     # the daily range it is measured in
    swing_top_bar: int              # the top of the swing it belongs to, on the line
    depth: float                    # from that top to the swing's low, in units
    over_resistance: float          # its low over the box's resistance, in units (negative: under it)
    under_support: float            # the share of its high-to-low travel under the support area
    sellers_rising: bool
    refused: tuple
    born_bar: int                   # the day the box it is read against became a box
    crossed_bar: Optional[int] = None   # the first later day whose high crossed the trigger
    bought: Optional[float] = None  # the trigger of the LPS of the day before, when its last day crossed it

    @property
    def start_bar(self) -> int:
        """Its first receding day: the day after the top."""
        return self.top_bar + 1

    @property
    def stood(self) -> bool:
        """An LPS on its last day: none of his sentences refuses it, and the box was a box by then."""
        return not self.refused and self.end_bar >= self.born_bar


def recedes(high, low, bar: int) -> bool:
    """A receding day makes a lower high or a lower low than the day before."""
    return bar >= 1 and bool(high[bar] < high[bar - 1] or low[bar] < low[bar - 1])


def run_top(high, low, end: int) -> int:
    """The day before the run of receding days that ends on ``end``."""
    bar = int(end)
    while recedes(high, low, bar):
        bar -= 1
    return bar


def window_top(high, low, end: int) -> int:
    """The day the pullback is read from: the run's own top, or — of a run longer than five bars — the highest
    high of its last five, the last day left out (the later day on a tie)."""
    top = run_top(high, low, end)
    if end - top + 1 <= M.LPS_MAX_BARS:
        return top
    return max(range(end - M.LPS_MAX_BARS + 1, end), key=lambda bar: (high[bar], bar))


def sellers_rising(high, low, top: int, end: int) -> bool:
    """His sentence one on the run's last three bars: they widen day by day and fall further day by day (a day's
    fall is the mean of its high's and its low's drop from the day before, so the first of the three is measured
    from the bar before them), and the last fall is bigger than the whole range of the day before. Three bars: a
    run of one receding day under its top never reads it."""
    if end - top < 2 or end < 3:
        return False
    h, l = np.asarray(high[end - 3:end + 1], dtype=float), np.asarray(low[end - 3:end + 1], dtype=float)
    spread = h[1:] - l[1:]
    fall = ((h[:-1] - h[1:]) + (l[:-1] - l[1:])) / 2.0
    return bool(spread[0] < spread[1] < spread[2] and fall[0] < fall[1] < fall[2] and fall[2] > spread[1])


def share_under(high, low, level: float) -> float:
    """The share of the bars' high-to-low travel that lies under ``level``: whole bars, never a close."""
    high, low = np.asarray(high, dtype=float), np.asarray(low, dtype=float)
    total = float(np.sum(high - low))
    if total <= 0:
        return float(np.all(high <= level))
    return float(np.sum(np.clip(np.minimum(high, level) - low, 0.0, None))) / total


def swing_top(turns, high, top: int, low_bar: int) -> int:
    """The top of the swing the pullback belongs to: the highest high since the line's last valley at or before
    the run's top, up to the day before the pullback's low (the later day on a tie). A bounce too small to turn
    the line does not open a new swing."""
    launch = max((t.bar for t in turns if t.kind == "valley" and t.bar <= top), default=top)
    return max(range(launch, low_bar), key=lambda bar: (high[bar], bar))


def measure(high, low, ranges, turns, end: int, *, R: float, S: float, box_unit: float,
            born_bar: int = 0) -> Pullback:
    """The run of receding days that ends on ``end``, measured against the box ``R`` / ``S`` whose lines' area is
    half of ``box_unit``, with every one of his sentences that refuses it."""
    whole = run_top(high, low, end)
    top = window_top(high, low, end)
    unit = float(ranges[max(0, end - M.LPS_UNIT_DAYS_BACK)])
    if not unit > 0:                    # a missing range compares false with every limit and would refuse nothing
        raise ValueError(f"the LPS has no daily range to be measured in: {unit!r}, "
                         f"{M.LPS_UNIT_DAYS_BACK} trading days before bar {end}")
    lows = np.asarray(low[top + 1:end + 1], dtype=float)
    low_bar = top + 1 + int(np.argmin(lows))
    lowest = float(lows.min())
    peak = swing_top(turns, high, whole, low_bar)
    depth = (float(high[peak]) - float(np.min(low[peak + 1:end + 1]))) / unit
    over = (lowest - float(R)) / unit
    under = share_under(high[top + 1:end + 1], low[top + 1:end + 1], float(S) - M.LINE_WORD_AREA_ATR * float(box_unit))
    sellers = sellers_rising(high, low, whole, end)
    refused = tuple(sentence for sentence, said in (
        (SELLERS_RISING, sellers),
        (SLICE, depth > M.LPS_DEPTH_MAX_RANGES),
        (UNDER_SUPPORT, under > M.LPS_UNDER_SUPPORT_SHARE),
        (OVER_RESISTANCE, over > M.LPS_CEILING_RANGES)) if said)
    return Pullback(top_bar=top, end_bar=end, trigger=float(high[end]), low=lowest, unit=unit,
                    swing_top_bar=peak, depth=depth, over_resistance=over, under_support=under,
                    sellers_rising=sellers, refused=refused, born_bar=int(born_bar))


def read(high, low, ranges, turns, *, read_bar: Optional[int] = None, **box) -> Optional[Pullback]:
    """The pullback as of ``read_bar`` (the last day by default): the last run of receding days (``measure``),
    with the first later day whose high crossed its trigger, and — when its own last day crossed the trigger of
    an LPS that stood the day before — that trigger: the cross was a buy, and because the day made a lower low
    too the pullback goes on (five of his own 35 end on such a day). None when no day has receded yet.

    A pullback is judged on the turns the line had made by the evening it ended, so its verdict is the same on
    whatever later day it is read: one refused that evening put no trigger on the board, and no later day can
    have crossed it (the core's blind check, Sun 27/09/2026: on SPCB the rally that crossed a refused pullback's
    high also turned the line under it, and the read said ``crossed``)."""
    read_bar = len(high) - 1 if read_bar is None else int(read_bar)
    end = read_bar
    while end >= 1 and not recedes(high, low, end):
        end -= 1
    if end < 1:
        return None
    found = measure(high, low, ranges, known_by(turns, end), end, **box)
    crossed = next((bar for bar in range(end + 1, read_bar + 1) if high[bar] > found.trigger), None)
    bought = None
    if high[end] > high[end - 1] and recedes(high, low, end - 1):
        before = measure(high, low, ranges, known_by(turns, end - 1), end - 1, **box)
        bought = before.trigger if before.stood else None
    return replace(found, crossed_bar=crossed, bought=bought)


# --------------------------------------------------------------------------- #
# The record: the LPS, its step on the trail, the state word                  #
# --------------------------------------------------------------------------- #
def _day(days, bar: int) -> str:
    return f"{days[bar]:%a %d/%m/%Y}"


def _span(days, pullback: Pullback) -> str:
    n = pullback.end_bar - pullback.top_bar
    if n == 1:
        return f"of {_day(days, pullback.end_bar)}, one receding day under the top of {_day(days, pullback.top_bar)}"
    return (f"from {_day(days, pullback.start_bar)} to {_day(days, pullback.end_bar)}, {n} receding days under the "
            f"top of {_day(days, pullback.top_bar)}")


def _facts(days, pullback: Pullback) -> str:
    where = (f"{pullback.over_resistance:.2f} daily ranges over resistance" if pullback.over_resistance > 0
             else f"{-pullback.over_resistance:.2f} daily ranges under resistance")
    return (f"its low {pullback.low:.2f} sits {where}, {pullback.depth:.2f} ranges under the swing's top of "
            f"{_day(days, pullback.swing_top_bar)}, measured in a {pullback.unit:.2f} daily range")


def record(pullback: Optional[Pullback], days, read_bar: int, *, read_against: str = ROLE_PARENT,
           how: Optional[str] = None) -> tuple:
    """The read's record of stage 6: ``(lps, steps, state)``. An LPS — a pullback none of his sentences refuses,
    its trigger still overhead, ended no earlier than the day the box became a box — fires. The day a later
    high crosses the trigger is the buy: ``crossed``, and nothing fires. ``(None, (), None)`` with no pullback
    to read, which leaves the state to the stage before. ``read_against`` and ``how`` are stamped as handed:
    which box the pullback was measured against and, for the mini, how its low sat against it (task 13)."""
    if pullback is None:
        return None, (), None
    span, trigger = _span(days, pullback), f"{pullback.trigger:.2f}"
    if not pullback.refused and pullback.end_bar < pullback.born_bar:
        said = (f"no LPS: the last pullback, {span}, ended before the box became a box on "
                f"{_day(days, pullback.born_bar)}")
        return None, (Step("LPS", said),), LINES_NO_LPS
    if pullback.refused:
        said = f"no LPS: the pullback {span} is refused: {'; '.join(pullback.refused)} ({_facts(days, pullback)})"
        return None, (Step("LPS", said),), LINES_NO_LPS
    if pullback.crossed_bar == read_bar:
        said = (f"crossed: the high of {_day(days, read_bar)} crossed the trigger {trigger}, the high of the last "
                f"day of the pullback {span}")
        return None, (Step("LPS", said),), CROSSED
    if pullback.crossed_bar is not None:
        said = (f"no LPS: the last pullback, {span}, was bought on {_day(days, pullback.crossed_bar)} at the cross "
                f"of {trigger}")
        return None, (Step("LPS", said),), LINES_NO_LPS
    also = "" if pullback.bought is None else (
        f"; that day's high crossed {pullback.bought:.2f}, the trigger of the day before, which was a buy, and the "
        "day made a lower low too, so the pullback goes on")
    against = "" if how is None else f"; read against the mini, {how}"
    said = (f"the LPS: the pullback {span}; the trigger is {trigger}, the high of {_day(days, pullback.end_bar)}; "
            f"{_facts(days, pullback)}{also}{against}")
    found = Lps(start_day=days[pullback.start_bar], end_day=days[pullback.end_bar], read_against=read_against,
                trigger_price=pullback.trigger, how=how)
    return found, (Step("LPS", said),), FIRED
