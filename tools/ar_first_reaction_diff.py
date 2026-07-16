"""First-reaction AR overlay diff — raw Phase-A anchor vs first-impulse tighten.

The raw ``resolve_phase_a`` fallbacks can pin the drawn automatic reaction at the
base edge, so the climax->AR stripe smears across half the chart. The flag-gated
``_first_impulse_ar_end`` (``AR_FIRST_REACTION_ENABLED``, see docs/strategy_v2.md
"Phase A — First-reaction AR anchor") tightens the AR to the first continuous
counter-move off the climax. This tool renders both reads on the *faithful* live
frame so the operator can eyeball the tighten before flipping the flag.

It captures the EXACT overlay the pipeline archives: ``read_structure`` ->
``structure.climax_bar`` / ``.ar_bar`` (the same call + fields as
``evaluation.py``), on the same frame ``_evaluate_ticker`` uses — baseline filter
+ ``_trim_to_period`` to ``DAILY_STRUCTURE_PERIOD`` (2y). The tighten is
overlay-only and tighten-only, so the climax never moves and the AR only ever
pulls earlier; the shift table's dAR column is <= 0 by construction.

Two modes:
  scan (default, no tickers)  : off/on capture over the whole cache; report which
                                overlays tighten and by how much; render the top
                                movers (largest AR pull-in).
  render (tickers given)      : render those specific tickers.

Read-only: reads the parquet cache, restores the flag after every capture, writes
PNGs to tools/fidelity/ar_first_reaction/. No network, no backend, nothing live
imports it -> shadow stays byte-identical.

    python -m tools.ar_first_reaction_diff                 # scan + render top movers
    python -m tools.ar_first_reaction_diff --top 10
    python -m tools.ar_first_reaction_diff AES JOF TAC     # render specific names
    python -m tools.ar_first_reaction_diff --scan --no-render   # measure only
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
from engine_alpha.structure.indicators import calculate_atr
from engine_alpha.structure.narrative import read_structure

_OUT_DIR = os.path.join(_THIS, "fidelity", "ar_first_reaction")
_MODES = ("off", "on")
_COLORS = {"off": "#8b5cf6", "on": "#16a34a"}
_LABELS = {"off": "OFF raw anchor", "on": "ON first-reaction"}
_CLIMAX_DY = {"off": 0.012, "on": 0.044}


def _prep_live(raw: pd.DataFrame):
    """The exact daily frame the screener reads: baseline filter, trim to
    DAILY_STRUCTURE_PERIOD, ATR cols. Mirrors evaluation._evaluate_ticker.
    Returns (df, atr) or (None, reason)."""
    base = apply_baseline_filters(raw.copy())
    if base is None:
        return None, "rejected at baseline filters"
    df, _ = base
    df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
    if len(df) < settings.STRUCTURE_ATR_SAMPLE_OFFSET:
        return None, "too few bars after trim"
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    atr = float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])
    if not (atr > 0):
        return None, "non-positive ATR snapshot"
    return df, atr


def _overlay(df, atr):
    """The (climax_bar, ar_bar, box_start_bar) the pipeline would archive for
    ``df`` right now, or None when no structure fires."""
    s = read_structure(df, atr)
    if s is None:
        return None
    return int(s.climax_bar), int(s.ar_bar), int(s.box.start_bar)


def capture_overlays(df, atr) -> dict:
    """Capture the Phase-A overlay with the first-reaction tighten OFF and ON,
    ALWAYS restoring the flag. Returns {mode: (climax, ar, box_start) | None}."""
    prev = settings.AR_FIRST_REACTION_ENABLED
    out = {}
    try:
        settings.AR_FIRST_REACTION_ENABLED = False
        out["off"] = _overlay(df, atr)
        settings.AR_FIRST_REACTION_ENABLED = True
        out["on"] = _overlay(df, atr)
    finally:
        settings.AR_FIRST_REACTION_ENABLED = prev
    return out


def _tighten(ovs):
    """Bars the AR pulls earlier (off.ar - on.ar), or None if either is missing.
    Tighten-only, so this is >= 0; a positive value means the stripe shrank."""
    off, on = ovs["off"], ovs["on"]
    if off is None or on is None:
        return None
    return off[1] - on[1]


def _load_cache():
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    return d, set(d.columns.get_level_values(0))


# ---------------------------------------------------------------- scan ----

def _capture_one(args):
    """Pool worker: one ticker's off/on capture (top-level for pickling)."""
    t, df, atr = args
    return t, capture_overlays(df, atr)


