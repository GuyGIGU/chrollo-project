"""Layer-2 staircase chart renderer — see the labeled staircase ON the chart.

For each ticker: replay the live spine to the active equilibrium box the LPS
lives in, run ``read_box_staircase`` over that box's base, and draw a PNG —
OHLC bars (bars, not candles) + the S/R rails + the labeled HH/HL/LH/LL
staircase line, with each swing's RAW GEOMETRIC rail event marked:

    red  v  below S   breach_S   (candidate spring OR breakdown — unclassified)
    grn  ^  above R   breach_R   (candidate SOS OR upthrust — unclassified)
    blue o  at a rail  touch_R / touch_S
    gray .  interior

These are GEOMETRY, not Wyckoff verdicts: a breach_R is only "a swing broke R".
Whether it is an SOS (strength that HOLDS, confirmed by a later LPS) or an
upthrust (a breach that FAILS back into the range) is decided by what comes
AFTER — that classification is Layer-2 Brick 2, not this substrate.

Reads the live parquet cache; changes nothing. PNGs go to the scratchpad (or
``--out DIR``).

    python -m tools.l2_staircase_render AEF NMAI BHF CSCO
    python -m tools.l2_staircase_render --cluster --out tools/fidelity/l2
"""
from __future__ import annotations

import argparse
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd

from config import settings
from core.structure.metrics import measure_resistance_events, read_box_staircase
from tools.lps_swing_census import CLUSTER, _first_complete, _latest_scan_fires
from tools.structure_case_audit import _prep

# R-rail event zone shading (Brick 2): SOS held = green band, upthrust = red,
# in_progress = gray. Rejections are ordinary range work — not shaded.
_ZONE_STYLE = {"SOS": "#1f9d8b", "upthrust": "#e04848", "in_progress": "#9aa0aa"}

_SCRATCH = os.environ.get(
    "CLAUDE_SCRATCH",
    os.path.join(_THIS, "fidelity", "l2"),
)

# RAW GEOMETRIC rail events — NOT classified Wyckoff verdicts. breach_R is just
# "broke R"; SOS (holds, confirmed by an LPS) vs upthrust (fails back in) is a
# Brick-2 read of what comes after, not a property of the breach itself.
_EVENT_STYLE = {
    "breach_S": ("v", "#e04848", "breach S (raw)"),
    "breach_R": ("^", "#1f9d8b", "breach R (raw)"),
    "touch_R": ("o", "#5b8aff", "touch R"),
    "touch_S": ("o", "#5b8aff", "touch S"),
    "interior": (".", "#9aa0aa", "interior"),
}


def _draw_bars(ax, plot_df):
    o = plot_df["Open"].values if "Open" in plot_df else plot_df["Close"].values
    h = plot_df["High"].values
    low = plot_df["Low"].values
    c = plot_df["Close"].values if "Close" in plot_df else plot_df["High"].values
    tick = 0.34
    bar_lw = 1.0 if len(plot_df) > 90 else 1.3
    for i in range(len(plot_df)):
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=bar_lw, alpha=0.55, zorder=2)
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=bar_lw, alpha=0.55, zorder=2)
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=bar_lw, alpha=0.55, zorder=2)


