"""CANDLE_SPREAD_AWARE A/B — score each latest-scan fire with the flag off vs on,
on the SAME bar, and surface how the self-referential bar-texture grade moves the
``box_tightness`` sub-score (and the total).

Read-only / faithful: it evaluates through the live ``_evaluate_ticker`` -> the
single shared ``score_setup`` call, flipping only ``settings.CANDLE_SPREAD_AWARE``
between the two passes. The ``box_tightness`` delta is purely the multiplicative
candle-readability grade (grades-not-vetoes, in ``[CANDLE_GRADE_FLOOR, 1.0]``);
everything else is held constant. Unlike the puzzle bonus this term can only
*discount* box_tightness (grade <= 1), so a clean base reads grade 1.00 / zero
change and a choppy wide-bar base gets docked. breadth is held None for both
passes, so the per-setup DELTA and the grade are exact; the absolute Score/Tier are
a breadth-neutral baseline (tier flips here are indicative — confirm exact behaviour
in a live scan).

    python -m tools.candle_ab                 # latest-scan fires
    python -m tools.candle_ab AAON TITN DHX    # explicit tickers
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
from core.pipeline.evaluation import _evaluate_ticker
from tools.lps_swing_census import _latest_scan_fires


def _eval(ticker: str, raw: pd.DataFrame, enabled: bool):
    prev = settings.CANDLE_SPREAD_AWARE
    settings.CANDLE_SPREAD_AWARE = enabled
    try:
        return _evaluate_ticker(ticker, raw.copy(), 0.0, None)
    finally:
        settings.CANDLE_SPREAD_AWARE = prev


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
        box_off = off["_sub_scores"].get("box_tightness")
        box_on = on["_sub_scores"].get("box_tightness")
        s_off, s_on = float(off["Score"]), float(on["Score"])
        grade = (box_on / box_off) if (box_off not in (None, 0)) else None
        rows.append({
            "t": t,
            "box_off": box_off, "box_on": box_on, "grade": grade,
            "off": s_off, "on": s_on, "d": round(s_on - s_off, 1),
            "tier_off": off["Tier"], "tier_on": on["Tier"],
        })

    # Most-docked first (lowest grade / most-negative delta) — the choppy bases.
    rows.sort(key=lambda r: (r["grade"] if r["grade"] is not None else 1.0))
    print(f"{'tkr':>6} {'box_off':>7} {'box_on':>7} {'grade':>5} "
          f"{'off':>6} {'on':>6} {'dlt':>5} {'tier':>9}")
    flips = docked = 0
    for r in rows:
        flip = "" if r["tier_off"] == r["tier_on"] else f" {r['tier_off']}->{r['tier_on']}"
        if flip:
            flips += 1
        if r["grade"] is not None and r["grade"] < 0.999:
            docked += 1
        print(f"{r['t']:>6} "
              f"{(r['box_off'] if r['box_off'] is not None else 0):>7.2f} "
              f"{(r['box_on'] if r['box_on'] is not None else 0):>7.2f} "
              f"{(r['grade'] if r['grade'] is not None else 1.0):>5.2f} "
              f"{r['off']:>6.1f} {r['on']:>6.1f} {r['d']:>5.1f} {(r['tier_on'] + flip):>9}")
    n = len(rows)
    if n:
        avg = sum(r["d"] for r in rows) / n
        print(f"\n{n} setups | {docked} docked (<1.00 grade) | mean dlt {avg:+.2f} | "
              f"min dlt {min(r['d'] for r in rows):+.1f} | {flips} tier flips (breadth-neutral baseline)")


def main() -> None:
    ap = argparse.ArgumentParser(description="CANDLE_SPREAD_AWARE A/B (flag off vs on).")
    ap.add_argument("tickers", nargs="*", help="tickers (default: latest-scan fires)")
    a = ap.parse_args()
    tickers = a.tickers or (_latest_scan_fires() or [])
    if not tickers:
        print("no tickers")
        return
    audit(tickers)


if __name__ == "__main__":
    main()
