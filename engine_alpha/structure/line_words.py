"""The words on the line: build step 5 of the final method (docs/final_method_2026-09.md, points 11 to 15).

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
the mini always has its own rail set (Q13).

DEFAULTS that are mine, placed or measured on his 35 marks, his word owed (docs/decisions.md, build step 5):
  thrust       a clean up-leg on the line: walk back from a line peak while the earlier peaks stay below it and
               every pause is smaller than a last supper's dig; the launch is the lowest valley reached, inside
               the box. It covers at least LINE_WORD_SOS_MIN_GROUND_ATR (his smallest SOS) and its top reaches
               the resistance area or clears the last swing high before the push began.
  THE SOS      the last thrust topping before the LPS low (the one the LPS hangs from, or the last before it),
               launched after the Phase C tip when there is one; with no LPS the last thrust, in progress.
  last supper  hindsight only: off a thrust's top, the deepest low within LINE_WORD_SUPPER_MAX_DAYS trading days
               digs at least LINE_WORD_SUPPER_DIG_ATR, sought only on the days before a later LPS window opens.
  Phase C      the deepest dip more than the rail area under S that recovered by the swing: before any lower low
               than its tip, a line peak reaches the support area (a high at or above S minus the area) and the
               valley after it has committed higher than the tip.
  spring test  the first line valley after the Phase C back inside the support area, higher than the tip.
  Phase D      the earliest of: the round trip after the Phase C (its recovery reaches the R area, then the next
               valley holds in the support area), the staircase near R after the Phase C (two consecutive line
               valleys, the second higher, both above the box midpoint, the peak between them in the R area),
               THE SOS's launch once an LPS follows it, the LPS window's first day; only an opening AFTER THE
               MIDDLE of the box counts (HIS: "Yes its a must", Mon 14/09/2026).
  mini         today's elected inner box, as facts; the LPS reads against it when its low sits inside the band or
               within the rail area of it.

Not built: the upthrust (point 10: its collapse test is unplaced and he has drawn none), the shakeout (parked
by him), the dead-space pardon keyed to a named leg (point 21: a grade change, his question still open).
"""
from __future__ import annotations

import json

import numpy as np

from config import settings
from engine_alpha.structure.pivots import turn_line, turn_line_floors

# Which words each step-5 flag lets ride out on a fire. The reader always computes every word.
_WORDS_BY_FLAG = {
    "LINE_WORD_SOS_ENABLED": ("thrusts", "the_sos"),
    "LINE_WORD_LAST_SUPPER_ENABLED": ("last_suppers",),
    "LINE_WORD_PHASE_C_ENABLED": ("phase_c", "spring_tests"),
    "LINE_WORD_PHASE_D_ENABLED": ("phase_d",),
    "LINE_WORD_MINI_ENABLED": ("mini",),
}


def _area(unit: float) -> float:
    return settings.LINE_WORD_AREA_ATR * unit


def _leg_into(line, i, start, unit):
    """(launch index, ground in ranges) of the clean up-leg into the peak ``line[i]``."""
    top = line[i][2]
    launch = k = i - 1
    while k - 2 >= 0 and line[k - 2][0] >= start:
        q, before = line[k - 1], line[k - 2]
        if q[1] != "peak" or before[1] != "valley" or q[2] >= top:
            break
        if (q[2] - line[k][2]) / unit >= settings.LINE_WORD_SUPPER_DIG_ATR:
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
        if ground >= settings.LINE_WORD_SOS_MIN_GROUND_ATR and reaches:
            out.append({"launch_bar": int(line[launch][0]), "launch_price": float(line[launch][2]),
                        "top_bar": int(line[i][0]), "top_price": float(line[i][2]),
                        "ground_ranges": round(float(ground), 3), "knowable_bar": line[i][3]})
    return out


def pick_the_sos(th, lps_low_bar, after=None):
    """THE SOS: the last thrust topping at or before the LPS low (the thrust the LPS hangs from, or the last before
    it; bounding by the low, not the window's first day, keeps a peak that sits inside the window). ``after`` bounds
    the launch: the Phase C tip (his "after the V tip"), or an earlier LPS. With no LPS, the last thrust, in progress."""
    pool = [t for t in th if after is None or t["launch_bar"] >= after]
    if lps_low_bar is None:
        return {**pool[-1], "in_progress": True} if pool else None
    before = [t for t in pool if t["top_bar"] <= lps_low_bar]
    return {**before[-1], "in_progress": False} if before else None


def last_suppers(th, lows, unit, lps_start):
    """The last suppers, in hindsight: the drop is sought only on the days before a later LPS window opens, so a
    last supper and that LPS never share a day (MRK: his drop ends Thu 30/07/2026, price digs on into his LPS
    window's first day, Mon 03/08). A drop straight into the LPS window is that LPS, not a last supper."""
    if lps_start is None:
        return []
    out = []
    for t in th:
        p = t["top_bar"]
        end = min(len(lows) - 1, p + settings.LINE_WORD_SUPPER_MAX_DAYS, lps_start - 1)
        if end <= p:
            continue
        k = int(np.argmin(lows[p + 1:end + 1]))
        low_bar = p + 1 + k
        dig = (t["top_price"] - float(lows[low_bar])) / unit
        if dig >= settings.LINE_WORD_SUPPER_DIG_ATR:
            out.append({"top_bar": p, "low_bar": low_bar, "dig_ranges": round(float(dig), 3),
                        "days": low_bar - p})
    return out


