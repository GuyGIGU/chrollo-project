"""The two-eyes reader's archive column family — ONE producer, three writers.

Task 6 of the two-eyes-reader build. The old engine stores a setup's geometry
as a price pair plus BAR OFFSETS into the frame it was read from. That works
for exactly as long as the frame does: once the two-year window slides past
the base, the offsets point at nothing and the drawing cannot be recovered.
And there is nowhere at all to put a second box, so his mini — which is not a
different setup, it is the same one read closer in — has never been storable.

This family fixes both, dark, before a single new-reader row exists:

* **two boxes of the same shape**, parent and mini, each carrying both lines
  as a price AND the DAY that line was anchored, the day the box opened, a
  nullable day it ended, and the daily range it was born with. A day survives
  any window;
* **which box the LPS was read against**, as a closed set, because with two
  live boxes "the LPS" is ambiguous and an ambiguous archive column is worse
  than an absent one;
* **whether the setup had a mini at all**, in THREE states — yes, no, and
  "the reader that wrote this row never looked", which is every row in the
  archive today and every row the old reader writes tomorrow.

Everything here is NULL under the old reader. NULL, not 0.0 and not "": a
zero price is a made-up price, and a made-up number in an archive column is
indistinguishable from a measured one forever after. Three writers reach this
table (the live scan, the archive seed, and the backend's manual route) and
EC-30 requires the family to ride all three through this one producer; a test
names each writer and fails at add time if one is left out.
"""
from __future__ import annotations

import datetime

import pandas as pd

from engine_alpha.two_eyes_roles import ROLES

__all__ = [
    "TWO_EYES_COLUMN_SQL",
    "TWO_EYES_LPS_BOXES",
    "two_eyes_archive_values",
]

#: The roles a box can hold, and the closed set the LPS column is drawn from.
#: THE record's own tuple, not a copy typed out again (EC-33): a word added to
#: the record would otherwise be accepted by the reader and refused here,
#: costing every fire that used it. EC-22 wants a committed test for each,
#: and the table's fresh-database CHECK is pinned to this same tuple.
TWO_EYES_LPS_BOXES = ROLES

#: One box's worth of columns, as suffix -> SQL type. Both boxes take the
#: same shape on purpose: the mini is read by the same eye as its parent, so
#: anything asked of one can be asked of the other.
_PER_BOX: dict[str, str] = {
    "r_price": "FLOAT",         # the resistance line
    "r_anchor_date": "TEXT",    # and the DAY it was anchored on
    "s_price": "FLOAT",         # the support line
    "s_anchor_date": "TEXT",    # and its day
    "opened_date": "TEXT",      # the box's first day
    "end_date": "TEXT",         # the day it stopped being a box; NULL = still live
    "daily_range": "FLOAT",     # the range it was born with, frozen
}

TWO_EYES_COLUMN_SQL: dict[str, str] = {
    **{f"two_eyes_{box}_{part}": sql
       for box in ("parent", "mini")
       for part, sql in _PER_BOX.items()},
    # Which of the live boxes the receding run was read inside.
    "two_eyes_lps_read_against": "TEXT",
    # 1 / 0 / NULL — and NULL is not "no".
    "two_eyes_has_mini": "INTEGER",
}

_DATE_COLUMNS = frozenset(
    name for name in TWO_EYES_COLUMN_SQL if name.endswith("_date"))


def _clean(value):
    """NaN and pandas' own nulls become None. A NaN that reaches SQLite binds
    as a float and reads back as a number, so it must die here."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):       # arrays, dates, anything exotic
        pass
    return value


def two_eyes_archive_values(get, *, prefixed: bool) -> dict:
    """Row -> ``{column: value}`` for every column in the family.

    ``get`` is the row's own lookup (``row.get``), ``prefixed`` picks the live
    result's ``_``-prefixed keys over the seed's bare ones — the same contract
    every other family producer in this tree takes.

    All-or-nothing is NOT the rule here, unlike the strategy family: a setup
    with no mini legitimately has a parent and no second box, so each half
    stands alone. What IS the rule is that an absent measure is NULL.
    """
    out: dict = {}
    for column, sql_type in TWO_EYES_COLUMN_SQL.items():
        value = _clean(get(("_" + column) if prefixed else column))
        if value is None:
            out[column] = None
            continue
        if column == "two_eyes_lps_read_against":
            value = str(value)
            if value not in TWO_EYES_LPS_BOXES:
                # LOUD, not coerced. This column is read as a closed set by
                # everything downstream; a fourth word silently stored is a
                # bug that surfaces a month later as an unreadable row.
                raise ValueError(
                    f"the LPS was read against {value!r}, which is not one of "
                    f"{TWO_EYES_LPS_BOXES}")
        elif column == "two_eyes_has_mini":
            value = _yes_or_no(value)
        elif sql_type == "FLOAT":
            value = float(value)
        elif column in _DATE_COLUMNS:
            value = _day(column, value)
        out[column] = value
    return out


def _yes_or_no(value) -> int:
    """1 or 0, and nothing else. ``int()`` would have stored a 2 as a 2 and
    truncated 0.7 to 0 — "no mini" — which is a different fact made up out of
    a bad number. Refused instead, like a word off the closed set."""
    if value in (True, False, 0, 1):          # bools, ints, floats, numpy scalars
        return int(value)
    raise ValueError(f"has-a-mini must be yes or no, got {value!r}")


def _day(column: str, value) -> str:
    """A day as YYYY-MM-DD — the one way every other date column in this table
    is written, so the archive reads the same whichever reader wrote the row.

    A timestamp is cut to its day rather than stored with a clock time the
    market never traded at; a string must BE a day. Anything else is refused:
    a column named for a day that holds something else cannot be redrawn,
    which is the whole reason this family carries days.
    """
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
