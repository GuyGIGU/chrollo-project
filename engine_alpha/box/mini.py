"""Read a smaller box alongside its parent, using the walk's own life rules.

Candidates open after the parent's birth, sit inside or across it, and have less than
80% of its price height (operator ruling, 2026-10-21). Filter size before the inner
walk so an oversized box cannot block a smaller candidate. The selected box must
also clear the parent's support area and differ from its two rails.

A mini has its own rails and never replaces the parent. It need not sit at the top.
The LPS uses it only when its low is in, on or near it; mini-side faults fall back
to the parent read.
"""
from __future__ import annotations

from typing import Optional

from engine_alpha import lps as lps_stage
from engine_alpha import numbers as M
from engine_alpha.record import ROLE_MINI, ROLE_PARENT, Box, Step
from engine_alpha.box.handover import Life, lies_beyond, lives
from engine_alpha.box.pairs import Pair
from engine_alpha.box.walk import Walk, _box_record

__all__ = ["STAGE", "a_small_box_inside", "candidates", "could_not_be_read", "find", "inside_or_across",
           "is_a_mini", "lps_box", "on_the_right_side", "read", "read_lps", "record", "where"]

STAGE = "mini"


# --------------------------------------------------------------------------- #
# Candidate geometry                                                         #
# --------------------------------------------------------------------------- #
def on_the_right_side(pair: Pair, parent: Pair) -> bool:
    """The pair opened after the parent became a box."""
    return pair.opening_bar > parent.birth_bar


def inside_or_across(pair: Pair, parent: Pair) -> bool:
    """Inside or across the parent, using the walk's definition of beyond."""
    return not lies_beyond(pair, parent)


def a_small_box_inside(pair: Pair, parent: Pair) -> bool:
    """Its bottom clears the parent's support area, and its rails are not the parent's twin."""
    twin = abs(pair.R - parent.R) <= parent.area and abs(pair.S - parent.S) <= parent.area
    return pair.S >= parent.S - parent.area and not twin


def candidates(found: Walk) -> list:
    """Born inner pairs below the size limit, in opening order, before the inner walk."""
    parent = found.winner
    if parent is None:
        return []
    return [p for p in found.pairs.values()
            if p.birth_bar is not None and p.feet != parent.feet
            and on_the_right_side(p, parent) and inside_or_across(p, parent)
            and p.height < M.MINI_MAX_PARENT_HEIGHT_RATIO * parent.height]


def is_a_mini(pair: Pair, parent: Pair) -> bool:
    """Check the selected inner box's support and distinct rails; no top-only restriction."""
    return a_small_box_inside(pair, parent)


# --------------------------------------------------------------------------- #
# The mini's life, by the walk's own rule                                     #
# --------------------------------------------------------------------------- #
def find(found: Walk, high, low, read_bar: int, ranges=None) -> tuple:
    """Walk eligible inner pairs; return their history only if the last is a small box inside the parent."""
    chosen = candidates(found)
    if not chosen:
        return ()
    walked = [t for t in found.ends if t.get("foot_bar") is not None]
    # His HCA reading (a pair the bars knew stands through a run that came back) is not asked of inner pairs:
    # inside the parent every inner pair's rails are levels the bars knew, so it would say nothing there.
    history = tuple(lives(chosen, walked, high, low, read_bar, known_rails=False, ranges=ranges))
    if not history or not is_a_mini(history[-1].pair, found.winner):
        return ()
    return history


def _when(found: Walk, bar: Optional[int]) -> str:
    if bar is None:
        return "not yet"
    if found.days is not None and 0 <= bar < len(found.days):
        return f"{found.days[bar]:%a %d/%m/%Y}"
    return f"bar {bar}"


def record(found: Walk, history: tuple) -> tuple:
    """The record of the mini: ``(box, step)`` — the live mini as a ``Box`` with the role ``mini`` (its own
    anchor days, its own frozen range, no end day), and one step in words: its lines, when it became a box and was
    shown, where it stands against the parent in the parent's ranges, how many candidates it was chosen from and
    the chain before it."""
    parent, life = found.winner, history[-1]
    pair = life.pair
    r, s = found.turns[pair.r_index], found.turns[pair.s_index]
    unit = parent.unit
    top = (pair.R - parent.R) / unit
    bottom = (parent.R - pair.S) / unit
    opens = "opens on resistance" if pair.top_first else "opens on support"
    said = (f"the mini: R {pair.R:.2f} ({r.day:%a %d/%m/%Y}) / S {pair.S:.2f} ({s.day:%a %d/%m/%Y}), {opens}, measured "
            f"in a {pair.unit:.2f} daily range, a box on {_when(found, pair.birth_bar)}, shown from "
            f"{_when(found, life.shown_bar)}; its top {abs(top):.2f} ranges {'over' if top >= 0 else 'under'} the "
            f"parent's resistance and its bottom {bottom:.2f} ranges under it; the inner box the walk shows, out of "
            f"{len(candidates(found))} pairs inside the parent's right side")
    if len(history) > 1:
        chain = ", ".join(f"{h.pair.R:.2f} / {h.pair.S:.2f} (ended {_when(found, h.ended_bar)})" for h in history[:-1])
        said += f"; before it, inside the parent: {chain}"
    return _box_record(found, pair, ROLE_MINI), Step(STAGE, said)


