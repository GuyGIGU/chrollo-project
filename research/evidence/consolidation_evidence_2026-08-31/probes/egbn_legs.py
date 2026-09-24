import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.evaluation import apply_baseline_filters
from engine_alpha.structure.box.box_gates import _measure_close_residence
from engine_alpha.structure.events.event_map import (
    read_rail_episodes, episode_sequence_stats, story_admission,
    resistance_contraction_admission)

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
raw = d["EGBN"].dropna(); raw = raw[raw.index <= pd.Timestamp("2026-01-07")]
df, _ = apply_baseline_filters(raw.copy())
df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
atr = float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])

R, S, start = 21.64, 20.49, 483
win = df.iloc[start:]
eq = _measure_close_residence(win, R, S, atr)
print(f"window {win.index[0].date()}..{win.index[-1].date()}  {len(win)} trading days\n")
print("THE FIRST TEST — eight checks on the drawn box")
rows = [
 ("touches of the ceiling",  eq['r_touches'], f">= {settings.EQ_MIN_TOUCHES_PER_RAIL}", eq['r_touches'] >= settings.EQ_MIN_TOUCHES_PER_RAIL),
 ("touches of the floor",    eq['s_touches'], f">= {settings.EQ_MIN_TOUCHES_PER_RAIL}", eq['s_touches'] >= settings.EQ_MIN_TOUCHES_PER_RAIL),
 ("ceiling touched across",  f"{eq['r_touch_thirds']}/3 of the time", f">= {settings.EQ_MIN_TOUCH_THIRDS}", eq['r_touch_thirds'] >= settings.EQ_MIN_TOUCH_THIRDS),
 ("floor touched across",    f"{eq['s_touch_thirds']}/3 of the time", f">= {settings.EQ_MIN_TOUCH_THIRDS}", eq['s_touch_thirds'] >= settings.EQ_MIN_TOUCH_THIRDS),
 ("closes in BOTTOM third",  f"{eq['lower_count']}/{eq['n']} = {eq['lower_dwell']}", f">= {settings.EQ_MIN_HALF_DWELL}", eq['lower_dwell'] >= settings.EQ_MIN_HALF_DWELL),
 ("closes in TOP third",     f"{eq['upper_count']}/{eq['n']} = {eq['upper_dwell']}", f">= {settings.EQ_MIN_HALF_DWELL}", eq['upper_dwell'] >= settings.EQ_MIN_HALF_DWELL),
 ("closes in MIDDLE third",  f"{eq['mid_count']}/{eq['n']} = {eq['mid_dwell']}", f"<= {settings.EQ_MAX_MID_DWELL}", eq['mid_dwell'] <= settings.EQ_MAX_MID_DWELL),
 ("height bins with dwell",  f"{eq['coverage_occupied']}/{eq['coverage_bins']} = {eq['coverage']}", f">= {settings.EQ_MIN_COVERAGE}", eq['coverage'] >= settings.EQ_MIN_COVERAGE),
]
for name, got, want, ok in rows:
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<24} {str(got):<22} needs {want}")
need = settings.EQ_MIN_HALF_DWELL * eq['n']
print(f"\n  the whole miss: needs {need:.2f} -> {int(need)+1} closes in the bottom third, has {eq['lower_count']}")

print("\nTHE SECOND TEST — the same window read as events")
stats = episode_sequence_stats(read_rail_episodes(win, R, S, atr))
for k in ("n_completed_s", "n_failed_s", "terminal_s_drift", "terminal_r_engagement", "terminal_r_posture"):
    print(f"  {k:<24} {stats.get(k)}")
print(f"  form 1 (support tests)  -> {story_admission(stats)}")
print(f"  form 2 (holds ceiling)  -> {resistance_contraction_admission(stats)}")
