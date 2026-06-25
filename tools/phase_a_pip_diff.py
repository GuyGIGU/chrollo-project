"""Phase-A overlay before/after — PIP vs the current zigzag (the eyeball gate).

The PIP->segment_swings wire (commit c08e61f, default-off behind
``PIP_PIVOTS_ENABLED``) is shadow-byte-identical and changes no firing/score/tier
field, but it DOES move the drawn Phase-A overlay (climax -> AR) on some setups,
because ``segment_swings`` feeds ``resolve_phase_a``. This tool lets the operator
judge whether PIP lands the climax -> AR where their eye does before flipping the
flag live.

It captures the EXACT overlay the pipeline archives: ``read_structure`` ->
``structure.climax_bar`` / ``.ar_bar`` (the same call + fields as
``evaluation.py``; those become ``_phase_a_start/end_date``). Crucially it reads on
the *faithful* live frame — baseline filter + ``_trim_to_period`` to
``DAILY_STRUCTURE_PERIOD`` (2y) — exactly like ``_evaluate_ticker`` and
``htf_audit._daily_box``. (``structure_case_audit._prep`` does NOT trim, so it
reads a 5y frame and can resolve a different, older root; this tool deliberately
does not reuse it.)

Two modes:
  scan (default, no tickers)  : run the faithful off/on capture over the whole
                                cache, report which setups' overlays actually
                                CHANGE on the live 2y frame, then render the top
                                movers. This is the honest universe measurement.
  render (tickers given)      : render those specific tickers.

Read-only: reads the parquet cache, restores the flag after every capture, writes
PNGs to tools/fidelity/pip_phase_a/. No network, no backend, nothing live imports
it -> shadow stays byte-identical.

    python -m tools.phase_a_pip_diff                 # scan + render top movers
    python -m tools.phase_a_pip_diff --top 10
    python -m tools.phase_a_pip_diff APYX ETG COLM   # render specific names
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
_OFF_COLOR = "#8b5cf6"   # current zigzag (matches pip_preview's CURRENT panel)
_ON_COLOR = "#2563eb"    # PIP


def _prep_live(raw: pd.DataFrame):
    """The exact daily frame the screener reads: baseline filter, trim to
    DAILY_STRUCTURE_PERIOD, ATR cols. Mirrors evaluation._evaluate_ticker /
    htf_audit._daily_box (which trim); NOT structure_case_audit._prep (which
    does not). Returns (df, atr) or (None, reason)."""
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


def _overlay_bars(df, atr):
    """The (climax_bar, ar_bar) the pipeline would archive for ``df`` right now,
    or None when no structure fires (same entry point + fields as evaluation)."""
    s = read_structure(df, atr)
    if s is None:
        return None
    return int(s.climax_bar), int(s.ar_bar)


def capture_overlays(df, atr):
    """Capture the Phase-A overlay flag-OFF then flag-ON, ALWAYS restoring the
    flag (a leaked PIP_PIVOTS_ENABLED=True would corrupt later in-process reads).
    Returns (off, on), each (climax, ar) or None."""
    prev = settings.PIP_PIVOTS_ENABLED
    try:
        settings.PIP_PIVOTS_ENABLED = False
        off = _overlay_bars(df, atr)
        settings.PIP_PIVOTS_ENABLED = True
        on = _overlay_bars(df, atr)
    finally:
        settings.PIP_PIVOTS_ENABLED = prev
    return off, on


def _shift(off, on):
    """(|Δclimax| + |Δar|) total, or None if either side has no overlay."""
    if off is None or on is None:
        return None
    return abs(on[0] - off[0]) + abs(on[1] - off[1])


def _load_cache():
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    return d, set(d.columns.get_level_values(0))


# ---------------------------------------------------------------- scan ----

def scan(d, level0):
    """Faithful universe measurement: per ticker, off vs on overlay on the live
    2y frame. Returns rows [(ticker, off, on, shift)] for FIRING setups (off not
    None), sorted by shift desc. Prints a summary + the changed table."""
    exclude = {getattr(settings, "MARKET_INDEX_SYMBOL", "SPY"), "SPY"}
    rows = []
    n_fire = 0
    tickers = sorted(t for t in level0 if t not in exclude)
    for i, t in enumerate(tickers):
        if i and i % 200 == 0:
            print(f"  ...scanned {i}/{len(tickers)}", file=sys.stderr)
        try:
            df, atr = _prep_live(d[t].dropna())
        except Exception as e:                       # malformed column -> skip
            continue
        if df is None:
            continue
        off, on = capture_overlays(df, atr)
        if off is None:
            continue                                  # no live overlay to compare
        n_fire += 1
        rows.append((t, off, on, _shift(off, on)))

    changed = [r for r in rows if r[3]]               # shift > 0
    changed.sort(key=lambda r: r[3], reverse=True)
    print(f"\n  faithful 2y-frame scan: {len(tickers)} tickers, "
          f"{n_fire} fire (have an overlay), {len(changed)} overlays CHANGE under PIP")
    if changed:
        print("\n  ticker   OFF(climax,AR)   ON(climax,AR)    dClimax  dAR")
        print("  " + "-" * 56)
        for t, off, on, sh in changed:
            print(f"  {t:<7}  {str(off):<15}  {str(on):<15}  "
                  f"{on[0]-off[0]:>+6}  {on[1]-off[1]:>+5}")
    return changed


# -------------------------------------------------------------- render ----

def _draw_overlay(ax, bars, df, base_off, n_win, color, label, *, climax_dy):
    """Draw a climax->AR segment: dashed guide at the climax bar, star at the
    climax High, dot at the AR Low, connected. Returns a one-line summary."""
    if bars is None:
        return f"{label}: no structure"
    climax_b, ar_b = bars
    cx, ax_x = climax_b - base_off, ar_b - base_off
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    if 0 <= cx < n_win:
        ax.axvline(cx, color=color, lw=1.0, ls="--", alpha=0.5, zorder=3)
    seg_x, seg_y = [], []
    if 0 <= cx < n_win:
        cy = highs[climax_b] * (1 + climax_dy)
        ax.scatter([cx], [cy], marker="*", s=240, color=color, zorder=6,
                   edgecolor="white", linewidth=0.7)
        seg_x.append(cx); seg_y.append(highs[climax_b])
    if 0 <= ax_x < n_win:
        ax.scatter([ax_x], [lows[ar_b]], marker="o", s=70, color=color, zorder=6,
                   edgecolor="white", linewidth=0.7)
        seg_x.append(ax_x); seg_y.append(lows[ar_b])
    if len(seg_x) == 2:
        ax.plot(seg_x, seg_y, color=color, lw=2.0, alpha=0.9, zorder=5)
    return f"{label}: climax {climax_b} -> AR {ar_b}"


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
        off, on = capture_overlays(df, atr)
        table.append((t, off, on))

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
        s_off = _draw_overlay(ax, off, df, base_off, win, _OFF_COLOR,
                              "OFF zigzag", climax_dy=0.012)
        s_on = _draw_overlay(ax, on, df, base_off, win, _ON_COLOR,
                             "ON  PIP", climax_dy=0.028)
        ax.set_xlim(-1, win)
        ax.grid(True, alpha=0.12)
        ax.set_title(f"{t}    {s_off}    |    {s_on}", fontsize=11,
                     fontweight="bold", loc="left")
        ax.legend(handles=[
            Line2D([0], [0], color=_OFF_COLOR, lw=2, marker="*",
                   label="OFF — current zigzag"),
            Line2D([0], [0], color=_ON_COLOR, lw=2, marker="*",
                   label="ON — PIP substrate"),
        ], loc="upper left", fontsize=9, framealpha=0.85)
        fig.suptitle(f"{t}  —  Phase-A overlay: PIP vs current zigzag  "
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
    print("\n  ticker   OFF(climax,AR)   ON(climax,AR)    dClimax  dAR")
    print("  " + "-" * 56)
    for t, off, on in rows:
        dcl = f"{on[0]-off[0]:>+6}" if (off and on) else "     -"
        dar = f"{on[1]-off[1]:>+5}" if (off and on) else "    -"
        print(f"  {t:<7}  {str(off):<15}  {str(on):<15}  {dcl}  {dar}")


# ---------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser(
        description="Eyeball the Phase-A overlay (climax->AR) under PIP vs the "
                    "current zigzag, on the faithful live 2y frame.")
    ap.add_argument("tickers", nargs="*",
                    help="render these tickers (default: scan + render top movers)")
    ap.add_argument("--window", type=int, default=260,
                    help="bars to show (default 260; 0 = all)")
    ap.add_argument("--scan", action="store_true",
                    help="run the faithful universe off/on measurement")
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