# --------------------------------------------------------------------------- #
# The LPS against the mini: his three positions                               #
# --------------------------------------------------------------------------- #
IN, ON, NEAR, AWAY = "in", "on", "near", "away"


def where(low: float, band) -> str:
    """Where a pullback's low sits against the mini, in the mini's OWN area (half its frozen range; his area, the
    only width): ``in`` — inside the band and clear of both lines; ``on`` — inside and within the area of a line
    (resting on it, a slight poke included: *"whenever they are slightly poking out or not does not matter one
    bit"*, Sat 26/09/2026); ``near`` — outside the band and within the area of a line; ``away`` — anything else.
    ``band`` is anything with ``R``, ``S`` and ``area``."""
    low, R, S, a = float(low), float(band.R), float(band.S), float(band.area)
    if S + a < low < R - a:
        return IN
    if S - a <= low <= R + a:
        return ON if S <= low <= R else NEAR
    return AWAY


def lps_box(low: float, band) -> tuple:
    """Which box the LPS is read against, and how (his sentence of Sun 13/09/2026: *"the LPS read can be against
    it if it is inside/near it/resting on it"*): ``("mini", word)`` when the low is in, on or near the mini;
    ``("parent", None)`` with no mini or a low away from it. ONE chooser, so the board draws the band that fired."""
    if band is None:
        return ROLE_PARENT, None
    word = where(low, band)
    return (ROLE_PARENT, None) if word == AWAY else (ROLE_MINI, word)


def could_not_be_read(exc: Exception) -> tuple:
    """The step the read carries when this stage fell over: the parent-only read stands, the mini is missing."""
    return (Step(STAGE, f"the mini could not be read: {type(exc).__name__}: {exc}"),)


# --------------------------------------------------------------------------- #
# What the reader calls: the mini, and the LPS against it                     #
# --------------------------------------------------------------------------- #
def read(found: Walk, high, low, ranges, read_bar: int) -> tuple:
    """The mini on one read: ``(box, pair, steps)`` — the live mini as a ``Box`` and its ``Pair`` with the step that
    says it, or ``(None, None, ())`` when the walk shows no inner box. A fault leaves the parent-only read standing
    with a step that says why, never a crash: by his ruling the LPS may be read against the mini, so a bug in the
    mini must never cost a fire."""
    try:
        history = find(found, high, low, read_bar, ranges=ranges)
        if not history:
            return None, None, ()
        box, step = record(found, history)
        return box, history[-1].pair, (step,)
    except Exception as exc:
        return None, None, could_not_be_read(exc)


def read_lps(parent_pullback, mini_pair: Pair, high, low, ranges, turns, days, read_bar: int, boxes) -> tuple:
    """The LPS against the mini, on his condition: when the pullback's low is in, on or near the mini (the mini's own
    area), it is measured again against the mini's lines and stamped with which box and how; its window and trigger
    are the bars' and do not move. Away from the mini, a mini that became a box only after the pullback ended, or a
    fault on the mini's side: the parent's read, with a sentence — never "no LPS", never a crashed read. Returns
    ``(lps, steps, word, pullback)``, the steps including every sentence the mini's side added."""
    against, how, extra, pullback = ROLE_PARENT, None, (), parent_pullback
    try:                                              # the chooser is the mini's side too
        against, how = lps_box(parent_pullback.low, mini_pair)
        if against == ROLE_MINI:
            inner = lps_stage.read(high, low, ranges, turns, R=mini_pair.R, S=mini_pair.S,
                                   box_unit=mini_pair.unit, born_bar=mini_pair.birth_bar)
            if inner is None or inner.end_bar < inner.born_bar:
                extra = (Step("LPS", f"the pullback's low {parent_pullback.low:.2f} sits {how} the mini "
                                     f"{mini_pair.R:.2f} / {mini_pair.S:.2f}, but the mini became a box "
                                     f"only on {days[mini_pair.birth_bar]:%a %d/%m/%Y}, after the pullback "
                                     f"ended: read against the parent"),)
                against, how = ROLE_PARENT, None
            else:
                pullback = inner
    except Exception as exc:                          # the parent's read stands; the trail says why
        extra = (Step("LPS", f"the mini's side of the LPS could not be read: {type(exc).__name__}: "
                             f"{exc}; read against the parent"),)
        against, how, pullback = ROLE_PARENT, None, parent_pullback
    try:
        the_lps, said, word = lps_stage.record(pullback, days, read_bar=read_bar, read_against=against, how=how)
    except Exception as exc:
        if against != ROLE_MINI:                      # stage 6's own record: as before the mini, not guarded here
            raise
        the_lps, said, word = lps_stage.record(parent_pullback, days, read_bar=read_bar)
        extra = extra + (Step("LPS", f"the LPS record against the mini could not be made: {type(exc).__name__}: "
                                     f"{exc}; read against the parent"),)
    # The archive tie: "mini" is said only with a stored mini. The pair and its box are set together, so this cannot
    # happen by construction; if it ever does, the parent's read stands, with a sentence.
    if the_lps is not None and the_lps.read_against == ROLE_MINI and not any(b.role == ROLE_MINI for b in boxes):
        the_lps, said, word = lps_stage.record(parent_pullback, days, read_bar=read_bar)
        extra = extra + (Step("LPS", "the LPS was read against the mini but no mini box is on the record: "
                                     "read against the parent"),)
    return the_lps, said + extra, word, pullback
