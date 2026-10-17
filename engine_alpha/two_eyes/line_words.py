"""The word rules of the two-eyes reader. They CHANGED ON PURPOSE at build task 12b (Fri 02/10/2026): the
upthrust follows his word of Thu 01/10/2026 on ALB ("that breach is not an upthrust in fact there is a later on
25/02/2026 ... that movement in 20/1 -> 27/1 and the crash afterwards could be treated as the place where the
trend ends"): crashing back may take more than one swing (``_crashes_back``), and a push that tops before the
box's fifteenth day is the trend still ending, never an upthrust (``_upthrust_printed``, the ONE predicate both
the upthrust and the spring's "the range ran on" read). Since then: the last supper is named once per box and only
when it digs deep (Sat 03/10 and Sun 04/10/2026), the numbers were re-placed in the box's own daily range (task
12b; the current ones are `two_eyes_numbers`), and the rules are put together in ONE place, :func:`assemble`, which
the story and :func:`read_line_words` both call (council review of Fri 09/10/2026, finding 13). What follows is
the copy's own header, kept for the record; two of its sentences no longer hold HERE: these words are not
measure-only (the story names them on the screen and the grade forgives their own swings), and the floors it
quotes (UNF 0.94, VIK 1.55) were re-measured in the box's own range (UNF 1.21, VIK 1.31: the floor is 1.25).

COPIED from engine_alpha/structure/events/line_words.py at cd87fcc (two-eyes-reader task 7): the word rules — THE SOS, the upthrust, the last supper, Phase C and its spring test, Phase D, the mini, and the reader `read_line_words`; NOT the old engine's flag plumbing (`_WORDS_BY_FLAG`, `any_word_enabled`, `emitted`), which is how the old engine emitted words, not a rule for reading one.

Verbatim, function for function, but for this: every number it reads (the LINE_WORD_* values) comes from the new reader's own
`two_eyes_numbers` instead of the SHARED settings, with the same values; and the line is the
copied swing line in this package. The original stays in the old
engine, frozen, and the old engine keeps reading it; this copy is the new reader's, and changes on
purpose from here. tests/engine/test_two_eyes_copies_equal_originals.py pinned the two equal once, on the
fixtures; the task that first changes this copy deletes that pin in the same commit.

The original's own documentation, unchanged:

The words on the line: build step 5 of the final method (docs/final_method_2026-09.md, points 10 to 15).

A MEASURE-ONLY reader. It reads the ONE turn line (``pivots.turn_line``, build step 4) over the whole frame, the
elected rails, the elected LPS and the elected mini, and returns words. Nothing that elects, vetoes, grades or
displays reads them: no word enters ``box_events._box_events_with_meta``, none replaces ``find_spring``, none
touches ``event_map.read_swing_map``. Every rule is a pure function of the line, so each word can be measured
alone; the step-5 flags only choose which words ride out on a fire (``emitted``).

The unit is the caller's ONE daily range (the zone ATR the evaluation already holds), the unit his numbers were
placed in; the line itself keeps each day's own range for its turns.

HIS WORDS the rules follow: the SOS never gates, is "a quick that covers a lot of ground, Sharp", "reaches or
breaches local Significant Highs like the Resistance" and "most be in Phase D ... after the V tip (either by after
Phase C)" (Q11); one Phase C per box "for now", a dip inside the support area never qualifies, recovery is judged
by the swing (Q14, sixteenth sitting); the last supper is "just another event" after an up-move (Q15); Phase D
opens after the spring and its recovery on SYRE and on the staircase near resistance on PBT (sixteenth sitting);
the mini always has its own rail set (Q13); "Phase C = Spring", deep dips, and "Place also matters a lot and
context going forward also plays a major part" (Mon 14/09/2026). At the SOS sitting (Tue 15/09/2026,
docs/decisions.md): THE SOS is "a push that's like a paradigm shift it signals local buyer strength and seeing an
LPS afterwards makes the Setup more higher quality", and running his push on to a higher top after a small pause
is "fine as long as we don't get some wonky stuff goin on ignoring when a run actually breaks"; the upthrust is
"an Event that belongs in Phase B, it is kind of a 'Reverse' Spring where price climbs quickly out of the structure
then crashes back into the trading range" (his UNF, Thu 11/06/2026); the last supper is "a deep correction after
the breach of resistance in phase D" (his BMRN, "I meant Resistance"). His upthrust tweaks (Wed 16/09/2026): "not
every small false breach of Resistance is one or a candidate for one. and only the swinged that actually breached
gets to be marked (just like a spring) not the entire run up from support with all of the Dips combined, and
usually only one UT is present. and it's the most major/devolped one rather then tiny hiccups in resistance."

DEFAULTS that are mine, placed or measured on his 35 marks, his word owed (docs/decisions.md, build step 5 and the
SOS sitting):
  thrust       a clean up-leg on the line: walk back from a line peak while the earlier peaks stay below it and
               every pause is smaller than a last supper's dig (the pause that stands for his "when a run actually
               breaks"); the launch is the lowest valley reached, inside the box, and its last swing starts at the
               line valley right before the top (his "I just marked the SOS as a single Swing with out dips"). It
               covers at least LINE_WORD_SOS_MIN_GROUND_ATR (his smallest SOS) and its top reaches the resistance
               area or clears the last swing high before the push began.
  THE SOS      of the thrusts launched at or after the Phase C tip (or an earlier LPS low) and topping at or before
               the LPS low, the last one topping after the middle of the box whose top clears, by more than the rail
               area, every high since the Phase C tip (else the box start) printed before the push began and every
               earlier push's top; a later top clearing it by less is that high tested again. A first push launched
               on that first day reads the line peak the floor fell from. With none clearing, the last push after
               the middle (his ANRO: "the last Clear Up swing before the LPS"); with no push after the middle, none.
  upthrust     ONE per box, his words: of the thrusts (the SOS's shape and floor) topping in Phase B (before the
               Phase C tip, else at or before the middle of the box) more than LINE_WORD_UPTHRUST_MIN_POKE_ATR over
               the resistance, that crash back under the resistance area (task 12b: a later line valley under
               it before any higher top; and topping no sooner than the box's fifteenth day), the one that climbed
               furthest out. What is marked is the swing that breached: from the line valley right before the top,
               never the whole run up from support with its dips. Named in hindsight, its knowable_bar is that
               valley's commit. The floor is mine, placed between the breach he crossed out (his UNF, Fri
               05/06/2026: 0.94 ranges over his resistance) and the smallest he has named (his VIK July note, Thu
               14/05/2026: 1.55).
  last supper  in hindsight, off a thrust whose top pokes over the resistance (the breach, any poke: HIS, Sat
               19/09/2026), after the Phase C tip
               and after the middle of the box (the Phase D test here, not the Phase D word), the deepest low within
               LINE_WORD_SUPPER_MAX_DAYS trading days digs at least LINE_WORD_SUPPER_DIG_ATR, sought only on the
               days before a later LPS window opens.
  Phase C      the deepest dip more than the rail area under S that recovered by the swing: before any lower low
               than its tip, a line peak reaches the support area (a high at or above S minus the area) and the
               valley after it has committed higher than the tip. Context going forward (his, Mon 14/09/2026):
               a dip after which the box went back up to the R area and then down under the support area
               again, or printed an upthrust (HIS VIK, Sat 19/09/2026), before the right side opened (the
               round trip or the staircase after it, after the middle,
               else the LPS window's first day) was still Phase B, and the next deepest takes the word
               (NKTR, ORMP).
  spring test  the first line valley after the Phase C back inside the support area, higher than the tip.
  Phase D      the earliest of: the round trip after the Phase C (its recovery reaches the R area, then the next
               valley holds in the support area), the staircase near R after the Phase C (two consecutive line
               valleys, the second higher, both above the box midpoint, the peak between them in the R area),
               THE SOS's last swing once an LPS follows it (not its launch, which can sit on the spring's own low:
               his SYRE, "after the spring and after the price recovers"), the LPS window's first day; only an
               opening AFTER THE MIDDLE of the box counts (HIS: "Yes its a must", Mon 14/09/2026).
  mini         today's elected inner box, as facts; the LPS reads against it when its low sits inside the band or
               within the rail area of it.

Not built: the shakeout (parked by him), the dead-space pardon keyed to a named leg (point 21: a grade change, his
question still open).
"""
from __future__ import annotations

