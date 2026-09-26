"""Read-only probe: the live swing-admission with ONE leg swapped to the
operator's unit — 'the bar's HIGH engages resistance' instead of 'the CLOSE
closed above it'. Nothing on disk changes; the patch lives in this process."""
import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.evaluation import apply_baseline_filters
from engine_alpha.structure.events import event_map
from engine_alpha.structure.narrative import read_structure

def frame(ticker, asof):
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    raw = d[ticker].dropna(); raw = raw[raw.index <= pd.Timestamp(asof)]
    b = apply_baseline_filters(raw.copy())
    if b is None: return None, None
    df, _ = b
    df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
    df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
    return df, float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])

ORIGINAL = event_map.story_admission
def bar_unit_admission(stats):
    """Same form, same support requirement — only the ceiling leg changes unit."""
    return (stats["n_completed_s"] >= 2
            and stats["terminal_r_engagement"]      # was terminal_r_posture
            and not stats["terminal_s_drift"])

def read(ticker, asof, admission, label):
    df, atr = frame(ticker, asof)
    if df is None:
        print(f"  {ticker:6s} {label:18s} -> not in universe"); return
    event_map.story_admission = admission
    try:
        s = read_structure(df, atr)
    finally:
        event_map.story_admission = ORIGINAL
    if s:
        print(f"  {ticker:6s} {label:18s} -> FIRE  R {s.box.R:.2f}/S {s.box.S:.2f}  "
              f"start {df.index[s.box.start_bar].date()}  pool={s.box.elected_pool}")
    else:
        print(f"  {ticker:6s} {label:18s} -> no read")

print("EGBN at the operator's mark, ALL FLAGS AT SHIPPED DEFAULTS\n")
for adm, lab in ((ORIGINAL, "as it ships"), (bar_unit_admission, "ceiling leg = bar")):
    read("EGBN", "2026-01-07", adm, lab)

print("\nthe two junk names that fired in the July bar-dwell A/B:\n")
for t in ("DGII", "FLG"):
    for adm, lab in ((ORIGINAL, "as it ships"), (bar_unit_admission, "ceiling leg = bar")):
        read(t, "2026-01-07", adm, lab)
