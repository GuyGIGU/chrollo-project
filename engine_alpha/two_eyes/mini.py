"""The mini: a second box inside the parent's right side, read with the walk's own functions (build task 13).

His two sentences: *"if you are reffering to mini consolidations then both boxes live, they are a part of the same
setup"* (Sun 20/09/2026) and *"The Mini consolidation is always built with it's own rail set - the LPS read can be
against it if it is inside/near it/resting on it and the trigger is always read against the LPS by itself"* (asked
Sat 12/09/2026, answered Sun 13/09/2026). And what a mini is: *"like a small box, same as the regular
consolidation"* (Wed 26/08/2026).

The walk already lists every pair of swing ends a swing connects, with the day each became a box, and it refuses
the parent's place to any pair inside or across the parent (``walk.left_for_good``: *"its own leg, a poke, a dip or
a mini"*). This stage runs the walk's own ``lives`` over the inner boxes (layers 1 and 2 below) — the same rule of
the pair, the same hand-overs, inside the subset — and the box that life shows is THE mini when it has the shape
(layers 3 and 4); otherwise there is none. Nothing here moves the parent; the
story and the state word keep reading the parent; the LPS may be read against the mini (stage 6, on his
condition). A mini never costs a fire: the read calls this stage inside its own guard.

The three layers (OURS, no new number — the parent's own area, half its frozen range, is the only width; his and
frozen):

1. **the parent's right side** — the pair opened after the parent BECAME a box (its birth, not its opening: a pair
   that opened between the parent's opening and its birth is the parent's own counter move, not a rest inside it);
2. **inside or across the parent** — the negation of the walk's "beyond" test: its support under the parent's
   resistance area, its resistance over the parent's support area (otherwise it is a new box's candidate, the
   parent's business);
3. **a small box inside it** — its bottom not under the parent's support area (never wrapping the parent; the
   standard's own ``S < bottom``), and not the parent again (not both lines within the parent's own line areas).

Where the mini sits in the parent is NOT a layer. The build of Sat 03/10/2026 had a fourth, "at the top" (its top
at or over the parent's resistance area, fitted to his two kept minis and three deletions) and asked him; his
answer the same evening: *"what is "at the top" rule? that mini consolidation can only appear at the top of a
consolidation? I don't think we should rule it to be that way we should gate mini consolidation by their
structure its just a semi smaller base inside/in the vicinity of a bigger one"*. The layer is gone: ST's deleted
mini 35.41 / 33.77 (a small box inside, its top under the parent's resistance area) is a mini again, by structure.

Measured on his 40 on his last receding day (Sat 03/10/2026): the three layers leave 11; with the fourth, 5 (DSGN,
EWTX, RGR, VIK, VLO); without layer 3 as well, 22.
"""
from __future__ import annotations

from typing import Optional

from engine_alpha.two_eyes.record import ROLE_MINI, ROLE_PARENT, Box, Step
from engine_alpha.two_eyes.walk import Life, Pair, Walk, _box_record, lives

__all__ = ["STAGE", "a_small_box_inside", "candidates", "could_not_be_read", "find", "inside_or_across",
           "is_a_mini", "lps_box", "on_the_right_side", "record", "where"]

STAGE = "mini"


# --------------------------------------------------------------------------- #
# The three layers, each one predicate                                        #
# --------------------------------------------------------------------------- #
def on_the_right_side(pair: Pair, parent: Pair) -> bool:
    """Layer 1: the pair opened after the parent became a box."""
    return pair.opening_bar > parent.birth_bar


def inside_or_across(pair: Pair, parent: Pair) -> bool:
    """Layer 2: not beyond the parent — the negation of the walk's test for a pair that could take its place."""
    return not (pair.S >= parent.R - parent.area or pair.R <= parent.S + parent.area)


def a_small_box_inside(pair: Pair, parent: Pair) -> bool:
    """Layer 3: its bottom over the parent's support area (never wrapping the parent), and not the parent again
    (both lines within the parent's own line areas is the parent, not a second box)."""
    twin = abs(pair.R - parent.R) <= parent.area and abs(pair.S - parent.S) <= parent.area
    return pair.S >= parent.S - parent.area and not twin


def candidates(found: Walk) -> list:
    """Every pair of the walk's listing that became a box inside the parent's right side (layers 1 and 2), in the
    order they open: the inner boxes the walk's own life is run over."""
    parent = found.winner
    if parent is None:
        return []
    return [p for p in found.pairs.values()
            if p.birth_bar is not None and p.feet != parent.feet
            and on_the_right_side(p, parent) and inside_or_across(p, parent)]


def is_a_mini(pair: Pair, parent: Pair) -> bool:
    """Layer 3 on the inner box the walk's life shows: a small box inside the parent — its structure, not where
    it sits (his ruling of Sat 03/10/2026)."""
    return a_small_box_inside(pair, parent)


# --------------------------------------------------------------------------- #
# The mini's life, by the walk's own rule                                     #
# --------------------------------------------------------------------------- #
def find(found: Walk, high, low, read_bar: int) -> tuple:
    """The mini's life on the read day: ``walk.lives`` over the inner boxes (layers 1 and 2) — the first to
    become a box is shown, and inside the subset it gives way exactly as the parent would. The last life is THE
    mini when the box it shows is a small box inside the parent (layer 3); the lives before it
    are the chain the read tells (words only). Empty when there is none, or when the inner box the walk shows is
    not a mini (a twin of the parent, a band under its support area)."""
    chosen = candidates(found)
    if not chosen:
        return ()
    walked = [t for t in found.ends if t.get("foot_bar") is not None]
    history = tuple(lives(chosen, walked, high, low, read_bar))
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
