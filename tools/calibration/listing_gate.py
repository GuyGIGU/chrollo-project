"""The listing gate: on his 35 drawings, does the two-legs walk LIST his pair, from which end of a trend, and
would his pair WIN — measured on the new reader's own line BEFORE the election is coded.

Task 9 of the two-eyes-reader build. Every later stage inherits its start from the end of the trend, so this
measures, per drawing and at three far-view floors (1.5, 2.5 and 3.0 daily ranges):

* the trend ends the far view reports, and which of them fall INSIDE his drawn box (a far floor too fine reads
  the box's own legs as trends, and a latest-first rule would start walking past his pair);
* whether the trend before his box is reported as a run at all, and how far before his first anchor it ended;
* whether his two anchors are turns of the fine line, to the cent, and which trend end's walk LISTS his pair
  after how many moves of the two legs ("I move one pair right until I find it, not only a single time. -> one
  line can stay on its anchor while the other moves, but they are connected like 2 lets placing one in front
  of the other", Sun 20/09/2026: each move takes ONE foot one turn of its own kind to the right);
* the day his pair became a box, his way: both lines answered by a later swing that reached the line's area and
  turned back, however far it poked (a spring answers at support), and fifteen trading days from the first
  anchor ("Lets go with 15 days", Sat 12/09/2026) — the later of the two;
* day by day from his first anchor to his last receding day, whether his pair WON among every pair the walk
  lists, under both election orders — the day the pair BECAME a box, or the earliest opening — with a chance
  column (the winner's two lines within half a daily range of his).

No engine rule is coded here: the line is the reader's (stage 1), the run reader is the copied one, and the
walk, the answering and the two orders are measurements written as pure functions so a hand-built line can
reason about each rule before his 35 are trusted to it (``tests/tooling/test_listing_gate.py``).

Offline, read-only, sidecars only: it reads the frozen as-drawn frames and writes to a directory you name.

    python -m tools.calibration.listing_gate                      # the board
    python -m tools.calibration.listing_gate --pages OUT          # the board AND one OHLC page per drawing
    python -m tools.calibration.listing_gate --pages OUT --floor 2.5
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import textwrap
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha.two_eyes import frame as two_eyes_frame  # noqa: E402
from engine_alpha.two_eyes import line as two_eyes_line  # noqa: E402
from engine_alpha.two_eyes import method_numbers as M  # noqa: E402
from engine_alpha.two_eyes.runs import runs_on_the_line  # noqa: E402
from tools.calibration.yardstick import his_last_lps_day, rails_close  # noqa: E402
from tools.regression.marks_corpus import load_corpus, setup_key  # noqa: E402
from core.calibration.replay import fixture_frame, load_sealed_fixture  # noqa: E402

#: The three far floors the plan asks the gate to measure (task 8 left the floor a parameter).
FAR_FLOORS = (1.5, 2.5, 3.0)

#: His rail area, the reader's own number: "rail area is about half a daily range".
AREA_RANGES = M.LINE_WORD_AREA_ATR

#: "Lets go with 15 days" (Sat 12/09/2026): the box needs fifteen trading days from its first anchor, the
#: anchor day being day one.
BOX_DAYS = 15

#: Ours, measurement bounds, recorded in the decisions record with the task:
#: a turn of the right kind within this many trading days of his anchor day is looked at as his anchor ...
ANCHOR_DAYS_APART = 3
#: ... and one whose price is within this many daily ranges of his is reported as NEAR, never counted as his
#: (his line is the anchor day's high or low to the cent; a near turn is the line's own reading of that swing).
NEAR_RANGES = 0.1
#: How many turns apart a candidate pair's two feet may be for the WON columns (his widest, ROIV, has five
#: turns between its anchors); the pair AT the trend end is always a candidate, whatever its reaction's length.
FEET_APART_MAX = 6
#: "The trend before his box": a run whose climax fell within two trading weeks before his first anchor.
NEAR_TREND_DAYS = 10
#: The second WON block sets aside pairs shorter than this, in their own unit: his "huge spread" word ("answer
#: a.", Sun 20/09/2026: huge against the box itself, bars almost as tall as the gap between the lines). His
#: own 35 pairs are 1.15 to 3.27 ranges tall, so none of his is set aside.
TALL_RANGES = 1.0

ORDERS = ("became", "opening", "walk")
ORDER_WORDS = {"became": "became a box first, then the earlier opening, then the tighter",
               "opening": "the earliest opening, then the tighter",
               "walk": "became a box first, then the earlier opening, then the WALK's order, then the tighter"}
POOLS = ("all", "tall", "extremes")
POOL_WORDS = {"all": "every pair the walk listed",
              "tall": f"pairs at least {TALL_RANGES:g} daily range tall (his 'huge spread' word)",
              "extremes": "tall pairs whose two lines are the extremes of the turns between their anchors"}


def _date(value) -> Optional[dt.date]:
    if value is None or isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


# --------------------------------------------------------------------------- #
# The measurements — pure functions of the line                               #
# --------------------------------------------------------------------------- #
def known_by(turns, bar: int) -> list:
    """The turns committed by ``bar``'s close: what a reader standing on that day has (the line is causal,
    task 8, so this equals the line built on the frame cut at that day)."""
    return [t for t in turns if t.knowable_bar is not None and t.knowable_bar <= bar]


def trend_ends(far_turns) -> list:
    """Every run of the far view whose reaction is decided, oldest first — the copied run reader on the
    committed turns; the forming turn at the edge decides nothing."""
    committed = [t for t in far_turns if t.knowable_bar is not None]
    return runs_on_the_line([(t.bar, t.kind, t.price, t.knowable_bar) for t in committed])


def split_by_his_box(ends: list, first_anchor_bar: int, last_bar: int) -> dict:
    """Where each trend end's climax fell against his box: before it (at his first anchor counts as before, and
    is also listed under "at"), inside it (after his first anchor, up to his last receding day), or after."""
    return {
        "before": [e for e in ends if e["climax_bar"] <= first_anchor_bar],
        "at": [e for e in ends if e["climax_bar"] == first_anchor_bar],
        "inside": [e for e in ends if first_anchor_bar < e["climax_bar"] <= last_bar],
        "after": [e for e in ends if e["climax_bar"] > last_bar],
    }


def _feet(turns, end: dict) -> Optional[tuple]:
    """A trend end's two feet as fine-line indices, (R foot, S foot): a buying climax is the R foot and its
    reaction low the S foot; a selling climax the mirror. The reaction foot is the one read on the LINE
    (``line_feet``, set by ``with_line_feet``) when the end carries it — the far view's own reaction low
    overshoots his on most drawings, its smaller swings being folded away — else the far view's. The far
    view's turns ARE fine turns (nested, task 8), so both are found; None only on a line that is not the far
    view's own."""
    if end.get("line_feet") is not None:
        return end["line_feet"]
    where = {(t.bar, t.kind): i for i, t in enumerate(turns)}
    if end["kind"] == "BC":
        r, s = where.get((end["climax_bar"], "peak")), where.get((end["ar_bar"], "valley"))
    else:
        s, r = where.get((end["climax_bar"], "valley")), where.get((end["ar_bar"], "peak"))
    if r is None or s is None:
        return None
    return r, s


