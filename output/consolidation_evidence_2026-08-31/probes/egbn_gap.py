"""Read-only: WHY does EGBN fail the first test, and what does the second pass do?"""
import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from core.pipeline.downloads import _trim_to_period
from engine_alpha.structure.indicators import calculate_atr
from engine_alpha.evaluation import apply_baseline_filters
from engine_alpha.structure.narrative import read_structure

TICKER, ASOF = "EGBN", "2026-01-07"

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
raw = d[TICKER].dropna()
raw = raw[raw.index <= pd.Timestamp(ASOF)]
base = apply_baseline_filters(raw.copy())
print(f"universe filter: {'PASS' if base is not None else 'REJECT'}")
df, _ = base
df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
atr = float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])
print(f"frame {df.index[0].date()}..{df.index[-1].date()}  {len(df)} bars  ATR {atr:.3f}\n")

def walk(label, **flags):
    prev = {k: getattr(settings, k) for k in flags}
    for k, v in flags.items(): setattr(settings, k, v)
    try:
        tr = []
        s = read_structure(df, atr, trace=tr)
    finally:
        for k, v in prev.items(): setattr(settings, k, v)
    print(f"===== {label} =====")
    if s:
        print(f"  result: FIRE   R {s.box.R:.2f} / S {s.box.S:.2f}  "
              f"start {df.index[s.box.start_bar].date()}  pool={getattr(s.box,'elected_pool',None)}")
    else:
        print("  result: no read")
    stages = {}
    for rec in tr:
        for c in rec.get("box_cascade", []) or []:
            stages[c.get("stage")] = stages.get(c.get("stage"), 0) + 1
    print(f"  roots walked: {len(tr)}   pair-election stages: {stages}")
    shown = 0
    for rec in tr:
        for c in rec.get("box_cascade", []) or []:
            if c.get("stage") == "occupancy" and c.get("reasons") and shown < 4:
                print(f"    occupancy refusal: {c['reasons']}")
                shown += 1
    print(f"  outcomes: {[r.get('outcome') for r in tr]}\n")

walk("PASS 1 - the read as it ships today")
walk("PASS 2 - with the second opinion armed", CONTRACTION_RESCUE_ENABLED=True)