def scan(d, level0, jobs: int = 1):
    """Faithful universe measurement: per ticker, the off/on overlay on the live
    2y frame. Returns rows [(ticker, {mode: ov})] whose AR tightens, sorted by
    tighten desc. Prints the summary + table."""
    exclude = {getattr(settings, "MARKET_INDEX_SYMBOL", "SPY"), "SPY"}
    tickers = sorted(t for t in level0 if t not in exclude)

    prepped = []
    for i, t in enumerate(tickers):
        if i and i % 500 == 0:
            print(f"  ...prepped {i}/{len(tickers)}", file=sys.stderr, flush=True)
        try:
            df, atr = _prep_live(d[t].dropna())
        except Exception:                            # malformed column -> skip
            continue
        if df is None:
            continue
        prepped.append((t, df, atr))
    print(f"  {len(prepped)}/{len(tickers)} tickers survive baseline; "
          f"capturing off/on overlays with jobs={jobs}", file=sys.stderr, flush=True)

    fires, movers = 0, []

    def _collect(t, ovs):
        nonlocal fires
        if ovs["off"] is None:
            return                                   # no live overlay to compare
        fires += 1
        tt = _tighten(ovs)
        if tt:
            movers.append((t, ovs, tt))

    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for i, (t, ovs) in enumerate(
                    pool.imap_unordered(_capture_one, prepped, chunksize=8)):
                if i and i % 200 == 0:
                    print(f"  ...captured {i}/{len(prepped)}",
                          file=sys.stderr, flush=True)
                _collect(t, ovs)
    else:
        for i, (t, df, atr) in enumerate(prepped):
            if i and i % 200 == 0:
                print(f"  ...captured {i}/{len(prepped)}",
                      file=sys.stderr, flush=True)
            _collect(t, capture_overlays(df, atr))

    movers.sort(key=lambda r: r[2], reverse=True)

    print(f"\n  faithful 2y-frame scan: {len(tickers)} tickers, {fires} fire "
          f"(have an overlay)")
    print(f"    first-reaction tighten re-anchors {len(movers)} of {fires} "
          f"overlays (AR pulled earlier)")
    if movers:
        pulls = [m[2] for m in movers]
        print(f"    tighten (bars): max={max(pulls)}  "
              f"median={sorted(pulls)[len(pulls) // 2]}  total={sum(pulls)}")
        print("\n  ticker   OFF(cx,AR)       ON(cx,AR)        dAR   old_span  new_span")
        print("  " + "-" * 66)
        for t, ovs, tt in movers:
            off, on = ovs["off"], ovs["on"]
            print(f"  {t:<7}  {str(off[:2]):<15}  {str(on[:2]):<15}  "
                  f"{on[1]-off[1]:>+4}  {off[1]-off[0]:>7}  {on[1]-on[0]:>7}")
    return movers


# -------------------------------------------------------------- render ----

def _draw_overlay(ax, ov, df, base_off, n_win, mode):
    """Draw a climax->AR segment: dashed guide at the climax bar, star at the
    climax, dot at the AR, connected. Orientation-aware — a buying climax tops at
    a High into a lower reaction, a selling climax troughs at a Low into a higher
    one — so both roots paint on the correct side of the candle. Returns a
    one-line summary."""
    label = _LABELS[mode]
    if ov is None:
        return f"{label}: no structure"
    climax_b, ar_b, _bs = ov
    color = _COLORS[mode]
    cx, ax_x = climax_b - base_off, ar_b - base_off
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    bc = float(highs[climax_b]) >= float(highs[ar_b])
    climax_y = float(highs[climax_b]) if bc else float(lows[climax_b])
    ar_y = float(lows[ar_b]) if bc else float(highs[ar_b])
    if 0 <= cx < n_win:
        ax.axvline(cx, color=color, lw=1.0, ls="--", alpha=0.5, zorder=3)
    seg_x, seg_y = [], []
    if 0 <= cx < n_win:
        cy = climax_y * (1 + (_CLIMAX_DY[mode] if bc else -_CLIMAX_DY[mode]))
        ax.scatter([cx], [cy], marker="*", s=240, color=color, zorder=6,
                   edgecolor="white", linewidth=0.7)
        seg_x.append(cx); seg_y.append(climax_y)
    if 0 <= ax_x < n_win:
        ax.scatter([ax_x], [ar_y], marker="o", s=70, color=color, zorder=6,
                   edgecolor="white", linewidth=0.7)
        seg_x.append(ax_x); seg_y.append(ar_y)
    if len(seg_x) == 2:
        ax.plot(seg_x, seg_y, color=color, lw=2.0, alpha=0.9, zorder=5)
    return f"{label}: {climax_b}->{ar_b}"


def render(tickers, window, d, level0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from tools.pip_preview import _draw_ohlc

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
        if all(ovs[m] is None for m in _MODES):
            print(f"  [skip {t}] no structure under either read — nothing to eyeball")
            continue
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
        fig.suptitle(f"{t}  —  Phase-A automatic reaction: raw vs first-reaction "
                     f"tighten  (faithful 2y frame, last {win} bars)",
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
    print("\n  ticker   OFF(cx,AR)       ON(cx,AR)")
    print("  " + "-" * 44)
    for t, ovs in rows:
        cells = [str(ovs[m][:2]) if ovs[m] else "None" for m in _MODES]
        print(f"  {t:<7}  {cells[0]:<15}  {cells[1]:<15}")


# ---------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser(
        description="Eyeball the Phase-A automatic-reaction overlay (climax->AR) "
                    "with the first-reaction tighten off vs on, on the faithful "
                    "live 2y frame.")
    ap.add_argument("tickers", nargs="*",
                    help="render these tickers (default: scan + render top movers)")
    ap.add_argument("--window", type=int, default=260,
                    help="bars to show (default 260; 0 = all)")
    ap.add_argument("--scan", action="store_true",
                    help="run the faithful universe off-vs-on measurement")
    ap.add_argument("--no-render", action="store_true",
                    help="with --scan: measure only, don't render")
    ap.add_argument("--top", type=int, default=6,
                    help="how many top movers to render after a scan (default 6)")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2),
                    help="process-pool size for the scan captures "
                         "(default: cores - 2; 1 = sequential)")
    a = ap.parse_args()

    d, level0 = _load_cache()

    if a.tickers:
        render([t.upper() for t in a.tickers], a.window, d, level0)
        return

    # No tickers -> scan (the honest default), then render the top movers.
    movers = scan(d, level0, jobs=a.jobs)
    if a.no_render or not movers:
        return
    top = [r[0] for r in movers[:a.top]]
    print(f"\n  rendering top {len(top)} movers: {' '.join(top)}")
    render(top, a.window, d, level0)


if __name__ == "__main__":
    main()