import numpy as np

from engine_alpha import two_eyes_numbers as M
from engine_alpha.two_eyes.swing_line import turn_line, turn_line_floors


def _area(unit: float) -> float:
    return M.LINE_WORD_AREA_ATR * unit


def _middle(start, read_bar):
    """The middle of the box, from its first day to the read day (his Phase D must)."""
    return start + max(1, read_bar - start) / 2.0


def _leg_into(line, i, start, unit):
    """(launch index, ground in ranges) of the clean up-leg into the peak ``line[i]``."""
    top = line[i][2]
    launch = k = i - 1
    while k - 2 >= 0 and line[k - 2][0] >= start:
        q, before = line[k - 1], line[k - 2]
        if q[1] != "peak" or before[1] != "valley" or q[2] >= top:
            break
        if (q[2] - line[k][2]) / unit >= M.LINE_WORD_SUPPER_DIG_ATR:
            break
        k -= 2
        if line[k][2] < line[launch][2]:
            launch = k
    return launch, (top - line[launch][2]) / unit


def thrusts(line, start, R, unit):
    """Every thrust on the line whose leg launches inside the box, oldest first."""
    out = []
    for i in range(1, len(line)):
        if line[i][1] != "peak" or line[i - 1][1] != "valley" or line[i - 1][0] < start:
            continue
        launch, ground = _leg_into(line, i, start, unit)
        # The last swing high before the push began: the leg's own pauses sit under its top by construction.
        last_high = next((line[k][2] for k in range(launch - 1, -1, -1) if line[k][1] == "peak"), None)
        reaches = line[i][2] >= R - _area(unit) or (last_high is not None and line[i][2] > last_high)
        if ground >= M.LINE_WORD_SOS_MIN_GROUND_ATR and reaches:
            out.append({"launch_bar": int(line[launch][0]), "launch_price": float(line[launch][2]),
                        "swing_bar": int(line[i - 1][0]), "top_bar": int(line[i][0]),
                        "top_price": float(line[i][2]), "ground_ranges": round(float(ground), 3),
                        "knowable_bar": line[i][3]})
    return out


