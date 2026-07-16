"""Shared-rail back-extension A/B — the gap-#3 lever's actual flag-on effect.

Runs the live reader twice per ticker (BOX_BACKEXT_ENABLED off, then on) and
diffs the outcome: fires gained/lost (the extension moves base_len, so the LPS
range threshold / spring / inner reads shift and a story can flip), starts
moved and by how many bars, whether the story changed rails (a different root
won after an LPS flip), and whether the LPS setup_type flipped within the same
rails ("re-storied" means rails AND setup stable, so setup flips get their own
bucket). This is the eyeball surface for the operator flip
— unlike tools/box_start_extension_census.py (raw band-conformance, the upper
bound), this measures what the LEVER actually does.

Read-only: reads the parquet cache, restores the flag, writes PNGs to
tools/fidelity/box_backext/. Nothing live imports it.

    python -m tools.box_backext_ab                 # universe A/B + render top movers
    python -m tools.box_backext_ab AGCO BKH        # A/B + render specific tickers
    python -m tools.box_backext_ab --no-render     # measure only
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

_OUT_DIR = os.path.join(_THIS, "fidelity", "box_backext")


def _snap(s, df):
    if s is None:
        return None
    box = s.box
    return {
        "R": float(box.R), "S": float(box.S),
        "start_bar": int(box.start_bar),
        "start_date": str(df.index[int(box.start_bar)].date()),
        "base_len": int(box.base_len),
        "setup": getattr(s.lps, "setup_type", None),
    }


def _ab_one(args):
    """Pool worker: read the same frame with the lever off, then on."""
    t, df, atr = args
    prev = settings.BOX_BACKEXT_ENABLED
    try:
        settings.BOX_BACKEXT_ENABLED = False
        off = _snap(read_structure(df, atr), df)
        settings.BOX_BACKEXT_ENABLED = True
        on = _snap(read_structure(df, atr), df)
    finally:
        settings.BOX_BACKEXT_ENABLED = prev
    return t, off, on


def _classify(off, on):
    if off is None and on is None:
        return None
    if off is not None and on is None:
        return "lost"
    if off is None and on is not None:
        return "gained"
    if abs(off["R"] - on["R"]) > 1e-9 or abs(off["S"] - on["S"]) > 1e-9:
        return "story_changed"
    # Same rails but a different LPS setup_type = the story flipped WITHIN the
    # box (the moved start shifted the LPS/spring/inner reads). "0 re-storied"
    # must mean rails AND setup stable, so this is its own bucket.
    if off["setup"] != on["setup"]:
        return "setup_flipped"
    if on["start_bar"] < off["start_bar"]:
        return "moved"
    return "unchanged"


def scan(d, level0, jobs: int = 1):
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
          f"A/B reading with jobs={jobs}", file=sys.stderr, flush=True)

    results = []
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for i, res in enumerate(
                    pool.imap_unordered(_ab_one, prepped, chunksize=8)):
                if i and i % 200 == 0:
                    print(f"  ...read {i}/{len(prepped)}", file=sys.stderr, flush=True)
                results.append(res)
    else:
        results = [_ab_one(p) for p in prepped]

    rows = []
    for t, off, on in results:
        kind = _classify(off, on)
        if kind is not None:
            rows.append((t, kind, off, on))

    n_off = sum(1 for _, k, *_ in rows if k not in ("gained",))
    n_on = sum(1 for _, k, *_ in rows if k not in ("lost",))
    moved = [(t, off, on) for t, k, off, on in rows if k == "moved"]
    lost = [t for t, k, *_ in rows if k == "lost"]
    gained = [t for t, k, *_ in rows if k == "gained"]
    changed = [t for t, k, *_ in rows if k == "story_changed"]
    flipped = [(t, off, on) for t, k, off, on in rows if k == "setup_flipped"]

    print(f"\n  shared-rail back-extension A/B: {n_off} fires OFF -> {n_on} fires ON")
    if moved:
        bars = [off["start_bar"] - on["start_bar"] for _, off, on in moved]
        print(f"    starts moved (same rails, same setup): {len(moved)}/{n_off} "
              f"(median {int(np.median(bars))} / max {max(bars)} bars)")
    print(f"    unchanged: {sum(1 for _, k, *_ in rows if k == 'unchanged')}")
    print(f"    fires lost: {len(lost)}  {lost if lost else ''}")
    print(f"    fires gained: {len(gained)}  {gained if gained else ''}")
    print(f"    story changed (different rails won): {len(changed)}  "
          f"{changed if changed else ''}")
    print(f"    setup flipped (same rails, LPS setup_type changed): {len(flipped)}")
    for t, off, on in flipped:
        print(f"      {t}: {off['setup']} -> {on['setup']}  "
              f"(start {off['start_date']} -> {on['start_date']})")

    moved.sort(key=lambda m: m[1]["start_bar"] - m[2]["start_bar"], reverse=True)
    if moved:
        print("\n  ticker   pinned start  extended start  -bars  base_len off->on")
        print("  " + "-" * 64)
        for t, off, on in moved[:25]:
            print(f"  {t:<7}  {off['start_date']}    {on['start_date']}     "
                  f"{off['start_bar'] - on['start_bar']:>4}   "
                  f"{off['base_len']:>4} -> {on['base_len']}")
    # Setup flips lead the render queue — they are the highest-value eyeball
    # material (the extension changed the story, not just the left edge).
    return flipped + moved


def render(pairs, window, d):
    """Render each (ticker, off, on): rails solid blue over the pinned span,
    amber dashed over the lever's extension span."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tools.pip_preview import _draw_ohlc

    os.makedirs(_OUT_DIR, exist_ok=True)
    for t, off, on in pairs:
        df, atr = _prep_live(d[t].dropna())
        if df is None:
            print(f"  [skip {t}] {atr}")
            continue
        n_all = len(df)
        win = window if (window and 0 < window < n_all) else n_all
        # Widen so a deep extension is never clipped out of the eyeball surface
        # (the title claims the full move; the drawn span must show it).
        win = min(n_all, max(win, n_all - int(on["start_bar"]) + 12))
        base_off = n_all - win
        sl = df.iloc[base_off:]
        h = sl["High"].values.astype(float)
        lo = sl["Low"].values.astype(float)
        c = sl["Close"].values.astype(float)
        o = sl["Open"].values.astype(float) if "Open" in sl.columns else c

        R, S = off["R"], off["S"]
        sb = off["start_bar"] - base_off
        xb = on["start_bar"] - base_off
        eb = win - 1
        bars = off["start_bar"] - on["start_bar"]

        fig, ax = plt.subplots(1, 1, figsize=(15, 6))
        _draw_ohlc(ax, o, h, lo, c)
        for y in (R, S):
            ax.hlines(y, max(sb, 0), eb, color="#2563eb", lw=1.8, zorder=4)
        if bars > 0:
            for y in (R, S):
                ax.hlines(y, max(xb, 0), max(sb, 0), color="#f59e0b", lw=1.8,
                          ls="--", zorder=4)
            ax.axvspan(max(xb, 0), max(sb, 0), color="#f59e0b", alpha=0.10, zorder=1)
            ax.axvline(max(xb, 0), color="#f59e0b", lw=1.2, ls="--", zorder=3)
        ax.axvline(max(sb, 0), color="#2563eb", lw=1.2, ls="--", zorder=3)
        ax.set_xlim(-1, win)
        ax.grid(True, alpha=0.12)
        flip = (f"  |  setup {off['setup']} -> {on['setup']}"
                if off.get("setup") != on.get("setup") else "")
        ax.set_title(
            f"{t}    pinned start {off['start_date']} (blue)  |  shared-rail "
            f"back-extension {on['start_date']} (-{bars} bars, amber){flip}",
            fontsize=10, fontweight="bold", loc="left")
        fig.suptitle(f"{t}  —  BOX_BACKEXT A/B (rails unchanged: "
                     f"R={R:.2f} S={S:.2f})", fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        out = os.path.join(_OUT_DIR, f"{t}.png")
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"  rendered {t} -> {out}")


