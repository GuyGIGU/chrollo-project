"""COPIED from engine_alpha/structure/box/box_end.py and engine_alpha/structure/narrative/bricks.py at cd87fcc (two-eyes-reader task 7): the box-end reader — `_committed`, `election_bar`, `_leave_bar`, `_child_end`, `box_end` (the whole module), and its frame-level wrapper `read_box_end` with `_finite` from bricks.py.

Verbatim, function for function, but for this: the two numbers it reads (LINE_WORD_AREA_ATR, BOX_END_BREAKOUT_ATR) come from the new
reader's own `method_numbers` instead of the SHARED settings, with the same values; and
`read_box_end` finds `box_end`, `election_bar` and the line in THIS package rather than importing
them from the old one inside the function. The original stays in the old
engine, frozen, and the old engine keeps reading it; this copy is the new reader's, and changes on
purpose from here. tests/engine/test_two_eyes_copies_equal_originals.py pinned the two equal once, on the
fixtures; the task that first changes this copy deletes that pin in the same commit.

The original's own documentation, unchanged:

The box's end, read on the ONE turn line: points 6, 8 and 26 of the final method, build step 11.

His words: "if the price continues to Rise/Fall with out recovering we can deduce that either that the
consolidating structure we measured ended and the price began to trend" (Q6); "hand-over means the box ended on a
run that never came back, and the box ends ONLY when the child is confirmed (26), dated on the confirming turn, the
parent then frozen back to its breakout day" (point 6); "After the parent's breakout, the first swing whose valley
holds in or above the parent's R area (frozen unit) is the child's root candidate; the child is confirmed the day a
later swing turns at one of the child's own anchors. Until that turn the parent stays the operative box ... The close
is used once, for the breakout day (R15); no close level ends a box" (point 26); "a fire already given to the parent
is never reassigned" and row 1 of point 6's precedence table (a pullback above R that recedes with the trigger
overhead is the parent's LPS and fires) come before row 4 (the child flag); and the mirror under support: "A dip
under the support area ... becomes a spring under 14's swing rule, a breakdown when that swing fails, and then the box
ended at its last turn before the dip" (point 8). A close-dated hand-over is Tested-DEAD.

The child is confirmed when it is a consolidation of its own: point 9's law applied to it, the election committing
when the answering completes, a later committed turn inside the area of EACH of its anchors (with the anchors, his
two turns at each rail). One later turn at one anchor is the parent's own LPS above R (row 1), measured on his marks
(NTCT, SILC, ST, MSGS, Sat 19/09/2026): the parent goes on and fires. The breakdown is the mirror, read the same way:
after the breakdown day (the one use of the close under S) a swing whose peak holds in or below the parent's S area
is a child candidate below, confirmed by its own answering; the parent ended at its last turn before the run left.
A dip that never confirms a child below is "under S, undetermined" (point 8), not an end.

Pure functions of the line, the bars and the elected box; they read no setting but the rail area and R15's margin,
gate nothing and grade nothing. ``narrative._walk_structure`` moves on past an ended box under ``BOX_END_ENABLED``;
the unconfirmed child rides as the chart's state ("root candidate, unconfirmed").
"""
from __future__ import annotations

import numpy as np

from engine_alpha.two_eyes import method_numbers as M
from engine_alpha.two_eyes.swing_line import turn_line, turn_line_floors

__all__ = ["box_end", "election_bar", "read_box_end"]


def _committed(line):
    return [(int(b), k, float(p), know) for (b, k, p, know) in line if know is not None]


def election_bar(line, R, S, second_anchor_bar, area):
    """The day the election committed: the later of the first committed turn inside R's area and the first inside
    S's area after the pair's second anchor (point 9: "the election of the pair commits whenever the answering
    completes"). None when the pair is not yet answered. The frozen unit is the ATR of this day."""
    at_r = at_s = None
    for bar, kind, price, know in _committed(line):
        if bar <= second_anchor_bar:
            continue
        if at_r is None and kind == "peak" and abs(price - R) <= area:
            at_r = int(know)
        elif at_s is None and kind == "valley" and abs(price - S) <= area:
            at_s = int(know)
        if at_r is not None and at_s is not None:
            return max(at_r, at_s)
    return None


def _leave_bar(closes, level, margin, after_bar, up):
    """R15's one use of the close: the first day after ``after_bar`` closing more than ``margin`` beyond ``level``
    (over R going up, under S going down). None while price has not left the box that way."""
    for i in range(int(after_bar) + 1, len(closes)):
        c = float(closes[i])
        if (c > level + margin) if up else (c < level - margin):
            return i
    return None