def _peak_before(line, bar):
    """The price of the line peak the turn on ``bar`` fell from: the turn right before the valley on that day,
    else the last peak before it."""
    k = next((i for i, t in enumerate(line) if t[0] == bar and t[1] == "valley"), None)
    if k is not None and k > 0:
        return line[k - 1][2]
    return next((t[2] for t in reversed(line) if t[1] == "peak" and t[0] < bar), None)


def pick_the_sos(th, lps_low_bar, after=None, *, line, highs, start, read_bar, unit):
    """THE SOS. Of the thrusts launched at or after ``after`` (the Phase C tip, or an earlier LPS low) and topping at
    or before the LPS low, the last one topping after the middle of the box whose top clears, by more than the rail
    area, every high since ``after`` (else the box start) printed before the push began and every earlier push's
    top; a first push launched on that first day reads the line peak the floor fell from. With none clearing, the
    last push after the middle. With no LPS the same read over every push, in progress: ``in_progress`` means no LPS
    follows it yet. With no push after the middle, none."""
    pool = [t for t in th if after is None or t["launch_bar"] >= after]
    if lps_low_bar is not None:
        pool = [t for t in pool if t["top_bar"] <= lps_low_bar]
    late = [t for t in pool if t["top_bar"] > _middle(start, read_bar)]
    if not late:
        return None
    first = start if after is None else after
    fell_from = _peak_before(line, first)

    def local_high(t):
        prior = [q["top_price"] for q in pool if q["top_bar"] < t["top_bar"]]
        before = highs[first:t["launch_bar"]]                 # before the push began: not its own launch day
        if len(before):
            prior.append(float(np.max(before)))
        if not prior and fell_from is not None:               # nothing printed since the floor: the peak it fell from
            prior.append(fell_from)
        return max(prior, default=float("-inf"))

    breaking = [t for t in late if t["top_price"] > local_high(t) + _area(unit)]
    return {**(breaking or late)[-1], "in_progress": lps_low_bar is None}


