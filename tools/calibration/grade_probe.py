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


def measures(row: dict, named: bool = True) -> dict:
    """The seven numbers of one read, or {} when the read shows no box."""
    if row.get("prepared") is None or row.get("won") is None:
        return {}
    pair = the_box(row, named)
    prepared, read = row["prepared"], row["read"]
    high = prepared["High"].to_numpy(dtype=float)
    low = prepared["Low"].to_numpy(dtype=float)
    last = len(prepared) - 1
    first = pair.opening_bar
    spread = high[first:last + 1] - low[first:last + 1]
    gap, unit = pair.R - pair.S, pair.unit
    area = M.LINE_WORD_AREA_ATR * unit
    turns = [t for t in row["line"].committed if first <= t.bar <= last]
    legs = sum(1 for a, b in zip(turns, turns[1:])
               if max(a.price, b.price) >= pair.R - area and min(a.price, b.price) <= pair.S + area)
    third = max(1, len(spread) // 3)
    return {
        "H": gap / unit,
        "S0": float(np.median(spread)) / gap,
        "S1": float(np.mean(spread >= 0.75 * gap)),
        "S2": legs / (len(spread) / 20.0),
        "S3": float(np.percentile(spread, 90)) / float(np.median(spread)),
        "V": float(np.median(spread[-third:])) / float(np.median(spread[:third])),
        "E": len({e.kind for e in read.events if e.committed and e.kind in EVENT_MAP}),
        "days": len(spread),
        "box": "mini" if pair is not row["won"] else "parent",
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


def chance(table: dict, junk: np.ndarray, shuffles: int = SHUFFLES, seed: int = 20261005) -> tuple:
    """The 95th percentile of the BEST of the six, for each score, under shuffles of the labels."""
    rng = np.random.default_rng(seed)
    best_auc, best_loco = [], []
    for _ in range(shuffles):
        shuffled = rng.permutation(junk)
        best_auc.append(max(auc(table[m], shuffled, s) for m, s in MEASURES))
        best_loco.append(max(loco(table[m], shuffled, s) for m, s in MEASURES))
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


def survivors(table: dict, junk: np.ndarray, bar_auc: float, bar_loco: float) -> tuple:
    scored = {m: (auc(table[m], junk, s), loco(table[m], junk, s)) for m, s in MEASURES}
    passed = sorted((m for m, (a, l) in scored.items() if a > bar_auc and l > bar_loco),
                    key=lambda m: (-scored[m][1], -scored[m][0]))
    kept, dropped = [], []
    for m in passed:
        twin = next((k for k in kept if abs(rank_corr(table[m], table[k])) >= TOGETHER), None)
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
    table = {m: np.array([c["m"][m] for c in charts], dtype=float) for m, _ in MEASURES + (CONTROL,)}
    parent = {m: np.array([c["parent"][m] for c in charts], dtype=float) for m, _ in MEASURES + (CONTROL,)}
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
    ends = ramps(table, is_junk, kept)
    for m, (full, zero) in ends.items():
        out.append(f"    {m}: 1 at {full:.3f} (his median), 0 at {zero:.3f} (the junk fires' median)")
    for c in charts:
        c["grade"] = grade(c["m"], ends)
        c["letter"] = letter(c["grade"]) if ends else ""
    # The grade's own leave-one-chart-out: each chart graded with the ramps placed without it.
    for i, c in enumerate(charts):
        keep = np.ones(len(charts), dtype=bool)
        keep[i] = False
        own = ramps({m: v[keep] for m, v in table.items()}, is_junk[keep], kept)
        c["loco_grade"] = grade(c["m"], own)
        c["loco_letter"] = letter(c["loco_grade"]) if own else ""
    if ends:
        out.extend(format_grades(charts, junk, ends))
    out.extend(format_charts(charts, bool(ends)))
    return out, charts, {"kept": kept, "ends": ends, "chance": [bar_auc, bar_loco],
                         "scored": {m: list(v) for m, v in scored.items()}}


def format_grades(charts: list, junk: list, ends: dict) -> list:
    tally = lambda cs, key: " · ".join(f"{n} {sum(1 for c in cs if c[key] == n)}" for n in "SABC")
    his = [c for c in charts if not c["junk"]]
    bad = [c for c in charts if c["junk"]]
    out = ["", f"  THE GRADE: his {len(his)}: {tally(his, 'letter')} · the junk fires: {tally(bad, 'letter')}",
           f"  the same, each chart graded with the ramps placed without it: his {tally(his, 'loco_letter')} · "
           f"the junk fires: {tally(bad, 'loco_letter')}",
           "  THE BAR (BMRN, FRPH, COLM under A on every day they fire):"]
    for j in junk:
        if j["ticker"] not in BAR or not j["m"]:
            continue
        days = [f"{day:%d/%m} {grade(m, ends):.0f} {letter(grade(m, ends))}" for day, m in j["every"] if m]
        out.append(f"    {j['key']}: {', '.join(days)}")
    return out


def format_charts(charts: list, graded: bool) -> list:
    """Every chart's numbers: by grade when there is one, else his drawings first, then the junk."""
    order = sorted(charts, key=lambda c: -c["grade"]) if graded else sorted(charts, key=lambda c: (c["junk"], c["key"]))
    out = ["", f"  {'chart':<20}{'':<8}{'box':<7}{'days':>5}{'grade':>7} {'':<2}{'loco':>5}  "
               + "".join(f"{m:>7}" for m, _ in MEASURES) + f"{'S0':>7}"]
    for c in order:
        who = "JUNK" if c["junk"] else ("" if c["fires"] else "no fire")
        g = f"{c['grade']:>7.1f} {c['letter']:<2}{c['loco_grade']:>5.0f}" if graded else f"{'':>7} {'':<2}{'':>5}"
        out.append(f"  {c['key']:<20}{who:<8}{c['m']['box']:<7}{c['m']['days']:>5}{g}  "
                   + "".join(f"{c['m'][m]:>7.2f}" for m, _ in MEASURES) + f"{c['m']['S0']:>7.2f}")
    return out


#: The measures said to him in plain words, for the pages.
def said(m: dict) -> str:
    return (f"Bars at least three quarters as tall as the box: {m['S1']:.0%} of its {m['days']} trading days "
            f"(the median bar is {m['S0']:.0%} of the box's height) · the box is {m['H']:.2f} daily ranges tall "
            f"· swings from one line to the other: {m['S2']:.1f} per 20 trading days · the story names "
            f"{m['E']} of the five events · measured on the {m['box']}")


def render_sheet(charts: list, out_dir: str, rank_by: str, graded: bool) -> str:
    """One OHLC page per chart and ONE sheet, his drawings and the junk fires ranked together: by the grade when
    there is one, else by the measure that came closest, best first."""
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tools.calibration.core_board import _render, _words
    from tools.research.full_package_render import _draw_bars

    os.makedirs(out_dir, exist_ok=True)
    sign = dict(MEASURES)[rank_by] if not graded else -1
    value = (lambda c: c["grade"]) if graded else (lambda c: c["m"][rank_by])
    order = sorted((c for c in charts if c["m"]), key=lambda c: sign * value(c))
    cells = []
    for n, c in enumerate(order, 1):
        path = os.path.join(out_dir, f"{n:02d}_{c['key'].replace(':', '_').replace('@', '_')}.png")
        who = "JUNK" if c["junk"] else "yours"
        head = f"{n}. {c['key']} ({who})" + (f" — grade {c['grade']:.0f} {c['letter']}" if graded else "")
        _render(plt, _draw_bars, c["row"], path, head, said(c["m"]) + ".  " + _words(c["row"]["read"], None),
                his=c["setup"])
        tag = "miss" if c["junk"] else "hit"
        cells.append(f'<figure class="{tag}"><img src="{os.path.basename(path)}" loading="lazy"><figcaption>'
                     f'<b>{n}. {c["key"]}</b> — {"JUNK: " + c.get("label", "") if c["junk"] else "your drawing"}'
                     f' · tall bars {c["m"]["S1"]:.0%} · box {c["m"]["H"]:.2f} ranges · story {c["m"]["E"]} of 5'
                     f'</figcaption></figure>')
    how = ("by the grade, best first" if graded else
           f"by the measure that came closest ({rank_by}: the share of the box's days whose bar is at least three "
           "quarters of the box's height), fewest first. It is NOT a grade: no measure passed the test written "
           "down before the probe ran")
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
        graded = bool(summary["kept"])
        closest = max(MEASURES, key=lambda ms: summary["scored"][ms[0]][0])[0]
        print(f"  the sheet: {render_sheet(charts, args.pages, closest, graded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