def with_line_feet(end: dict, turns, ranges) -> dict:
    """The trend end with its pair read on the line: the climax, and the reaction by point 4's rule on the
    fine turns with the climax bar's own end left out and undercuts inside the area read as the same low (the
    area in the climax day's range). A reaction the line has not decided leaves the far view's feet."""
    pair = end_pair_on_the_line(turns, end, own_end_left_out=True,
                                area=AREA_RANGES * float(ranges[end["climax_bar"]]))
    return {**end, "line_feet": pair}


def _reaction_within_area(tup, climax: int, direction: int, area: float) -> Optional[int]:
    """Point 4's reaction rule with his rail area: a later low that undercuts the reaction low by LESS than the
    area is the same low (a spring, an event on the box), not a new reaction low; one that undercuts by more
    moves the reaction low to it; a higher low decides the reaction. Mirror for a selling climax."""
    want = "valley" if direction > 0 else "peak"
    cand = None
    for j in range(climax + 1, len(tup)):
        if tup[j][1] != want:
            continue
        if tup[j][3] is None:
            return None                                   # the forming turn decides nothing yet
        if cand is None:
            cand = j
            continue
        beyond = tup[cand][2] - tup[j][2] if direction > 0 else tup[j][2] - tup[cand][2]
        if beyond > area:
            cand = j                                      # a new low, beyond the area
        else:
            return cand                                   # a higher low, or an undercut inside the area
    return None


def reaction_on_the_line(turns, end: dict, own_end_left_out: bool = False,
                         area: Optional[float] = None) -> Optional[int]:
    """The trend end's reaction read on the FINE line: from its climax, the lowest committed valley before the
    first higher low (the mirror for a selling climax) — point 4's rule, the copied ``_reaction``, on the fine
    turns instead of the far view's. With ``own_end_left_out`` a valley the climax bar itself carries (a wide
    bar's own low) is skipped, so the reaction starts on the bars after it. With ``area`` (a price) an undercut
    smaller than the area is the same low. The fine index, or None while the reaction is undecided."""
    from engine_alpha.two_eyes.runs import _reaction

    kind = "peak" if end["kind"] == "BC" else "valley"
    climax = next((i for i, t in enumerate(turns) if t.bar == end["climax_bar"] and t.kind == kind), None)
    if climax is None:
        return None
    tup = [(t.bar, t.kind, t.price, t.knowable_bar) for t in turns]
    dropped = None
    if own_end_left_out and climax + 1 < len(tup) and tup[climax + 1][0] == tup[climax][0]:
        dropped = climax + 1
        tup = tup[:dropped] + tup[dropped + 1:]
    direction = 1 if end["kind"] == "BC" else -1
    got = _reaction(tup, climax, direction) if area is None else _reaction_within_area(tup, climax, direction, area)
    if got is None:
        return None
    return got + 1 if dropped is not None and got >= dropped else got


def end_pair_on_the_line(turns, end: dict, own_end_left_out: bool = False,
                         area: Optional[float] = None) -> Optional[tuple]:
    """The pair the trend end itself makes when its reaction is read on the fine line: (R index, S index) —
    the climax and its reaction low for a buying climax, the reaction top and the climax for a selling one."""
    reaction = reaction_on_the_line(turns, end, own_end_left_out, area)
    if reaction is None:
        return None
    kind = "peak" if end["kind"] == "BC" else "valley"
    climax = next(i for i, t in enumerate(turns) if t.bar == end["climax_bar"] and t.kind == kind)
    return (climax, reaction) if end["kind"] == "BC" else (reaction, climax)


def extremes_between(turns, r_index: int, s_index: int) -> bool:
    """Each of the pair's lines is the extreme of the turns between its two anchors: no peak between them above
    R, no valley between them below S — the two legs stand on one stride of ground."""
    lo, hi = sorted((r_index, s_index))
    R, S = turns[r_index].price, turns[s_index].price
    return not any((t.kind == "peak" and t.price > R) or (t.kind == "valley" and t.price < S)
                   for t in turns[lo + 1:hi])


def walk_to(turns, end: dict, r_index: int, s_index: int) -> Optional[dict]:
    """The moves of the two legs from a trend end's pair to the pair (r_index, s_index): each move takes one
    foot to the next turn of its own kind on the right. None when a foot would have to move left."""
    feet = _feet(turns, end)
    if feet is None or r_index < feet[0] or s_index < feet[1]:
        return None
    r_moves = sum(1 for i in range(feet[0] + 1, r_index + 1) if turns[i].kind == "peak")
    s_moves = sum(1 for i in range(feet[1] + 1, s_index + 1) if turns[i].kind == "valley")
    return {"r_moves": r_moves, "s_moves": s_moves, "steps": r_moves + s_moves}


def listing(turns, ends: list, r_index: int, s_index: int) -> dict:
    """The latest trend end whose walk reaches his pair, and the moves it takes; ``by_latest`` says whether
    that is the latest trend end of all — what a latest-first rule would start from."""
    for k in range(len(ends) - 1, -1, -1):
        walk = walk_to(turns, ends[k], r_index, s_index)
        if walk is not None:
            return {"by": ends[k], "by_latest": k == len(ends) - 1, **walk}
    return {"by": None, "by_latest": False, "steps": None, "r_moves": None, "s_moves": None}