def _crashes_back(line, k, R, unit):
    """Where the push topping at the line peak ``line[k]`` crashes back into the range: the first later line
    valley under the resistance area, before any line peak over its top. It may take more than one swing (his ALB,
    Wed 25/02/2026: the next low still holds over the area). The index of that valley, or None while the price
    has not crashed back (or went on to a higher top first)."""
    area, top = _area(unit), line[k][2]
    for j in range(k + 1, len(line)):
        _, kind, price, _ = line[j]
        if kind == "peak" and price > top:
            return None
        if kind == "valley" and price < R - area:
            return j
    return None


def _upthrust_printed(line, k, R, unit, fifteenth=None):
    """ONE predicate for "an upthrust printed" on the line peak ``line[k]``, read by THE upthrust and by the
    spring's "the range ran on": it climbs more than LINE_WORD_UPTHRUST_MIN_POKE_ATR ranges over the resistance,
    it tops no sooner than the box's fifteenth day when that day is given (before it the trend is still ending:
    his ALB, the run of Tue 20/01 to Tue 27/01/2026, "is not an upthrust"), and it crashes back
    (``_crashes_back``). The index of the valley it crashed back to, or None."""
    if (line[k][2] - R) / unit <= M.LINE_WORD_UPTHRUST_MIN_POKE_ATR:
        return None
    if fifteenth is not None and line[k][0] < fifteenth:
        return None
    return _crashes_back(line, k, R, unit)


def the_upthrust(th, line, R, unit, pc, start, read_bar, fifteenth=None):
    """THE upthrust, one per box. His words Tue 15/09/2026: "an Event that belongs in Phase B, it is kind of a
    'Reverse' Spring where price climbs quickly out of the structure then crashes back into the trading range" (his
    UNF, Thu 11/06/2026), tweaked Wed 16/09/2026: "not every small false breach of Resistance is one or a candidate
    for one ... only the swinged that actually breached gets to be marked (just like a spring) not the entire run
    up from support with all of the Dips combined ... usually only one UT is present. and it's the most
    major/devolped one rather then tiny hiccups in resistance."

    Of the thrusts topping in Phase B (before the Phase C tip when the box has one, else at or before the middle of
    the box) for which an upthrust printed (``_upthrust_printed``: the climb over the resistance, the box's
    fifteenth day ``fifteenth`` when given, the crash back under the resistance area), the one that climbed
    furthest out; the earlier one when two climb the same. It is marked from the swing that breached (the line valley right before the top), never the run
    up from support with its dips; that run stays in the record as ``launch_bar``/``launch_price``, data and never
    the mark, and ``candidates`` counts how many pushes reached the pick, so his "usually only one" can be read
    from the measurement. A word read in hindsight: ``knowable_bar`` is the commit of the valley it crashed back to
    (None while that valley forms)."""
    half = _middle(start, read_bar)
    at = {(t[0], t[1]): k for k, t in enumerate(line)}
    best, seen = None, 0
    for t in th:
        p = t["top_bar"]
        in_b = p < pc["tip_bar"] if pc is not None else p <= half
        k = at.get((p, "peak"))
        if not in_b or k is None:
            continue
        back = _upthrust_printed(line, k, R, unit, fifteenth)
        if back is None:
            continue
        poke = (t["top_price"] - R) / unit
        back_bar, _, back_price, know = line[back]
        seen += 1
        if best is None or poke > best[0]:
            # line[k - 1] is the valley the thrust's last swing starts at: the swing that actually breached.
            best = (poke, {"swing_bar": t["swing_bar"], "swing_price": float(line[k - 1][2]), "top_bar": p,
                           "top_price": t["top_price"], "back_bar": int(back_bar), "back_price": float(back_price),
                           "launch_bar": t["launch_bar"], "launch_price": t["launch_price"],
                           "poke_ranges": round(float(poke), 3), "days": int(back_bar) - p, "knowable_bar": know})
    return None if best is None else {**best[1], "candidates": seen}


