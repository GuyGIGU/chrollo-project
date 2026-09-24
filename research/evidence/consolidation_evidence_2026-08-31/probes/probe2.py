"""ONE concept judged in the operator's unit: 'the bar engages the ceiling'
decided by the bar's HIGH, close anywhere. Patches the single shared predicate,
so the story-pool prefilter AND the admission's ceiling leg move together.
Support-test requirement (the junk separator) untouched. In-process only."""
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
def bar_unit_posture(last_high, last_close, R, tol):
    return event_map.frame_r_engaged(last_high, R, tol)   # close ignored

CASES = [("EGBN", "2026-01-07", "the operator's mark"),
         ("DGII", "2026-01-07", "junk twin that fired in July"),
         ("FLG",  "2026-01-07", "junk that fired in July"),
         ("CHCT", "2026-01-07", "drift junk"),
         ("COLM", "2026-01-07", "drift junk")]

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
def frame(t, asof):
    raw = d[t].dropna(); raw = raw[raw.index <= pd.Timestamp(asof)]
    b = apply_baseline_filters(raw.copy())
    if b is None: return None, None
    df, _ = b
    df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
    df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
    return df, float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])

for t, asof, note in CASES:
    df, atr = frame(t, asof)
    if df is None:
        print(f"{t:6s} {note:32s} not in universe"); continue
    out = []
    for patch, lab in ((None, "ships"), (bar_unit_posture, "bar-unit")):
        if patch: event_map.frame_terminal_posture = patch
        try:
            s = read_structure(df, atr)
        finally:
            event_map.frame_terminal_posture = ORIG
        out.append(f"{lab}: " + (f"FIRE {s.box.R:.2f}/{s.box.S:.2f} "
                   f"{df.index[s.box.start_bar].date()} pool={s.box.elected_pool}"
                   if s else "no read"))
    print(f"{t:6s} {note:32s} {out[0]:52s} | {out[1]}")
