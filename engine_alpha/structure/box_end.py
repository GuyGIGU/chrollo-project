"""The box's end, read on the ONE turn line: points 6, 8 and 26 of the final method, build step 11.

His words: "if the price continues to Rise/Fall with out recovering we can deduce that either that the
consolidating structure we measured ended and the price began to trend" (Q6); "hand-over means the box ended on a
run that never came back, and the box ends ONLY when the child is confirmed (26), dated on the confirming turn, the
parent then frozen back to its breakout day" (point 6); "After the parent's breakout, the first swing whose valley
holds in or above the parent's R area (frozen unit) is the child's root candidate; the child is confirmed the day a
later swing turns at one of the child's own anchors. Until that turn the parent stays the operative box ... The close
is used once, for the breakout day (R15); no close level ends a box" (point 26); and the mirror under support: "A dip
under the support area ... becomes a spring under 14's swing rule, a breakdown when that swing fails, and then the box
ended at its last turn before the dip" (point 8). A close-dated hand-over is Tested-DEAD.

Pure functions of the line, the bars and the elected box; they read no setting but the rail area and R15's breakout
margin, gate nothing and grade nothing. ``narrative._walk_structure`` moves on past an ended box under
``BOX_END_ENABLED``; the unconfirmed child rides as the chart's state ("root candidate, unconfirmed").
"""
from __future__ import annotations

from config import settings

__all__ = ["box_end", "election_bar"]


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


def _breakout_bar(closes, R, unit, after_bar):
    """R15's one use of the close: the first day after ``after_bar`` closing more than BOX_END_BREAKOUT_ATR ranges
    over R. None while price has not left the box upward."""
    margin = float(settings.BOX_END_BREAKOUT_ATR) * unit
    for i in range(int(after_bar) + 1, len(closes)):
        if float(closes[i]) > R + margin:
            return i
    return None


def _hand_over(line, closes, R, area, unit, after_bar):
    """The upward end. After the breakout day, every committed swing whose valley holds in or above the parent's R
    area is a child root candidate (its peak and that valley are the child's anchors; the first one is the
    chart's "root candidate, unconfirmed"); the day a later committed turn sits inside the area of one candidate's
    anchor, that child is confirmed and the parent ends on that turn. A valley back under the R area before any
    confirmation means the run came back: the box goes on, and a later breakout starts the read again. Returns
    ``(end, candidate)``: the end dict when confirmed, else the first unconfirmed candidate or None."""
    turns = _committed(line)
    breakout = _breakout_bar(closes, R, unit, after_bar)
    while breakout is not None:
        candidates = []
        came_back = None
        for i, (bar, kind, price, know) in enumerate(turns):
            if bar <= breakout:
                continue
            for c in candidates:                             # a later turn at one of a child's own anchors
                if bar > c["ar_bar"] and ((kind == "valley" and abs(price - c["ar_price"]) <= area)
                                          or (kind == "peak" and abs(price - c["climax_price"]) <= area)):
                    return ({"kind": "hand-over", "end_bar": int(bar), "known_bar": int(know),
                             "breakout_bar": int(breakout), "child": c}, None)
            if kind != "valley":
                continue
            if price < R - area:
                came_back = bar                              # the run came back into the box
                break
            peak = next((t for t in reversed(turns[:i]) if t[1] == "peak"), None)
            if peak is not None:
                candidates.append({"climax_bar": peak[0], "climax_price": peak[2], "ar_bar": bar,
                                   "ar_price": price, "breakout_bar": int(breakout)})
        if came_back is None:
            return None, (candidates[0] if candidates else None)
        breakout = _breakout_bar(closes, R, unit, came_back)
    return None, None


def _breakdown(line, S, area, after_bar):
    """The downward end (the mirror). A committed valley more than the area under S after ``after_bar`` is a dip;
    its tip is its lowest low so far. It recovers by the swing (point 14: a later peak reaches the support area
    and the valley after it commits higher than the tip) and is then a spring, not an end; it fails when that
    swing fails: a peak reached the support area and the valley after it printed under the tip. The box then
    ended at its last turn before the dip, known on that valley's commit. A lower low with no such attempt before
    it only deepens the dip: still open, undetermined, no end. Returns the end dict or None."""
    turns = _committed(line)
    for i, (bar, kind, price, know) in enumerate(turns):
        if bar <= after_bar or kind != "valley" or price >= S - area:
            continue
        tip, attempted = price, False
        for j in range(i + 1, len(turns)):
            b2, k2, p2, know2 = turns[j]
            if k2 == "peak":
                if p2 >= S - area:
                    attempted = True                          # the recovery swing reached the support area
                continue
            if p2 > tip and attempted:
                break                                         # recovered by the swing: a spring, not an end
            if p2 < tip:
                if attempted:
                    last_turn_before = turns[i - 1][0] if i > 0 else bar
                    return {"kind": "breakdown", "end_bar": int(last_turn_before), "known_bar": int(know2),
                            "dip_bar": int(bar), "lower_low_bar": int(b2)}
                tip = p2                                      # the dip deepens; not decided yet
        else:
            return None                                       # the dip is still open: undetermined, no end yet
    return None


def box_end(line, closes, R, S, r_anchor_bar, s_anchor_bar, unit):
    """Has this box ended before the read day? The hand-over (upward) and the breakdown (downward), whichever is
    known first. Returns ``(end, child_candidate)``: ``end`` is None while the box is live; ``child_candidate`` is
    the unconfirmed child's anchors when a breakout printed one (the chart's "root candidate, unconfirmed")."""
    area = float(settings.LINE_WORD_AREA_ATR) * float(unit)
    after = max(int(r_anchor_bar), int(s_anchor_bar))
    up, candidate = _hand_over(line, closes, float(R), area, float(unit), after)
    down = _breakdown(line, float(S), area, after)
    ends = [e for e in (up, down) if e is not None]
    if not ends:
        return None, candidate
    return min(ends, key=lambda e: e["known_bar"]), candidate
