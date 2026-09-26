import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.evaluation import apply_baseline_filters
from engine_alpha.structure.box.box_gates import _measure_close_residence
from engine_alpha.structure.metrics import measure_dwell_balance

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
raw = d["EGBN"].dropna(); raw = raw[raw.index <= pd.Timestamp("2026-01-07")]
df, _ = apply_baseline_filters(raw.copy())
df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
atr = float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])
R, S = 21.64, 20.49
lo_third = S + (R - S) / 3

for n, tag in ((17, "the window the engine judged"), (22, "the whole base to your mark")):
    w = df.iloc[483:483+n]
    c = _measure_close_residence(w, R, S, atr)
    b = measure_dwell_balance(w, R, S, atr)
    touched = int(((w["Low"] <= lo_third)).sum())
    print(f"\n{tag}  ({w.index[0].date()}..{w.index[-1].date()}, {n} days)")
    print(f"  CLOSES in the bottom third (what gates today) : {c['lower_dwell']:.4f}"
          f"   {'PASS' if c['lower_dwell'] >= 0.15 else 'FAIL'} vs 0.15")
    print(f"  BAR RANGES touching the bottom third          : {b['lower_dwell']:.4f}"
          f"   {'PASS' if b['lower_dwell'] >= 0.15 else 'FAIL'} vs 0.15")
    print(f"  days whose LOW reached the bottom third       : {touched} of {n}")
    print(f"  bar-range top third {b['upper_dwell']:.4f} | middle {b['mid_dwell']:.4f} "
          f"| coverage {b['coverage']:.4f}")

w = df.iloc[483:500]
print("\n  the last 7 days of the judged window, bar by bar (bottom third starts %.2f):" % lo_third)
for i in range(-8, 0):
    r = w.iloc[i]
    print(f"    {w.index[i].date()}  L {r['Low']:.2f}  H {r['High']:.2f}  C {r['Close']:.2f}"
          f"   low in bottom third: {'yes' if r['Low'] <= lo_third else 'no '}"
          f"   close in bottom third: {'yes' if r['Close'] <= lo_third else 'no'}")
