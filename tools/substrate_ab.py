"""Substrate A/B — the FULL detection stack on order-N pivots vs PIP election.

The macro Phase-A read (docs/pip_macro_phase_a.md) only re-draws the overlay.
THIS harness answers the deeper "which skeleton should the engine read charts
with?" question: it runs the REAL per-ticker pipeline
(``screener._evaluate_ticker`` — baseline, structure, LPS, scoring) twice per
ticker on identical frames + market scalars:

  A (shipped) : ``pivots._find_pivots`` rolling-window election, untouched.
  B (PIP)     : ``_find_pivots`` swapped — inside ``box_primitives`` and
                ``metrics`` ONLY — for a PIP importance election with a
                scale-free ``dist_min`` (fraction of window price range).

The swap points are exactly the substrate-dependent consumers that feed live
fields: box R/S candidate enumeration + validation (box_primitives) and the
contraction / ascending-support / traversal measures (metrics). Deliberately
NOT swapped: lps.py (imports no pivots — pure bar geometry), bar-spread /
ATR / volume / RS / breadth (bar-level), segmentation & market_structure
(overlay / measure-only; both PIP flags stay OFF for both engines so the ONLY
delta is the election function).

Honest-comparison caveat baked into the readout: every downstream threshold
(touch tolerance, EQ gates, traversal floors...) was CALIBRATED on the order-N
skeleton, so engine B is "PIP + foreign calibration" — a lower bound on PIP's
potential, an upper bound on migration risk. Read the deltas as directional
evidence for pick-vs-merge, not as a final PIP verdict.

Measure-only: patches live only inside this tool's worker processes (patch ->
eval -> restore in ``finally``); nothing live imports this file.

    python -m tools.substrate_ab --scan                 # full-universe A/B -> JSON + summary
    python -m tools.substrate_ab --scan --dist-min 0.03
    python -m tools.substrate_ab TICK1 TICK2 --render   # A/B box render for specific names
    python -m tools.substrate_ab --render-divergent 12  # render top box-divergent tickers
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.pip import pip_indices

_OUT_DIR = os.path.join(_THIS, "fidelity", "substrate_ab")
_JSON_PATH = os.path.join(_OUT_DIR, "substrate_ab_results.json")

_A_COLOR = "#8b5cf6"   # shipped substrate (matches the other fidelity tools)
_B_COLOR = "#f59e0b"   # PIP substrate

# Scalar result fields worth keeping (canonical + the taste-function extras).
# Everything json-scalar in the result row is captured; frames are dropped.
_CANONICAL = ("Setup", "Score", "Tier", "Base Len", "Box Width", "LPS Length",
              "_R", "_S", "_trigger_price")


# ------------------------------------------------------------- substrate ----

def _pip_find_pivots_factory(dist_min: float):
    """A drop-in for ``pivots._find_pivots(highs, lows, order)`` that elects
    bars by PIP chord importance instead of a rolling window. ``order`` is
    accepted and ignored — PIP's ``dist_min`` is scale-free, so one knob serves
    every window size the detectors probe."""
    def pip_find_pivots(highs, lows, order):  # noqa: ARG001 (order unused)
        highs = np.asarray(highs, dtype=float)
        lows = np.asarray(lows, dtype=float)
        n = len(highs)
        if n < 3 or len(lows) != n:
            return [], []
        P = (highs + lows) / 2.0
        idx = pip_indices(P, dist_min=dist_min)
        if len(idx) < 2:
            return [], []
        idx_sorted = sorted(idx)
        peaks: list[int] = []
        valleys: list[int] = []
        for pos, i in enumerate(idx_sorted):
            neighbours = []
            if pos > 0:
                neighbours.append(P[idx_sorted[pos - 1]])
            if pos < len(idx_sorted) - 1:
                neighbours.append(P[idx_sorted[pos + 1]])
            ref = float(np.mean(neighbours)) if neighbours else float(P[i])
            (peaks if float(P[i]) >= ref else valleys).append(i)
        return peaks, valleys
    return pip_find_pivots


def _patched_modules():
    import engine_alpha.structure.box_primitives as bp
    import engine_alpha.structure.metrics as mx
    return (bp, mx)


def _scalars_only(result) -> dict:
    """Project a result row down to json-scalar fields (drop frames/arrays)."""
    out = {}
    for k, v in result.items():
        if isinstance(v, (str, int, bool)) or v is None:
            out[k] = v
        elif isinstance(v, float):
            out[k] = round(v, 6)
        elif isinstance(v, np.floating):
            out[k] = round(float(v), 6)
        elif isinstance(v, np.integer):
            out[k] = int(v)
    return out


def _eval_both(args):
    """Pool worker: one ticker through the REAL pipeline under both substrates.

    Patch -> eval -> restore inside the worker; patch state is per-process and
    always restored, so A runs are never contaminated."""
    ticker, df, spy_6m, breadth, dist_min = args
    from engine_alpha.evaluation import EVAL_ERROR
    from core.pipeline.screener import _evaluate_ticker

    def run():
        r = _evaluate_ticker(ticker, df, spy_6m, breadth)
        if r is None or r is EVAL_ERROR:
            return None
        return _scalars_only(r)

    a = run()

    mods = _patched_modules()
    originals = [m._find_pivots for m in mods]
    pip_fp = _pip_find_pivots_factory(dist_min)
    try:
        for m in mods:
            m._find_pivots = pip_fp
        b = run()
    finally:
        for m, orig in zip(mods, originals):
            m._find_pivots = orig

    return ticker, a, b


# ------------------------------------------------------------------ scan ----

def _load_cache():
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    return d, sorted(set(d.columns.get_level_values(0)))


def _spy_6m(d) -> float:
    """SPY 6-month return off the cache — one number, shared by both engines
    (any constant is fair for the A/B; this keeps the uptrend context real)."""
    try:
        spy = d["SPY"]["Close"].dropna()
        if len(spy) < 130:
            return 0.0
        return float(spy.iloc[-1] / spy.iloc[-126] - 1.0)
    except Exception:
        return 0.0


def scan(jobs: int, dist_min: float) -> dict:
    d, tickers = _load_cache()
    spy_6m = _spy_6m(d)
    exclude = {getattr(settings, "MARKET_INDEX_SYMBOL", "SPY"), "SPY"}

    work = []
    for t in tickers:
        if t in exclude:
            continue
        try:
            df = d[t].dropna()
        except Exception:
            continue
        if len(df) < 50:
            continue
        work.append((t, df, spy_6m, None, dist_min))
    print(f"  {len(work)} tickers queued; spy_6m={spy_6m:+.3f}; breadth=None "
          f"(identical for both engines); dist_min={dist_min}; jobs={jobs}",
          file=sys.stderr, flush=True)

    results = {}
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for i, (t, a, b) in enumerate(
                    pool.imap_unordered(_eval_both, work, chunksize=8)):
                if i and i % 200 == 0:
                    print(f"  ...evaluated {i}/{len(work)}",
                          file=sys.stderr, flush=True)
                if a is not None or b is not None:
                    results[t] = {"A": a, "B": b}
    else:
        for i, w in enumerate(work):
            if i and i % 200 == 0:
                print(f"  ...evaluated {i}/{len(work)}", file=sys.stderr, flush=True)
            t, a, b = _eval_both(w)
            if a is not None or b is not None:
                results[t] = {"A": a, "B": b}

    os.makedirs(_OUT_DIR, exist_ok=True)
    payload = {"dist_min": dist_min, "spy_6m": round(spy_6m, 6),
               "n_evaluated": len(work), "results": results}
    with open(_JSON_PATH, "w") as f:
        json.dump(payload, f)
    print(f"  wrote {_JSON_PATH}", file=sys.stderr, flush=True)
    return payload


# --------------------------------------------------------------- summary ----

def _fmt(v, nd=3):
    return "None" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def summarize(payload: dict):
    res = payload["results"]
    fires_a = {t for t, r in res.items() if r["A"]}
    fires_b = {t for t, r in res.items() if r["B"]}
    both = sorted(fires_a & fires_b)
    only_a = sorted(fires_a - fires_b)
    only_b = sorted(fires_b - fires_a)

    print(f"\n  SUBSTRATE A/B  (A = shipped order-N pivots, B = PIP dist_min="
          f"{payload['dist_min']}; {payload['n_evaluated']} tickers evaluated)")
    print(f"    fires: A {len(fires_a)}   B {len(fires_b)}   both {len(both)}   "
          f"only-A {len(only_a)}   only-B {len(only_b)}")
    if only_a:
        print(f"    only-A: {' '.join(only_a)}")
    if only_b:
        print(f"    only-B: {' '.join(only_b)}")

    if not both:
        return

    def col(t, eng, key):
        return res[t][eng].get(key)

    rows = []
    for t in both:
        bw_a, bw_b = col(t, "A", "Box Width"), col(t, "B", "Box Width")
        bl_a, bl_b = col(t, "A", "Base Len"), col(t, "B", "Base Len")
        sc_a, sc_b = col(t, "A", "Score"), col(t, "B", "Score")
        tier_a, tier_b = col(t, "A", "Tier"), col(t, "B", "Tier")
        s_a, s_b = col(t, "A", "_S"), col(t, "B", "_S")
        r_a, r_b = col(t, "A", "_R"), col(t, "B", "_R")
        box_moved = (s_a != s_b) or (r_a != r_b) or (bl_a != bl_b)
        rows.append((t, bw_a, bw_b, bl_a, bl_b, sc_a, sc_b,
                     tier_a, tier_b, box_moved))

    moved = [r for r in rows if r[9]]
    dbw = [r[2] - r[1] for r in moved if r[1] is not None and r[2] is not None]
    tighter_b = sum(1 for x in dbw if x < -1e-9)
    tighter_a = sum(1 for x in dbw if x > 1e-9)
    tier_flips = [(r[0], r[7], r[8]) for r in rows if r[7] != r[8]]

    print(f"\n    common fires with a DIFFERENT box (S, R or base length): "
          f"{len(moved)}/{len(both)}")
    if dbw:
        print(f"    box-width delta (B - A) on moved boxes: median "
              f"{np.median(dbw):+.4f}   B tighter {tighter_b}   A tighter {tighter_a}")
    print(f"    tier flips: {len(tier_flips)}"
          + (f"   {['%s %s->%s' % f for f in tier_flips]}" if tier_flips else ""))

    moved.sort(key=lambda r: abs((r[2] or 0) - (r[1] or 0)), reverse=True)
    print("\n    ticker   boxW A -> B        baseLen A -> B    score A -> B      tier")
    print("    " + "-" * 72)
    for t, bw_a, bw_b, bl_a, bl_b, sc_a, sc_b, ta, tb, _ in moved[:25]:
        print(f"    {t:<7}  {_fmt(bw_a)} -> {_fmt(bw_b)}   "
              f"{_fmt(bl_a,0):>5} -> {_fmt(bl_b,0):<5}   "
              f"{_fmt(sc_a,1):>6} -> {_fmt(sc_b,1):<6}   {ta}->{tb}")
    return moved


# ---------------------------------------------------------------- render ----

def render(tickers: list[str], window: int):
    """A/B box render: both engines' elected R/S rails + box start on one
    chart, via the same read_structure the pipeline draws from."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    from tools.phase_a_pip_diff import _prep_live
    from engine_alpha.structure.narrative import read_structure
    from tools.pip_preview import _draw_ohlc

    d, _ = _load_cache()
    os.makedirs(_OUT_DIR, exist_ok=True)

    def read_box(df, atr):
        s = read_structure(df, atr)
        if s is None:
            return None
        return (int(s.box.start_bar), float(s.box.S), float(s.box.R))

    for t in tickers:
        t = t.upper()
        try:
            df, atr = _prep_live(d[t].dropna())
        except Exception:
            print(f"  [skip {t}] not in cache")
            continue
        if df is None:
            print(f"  [skip {t}] {atr}")
            continue

        box_a = read_box(df, atr)
        mods = _patched_modules()
        originals = [m._find_pivots for m in mods]
        try:
            pip_fp = _pip_find_pivots_factory(_ARGS.dist_min)
            for m in mods:
                m._find_pivots = pip_fp
            box_b = read_box(df, atr)
        finally:
            for m, orig in zip(mods, originals):
                m._find_pivots = orig

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
        titles = []
        for box, color, name in ((box_a, _A_COLOR, "A shipped"),
                                 (box_b, _B_COLOR, "B PIP")):
            if box is None:
                titles.append(f"{name}: no structure")
                continue
            sb, S, R = box
            x0 = max(0, sb - base_off)
            ax.hlines([S, R], x0, win - 1, color=color, lw=1.8,
                      ls="-" if name.startswith("A") else "--", alpha=0.9)
            ax.axvline(x0, color=color, lw=1.0, ls=":", alpha=0.6)
            titles.append(f"{name}: start {sb}  S {S:.2f}  R {R:.2f}  "
                          f"w {(R - S) / S:.3f}")
        ax.set_xlim(-1, win)
        ax.grid(True, alpha=0.12)
        ax.set_title(f"{t}    " + "    |    ".join(titles), fontsize=10,
                     fontweight="bold", loc="left")
        ax.legend(handles=[
            Line2D([0], [0], color=_A_COLOR, lw=2, label="A — shipped pivots"),
            Line2D([0], [0], color=_B_COLOR, lw=2, ls="--", label="B — PIP election"),
        ], loc="upper left", fontsize=9, framealpha=0.85)
        fig.suptitle(f"{t}  —  elected box: shipped vs PIP substrate "
                     f"(faithful 2y frame, last {win} bars)",
                     fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        out = os.path.join(_OUT_DIR, f"{t}.png")
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"  rendered {t} -> {out}")


