"""Regenerate output/screener_data.json from the CACHED parquet, no network fetch.

Lets you preview the Screener Grid — including the new weekly/monthly HTF context
band on each card — on the existing cache, without running a full (and now 5y)
scan. Read-only on market data; it rewrites the grid JSON the dashboard serves
and may refresh local derived caches such as market_context.json and
output/sector_etf_cache.json. Reuses the real pipeline helpers, so the output
matches a live scan.

    python -m tools.htf_preview
    python -m tools.htf_preview --cache market_data_cache_5y.parquet

A backup of the current screener_data.json is written alongside (.bak) first.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd

from config import settings
from core.pipeline.data import get_market_context
from core.pipeline.screener import (
    _evaluate_frames,
    _prepare_ticker_frames,
    _regime_archive_fields,
)
from output.dashboard import OUTPUT_DIR, generate_dashboard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None,
                    help="parquet path (default: settings.CACHE_FILENAME, with old 2y fallback)")
    a = ap.parse_args()

    path = a.cache or settings.CACHE_FILENAME
    if not os.path.exists(path) and os.path.exists("market_data_cache_2y.parquet"):
        path = "market_data_cache_2y.parquet"
        print(f"(cache {settings.CACHE_FILENAME!r} absent — using {path!r})")
    if not os.path.exists(path):
        print(f"No cache parquet found at {path!r}.")
        return

    data = pd.read_parquet(path, engine=settings.PARQUET_ENGINE)
    tickers = sorted(set(data.columns.get_level_values(0)))
    print(f"Loaded {len(tickers)} tickers from {path}")

    ticker_frames = _prepare_ticker_frames(tickers, data)
    market_context = get_market_context(data, ticker_frames)
    spy_6m = float(market_context.get("spy_6m_return") or 0.0)
    breadth = market_context.get("breadth_pct")

    print(f"Evaluating {len(ticker_frames)} frames...")
    results = _evaluate_frames(ticker_frames, spy_6m, breadth)
    if not results:
        print("No setups fired on this cache.")
        return

    results_df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
    for key, value in _regime_archive_fields(market_context).items():
        results_df[key] = value

    out = os.path.join(OUTPUT_DIR, "screener_data.json")
    if os.path.exists(out):
        shutil.copyfile(out, out + ".bak")
        print(f"Backed up existing grid -> {out}.bak")

    generate_dashboard(results_df, data, tickers, market_context)

    n_w = sum(1 for r in results if r.get("_htf_w_in_consol"))
    n_re = sum(1 for r in results if r.get("_htf_w_reaccum"))
    print(f"Wrote {out}: {len(results)} setups — {n_w} with a weekly HTF box, "
          f"{n_re} flagged weekly re-accumulation. Reload the dashboard to view.")


if __name__ == "__main__":
    main()
