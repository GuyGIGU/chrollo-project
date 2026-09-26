"""When the market was open — the NYSE session rules, owned in one place.

Moved here from `core/pipeline/market_data/market_calendar.py` (two-eyes-reader task 5)
because two parts of the system legitimately need it and the dependency arrow
only points one way: `engine_alpha` is a LEAF — it may not import `core`, and
a test enforces that — while `core` imports the engine everywhere. So the
rules live on the engine's side and the pipeline's calendar re-exports them.

Nothing about the rules changed in the move. `core/pipeline/market_data/market_calendar.py`
is still the name every existing caller uses, and still the home of the
freshness helpers (early closes, finalization margins, "why is the market
shut") that belong to the data pipeline rather than to a chart read.

The reader needs exactly one thing from here: whether two days in a frame are
consecutive trading sessions. That is how a day deleted from the middle of a
chart is caught — the only way to catch it, since every remaining bar is valid
and the index is still sorted. Counting weekdays instead would refuse every
market holiday in the corpus.
"""
from __future__ import annotations

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
    sunday_to_monday,
)
from pandas.tseries.offsets import CustomBusinessDay


class NyseHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01",
                observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas Day", month=12, day=25, observance=nearest_workday),
    ]


#: Days the NYSE closed that no rule predicts — funerals, disasters, attacks.
#: A rule calendar cannot generate these, so they are listed, and the list is
#: the difference between a frame contract that works and one that refuses
#: every chart: measured on the frozen fixtures, the single missing 2025-01-09
#: made all 35 of his drawings and all 37 fleet charts look like they had a
#: day deleted from the middle.
#:
#: This also means `session_gap` was quietly wrong for the pipeline's own
#: freshness checks across each of these dates, since it grew from the same
#: rule calendar.
UNSCHEDULED_CLOSURES = (
    "2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14",  # the attacks
    "2004-06-11",   # President Reagan's funeral
    "2007-01-02",   # President Ford's funeral
    "2012-10-29", "2012-10-30",     # Hurricane Sandy
    "2018-12-05",   # President Bush's funeral
    "2025-01-09",   # President Carter's National Day of Mourning
)

NYSE_BUSINESS_DAY = CustomBusinessDay(
    calendar=NyseHolidayCalendar(),
    holidays=[pd.Timestamp(day) for day in UNSCHEDULED_CLOSURES],
)


def normalize_session_date(day) -> pd.Timestamp:
    return pd.Timestamp(day).normalize()


def is_trading_session(day) -> bool:
    day = normalize_session_date(day)
    return not pd.date_range(day, day, freq=NYSE_BUSINESS_DAY).empty


def session_gap(last_session, expected_session) -> int:
    """How many trading sessions separate two days. Consecutive days give 1."""
    last_session = normalize_session_date(last_session)
    expected_session = normalize_session_date(expected_session)
    if last_session >= expected_session:
        return 0
    return max(0, len(pd.date_range(last_session, expected_session,
                                    freq=NYSE_BUSINESS_DAY)) - 1)