def _child_end(line, closes, level, area, margin, after_bar, up):
    """One direction of the end, the same read both ways. After the day price left the box (``_leave_bar``), every
    committed swing whose near anchor holds in or beyond the parent's rail area (a valley in or above R going up; a
    peak in or below S going down) is a child root candidate, its two turns the child's anchors; the child is
    confirmed, and the parent ended, when the child's own answering completes: a later committed turn inside the
    area of EACH of its anchors (dated on the later of the two, known on its commit). A near anchor back inside the
    box before that means the run came back: the box goes on, and a later leaving starts the read again. Returns
    ``(end, candidate)``: the end dict when confirmed, else the first unconfirmed candidate or None."""
    turns = _committed(line)
    near_kind, far_kind = ("valley", "peak") if up else ("peak", "valley")
    left = _leave_bar(closes, level, margin, after_bar, up)
    while left is not None:
        candidates = []
        came_back = None
        for i, (bar, kind, price, know) in enumerate(turns):
            if bar <= left:
                continue
            for c in candidates:                             # every turn here sits after the candidate
                if kind == far_kind and abs(price - c["far_price"]) <= area and c["far_answered"] is None:
                    c["far_answered"] = int(know)
                elif kind == near_kind and abs(price - c["near_price"]) <= area and c["near_answered"] is None:
                    c["near_answered"] = int(know)
                if c["far_answered"] is not None and c["near_answered"] is not None:
                    child = ({"climax_bar": c["far_bar"], "climax_price": c["far_price"], "ar_bar": c["near_bar"],
                              "ar_price": c["near_price"]})
                    return ({"kind": "hand-over" if up else "breakdown", "end_bar": int(bar),
                             "known_bar": int(max(c["far_answered"], c["near_answered"])),
                             "left_bar": int(left), "child": child}, None)
            if kind != near_kind:
                continue
            inside = price < level - area if up else price > level + area
            if inside:
                came_back = bar                              # the run came back into the box
                break
            far = next((t for t in reversed(turns[:i]) if t[1] == far_kind), None)
            if far is not None:
                candidates.append({"far_bar": far[0], "far_price": far[2], "near_bar": bar, "near_price": price,
                                   "far_answered": None, "near_answered": None})
        if came_back is None:
            first = candidates[0] if candidates else None
            candidate = ({"climax_bar": first["far_bar"], "climax_price": first["far_price"],
                          "ar_bar": first["near_bar"], "ar_price": first["near_price"], "left_bar": int(left)}
                         if first else None)
            return None, candidate
        left = _leave_bar(closes, level, margin, came_back, up)
    return None, None


def box_end(line, closes, R, S, r_anchor_bar, s_anchor_bar, unit):
    """Has this box ended before the read day? The hand-over above (a child confirmed after the breakout day) and
    the breakdown below (a child confirmed after the breakdown day), whichever is known first. Returns
    ``(end, child_candidate)``: ``end`` is None while the box is live; ``child_candidate`` is the first unconfirmed
    child above when the breakout printed one (the chart's "root candidate, unconfirmed"). The end's ``end_bar`` is
    the parent's last turn before price left (where the parent freezes, point 26 / point 8)."""
    area = float(M.LINE_WORD_AREA_ATR) * float(unit)
    margin = float(M.BOX_END_BREAKOUT_ATR) * float(unit)
    after = max(int(r_anchor_bar), int(s_anchor_bar))
    up, candidate = _child_end(line, closes, float(R), area, margin, after, True)
    down, _below = _child_end(line, closes, float(S), area, margin, after, False)
    ends = [e for e in (up, down) if e is not None]
    if not ends:
        return None, candidate
    end = min(ends, key=lambda e: e["known_bar"])
    turns = _committed(line)
    before = [t[0] for t in turns if t[0] < end["left_bar"]]
    end["end_bar"] = int(before[-1]) if before else int(end["left_bar"])
    return end, candidate


def _finite(x) -> bool:
    try:
        return x is not None and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def read_box_end(df, box, atr):
    """Build step 11 (dark): has this box ended? The line on the whole frame, the unit frozen at the election
    day (the ATR of the day the answering completed, when the frame carries ATR_10; else the walk's ATR), then
    ``box_end.box_end``. Returns ``(end, child_candidate, unit)``."""
    unit = float(atr)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    line = turn_line(highs, lows, turn_line_floors(df, unit))
    area = float(M.LINE_WORD_AREA_ATR) * unit
    day = election_bar(line, float(box.R), float(box.S), max(int(box.r_anchor_bar), int(box.s_anchor_bar)), area)
    if day is not None and "ATR_10" in getattr(df, "columns", ()):
        frozen = float(df["ATR_10"].iloc[min(int(day), len(df) - 1)])
        if _finite(frozen) and frozen > 0:
            unit = frozen
    end, child = box_end(line, df["Close"].to_numpy(dtype=float), float(box.R), float(box.S),
                         int(box.r_anchor_bar), int(box.s_anchor_bar), unit)
    return end, child, unit