def last_suppers(th, lows, unit, lps_start, *, R, pc, start, read_bar):
    """The last supper, in hindsight, ONCE per box (his word, Sat 03/10/2026: "a last supper is a noticeable deep
    correction that happens *usually only once either pre or post break out").

    The corrections that qualify: off a thrust whose top breaches resistance (any poke over R, his words Sat
    19/09/2026: "every poke over resistance is a breach even small ones count but that shouldn't worry us at all
    since its still in the resistance area"), after the Phase C tip when there is
    one and after the middle of the box (the Phase D test here is those two clauses, not the Phase D word), whose
    deepest low within four trading days digs as deep as his shallowest less the margin (LINE_WORD_SUPPER_NAMED_DIG_ATR:
    "noticeable deep"; a shallower pause still ends a push). The drop is sought only on the days before a later LPS
    window opens, so a last supper and that LPS never share a day (MRK: his drop ends Thu 30/07/2026, price digs on
    into his LPS window's first day, Mon 03/08). A drop straight into the LPS window is that LPS, not a last supper.

    Of the corrections, the box carries the one off its HIGHEST top (ours: on his eight it is his, or on SILC THE
    SOS's top of the same correction one trading day before his; the deepest loses VIK, the last MRK, the first
    four). So two tops falling into ONE low are
    one correction, named from the higher top (SILC, NTCT, WTS: THE SOS's top and his a day or three later). The
    later top wins an exact tie of price. A list of at most one."""
    if lps_start is None:
        return []
    half = _middle(start, read_bar)
    best = None
    for t in th:
        p = t["top_bar"]
        if t["top_price"] <= R or p <= half or (pc is not None and p <= pc["tip_bar"]):
            continue
        end = min(len(lows) - 1, p + M.LINE_WORD_SUPPER_MAX_DAYS, lps_start - 1)
        if end <= p:
            continue
        k = int(np.argmin(lows[p + 1:end + 1]))
        low_bar = p + 1 + k
        dig = (t["top_price"] - float(lows[low_bar])) / unit
        if dig >= M.LINE_WORD_SUPPER_NAMED_DIG_ATR and (best is None or (t["top_price"], p) >= best[0]):
            best = ((t["top_price"], p), {"top_bar": p, "low_bar": low_bar, "dig_ranges": round(float(dig), 3),
                                          "days": low_bar - p})
    return [] if best is None else [best[1]]