def main():
    ap = argparse.ArgumentParser(
        description="A/B the shared-rail back-extension lever (BOX_BACKEXT) "
                    "over the live universe.")
    ap.add_argument("tickers", nargs="*",
                    help="A/B + render these tickers (default: scan + render top movers)")
    ap.add_argument("--window", type=int, default=260,
                    help="bars to show (default 260; 0 = all)")
    ap.add_argument("--no-render", action="store_true",
                    help="measure only, don't render")
    ap.add_argument("--top", type=int, default=12,
                    help="how many top movers to render (default 12)")
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
            _, off, on = _ab_one((t, df, atr))
            kind = _classify(off, on)
            print(f"  {t}: {kind}"
                  + (f"  pinned {off['start_date']} -> extended {on['start_date']} "
                     f"(-{off['start_bar'] - on['start_bar']} bars)"
                     if kind in ("moved", "setup_flipped") else "")
                  + (f"  setup {off['setup']} -> {on['setup']}"
                     if kind == "setup_flipped" else ""))
            if kind in ("moved", "setup_flipped"):
                pairs.append((t, off, on))
        if not a.no_render:
            render(pairs, a.window, d)
        return

    moved = scan(d, level0, jobs=a.jobs)
    if a.no_render:
        return
    top = moved[:a.top]
    if top:
        print(f"\n  rendering top {len(top)} movers")
        render(top, a.window, d)


if __name__ == "__main__":
    main()
