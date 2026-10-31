"""NYSE trading-session helpers used by data freshness checks."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
# The NYSE session RULES live on the engine's side of the fence: the
# engine is a leaf and may not import core, while core imports the engine
# everywhere, so one home for the rules means the engine's. Re-exported
# here under the names this module has always published (two-eyes-reader
# task 5) -- no caller changes, and there is still exactly one calendar.
from engine_alpha.chart import (  # noqa: F401
    NYSE_BUSINESS_DAY,
    NyseHolidayCalendar as _NyseHolidayCalendar,
    is_trading_session,
    normalize_session_date,
    session_gap,
)

# The trading DAY's clock stays here: when the market opens, closes and closes
# early belongs to the data pipeline's freshness checks, not to a chart read.
MARKET_TZ = ZoneInfo("America/New_York")
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)


def _thanksgiving_date(year: int) -> date:
    first = datetime(year, 11, 1).date()
    days_to_thursday = (3 - first.weekday()) % 7
    return first + timedelta(days=days_to_thursday + 21)


def is_early_close_session(day) -> bool:
    day = normalize_session_date(day)
    if not is_trading_session(day):
        return False

    value = day.date()
    if value.month == 7 and value.day == 3:
        return True
    if value == _thanksgiving_date(value.year) + timedelta(days=1):
        return True
    if value.month == 12 and value.day == 24:
        return True
    return False


def session_close_time(day) -> time:
    return EARLY_CLOSE if is_early_close_session(day) else REGULAR_CLOSE


def session_close_at(day) -> datetime:
    day = normalize_session_date(day)
    return datetime.combine(day.date(), session_close_time(day), tzinfo=MARKET_TZ)


def _finalization_margin() -> timedelta:
    """Minutes to wait after the close before a session's daily bar is treated as
    final. Read LAZILY: ``config`` is import-shadowed under the backend cwd, so a
    module-level settings read here would crash service boot — and a missing/broken
    setting falls back to a safe default."""
    try:
        from config import settings
        minutes = int(getattr(settings, "SESSION_FINALIZATION_MARGIN_MINUTES", 30))
    except Exception:
        minutes = 30
    return timedelta(minutes=max(0, minutes))


def session_is_final(day, now_et: datetime | None = None) -> bool:
    """True when ``day``'s regular session is COMPLETE and its daily bar has settled.

    A past trading session is always final. TODAY's session is final only once ``now``
    has passed the close by the finalization margin — the provider keeps revising the
    last bar for a few minutes after the bell, so a bar fetched in that window is a
    PARTIAL close, not a real one. A non-trading ``day`` is trivially final (it has no
    forming bar to protect)."""
    now_et = now_et or datetime.now(MARKET_TZ)
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=MARKET_TZ)
    else:
        now_et = now_et.astimezone(MARKET_TZ)
    day = normalize_session_date(day)
    today = normalize_session_date(now_et.date())
    if day < today:
        return True
    if day > today:
        return False
    if not is_trading_session(today):
        return True
    return now_et >= session_close_at(today) + _finalization_margin()


def previous_trading_session(day) -> pd.Timestamp:
    return normalize_session_date(day) - NYSE_BUSINESS_DAY


def next_trading_session_after(day) -> pd.Timestamp:
    return normalize_session_date(day) + NYSE_BUSINESS_DAY



def latest_completed_session(now_et: datetime | None = None) -> pd.Timestamp:
    now_et = now_et or datetime.now(MARKET_TZ)
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=MARKET_TZ)
    else:
        now_et = now_et.astimezone(MARKET_TZ)

    today = normalize_session_date(now_et.date())
    # "Completed" means the session's bar is FINAL (close + finalization margin), not
    # merely past the bell: the provider keeps settling the last bar for minutes after
    # the close, so treating today as complete at 16:00 would let a PARTIAL bar into the
    # cache / coverage checks / archive. session_is_final applies the margin.
    if is_trading_session(today) and session_is_final(today, now_et):
        return today
    return previous_trading_session(today)


def next_session_close(now_et: datetime | None = None) -> tuple[pd.Timestamp, datetime]:
    now_et = now_et or datetime.now(MARKET_TZ)
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=MARKET_TZ)
    else:
        now_et = now_et.astimezone(MARKET_TZ)

    today = normalize_session_date(now_et.date())
    if is_trading_session(today) and now_et < session_close_at(today):
        session = today
    else:
        session = next_trading_session_after(today)
    return session, session_close_at(session)


def market_closed_reason(now_et: datetime | None = None) -> str | None:
    now_et = now_et or datetime.now(MARKET_TZ)
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=MARKET_TZ)
    else:
        now_et = now_et.astimezone(MARKET_TZ)

    today = normalize_session_date(now_et.date())
    if not is_trading_session(today):
        return "weekend" if now_et.weekday() >= 5 else "holiday"
    if now_et.time() < REGULAR_OPEN:
        return "before_open"
    if now_et >= session_close_at(today):
        return "after_close"
    return None
