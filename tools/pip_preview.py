"""PIP swing-skeleton preview — eyeball PIP vs the current zigzag substrate.

Renders, per ticker, OHLC bars overlaid with:
  panel 1     : the CURRENT zigzag (pivots._find_pivots at the engine's order
                + _build_zigzag) — the single-scale substrate everything reads
  panels 2..n : the PIP skeleton at coarse / mid / fine resolutions
so you can judge whether PIP's multi-resolution read (trend -> climax -> box ->
inner structure) matches your eye before any live consumer touches it.

Read-only: reads the live parquet cache + the calibrated baseline prep and
renders to tools/fidelity/pip/<TICKER>.png. No network, no backend, no
behaviour change (nothing in the live path imports core.structure.pip).

    python -m tools.pip_preview MYRG AXGN EIX
    python -m tools.pip_preview MYRG --window 300 --levels 5,12,30
"""
from __future__ import annotations

import argparse
import os

try:  # works under both `python -m tools.pip_preview` and `python tools/pip_preview.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

configure_path()

_THIS = os.path.dirname(os.path.abspath(__file__))

import pandas as pd

from config import settings
from core.structure.box_primitives import _pivot_order
from core.structure.pip import pip_pivots
from core.structure.pivots import _build_zigzag, _find_pivots
from tools.structure_case_audit import _prep

_OUT_DIR = os.path.join(_THIS, "fidelity", "pip")
_DEFAULT = ["MYRG", "AXGN", "EIX"]


def _current_zigzag(highs, lows):
    """The skeleton the engine reads today: fixed-order pivots -> alternating zigzag."""
    peaks, valleys = _find_pivots(highs, lows, _pivot_order(len(highs)))
    if not peaks or not valleys:
        return []
    return _build_zigzag(peaks, valleys, highs, lows)


def _draw_ohlc(ax, o, h, low, c):
    tick = 0.34
    lw = 1.0 if len(c) > 120 else 1.3
    for i in range(len(c)):
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=lw, zorder=2, solid_capstyle="round")
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=lw, zorder=2)
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=lw, zorder=2)


def _overlay(ax, zz, color, label):
    if not zz:
        ax.set_title(f"{label}: (no skeleton)", fontsize=10, loc="left")
        ax.grid(True, alpha=0.12)
        return
    ax.plot([b for b, _, _ in zz], [p for _, _, p in zz],
            color=color, lw=1.6, zorder=4, alpha=0.9)
    pk = [(b, p) for b, k, p in zz if k == "peak"]
    vl = [(b, p) for b, k, p in zz if k == "valley"]
    if pk:
        ax.scatter([b for b, _ in pk], [p for _, p in pk], marker="v", s=42,
                   color=color, zorder=5, edgecolor="white", linewidth=0.5)
    if vl:
        ax.scatter([b for b, _ in vl], [p for _, p in vl], marker="^", s=42,
                   color=color, zorder=5, edgecolor="white", linewidth=0.5)
    ax.set_title(f"{label}  ({len(zz)} pivots)", fontsize=10, fontweight="bold", loc="left")
    ax.grid(True, alpha=0.12)


def render(tickers, window, levels):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(_OUT_DIR, exist_ok=True)
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))

    for t in tickers:
        t = t.upper()
        if t not in level0:
            print(f"  [skip {t}] not in cache")
            continue
        df, atr = _prep(d[t].dropna())
        if df is None:
            print(f"  [skip {t}] {atr}")     # atr carries the rejection reason
            continue
        if window and 0 < window < len(df):
            df = df.tail(window).reset_index(drop=True)
        h = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)
        c = df["Close"].values.astype(float)
        o = df["Open"].values.astype(float) if "Open" in df.columns else c

        panels = [(f"CURRENT zigzag (order {_pivot_order(len(df))})",
                   _current_zigzag(h, low), "#8b5cf6")]
        pip_colors = ["#2563eb", "#d4960a", "#0d9488", "#be185d"]
        for k, col in zip(levels, pip_colors):
            panels.append((f"PIP top-{k}", pip_pivots(h, low, n_points=k), col))

        fig, axes = plt.subplots(len(panels), 1, figsize=(15, 3.1 * len(panels)),
                                 sharex=True)
        if len(panels) == 1:
            axes = [axes]
        for ax, (label, zz, col) in zip(axes, panels):
            _draw_ohlc(ax, o, h, low, c)
            _overlay(ax, zz, col, label)
            ax.set_xlim(-1, len(c))
        fig.suptitle(f"{t}  —  PIP skeleton vs current zigzag  (last {len(df)} bars)",
                     fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.98))
        out = os.path.join(_OUT_DIR, f"{t}.png")
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"  rendered {t} -> {out}")


def main():
    ap = argparse.ArgumentParser(description="Eyeball the PIP skeleton vs the current zigzag.")
    ap.add_argument("tickers", nargs="*", help="tickers (default: MYRG AXGN EIX)")
    ap.add_argument("--window", type=int, default=250,
                    help="bars to show / compute on (default 250; 0 = all)")
    ap.add_argument("--levels", type=str, default="5,15,40",
                    help="PIP point counts, comma-separated (default 5,15,40)")
    a = ap.parse_args()
    tickers = [t.upper() for t in a.tickers] or _DEFAULT
    levels = [int(x) for x in a.levels.split(",") if x.strip()]
    render(tickers, a.window, levels)


if __name__ == "__main__":
    main()
