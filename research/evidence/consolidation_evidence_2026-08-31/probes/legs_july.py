import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd, numpy as np
from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.evaluation import apply_baseline_filters

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
raw = d["EGBN"].dropna(); raw = raw[raw.index <= pd.Timestamp("2026-01-07")]
df, _ = apply_baseline_filters(raw.copy())
df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
df["ATR_10"] = calculate_atr(df, 10); df["ATR_50"] = calculate_atr(df, 50)
R, S = 21.64, 20.49
lo_top, up_bot = S + (R - S) / 3, S + 2 * (R - S) / 3

for n in (17, 22):
    w = df.iloc[483:483+n]
    H, L, C = w["High"].values, w["Low"].values, w["Close"].values
    pos = np.clip((C - S) / (R - S), 0, 1)
    print(f"\n{n}-day window  (bottom third <= {lo_top:.2f}, top third >= {up_bot:.2f})")
    print(f"  lower  close-basis {np.mean(pos <= 1/3):.4f}   bar-basis {np.mean(L <= lo_top):.4f}   floor 0.15")
    print(f"  upper  close-basis {np.mean(pos >= 2/3):.4f}   bar-basis {np.mean(H >= up_bot):.4f}   floor 0.15")
    interior = (L > lo_top) & (H < up_bot)
    print(f"  mid    close-basis {np.mean((pos>1/3)&(pos<2/3)):.4f}   bar-basis {np.mean(interior):.4f}   cap  0.45")
