"""E3 puzzle-quality A/B — score each latest-scan fire with PUZZLE_SCORE_ENABLED
off vs on, on the SAME bar (no best-of-window drift), and surface the lift.

Read-only / faithful: it evaluates through the live ``_evaluate_ticker`` -> the
single shared ``_run_eval_chain`` -> the single ``score_setup`` call, flipping only
``settings.PUZZLE_SCORE_ENABLED`` between the two passes. The Score delta is purely
the additive puzzle bonus (bonus-only, grades-not-vetoes); everything else is held
constant. breadth is held None for both passes, so the per-setup DELTA and the
puzzle grades are exact; the absolute Score/Tier are a breadth-neutral baseline
(tier flips here are indicative — confirm exact behaviour in a live scan).

    python -m tools.puzzle_ab                 # latest-scan fires
    python -m tools.puzzle_ab AAON BCH CL      # explicit tickers
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
from engine_alpha.evaluation import _evaluate_ticker
from tools.lps_swing_census import _latest_scan_fires


def _eval(ticker: str, raw: pd.DataFrame, enabled: bool):
    prev = settings.PUZZLE_SCORE_ENABLED
    settings.PUZZLE_SCORE_ENABLED = enabled
    try:
        return _evaluate_ticker(ticker, raw.copy(), 0.0, None)
    finally:
        settings.PUZZLE_SCORE_ENABLED = prev


def audit(tickers: list[str]) -> None:
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))

    rows = []
    for t in tickers:
        t = t.upper()
        if t not in level0:
            continue
        raw = d[t].dropna()
        off = _eval(t, raw, False)
        on = _eval(t, raw, True)
        if off is None or on is None:
            continue
        s_off, s_on = float(off["Score"]), float(on["Score"])
        rows.append({
            "t": t,
            "off": s_off, "on": s_on, "d": round(s_on - s_off, 1),
            "tier_off": off["Tier"], "tier_on": on["Tier"],
            "puz": on["_sub_scores"].get("puzzle_quality"),
            "comp": on.get("_puzzle_completeness"),
            "chr": on.get("_puzzle_chronology"),
            "ut": on.get("_puzzle_upthrust_terminal"),
        })

    rows.sort(key=lambda r: r["d"], reverse=True)
    print(f"{'tkr':>6} {'off':>6} {'on':>6} {'dlt':>5} {'s_puz':>6} "
          f"{'comp':>4} {'chronology':>10} {'tier':>9} {'UT':>3}")
    flips = 0
    for r in rows:
        flip = "" if r["tier_off"] == r["tier_on"] else f" {r['tier_off']}->{r['tier_on']}"
        if flip:
            flips += 1
        ut = "yes" if r["ut"] else ""
        print(f"{r['t']:>6} {r['off']:>6.1f} {r['on']:>6.1f} {r['d']:>5.1f} "
              f"{(r['puz'] if r['puz'] is not None else 0):>6.2f} "
              f"{(r['comp'] if r['comp'] is not None else '-'):>4} "
              f"{str(r['chr']):>10} {(r['tier_on'] + flip):>9} {ut:>3}")
    n = len(rows)
    if n:
        avg = sum(r["d"] for r in rows) / n
        moved = sum(1 for r in rows if r["d"] > 0)
        print(f"\n{n} setups | {moved} lifted | mean dlt {avg:+.2f} | "
              f"max dlt {rows[0]['d']:+.1f} | {flips} tier flips (breadth-neutral baseline)")


def main() -> None:
    ap = argparse.ArgumentParser(description="E3 puzzle-quality A/B (flag off vs on).")
    ap.add_argument("tickers", nargs="*", help="tickers (default: latest-scan fires)")
    a = ap.parse_args()
    tickers = a.tickers or (_latest_scan_fires() or [])
    if not tickers:
        print("no tickers")
        return
    audit(tickers)


if __name__ == "__main__":
    main()
