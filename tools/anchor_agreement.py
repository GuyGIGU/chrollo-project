"""
Read-only blast-radius diagnostic for the swing-segmentation layer.

For every ticker in the frozen shadow fixture (the current firing set), it runs
today's engine to get the chosen BC anchor, then runs ``segment_swings`` to get
the root-swing BC (the trend->range bridge), and reports where they AGREE vs
DISAGREE. Disagreements are exactly the tickers a Phase-2 wiring could move.

Pure measurement: changes nothing, gates nothing. Just tells us the size and
shape of the gap before we touch behavior.

    python -m tools.anchor_agreement
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import settings
from core.pipeline.screener import apply_baseline_filters
from core.structure.consolidation import find_consolidation
from core.structure.indicators import calculate_atr
from core.structure.segmentation import segment_swings
from tools.shadow_diff import _load_fixture

# A BC within this many bars of the segmentation root counts as agreement
# (pivot detection has a few-bar granularity).
TOL_BARS = 3
# Lead-in bars before the engine's BC so the segmentation window also contains
# the trend running INTO the base (and any later true climax).
LEAD_IN = 60
LOOKBACK_CAP = 250


def _date(df, i):
    try:
        return str(df.index[i])[:10]
    except (IndexError, TypeError, ValueError):
        return "?"


def main() -> None:
    frames, _scalars = _load_fixture()

    agree, disagree, skipped = [], [], []

    for ticker in sorted(frames):
        raw = frames[ticker]
        base = apply_baseline_filters(raw.copy())
        if base is None:
            skipped.append((ticker, "baseline"))
            continue
        df, _yr = base
        df = df.copy()
        df["ATR_10"] = calculate_atr(df, 10)
        df["ATR_50"] = calculate_atr(df, 50)

        tup = find_consolidation(df, min_days=settings.MIN_BASE_DAYS)
        base_len, bc_anchor_bar = tup[0], tup[9]
        if base_len == 0:
            skipped.append((ticker, "no_base"))
            continue

        atr = float(df.iloc[-6]["ATR_10"])
        bars_since_bc = len(df) - bc_anchor_bar
        lookback = min(len(df), max(bars_since_bc + LEAD_IN, settings.MIN_BASE_DAYS + LEAD_IN))
        lookback = min(lookback, LOOKBACK_CAP)

        seg = segment_swings(df, atr, lookback=lookback)
        root = seg.get("root_swing")
        if root is None:
            skipped.append((ticker, "no_root"))
            continue

        eng_bc = bc_anchor_bar
        seg_bc = root["bc_bar"]
        gap = seg_bc - eng_bc
        eng_price = float(df["High"].iloc[eng_bc])
        seg_price = float(df["High"].iloc[seg_bc])

        rec = {
            "ticker": ticker,
            "gap": gap,
            "eng_bc_date": _date(df, eng_bc), "eng_bc_px": round(eng_price, 2),
            "seg_bc_date": _date(df, seg_bc), "seg_bc_px": round(seg_price, 2),
            "burst": root.get("counter_burst_ratio"),
            "trend_disp": root.get("trend_disp_atr"),
            "px_higher": seg_price > eng_price * 1.02,  # seg climax materially above engine's
        }
        (agree if abs(gap) <= TOL_BARS else disagree).append(rec)

    total = len(agree) + len(disagree)
    print("=" * 72)
    print("  ANCHOR-AGREEMENT DIAGNOSTIC  (engine BC vs segmentation root swing)")
    print("=" * 72)
    print(f"  fixture tickers: {len(frames)}   compared: {total}   skipped: {len(skipped)}")
    if total:
        print(f"  AGREE  (|gap| <= {TOL_BARS} bars): {len(agree)}  ({100*len(agree)/total:.0f}%)")
        print(f"  DISAGREE                        : {len(disagree)}  ({100*len(disagree)/total:.0f}%)")
    if skipped:
        from collections import Counter
        print(f"  skipped reasons: {dict(Counter(r for _, r in skipped))}")

    if disagree:
        print("\n  DISAGREEMENTS (the Phase-2 blast radius):")
        print(f"  {'ticker':8} {'gap':>5}  {'engine BC':>20}  {'segmentation BC':>20}  {'burst':>6} {'trendATR':>8}  flag")
        for r in sorted(disagree, key=lambda x: abs(x["gap"]), reverse=True):
            flag = "seg-climax-higher" if r["px_higher"] else ""
            print(f"  {r['ticker']:8} {r['gap']:>5}  "
                  f"{r['eng_bc_date']:>10} {r['eng_bc_px']:>8.2f}  "
                  f"{r['seg_bc_date']:>10} {r['seg_bc_px']:>8.2f}  "
                  f"{str(r['burst']):>6} {str(r['trend_disp']):>8}  {flag}")

    # A couple of agreement spot-checks for confidence (e.g., MEOH).
    if agree:
        print("\n  AGREEMENT spot-checks:")
        for r in agree[:6]:
            print(f"  {r['ticker']:8} gap={r['gap']:>2}  BC {r['eng_bc_date']} @ {r['eng_bc_px']}")


if __name__ == "__main__":
    main()
