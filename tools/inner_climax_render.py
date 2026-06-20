"""
Inner-climax eyeball renderer — compare the inner-box anchor: today's mechanical
midpoint vs the detected inner climax (_detect_inner_phase_b_start).

For each ticker it draws a stacked 2-panel chart on the SAME price window:
    TOP     parent (outer) box  +  MIDPOINT inner   (today's _INNER_SEARCH_FRACTION)
    BOTTOM  parent (outer) box  +  CLIMAX  inner    (detected inner climax → AR)

The parent box is drawn the same in both panels (it never moves). Only the inner
box's start changes. The bottom panel marks the detected inner-climax AR (the
inner Phase B start) with a vertical line so you can judge whether the climax
anchor frames a more honest inner consolidation than the halfway point.

DIAGNOSTIC ONLY — reads the committed shadow fixture, runs no engine path that
fires, changes nothing. Stage-1 "eyeball before the flip".

    python -m tools.inner_climax_render FMNB CYTK IBCP FOR WFG APYX
    (no args -> a default divergence set from the fixture inspection)
"""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS_DIR, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import settings
from core.pipeline.screener import apply_baseline_filters
from core.structure.box_primitives import (
    INNER_MIN_DAYS,
    _detect_inner_phase_b_start,
    inner_zigzag,
)
from core.structure.consolidation import find_outer_box
from core.structure.indicators import calculate_atr
from tools.shadow_diff import _load_fixture

_OUT_DIR = os.path.join(_THIS_DIR, "fidelity", "inner")
_DEFAULT = ["FMNB", "CYTK", "IBCP", "FOR", "WFG", "APYX"]


def _draw_bars(ax, plot_df):
    o = plot_df["Open"].values
    h = plot_df["High"].values
    low = plot_df["Low"].values
    c = plot_df["Close"].values
    xs = range(len(plot_df))
    tick = 0.34
    bar_lw = 1.1 if len(plot_df) > 90 else 1.4
    for i in xs:
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=bar_lw, zorder=3, solid_capstyle="round")
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=bar_lw, zorder=3, solid_capstyle="round")
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=bar_lw, zorder=3, solid_capstyle="round")


def _box(ax, x0, last_x, box, color, alpha, label):
    """box = (start_df, R, S, bw); draw rectangle + R/S lines + start marker."""
    from matplotlib.patches import Rectangle

    start_df, R, S, bw = box
    bx0 = max(0, start_df - x0)
    ax.add_patch(Rectangle(
        (bx0 - 0.4, S), (last_x - bx0) + 0.8, max(R - S, 1e-9),
        facecolor=color, alpha=alpha, edgecolor=color, lw=1.4, zorder=1,
    ))
    ax.axvline(bx0, color=color, lw=1.4, alpha=0.85, zorder=2)
    ax.axhline(R, color=color, ls="--", lw=0.9, alpha=0.7)
    ax.axhline(S, color=color, ls="--", lw=0.9, alpha=0.7)


def _inner_box(eval_df, n, start):
    if start is None or start >= len(eval_df) or (n - start) < INNER_MIN_DAYS:
        return None
    r = inner_zigzag(eval_df, start, n - start)
    if r[0] == 0:
        return None
    return (n - r[0], r[1], r[2], r[3])     # (start_df, R, S, bw)


def render(tickers):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(_OUT_DIR, exist_ok=True)
    frames, _scalars = _load_fixture()

    for ticker in tickers:
        raw = frames.get(ticker)
        if raw is None:
            print(f"  [skip {ticker}] not in fixture")
            continue
        base = apply_baseline_filters(raw.copy())
        if base is None:
            print(f"  [skip {ticker}] baseline filter")
            continue
        df = base[0].copy()
        df["ATR_10"] = calculate_atr(df, 10)
        df["ATR_50"] = calculate_atr(df, 50)
        n = len(df)

        outer = find_outer_box(df)
        if outer[0] == 0:
            print(f"  [skip {ticker}] no outer box")
            continue
        obl, R_o, S_o, bw_o, opbs = outer[0], outer[1], outer[2], outer[3], outer[10]
        parent = (opbs, R_o, S_o, bw_o)

        eval_df = df.iloc[:-5] if n > 5 else df
        mid_start = opbs + int(obl * settings.INNER_SEARCH_FRACTION)
        det_off = _detect_inner_phase_b_start(eval_df.iloc[opbs:])
        det_start = (opbs + det_off) if det_off is not None else None

        inner_mid = _inner_box(eval_df, n, mid_start)
        inner_det = _inner_box(eval_df, n, det_start)

        show = min(n, (n - opbs) + 30)
        x0 = n - show
        last_x = show - 1
        plot_df = df.tail(show).copy().reset_index(drop=True)

        def gate(b):
            return "wins" if (b and b[3] < bw_o * settings.INNER_TIGHTNESS_RATIO) else "no"

        fig, axes = plt.subplots(2, 1, figsize=(15, 11), sharex=True)
        panels = [
            (axes[0], inner_mid, mid_start, "#e0903a", "MIDPOINT inner (today)"),
            (axes[1], inner_det, det_start, "#1fae5a", "CLIMAX inner (detected)"),
        ]
        for ax, inner, istart, icol, ilabel in panels:
            _draw_bars(ax, plot_df)
            _box(ax, x0, last_x, parent, "#8b5cf6", 0.10, "parent")
            sub = f"parent box={bw_o:.3f}"
            if inner is not None:
                _box(ax, x0, last_x, inner, icol, 0.18, ilabel)
                sub = (f"parent={bw_o:.3f}   inner={inner[3]:.3f}  "
                       f"({gate(inner)} 0.75 gate)   start@{istart}")
            else:
                sub = f"parent={bw_o:.3f}   inner: none"
            ax.set_title(f"{ilabel}:  {sub}", fontsize=11, fontweight="bold", loc="left")
            ax.set_xlim(-1, last_x + 1)
            ax.margins(y=0.06)
            ax.grid(True, alpha=0.12)

        off = (det_start - mid_start) if det_start is not None else None
        off_s = f"climax−midpoint = {off:+d} bars" if off is not None else "no climax detected"
        fig.suptitle(f"{ticker}  —  inner anchor: midpoint (top) vs climax (bottom)   [{off_s}]",
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
