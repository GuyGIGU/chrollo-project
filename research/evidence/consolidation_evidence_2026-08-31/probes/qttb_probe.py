"""Why does QTTB (tier-S strict fire) stop firing under the bar-unit patch?"""
import os, sys, contextlib
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.evaluation import apply_baseline_filters
from engine_alpha.structure.events import event_map
from engine_alpha.structure.narrative import read_structure

ORIG = event_map.frame_terminal_posture
def bar_unit(last_high, last_close, R, tol):
    return event_map.frame_r_engaged(last_high, R, tol)

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
raw = d["QTTB"].dropna()
df, _ = apply_baseline_filters(raw.copy())
df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
atr = float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])

for on, lab in ((False, "SHIPPED"), (True, "PATCHED")):
    event_map.frame_terminal_posture = bar_unit if on else ORIG
    try:
        tr = []
        s = read_structure(df, atr, trace=tr)
    finally:
        event_map.frame_terminal_posture = ORIG
    print(f"===== {lab} =====")
    if s:
        print(f"  FIRE  R {s.box.R:.2f}/S {s.box.S:.2f} start {df.index[s.box.start_bar].date()} "
              f"pool={s.box.elected_pool}")
    else:
        print("  no read")
    for i, rec in enumerate(tr):
        out = rec.get("outcome")
        if out != "no_box":
            elected = [c for c in rec.get("box_cascade", []) or []
                       if c.get("stage") == "selection"]
            e = elected[0] if elected else {}
            print(f"    root #{i}: outcome={out}  "
                  f"elected R {e.get('R')}/S {e.get('S')} start {e.get('cand_start')} "
                  f"pool_rescued={e.get('rescued')}")
    print(f"    total roots: {len(tr)}, outcomes: "
          f"{ {o: [r.get('outcome') for r in tr].count(o) for o in set(r.get('outcome') for r in tr)} }\n")
