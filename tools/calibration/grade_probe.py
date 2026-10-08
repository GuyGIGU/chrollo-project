"""The grade probe (task 14 of the two-eyes-reader build): the hypotheses of the decisions row of Mon 05/10/2026,
measured on his drawings and the junk charts, on the reader's OWN box. It measures and reports; it grades nothing
the reader carries.

Each measure is read on the box the LPS was read against (the mini when the LPS names the mini, else the parent),
in that box's own frozen daily range, over its days from its opening day to the read day. His drawings are read
on his last receding day, each junk chart on its first fire day in its ten-day window (the core board's reads).

    H   the box's height in its own daily range                                      (junk higher)
    S0  the plain average: the median bar's spread over the gap between the lines   (the CONTROL, never a term)
    S1  the share of the box's days whose bar is at least 3/4 of the gap tall       (junk higher)
    S2  the line's legs from one line's area to the other's, per 20 trading days     (junk lower)
    S3  the 90th-percentile bar's spread over the median bar's                       (junk higher)
    V   the spread profile: the last third's median spread over the first third's    (junk higher)
    E   the event map: the committed story words, each kind once                     (junk lower)

What survives (the row, word for word in effect): the rank separation in the stated direction beats the 95th
percentile of the best of the six under 2,000 label shuffles, AND the leave-one-chart-out score beats the same
family's shuffled 95th percentile; at most three, by the leave-one-chart-out score, never two whose rank
correlation is 0.7 or more. The grade: each survivor 1 at his median or better, 0 at the junk fires' median or
worse, linear between; 100 times their average; S at 75, A at 50, B at 25, C below.

The second probe (the decisions row of Mon 05/10/2026, written down after the first found nothing, from his word
"FRPH is total junk because the box is mostly dead space"), on the same box and the same reads:

    D   the box's dead days: over the base (the box's days from its opening day to the day before THE SOS's push
        begins, or to the read day when the story names no SOS whose push begins after the box opened), the share
        of days whose bar does not reach the box: its low above the resistance or its high under the support
                                                                                     (junk higher)

Its test is the first probe's, the family being this one measure. For the record, deciding nothing: D with FRPH
(the chart that taught it) left out, D over the box's whole days to the read day, and D on the parent. When D
survives, THE GRADE is D alone, as written down.

    Dp  D read on the PARENT, the setup's base, whatever box the LPS was read against
                                                                                     (junk higher)

Beside the grade, never in its place, the board prints the grade Dp would give: OURS, chosen AFTER seeing the board
(the result row of Mon 05/10/2026 records the departure), for his call. The base's window is bounded by THE SOS of
the parent's story, not the mini's own: on his VIK the push began before the mini opened, so the mini's base ran to
the read day and counted the mini's own push and pullback; on his VLO the mini sits inside the parent's base and the
price fell out of it for two weeks. Chosen after the board, Dp must beat the BEST OF THE TWO (D and Dp) under the
same shuffles, on both counts, and only when the written-down D survived.

The third reading (the decisions row of Fri 09/10/2026, written down before it was measured: his COLM word *"base
dosen't hold and dosen't answer for an LPS anywhere"* and the study of his 40), always on the PARENT. OURS, every
part chosen after seeing the lists:

    Dh  the base's empty days counted his way: a day whose bar misses the box by more than the line's area (half the
        box's daily range: his 30/08/2026 respect), outside every swing the reader names (his 13/09/2026 story)
                                                                                     (junk higher)
    the hold   after THE SOS's top to the read day, no low more than the line's area under the support; U, how far
               under it the lowest low lies, in daily ranges, for the record. No swing is pardoned here.
    K   the grade's own order: Dh when the base holds, else 1 + Dh                   (junk higher)

The grade: Dh ramps as D did (1 at his median, 0 at the junk fires' median), a base that does not hold scores 0,
and the grade is the smaller of the two. K must beat the best of FOUR (D, Dp, Dh and K) under the same shuffles,
on both counts; when it does, the board grades by the third reading, his to approve.

The fourth reading (the decisions row of Fri 09/10/2026, written down after the third's board): the same Dh, with

    the hold   the base does not hold when, after THE SOS's top, a low falls beyond the support's area AND under the
               base's own lowest low (his "reaches a lower level"): his JAZZ dips under the support on his own LPS
               and stays over its base's low
    K4  Dh when the base holds so, else 1 + Dh                                       (junk higher)

and the ramp's ends from his words, not the medians: 1 at no empty day, 0 at one half ("mostly dead space"). K4
must beat the best of FIVE (D, Dp, Dh, K and K4); when it does, the board grades by the fourth reading.

The fifth reading (his ruling of Fri 09/10/2026, "I'd forgive only that swing," correct): the fourth's hold and ends,

    Dw  Dh with the story narrowed to each named event's own swing on the line: a day is forgiven only inside both
        the reader's span for the event and the line's legs into and out of its extreme (from the last committed
        turn before the event's day to the first after it, else the read day)          (junk higher)
    K5  Dw when the base holds (the fourth's hold), else 1 + Dw                       (junk higher)

K5 must beat the best of SIX (D, Dp, Dh, K, K4 and K5); when it does, the board grades by the fifth reading.

Offline, read-only, sidecars only:

    python -m tools.calibration.grade_probe                  # the board
    python -m tools.calibration.grade_probe --json OUT.json  # and every chart's measures and grade
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

try:
    from tools._bootstrap import configure_path
except ImportError:  # invoked as a script from the repo root
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path  # type: ignore
configure_path(backend=True)

from engine_alpha import two_eyes  # noqa: E402
from engine_alpha.two_eyes import method_numbers as M  # noqa: E402
from engine_alpha.two_eyes import record  # noqa: E402
from tools.calibration.core_board import junk_rows, run_board  # noqa: E402
from tools.regression.marks_corpus import load_corpus  # noqa: E402
from core.calibration.replay import load_sealed_fixture  # noqa: E402

#: The six candidates and the control, each with its stated direction: +1 the junk reads higher, -1 lower.
MEASURES = (("H", +1), ("S1", +1), ("S2", -1), ("S3", +1), ("V", +1), ("E", -1))
CONTROL = ("S0", +1)
#: The second probe's family: his dead space, one measure.
SECOND = (("D", +1),)
#: D read on the parent: OURS, chosen after the board, printed beside the grade for his call, never in its place.
PARENT = ("Dp", +1)
#: The third reading's two numbers (Dh, and K, the grade's own order), and the four readings looked at before it,
#: whose best under the same shuffles it must beat: chosen after the lists, it pays the stricter bar.
HIS_WAY = (("Dh", +1), ("K", +1))
THIRD = SECOND + (PARENT,) + HIS_WAY
#: The fourth reading's order, and the five readings looked at before it.
FOURTH = THIRD + (("K4", +1),)
#: The fourth reading's ramp, from his words: 1 at no empty day, 0 at one half (his FRPH "mostly dead space").
ENDS4 = {"Dh": (0.0, 0.5)}
#: The fifth reading (his ruling of Fri 09/10/2026): the story forgives a named event's own swing only.
FIFTH = FOURTH + (("K5", +1),)
ENDS5 = {"Dw": (0.0, 0.5)}
#: The swings the reader names, whose days are story and never empty (his 13/09/2026 ruling). Phase D is a day.
STORY = (record.SPRING, record.SPRING_TEST, record.UPTHRUST, record.LAST_SUPPER, record.SOS)
#: The story's words the event map counts, each kind once (the spring test rides with its spring).
EVENT_MAP = (record.SPRING, record.UPTHRUST, record.SOS, record.LAST_SUPPER, record.PHASE_D)
SHUFFLES = 2000
TOGETHER = 0.7
KEEP = 3
LETTERS = ((75.0, "S"), (50.0, "A"), (25.0, "B"))
BAR = ("BMRN", "FRPH", "COLM")


def the_box(row: dict, named: bool = True):
    """The pair the measures read: the box the LPS was read against, or (``named=False``) the parent."""
    if named and row.get("lps_box") == two_eyes.ROLE_MINI and row.get("mini_pair") is not None:
        return row["mini_pair"]
    return row["won"]


def ending_sos(row: dict, first: int):
    """THE SOS that ends the base: the story's first SOS, when its push begins after the box opened; else None."""
    sos = next((e for e in row["read"].events if e.kind == record.SOS and e.first_day is not None), None)
    if sos is None:
        return None
    days = [d.date() for d in row["prepared"].index]
    push = days.index(sos.first_day) if sos.first_day in days else None
    return sos if push is not None and push > first else None


