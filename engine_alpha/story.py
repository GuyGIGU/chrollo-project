"""Stage 5, the story: the words the drawing printed against the box shown — THE SOS, the upthrust, the last
supper, the spring and its test, Phase C and Phase D — as the rules that find them and the dated events they make.
"""
from __future__ import annotations

from typing import Optional
import numpy as np
from engine_alpha import numbers as M
from engine_alpha.record import (LAST_SUPPER, PHASE_D, SOS, SPRING, SPRING_TEST, UPTHRUST, Event, Step)
from engine_alpha.line import turn_line, turn_line_floors


#: The stage name of the story's one step on the trail.
STAGE = "story"

def _lps_days(pullback, low) -> tuple:
    """The first day and the low's day of the pullback the words lean on: the one the LPS stage measured, when it
    stood on its last day (none of his sentences refused it and the box was a box), whether it has since been
    bought or not. ``(None, None)`` otherwise."""
    if pullback is None or not pullback.stood:
        return None, None
    start, end = int(pullback.start_bar), int(pullback.end_bar)
    return start, start + int(np.argmin(low[start:end + 1]))

def read(turns, high, low, days, *, start_bar: int, R: float, S: float, unit: float, read_bar: int,
         pullback=None, trend_end_bar: Optional[int] = None) -> tuple:
    """The events of the box shown, oldest first. ``turns`` is the read's own line, forming turn included;
    ``start_bar`` the day the box opened; ``unit`` the one daily range the words are measured in; ``pullback``
    what the LPS stage measured, or None; ``trend_end_bar`` the top (or low) of the trend the box took its place
    from, when it took it from a box anchored inside that trend.

    "The trend still ending": a push that tops within fourteen trading days of the END OF THE TREND is no
    upthrust. The trend's end is the box's first line, or the earlier ``trend_end_bar`` when there is one: his ALB
    (Thu 01/10/2026), "even a later pair could work if that movement in 20/1 -> 27/1 and the crash afterwards
    could be treated as the place where the trend ends" and "there is a later [upthrust] on 25/02/2026". On the
    reader's own, later ALB box (it opens Thu 05/02/2026) the trend ended on Tue 27/01/2026, so the push of Wed
    25/02 is his upthrust there too; counted from the box's own first line it would be one day short."""
    line = [(int(t.bar), t.kind, float(t.price), None if t.knowable_bar is None else int(t.knowable_bar))
            for t in turns]
    start, read_bar, unit = int(start_bar), int(read_bar), float(unit)
    ended = start if trend_end_bar is None else min(start, int(trend_end_bar))
    fifteenth = ended + M.BOX_DAYS - 1
    lps_start, lps_low_bar = _lps_days(pullback, low)
    at = {(bar, kind): know for bar, kind, _, know in line}

    def day(bar: Optional[int]):
        return None if bar is None else days[int(bar)]

    words = assemble(line, high, low, start=start, R=R, S=S, unit=unit, read_bar=read_bar,
                        lps_start=lps_start, lps_low_bar=lps_low_bar, fifteenth=fifteenth)
    pushes, spring, sos = words["thrusts"], words["phase_c"], words["the_sos"]
    out = []
    if spring is not None:
        # The spring's days are its own dip, first bar under the support area to the tip; the recovery is the
        # swing after it (his GFR, Thu 16/10/2026: "not the spring itself"). Its commit day is the recovery's.
        out.append(Event(kind=SPRING, day=day(spring["tip_bar"]), price=spring["tip_price"],
                         first_day=day(spring["first_bar"]), last_day=day(spring["tip_bar"]),
                         size=spring["depth_ranges"], committed=spring["knowable_bar"] is not None,
                         known_day=day(spring["knowable_bar"])))
    for test in words["spring_tests"]:
        out.append(Event(kind=SPRING_TEST, day=day(test["tip_bar"]), price=test["tip_price"],
                         committed=test["knowable_bar"] is not None, known_day=day(test["knowable_bar"])))
    up = words["the_upthrust"]
    if up is not None:
        out.append(Event(kind=UPTHRUST, day=day(up["top_bar"]), price=up["top_price"],
                         first_day=day(up["swing_bar"]), last_day=day(up["back_bar"]), size=up["poke_ranges"],
                         committed=up["knowable_bar"] is not None, known_day=day(up["knowable_bar"])))
    sos_settled = sos is not None and sos["knowable_bar"] is not None and not sos["in_progress"]
    if sos is not None:
        settled = sos_settled
        out.append(Event(kind=SOS, day=day(sos["top_bar"]), price=sos["top_price"], first_day=day(sos["swing_bar"]),
                         last_day=day(sos["top_bar"]), size=sos["ground_ranges"], committed=settled,
                         known_day=day(sos["knowable_bar"]) if settled else None,
                         note="" if not sos["in_progress"] else "no LPS follows it yet"))
    tops = {t["top_bar"]: t["top_price"] for t in pushes}
    for supper in words["last_suppers"]:
        out.append(Event(kind=LAST_SUPPER, day=day(supper["top_bar"]), price=tops[supper["top_bar"]],
                         first_day=day(supper["top_bar"]), last_day=day(supper["low_bar"]),
                         size=supper["dig_ranges"], committed=True, known_day=day(supper["low_bar"])))
    opens = words["phase_d"]
    if opens is not None:
        bar, opener = int(opens["open_bar"]), opens["opener"]
        # The right side's opening is as settled as what opened it: a low of the line that has committed (the
        # round trip, the staircase); THE SOS once THE SOS is itself settled; the LPS once it has been bought
        # (until then the pullback is only the read day's own, and tomorrow's read may measure another).
        low_known = at.get((bar, "valley"))
        bought = None if pullback is None else pullback.crossed_bar
        known = {"round trip": low_known, "staircase": low_known,
                 "SOS": sos["knowable_bar"] if sos_settled else None, "LPS": bought}[opener]
        out.append(Event(kind=PHASE_D, day=day(bar), price=float(low[bar]), committed=known is not None,
                         known_day=None if known is None else day(max(int(known), bar)), note=opener))
    return tuple(sorted(out, key=lambda e: (e.day, e.kind)))

def _said(event: Event) -> str:
    words = {SPRING: "the spring's tip", SPRING_TEST: "the spring's test", UPTHRUST: "THE upthrust tops",
             SOS: "THE SOS tops", LAST_SUPPER: "a last supper tops", PHASE_D: "Phase D opens"}[event.kind]
    price = "" if event.kind == PHASE_D else f" at {event.price:.2f}"
    note = f" ({event.note})" if event.note else ""
    return f"{words} {event.day:%a %d/%m/%Y}{price}{note}{'' if event.committed else ', provisional'}"

def record(events) -> tuple:
    """The story's one step on the trail: the words, in the order of their days."""
    if not events:
        return (Step(STAGE, "the story: no word is named on this box yet"),)
    return (Step(STAGE, "the story: " + "; ".join(_said(e) for e in events)),)

def could_not_be_read(exc: BaseException) -> tuple:
    """The step a story that fell over leaves: the read stands, the words are missing, and the trail says why."""
    return (Step(STAGE, f"the story could not be read ({type(exc).__name__}: {exc}); the read stands without it"),)


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
