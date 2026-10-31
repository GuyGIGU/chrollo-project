"""The alpha reader's archive column family, through ONE producer for its three writers (the live scan, the seed, the
backend's manual route): two boxes of one shape (parent and mini) as prices and the DAYS they were anchored, which box
the LPS was read against, whether the setup had a mini (1 / 0 / NULL = never looked), the LPS volume ratio and the
clarity JSON. An absent measure is NULL, never 0.0 and never "".
"""
from __future__ import annotations

import datetime
import math

import pandas as pd

from engine_alpha.record import ROLES, height_in_ranges

__all__ = [
    "SCREEN_KEY",
    "SCREEN_ROLES",
    "ALPHA_COLUMN_SQL",
    "ALPHA_LPS_BOXES",
    "alpha_archive_values",
    "alpha_screen_boxes",
    "volume_vs_50d",
]

#: The roles a box can hold, the closed set the LPS column is drawn from: THE record's own tuple, not a copy.
ALPHA_LPS_BOXES = ROLES

#: One box's worth of columns, suffix -> SQL type; both boxes take the same shape.
_PER_BOX: dict[str, str] = {
    "r_price": "FLOAT",         # the resistance line
    "r_anchor_date": "TEXT",    # and the DAY it was anchored on
    "s_price": "FLOAT",         # the support line
    "s_anchor_date": "TEXT",    # and its day
    "opened_date": "TEXT",      # the box's first day
    "end_date": "TEXT",         # the day it stopped being a box; NULL = still live
    "daily_range": "FLOAT",     # the range it was born with, frozen
}

ALPHA_COLUMN_SQL: dict[str, str] = {
    **{f"two_eyes_{box}_{part}": sql
       for box in ("parent", "mini")
       for part, sql in _PER_BOX.items()},
    # Which of the live boxes the receding run was read inside.
    "two_eyes_lps_read_against": "TEXT",
    # 1 / 0 / NULL — and NULL is not "no".
    "two_eyes_has_mini": "INTEGER",
    # The LPS pullback's volume against the 50-day average, on this reader's own LPS days: a fact, never a gate.
    "two_eyes_lps_volume_ratio": "FLOAT",
    "two_eyes_clarity_json": "TEXT",
}

_DATE_COLUMNS = frozenset(
    name for name in ALPHA_COLUMN_SQL if name.endswith("_date"))


def _clean(value):
    """NaN and pandas' own nulls become None: the family says "no value" one way for every writer and reader."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):       # arrays, dates, anything exotic
        pass
    return value


def alpha_archive_values(get, *, prefixed: bool) -> dict:
    """Row -> ``{column: value}`` for every column in the family; ``get`` is the row's own lookup, ``prefixed`` picks the
    live result's ``_``-prefixed keys over the seed's bare ones. Each box stands alone; an absent measure is NULL."""
    out: dict = {}
    for column, sql_type in ALPHA_COLUMN_SQL.items():
        value = _clean(get(("_" + column) if prefixed else column))
        if value is None:
            out[column] = None
            continue
        if column == "two_eyes_lps_read_against":
            value = str(value)
            if value not in ALPHA_LPS_BOXES:
                # LOUD, not coerced: a fourth word silently stored is an unreadable row a month later.
                raise ValueError(
                    f"the LPS was read against {value!r}, which is not one of "
                    f"{ALPHA_LPS_BOXES}")
        elif column == "two_eyes_has_mini":
            value = _yes_or_no(value)
        elif sql_type == "FLOAT":
            value = float(value)
        elif column in _DATE_COLUMNS:
            value = _day(column, value)
        out[column] = value
    return out


#: The boxes the screen draws, in order: the setup's own box, then the mini inside it; never an earlier box.
SCREEN_ROLES = ("parent", "mini")

#: The result key the screen's ONE block rides on, from the adapter to the scan's wire; not a column.
SCREEN_KEY = "_wire_alpha"


def alpha_screen_boxes(values: dict) -> list:
    """The family's boxes as the screen reads them: each line's price and anchor day, the opened and end days, the height
    in its own ranges. ``values`` is :func:`alpha_archive_values`' output, so the wire and the archive's chart cannot drift."""
    boxes = []
    for role in SCREEN_ROLES:
        def part(name, role=role):
            return values.get(f"two_eyes_{role}_{name}")
        if part("r_price") is None or part("s_price") is None:
            continue
        unit = part("daily_range")
        boxes.append({"role": role,
                      "r": part("r_price"), "r_day": part("r_anchor_date"),
                      "s": part("s_price"), "s_day": part("s_anchor_date"),
                      "opened": part("opened_date"), "end": part("end_date"),
                      "ranges_tall": height_in_ranges(part("r_price"), part("s_price"), unit)})
    return boxes


def _day_position(df, day):
    """``day``'s row in the frame, or None when it is not there (exactly once)."""
    if not day:
        return None
    try:
        pos = df.index.get_loc(pd.Timestamp(day))
    except (KeyError, TypeError, ValueError):
        return None
    return pos if isinstance(pos, int) else None


def volume_vs_50d(df, day, first_day=None):
    """The volume on ``day`` — or the average from ``first_day`` to ``day``, both included — against the 50-day average
    ending on ``day``: ONE measure for the screen's panel and the family's column. None when a day is not in the frame."""
    pos = _day_position(df, day)
    start = pos if first_day is None else _day_position(df, first_day)
    if pos is None or start is None or start > pos:
        return None
    volume = float(df["Volume"].iloc[start: pos + 1].mean())
    average = float(df["Volume"].iloc[max(0, pos - 49): pos + 1].mean())
    if not (math.isfinite(volume) and math.isfinite(average)) or average <= 0:
        return None
    return round(volume / average, 2)


def _yes_or_no(value) -> int:
    """1 or 0, and nothing else: ``int()`` would have stored a 2, or truncated 0.7 into a made-up "no"."""
    if value in (True, False, 0, 1):          # bools, ints, floats, numpy scalars
        return int(value)
    raise ValueError(f"has-a-mini must be yes or no, got {value!r}")


def _day(column: str, value) -> str:
    """A day as YYYY-MM-DD: a timestamp is cut to its day, a string must BE a day, anything else is refused."""
    if isinstance(value, datetime.datetime):  # before date: it is a subclass
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    raise ValueError(f"{column} must be a day, got {value!r}")