def base_end(row: dict, first: int, last: int) -> int:
    """The base's last day: the day before THE SOS's push begins, when the story names one beginning after the box
    opened; else the read day. From THE SOS's push on is the right side, never dead space."""
    sos = ending_sos(row, first)
    if sos is None:
        return last
    return [d.date() for d in row["prepared"].index].index(sos.first_day) - 1


def his_way(row: dict) -> dict:
    """The third reading, on the parent: the base's empty days counted his way (Dh) and the hold after THE SOS's
    top (the decisions row of Fri 09/10/2026)."""
    pair, prepared = row["won"], row["prepared"]
    high = prepared["High"].to_numpy(dtype=float)
    low = prepared["Low"].to_numpy(dtype=float)
    days = [d.date() for d in prepared.index]
    first, last = pair.opening_bar, len(prepared) - 1
    end = base_end(row, first, last)
    area = M.LINE_WORD_AREA_ATR * pair.unit
    named = [e for e in row["read"].events if e.kind in STORY]
    swings = [(e.first_day or e.day, e.last_day or e.day) for e in named]
    beyond = [i for i in range(first, end + 1)
              if low[i] > pair.R + area or high[i] < pair.S - area]     # beyond the line's area: not a hair
    empty = [days[i] for i in beyond
             if not any(a <= days[i] <= b for a, b in swings)]          # outside every named span: not story
    # the fifth reading: each span narrowed to the event's own swing, the line's legs into and out of its extreme
    turns = [t.day for t in row["line"].committed]
    own = [(max(a, max((t for t in turns if t < e.day), default=days[0])),
            min(b, min((t for t in turns if t > e.day), default=days[last]))) for e, (a, b) in zip(named, swings)]
    empty_w = [days[i] for i in beyond if not any(a <= days[i] <= b for a, b in own)]
    sos = ending_sos(row, first)
    right = range(days.index(sos.day) + 1, last + 1) if sos is not None and sos.day in days else range(0)
    lowest = float(low[right.start:right.stop].min()) if len(right) else None
    floor = float(low[first:end + 1].min())                                 # the base's own lowest low
    out = {"Dh": len(empty) / (end - first + 1), "Dh_days": end - first + 1, "Dh_empty": empty,
           "U": max(0.0, (pair.S - lowest) / pair.unit) if lowest is not None else 0.0,
           "holds": lowest is None or lowest >= pair.S - area,
           # the fourth reading: beyond the support's area AND a lower level than the base ever made
           "holds4": lowest is None or lowest >= pair.S - area or lowest >= floor, "floor": floor,
           "Dw": len(empty_w) / (end - first + 1), "Dw_empty": empty_w}
    out["K"] = order_key(out)
    out["K4"] = out["Dh"] if out["holds4"] else 1.0 + out["Dh"]
    out["K5"] = out["Dw"] if out["holds4"] else 1.0 + out["Dw"]
    return out


def order_key(m: dict) -> float:
    """The third grade's own order, label-free: a base that does not hold under every base that holds, then Dh."""
    return m["Dh"] if m["holds"] else 1.0 + m["Dh"]


