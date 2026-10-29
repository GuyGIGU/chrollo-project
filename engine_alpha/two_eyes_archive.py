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
import math

import pandas as pd

from engine_alpha.two_eyes_roles import ROLES, height_in_ranges

__all__ = [
    "SCREEN_KEY",
    "SCREEN_ROLES",
    "TWO_EYES_COLUMN_SQL",
    "TWO_EYES_LPS_BOXES",
    "two_eyes_archive_values",
    "two_eyes_screen_boxes",
    "volume_vs_50d",
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
    # The LPS pullback's average volume against the 50-day average ending on its
    # last day, on this reader's own LPS days: the one setup fact that separated
    # the archive's big winners (decisions.md Nulls, 2026-10-04). Archived so the
    # archive can keep measuring it after the flip (his word Mon 12/10/2026,
    # option A). A fact: never a gate, never a point.
    "two_eyes_lps_volume_ratio": "FLOAT",
    "two_eyes_clarity_json": "TEXT",
}

_DATE_COLUMNS = frozenset(
    name for name in TWO_EYES_COLUMN_SQL if name.endswith("_date"))


def _clean(value):
    """NaN and pandas' own nulls become None: the family's one producer says
    "no value" one way for every writer and every reader of the row (SQLite
    would store a bare NaN as empty too; pandas' NaT and NA would not bind)."""
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


#: The boxes the screen draws, in the order it draws them: the setup's own box, then the mini inside it. Never an
#: earlier box (build task 15, ours): the earlier boxes are each night's own telling (the known limit of Fri
#: 02/10/2026), the archive keeps none, and a screen that drew them would disagree with the archive's view of the
#: same row. The approval pack's pages still draw them.
SCREEN_ROLES = ("parent", "mini")

#: The result key the screen's ONE block rides on, from the adapter to the scan's wire (`core/pipeline/screening/
#: dashboard.py` hands it to the chart as ``two_eyes``). Not a column: the archive keeps the family. It lives here,
#: in a module the nightly path already loads, so the wire can name it without importing the new reader.
SCREEN_KEY = "_wire_two_eyes"


def two_eyes_screen_boxes(values: dict) -> list:
    """The family's boxes as the screen reads them: each line's price and the day it was anchored, the day the box
    opened and the day it ended (None while live), and how many of its own daily ranges tall it is (None without a
    stored range). Nothing the browser would have to work out.

    ``values`` is :func:`two_eyes_archive_values`' own output, so the scan's wire (built from a live result) and the
    archive's chart (built from a stored row) are shaped by ONE function from ONE family and cannot drift apart. A
    role whose two lines are not both there draws no box. The height is a ratio of two prices on one scale, so the
    archive's chart, which rescales the lines onto today's candles, keeps it as it is.
    """
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
    """The volume on ``day`` — or the average volume from ``first_day`` to
    ``day``, both included — against the 50-day average ending on ``day`` (that
    day included, as the engine's Vol_50 counts it, which is how the old
    reader's LPS read divides its pullback's volume). Volume at a key point, a
    spring's day or an LPS pullback's run of days: ONE measure (EC-3), shared by
    the screen's panel and the family's ``two_eyes_lps_volume_ratio`` so the two
    cannot disagree. It lives here, beside the column it fills, because the old
    chart reader's files are frozen and both callers already load this module.
    A fact, never a gate or a point. None when a day is not in the frame, the
    run ends before it starts, or the average is unreadable."""
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
