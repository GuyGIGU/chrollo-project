"""Render the above-the-rail question on the two charts that decide it.

WTS is the only mark in the sealed corpus where the TIGHT-BOX widening actually
does the admitting: its box is 6.36% wide, so ``_zone_tolerance`` returns half a
box height (9.170) rather than half an ATR (4.341), and the allowance above the
rail more than doubles - 0.5 ATR becomes 1.056 ATR. SILC is drawn beside it as
the ordinary case: above the rail too, but comfortably inside the flat bound.

The operator's question is visual, so the chart answers exactly it: where the
rail is, where the flat 0.5-ATR bound WOULD have stopped, where the widened
bound actually stops, and where the elected LPS's low sits between them.

Read-only. Renders from the SEALED fixture at the SEALED first_fire, never a
live re-fetch, so the picture and the census numbers cannot disagree.

Usage (repo venv, from the repo root):
    python output/consolidation_evidence_2026-09-02/probes/render_above_rail.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tools._bootstrap import configure_path                       # noqa: E402

configure_path(backend=True)

import matplotlib                                                 # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.patches import Rectangle                          # noqa: E402

from engine_alpha.structure.lps import _zone_tolerance            # noqa: E402
from engine_alpha.structure.narrative import read_structure       # noqa: E402
from tools.above_rail_census import _atr_at                       # noqa: E402
from tools.replay import fixture_frame, load_sealed_fixture       # noqa: E402

CASES = (("WTS:2026-06-12", "2026-06-08"), ("SILC:2026-04-13", "2026-04-10"))
LEAD_IN = 20
BG, PANEL, INK, MUTED = "#0f1218", "#161a23", "#e8ecf4", "#8b94a8"
UP, DOWN = "#3fa96b", "#c8556b"
RAIL, WIDE, FLAT, SHELF = "#e0b64a", "#5b8dd6", "#a78bfa", "#4ade80"


def read_case(frames, key, fire):
    df = fixture_frame(frames, key, None)
    work, atr = _atr_at(df.loc[:fire])
    structure = read_structure(work, atr)
    box, lps = structure.box, structure.lps
    resistance, support = float(box.R), float(box.S)
    return {
        "key": key, "fire": fire, "frame": work, "atr": atr,
        "R": resistance, "S": support,
        "height": resistance - support,
        "width_pct": (resistance - support) / support * 100.0,
        "zone_tol": _zone_tolerance(support, resistance, atr),
        "flat": 0.5 * atr,
        "lps_low": float(lps.low), "lps_zone": lps.zone_type,
        "start": int(box.start_bar),
        "lps_start": int(lps.start_bar),
        "lps_end": min(int(lps.end_bar), len(work) - 1),
    }


def draw(ax, case):
    work = case["frame"]
    lo = max(0, case["start"] - LEAD_IN)
    view = work.iloc[lo:]
    n = len(view)
    tight = case["width_pct"] < 10.0

    ax.set_facecolor(PANEL)

    # The admission area above the rail, and where the flat bound would stop.
    ax.add_patch(Rectangle((-0.5, case["R"]), n, case["zone_tol"],
                           facecolor=WIDE, alpha=0.14, zorder=0))
    ax.axhline(case["R"] + case["zone_tol"], color=WIDE, lw=1.5, zorder=3)
    ax.axhline(case["R"] + case["flat"], color=FLAT, lw=1.4,
               ls=(0, (5, 3)), zorder=3)
    ax.axhline(case["R"], color=RAIL, lw=2.0, zorder=4)
    ax.axhline(case["S"], color=RAIL, lw=2.0, zorder=4)

    # The elected LPS window.
    ls, le = case["lps_start"] - lo, case["lps_end"] - lo
    if le >= 0:
        ax.add_patch(Rectangle((ls - 0.5, view["Low"].min()),
                               max(le - ls + 1, 1),
                               view["High"].max() - view["Low"].min(),
                               facecolor=SHELF, alpha=0.10, zorder=1))
    ax.axhline(case["lps_low"], color=SHELF, lw=1.6, ls=(0, (2, 2)), zorder=5)

    for i in range(n):
        row = view.iloc[i]
        col = UP if float(row["Close"]) >= float(row["Open"]) else DOWN
        ax.plot([i, i], [float(row["Low"]), float(row["High"])],
                color=col, lw=0.9, zorder=2)
        o, c = float(row["Open"]), float(row["Close"])
        ax.add_patch(Rectangle((i - 0.32, min(o, c)), 0.64,
                               max(abs(c - o), case["atr"] * 0.012),
                               facecolor=col, edgecolor=col, lw=0.5, zorder=2))

    gap_atr = (case["lps_low"] - case["R"]) / case["atr"]
    gap_box = (case["lps_low"] - case["R"]) / case["height"]
    ax.set_title(
        f"{case['key'].split(':')[0]}  —  LPS rests {gap_atr:+.3f} ATR above resistance "
        f"({gap_box:+.2f} box heights)",
        color=INK, fontsize=12, pad=10, loc="left")
    ax.text(0.005, 0.965,
            f"box {case['S']:.2f} – {case['R']:.2f}   width {case['width_pct']:.2f}%"
            f"   ATR {case['atr']:.2f}   "
            + ("TIGHT BASE → allowance = half a box height"
               if tight else "normal base → allowance = half an ATR")
            + f"   ({case['zone_tol'] / case['atr']:.3f} ATR)",
            transform=ax.transAxes, color=MUTED, fontsize=8.5, va="top")

    span = case["R"] + case["zone_tol"] - case["S"]
    ax.set_ylim(case["S"] - span * 0.30, case["R"] + case["zone_tol"] + span * 0.26)
    ax.set_xlim(-1, n)
    ax.tick_params(colors=MUTED, labelsize=8)
    for side in ax.spines.values():
        side.set_color("#2a3040")

    # Date ticks so the shelf can be located on a real chart.
    step = max(n // 7, 1)
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([view.index[i].strftime("%b %d") for i in ticks],
                       color=MUTED, fontsize=7.5)

    # A legend instead of inline labels: on a normal base the admission ceiling
    # and the flat bound are the SAME line, and overlapping text hid that.
    coincide = abs(case["zone_tol"] - case["flat"]) < 1e-9
    entries = [
        (RAIL, "-", f"resistance {case['R']:.2f}  /  support {case['S']:.2f}"),
        (SHELF, (0, (2, 2)), f"elected LPS low {case['lps_low']:.2f}"),
    ]
    if coincide:
        entries.append((WIDE, "-", f"admission ceiling = flat 0.5·ATR bound "
                                   f"{case['R'] + case['flat']:.2f}"))
    else:
        entries.append((WIDE, "-", f"admission ceiling {case['R'] + case['zone_tol']:.2f} "
                                   f"(half a box height)"))
        entries.append((FLAT, (0, (5, 3)), f"flat 0.5·ATR bound would stop at "
                                           f"{case['R'] + case['flat']:.2f}"))
    handles = [plt.Line2D([], [], color=c, ls=st, lw=1.8, label=lab)
               for c, st, lab in entries]
    leg = ax.legend(handles=handles, loc="lower left", fontsize=8.2,
                    framealpha=0.92, facecolor=BG, edgecolor="#2a3040",
                    labelcolor=INK, borderpad=0.7, handlelength=2.4)
    leg.set_zorder(9)


def main() -> int:
    frames, _ = load_sealed_fixture()
    cases = [read_case(frames, key, fire) for key, fire in CASES]

    fig, axes = plt.subplots(len(cases), 1, figsize=(13, 9.5))
    fig.patch.set_facecolor(BG)
    for ax, case in zip(axes, cases):
        draw(ax, case)

    fig.suptitle(
        "Does a rest ABOVE the line still read as \"at resistance\"?",
        color=INK, fontsize=14.5, x=0.012, ha="left", y=0.985)
    fig.text(0.012, 0.949,
             "Both fire in your sealed must-fire corpus, both rest ABOVE the rail.",
             color=MUTED, fontsize=9.5, ha="left")
    fig.text(0.012, 0.926,
             "WTS is the only one the TIGHT-BASE widening admits: under 10% wide, "
             "the allowance stops being half an ATR and becomes half a box height.",
             color=MUTED, fontsize=9.5, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.912))

    out = os.path.join(os.path.dirname(__file__), "..", "above_rail_wts_silc.png")
    out = os.path.abspath(out)
    fig.savefig(out, dpi=150, facecolor=BG)
    print(f"wrote {out}")
    for case in cases:
        print(f"  {case['key']:18s} R={case['R']:.3f} low={case['lps_low']:.3f} "
              f"gap={(case['lps_low'] - case['R']) / case['atr']:+.3f} ATR "
              f"tol={case['zone_tol'] / case['atr']:.3f} ATR "
              f"width={case['width_pct']:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
