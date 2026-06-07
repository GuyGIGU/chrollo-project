"""Explain why a ticker's consolidation fires, demotes, or is rejected under the
worked-equilibrium rule — the per-ticker view for dialing the EQ_* / width knobs.

For each ticker (default: the cases that drove the rewrite) it prints the chosen
parent box, the measure_equilibrium read on it, the parent/inner verdict, and the
final tier/score — or "REJECTED (no worked equilibrium)".

    python -m tools.equilibrium_explain DBD RLGT BBVA COLM
    python -m tools.equilibrium_explain            # default set

Reads the live cache; read-only.
"""
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd

from config import settings
from core.pipeline.evaluation import _evaluate_ticker, apply_baseline_filters
from core.structure import detect_boxes, measure_equilibrium
from core.structure.indicators import calculate_atr

DEFAULT = ["DBD", "RLGT", "BBVA", "ABEV", "COLM", "FLG", "KWR"]


def _market_scalars(d, level0):
    spy = settings.SPY_SYMBOL
    spy_6m = 0.0
    if spy in level0:
        sc = d[spy]["Close"].dropna()
        if len(sc) > settings.RS_LOOKBACK_BARS:
            spy_6m = float(sc.iloc[-1] / sc.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)
    bc = bt = 0
    for t in level0:
        if t == spy:
            continue
        cl = d[t]["Close"].dropna()
        if len(cl) >= 50:
            m = float(cl.iloc[-50:].mean())
            if pd.notna(m):
                bt += 1
                bc += int(float(cl.iloc[-1]) > m)
    return spy_6m, (bc / bt if bt else None)


def explain(ticker, raw, spy_6m, breadth):
    print("=" * 84)
    print(ticker)
    base = apply_baseline_filters(raw.copy())
    if base is None:
        print("  rejected at baseline filters (price/vol/trend/return)")
        return
    df, _ = base
    df = df.copy()
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    atr = float(df.iloc[-6]["ATR_10"])

    boxes = detect_boxes(df, min_days=settings.MIN_BASE_DAYS, select="earliest")
    parent = boxes["parent"]
    if parent[0] == 0:
        print("  REJECTED - no worked equilibrium (no Resistance/Support-anchor "
              "pair respects + touches + zigzags through with no dead space)")
        return

    base_len, R, S, bw = parent[0], parent[1], parent[2], parent[3]
    base_df = df.iloc[-base_len:]
    eq = measure_equilibrium(base_df, R, S, atr)
    print(f"  box R={R:.2f} S={S:.2f}  width={bw:.3f}  base_len={base_len}")
    print(f"  equilibrium: touches r/s={eq['r_touches']}/{eq['s_touches']} "
          f"thirds r/s={eq['r_touch_thirds']}/{eq['s_touch_thirds']}  "
          f"dwell lo/mid/hi={eq['lower_dwell']}/{eq['mid_dwell']}/{eq['upper_dwell']}  "
          f"coverage={eq['coverage']}")
    if boxes["inner"]:
        i = boxes["inner"]
        print(f"  inner: R={i['R']:.2f} S={i['S']:.2f} width={i['box_width']:.3f}")

    res = _evaluate_ticker(ticker, raw, spy_6m, breadth, select="earliest")
    if res:
        cap = " (width-capped from S)" if (res["Tier"] == "A" and bw > settings.S_MAX_BOX_WIDTH) else ""
        print(f"  >>> FIRES  {res['Tier']}{cap}  score={res['Score']}  {res['Setup']}")
    else:
        print("  >>> valid box but no active LPS / failed a later filter -> no fire")


def main():
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))
    spy_6m, breadth = _market_scalars(d, level0)
    for t in ([x.upper() for x in sys.argv[1:]] or DEFAULT):
        if t not in level0:
            print(f"{t}: not in cache"); continue
        explain(t, d[t].dropna(), spy_6m, breadth)


if __name__ == "__main__":
    main()
