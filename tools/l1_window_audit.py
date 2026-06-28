"""Layer-1 window read — eyeball ``classify_window_descent`` on real LPS windows.

Read-only. For each ticker that fires an LPS/REBOUND on the latest archived scan
(or an explicit list), replay the live spine to the elected Phase-D LPS, then run
the order-AWARE Layer-1 reader (``classify_window_descent``) over the SAME window
the order-agnostic live election reads (``df.iloc[start_bar:start_bar+length]``).

The point of the eyeball: surface where the order-aware read DISAGREES with the
live election — a window the engine fired but L1 calls a ``rising_march`` (a
markup leg, not a test) or one that already ``turned`` up before its last bar.
Those are the cases to look at on the chart before wiring L1 into the live LPS
election (flag-gated). It also prints the ``depth_atr`` distribution so the
big-dip threshold can be picked from real fires rather than guessed.

It reads the live parquet cache + the calibrated bricks; it changes nothing and
gates nothing — the order-agnostic ``_pairwise_descent_fraction`` stays the live
read.

    python -m tools.l1_window_audit                 # latest-scan LPS/REBOUND fires
    python -m tools.l1_window_audit OHI AEF NMAI     # explicit tickers
    python -m tools.l1_window_audit --cluster        # the swing-census cluster
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
from core.structure.market_structure import classify_window_descent
from tools.lps_swing_census import CLUSTER, _first_complete, _latest_scan_fires
from tools.structure_case_audit import _prep


def _base_spread(df: pd.DataFrame, box) -> float:
    """Median bar spread across the box base — the 'base average' L1 compares the
    window's tightness against (drives ``tighter_than_base`` + the flat band)."""
    base = df.iloc[int(box.start_bar):]
    spreads = (base["High"].astype(float) - base["Low"].astype(float))
    return float(spreads.median()) if len(spreads) else 0.0


def _l1_read(df: pd.DataFrame, box, lps, atr: float) -> dict:
    start = int(lps.start_bar)
    end = start + int(lps.length)
    window = df.iloc[start:end]
    highs = window["High"].values.astype(float)
    lows = window["Low"].values.astype(float)
    out = classify_window_descent(
        highs, lows, base_spread=_base_spread(df, box), atr=atr,
    )
    box_height = float(box.R) - float(box.S)
    out["depth_box"] = (out["depth"] / box_height) if box_height > 0 else 0.0
    # Net Close advance over the window / box height — the SAME metric the live
    # markup gate (LPS_RESCUE_MAX_ADVANCE_BOX) tests. Lets the eyeball judge a
    # rising_march by real markup magnitude, not just "both bars ticked up".
    net_close = float(window["Close"].iloc[-1]) - float(window["Close"].iloc[0])
    out["net_adv_box"] = (net_close / box_height) if box_height > 0 else 0.0
    return out


def _flag(out: dict) -> str:
    """The eyeball target: where the order-aware read contradicts a live fire."""
    if out["rising_march"]:
        return "<< MARCH"          # L1: markup leg, not a test
    if out["classification"] == "turned":
        return "<< TURNED"         # L1: test ended before the window did
    if len(out["noise_pokes"]) >= 2:
        return "~pokes"            # soft: several forgiven high-pokes
    return ""


def audit(tickers: list[str]) -> None:
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))

    hdr = (f"{'ticker':>7} {'len':>3} {'swing_type(live)':>20} "
           f"{'loDsc':>5} {'hiDsc':>5} | {'L1 class':>12} {'pk':>2} {'turn':>4} "
           f"{'end_shape':>10} {'march':>5} {'netAdv':>6} {'dpthBox':>7} {'dpthATR':>7}  flag")
    print(hdr)
    print("-" * len(hdr))

    rows = []
    for t in tickers:
        t = t.upper()
        if t not in level0:
            print(f"{t:>7}  not-in-cache")
            continue
        prep = _prep(d[t].dropna())
        if prep[0] is None:
            print(f"{t:>7}  prep-reject: {prep[1]}")
            continue
        df, atr = prep
        box, lps = _first_complete(df, atr)
        if lps is None:
            print(f"{t:>7}  no-complete-narrative (does not fire today)")
            continue
        out = _l1_read(df, box, lps, atr)
        flag = _flag(out)
        turn = "-" if out["confirmed_turn_bar"] is None else str(out["confirmed_turn_bar"])
        depth_atr = "-" if out["depth_atr"] is None else f"{out['depth_atr']:.2f}"
        print(f"{t:>7} {lps.length:>3} {lps.swing_type:>20} "
              f"{lps.descent_frac:>5.2f} {lps.high_descent_frac:>5.2f} | "
              f"{out['classification']:>12} {len(out['noise_pokes']):>2} {turn:>4} "
              f"{out['end_shape']:>10} {('Y' if out['rising_march'] else 'n'):>5} "
              f"{out['net_adv_box']:>6.2f} {out['depth_box']:>7.2f} {depth_atr:>7}  {flag}")
        rows.append({"ticker": t, "swing_type": lps.swing_type, "out": out, "flag": flag})

    _summary(rows)


def _summary(rows: list[dict]) -> None:
    if not rows:
        return
    from collections import Counter
    classes = Counter(r["out"]["classification"] for r in rows)
    march = [r for r in rows if r["out"]["rising_march"]]
    turned = [r for r in rows if r["out"]["classification"] == "turned"]
    depths = sorted(r["out"]["depth_atr"] for r in rows if r["out"]["depth_atr"] is not None)

    print()
    print(f"LAYER-1 WINDOW READ  ({len(rows)} fires)")
    print("  classification:", ", ".join(f"{k}:{v}" for k, v in classes.most_common()))
    if march:
        print(f"  rising_march (L1 would reject as markup) [{len(march)}]: "
              + ", ".join(f"{r['ticker']}({r['swing_type']})" for r in march))
    if turned:
        print(f"  turned (test ended mid-window) [{len(turned)}]: "
              + ", ".join(f"{r['ticker']}@bar{r['out']['confirmed_turn_bar']}" for r in turned))
    if depths:
        mid = depths[len(depths) // 2]
        print(f"  depth_atr: min={depths[0]:.2f} med={mid:.2f} max={depths[-1]:.2f} "
              f"(big-dip threshold candidate = high end)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Layer-1 window read eyeball.")
    ap.add_argument("tickers", nargs="*", help="tickers (default: latest-scan fires)")
    ap.add_argument("--cluster", action="store_true", help="the swing-census cluster")
    a = ap.parse_args()
    if a.cluster:
        tickers = CLUSTER
    elif a.tickers:
        tickers = a.tickers
    else:
        tickers = _latest_scan_fires() or CLUSTER
    audit(tickers)


if __name__ == "__main__":
    main()
