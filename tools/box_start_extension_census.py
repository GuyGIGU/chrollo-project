"""Box-START back-extension census — parked calibration gap #3 (AGCO, 2026-07-02).

The AGCO dissection proved the elected rails (R 123.32 / S 111.30) are FULLY
VALID by every engine gate from 03-25, yet the box starts 04-02 because
candidate starts are pinned to the anchor pair (``cand_start = min(r_anchor,
s_anchor)``) — the earliest-valid election cannot reach an earlier start its
own gates would bless. This tool measures how often that happens across the
universe, measure-only:

For every FIRING setup, take the elected box exactly as the live reader returns
it and walk the start LEFTWARD over bars that conform to the box's own buffered
band ``[S - 0.5*ATR, R + 0.5*ATR]`` (the same band the respect gate uses). The
conforming run length is the "hidden cause" the generator could not propose.
Bars that TOUCH a rail inside that run (``TOUCH_TOLERANCE_ATR``) are counted
separately — an extension with rail touches is worked range, not just drift.

Read-only: reads the parquet cache, changes no flags, writes PNGs to
tools/fidelity/box_start_extension/. Nothing live imports it.

    python -m tools.box_start_extension_census                 # scan + render top
    python -m tools.box_start_extension_census --top 12
    python -m tools.box_start_extension_census AGCO NVDA       # render specific
    python -m tools.box_start_extension_census --no-render     # measure only
"""
from __future__ import annotations

import argparse
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np

from config import settings
from engine_alpha.structure.narrative import read_structure
from tools.phase_a_pip_diff import _load_cache, _prep_live

_OUT_DIR = os.path.join(_THIS, "fidelity", "box_start_extension")


def _census_one(args):
    """Pool worker: one ticker's elected box + band-conforming left extension."""
    t, df, atr = args
    s = read_structure(df, atr)
    if s is None:
        return t, None
    box = s.box
    R, S = float(box.R), float(box.S)
    start = int(box.start_bar)
    buf = settings.BOUNDARY_ATR_BUFFER * atr
    tb = settings.TOUCH_TOLERANCE_ATR * atr

    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)

    j = start - 1
    while j >= 0 and highs[j] <= R + buf and lows[j] >= S - buf:
        j -= 1
    ext_start = j + 1                      # first conforming bar of the run
    ext_days = start - ext_start
    ext_hi = highs[ext_start:start]
    ext_lo = lows[ext_start:start]
    return t, {
        "start_bar": start,
        "start_date": str(df.index[start].date()),
        "ext_days": int(ext_days),
        "ext_start_date": str(df.index[ext_start].date()) if ext_days else None,
        "ext_r_touches": int((np.abs(ext_hi - R) <= tb).sum()),
        "ext_s_touches": int((np.abs(ext_lo - S) <= tb).sum()),
        "base_len": int(box.base_len),
        "R": R, "S": S,
        "box_width": float(box.box_width),
    }


def scan(d, level0, jobs: int = 1):
    """Universe census on the faithful live 2y frame. Returns firing rows
    [(ticker, info)] sorted by ext_days desc; prints distribution + table."""
    exclude = {getattr(settings, "MARKET_INDEX_SYMBOL", "SPY"), "SPY"}
    tickers = sorted(t for t in level0 if t not in exclude)

    prepped = []
    for i, t in enumerate(tickers):
        if i and i % 500 == 0:
            print(f"  ...prepped {i}/{len(tickers)}", file=sys.stderr, flush=True)
        try:
            df, atr = _prep_live(d[t].dropna())
        except Exception:
            continue
        if df is None:
            continue
        prepped.append((t, df, atr))
    print(f"  {len(prepped)}/{len(tickers)} tickers survive baseline; "
          f"reading structures with jobs={jobs}", file=sys.stderr, flush=True)

    rows = []
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for i, (t, info) in enumerate(
                    pool.imap_unordered(_census_one, prepped, chunksize=8)):
                if i and i % 200 == 0:
                    print(f"  ...read {i}/{len(prepped)}", file=sys.stderr, flush=True)
                if info is not None:
                    rows.append((t, info))
    else:
        for t, df, atr in prepped:
            t, info = _census_one((t, df, atr))
            if info is not None:
                rows.append((t, info))

    rows.sort(key=lambda r: r[1]["ext_days"], reverse=True)
    n = len(rows)
    ext = [r[1]["ext_days"] for r in rows]
    worked = [r for r in rows if r[1]["ext_days"] > 0
              and (r[1]["ext_r_touches"] + r[1]["ext_s_touches"]) > 0]
    buckets = {
        "0 (start already earliest-conforming)": sum(1 for e in ext if e == 0),
        "1-2 bars": sum(1 for e in ext if 1 <= e <= 2),
        "3-5 bars": sum(1 for e in ext if 3 <= e <= 5),
        "6-10 bars": sum(1 for e in ext if 6 <= e <= 10),
        ">10 bars": sum(1 for e in ext if e > 10),
    }
    print(f"\n  box-start back-extension census: {n} firing setups")
    for k, v in buckets.items():
        print(f"    {k:<38} {v:>4}  ({v / n * 100:.0f}%)" if n else f"    {k}: 0")
    if n:
        nz = [e for e in ext if e > 0]
        print(f"    extensions > 0: {len(nz)}/{n} ({len(nz) / n * 100:.0f}%)"
              + (f", median {int(np.median(nz))} / max {max(nz)} bars" if nz else ""))
        print(f"    extensions containing rail TOUCHES (worked, AGCO-class): "
              f"{len(worked)}/{n} ({len(worked) / n * 100:.0f}%)")

    top = [r for r in rows if r[1]["ext_days"] > 0][:25]
    if top:
        print("\n  ticker   elected start  ext start    +bars  extR/extS touch  base_len")
        print("  " + "-" * 72)
        for t, x in top:
            print(f"  {t:<7}  {x['start_date']}    {x['ext_start_date']}   "
                  f"{x['ext_days']:>4}   {x['ext_r_touches']}/{x['ext_s_touches']:<12} "
                  f"{x['base_len']:>5}")
    return rows