def dips(line, highs, start, S, unit, lows=None):
    """Every line valley more than the rail area under S inside the box, with its recovery by the swing:
    recovered (the answering valley has committed), recovering (it is still forming, or the reaching swing has
    not been answered yet), failed (a lower low than the tip printed first), or under S, undetermined.

    The dip's OWN days are ``first_bar`` to ``tip_bar``: the run of bars under the support area that ends at the
    tip, read on ``lows`` (his GFR, Thu 16/10/2026: *"you marked the bars going up, aka the recover after the
    swing, not the spring itself"*). The recovery is the swing after it: ``reach_bar`` (the first bar whose high
    is back in the area), ``reach_turn_bar`` (the bar of the line peak that reached) and ``confirm_bar``."""
    area = _area(unit)
    out = []
    for i, (vb, vk, vp, _) in enumerate(line):
        if vk != "valley" or vb < start or vp >= S - area:
            continue
        state, reach, confirm = "under S, undetermined", None, None
        for j in range(i + 1, len(line)):
            _, kind, price, know = line[j]
            if kind == "valley" and price <= vp:
                state = "failed"
                break
            if kind == "peak" and reach is None and price >= S - area:
                reach = j
            elif kind == "valley" and reach is not None:
                confirm = j
                state = "recovered" if know is not None else "recovering"
                break
        else:
            if reach is not None:
                state = "recovering"
        reach_bar = None
        if reach is not None:          # from the tip's own bar: one bar may carry the tip and the reaching peak
            seg = np.asarray(highs[vb:line[reach][0] + 1], dtype=float)
            reach_bar = vb + int(np.argmax(seg >= S - area))
        first_bar = int(vb)
        if lows is not None:           # walk back over the bars under the area, never before the box opened
            while first_bar - 1 >= start and float(lows[first_bar - 1]) < S - area:
                first_bar -= 1
        out.append({"start_bar": int(line[i - 1][0]) if i > 0 else None, "first_bar": first_bar, "tip_bar": int(vb),
                    "tip_price": float(vp), "depth_ranges": round(float((S - vp) / unit), 3), "state": state,
                    "reach_bar": reach_bar, "reach_turn_bar": int(line[reach][0]) if reach is not None else None,
                    "confirm_bar": int(line[confirm][0]) if confirm is not None else None,
                    "knowable_bar": line[confirm][3] if confirm is not None else None})
    return out


def _right_side_opens(line, i, start, R, S, unit, lps_start, read_bar):
    """Where the right side would open after the dip at line[i]: the round trip after it (its recovery reaches the
    R area with no lower low first, then the next valley holds the support area) or the first staircase near R
    after it, each only after the middle of the box (his must), else the LPS window's first day."""
    area, mid = _area(unit), (R + S) / 2.0
    half = _middle(start, read_bar)
    opens = []
    j = next((k for k in range(i + 1, len(line)) if line[k][1] == "peak" and line[k][2] >= R - area), None)
    if j is not None and j + 1 < len(line):
        lower_first = any(t[1] == "valley" and t[2] < line[i][2] for t in line[i + 1:j])
        if not lower_first and line[j + 1][2] >= S - area and line[j + 1][0] > half:
            opens.append(int(line[j + 1][0]))
    for k in range(i, len(line) - 2):
        v1, p, v2 = line[k], line[k + 1], line[k + 2]
        if v1[1] == "valley" and v2[2] > v1[2] > mid and p[2] >= R - area and v2[0] > half:
            opens.append(int(v2[0]))
            break
    if lps_start is not None:
        opens.append(int(lps_start))
    return min(opens) if opens else None


def _range_ran_on(line, i, R, S, unit, open_bar, half, fifteenth=None):
    """After the dip at line[i], before the right side opened, the box went back up to the R area and then down
    under the support area again, or an upthrust printed (a top at or before the middle of the box for which
    ``_upthrust_printed`` holds; a later one is a push in
    Phase D): the range was still running, so the dip was Phase B. His VIK (Sat
    19/09/2026): the dip of Wed 29/04/2026 is "No" spring, his upthrust of Thu 14/05/2026 came after it."""
    area, back_at_r = _area(unit), False
    for k in range(i + 1, len(line)):
        b, kind, p, _ = line[k]
        if open_bar is not None and b >= open_bar:
            return False
        if kind == "peak" and p >= R - area:
            back_at_r = True
            if b <= half and _upthrust_printed(line, k, R, unit, fifteenth) is not None:
                return True
        elif kind == "valley" and back_at_r and p < S - area:
            return True
    return False


