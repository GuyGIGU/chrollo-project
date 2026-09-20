"""What a read of a chart IS — the record the whole rewrite fills in.

Task 5 of the two-eyes-reader build. Every later stage turns a field here from
empty to answered; none of them may change its SHAPE, because the adapter, the
archive row and the screen are all built against this from the first commit.
That is the point of writing it while it is still empty.

The shape follows his method, not the old engine's:

* a read holds a LIST of boxes, not one. The mini is a second box that lives
  at the same time as its parent — his ruling of Sun 20/09/2026, "if you are
  reffering to mini consolidations then both boxes live, they are a part of
  the same setup" — and the walk also passes boxes it considered and left
  behind, which is what `earlier` is for.
* a box carries the DAY each line was anchored, not just the price. A price
  alone cannot be redrawn once the window slides, and "did the engine open on
  his day" is unanswerable without it.
* the LPS says which box it was read against. With two live boxes, "the last
  run of receding days" is ambiguous until you say receding INSIDE WHAT.
* the trail is how the winner was chosen. He asked to see why, not just what,
  so it rides every read rather than being reconstructed on demand.

Nothing here judges. These are facts and the record of how they were found.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

#: What a box is doing in this read. A closed set: the parent is the setup's
#: own box, a mini lives inside the parent's life, and earlier is a pair the
#: walk tried and left behind.
ROLE_PARENT = "parent"
ROLE_MINI = "mini"
ROLE_EARLIER = "earlier"
ROLES = (ROLE_PARENT, ROLE_MINI, ROLE_EARLIER)

#: The state words a read can carry. The first version answers only "no lines"
#: — honestly empty beats accidentally right.
NO_LINES = "no lines"
READ_FAILED = "no lines, the read failed"


@dataclass(frozen=True)
class Line:
    """One drawn line: its price, and the day it was anchored on."""
    price: float
    anchor_day: dt.date


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
        if self.role not in ROLES:
            raise ValueError(f"unknown box role {self.role!r}; expected one of {ROLES}")


@dataclass(frozen=True)
class Lps:
    """The last run of receding days, and which box it receded inside."""
    start_day: dt.date
    end_day: dt.date
    read_against: str           # a box role; with two live boxes this is not optional
    trigger_price: Optional[float] = None

    def __post_init__(self):
        # Validated the same way a box's role is. A closed set that is checked
        # in one place and not the other is a closed set in name only.
        if self.read_against not in ROLES:
            raise ValueError(
                f"the LPS was read against {self.read_against!r}; expected one "
                f"of {ROLES}")


@dataclass(frozen=True)
class Step:
    """One step of the walk, kept so the trail can be read back."""
    stage: str
    saying: str


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

    def __post_init__(self):
        # Frozen, but a list slipped in through `boxes` or `trail` would make
        # the record mutable through the back door. Coerced, not merely
        # annotated (object.__setattr__ is how a frozen dataclass does this).
        object.__setattr__(self, "boxes", tuple(self.boxes))
        object.__setattr__(self, "trail", tuple(self.trail))

    @property
    def parent(self) -> Optional[Box]:
        """The setup's own box, or None while there are no lines."""
        return next((b for b in self.boxes if b.role == ROLE_PARENT), None)

    @property
    def mini(self) -> Optional[Box]:
        return next((b for b in self.boxes if b.role == ROLE_MINI), None)

    @property
    def fired(self) -> bool:
        """A read only fires when it has a box AND a buy to go with it."""
        return self.parent is not None and self.lps is not None \
            and self.lps.trigger_price is not None and not self.failed


def crashed(ticker: str, as_of, why: str) -> Read:
    """A read that fell over. Counted as a failure, never as 'no lines'."""
    return Read(ticker=ticker, as_of=as_of, state=READ_FAILED, failed=True,
                refusal=why)
