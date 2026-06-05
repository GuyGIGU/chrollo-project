"""
Phase-B A/B chart renderer — eyeball the box framing under both selection rules.

For each ticker it draws a stacked 2-panel chart:
    TOP    select="best"      (today's global-best-score box)
    BOTTOM select="earliest"  (Change B: earliest good-enough range start)

Each panel overlays the consolidation BOX (start->end x range, S..R y range),
the R/S lines, and a title with base_len / box_width / fire result, so you can
judge whether the longer "earliest" framing is the honest range or an over-reach.

Renders from the committed shadow fixture (hermetic; no network/backend).

    python -m tools.phaseb_render SKT SMFG CGEM NMM VIK YOU
    (no args -> a default movers set)
"""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS_DIR, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import settings
from core.pipeline.screener import apply_baseline_filters, _evaluate_ticker
from core.structure.consolidation import find_consolidation
from core.structure.indicators import calculate_atr
from tools.shadow_diff import _load_fixture

_OUT_DIR = os.path.join(_THIS_DIR, "fidelity", "ab")
_DEFAULT = ["SKT", "SMFG", "CGEM", "NMM", "VIK", "YOU"]


def _panel(ax, plot_df, x0, box, fires, label):
    """Draw OHLC bars + the consolidation box for one selection mode."""
    from matplotlib.patches import Rectangle

    o = plot_df["Open"].values
    h = plot_df["High"].values
    low = plot_df["Low"].values
    c = plot_df["Close"].values
    xs = list(range(len(plot_df)))
    last_x = len(xs) - 1

    base_len, R, S, bw, rt, st, pbs_df = box
    # Box x-range: from phase_b_start (df-positional) into the shown window.
    box_x0 = pbs_df - x0
    if box_x0 < 0:
        box_x0 = 0
    ax.add_patch(Rectangle(
        (box_x0 - 0.4, S), (last_x - box_x0) + 0.8, max(R - S, 1e-9),
        facecolor="#8b5cf6", alpha=0.12, edgecolor="#8b5cf6", lw=1.3, zorder=1,
    ))
    ax.axvline(box_x0, color="#8b5cf6", alpha=0.6, lw=1.2, zorder=1)
    ax.axhline(R, color="#5b8aff", ls="--", lw=0.9, alpha=0.8)
    ax.axhline(S, color="#5b8aff", ls="--", lw=0.9, alpha=0.8)

    tick = 0.34
    bar_lw = 1.1 if len(xs) > 90 else 1.4
    for i in xs:
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=bar_lw, zorder=3, solid_capstyle="round")
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=bar_lw, zorder=3, solid_capstyle="round")
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=bar_lw, zorder=3, solid_capstyle="round")

    fire_str = fires if fires else "no fire"
    ax.set_title(
        f"{label}:  base_len={base_len}  R={R:.2f} S={S:.2f}  box={bw:.3f}  "
        f"touches r/s={rt}/{st}  ->  {fire_str}",
        fontsize=11, fontweight="bold", loc="left",
    )
    ax.set_xlim(-1, last_x + 1)
    ax.margins(y=0.06)
    ax.grid(True, alpha=0.12)


def _box_for(df, select):
    t = find_consolidation(df, min_days=settings.MIN_BASE_DAYS, select=select)
    base_len = t[0]
    if base_len == 0:
        return None
    R, S, bw, rt, st = t[1], t[2], t[3], t[4], t[5]
    pbs_df = len(df) - base_len
    return (base_len, R, S, bw, rt, st, pbs_df)


def render(tickers):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(_OUT_DIR, exist_ok=True)
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    for ticker in tickers:
        raw = frames.get(ticker)
        if raw is None:
            print(f"  [skip {ticker}] not in fixture")
            continue
        base = apply_baseline_filters(raw.copy())
        if base is None:
            print(f"  [skip {ticker}] baseline filter")
            continue
        df, _yr = base
        df = df.copy()
        df["ATR_10"] = calculate_atr(df, 10)
        df["ATR_50"] = calculate_atr(df, 50)
        n = len(df)

        boxes = {}
        fires = {}
        for sel in ("best", "earliest"):
            boxes[sel] = _box_for(df, sel)
            res = _evaluate_ticker(ticker, raw, spy_6m, breadth, select=sel)
            fires[sel] = (f"FIRES {res['Tier']} {res['Score']:.1f}" if res else "")

        starts = [b[6] for b in boxes.values() if b]
        if not starts:
            print(f"  [skip {ticker}] no box either mode")
            continue
        earliest_start = min(starts)
        show = min(n, (n - earliest_start) + 45)
        x0 = n - show
        plot_df = df.tail(show).copy().reset_index(drop=True)

        fig, axes = plt.subplots(2, 1, figsize=(15, 11), sharex=True)
        for ax, sel in zip(axes, ("best", "earliest")):
            if boxes[sel] is None:
                ax.set_title(f"{sel}: no valid box", fontsize=11, loc="left")
                continue
            _panel(ax, plot_df, x0, boxes[sel], fires[sel],
                   label=f"{sel.upper():8}")
        fig.suptitle(f"{ticker}  —  Phase-B box: best (top) vs earliest (bottom)",
                     fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.98))
        out = os.path.join(_OUT_DIR, f"{ticker}.png")
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"  rendered {ticker} -> {out}")

    print(f"\nCharts in: {_OUT_DIR}")


def main():
    tickers = [a.upper() for a in sys.argv[1:]] or _DEFAULT
    render(tickers)


if __name__ == "__main__":
    main()