def phase_c(line, highs, start, S, unit, R, lps_start, read_bar, fifteenth=None, lows=None):
    """One Phase C per box, the spring: the deepest dip that recovered by the swing and after which the range
    did not run on (back to the R area, then under the support area again, before the right side opened)."""
    at = {(t[0], t[1]): k for k, t in enumerate(line)}
    recovered = sorted((d for d in dips(line, highs, start, S, unit, lows=lows) if d["state"] == "recovered"),
                       key=lambda d: -d["depth_ranges"])
    half = _middle(start, read_bar)
    for d in recovered:
        i = at[(d["tip_bar"], "valley")]
        opens = _right_side_opens(line, i, start, R, S, unit, lps_start, read_bar)
        if not _range_ran_on(line, i, R, S, unit, opens, half, fifteenth):
            return d
    return None


def spring_tests(line, pc, S, unit, sos=None):
    """After the Phase C, the FIRST line valley after its recovery that holds over the spring's low and no higher
    than the top of the support area: one test per Phase C. (Naming every such valley named up to 11 on one box,
    so it could never miss one he drew.) A test is a swing of its own, on a bar after the reaching peak's: the
    low of the very bar whose high reached back into the area is the spring's recovery, not a test (his GFR,
    Thu 16/10/2026: two Phase C events, *"one of them is already engulfed in the other"*). It may sit UNDER the
    support area, and the valley THE SOS's swing rises from is the SOS's own, never a test (his AAPL, Fri
    17/10/2026: the test of Tue 06/10 sat 0.55 ranges under support, and *"what you marked as the Test is already
    a part of the SOS"*)."""
    if pc is None:
        return []
    after = pc["reach_turn_bar"] if pc.get("reach_turn_bar") is not None else pc["tip_bar"]
    before = sos["swing_bar"] if sos is not None else None
    for (b, k, p, know) in line:
        if before is not None and b >= before:
            break
        if k == "valley" and b > after and pc["tip_price"] < p <= S + _area(unit):
            return [{"tip_bar": int(b), "tip_price": float(p), "knowable_bar": know}]
    return []


def phase_d(line, start, R, S, unit, pc, sos, lps_start, read_bar):
    """Where the right side opens: the earliest opening AFTER THE MIDDLE of the box, a must (his ruling Mon
    14/09/2026), among the round trip after the Phase C (its recovery reaches the R area, then the next valley holds
    in the support area), the first staircase near R after the Phase C and after the middle (two consecutive line
    valleys, the second higher, both above the box midpoint, the peak between them in the R area), THE SOS's last
    swing once an LPS follows it, and the LPS window's first day. An opening at or before the middle stays listed and
    opens nothing; with no opening after the middle there is no Phase D yet."""
    area, mid = _area(unit), (R + S) / 2.0
    half = _middle(start, read_bar)
    openings = {}
    after = start
    if pc is not None:
        after = pc["tip_bar"]
        i = next(k for k, t in enumerate(line) if t[0] == pc["tip_bar"] and t[1] == "valley")
        j = next((k for k in range(i + 1, len(line)) if line[k][1] == "peak" and line[k][2] >= R - area), None)
        if j is not None and j + 1 < len(line) and line[j + 1][2] >= S - area:
            openings["round trip"] = int(line[j + 1][0])
    stairs = [int(line[k + 2][0]) for k in range(len(line) - 2)
              if line[k][1] == "valley" and line[k][0] >= after
              and line[k + 2][2] > line[k][2] > mid and line[k + 1][2] >= R - area]
    if stairs:
        openings["staircase"] = next((bar for bar in stairs if bar > half), stairs[0])
    if sos is not None and not sos["in_progress"]:
        openings["SOS"] = int(sos["swing_bar"])
    if lps_start is not None:
        openings["LPS"] = int(lps_start)
    later = {name: bar for name, bar in openings.items() if bar > half}
    if not later:
        return None
    opener = min(later, key=lambda name: later[name])
    position = (later[opener] - start) / max(1, read_bar - start)
    return {"open_bar": later[opener], "opener": opener, "position": round(float(position), 3),
            "openings": openings, "before_middle": sorted(set(openings) - set(later))}


