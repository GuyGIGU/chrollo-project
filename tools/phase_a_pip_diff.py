"""Phase-A overlay 3-way — current zigzag vs flat-PIP vs MACRO-PIP (the eyeball gate).

History: the flat PIP->segment_swings wire (commit c08e61f, ``PIP_PIVOTS_ENABLED``)
was judged with the 2-way ancestor of this tool (d43e7fd) and ruled a WASH — it
fixed some inverted climax->AR overlays and created others (GBTG/PLSE/CGNX) — so
it stayed default-off. The MACRO read (``PIP_MACRO_PHASE_A_ENABLED``,
``pip.macro_bridge_zigzag``) is the multi-resolution retry: stop at the smallest
top-K skeleton holding a confirmed climax->AR bridge, so late range retests and
noise dips are not in the skeleton to steal the climax/AR. This tool renders all
THREE reads so the operator can judge whether macro beats both.

It captures the EXACT overlay the pipeline archives: ``read_structure`` ->
``structure.climax_bar`` / ``.ar_bar`` (the same call + fields as
``evaluation.py``; those become ``_phase_a_start/end_date``), on the *faithful*
live frame — baseline filter + ``_trim_to_period`` to ``DAILY_STRUCTURE_PERIOD``
(2y) — exactly like ``_evaluate_ticker``. (``structure_case_audit._prep`` does
NOT trim; this tool deliberately does not reuse it.)

Alongside the shift table it reports a programmatic sanity proxy per mode:
**stolen climaxes** — overlays whose climax bar lands ON/AFTER the box start
(a Phase-A climax should precede the range that reacts to it; a climax inside
the box is a late R-touch theft).

Two modes:
  scan (default, no tickers)  : faithful off/flat/macro capture over the whole
                                cache; report which overlays CHANGE (off vs
                                macro), the flat reference count, the stolen-
                                climax counts; render the top movers.
  render (tickers given)      : render those specific tickers.

Read-only: reads the parquet cache, restores the flags after every capture,
writes PNGs to tools/fidelity/pip_phase_a/. No network, no backend, nothing
live imports it -> shadow stays byte-identical.

    python -m tools.phase_a_pip_diff                 # scan + render top movers
    python -m tools.phase_a_pip_diff --top 10
    python -m tools.phase_a_pip_diff GBTG PLSE CGNX  # render specific names
    python -m tools.phase_a_pip_diff --scan --no-render   # measure only
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
from core.pipeline.downloads import _trim_to_period
from core.pipeline.evaluation import apply_baseline_filters
from core.structure.indicators import calculate_atr
from core.structure.narrative import read_structure
from tools.pip_preview import _draw_ohlc

_OUT_DIR = os.path.join(_THIS, "fidelity", "pip_phase_a")
_MODES = ("off", "flat", "macro")
_COLORS = {"off": "#8b5cf6", "flat": "#94a3b8", "macro": "#2563eb"}
_LABELS = {"off": "OFF current zigzag", "flat": "FLAT PIP", "macro": "MACRO PIP"}
_CLIMAX_DY = {"off": 0.012, "flat": 0.028, "macro": 0.044}


def _prep_live(raw: pd.DataFrame):
    """The exact daily frame the screener reads: baseline filter, trim to
    DAILY_STRUCTURE_PERIOD, ATR cols. Mirrors evaluation._evaluate_ticker.
    Returns (df, atr) or (None, reason)."""
    base = apply_baseline_filters(raw.copy())
    if base is None:
        return None, "rejected at baseline filters"
    df, _ = base
    df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
    if len(df) < 6:
        return None, "too few bars after trim"
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    atr = float(df["ATR_10"].iloc[-6])
    if not (atr > 0):
        return None, "non-positive ATR snapshot"
    return df, atr


def _overlay(df, atr):
    """The (climax_bar, ar_bar, box_start_bar) the pipeline would archive for
    ``df`` right now, or None when no structure fires (same entry point +
    fields as evaluation)."""
    s = read_structure(df, atr)
    if s is None:
        return None
    return int(s.climax_bar), int(s.ar_bar), int(s.box.start_bar)


def capture_overlays(df, atr) -> dict:
    """Capture the Phase-A overlay under all three reads, ALWAYS restoring the
    flags (a leaked True would corrupt later in-process reads). Returns
    {mode: (climax, ar, box_start) | None}."""
    prev_flat = settings.PIP_PIVOTS_ENABLED
    prev_macro = settings.PIP_MACRO_PHASE_A_ENABLED
    out = {}
    try:
        settings.PIP_PIVOTS_ENABLED = False
        settings.PIP_MACRO_PHASE_A_ENABLED = False
        out["off"] = _overlay(df, atr)
        settings.PIP_PIVOTS_ENABLED = True
        out["flat"] = _overlay(df, atr)
        settings.PIP_PIVOTS_ENABLED = False
        settings.PIP_MACRO_PHASE_A_ENABLED = True
        out["macro"] = _overlay(df, atr)
    finally:
        settings.PIP_PIVOTS_ENABLED = prev_flat
        settings.PIP_MACRO_PHASE_A_ENABLED = prev_macro
    return out


def _shift(a, b):
    """(|Δclimax| + |Δar|) between two overlays, or None if either is missing."""
    if a is None or b is None:
        return None
    return abs(b[0] - a[0]) + abs(b[1] - a[1])


def _stolen(ov):
    """A climax ON/AFTER the box start is a theft (Phase A must precede B)."""
    return ov is not None and ov[0] >= ov[2]


def _load_cache():
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    return d, set(d.columns.get_level_values(0))


# ---------------------------------------------------------------- scan ----

def scan(d, level0):
    """Faithful universe measurement: per ticker, the 3-way overlay on the live
    2y frame. Returns rows [(ticker, {mode: ov}, shift_off_macro)] for FIRING
    setups (off not None), sorted by shift desc. Prints the summary + tables."""
    exclude = {getattr(settings, "MARKET_INDEX_SYMBOL", "SPY"), "SPY"}
    rows = []
    tickers = sorted(t for t in level0 if t not in exclude)
    for i, t in enumerate(tickers):
        if i and i % 200 == 0:
            print(f"  ...scanned {i}/{len(tickers)}", file=sys.stderr)
        try:
            df, atr = _prep_live(d[t].dropna())
        except Exception:                            # malformed column -> skip
            continue
        if df is None:
            continue
        ovs = capture_overlays(df, atr)
        if ovs["off"] is None:
            continue                                 # no live overlay to compare
        rows.append((t, ovs, _shift(ovs["off"], ovs["macro"])))

    n_fire = len(rows)
    macro_changed = [r for r in rows if r[2]]
    flat_changed = [r for r in rows if _shift(r[1]["off"], r[1]["flat"])]
    macro_changed.sort(key=lambda r: r[2], reverse=True)

    print(f"\n  faithful 2y-frame scan: {len(tickers)} tickers, {n_fire} fire "
          f"(have an overlay)")
    print(f"    off vs MACRO : {len(macro_changed)} overlays change")
    print(f"    off vs FLAT  : {len(flat_changed)} overlays change  (d43e7fd reference)")
    stolen = {m: sum(1 for _, ovs, _s in rows if _stolen(ovs[m])) for m in _MODES}
    print(f"    stolen climaxes (climax bar >= box start, of {n_fire}): "
          f"off {stolen['off']}  flat {stolen['flat']}  macro {stolen['macro']}")

    if macro_changed:
        print("\n  ticker   OFF(cx,AR)       MACRO(cx,AR)     dCx     dAR   theft off->macro")
        print("  " + "-" * 74)
        for t, ovs, sh in macro_changed:
            off, mac = ovs["off"], ovs["macro"]
            theft = f"{'Y' if _stolen(off) else '-'} -> {'Y' if _stolen(mac) else '-'}"
            print(f"  {t:<7}  {str(off[:2]):<15}  {str(mac[:2]):<15}  "
                  f"{mac[0]-off[0]:>+5}  {mac[1]-off[1]:>+5}   {theft}")
    return macro_changed


# -------------------------------------------------------------- render ----

def _draw_overlay(ax, ov, df, base_off, n_win, mode):
    """Draw a climax->AR segment: dashed guide at the climax bar, star at the
    climax High, dot at the AR Low, connected. Returns a one-line summary."""
    label = _LABELS[mode]
    if ov is None:
        return f"{label}: no structure"
    climax_b, ar_b, _bs = ov
    color = _COLORS[mode]
    cx, ax_x = climax_b - base_off, ar_b - base_off
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    if 0 <= cx < n_win:
        ax.axvline(cx, color=color, lw=1.0, ls="--", alpha=0.5, zorder=3)
    seg_x, seg_y = [], []
    if 0 <= cx < n_win:
        cy = highs[climax_b] * (1 + _CLIMAX_DY[mode])
        ax.scatter([cx], [cy], marker="*", s=240, color=color, zorder=6,
                   edgecolor="white", linewidth=0.7)
        seg_x.append(cx); seg_y.append(highs[climax_b])
    if 0 <= ax_x < n_win:
        ax.scatter([ax_x], [lows[ar_b]], marker="o", s=70, color=color, zorder=6,
                   edgecolor="white", linewidth=0.7)
        seg_x.append(ax_x); seg_y.append(lows[ar_b])
    if len(seg_x) == 2:
        ax.plot(seg_x, seg_y, color=color, lw=2.0, alpha=0.9, zorder=5)
    return f"{label}: {climax_b}->{ar_b}"


def render(tickers, window, d, level0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    os.makedirs(_OUT_DIR, exist_ok=True)
    table = []
    for t in tickers:
        t = t.upper()
        if t not in level0:
            print(f"  [skip {t}] not in cache")
            continue
        df, atr = _prep_live(d[t].dropna())
        if df is None:
            print(f"  [skip {t}] {atr}")              # atr carries the reason
            continue
        ovs = capture_overlays(df, atr)
        table.append((t, ovs))

        n_all = len(df)
        win = window if (window and 0 < window < n_all) else n_all
        base_off = n_all - win
        sl = df.iloc[base_off:]
        h = sl["High"].values.astype(float)
        low = sl["Low"].values.astype(float)
        c = sl["Close"].values.astype(float)
        o = sl["Open"].values.astype(float) if "Open" in sl.columns else c

        fig, ax = plt.subplots(1, 1, figsize=(15, 6))
        _draw_ohlc(ax, o, h, low, c)
        summaries = [_draw_overlay(ax, ovs[m], df, base_off, win, m) for m in _MODES]
        ax.set_xlim(-1, win)
        ax.grid(True, alpha=0.12)
        ax.set_title(f"{t}    " + "    |    ".join(summaries), fontsize=10,
                     fontweight="bold", loc="left")
        ax.legend(handles=[
            Line2D([0], [0], color=_COLORS[m], lw=2, marker="*", label=_LABELS[m])
            for m in _MODES
        ], loc="upper left", fontsize=9, framealpha=0.85)
        fig.suptitle(f"{t}  —  Phase-A overlay: current vs flat-PIP vs MACRO-PIP  "
                     f"(faithful 2y frame, last {win} bars)",
                     fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        out = os.path.join(_OUT_DIR, f"{t}.png")
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"  rendered {t} -> {out}")
    _print_table(table)


def _print_table(rows):
    if not rows:
        return
    print("\n  ticker   OFF(cx,AR)       FLAT(cx,AR)      MACRO(cx,AR)")
    print("  " + "-" * 60)
    for t, ovs in rows:
        cells = [str(ovs[m][:2]) if ovs[m] else "None" for m in _MODES]
        print(f"  {t:<7}  {cells[0]:<15}  {cells[1]:<15}  {cells[2]:<15}")


# ---------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser(
        description="Eyeball the Phase-A overlay (climax->AR) under the current "
                    "zigzag vs flat-PIP vs MACRO-PIP, on the faithful live 2y frame.")
    ap.add_argument("tickers", nargs="*",
                    help="render these tickers (default: scan + render top movers)")
    ap.add_argument("--window", type=int, default=260,
                    help="bars to show (default 260; 0 = all)")
    ap.add_argument("--scan", action="store_true",
                    help="run the faithful universe 3-way measurement")
    ap.add_argument("--no-render", action="store_true",
                    help="with --scan: measure only, don't render")
    ap.add_argument("--top", type=int, default=6,
                    help="how many top movers to render after a scan (default 6)")
    a = ap.parse_args()

    d, level0 = _load_cache()

    if a.tickers:
        render([t.upper() for t in a.tickers], a.window, d, level0)
        return

    # No tickers -> scan (the honest default), then render the top movers.
    changed = scan(d, level0)
    if a.no_render or not changed:
        return
    top = [r[0] for r in changed[:a.top]]
    print(f"\n  rendering top {len(top)} movers: {' '.join(top)}")
    render(top, a.window, d, level0)


if __name__ == "__main__":
    main()