def anchor_turns(turns, r_bar: int, s_bar: int, r_price: float, s_price: float, unit: float) -> dict:
    """His two anchors on the line. ``exact``: a turn of the right kind on his day at his price to the cent.
    ``price``: his price to the cent on a turn within three trading days (his click on the second of two
    equal highs). ``near``: a turn within three days whose price is within a tenth of a range of his — the
    line's own reading of that swing, reported and never counted as his line. Else None, and ``why`` names
    what the line has instead."""
    out = {"R": None, "S": None, "r_match": None, "s_match": None, "why": None}
    notes = []
    for rail, kind, bar, price in (("R", "peak", r_bar, r_price), ("S", "valley", s_bar, s_price)):
        slot = rail.lower() + "_match"
        near = [i for i, t in enumerate(turns) if t.kind == kind and abs(t.bar - bar) <= ANCHOR_DAYS_APART]
        same_price = [i for i in near if abs(turns[i].price - price) < 0.005]
        exact = [i for i in same_price if turns[i].bar == bar]
        if exact:
            out[rail], out[slot] = exact[0], "exact"
            continue
        if same_price:
            i = min(same_price, key=lambda i: abs(turns[i].bar - bar))
            out[rail], out[slot] = i, "price"
            notes.append(f"his {rail} day carries no {kind}; the line's {price:.2f} is on "
                         f"{turns[i].day:%a %d/%m/%Y}")
            continue
        if not near:
            notes.append(f"no {kind} of the line within {ANCHOR_DAYS_APART} trading days of his {rail} day")
            continue
        i = min(near, key=lambda i: (abs(turns[i].price - price), abs(turns[i].bar - bar)))
        off = abs(turns[i].price - price) / unit
        if off <= NEAR_RANGES:
            out[rail], out[slot] = i, "near"
            notes.append(f"his {rail} {price:.2f} is not a turn of the line; its nearest {kind} is "
                         f"{turns[i].price:.2f} on {turns[i].day:%a %d/%m/%Y}, {off:.2f} ranges off (NEAR)")
        else:
            notes.append(f"his {rail} {price:.2f} is not a turn of the line; its nearest {kind} is "
                         f"{turns[i].price:.2f} on {turns[i].day:%a %d/%m/%Y}, {off:.2f} ranges off")
    out["why"] = " · ".join(notes) or None
    return out


def answered(turns, ranges, r_index: int, s_index: int) -> dict:
    """The pair's two lines answered his way, and the day it became a box.

    A line is answered by the first later committed swing that reached its area (half a daily range, the
    pair's OWN unit: the range of its second anchor's day) and turned back, however far it poked: a peak at or
    above R minus the area, a valley at or below S plus the area (the spring). Each answer is known on the
    close that committed that turn. ``complete`` is the later of the two; ``fifteenth`` the pair's fifteenth
    trading day from its first anchor; ``birth`` the later of those — None until both lines are answered.
    """
    R, S = turns[r_index].price, turns[s_index].price
    opening = min(turns[r_index].bar, turns[s_index].bar)
    second = max(turns[r_index].bar, turns[s_index].bar)
    unit = float(ranges[second])
    area = AREA_RANGES * unit
    out = {"R": None, "S": None, "r_known": None, "s_known": None, "unit": unit,
           "fifteenth": opening + BOX_DAYS - 1, "complete": None, "birth": None}
    for i in range(max(r_index, s_index) + 1, len(turns)):
        t = turns[i]
        if t.knowable_bar is None:
            break                                     # the forming turn has not turned back yet
        if out["R"] is None and t.kind == "peak" and t.price >= R - area:
            out["R"], out["r_known"] = i, t.knowable_bar
        if out["S"] is None and t.kind == "valley" and t.price <= S + area:
            out["S"], out["s_known"] = i, t.knowable_bar
        if out["R"] is not None and out["S"] is not None:
            break
    if out["R"] is not None and out["S"] is not None:
        out["complete"] = max(out["r_known"], out["s_known"])
        out["birth"] = max(out["complete"], out["fifteenth"])
    return out


@dataclass(frozen=True)
class Pair:
    """One candidate pair of the walk: its two feet, its lines, its own unit, and the day it became a box."""
    name: str
    r_index: int
    s_index: int
    R: float
    S: float
    opening_bar: int
    second_bar: int
    unit: float
    birth_bar: Optional[int]
    r_known: Optional[int]
    s_known: Optional[int]
    position: Optional[int] = None       # the two legs' moves from the trend end's pair to this one

    @property
    def height(self) -> float:
        return self.R - self.S


def _pair(turns, ranges, i: int, j: int, position: Optional[int] = None) -> Pair:
    a = answered(turns, ranges, i, j)
    return Pair(name=f"{turns[i].day:%d/%m}/{turns[j].day:%d/%m}", r_index=i, s_index=j,
                R=turns[i].price, S=turns[j].price,
                opening_bar=min(turns[i].bar, turns[j].bar), second_bar=max(turns[i].bar, turns[j].bar),
                unit=a["unit"], birth_bar=a["birth"], r_known=a["r_known"], s_known=a["s_known"],
                position=position)


def candidates(turns, ranges, end: dict, feet_apart: int = FEET_APART_MAX) -> list:
    """Every pair the walk from a trend end lists: a committed peak at or after the R foot with a committed
    valley at or after the S foot, the two within ``feet_apart`` turns of each other (the pair at the trend
    end itself always), resistance above support."""
    feet = _feet(turns, end)
    if feet is None:
        return []
    r_foot, s_foot = feet
    out = []
    for i in range(r_foot, len(turns)):
        if turns[i].kind != "peak" or turns[i].knowable_bar is None:
            continue
        lo, hi = max(s_foot, i - feet_apart), min(len(turns), i + feet_apart + 1)
        js = set(range(lo, hi))
        if i == r_foot:
            js.add(s_foot)
        for j in sorted(js):
            t = turns[j]
            if t.kind != "valley" or t.knowable_bar is None or turns[i].price <= t.price:
                continue
            walk = walk_to(turns, end, i, j)
            out.append(_pair(turns, ranges, i, j, None if walk is None else walk["steps"]))
    return out


def winner(cands: list, bar: int, order: str) -> Optional[Pair]:
    """The box that stands on ``bar`` among the pairs born by then. ``became``: the pair that became a box
    first, then the earlier opening, then the tighter. ``opening``: the earliest opening among the boxes,
    then the tighter — the key that re-widens the box the day an earlier, wider pair is answered late.
    ``walk``: the pair that became a box first, then the earlier opening, then the one FEWER moves from the
    trend end (the first instance the walk found), then the tighter."""
    boxes = [c for c in cands if c.birth_bar is not None and c.birth_bar <= bar]
    if not boxes:
        return None
    if order == "became":
        return min(boxes, key=lambda c: (c.birth_bar, c.opening_bar, c.height, c.r_index, c.s_index))
    if order == "opening":
        return min(boxes, key=lambda c: (c.opening_bar, c.height, c.r_index, c.s_index))
    if order == "walk":
        return min(boxes, key=lambda c: (c.birth_bar, c.opening_bar, c.position if c.position is not None else 0,
                                         c.height, c.r_index, c.s_index))
    raise ValueError(f"unknown order {order!r}: expected one of {ORDERS}")