def _render_one(ax, ticker, df, atr, box):
    from matplotlib.patches import Rectangle

    start = int(box.start_bar)
    base = df.iloc[start:].reset_index(drop=True)
    R, S = float(box.R), float(box.S)
    out = read_box_staircase(df.iloc[start:], R, S, atr)
    last_x = len(base) - 1

    ax.add_patch(Rectangle((-0.4, S), last_x + 0.8, max(R - S, 1e-9),
                           facecolor="#8b5cf6", alpha=0.08, edgecolor="none", zorder=0))
    ax.axhline(R, color="#5b8aff", ls="--", lw=1.0, alpha=0.85)
    ax.axhline(S, color="#5b8aff", ls="--", lw=1.0, alpha=0.85)
    ax.text(last_x, R, " R", color="#5b8aff", va="center", fontsize=8, fontweight="bold")
    ax.text(last_x, S, " S", color="#5b8aff", va="center", fontsize=8, fontweight="bold")

    _draw_bars(ax, base)

    sw = out["swings"]
    if sw:
        xs = [s["bar"] for s in sw]
        ys = [s["price"] for s in sw]
        # The staircase line itself.
        ax.plot(xs, ys, color="#e0a030", lw=1.6, alpha=0.9, zorder=4)
        for s in sw:
            marker, color, _ = _EVENT_STYLE.get(s["rail_event"], _EVENT_STYLE["interior"])
            ms = 9 if s["rail_event"].startswith("breach") else 6
            ax.plot(s["bar"], s["price"], marker=marker, color=color,
                    markersize=ms, zorder=5)
            # Label HH/HL/LH/LL above peaks, below valleys.
            if s["label"] in ("HH", "HL", "LH", "LL"):
                dy = 1 if s["kind"] == "peak" else -1
                ax.annotate(s["label"], (s["bar"], s["price"]),
                            textcoords="offset points", xytext=(0, 9 * dy),
                            ha="center", fontsize=7.5, color="#333",
                            va="bottom" if dy > 0 else "top")

    # Brick 2: shade each R-rail event zone + label its peak (rejections are
    # ordinary range work, not shaded).
    for e in measure_resistance_events(df.iloc[start:], R, S, atr):
        if e["type"] in ("rejection", "range"):   # range = Phase-B, not an SOS
            continue
        col = _ZONE_STYLE.get(e["type"], "#9aa0aa")
        ax.axvspan(e["zone_start"] - 0.4, e["zone_end"] + 0.4,
                   color=col, alpha=0.10, zorder=1)
        tag = e["type"] + (f" str{e['strength_box']:.1f}"
                           if e.get("strength_box") is not None else "")
        ax.annotate(tag, (e["peak_bar"], e["peak_price"]),
                    textcoords="offset points", xytext=(0, 24), ha="center",
                    fontsize=8, fontweight="bold", color=col,
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.1))

    # Sparse date ticks.
    n = len(base)
    step = max(1, n // 8)
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(df.index[start + t])[:10] for t in ticks],
                       rotation=35, ha="right", fontsize=7)

    c = out["counts"]
    ax.set_title(
        f"{ticker}   S={S:.2f} R={R:.2f}   "
        f"HH:{c['HH']} HL:{c['HL']} LH:{c['LH']} LL:{c['LL']}   "
        f"trend={out['trend_state']}   is_zigzag={out['is_zigzag']}",
        fontsize=11, fontweight="bold", loc="left",
    )
    ax.set_xlim(-1, last_x + 1)
    ax.margins(y=0.10)
    ax.grid(True, alpha=0.12)


def render(tickers, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))
    written = []

    for t in tickers:
        t = t.upper()
        if t not in level0:
            print(f"  [skip {t}] not in cache")
            continue
        prep = _prep(d[t].dropna())
        if prep[0] is None:
            print(f"  [skip {t}] prep-reject: {prep[1]}")
            continue
        df, atr = prep
        box, _lps = _first_complete(df, atr)
        if box is None:
            print(f"  [skip {t}] no-complete-narrative (does not fire today)")
            continue

        fig, ax = plt.subplots(figsize=(14, 7))
        _render_one(ax, t, df, atr, box)
        # Legend for the rail-event markers.
        from matplotlib.lines import Line2D
        handles = [Line2D([0], [0], marker=m, color="w", markerfacecolor=col,
                          markersize=9, label=lbl)
                   for (m, col, lbl) in _EVENT_STYLE.values()]
        ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.9)
        fig.tight_layout()
        path = os.path.join(out_dir, f"l2_{t}.png")
        fig.savefig(path, dpi=130)
        plt.close(fig)
        written.append(path)
        print(f"  rendered {t} -> {path}")

    print(f"\nCharts in: {out_dir}")
    return written


def main():
    ap = argparse.ArgumentParser(description="Layer-2 staircase chart renderer.")
    ap.add_argument("tickers", nargs="*", help="tickers (default: latest-scan fires)")
    ap.add_argument("--cluster", action="store_true", help="the swing-census cluster")
    ap.add_argument("--out", default=_SCRATCH, help="output directory for PNGs")
    a = ap.parse_args()
    if a.cluster:
        tickers = CLUSTER
    elif a.tickers:
        tickers = a.tickers
    else:
        tickers = (_latest_scan_fires() or CLUSTER)[:8]
    render(tickers, a.out)


if __name__ == "__main__":
    main()