def render(pairs, window, d):
    """Render each (ticker, info): rails over the elected span (solid) and the
    band-conforming extension span (hatched) so the operator can judge whether
    the earlier start is the better read."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tools.pip_preview import _draw_ohlc

    os.makedirs(_OUT_DIR, exist_ok=True)
    for t, info in pairs:
        df, atr = _prep_live(d[t].dropna())
        if df is None:
            print(f"  [skip {t}] {atr}")
            continue
        n_all = len(df)
        win = window if (window and 0 < window < n_all) else n_all
        base_off = n_all - win
        sl = df.iloc[base_off:]
        h = sl["High"].values.astype(float)
        lo = sl["Low"].values.astype(float)
        c = sl["Close"].values.astype(float)
        o = sl["Open"].values.astype(float) if "Open" in sl.columns else c

        R, S = info["R"], info["S"]
        sb = info["start_bar"] - base_off
        eb = win - 1
        ext_days = info["ext_days"]
        xb = sb - ext_days

        fig, ax = plt.subplots(1, 1, figsize=(15, 6))
        _draw_ohlc(ax, o, h, lo, c)
        for y in (R, S):
            ax.hlines(y, max(sb, 0), eb, color="#2563eb", lw=1.8, zorder=4)
        if ext_days > 0:
            for y in (R, S):
                ax.hlines(y, max(xb, 0), max(sb, 0), color="#f59e0b", lw=1.8,
                          ls="--", zorder=4)
            ax.axvspan(max(xb, 0), max(sb, 0), color="#f59e0b", alpha=0.10, zorder=1)
            ax.axvline(max(xb, 0), color="#f59e0b", lw=1.2, ls="--", zorder=3)
        ax.axvline(max(sb, 0), color="#2563eb", lw=1.2, ls="--", zorder=3)
        ax.set_xlim(-1, win)
        ax.grid(True, alpha=0.12)
        touch = f"{info['ext_r_touches']}R/{info['ext_s_touches']}S touches inside"
        ax.set_title(
            f"{t}    elected start {info['start_date']} (blue)  |  band-conforming "
            f"extension {info['ext_start_date'] or '-'} (+{ext_days} bars, amber, {touch})",
            fontsize=10, fontweight="bold", loc="left")
        fig.suptitle(f"{t}  —  box-start back-extension (rails unchanged: "
                     f"R={R:.2f} S={S:.2f})", fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        out = os.path.join(_OUT_DIR, f"{t}.png")
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"  rendered {t} -> {out}")


def main():
    ap = argparse.ArgumentParser(
        description="Census: how far does each elected box's start extend "
                    "leftward over bars conforming to its own buffered band?")
    ap.add_argument("tickers", nargs="*",
                    help="render these tickers (default: scan + render top extenders)")
    ap.add_argument("--window", type=int, default=260,
                    help="bars to show (default 260; 0 = all)")
    ap.add_argument("--no-render", action="store_true",
                    help="measure only, don't render")
    ap.add_argument("--top", type=int, default=10,
                    help="how many top extenders to render (default 10)")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2),
                    help="process-pool size (default: cores - 2)")
    a = ap.parse_args()

    d, level0 = _load_cache()

    if a.tickers:
        pairs = []
        for t in (x.upper() for x in a.tickers):
            if t not in level0:
                print(f"  [skip {t}] not in cache")
                continue
            df, atr = _prep_live(d[t].dropna())
            if df is None:
                print(f"  [skip {t}] {atr}")
                continue
            _, info = _census_one((t, df, atr))
            if info is None:
                print(f"  [skip {t}] no firing structure")
                continue
            print(f"  {t}: elected {info['start_date']}  ext +{info['ext_days']} "
                  f"-> {info['ext_start_date']}  touches "
                  f"{info['ext_r_touches']}R/{info['ext_s_touches']}S")
            pairs.append((t, info))
        render(pairs, a.window, d)
        return

    rows = scan(d, level0, jobs=a.jobs)
    if a.no_render:
        return
    top = [r for r in rows if r[1]["ext_days"] > 0][:a.top]
    if top:
        print(f"\n  rendering top {len(top)} extenders")
        render(top, a.window, d)


if __name__ == "__main__":
    main()