def _same(a: Pair, b: Pair) -> bool:
    return a is b or (a.r_index, a.s_index, a.R, a.S) == (b.r_index, b.s_index, b.R, b.S)


def _where(c: Pair, his: Pair, unit: float) -> str:
    area = AREA_RANGES * unit
    if c.S >= his.R - area or c.R <= his.S + area:
        return "beyond"
    if c.R <= his.R + area and c.S >= his.S - area:
        return "inside"
    return "overlapping"


def won_by_day(cands: list, his: Pair, bars, unit: float, min_height_ranges: Optional[float] = None) -> dict:
    """Day by day over ``bars``, under each order: the first day his pair won, whether it won on the last day
    (and whether the winner's lines were within half a range of his — the chance column), how many days it
    won; plus every box born before his, and where it sits against his lines. With ``min_height_ranges`` the
    pairs shorter than that, in their own unit, are set aside first — his "huge spread" word, bars almost as
    tall as the gap between the lines (his pair is never set aside: it is what is being measured)."""
    bars = list(bars)
    if min_height_ranges is not None:
        cands = [c for c in cands if _same(c, his) or c.height >= min_height_ranges * c.unit]
    out = {"boxes": sum(1 for c in cands if c.birth_bar is not None and c.birth_bar <= bars[-1])}
    for order in ORDERS:
        first, days, on_last, chance = None, 0, False, False
        for bar in bars:
            w = winner(cands, bar, order)
            if w is None:
                continue
            mine = _same(w, his)
            if mine:
                days += 1
                first = bar if first is None else first
            if bar == bars[-1]:
                on_last = mine
                chance = mine or rails_close(his.R, his.S, w.R, w.S, unit)
        out[order] = {"first": first, "on_last": on_last, "chance_on_last": chance, "days": days}
    before = [c for c in cands if c.birth_bar is not None and his.birth_bar is not None
              and c.birth_bar < his.birth_bar]
    out["born_before_his"] = [{"name": c.name, "R": c.R, "S": c.S, "birth": c.birth_bar,
                               "where": _where(c, his, unit)}
                              for c in sorted(before, key=lambda c: (c.birth_bar, c.opening_bar))]
    return out


def unlisted_first(rows: list) -> list:
    """What it could not list, then what it could; stable within each half."""
    return [r for r in rows if not r.get("listed")] + [r for r in rows if r.get("listed")]


# --------------------------------------------------------------------------- #
# One drawing                                                                 #
# --------------------------------------------------------------------------- #
def _trend_before(end: Optional[dict], first_bar: int, ranges, days) -> Optional[dict]:
    if end is None:
        return None
    unit = float(ranges[end["climax_bar"]])
    return {"kind": end["kind"], "climax_day": days[end["climax_bar"]], "ar_day": days[end["ar_bar"]],
            "distance": first_bar - end["climax_bar"], "ar_inside": end["ar_bar"] > first_bar,
            "height_ranges": abs(end["climax_price"] - end["launch_price"]) / unit if unit > 0 else None}


def _end_pair(turns, ranges, end: Optional[dict], r_i, s_i, rails: dict, unit: float, first_bar: int) -> dict:
    """The latest trend end at or before his first anchor, read as a pair on the fine line, against his pair:
    is his first anchor one of the trend end's own feet (its climax, or its reaction on the far view), and is
    the pair the trend end makes on the line his pair — to the cent, within half a range, or with the climax
    bar's own other end left out."""
    out = {"foot": False, "same": None, "close": None, "same_own_end_out": None, "same_within_area": None,
           "pair": None, "pair_within_area": None}
    if end is None:
        return out
    out["foot"] = first_bar in (end["climax_bar"], end["ar_bar"])
    pair = end_pair_on_the_line(turns, end)
    out["pair"] = pair
    if pair is not None:
        out["same"] = (r_i, s_i) == pair
        out["close"] = rails_close(rails["R"], rails["S"], turns[pair[0]].price, turns[pair[1]].price, unit)
    variant = end_pair_on_the_line(turns, end, own_end_left_out=True)
    if variant is not None:
        out["same_own_end_out"] = (r_i, s_i) == variant
    # The reaction with the climax bar's own end left out AND undercuts inside the area read as the same low;
    # the area in the trend end's own unit, the range of its climax day.
    within = end_pair_on_the_line(turns, end, own_end_left_out=True,
                                  area=AREA_RANGES * float(ranges[end["climax_bar"]]))
    out["pair_within_area"] = within
    if within is not None:
        out["same_within_area"] = (r_i, s_i) == within
    return out