# ------------------------------------------------------------------ main ----

_ARGS = None


def main():
    global _ARGS
    ap = argparse.ArgumentParser(description="Full-stack substrate A/B: shipped "
                                             "pivots vs PIP election.")
    ap.add_argument("tickers", nargs="*", help="with --render: tickers to render")
    ap.add_argument("--scan", action="store_true", help="run the universe A/B")
    ap.add_argument("--summary", action="store_true",
                    help="summarize an existing results JSON")
    ap.add_argument("--render", action="store_true", help="render given tickers")
    ap.add_argument("--render-divergent", type=int, default=0, metavar="N",
                    help="render the N most box-divergent common fires")
    ap.add_argument("--window", type=int, default=300)
    ap.add_argument("--dist-min", type=float, default=0.03)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    _ARGS = ap.parse_args()

    if _ARGS.scan:
        payload = scan(_ARGS.jobs, _ARGS.dist_min)
        summarize(payload)
        return

    if _ARGS.summary or _ARGS.render_divergent:
        with open(_JSON_PATH) as f:
            payload = json.load(f)
        moved = summarize(payload)
        if _ARGS.render_divergent and moved:
            names = [r[0] for r in moved[:_ARGS.render_divergent]]
            print(f"\n  rendering {len(names)} divergent: {' '.join(names)}")
            render(names, _ARGS.window)
        return

    if _ARGS.tickers:
        render([t.upper() for t in _ARGS.tickers], _ARGS.window)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