def mini(inner, lps, unit, read_bar):
    """Today's elected inner box as the mini, and whether the LPS reads against it."""
    if inner is None:
        return None
    area = _area(unit)
    R, S = float(inner.R), float(inner.S)
    against = None
    if lps is not None:
        against = "mini" if S - area <= float(lps.low) <= R + area else "parent"
    return {"start_bar": int(inner.start_bar), "end_bar": int(read_bar), "R": R, "S": S,
            "days": int(read_bar) - int(inner.start_bar) + 1, "height_ranges": round((R - S) / unit, 3),
            "position": getattr(inner, "position", None), "lps_reads_against": against}


def _empty(unit, read_bar):
    return {"basis": {"unit_atr": unit, "area_atr": M.LINE_WORD_AREA_ATR, "read_bar": read_bar},
            "thrusts": [], "the_sos": None, "the_upthrust": None, "last_suppers": [], "phase_c": None,
            "spring_tests": [], "phase_d": None, "mini": None}


def assemble(line, highs, lows, *, start: int, R: float, S: float, unit: float, read_bar: int,
             lps_start=None, lps_low_bar=None, fifteenth: int) -> dict:
    """The word rules put together ONCE: the pushes, the spring and its tests, THE SOS, THE upthrust, the last
    suppers and the opening of Phase D, on ``line`` (bar, kind, price, knowable bar) inside the box opened on
    ``start``. The story (``story.read``) and :func:`read_line_words` both call it (council review 2026-10-09,
    finding 13); word recall feeds it the reader's own line, in the box's own daily range. ``fifteenth`` is the
    caller's: the story counts it from the end of the trend, a box with no trend end (his own drawn box, in
    word recall) from its own first line."""
    pushes = thrusts(line, start, R, unit)
    spring = phase_c(line, highs, start, S, unit, R, lps_start, read_bar, fifteenth=fifteenth, lows=lows)
    sos = pick_the_sos(pushes, lps_low_bar, after=spring["tip_bar"] if spring is not None else None,
                       line=line, highs=highs, start=start, read_bar=read_bar, unit=unit)
    return {"thrusts": pushes, "phase_c": spring, "the_sos": sos,
            "spring_tests": spring_tests(line, spring, S, unit, sos=sos),
            "the_upthrust": the_upthrust(pushes, line, R, unit, spring, start, read_bar, fifteenth=fifteenth),
            "last_suppers": last_suppers(pushes, lows, unit, lps_start, R=R, pc=spring, start=start,
                                         read_bar=read_bar),
            "phase_d": phase_d(line, start, R, S, unit, spring, sos, lps_start, read_bar)}


def read_line_words(df, box, unit, *, lps=None, inner=None, line=None):
    """Every word on the line inside the elected box, read on the frame's last day. ``box`` carries
    ``start_bar``, ``R`` and ``S``; ``lps`` (``start_bar``, ``low_bar``, ``low``) and ``inner`` (the mini) may be
    None. Bars are the frame's own positions. ``line`` is the turn line to read (bar, kind, price, knowable
    bar); without it the line is built here from the frame's per-bar range, the scalar ``unit`` filling any bar
    with none. Word recall passes the READER's own line, so it measures the words the reader names."""
    n = len(df)
    unit = float(unit) if unit is not None else float("nan")
    if n == 0 or not np.isfinite(unit) or unit <= 0:
        return _empty(None, n - 1)
    rec = _empty(unit, n - 1)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    if line is None:
        line = [(int(b), k, float(p), None if know is None else int(know))      # native types: the record is JSON
                for (b, k, p, know) in turn_line(highs, lows, turn_line_floors(df, unit))]
    start, R, S = int(box.start_bar), float(box.R), float(box.S)
    lps_start = int(lps.start_bar) if lps is not None else None
    lps_low_bar = int(lps.low_bar) if lps is not None else None
    rec.update(assemble(line, highs, lows, start=start, R=R, S=S, unit=unit, read_bar=n - 1,
                        lps_start=lps_start, lps_low_bar=lps_low_bar, fifteenth=start + M.BOX_DAYS - 1),
               mini=mini(inner, lps, unit, n - 1))
    return rec