def score_setup(setup: dict, raw, floors=FAR_FLOORS) -> dict:
    """One drawn setup, the line built once on the frame cut at his day, every measurement per far floor."""
    started = time.perf_counter()
    as_of = _date(setup["as_of"])
    prepared = two_eyes_frame.prepare(raw.loc[:pd.Timestamp(as_of)])
    line = two_eyes_line.build(prepared)
    days = [d.date() for d in prepared.index]
    ranges = prepared[two_eyes_frame.DAILY_RANGE].to_numpy(dtype=float)
    rails = setup["rails_drawn"]
    r_bar, s_bar = days.index(_date(setup["anchors"]["R"])), days.index(_date(setup["anchors"]["S"]))
    first_bar, last_bar = min(r_bar, s_bar), days.index(his_last_lps_day(setup))
    unit = float(ranges[max(r_bar, s_bar)])
    turns = list(line.turns)
    anchors = anchor_turns(turns, r_bar, s_bar, rails["R"], rails["S"], unit)
    r_i, s_i = anchors["R"], anchors["S"]
    have_pair = r_i is not None and s_i is not None
    his_pair = _pair(turns, ranges, r_i, s_i) if have_pair else None
    row = {
        "key": setup_key(setup), "ticker": setup["ticker"], "as_of": as_of, "days": days,
        "first_bar": first_bar, "last_bar": last_bar, "r_bar": r_bar, "s_bar": s_bar, "unit": unit,
        "anchors": anchors, "gap": abs(r_i - s_i) if have_pair else None,
        "answered": answered(turns, ranges, r_i, s_i) if have_pair else None,
        "his_pair": his_pair, "turns": turns, "floors": {}, "prepared": prepared,
    }
    for floor in floors:
        far = known_by(line.far(floor), last_bar)
        ends = [with_line_feet(e, turns, ranges) for e in trend_ends(far)]
        split = split_by_his_box(ends, first_bar, last_bar)
        before = split["before"][-1] if split["before"] else None
        lst = listing(turns, ends, r_i, s_i) if have_pair else \
            {"by": None, "by_latest": False, "steps": None, "r_moves": None, "s_moves": None}
        won, pool = {name: None for name in POOLS}, 0
        if lst["by"] is not None:
            cands = candidates(turns, ranges, lst["by"])
            his_in = next((c for c in cands if (c.r_index, c.s_index) == (r_i, s_i)), None)
            if his_in is None:                        # his feet further apart than the reach: still his pair
                his_in = _pair(turns, ranges, r_i, s_i, lst["steps"])
                cands.append(his_in)
            pool = len(cands)
            bars = range(first_bar, last_bar + 1)
            tall = [c for c in cands if _same(c, his_in) or c.height >= TALL_RANGES * c.unit]
            extremes = [c for c in tall if _same(c, his_in) or extremes_between(turns, c.r_index, c.s_index)]
            won = {"all": won_by_day(cands, his_in, bars, unit), "tall": won_by_day(tall, his_in, bars, unit),
                   "extremes": won_by_day(extremes, his_in, bars, unit)}
        row["floors"][floor] = {
            "far": far, "ends": ends, "split": {k: len(v) for k, v in split.items()},
            "inside_days": [days[e["climax_bar"]] for e in split["inside"]],
            "trend_before": _trend_before(before, first_bar, ranges, days),
            "end_pair": _end_pair(turns, ranges, before, r_i, s_i, rails, unit, first_bar),
            "listed": lst, "pool": pool, "won": won,
        }
    row["listed"] = any(f["listed"]["by"] is not None for f in row["floors"].values())
    row["seconds"] = time.perf_counter() - started
    return row


def run_gate(setups: list, frames: dict, floors=FAR_FLOORS) -> list:
    return [score_setup(s, fixture_frame(frames, setup_key(s), s["ticker"]), floors) for s in setups]


# --------------------------------------------------------------------------- #
# The board                                                                   #
# --------------------------------------------------------------------------- #
def _n(rows, pred) -> str:
    return f"{sum(1 for r in rows if pred(r)):>2} of {len(rows)}"


def _med_worst(values) -> str:
    values = [v for v in values if v is not None]
    if not values:
        return "   -"
    return f"median {statistics.median(values):g} · worst {max(values):g}"


def _day(d) -> str:
    return d.strftime("%a %d/%m/%Y") if d else "-"


