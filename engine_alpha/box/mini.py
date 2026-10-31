"""The mini (off behind ``MINI_ENABLED``): a smaller box inside or across the parent, read with the walk's own life
rules over the pairs that opened after the parent's birth and stand under ``MINI_MAX_PARENT_HEIGHT_RATIO`` of its
height; it has its own rails and never replaces the parent. The LPS is read against it only when the pullback's low
is in, on or near it (``read_lps``); a fault on the mini's side leaves the parent's read standing.
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
    # His HCA reading is not asked of inner pairs: inside the parent every pair's rails are levels the bars knew.
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
    """The record of the mini, ``(box, step)``: the live mini as a ``Box`` with the role ``mini``, and one step in
    words — its lines, its birth and showing, where it stands against the parent, the candidates, the chain before."""
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
    """Where a pullback's low sits against the mini, in the mini's own area: ``in`` (clear of both lines), ``on``
    (inside, within a line's area), ``near`` (outside, within it) or ``away``. ``band`` has ``R``, ``S``, ``area``."""
    low, R, S, a = float(low), float(band.R), float(band.S), float(band.area)
    if S + a < low < R - a:
        return IN
    if S - a <= low <= R + a:
        return ON if S <= low <= R else NEAR
    return AWAY


def lps_box(low: float, band) -> tuple:
    """Which box the LPS is read against, and how (his ruling, Sun 13/09/2026): ``("mini", word)`` when the low is
    in, on or near the mini; ``("parent", None)`` with no mini or a low away from it."""
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
    """The mini on one read, ``(box, pair, steps)``, or ``(None, None, ())`` when the walk shows no inner box; a
    fault leaves the parent-only read standing with a step that says why, never a crash."""
    try:
        history = find(found, high, low, read_bar, ranges=ranges)
        if not history:
            return None, None, ()
        box, step = record(found, history)
        return box, history[-1].pair, (step,)
    except Exception as exc:
        return None, None, could_not_be_read(exc)


def read_lps(parent_pullback, mini_pair: Pair, high, low, ranges, turns, days, read_bar: int, boxes) -> tuple:
    """The LPS against the mini when the pullback's low is in, on or near it, measured again against the mini's lines
    and stamped with which box and how; otherwise, or on any fault of the mini's side, the parent's read with a
    sentence. Returns ``(lps, steps, word, pullback)``."""
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
    # The archive tie: "mini" is said only with a stored mini box; else the parent's read stands, with a sentence.
    if the_lps is not None and the_lps.read_against == ROLE_MINI and not any(b.role == ROLE_MINI for b in boxes):
        the_lps, said, word = lps_stage.record(parent_pullback, days, read_bar=read_bar)
        extra = extra + (Step("LPS", "the LPS was read against the mini but no mini box is on the record: "
                                     "read against the parent"),)
    return the_lps, said + extra, word, pullback
