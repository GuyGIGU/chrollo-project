"""The record of one read: ``Read``, ``Box``, ``Lps``, ``Event``, ``Grade`` and the trail's ``Step``; the roles a
box can hold; the ten state words; the words of the story. Facts and dated words — nothing here decides a fire.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

#: The roles a box can hold in a read: the setup's own box, the mini inside it, a pair the walk left behind.
ROLE_PARENT = "parent"
ROLE_MINI = "mini"
ROLE_EARLIER = "earlier"
ROLES = (ROLE_PARENT, ROLE_MINI, ROLE_EARLIER)

def height_in_ranges(R, S, unit):
    """The box's height in its own daily range, the ONE place it is read; None when the unit is missing or not a number."""
    try:
        unit = float(unit)
    except (TypeError, ValueError):
        return None
    if unit != unit or unit <= 0 or unit in (float("inf"), float("-inf")):
        return None
    return float(R - S) / unit


#: Separate an absent structure from a failed read.
NO_LINES = "no lines"
READ_FAILED = "no lines, the read failed"

#: The ten words a chart can carry on the screen: ONE closed table, each word's one home. ``READ_FAILED`` is never
#: one of them.
FIRED = "fired"
CROSSED = "crossed"
LINES_NO_LPS = "lines, no LPS yet"
FORMING = "forming N of 15"
ROOT_CANDIDATE = "root candidate, unconfirmed"
BEYOND_R = "beyond R, undetermined"
UNDER_S = "under S, undetermined"
BROKE_DOWN = "broke down"
NOT_SCANNED = "not scanned"
STATE_WORDS = (FIRED, CROSSED, LINES_NO_LPS, FORMING, ROOT_CANDIDATE, BEYOND_R, UNDER_S, BROKE_DOWN,
               NOT_SCANNED, NO_LINES)

#: The words of the story (stage 5): what the drawing did against the box and its two lines. A closed set, each
#: word his; the LPS is ``Read.lps`` and the mini a second box, not words.
SPRING = "spring"               # his "Phase C = Spring btw." (Mon 14/09/2026)
SPRING_TEST = "spring test"
UPTHRUST = "upthrust"
SOS = "SOS"
LAST_SUPPER = "last supper"
PHASE_D = "Phase D"
EVENT_KINDS = (SPRING, SPRING_TEST, UPTHRUST, SOS, LAST_SUPPER, PHASE_D)

