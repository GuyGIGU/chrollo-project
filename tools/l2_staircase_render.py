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
from engine_alpha.structure.metrics import read_box_events, read_box_staircase
from tools.lps_swing_census import CLUSTER, _first_complete, _latest_scan_fires
from tools.structure_case_audit import _prep

# Unified event-zone shading (read_box_events): one FIXED color per event CLASS so
# the operator learns one legend. SOS green (strength that held), markup amber (held
# far above R = post-breakout markup), upthrust red (failed breach), spring purple
# (breach-S-that-reclaims), test blue (touch-of-S-that-holds), LPS teal. range +
# rejection are ordinary range work — not shaded.
_ZONE_STYLE = {
    "SOS": "#1f9d8b", "markup": "#e0a030", "upthrust": "#e04848",
    "spring": "#8b5cf6", "test": "#5b8aff", "lps": "#0ea5a5",
    "in_progress": "#9aa0aa", "failed": "#c98a8a",
}
_ZONE_SKIP = {"rejection", "range"}

_SCRATCH = os.environ.get(
    "CLAUDE_SCRATCH",
    os.path.join(_THIS, "fidelity", "l2"),
)

# RAW GEOMETRIC rail events — NOT classified Wyckoff verdicts. breach_R is just
# "broke R"; SOS (holds, confirmed by an LPS) vs upthrust (fails back in) is a
# Brick-2 read of what comes after, not a property of the breach itself.
# Neutral grey for the RAW breach markers so "a swing poked the rail" (geometry)
# never shares a hue with a CLASSIFIED zone (e.g. green SOS / red upthrust) — the
# raw marker and the confirmed class are opposite epistemic statuses.
_EVENT_STYLE = {
    "breach_S": ("v", "#444444", "breach S (raw)"),
    "breach_R": ("^", "#444444", "breach R (raw)"),
    "touch_R": ("o", "#8aa0c8", "touch R"),
    "touch_S": ("o", "#8aa0c8", "touch S"),
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

    # Unified independent event view (read_box_events): each Wyckoff piece as an
    # AREA, one fixed color per CLASS. R-rail labels float up (near R), S-rail
    # labels float down (near S) so overlapping zones stay individually readable.
    events = read_box_events(df, box, atr)
    counts = {}
    for e in events:
        t = e["type"]
        counts[t] = counts.get(t, 0) + 1
        if t in _ZONE_SKIP:
            continue
        col = _ZONE_STYLE.get(t, "#9aa0aa")
        ax.axvspan(e["zone_start"] - 0.4, e["zone_end"] + 0.4,
                   color=col, alpha=0.11, zorder=1)
        midx = (e["zone_start"] + e["zone_end"]) / 2.0
        up = e.get("rail") == "R"
        tag = t
        if e.get("strength_box") is not None:
            tag += f" {e['strength_box']:.1f}"
        elif e.get("undercut_atr") is not None:
            tag += f" {e['undercut_atr']:.1f}atr"
        ax.annotate(tag, (midx, R if up else S),
                    textcoords="offset points", xytext=(0, 26 if up else -26),
                    ha="center", fontsize=7.5, fontweight="bold", color=col,
                    va="bottom" if up else "top",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=col, lw=0.8, alpha=0.85))
    setattr(ax, "_l2_event_counts", counts)

    # Sparse date ticks.
    n = len(base)
    step = max(1, n // 8)
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(df.index[start + t])[:10] for t in ticks],
                       rotation=35, ha="right", fontsize=7)

    c = out["counts"]
    ec = getattr(ax, "_l2_event_counts", {})
    named = [f"{k}:{ec[k]}" for k in
             ("spring", "test", "SOS", "lps", "upthrust", "markup") if ec.get(k)]
    prov = [f"{k}:{ec[k]}" for k in ("in_progress", "failed") if ec.get(k)]
    event_line = "  ".join(named) if named else "no named events"
    if prov:
        event_line += "   (provisional: " + " ".join(prov) + ")"
    ax.set_title(
        f"{ticker}   S={S:.2f} R={R:.2f}   "
        f"HH:{c['HH']} HL:{c['HL']} LH:{c['LH']} LL:{c['LL']}   "
        f"trend={out['trend_state']}   is_zigzag={out['is_zigzag']}\n"
        f"events:  {event_line}",
        fontsize=10.5, fontweight="bold", loc="left",
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
        # Two legends: raw swing markers (geometry) AND the classified event-zone
        # colors, so every shaded class the operator signs off on is self-documented.
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        marker_handles = [Line2D([0], [0], marker=m, color="w", markerfacecolor=col,
                                 markersize=9, label=lbl)
                          for (m, col, lbl) in _EVENT_STYLE.values()]
        zone_handles = [Patch(facecolor=col, alpha=0.45, label=cls)
                        for cls, col in _ZONE_STYLE.items()]
        leg1 = ax.legend(handles=marker_handles, loc="upper left",
                         fontsize=8, framealpha=0.9, title="raw swing markers")
        ax.add_artist(leg1)
        ax.legend(handles=zone_handles, loc="upper right", fontsize=7.5,
                  framealpha=0.9, title="event zones", ncol=2)
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