def format_board(rows: list, floors=FAR_FLOORS) -> str:
    out = ["", "THE LISTING GATE — his 35 drawings on the new reader's line, "
           + dt.date.today().strftime("%A %d/%m/%Y"), ""]
    exact = lambda r: r["anchors"]["r_match"] == "exact" and r["anchors"]["s_match"] == "exact"
    his_line = lambda r: r["anchors"]["r_match"] in ("exact", "price") and r["anchors"]["s_match"] in ("exact", "price")
    out.append("HIS TWO ANCHORS ON THE LINE (the fine line, the same at every floor)")
    out.append(f"  both turns on his days, to the cent            {_n(rows, exact)}")
    out.append(f"  both his prices to the cent (a day's tie)       {_n(rows, his_line)}")
    out.append(f"  one of them only NEAR (within a tenth of a range) "
               f"{_n(rows, lambda r: r['gap'] is not None and not his_line(r))}")
    out.append(f"  one of them not on the line at all              {_n(rows, lambda r: r['gap'] is None)}")
    out.append(f"  turns between his two anchors                   "
               f"{_med_worst([r['gap'] - 1 for r in rows if r['gap'] is not None])}   "
               f"(adjacent: {sum(1 for r in rows if r['gap'] == 1)})")
    born = lambda r: r["answered"] is not None and r["answered"]["birth"] is not None and \
        r["answered"]["birth"] <= r["last_bar"]
    on_clock = lambda r: born(r) and r["answered"]["birth"] == r["answered"]["fifteenth"]
    out.append("")
    out.append("HIS PAIR A BOX BY HIS LAST RECEDING DAY, his way (both lines answered, fifteen days)")
    out.append(f"  yes                                             {_n(rows, born)}")
    out.append(f"    …on its fifteenth day (answered before it)    {_n(rows, on_clock)}")
    late = [r["key"] for r in rows if born(r) and not on_clock(r)]
    out.append(f"    …later, when the second line was answered    {len(late):>2} of {len(rows)}"
               f"{'   ' + ', '.join(late) if late else ''}")
    never = [r["key"] for r in rows if r["gap"] is not None and not born(r)]
    out.append(f"  not a box by his day                            {len(never):>2} of {len(rows)}"
               f"{'   ' + ', '.join(never) if never else ''}")
    out.append(f"  days from the first anchor to the box           "
               f"{_med_worst([r['answered']['birth'] - r['first_bar'] + 1 for r in rows if born(r)])}")

    head = f"{'':<50}" + "".join(f"{'far ' + str(f):>14}" for f in floors)
    out += ["", head, "-" * len(head)]

    def per_floor(label, value):
        out.append(f"{label:<50}" + "".join(f"{value(f):>14}" for f in floors))

    F = lambda r, f: r["floors"][f]
    per_floor("THE TREND BEFORE HIS BOX reported as a run", lambda f: _n(rows, lambda r: F(r, f)["trend_before"] is not None))
    per_floor("  …ending AT his first anchor", lambda f: _n(rows, lambda r: (F(r, f)["trend_before"] or {}).get("distance") == 0))
    per_floor(f"  …ending within {NEAR_TREND_DAYS} trading days before it", lambda f: _n(rows, lambda r: 0 < ((F(r, f)["trend_before"] or {}).get("distance") or -1) <= NEAR_TREND_DAYS))
    per_floor("  …ending further back", lambda f: _n(rows, lambda r: ((F(r, f)["trend_before"] or {}).get("distance") or -1) > NEAR_TREND_DAYS))
    per_floor("  …its reaction low falls INSIDE his box", lambda f: _n(rows, lambda r: bool((F(r, f)["trend_before"] or {}).get("ar_inside"))))
    per_floor("TREND ENDS INSIDE HIS BOX (drawings with any)", lambda f: _n(rows, lambda r: F(r, f)["split"]["inside"] > 0))
    per_floor("  …how many, over all drawings", lambda f: f"{sum(F(r, f)['split']['inside'] for r in rows):>2}")
    E = lambda r, f: F(r, f)["end_pair"]
    per_floor("HIS FIRST ANCHOR IS A FOOT of that trend end (its climax or its reaction)", lambda f: _n(rows, lambda r: E(r, f)["foot"]))
    per_floor("HIS PAIR IS the trend end's pair read on the line", lambda f: _n(rows, lambda r: E(r, f)["same"] is True))
    per_floor("  …within half a range of it", lambda f: _n(rows, lambda r: E(r, f)["close"] is True))
    per_floor("  …to the cent with the climax bar's own other end left out", lambda f: _n(rows, lambda r: E(r, f)["same_own_end_out"] is True))
    per_floor("  …and undercuts inside the area read as the same low", lambda f: _n(rows, lambda r: E(r, f)["same_within_area"] is True))
    per_floor("HIS PAIR LISTED by some trend end's walk", lambda f: _n(rows, lambda r: F(r, f)["listed"]["by"] is not None))
    per_floor("  …by the LATEST trend end", lambda f: _n(rows, lambda r: F(r, f)["listed"]["by_latest"]))
    per_floor("  …only by an earlier one", lambda f: _n(rows, lambda r: F(r, f)["listed"]["by"] is not None and not F(r, f)["listed"]["by_latest"]))
    per_floor("  …with no move at all (his pair IS the trend end)", lambda f: _n(rows, lambda r: F(r, f)["listed"]["steps"] == 0))
    out.append(f"{'  moves of the two legs to his pair':<50}"
               + "".join(f"{_med_worst([F(r, f)['listed']['steps'] for r in rows]):>14}" for f in floors))
    out.append(f"{'  pairs the walk listed (the pool)':<50}"
               + "".join(f"{_med_worst([F(r, f)['pool'] for r in rows if F(r, f)['won']]):>14}" for f in floors))
    out += ["", "THE ELECTION — his pair WON on his last receding day (in brackets: the winner within half a range of his)"]
    for pool in POOLS:
        out.append(f"  {POOL_WORDS[pool]}")
        W = lambda r, f, order, p=pool: ((F(r, f)["won"] or {}).get(p) or {}).get(order) or {}
        for order in ORDERS:
            per_floor(f"    {ORDER_WORDS[order]}",
                      lambda f, o=order: f"{sum(1 for r in rows if W(r, f, o).get('on_last') is True):>2} "
                                         f"({sum(1 for r in rows if W(r, f, o).get('chance_on_last') is True):>2})")
        out.append(f"{'    boxes born BEFORE his pair':<50}"
                   + "".join(f"{_med_worst([len(F(r, f)['won'][pool]['born_before_his']) for r in rows if (F(r, f)['won'] or {}).get(pool)]):>14}" for f in floors))
        for where in ("beyond", "overlapping", "inside"):
            per_floor(f"      …{where} his lines (drawings with any)", lambda f, w=where, p=pool: _n(rows, lambda r: any(b["where"] == w for b in ((F(r, f)["won"] or {}).get(p) or {}).get("born_before_his", []))))

    out += ["", "EACH DRAWING — what could not be listed first"]
    for r in unlisted_first(rows):
        a = r["anchors"]
        ans = r["answered"]
        box = "no pair" if ans is None else ("not a box by his day" if ans["birth"] is None or ans["birth"] > r["last_bar"]
                                              else f"box on {r['days'][ans['birth']]:%d/%m}"
                                              + (" (15th day)" if ans["birth"] == ans["fifteenth"] else " (answered)"))
        line = f"  {r['key']:<16} R {a['r_match'] or 'NO'} S {a['s_match'] or 'NO'} gap {r['gap'] if r['gap'] is not None else '-'} · {box}"
        for f in floors:
            x = F(r, f)
            tb = x["trend_before"]
            end = "no run" if tb is None else f"{tb['kind']} {tb['distance']}d{'*' if tb['ar_inside'] else ''}"
            lst = x["listed"]
            steps = "-" if lst["by"] is None else f"{lst['steps']}{'' if lst['by_latest'] else 'e'}"
            ep = x["end_pair"]
            foot = ("F" if ep["foot"] else "") + ("=" if ep["same"] else ("~" if ep["close"] else "")) \
                + ("a" if ep["same_within_area"] and not ep["same"] else "")
            w = ""
            for pool in POOLS:
                won = (x["won"] or {}).get(pool)
                if won:
                    w += " " + pool[0] + "".join(
                        ("✓" if won[o]["on_last"] else ("~" if won[o]["chance_on_last"] else "✗")) for o in ORDERS) \
                        + f"-{len(won['born_before_his'])}"
            line += f" | {f}: end {end} {foot} in {x['split']['inside']} moves {steps}{w}"
        out.append(line)
        if a["why"]:
            out.append(f"  {'':<16} {a['why']}")
    out += ["", "  legend: end = the latest trend end at or before his first anchor, days before it (* its reaction low"
            " is inside his box); F = his first anchor is one of its feet; = / ~ = the pair it makes on the line is"
            " his to the cent / within half a range, a = his to the cent once the climax bar's own end is left out"
            " and undercuts inside the area are the same low; in = trend ends inside his box; moves = the two legs'"
            " moves from the trend end that lists his pair (e: not the latest); then, per pool (a = every pair,"
            " t = tall, e = tall and extremes), the three orders (became / opening / walk): ✓ his pair won on his"
            " last receding day, ~ the winner within half a range of his, ✗ another pair; -n = boxes born before his",
            ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# The pages                                                                   #
# --------------------------------------------------------------------------- #
_HIS = "#d62728"        # his lines, red
_LINE = "#8a8a8a"       # the fine line
_FAR = "#1f4e9c"        # the far view and the trend ends
_INSIDE = "#e8891d"     # a trend end inside his box
_ANSWER = "#2e8b57"     # the swings that answered his lines
_WINNER = "#1f77b4"     # the pair that would have won on his day

_LEAD_IN = 45           # trading days before his box, at least
_LEAD_IN_MAX = 130      # and at most, to reach the trend end that lists his pair


def render_pages(rows: list, setups: dict, out_dir: str, floor: float) -> list:
    """One OHLC page per drawing, the unlisted first: his lines red, the line grey, the far view and its trend
    ends blue, the answers green, the pair that would have won on his day dashed blue."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from tools.research.full_package_render import _draw_bars

    refuse_sealed_output(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for order, row in enumerate(unlisted_first(rows), start=1):
        path = os.path.join(out_dir, f"{order:02d}_{row['key'].replace(':', '_')}.png")
        _render_one(plt, _draw_bars, row, setups[row["key"]], floor, path)
        written.append(path)
    return written


def _window(row: dict, floor: float) -> int:
    lo = row["first_bar"] - _LEAD_IN
    end = row["floors"][floor]["listed"]["by"]
    if end is not None:
        lo = min(lo, end["climax_bar"] - 5)
    return max(0, lo, row["first_bar"] - _LEAD_IN_MAX)


def _render_one(plt, draw_bars, row: dict, setup: dict, floor: float, path: str):
    prepared, days, turns = row["prepared"], row["days"], row["turns"]
    at = row["floors"][floor]
    lo = _window(row, floor)
    view = prepared.iloc[lo:]
    x = lambda bar: bar - lo
    fig, ax = plt.subplots(figsize=(16, 8))
    draw_bars(ax, view["Open"].values, view["High"].values, view["Low"].values, view["Close"].values)

    rails, band = setup["rails_drawn"], AREA_RANGES * row["unit"]
    for price, name in ((rails["R"], "his R"), (rails["S"], "his S")):
        ax.axhspan(price - band, price + band, color=_HIS, alpha=.08, zorder=0)
        ax.axhline(price, color=_HIS, lw=1.7, zorder=4)
        ax.annotate(f"{name} {price:.2f}", (0.004, price), xycoords=("axes fraction", "data"),
                    color=_HIS, fontsize=9, va="bottom", zorder=5)
    ax.axvspan(x(row["first_bar"]), x(row["last_bar"]), color=_HIS, alpha=.05, zorder=0)
    for bar, price in ((row["r_bar"], rails["R"]), (row["s_bar"], rails["S"])):
        ax.plot([x(bar)], [price], marker="o", ms=13, mfc="none", mec=_HIS, mew=1.8, zorder=6)
    lps = setup.get("lps2") or setup.get("lps")
    if lps:
        a, b = days.index(_date(lps[0])), days.index(_date(lps[1]))
        ax.axvspan(x(a), x(b), color="#8a6d3b", alpha=.13, zorder=1)
    trig = _date(setup.get("trigger"))
    if trig in days and setup.get("trigger_price"):
        ax.plot([x(days.index(trig))], [setup["trigger_price"]], marker="^", ms=11, color=_HIS, zorder=6)

    # The fine line and the far view, as of his last receding day.
    fine = [t for t in known_by(turns, row["last_bar"]) if t.bar >= lo]
    if fine:
        ax.plot([x(t.bar) for t in fine], [t.price for t in fine], color=_LINE, lw=.8, alpha=.7, zorder=2)
    far = [t for t in at["far"] if t.bar >= lo]
    if far:
        ax.plot([x(t.bar) for t in far], [t.price for t in far], color=_FAR, lw=1.7, alpha=.9, zorder=3,
                marker="o", ms=3.5)

    # The trend ends: the climax (a wedge) and its reaction (a dot); the one the walk starts from is named.
    by = at["listed"]["by"]
    for end in at["ends"]:
        if end["climax_bar"] < lo:
            continue
        inside = row["first_bar"] < end["climax_bar"] <= row["last_bar"]
        color = _INSIDE if inside else _FAR
        mark = "v" if end["kind"] == "BC" else "^"
        ax.plot([x(end["climax_bar"])], [end["climax_price"]], marker=mark, ms=12, color=color, zorder=7,
                mec="white", mew=.8)
        ax.plot([x(end["ar_bar"])], [end["ar_price"]], marker="o", ms=7, color=color, zorder=7, mec="white")
        label = "trend end" + (" INSIDE his box" if inside else "")
        if by is not None and end is by:
            label = f"trend end — the walk starts here ({at['listed']['steps']} moves to his pair)"
        ax.annotate(label, (x(end["climax_bar"]), end["climax_price"]), xytext=(0, 14 if mark == "v" else -18),
                    textcoords="offset points", color=color, fontsize=8, ha="center", zorder=8)

    # His pair's answers, and the day it became a box.
    ans = row["answered"]
    if ans:
        for idx in (ans["R"], ans["S"]):
            if idx is not None and turns[idx].bar >= lo:
                ax.plot([x(turns[idx].bar)], [turns[idx].price], marker="s", ms=9, mfc="none", mec=_ANSWER,
                        mew=2, zorder=7)
        if ans["birth"] is not None and ans["birth"] < len(days):
            ax.axvline(x(ans["birth"]), color=_ANSWER, lw=1.2, ls=":", zorder=3)
            ax.annotate(f"his box on {days[ans['birth']]:%d/%m}"
                        + (" (15th day)" if ans["birth"] == ans["fifteenth"] else " (second line answered)"),
                        (x(ans["birth"]), 0.03), xycoords=("data", "axes fraction"), color=_ANSWER,
                        fontsize=8, ha="left", va="bottom")

    # The trend end's own pair read on the line (its reaction on the fine turns): hollow diamonds.
    ep = at["end_pair"]
    if ep["pair"] is not None:
        for idx in ep["pair"]:
            if turns[idx].bar >= lo:
                ax.plot([x(turns[idx].bar)], [turns[idx].price], marker="D", ms=9, mfc="none", mec=_FAR, mew=1.6,
                        zorder=7)

    # The pair that would have won on his last receding day under the strictest pool and the walk's order
    # (tall pairs, each line the extreme between its anchors; became first, then the walk), when not his.
    won = (at["won"] or {}).get("extremes")
    verdict = "NOT LISTED"
    if won:
        verdict = f"LISTED ({at['listed']['steps']} moves) · WON on his day: " \
                  f"{'yes' if won['walk']['on_last'] else ('within half a range' if won['walk']['chance_on_last'] else 'no')}"
        pool = candidates(turns, prepared[two_eyes_frame.DAILY_RANGE].to_numpy(dtype=float), by)
        his = row["his_pair"]
        pool = [c for c in pool if _same(c, his)
                or (c.height >= TALL_RANGES * c.unit and extremes_between(turns, c.r_index, c.s_index))]
        w = winner(pool, row["last_bar"], "walk")
        if w is not None and not _same(w, his):
            for price, name in ((w.R, "would win R"), (w.S, "would win S")):
                ax.axhline(price, color=_WINNER, lw=1.4, ls="--", zorder=4)
                ax.annotate(f"{name} {price:.2f} (pair {w.name}, box on {days[w.birth_bar]:%d/%m})", (0.70, price),
                            xycoords=("axes fraction", "data"), color=_WINNER, fontsize=8.5, va="bottom", zorder=5)

    n = len(view)
    step = max(1, n // 12)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([days[lo + i].strftime("%d/%m/%y") for i in range(0, n, step)], fontsize=8)
    ax.set_xlim(-2, n + 1)
    ax.set_title(f"{row['key']}  —  {verdict}   ·   far floor {floor} ranges", fontsize=13, loc="left",
                 fontweight="bold")
    ax.set_xlabel(textwrap.fill(_words(row, floor), 210), fontsize=9.5, labelpad=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _words(row: dict, floor: float) -> str:
    a, at, days = row["anchors"], row["floors"][floor], row["days"]
    parts = []
    if a["why"]:
        parts.append(a["why"] + ".")
    tb = at["trend_before"]
    if tb is None:
        parts.append("No run ends before his box at this floor.")
    else:
        parts.append(f"The trend before his box: a {'rise' if tb['kind'] == 'BC' else 'decline'} of "
                     f"{tb['height_ranges']:.1f} ranges ending {_day(tb['climax_day'])}, "
                     f"{tb['distance']} trading days before his first anchor"
                     + ("; its reaction low falls inside his box." if tb["ar_inside"] else "."))
    if at["split"]["inside"]:
        parts.append(f"{at['split']['inside']} trend end(s) inside his box: "
                     + ", ".join(d.strftime("%d/%m") for d in at["inside_days"]) + ".")
    ep = at["end_pair"]
    if ep["pair"] is not None:
        turns = row["turns"]
        r, s = turns[ep["pair"][0]], turns[ep["pair"][1]]
        parts.append(f"That trend end, its reaction read on the line, makes the pair {r.price:.2f} ({r.day:%d/%m}) / "
                     f"{s.price:.2f} ({s.day:%d/%m}): "
                     + ("HIS PAIR." if ep["same"] else "within half a range of his." if ep["close"] else
                        "his to the cent once the climax bar's own other end is left out." if ep["same_own_end_out"]
                        else "not his."))
    lst = at["listed"]
    if lst["by"] is not None:
        parts.append(f"Listed from the trend end of {_day(days[lst['by']['climax_bar']])}"
                     f"{'' if lst['by_latest'] else ' (not the latest)'}: R moved {lst['r_moves']}, S moved "
                     f"{lst['s_moves']}.")
    won = at["won"] or {}
    if won.get("all"):
        before = won["all"]["born_before_his"]
        parts.append(f"{len(before)} pair(s) became a box before his"
                     + (" (" + ", ".join(f"{b['name']} {b['where']}" for b in before[:4])
                        + (", …" if len(before) > 4 else "") + ")" if before else "")
                     + f"; {len(won['tall']['born_before_his'])} once pairs under one range are set aside, "
                     f"{len(won['extremes']['born_before_his'])} once each line must also be the extreme between the anchors.")
    return "  ".join(parts)


def write_contact_sheet(rows: list, pages: list, out_dir: str, floor: float) -> str:
    cells = []
    for row, page in zip(unlisted_first(rows), pages):
        at = row["floors"][floor]
        won = ((at["won"] or {}).get("extremes") or {}).get("walk") or {}
        klass = "miss" if not row["listed"] else ("hit" if won.get("on_last") else "chance")
        cells.append(f'<figure class="{klass}"><img src="{os.path.basename(page)}" loading="lazy">'
                     f'<figcaption><b>{row["key"]}</b> — {"listed" if row["listed"] else "NOT listed"}'
                     f'{" · won on his day" if klass == "hit" else ""}</figcaption></figure>')
    html = f"""<!doctype html><meta charset="utf-8">
<title>The listing gate — far floor {floor}</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f7;color:#222}}
 h1{{font-size:20px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
 figure{{margin:0;padding:8px;border:2px solid #ddd;border-radius:6px;background:#fff}}
 figure.miss{{border-color:#d62728}} figure.chance{{border-color:#e8a33d}} figure.hit{{border-color:#2e8b57}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}}
</style>
<h1>The listing gate — far floor {floor} daily ranges</h1>
<p>OHLC bars. Red: his two lines, their areas, his anchors (circles), his box (shaded), his last receding days
 (brown) and his buy (triangle). Grey: the reader's line as of his last receding day. Blue: the far view, its
 trend ends (wedge = the climax, dot = the reaction low); orange: a trend end inside his box. Green squares: the
 swings that answered his lines; green dotted line: the day his pair became a box. Dashed blue: the pair that
 would have won on his day, when it is not his. The unlisted come first.</p>
<div class="grid">{''.join(cells)}</div>
"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# --------------------------------------------------------------------------- #
# The run                                                                     #
# --------------------------------------------------------------------------- #
def _jsonable(rows: list) -> list:
    keep = ("key", "ticker", "as_of", "first_bar", "last_bar", "unit", "anchors", "gap", "answered", "listed",
            "seconds")
    out = []
    for r in rows:
        j = {k: r[k] for k in keep}
        j["floors"] = {str(f): {k: v for k, v in x.items() if k not in ("far", "ends")}
                       | {"ends": [{k: v for k, v in e.items()} for e in x["ends"]]}
                       for f, x in r["floors"].items()}
        out.append(j)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", metavar="DIR", help="also write one OHLC page per drawing and a contact sheet here")
    ap.add_argument("--floor", type=float, default=2.5, help="the far floor the pages are drawn at (default 2.5)")
    ap.add_argument("--json", metavar="PATH", help="also dump the measurements as JSON")
    args = ap.parse_args()

    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    floors = tuple(sorted(set(FAR_FLOORS) | {args.floor}))
    started = time.perf_counter()
    rows = run_gate(setups, frames, floors)
    print(format_board(rows, floors))
    print(f"  {len(rows)} drawings read in {time.perf_counter() - started:.1f}s")
    if args.pages:
        by_key = {setup_key(s): s for s in setups}
        pages = render_pages(rows, by_key, args.pages, args.floor)
        sheet = write_contact_sheet(rows, pages, args.pages, args.floor)
        print(f"  {len(pages)} pages · contact sheet {sheet}")
    if args.json:
        refuse_sealed_output(args.json)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(_jsonable(rows), f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
