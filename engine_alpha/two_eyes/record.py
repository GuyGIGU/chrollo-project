"""The shared record of a two-eyes chart read.

A read carries concurrent parent and mini boxes, earlier boxes, dated rail
anchors, the LPS and which box it used, and the trail explaining the read.
The adapter, archive and screen share this contract. The mini belongs to the
same setup as its parent and keeps its own rails (operator ruling,
20/09/2026); the two boxes do not replace one another.

These dataclasses store facts and resolved judgments; they compute no grade.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

#: What a box is doing in this read — a closed set, owned by a module with no
#: imports so the archive can use the same tuple without importing this
#: package into the old reader's nightly path.
from engine_alpha.two_eyes_roles import ROLE_EARLIER, ROLE_MINI, ROLE_PARENT, ROLES  # noqa: E402,F401

#: Separate an absent structure from a failed read.
NO_LINES = "no lines"
READ_FAILED = "no lines, the read failed"

#: The ten words a chart can carry on the screen: ONE closed table, and each word's one home. The table is the
#: builder's (final method, point 22), approved inside his "Go!" of Sun 13/09/2026; three of its words answer
#: his own: a chart with lines and no LPS still shows ("Yes"), the buy day ("we can go with nothing"), a refused
#: chart ("lets go with not scanned"). The old engine keeps its own copy in a frozen file this package may not
#: import; a test outside the package holds the two equal. ``READ_FAILED`` is never one of them.
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

#: The words of the story (stage 5): what the drawing did against the box and its two lines. A closed set; each
#: word is his. Not here: the LPS (it is ``Read.lps``), the mini (a second box), the shakeout (parked by him,
#: Sun 13/09/2026: "we can stick with Phase C only for now").
SPRING = "spring"               # his "Phase C = Spring btw." (Mon 14/09/2026)
SPRING_TEST = "spring test"
UPTHRUST = "upthrust"
SOS = "SOS"
LAST_SUPPER = "last supper"
PHASE_D = "Phase D"
EVENT_KINDS = (SPRING, SPRING_TEST, UPTHRUST, SOS, LAST_SUPPER, PHASE_D)


def _as_day(value):
    """A plain day, or None.

    A timestamp is what a date index hands out, and it passes for a day
    (it is one, by inheritance) until something writes it down: then it
    carries a clock time the market never traded at, and the archive,
    which stores days, refuses the whole fire. Cut here, once, so every
    reader of the record gets a day.
    """
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
    #: The daily range the box was measured in, frozen at its birth — never
    #: the read day's, so a box does not change size because today was wide.
    daily_range: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "opened_day", _as_day(self.opened_day))
        object.__setattr__(self, "end_day", _as_day(self.end_day))
        if self.role not in ROLES:
            raise ValueError(f"unknown box role {self.role!r}; expected one of {ROLES}")


#: HOW the LPS sat against the mini, his three positions (Sun 13/09/2026: *"the
#: LPS read can be against it if it is inside/near it/resting on it"*): its low
#: inside the mini's band, resting on one of its lines, or near one from outside.
#: Said only of the mini (ours): the parent's read carries no word.
LPS_HOW = ("in", "on", "near")


@dataclass(frozen=True)
class Lps:
    """The last run of receding days, which box it receded inside, and — when
    that box is the mini — how its low sat against it."""
    start_day: dt.date
    end_day: dt.date
    read_against: str           # a box role; with two live boxes this is not optional
    trigger_price: Optional[float] = None
    how: Optional[str] = None   # one of LPS_HOW when read against the mini; else None

    def __post_init__(self):
        object.__setattr__(self, "start_day", _as_day(self.start_day))
        object.__setattr__(self, "end_day", _as_day(self.end_day))
        # Validated the same way a box's role is. A closed set that is checked
        # in one place and not the other is a closed set in name only.
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
    """One word of the story, as a fact: which word, the day it points at and the price there (a spring's tip, an
    upthrust's or a push's top, the day the right side opens), and around it the first day of the swing that
    makes it and its last day. Days and prices only: a bar index never leaves the reader. ``committed`` is
    False while the swing it stands on, or the swing that answers it, is still forming; ``known_day`` is the
    day it could first be said. Nothing that decides a fire reads an event."""
    kind: str
    day: dt.date
    price: float
    first_day: Optional[dt.date] = None
    last_day: Optional[dt.date] = None
    #: How big, in the unit the words are read in (a spring's depth under support, a climb over resistance,
    #: the ground a push covered, a last supper's drop). A fact for the grade, never a gate.
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
    """The grade (stage 7): his dead space and whether the base held, read on the setup's box. ``score`` runs from 0
    to 100 and ``letter`` follows it; ``empty_days`` of the base's ``base_days`` were empty his way; ``holds`` is
    False when, after THE SOS's top, the price fell under the whole base. A verdict and its facts: nothing that
    decides a fire reads it."""
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
    """One chart, read once, as of one day.

    `state` is the one word the screen shows. `failed` separates "the chart
    has no lines" from "the read crashed": they are the same sentence to a
    careless caller and completely different facts to him.
    """
    ticker: str
    as_of: Optional[dt.date] = None
    boxes: tuple = ()
    lps: Optional[Lps] = None
    trail: tuple = ()
    state: str = NO_LINES
    failed: bool = False
    refusal: Optional[str] = None
    # The read day's own close. The archive stores it as the setup's price,
    # and the forward-returns backfill scales every trigger by it — so a
    # stand-in (the resistance line was the first one) quietly regrades the
    # outcome of every fire. None until a frame has been read.
    close: Optional[float] = None
    # The story (stage 5): the events the drawing printed against the box shown. Empty until the story is read,
    # and empty again when it could not be: a word never costs a fire, so `fired` does not read this.
    events: tuple = ()
    # The number that rides BESIDE a state word that counts days ("forming N of 15": N; a run of days beyond a
    # line: its length). Never written into the word, which is one of the closed ten.
    state_days: Optional[int] = None
    # The grade (stage 7): None with no box, and None again when it could not be read: a grade never costs a
    # fire, so `fired` does not read this.
    grade: Optional[Grade] = None

    def __post_init__(self):
        # Frozen, but a list slipped in through `boxes` or `trail` would make
        # the record mutable through the back door. Coerced, not merely
        # annotated (object.__setattr__ is how a frozen dataclass does this).
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
    """A read that fell over. Counted as a failure, never as 'no lines'.

    The path a broken read takes may not break in turn: a day it cannot read
    is dropped rather than raised, so the refusal still arrives.
    """
    try:
        day = _as_day(as_of)
    except TypeError:
        day = None
    return Read(ticker=ticker, as_of=day, state=READ_FAILED, failed=True,
                refusal=why)
