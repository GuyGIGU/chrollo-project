"""NYSE trading-session helpers used by data freshness checks."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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


class _NyseHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas Day", month=12, day=25, observance=nearest_workday),
    ]


NYSE_BUSINESS_DAY = CustomBusinessDay(calendar=_NyseHolidayCalendar())


def normalize_session_date(day) -> pd.Timestamp:
    return pd.Timestamp(day).normalize()


def is_trading_session(day) -> bool:
    day = normalize_session_date(day)
    return not pd.date_range(day, day, freq=NYSE_BUSINESS_DAY).empty


def previous_trading_session(day) -> pd.Timestamp:
    return normalize_session_date(day) - NYSE_BUSINESS_DAY


def session_gap(last_session, expected_session) -> int:
    last_session = normalize_session_date(last_session)
    expected_session = normalize_session_date(expected_session)
    if last_session >= expected_session:
        return 0
    return max(0, len(pd.date_range(last_session, expected_session, freq=NYSE_BUSINESS_DAY)) - 1)


def latest_completed_session(now_et: datetime | None = None) -> pd.Timestamp:
    now_et = now_et or datetime.now(ZoneInfo("America/New_York"))
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=ZoneInfo("America/New_York"))
    else:
        now_et = now_et.astimezone(ZoneInfo("America/New_York"))

    today = normalize_session_date(now_et.date())
    after_close = (now_et.hour, now_et.minute) >= (16, 0)
    if is_trading_session(today) and after_close:
        return today
    return previous_trading_session(today)