def dips(line, highs, start, S, unit):
    """Every line valley more than the rail area under S inside the box, with its recovery by the swing:
    recovered (the answering valley has committed), recovering (it is still forming, or the reaching swing has
    not been answered yet), failed (a lower low than the tip printed first), or under S, undetermined."""
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
        out.append({"start_bar": int(line[i - 1][0]) if i > 0 else None, "tip_bar": int(vb),
                    "tip_price": float(vp), "depth_ranges": round(float((S - vp) / unit), 3), "state": state,
                    "reach_bar": reach_bar, "confirm_bar": int(line[confirm][0]) if confirm is not None else None,
                    "knowable_bar": line[confirm][3] if confirm is not None else None})
    return out


def phase_c(line, highs, start, S, unit):
    """One Phase C per box: the deepest dip that recovered by the swing."""
    recovered = [d for d in dips(line, highs, start, S, unit) if d["state"] == "recovered"]
    return max(recovered, key=lambda d: d["depth_ranges"]) if recovered else None


def spring_tests(line, pc, S, unit):
    """After the Phase C, the FIRST line valley back inside the support area holding higher than the tip: one test
    per Phase C. (Naming every such valley named up to 11 on one box, so it could never miss one he drew.)"""
    if pc is None:
        return []
    for (b, k, p, know) in line:
        if k == "valley" and b > pc["tip_bar"] and abs(p - S) <= _area(unit) and p > pc["tip_price"]:
            return [{"tip_bar": int(b), "tip_price": float(p), "knowable_bar": know}]
    return []


def phase_d(line, start, R, S, unit, pc, sos, lps_start, read_bar):
    """Where the right side opens: the earliest opening AFTER THE MIDDLE of the box, a must (his ruling Mon
    14/09/2026), among the round trip after the Phase C (its recovery reaches the R area, then the next valley holds
    in the support area), the first staircase near R after the Phase C and after the middle (two consecutive line
    valleys, the second higher, both above the box midpoint, the peak between them in the R area), THE SOS's launch
    once an LPS follows it, and the LPS window's first day. An opening at or before the middle stays listed and opens
    nothing; with no opening after the middle there is no Phase D yet."""
    area, mid = _area(unit), (R + S) / 2.0
    half = start + max(1, read_bar - start) / 2.0
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
        openings["SOS"] = int(sos["launch_bar"])
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
    return {"basis": {"unit_atr": unit, "area_atr": settings.LINE_WORD_AREA_ATR, "read_bar": read_bar},
            "thrusts": [], "the_sos": None, "last_suppers": [], "phase_c": None, "spring_tests": [],
            "phase_d": None, "mini": None}


def read_line_words(df, box, unit, *, lps=None, inner=None):
    """Every word on the line inside the elected box, read on the frame's last day. ``box`` carries
    ``start_bar``, ``R`` and ``S``; ``lps`` (``start_bar``, ``low_bar``, ``low``) and ``inner`` (the mini) may be
    None. Bars are the frame's own positions."""
    n = len(df)
    unit = float(unit) if unit is not None else float("nan")
    if n == 0 or not np.isfinite(unit) or unit <= 0:
        return _empty(None, n - 1)
    rec = _empty(unit, n - 1)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    line = [(int(b), k, float(p), None if know is None else int(know))          # native types: the record is JSON
            for (b, k, p, know) in turn_line(highs, lows, turn_line_floors(df, unit))]
    start, R, S = int(box.start_bar), float(box.R), float(box.S)
    lps_start = int(lps.start_bar) if lps is not None else None
    lps_low_bar = int(lps.low_bar) if lps is not None else None
    th = thrusts(line, start, R, unit)
    pc = phase_c(line, highs, start, S, unit)
    sos = pick_the_sos(th, lps_low_bar, after=pc["tip_bar"] if pc is not None else None)
    rec.update(thrusts=th, the_sos=sos, last_suppers=last_suppers(th, lows, unit, lps_start), phase_c=pc,
               spring_tests=spring_tests(line, pc, S, unit),
               phase_d=phase_d(line, start, R, S, unit, pc, sos, lps_start, n - 1),
               mini=mini(inner, lps, unit, n - 1))
    return rec


def any_word_enabled() -> bool:
    return any(getattr(settings, flag) for flag in _WORDS_BY_FLAG)


def emitted(rec) -> str:
    """The words whose flag is on, as ONE compact JSON string: the only form they leave the reader in."""
    keep = {"basis": rec["basis"]}
    for flag, keys in _WORDS_BY_FLAG.items():
        if getattr(settings, flag):
            keep.update({k: rec[k] for k in keys})
    return json.dumps(keep, sort_keys=True, separators=(",", ":"))
