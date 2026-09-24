import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.evaluation import apply_baseline_filters
from engine_alpha.structure.events import event_map
from engine_alpha.structure.narrative import read_structure

ORIG = event_map.frame_terminal_posture
def bar_unit(h, c, R, tol): return event_map.frame_r_engaged(h, R, tol)

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
raw = d["QTTB"].dropna()
df, _ = apply_baseline_filters(raw.copy())
df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
atr = float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])

for on, lab in ((False, "SHIPPED"), (True, "PATCHED")):
    event_map.frame_terminal_posture = bar_unit if on else ORIG
    try:
        s = read_structure(df, atr)
    finally:
        event_map.frame_terminal_posture = ORIG
    b = s.box
    w = (b.R - b.S) / b.S
    print(f"{lab}: R {b.R:.2f} S {b.S:.2f} width {w:.4f} "
          f"start {df.index[b.start_bar].date()} pool={b.elected_pool}")
    lps = getattr(s, "lps", None)
    for name in ("lps", "lps_start_bar", "lps_end_bar", "spring_bar"):
        v = getattr(s, name, "n/a")
        if v != "n/a" and v is not None and "bar" in name:
            v = f"{v} = {df.index[int(v)].date()}"
        print(f"    {name}: {v}")
    print(f"    last close {df['Close'].iloc[-1]:.2f}  ext cap R*1.15 = {b.R*1.15:.2f}")