def _as_day(value):
    """A plain day, or None: a timestamp is cut to its date here, once, so no clock time ever reaches the archive."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):      # before date: a timestamp is both
        return value.date()
    if isinstance(value, dt.date):
        return value
    raise TypeError(f"expected a day, got {value!r}")

@dataclass(frozen=True)
class Line:
    """One drawn line: its price, and the day it was anchored on."""
    price: float
    anchor_day: dt.date

    def __post_init__(self):
        object.__setattr__(self, "anchor_day", _as_day(self.anchor_day))

@dataclass(frozen=True)
class Box:
    """A pair of lines with a life. `end_day` is None while it is still live."""
    resistance: Line
    support: Line
    opened_day: dt.date
    end_day: Optional[dt.date] = None
    role: str = ROLE_PARENT
    #: The daily range the box was measured in, frozen at its birth, never the read day's.
    daily_range: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "opened_day", _as_day(self.opened_day))
        object.__setattr__(self, "end_day", _as_day(self.end_day))
        if self.role not in ROLES:
            raise ValueError(f"unknown box role {self.role!r}; expected one of {ROLES}")

#: HOW the LPS sat against the mini: its low inside the mini's band, resting on one of its lines, or near one from
#: outside. Said of the mini only; the parent's read carries no word.
LPS_HOW = ("in", "on", "near")

@dataclass(frozen=True)
class Lps:
    """The last run of receding days, the box it receded inside and, for the mini, how its low sat against it."""
    start_day: dt.date
    end_day: dt.date
    read_against: str           # a box role; with two live boxes this is not optional
    trigger_price: Optional[float] = None
    how: Optional[str] = None   # one of LPS_HOW when read against the mini; else None

    def __post_init__(self):
        object.__setattr__(self, "start_day", _as_day(self.start_day))
        object.__setattr__(self, "end_day", _as_day(self.end_day))
        if self.read_against not in ROLES:
            raise ValueError(
                f"the LPS was read against {self.read_against!r}; expected one "
                f"of {ROLES}")
        if self.how is not None and self.how not in LPS_HOW:
            raise ValueError(f"the LPS sat {self.how!r} against its box; expected one of {LPS_HOW}")
        if self.how is not None and self.read_against != ROLE_MINI:
            raise ValueError(f"how the LPS sat is said of the mini only, not of {self.read_against!r}")

@dataclass(frozen=True)
class Step:
    """One step of the walk, kept so the trail can be read back."""
    stage: str
    saying: str

@dataclass(frozen=True)
class Event:
    """One word of the story as a fact: the word, the day and price it points at, the first and last day of the swing
    that makes it. ``committed`` is False while that swing, or its answer, is still forming; ``known_day`` is the day
    it could first be said."""
    kind: str
    day: dt.date
    price: float
    first_day: Optional[dt.date] = None
    last_day: Optional[dt.date] = None
    #: How big, in the unit the words are read in. A fact for the grade, never a gate.
    size: Optional[float] = None
    committed: bool = False
    known_day: Optional[dt.date] = None
    note: str = ""

    def __post_init__(self):
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event {self.kind!r}; expected one of {EVENT_KINDS}")
        for name in ("day", "first_day", "last_day", "known_day"):
            object.__setattr__(self, name, _as_day(getattr(self, name)))
        if self.day is None:
            raise TypeError("an event points at a day")

#: The grade's letters, best first (stage 7). The cuts on the score are the reader's own numbers.
GRADE_LETTERS = ("S", "A", "B", "C")

@dataclass(frozen=True)
class Grade:
    """The grade (stage 7): ``score`` 0 to 100 and its ``letter``; ``empty_days`` of ``base_days`` were empty his way;
    ``holds`` is False when, after the SOS's top, the price fell under the whole base."""
    score: float
    letter: str
    empty_days: int
    base_days: int
    holds: bool
    clarity: Optional[dict] = None

    def __post_init__(self):
        if self.letter not in GRADE_LETTERS:
            raise ValueError(f"unknown grade letter {self.letter!r}; expected one of {GRADE_LETTERS}")
        if not 0.0 <= self.score <= 100.0:
            raise ValueError(f"a grade runs from 0 to 100, not {self.score!r}")
        if not 0 <= self.empty_days <= self.base_days:
            raise ValueError(f"{self.empty_days} empty days of a base of {self.base_days}")

@dataclass(frozen=True)
class Read:
    """One chart, read once, as of one day. ``state`` is the one word the screen shows; ``failed`` separates "the
    chart has no lines" from "the read crashed"."""
    ticker: str
    as_of: Optional[dt.date] = None
    boxes: tuple = ()
    lps: Optional[Lps] = None
    trail: tuple = ()
    state: str = NO_LINES
    failed: bool = False
    refusal: Optional[str] = None
    # The read day's own close: the archive stores it as the setup's price and the backfill scales every trigger by it.
    close: Optional[float] = None
    # The story's events; empty when it could not be read: a word never costs a fire, so `fired` does not read this.
    events: tuple = ()
    # The number beside a state word that counts days ("forming N of 15": N); never written into the word.
    state_days: Optional[int] = None
    # None with no box, and when it could not be read: a grade never costs a fire, so `fired` does not read this.
    grade: Optional[Grade] = None

    def __post_init__(self):
        # coerced, not merely annotated: a list through `boxes` or `trail` would make the record mutable
        object.__setattr__(self, "boxes", tuple(self.boxes))
        object.__setattr__(self, "trail", tuple(self.trail))
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "as_of", _as_day(self.as_of))

    @property
    def parent(self) -> Optional[Box]:
        """The setup's own box, or None while there are no lines."""
        return next((b for b in self.boxes if b.role == ROLE_PARENT), None)

    @property
    def mini(self) -> Optional[Box]:
        return next((b for b in self.boxes if b.role == ROLE_MINI), None)

    @property
    def fired(self) -> bool:
        """A read only fires when it has a box AND a buy to go with it. It reads no event and no state word."""
        return self.parent is not None and self.lps is not None \
            and self.lps.trigger_price is not None and not self.failed

def crashed(ticker: str, as_of, why: str) -> Read:
    """A read that fell over: counted as a failure, never as 'no lines'; a day it cannot read is dropped, not raised."""
    try:
        day = _as_day(as_of)
    except TypeError:
        day = None
    return Read(ticker=ticker, as_of=day, state=READ_FAILED, failed=True,
                refusal=why)
