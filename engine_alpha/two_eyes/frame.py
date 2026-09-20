"""The frame contract: what a chart must be before anybody reads it.

Task 5 of the two-eyes-reader build. The new reader is built on the promise
that a bar is a fact, so the one thing it may never do is read a frame that is
quietly wrong. Everything here fails CLOSED and LOUD — a refusal names the
rule, the day and the value, because a silent repair is how a chart comes to
be read as something the market never traded.

**What can really reach a reader.** Less than the council assumed, and a
blind survey corrected it twice. The eval path's only gate is the baseline
filter (history length, price, volume, the two averages, the year), whose
docstring forbids NaN hardening on purpose. So these reach a read unchecked
today: a day deleted from the middle, an unsorted index, the same date twice,
a bar whose high is under its low, and a missing column. This is the only
contract of its kind in the tree.

A NaN price does NOT reach it: the scan drops incomplete bars before the read
(`core/pipeline/screener.py`). That drop has a consequence this contract turns
from silent to loud — dropping a bad day leaves a HOLE, and a hole is exactly
what "a trading day is missing from the middle" refuses. So a ticker the old
engine reads straight through, on a frame quietly missing a day, becomes a
counted failure here. That is the contract working as intended, and it is
written down because it will show up as refusals the day the switch flips,
not as a surprise.

A deleted day is the dangerous one, because nothing about the remaining rows
looks wrong — every bar is valid, the index is still sorted, and the box
simply becomes a day shorter than the market was. It is only detectable
against a trading calendar, so this uses the project's own NYSE calendar
rather than counting weekdays (which would refuse every holiday) or guessing
from gap sizes (which would not refuse anything).
"""
from __future__ import annotations

import pandas as pd

# The project's ONE NYSE session calendar. Not the old chart reader — this
# package imports nothing from that — and not a second copy of the holiday
# rules, which is how two parts of a system come to disagree about whether
# the market was open. It sits on the engine's side of the fence because the
# engine is a leaf that may not import `core`; the pipeline's calendar
# re-exports it under the name its callers have always used.
from engine_alpha.market_sessions import session_gap

OHLC = ("Open", "High", "Low", "Close")


class FrameRefused(ValueError):
    """A chart that may not be read, and the reason, in one sentence."""


def _refuse(rule: str, detail: str) -> None:
    raise FrameRefused(f"{rule}: {detail}")


def check(df: pd.DataFrame) -> None:
    """Refuse a frame no reader should be asked to read. Returns None or raises.

    The order is deliberate — shape, then time, then the bars — so the first
    refusal is the most basic thing wrong, not an accident of iteration.
    """
    if df is None or len(df) == 0:
        _refuse("empty frame", "no bars at all")

    missing = [c for c in OHLC if c not in df.columns]
    if missing:
        _refuse("missing column(s)", ", ".join(missing))

    index = df.index
    if not isinstance(index, pd.DatetimeIndex):
        _refuse("index is not dates", f"got {type(index).__name__}")
    if index.hasnans:
        _refuse("index has a missing date", "at least one day is NaT")

    # Order is asked of the WHOLE index first. Walking pairwise would find a
    # shuffled frame too, but it would report the first gap it tripped over —
    # true of that pair, and the wrong diagnosis of the frame.
    if not index.is_monotonic_increasing:
        for position in range(1, len(index)):
            if index[position] < index[position - 1]:
                _refuse("days out of order",
                        f"{index[position].date()} comes after "
                        f"{index[position - 1].date()}")

    for position in range(1, len(index)):
        before, after = index[position - 1], index[position]
        # The DAY, not the timestamp. Comparing timestamps let the same day
        # through twice whenever the two rows carried different clock times —
        # 09:30 and 16:00 on one date read as two consecutive days, because
        # the gap rule below normalizes and this one did not. A rule whose
        # name says "day" has to be asked in days.
        if after.normalize() == before.normalize():
            _refuse("the same day twice", f"{after.date()} appears at "
                                          f"{position - 1} and {position}")
        gap = session_gap(before, after)
        if gap > 1:
            _refuse("a trading day is missing from the middle",
                    f"{gap - 1} session(s) between {before.date()} and "
                    f"{after.date()}")

    bad_bar = df[df["High"] < df["Low"]]
    if len(bad_bar):
        day = bad_bar.index[0]
        _refuse("a high under its low",
                f"{day.date()}: high {float(bad_bar.iloc[0]['High'])} < "
                f"low {float(bad_bar.iloc[0]['Low'])}")

    holed = df[df[list(OHLC)].isna().any(axis=1)]
    if len(holed):
        _refuse("a bar with a missing number",
                f"{holed.index[0].date()} — this is dropped upstream today, so "
                "its arrival here means the prep was bypassed")
