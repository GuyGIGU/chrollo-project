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
(`core/pipeline/screening/screener.py`). That drop has a consequence this contract turns
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
from engine_alpha import two_eyes_numbers as M
from engine_alpha.two_eyes.daily_range import calculate_atr

OHLC = ("Open", "High", "Low", "Close")

#: The column that carries each day's range once a frame is prepared. The name is the one the copied
#: pieces read (the word rules, the swing line's floors), so it stays ATR_10 although the reader calls
#: it the daily range.
DAILY_RANGE = "ATR_10"


class FrameRefused(ValueError):
    """A chart that may not be read, and the reason, in one sentence. ``rule`` is the rule's own name alone (the
    sentence's first half), so a night can count its refusals by rule without taking the sentence apart."""
    rule: str = ""


def _refuse(rule: str, detail: str) -> None:
    refusal = FrameRefused(f"{rule}: {detail}")
    refusal.rule = rule
    raise refusal


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

# The daily-structure window rule (copied from the old engine's frames.py at 61c88cc, two-eyes-reader task 8;
# the ONE home since that engine retired, Sat 31/10/2026): the adapter's stock facts and
# core/pipeline/market_data/downloads.py cut their frames with it too.
def _trim_to_period(data: pd.DataFrame, period: str) -> pd.DataFrame:
    """Trim DataFrame index to the trailing period window (e.g., '2y')."""
    if data.empty:
        return data
    if period.endswith('y'):
        years = int(period[:-1])
        cutoff = data.index.max() - pd.Timedelta(days=365 * years + 5)
    elif period.endswith('mo'):
        months = int(period[:-2])
        cutoff = data.index.max() - pd.Timedelta(days=30 * months + 2)
    else:
        return data
    return data.loc[data.index >= cutoff]


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """A chart made ready to read, in this order: the contract (``check``), each day's range on the LONG
    frame, then the cut to the reading window with the ranges carried.

    Stage 1 of the two-eyes reader (task 8). The order is the point. The old engine cuts first and computes
    its range inside the window, so its first weeks read a cold average; here the unit warms up on the bars
    before the window and every bar inside it has its range. Sliding the window's left edge by a day then
    changes no range; the line's first turns depend on where that edge falls for a few weeks at most and
    are the same turns after (its own tests measure and pin it). Returns a copy; the frame handed in is
    never written to.
    """
    check(df)
    out = df.copy()
    out[DAILY_RANGE] = calculate_atr(out, M.DAILY_RANGE_DAYS)
    return _trim_to_period(out, M.READ_WINDOW)