def measures(row: dict, named: bool = True) -> dict:
    """The nine numbers of one read, or {} when the read shows no box."""
    if row.get("prepared") is None or row.get("won") is None:
        return {}
    pair = the_box(row, named)
    prepared, read = row["prepared"], row["read"]
    high = prepared["High"].to_numpy(dtype=float)
    low = prepared["Low"].to_numpy(dtype=float)
    last = len(prepared) - 1
    first = pair.opening_bar
    end = base_end(row, first, last)
    missed = (low > pair.R) | (high < pair.S)           # the bar does not reach the box: wholly over it or under it
    spread = high[first:last + 1] - low[first:last + 1]
    gap, unit = pair.R - pair.S, pair.unit
    area = M.LINE_WORD_AREA_ATR * unit
    turns = [t for t in row["line"].committed if first <= t.bar <= last]
    legs = sum(1 for a, b in zip(turns, turns[1:])
               if max(a.price, b.price) >= pair.R - area and min(a.price, b.price) <= pair.S + area)
    third = max(1, len(spread) // 3)
    on_parent = None if pair is row["won"] else measures(row, named=False)
    return {
        "H": gap / unit,
        "S0": float(np.median(spread)) / gap,
        "S1": float(np.mean(spread >= 0.75 * gap)),
        "S2": legs / (len(spread) / 20.0),
        "S3": float(np.percentile(spread, 90)) / float(np.median(spread)),
        "V": float(np.median(spread[-third:])) / float(np.median(spread[:third])),
        "E": len({e.kind for e in read.events if e.committed and e.kind in EVENT_MAP}),
        "D": float(np.mean(missed[first:end + 1])),
        "Dp": float(np.mean(missed[first:end + 1])) if on_parent is None else on_parent["D"],
        "D_all": float(np.mean(missed[first:last + 1])),
        "base_days": end - first + 1,
        "Dp_days": end - first + 1 if on_parent is None else on_parent["base_days"],
        "days": len(spread),
        "box": "mini" if pair is not row["won"] else "parent",
        **his_way(row),                                 # the third reading: always the parent
    }


# --------------------------------------------------------------------------- #
# The statistics: one rank separation, one cut, both against shuffled labels   #
# --------------------------------------------------------------------------- #
def auc(x: np.ndarray, junk: np.ndarray, sign: int) -> float:
    """The chance that a junk chart reads worse than one of his (worse: the stated direction), ties half."""
    v = sign * x
    j, g = v[junk], v[~junk]
    return float(((j[:, None] > g[None, :]).sum() + 0.5 * (j[:, None] == g[None, :]).sum()) / (len(j) * len(g)))


def best_cut(v: np.ndarray, junk: np.ndarray) -> float:
    """The cut on ``v`` (junk when above it) that best separates the two, balanced; the lowest of tied bests,
    placed half way to the next value up."""
    j, g = np.sort(v[junk]), np.sort(v[~junk])
    cands = np.concatenate(([-np.inf], np.unique(v)))
    tp = len(j) - np.searchsorted(j, cands, side="right")
    tn = np.searchsorted(g, cands, side="right")
    score = 0.5 * (tp / len(j) + tn / len(g))
    k = int(np.argmax(score))
    if k == 0:
        return -np.inf
    above = cands[k + 1] if k + 1 < len(cands) else cands[k]
    return 0.5 * (cands[k] + above)


def loco(x: np.ndarray, junk: np.ndarray, sign: int) -> float:
    """Leave one chart out: the cut placed on the others, the one left out judged; balanced accuracy."""
    v = sign * x
    said_junk = np.zeros(len(v), dtype=bool)
    keep = np.ones(len(v), dtype=bool)
    for i in range(len(v)):
        keep[i] = False
        said_junk[i] = v[i] > best_cut(v[keep], junk[keep])
        keep[i] = True
    return float(0.5 * (said_junk[junk].mean() + (~said_junk[~junk]).mean()))


def chance(table: dict, junk: np.ndarray, shuffles: int = SHUFFLES, seed: int = 20261005,
           family: tuple = MEASURES) -> tuple:
    """The 95th percentile of the BEST of the family (the six, or the second probe's one), for each score, under
    shuffles of the labels."""
    rng = np.random.default_rng(seed)
    best_auc, best_loco = [], []
    for _ in range(shuffles):
        shuffled = rng.permutation(junk)
        best_auc.append(max(auc(table[m], shuffled, s) for m, s in family))
        best_loco.append(max(loco(table[m], shuffled, s) for m, s in family))
    return float(np.percentile(best_auc, 95)), float(np.percentile(best_loco, 95))


def ranks(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[order] = np.arange(len(x))
    for value in np.unique(x):                     # ties share their average rank
        tied = x == value
        r[tied] = r[tied].mean()
    return r


def rank_corr(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


def survivors(table: dict, junk: np.ndarray, bar_auc: float, bar_loco: float, family: tuple = MEASURES) -> tuple:
    scored = {m: (auc(table[m], junk, s), loco(table[m], junk, s)) for m, s in family}
    passed = sorted((m for m, (a, l) in scored.items() if a > bar_auc and l > bar_loco),
                    key=lambda m: (-scored[m][1], -scored[m][0]))
    kept, dropped = [], []
    sign = dict(family)
    for m in passed:
        # "move together" as graded: each measure turned to its stated direction first, so two that rise apart
        # (a correlation of -0.7 between two measures that both read the junk higher) are not twins
        twin = next((k for k in kept if rank_corr(sign[m] * table[m], sign[k] * table[k]) >= TOGETHER), None)
        if twin is not None:
            dropped.append((m, twin))
        elif len(kept) < KEEP:
            kept.append(m)
        else:
            dropped.append((m, None))
    return scored, kept, dropped


# --------------------------------------------------------------------------- #
# The grade, as the row states it                                             #
# --------------------------------------------------------------------------- #
def ramps(table: dict, junk: np.ndarray, kept: list) -> dict:
    """Each survivor's two ends: 1 at his median or better, 0 at the junk fires' median or worse."""
    return {m: (float(np.median(table[m][~junk])), float(np.median(table[m][junk]))) for m in kept}


def grade(values: dict, ends: dict) -> float:
    if not ends:
        return float("nan")
    points = []
    for m, (full, zero) in ends.items():
        p = (values[m] - zero) / (full - zero) if full != zero else 1.0
        points.append(min(1.0, max(0.0, p)))
    return 100.0 * float(np.mean(points))


def letter(g: float) -> str:
    return next((name for cut, name in LETTERS if g >= cut), "C")


def third_grade(m: dict, ends: dict) -> float:
    """The third reading's grade: the smaller of Dh's ramp and the hold. Each fault sinks a setup alone in his words
    (FRPH by its dead space, COLM by its fall), so a base that does not hold scores 0 whatever its days."""
    return grade(m, ends) if m["holds"] else 0.0


def fourth_grade(m: dict, ends: dict = ENDS4) -> float:
    """The fourth reading's grade: the smaller of Dh's ramp (his ends) and the hold read as his words say it."""
    return grade(m, ends) if m["holds4"] else 0.0


def fourth_term(table: dict, is_junk: np.ndarray, shuffles: int = SHUFFLES) -> tuple:
    """The fourth reading, OURS after the third's board: does K4 beat the best of the five readings looked at under
    the same shuffles, on both counts? Returns (passes?, the bar, its two scores)."""
    bar = chance(table, is_junk, shuffles, family=FOURTH)
    a, l = auc(table["K4"], is_junk, +1), loco(table["K4"], is_junk, +1)
    return a > bar[0] and l > bar[1], bar, (a, l)


def fifth_grade(m: dict, ends: dict = ENDS5) -> float:
    """The fifth reading's grade: the smaller of Dw's ramp (his ends) and the fourth's hold."""
    return grade(m, ends) if m["holds4"] else 0.0


def fifth_term(table: dict, is_junk: np.ndarray, shuffles: int = SHUFFLES) -> tuple:
    """The fifth reading, his ruling after the fourth's board: does K5 beat the best of the six readings looked at
    under the same shuffles, on both counts? Returns (passes?, the bar, its two scores)."""
    bar = chance(table, is_junk, shuffles, family=FIFTH)
    a, l = auc(table["K5"], is_junk, +1), loco(table["K5"], is_junk, +1)
    return a > bar[0] and l > bar[1], bar, (a, l)


def third_term(table: dict, is_junk: np.ndarray, shuffles: int = SHUFFLES) -> tuple:
    """The third reading, OURS after the lists: does its order K beat the best of the four readings looked at (D,
    Dp, Dh and K) under the same shuffles, on both counts? Returns (passes?, the bar, its two scores)."""
    bar = chance(table, is_junk, shuffles, family=THIRD)
    a, l = auc(table["K"], is_junk, +1), loco(table["K"], is_junk, +1)
    return a > bar[0] and l > bar[1], bar, (a, l)


# --------------------------------------------------------------------------- #
# The run                                                                     #
# --------------------------------------------------------------------------- #
def collect() -> tuple:
    """Every chart's measures: his drawings on his last receding day, each junk chart on its first fire day (and
    on every fire day, for the bar)."""
    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    his = []
    for row in run_board(setups, frames):
        on = row["on_last"]
        his.append({"key": row["key"], "ticker": row["ticker"], "junk": False, "fires": bool(row["strict"]),
                    "day": on["day"], "m": measures(on), "parent": measures(on, named=False),
                    "row": on, "setup": row["setup"]})
    junk, silent = [], []
    for row in junk_rows():
        if not row["fires"]:
            silent.append(row["key"])
            continue
        first = row["fires"][0]
        junk.append({"key": row["key"], "ticker": row["ticker"], "junk": True, "fires": True, "day": first["day"],
                     "label": row["label"], "m": measures(first), "parent": measures(first, named=False),
                     "every": [(f["day"], measures(f)) for f in row["fires"]], "row": first, "setup": None})
    return his, junk, silent


def quartiles(x: np.ndarray) -> str:
    q = np.percentile(x, [0, 25, 50, 75, 100])
    return " / ".join(f"{v:.2f}" for v in q)


def board(his: list, junk: list, silent: list, shuffles: int = SHUFFLES) -> tuple:
    charts = [c for c in his + junk if c["m"]]
    no_box = [c["key"] for c in his + junk if not c["m"]]
    is_junk = np.array([c["junk"] for c in charts])
    every = MEASURES + (CONTROL,) + SECOND + (PARENT,) + HIS_WAY + FOURTH[-1:] + FIFTH[-1:]
    table = {m: np.array([c["m"][m] for c in charts], dtype=float) for m, _ in every}
    parent = {m: np.array([c["parent"][m] for c in charts], dtype=float) for m, _ in every}
    bar_auc, bar_loco = chance(table, is_junk, shuffles)
    scored, kept, dropped = survivors(table, is_junk, bar_auc, bar_loco)
    out = [f"THE GRADE PROBE — {int((~is_junk).sum())} of his drawings and {int(is_junk.sum())} junk fires, on the "
           "reader's own box (the one the LPS was read against)", ""]
    if silent:
        out.append(f"  junk charts that never fire in their window (not graded): {', '.join(silent)}")
    if no_box:
        out.append(f"  no box on the read day (not measured): {', '.join(no_box)}")
    out.append(f"  the box measured is the mini on: {', '.join(c['key'] for c in charts if c['m']['box'] == 'mini')}")
    out.append(f"  chance ({shuffles} shuffles, the best of six): rank separation {bar_auc:.3f} · "
               f"leave-one-chart-out {bar_loco:.3f}")
    out.append("")
    out.append(f"  {'':<4}{'his: min / q25 / median / q75 / max':<40}{'junk fires: min / q25 / median / q75 / max':<44}"
               f"{'sep':>6}{'loco':>7}{'parent':>8}")
    for m, sign in MEASURES + (CONTROL,):
        a, l = auc(table[m], is_junk, sign), loco(table[m], is_junk, sign)
        verdict = "KEPT" if m in kept else ("control" if m == CONTROL[0] else
                                           "passes, dropped" if any(m == d for d, _ in dropped) else "")
        out.append(f"  {m:<4}{quartiles(table[m][~is_junk]):<40}{quartiles(table[m][is_junk]):<44}"
                   f"{a:>6.3f}{l:>7.3f}{auc(parent[m], is_junk, sign):>8.3f}  {verdict}")
    for m, twin in dropped:
        why = f"moves with {twin} (rank correlation {rank_corr(table[m], table[twin]):+.2f})" if twin else \
            "a fourth survivor"
        out.append(f"  {m} passes and is dropped: {why}")
    out.append("")
    out.append("  rank correlations: " + " · ".join(
        f"{a}~{b} {rank_corr(table[a], table[b]):+.2f}" for i, (a, _) in enumerate(MEASURES)
        for b, _ in MEASURES[i + 1:]))
    out.append("")
    out.append(f"  SURVIVORS: {', '.join(kept) if kept else 'none'}")
    second, kept2, beside, second_summary = second_probe(charts, table, parent, is_junk, shuffles)
    out.extend(second)
    kept = kept + kept2
    ends = grade_all(charts, table, is_junk, kept, "")
    alt = grade_all(charts, table, is_junk, beside, "_p")
    if ends:
        out.extend(format_grades(charts, junk, ends))
    if alt:
        out.extend(format_grades(charts, junk, alt, "_p", "BESIDE IT, ON THE PARENT (ours, chosen after the board; "
                                                         "his call)"))
    third, third_passes, third_summary = third_probe(charts, table, is_junk, junk, shuffles)
    out.extend(third)
    fourth, fourth_passes, fourth_summary = fourth_probe(charts, table, is_junk, junk, shuffles)
    out.extend(fourth)
    fifth, fifth_passes, fifth_summary = fifth_probe(charts, table, is_junk, junk, shuffles)
    out.extend(fifth)
    out.extend(format_charts(charts, bool(ends), bool(alt), graded_by(fifth_passes, fourth_passes, third_passes)))
    return out, charts, {"kept": kept, "ends": ends, "beside": alt, "chance": [bar_auc, bar_loco],
                         "scored": {m: list(v) for m, v in scored.items()}, "second": second_summary,
                         "third": third_summary, "fourth": fourth_summary, "fifth": fifth_summary}


def graded_by(fifth: bool, fourth: bool, third: bool) -> str:
    """The latest reading that passed its bar, which the chart table and the sheet grade by: "5", "4", "h" or ""."""
    return "5" if fifth else "4" if fourth else "h" if third else ""


def fourth_probe(charts: list, table: dict, is_junk: np.ndarray, junk: list, shuffles: int) -> tuple:
    """The fourth reading's lines (the decisions row of Fri 09/10/2026, after the third's board): the hold read as
    his words say it, K4 against the best of five, the grade on his ends, the bar, and his under S and why."""
    return fixed_ends_probe(charts, table, is_junk, junk, shuffles, "FOURTH", "the fall under the whole base, the ends "
                            "from his word (the decisions row of Fri 09/10/2026, written down after the third's board; "
                            "OURS)", "the five: D, Dp, Dh, K and K4", "4", fourth_term, fourth_grade, ENDS4, "Dh")


def fifth_probe(charts: list, table: dict, is_junk: np.ndarray, junk: list, shuffles: int) -> tuple:
    """The fifth reading's lines (his ruling of Fri 09/10/2026): the story narrowed to each event's own swing, K5
    against the best of six, the grade on his ends, the bar, and his under S and why."""
    return fixed_ends_probe(charts, table, is_junk, junk, shuffles, "FIFTH", "the story forgives an event's own swing "
                            "only (his ruling of Fri 09/10/2026, written down before it ran)",
                            "the six: D, Dp, Dh, K, K4 and K5", "5", fifth_term, fifth_grade, ENDS5, "Dw")


def fixed_ends_probe(charts: list, table: dict, is_junk: np.ndarray, junk: list, shuffles: int, name: str, what: str,
                     family: str, n: str, term, grader, ends: dict, empty: str) -> tuple:
    """A reading graded on his fixed ends with the fourth's hold: its lines, and each chart's grade under ``_<n>``."""
    passes, bar, (a, l) = term(table, is_junk, shuffles)
    broke = lambda junk_side: ", ".join(c["key"] for c in charts if c["junk"] == junk_side and not c["m"]["holds4"])
    held = np.array([c["m"]["holds4"] for c in charts])
    out = ["", f"  THE {name} READING — {what}",
           f"  the hold: his {int(held[~is_junk].sum())} of {int((~is_junk).sum())} hold"
           f"{' (not: ' + broke(False) + ')' if broke(False) else ''}; the junk fires {int(held[is_junk].sum())} of "
           f"{int(is_junk.sum())}{' (not: ' + broke(True) + ')' if broke(True) else ''}",
           f"  chance ({shuffles} shuffles, the best of {family}): rank separation {bar[0]:.3f} · "
           f"leave-one-chart-out {bar[1]:.3f}",
           f"  K{n}  {quartiles(table['K' + n][~is_junk]):<40}{quartiles(table['K' + n][is_junk]):<44}{a:>6.3f}"
           f"{l:>7.3f}  {'passes' if passes else 'fails'}"]
    for c in charts:
        c["grade_" + n] = c["loco_grade_" + n] = grader(c["m"])        # fixed ends: left out, the same grade
        c["letter_" + n] = c["loco_letter_" + n] = letter(c["grade_" + n])
    title = (f"THE GRADE, THE {name} READING (his to approve)" if passes else
             f"THE {name} READING'S GRADE, for the record (it fails the strictest bar)")
    (key, (full, zero)), = ends.items()
    out.extend(format_grades(charts, junk, ends, "_" + n, title, grader,
                             f"    {key}: 1 at {full:.3f} (no empty day), 0 at {zero:.3f} (one half: "
                             "his 'mostly dead space'); a base that does not hold: 0; the ends are fixed, so a chart "
                             "left out grades the same"))
    low = sorted((c for c in charts if not c["junk"] and c["letter_" + n] != "S"), key=lambda c: -c["grade_" + n])
    out.append(f"  his under S on the {name.lower()} reading: {len(low)}")
    for c in low:
        m = c["m"]
        why = ("does not hold: after THE SOS's top it fell under the base's lowest low" if not m["holds4"] else
               f"{len(m[empty + '_empty'])} of its {m['Dh_days']} base days empty his way")
        out.append(f"    {c['key']}: {c['grade_' + n]:.0f} {c['letter_' + n]} — {why}")
    junk_s = [c["key"] for c in charts if c["junk"] and c["letter_" + n] in "SA"]
    out.append(f"  the junk fires at S or A on the {name.lower()} reading: {', '.join(junk_s) if junk_s else 'none'}")
    return out, passes, {"chance": list(bar), "scored": [a, l], "passes": passes, "ends": ends}


def third_probe(charts: list, table: dict, is_junk: np.ndarray, junk: list, shuffles: int) -> tuple:
    """The third reading's lines (the decisions row of Fri 09/10/2026): Dh and the hold, the grade's order against
    the best of the four, its grade on every chart (the grade when it passes, else for the record only), and which
    of his fall under S and why."""
    passes, bar, (a, l) = third_term(table, is_junk, shuffles)
    holds = np.array([c["m"]["holds"] for c in charts])
    under = np.array([c["m"]["U"] for c in charts])
    broke = lambda junk_side: ", ".join(c["key"] for c in charts if c["junk"] == junk_side and not c["m"]["holds"])
    out = ["", "  THE THIRD READING — his way, on the parent, and the hold (the decisions row of Fri 09/10/2026, "
               "written down before it ran; OURS, chosen after the lists)",
           f"  {'':<4}{'his: min / q25 / median / q75 / max':<40}{'junk fires: min / q25 / median / q75 / max':<44}"
           f"{'sep':>6}{'loco':>7}",
           f"  Dh  {quartiles(table['Dh'][~is_junk]):<40}{quartiles(table['Dh'][is_junk]):<44}"
           f"{auc(table['Dh'], is_junk, +1):>6.3f}{loco(table['Dh'], is_junk, +1):>7.3f}",
           f"  U   {quartiles(under[~is_junk]):<40}{quartiles(under[is_junk]):<44}"
           "  (daily ranges under the support after THE SOS's top)",
           f"  the hold: his {int(holds[~is_junk].sum())} of {int((~is_junk).sum())} hold"
           f"{' (not: ' + broke(False) + ')' if broke(False) else ''}; the junk fires {int(holds[is_junk].sum())} of "
           f"{int(is_junk.sum())}{' (not: ' + broke(True) + ')' if broke(True) else ''}",
           f"  chance ({shuffles} shuffles, the best of the four: D, Dp, Dh and the grade's order): rank separation "
           f"{bar[0]:.3f} · leave-one-chart-out {bar[1]:.3f}",
           f"  K   {quartiles(table['K'][~is_junk]):<40}{quartiles(table['K'][is_junk]):<44}{a:>6.3f}{l:>7.3f}"
           f"  {'passes' if passes else 'fails'} (the grade's own order)"]
    ends = grade_all(charts, table, is_junk, ["Dh"], "_h", third_grade)
    title = ("THE GRADE, THE THIRD READING (his to approve)" if passes else
             "THE THIRD READING'S GRADE, for the record (it fails the stricter bar; THE GRADE stays D as written)")
    out.extend(format_grades(charts, junk, ends, "_h", title, third_grade))
    out.append("    a base that does not hold: 0")
    low = sorted((c for c in charts if not c["junk"] and c["letter_h"] != "S"), key=lambda c: -c["grade_h"])
    out.append(f"  his under S on the third reading: {len(low)}")
    for c in low:
        m = c["m"]
        why = (f"does not hold: its lowest low after THE SOS's top lies {m['U']:.2f} daily ranges under the support"
               if not m["holds"] else
               f"{len(m['Dh_empty'])} of its {m['Dh_days']} base days empty his way: "
               + " ".join(f"{d:%d/%m}" for d in m["Dh_empty"][:12]) + (" ..." if len(m["Dh_empty"]) > 12 else ""))
        out.append(f"    {c['key']}: {c['grade_h']:.0f} {c['letter_h']} — {why}")
    return out, passes, {"chance": list(bar), "scored": [a, l], "passes": passes, "ends": ends}


def grade_all(charts: list, table: dict, is_junk: np.ndarray, kept: list, sfx: str, grader=grade) -> dict:
    """Each chart's grade and letter on the kept terms (``sfx`` names the field set), and each graded again with
    the ramps placed without it. Returns the ramps' ends, {} when nothing is kept."""
    ends = ramps(table, is_junk, kept)
    for i, c in enumerate(charts):
        keep = np.ones(len(charts), dtype=bool)
        keep[i] = False
        own = ramps({m: v[keep] for m, v in table.items()}, is_junk[keep], kept)
        c["grade" + sfx], c["loco_grade" + sfx] = grader(c["m"], ends), grader(c["m"], own)
        c["letter" + sfx] = letter(c["grade" + sfx]) if ends else ""
        c["loco_letter" + sfx] = letter(c["loco_grade" + sfx]) if own else ""
    return ends


def second_probe(charts: list, table: dict, parent: dict, is_junk: np.ndarray, shuffles: int) -> tuple:
    """The second probe's lines, its survivors (THE GRADE's terms, as written down), and the parent reading printed
    beside the grade: the dead days against their own chance bar, three readings for the record that decide
    nothing, then Dp against the best of the two."""
    bar_auc, bar_loco = chance(table, is_junk, shuffles, family=SECOND)
    scored, kept, _ = survivors(table, is_junk, bar_auc, bar_loco, family=SECOND)
    base = np.array([c["m"]["base_days"] for c in charts], dtype=float)
    cut = np.array([c["m"]["base_days"] < c["m"]["days"] for c in charts])
    out = ["", "  THE SECOND PROBE — his dead space (the decisions row of Mon 05/10/2026, written down before it ran)",
           f"  the base: his {quartiles(base[~is_junk])} days, the junk fires' {quartiles(base[is_junk])}; ended by "
           f"THE SOS's push on {int(cut[~is_junk].sum())} of his and {int(cut[is_junk].sum())} junk fires",
           f"  chance ({shuffles} shuffles, the one measure): rank separation {bar_auc:.3f} · "
           f"leave-one-chart-out {bar_loco:.3f}", "",
           f"  {'':<4}{'his: min / q25 / median / q75 / max':<40}{'junk fires: min / q25 / median / q75 / max':<44}"
           f"{'sep':>6}{'loco':>7}{'parent':>8}"]
    for m, sign in SECOND:
        a, l = scored[m]
        out.append(f"  {m:<4}{quartiles(table[m][~is_junk]):<40}{quartiles(table[m][is_junk]):<44}"
                   f"{a:>6.3f}{l:>7.3f}{auc(parent[m], is_junk, sign):>8.3f}  {'KEPT' if m in kept else ''}")
    tickers = np.array([c["ticker"] for c in charts])
    without = ~(is_junk & (tickers == "FRPH"))
    whole = np.array([c["m"]["D_all"] for c in charts])
    d, j = table["D"][without], is_junk[without]
    out += ["  for the record, deciding nothing:",
            f"    FRPH (the chart that taught it) left out: separation {auc(d, j, +1):.3f} · "
            f"leave-one-chart-out {loco(d, j, +1):.3f}",
            f"    over the box's whole days to the read day: his median {np.median(whole[~is_junk]):.2f}, the junk "
            f"fires' {np.median(whole[is_junk]):.2f} · separation {auc(whole, is_junk, +1):.3f} · "
            f"leave-one-chart-out {loco(whole, is_junk, +1):.3f}",
            f"    on the parent: separation {auc(parent['D'], is_junk, +1):.3f} · "
            f"leave-one-chart-out {loco(parent['D'], is_junk, +1):.3f}",
            "", f"  SURVIVORS (the second probe): {', '.join(kept) if kept else 'none'}"]
    term, passes, pair_bar, (a, l) = parent_term(table, is_junk, kept, shuffles)
    out += ["", "  BESIDE THE GRADE, NEVER IN ITS PLACE (ours, chosen after the board; his call): D on the parent",
            f"  chance ({shuffles} shuffles, the best of D and Dp): rank separation {pair_bar[0]:.3f} · "
            f"leave-one-chart-out {pair_bar[1]:.3f}",
            f"  Dp  {quartiles(table['Dp'][~is_junk]):<40}{quartiles(table['Dp'][is_junk]):<44}{a:>6.3f}{l:>7.3f}"
            f"  {'passes' if passes else 'fails'}"]
    return out, kept, term, {"chance": [bar_auc, bar_loco], "scored": {m: list(v) for m, v in scored.items()},
                             "parent": {"chance": list(pair_bar), "scored": [a, l], "passes": passes}}


def parent_term(table: dict, is_junk: np.ndarray, survived: list, shuffles: int = SHUFFLES) -> tuple:
    """The parent reading, OURS after the board: Dp, shown beside the grade only when the written-down D survived
    and Dp beats the best of the two under the same shuffles on both counts. Returns (the terms, passes?, the bar,
    its two scores)."""
    bar = chance(table, is_junk, shuffles, family=SECOND + (PARENT,))
    a, l = auc(table["Dp"], is_junk, +1), loco(table["Dp"], is_junk, +1)
    passes = "D" in survived and a > bar[0] and l > bar[1]
    return (["Dp"] if passes else []), passes, bar, (a, l)


def format_grades(charts: list, junk: list, ends: dict, sfx: str = "", title: str = "THE GRADE",
                  grader=grade, said_ends: str = "") -> list:
    tally = lambda cs, key: " · ".join(f"{n} {sum(1 for c in cs if c[key + sfx] == n)}" for n in "SABC")
    his = [c for c in charts if not c["junk"]]
    bad = [c for c in charts if c["junk"]]
    out = [""] + ([said_ends] if said_ends else [
        f"    {m}: 1 at {full:.3f} (his median), 0 at {zero:.3f} (the junk fires' median)" for m, (full, zero) in
        ends.items()])
    out += [f"  {title}: his {len(his)}: {tally(his, 'letter')} · the junk fires: {tally(bad, 'letter')}",
            f"  the same, each chart graded with the ramps placed without it: his {tally(his, 'loco_letter')} · "
            f"the junk fires: {tally(bad, 'loco_letter')}",
            "  THE BAR (BMRN, FRPH, COLM under A on every day they fire):"]
    for j in junk:
        if j["ticker"] not in BAR or not j["m"]:
            continue
        days = [f"{day:%d/%m} {grader(m, ends):.0f} {letter(grader(m, ends))}" for day, m in j["every"] if m]
        out.append(f"    {j['key']}: {', '.join(days)}")
    return out


#: For each later reading the board can grade by: its order, its empty days and its hold.
ORDER_KEY = {"5": "K5", "4": "K4", "h": "K"}
EMPTY_OF = {"5": "Dw_empty", "4": "Dh_empty", "h": "Dh_empty"}
HOLD_OF = {"5": "holds4", "4": "holds4", "h": "holds"}


def format_charts(charts: list, graded: bool, beside: bool = False, third: str = "") -> list:
    """Every chart's numbers: by grade when there is one (the fifth, fourth or third reading's when it passed:
    ``third`` is "5", "4", "h" or ""), else his drawings first, then the junk; the grade on the parent beside it when
    there is one, and the later readings' always."""
    if third:
        order = sorted(charts, key=lambda c: (-c["grade_" + third], c["m"][ORDER_KEY[third]], c["key"]))
    elif graded:
        order = sorted(charts, key=lambda c: -c["grade"])
    else:
        order = sorted(charts, key=lambda c: (c["junk"], c["key"]))
    out = ["", f"  {'chart':<20}{'':<8}{'box':<7}{'days':>5}{'grade':>7} {'':<2}{'loco':>6}"
               + (f"{'parent':>8} {'':<2}" if beside else "") + f"{'third':>7} {'':<2}{'loco':>6}"
               + f"{'fourth':>7} {'':<2}{'fifth':>7} {'':<2}  "
               + "".join(f"{m:>7}" for m, _ in MEASURES) + f"{'S0':>7}{'D':>7}{'base':>6}{'Dp':>7}"
               + f"{'Dh':>7}{'Dw':>7}{'U':>6}{'hold':>6}{'hold4':>6}"]
    for c in order:
        who = "JUNK" if c["junk"] else ("" if c["fires"] else "no fire")
        g = f"{c['grade']:>7.1f} {c['letter']:<2}{c['loco_grade']:>6.1f}" if graded else f"{'':>7} {'':<2}{'':>6}"
        p = f"{c['grade_p']:>8.1f} {c['letter_p']:<2}" if beside else ""
        h = (f"{c['grade_h']:>7.1f} {c['letter_h']:<2}{c['loco_grade_h']:>6.1f}{c['grade_4']:>7.1f} {c['letter_4']:<2}"
             f"{c['grade_5']:>7.1f} {c['letter_5']:<2}")
        out.append(f"  {c['key']:<20}{who:<8}{c['m']['box']:<7}{c['m']['days']:>5}{g}{p}{h}  "
                   + "".join(f"{c['m'][m]:>7.2f}" for m, _ in MEASURES) + f"{c['m']['S0']:>7.2f}"
                   + f"{c['m']['D']:>7.2f}{c['m']['base_days']:>6}{c['m']['Dp']:>7.2f}"
                   + f"{c['m']['Dh']:>7.2f}{c['m']['Dw']:>7.2f}{c['m']['U']:>6.2f}"
                   + f"{'yes' if c['m']['holds'] else 'NO':>6}"
                   + f"{'yes' if c['m']['holds4'] else 'NO':>6}")
    return out


#: The measure an ungraded sheet is ranked by, in plain words: his dead space.
PLAIN = {"D": "his dead space (the share of the base's days on which no bar is in the box)",
         "Dp": "his dead space on the parent (the share of the base's days on which no bar is in the box)"}


#: The measures said to him in plain words, for the pages.
def said(m: dict) -> str:
    base = "the days before THE SOS's push" if m["base_days"] < m["days"] else "no SOS ends it: to the read day"
    parent = f" (on the parent: {m['Dp']:.0%} of its {m['Dp_days']})" if m["box"] == "mini" else ""
    return (f"No bar in the box on {m['D']:.0%} of the base's {m['base_days']} trading days ({base}){parent} · "
            f"bars at least three quarters as tall as the box: {m['S1']:.0%} of its {m['days']} trading days "
            f"(the median bar is {m['S0']:.0%} of the box's height) · the box is {m['H']:.2f} daily ranges tall "
            f"· swings from one line to the other: {m['S2']:.1f} per 20 trading days · the story names "
            f"{m['E']} of the five events · measured on the {m['box']} · counted your way on the parent "
            f"(forgiving only each named event's own swing): {len(m['Dw_empty'])} of the base's {m['Dh_days']} days "
            "empty · after THE SOS's top the base "
            + ("holds" if m["holds4"] else f"does NOT hold: a low {m['U']:.2f} daily ranges under the support, "
               "under the base's own lowest low"))


def render_sheet(charts: list, out_dir: str, rank_by: str, graded: bool, third: str = "") -> str:
    """One OHLC page per chart and ONE sheet, his drawings and the junk fires ranked together: by the latest later
    reading's grade that passed its bar (``third``: "5", "4" or "h"), else by the grade when there is one, else by
    the measure that came closest, best first."""
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tools.calibration.core_board import _render, _words
    from tools.research.full_package_render import _draw_bars

    os.makedirs(out_dir, exist_ok=True)
    sign = dict(MEASURES + SECOND)[rank_by] if not graded else -1
    value = (lambda c: c["grade"]) if graded else (lambda c: c["m"][rank_by])
    order = sorted((c for c in charts if c["m"]), key=lambda c: sign * value(c))
    if third:
        order = sorted((c for c in charts if c["m"]),
                       key=lambda c: (-c["grade_" + third], c["m"][ORDER_KEY[third]], c["key"]))
    cells = []
    for n, c in enumerate(order, 1):
        path = os.path.join(out_dir, f"{n:02d}_{c['key'].replace(':', '_').replace('@', '_')}.png")
        who = "JUNK" if c["junk"] else "yours"
        head = f"{n}. {c['key']} ({who})" + (f" — grade {c['grade']:.0f} {c['letter']}" if graded else "") + (
            f" (on the parent: {c['grade_p']:.0f} {c['letter_p']})" if graded and c.get("letter_p") else "")
        if third:
            head = (f"{n}. {c['key']} ({who}) — grade {c['grade_' + third]:.0f} {c['letter_' + third]}"
                    + (f" (the dead days as written: {c['grade']:.0f} {c['letter']})" if graded else ""))
        _render(plt, _draw_bars, c["row"], path, head, said(c["m"]) + ".  " + _words(c["row"]["read"], None),
                his=c["setup"])
        tag = "miss" if c["junk"] else "hit"
        cells.append(f'<figure class="{tag}"><img src="{os.path.basename(path)}" loading="lazy"><figcaption>'
                     f'<b>{n}. {c["key"]}</b> — {"JUNK: " + c.get("label", "") if c["junk"] else "your drawing"}'
                     + (f' · grade {c["grade"]:.0f} {c["letter"]}, on the parent {c["grade_p"]:.0f} {c["letter_p"]}'
                        if graded and c.get("letter_p") else "")
                     + (f' · grade {c["grade_" + third]:.0f} {c["letter_" + third]} · your way '
                        f'{len(c["m"][EMPTY_OF[third]])} of {c["m"]["Dh_days"]} base days empty · '
                        + ("holds" if c["m"][HOLD_OF[third]] else
                           f'does NOT hold ({c["m"]["U"]:.2f} ranges under the support)')
                        + (f' · as written {c["grade"]:.0f} {c["letter"]}' if graded else "") if third else "")
                     + f' · no bar in the box {c["m"]["D"]:.0%} of the base · tall bars {c["m"]["S1"]:.0%}'
                     f' · box {c["m"]["H"]:.2f} ranges · story {c["m"]["E"]} of 5</figcaption></figure>')
    how = ("by the grade (your way on the parent, and the hold), best first" if third else
           "by the grade, best first" if graded else
           f"by {PLAIN[rank_by]}, fewest first. It is NOT a grade: no measure passed the test written down before "
           "the probe ran")
    html = f"""<!doctype html><meta charset="utf-8">
<title>The grade sheet</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f7;color:#222}}
 h1{{font-size:20px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
 figure{{margin:0;padding:8px;border:2px solid #ddd;border-radius:6px;background:#fff}}
 figure.miss{{border-color:#d62728}} figure.hit{{border-color:#2e8b57}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}}
</style>
<h1>The grade sheet — your drawings and the junk fires, ranked together</h1>
<p>Ranked {how}. OHLC bars. Blue dashed: the reader's box (thin: the mini); red: your lines, your LPS days and
 your buy. Green border: your drawing, read on your last receding day. Red border: a junk chart, read on its first
 fire day. The numbers under each chart are measured on the box the reader's LPS was read against.</p>
<div class="grid">{''.join(cells)}</div>
"""
    sheet = os.path.join(out_dir, "index.html")
    with open(sheet, "w", encoding="utf-8") as f:
        f.write(html)
    return sheet


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="OUT", help="also write every chart's measures and grade here")
    ap.add_argument("--pages", metavar="DIR", help="also write one OHLC page per chart and the ranked sheet here")
    ap.add_argument("--shuffles", type=int, default=SHUFFLES, help=argparse.SUPPRESS)
    args = ap.parse_args()
    started = time.perf_counter()
    his, junk, silent = collect()
    read_in = time.perf_counter() - started
    out, charts, summary = board(his, junk, silent, args.shuffles)
    print("\n".join(out))
    print(f"\n  read in {read_in:.0f}s, measured in {time.perf_counter() - started - read_in:.0f}s")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "charts": [
                {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in c.items()
                 if k not in ("every", "row", "setup")} for c in charts]}, f, indent=1, default=str)
    if args.pages:
        third = graded_by(*(summary[n]["passes"] for n in ("fifth", "fourth", "third")))
        print(f"  the sheet: {render_sheet(charts, args.pages, 'D', bool(summary['kept']), third)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
