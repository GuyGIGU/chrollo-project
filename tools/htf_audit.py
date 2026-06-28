"""HTF context audit — eyeball the weekly/monthly structure read for a ticker.

Read-only. For each ticker it loads the live parquet cache, runs the DAILY read
(trimmed to DAILY_STRUCTURE_PERIOD, exactly as the screener will) for the nesting
box, then resamples to weekly + monthly and runs the same calibrated bricks under
the timeframe window override — printing Stage-2 trend, the worked box + phase,
the re-accumulation flag, and how the box maps to dates so it can be compared to a
TradingView chart. This is the calibration instrument for the HTF window presets.

    python -m tools.htf_audit NVDA AAPL AMD            # today
    python -m tools.htf_audit NVDA --as-of 2026-03-30  # historical
    python -m tools.htf_audit NVDA --cache market_data_cache_5y.parquet
"""
from __future__ import annotations

import argparse
import os

try:  # works under both `python -m tools.htf_audit` and `python tools/htf_audit.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

configure_path()

import pandas as pd

from config import settings
from core.pipeline.downloads import _trim_to_period
from core.pipeline.evaluation import apply_baseline_filters
from core.structure import htf
from core.structure.indicators import calculate_atr
from core.structure.narrative import read_structure

DEFAULT = ["NVDA", "AAPL", "MSFT", "AMD", "AVGO", "SPY"]


def _bar_date(df, bar) -> str:
    try:
        b = int(bar)
    except (TypeError, ValueError):
        return "   -    "
    if b < 0 or b >= len(df):
        return f"#{b}?"
    idx = df.index[b]
    d = getattr(idx, "date", None)
    return d().isoformat() if callable(d) else str(idx)[:10]


def _daily_box(raw: pd.DataFrame):
    """The firing daily (R, S) for the nesting test — None if no daily structure."""
    base = apply_baseline_filters(raw.copy())
    if base is None:
        return None
    df, _ = base
    df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD)
    if len(df) < 6:
        return None
    df = df.copy()
    df["ATR_10"] = calculate_atr(df, 10)
    s = read_structure(df, float(df["ATR_10"].iloc[-6]))
    return (float(s.R), float(s.S)) if s is not None else None


def _audit_tf(raw: pd.DataFrame, tf: str, daily_box):
    htf_df = htf.resample_ohlc(raw, tf)
    if htf_df is None:
        print(f"  {tf:<7}: no resampled frame")
        return
    work = htf_df.copy()
    work["ATR_10"] = calculate_atr(work, 10)
    work["Vol_50"] = work["Volume"].rolling(50, min_periods=1).mean()
    work["Spread"] = work["High"] - work["Low"]
    stage = htf.htf_stage2(work)
    ctx = htf.read_htf_context(raw, tf, daily_box=daily_box)
    p = htf._PREFIX[tf]

    detail = ""
    if len(work) >= 2:
        atr = float(work["ATR_10"].iloc[-2])
        if atr > 0:
            with htf.timeframe_windows(tf):
                s = htf._read_htf_structure(work, atr)
            if s is not None:
                box, root = s["box"], s["root"]
                detail = (f"  | root {_bar_date(work, root.climax_bar)}->"
                          f"{_bar_date(work, root.ar_bar)}  box@{_bar_date(work, box.start_bar)}"
                          f"  spring={'Y' if s['spring'] else 'N'} lps={'Y' if s['lps'] else 'N'}")

    print(f"  {tf:<7}({len(htf_df):>3} bars): stage2={str(stage['stage2']):<5} {stage['trend_state']:<7}"
          f" | in_consol={str(ctx[p+'in_consol']):<5} phase={str(ctx[p+'phase']):<4}"
          f" | box R={ctx[p+'box_r']} S={ctx[p+'box_s']} w={ctx[p+'box_width']}"
          f" | reaccum={str(ctx[p+'reaccum']):<5} nested={ctx[p+'daily_nested']}{detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", help="tickers (default: a liquid sample)")
    ap.add_argument("--as-of", default=None, metavar="YYYY-MM-DD")
    ap.add_argument("--cache", default=None, help="parquet path (default: settings, with 2y fallback)")
    a = ap.parse_args()

    path = a.cache or settings.CACHE_FILENAME
    if not os.path.exists(path) and os.path.exists("market_data_cache_2y.parquet"):
        path = "market_data_cache_2y.parquet"
        print(f"(cache {settings.CACHE_FILENAME!r} absent — falling back to {path!r})")
    d = pd.read_parquet(path, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))
    tickers = [t.upper() for t in a.tickers] or DEFAULT

    for t in tickers:
        print("=" * 100)
        if t not in level0:
            print(f"{t}: not in cache")
            continue
        raw = d[t].dropna()
        if a.as_of:
            raw = raw[raw.index <= pd.Timestamp(a.as_of)]
        if len(raw) == 0:
            print(f"{t}: no rows")
            continue
        dbox = _daily_box(raw)
        dbox_s = f"R={dbox[0]:.2f} S={dbox[1]:.2f}" if dbox else "none"
        print(f"{t}  (daily bars {len(raw)}, last {_bar_date(raw, len(raw)-1)})  daily box: {dbox_s}")
        _audit_tf(raw, "weekly", dbox)
        _audit_tf(raw, "monthly", dbox)
    print("=" * 100)


if __name__ == "__main__":
    main()
