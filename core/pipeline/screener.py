"""
The Conductor -- runs the whole screen end to end.

This is the piece that knows the order of operations for a scan:

    1. load the ticker universe and market data
    2. prepare one DataFrame per ticker
    3. broadcast market context to worker processes
    4. evaluate tickers in parallel and rank the passing setups

Per-ticker structure/scoring lives in ``core.pipeline.evaluation``. Display and
persistence live further out (``output/`` and ``core.archive``); this module
just returns the ranked DataFrame plus the raw market data.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from config import settings
from core.pipeline.data import fetch_data, get_market_context, get_tickers
from core.pipeline.evaluation import _evaluate_ticker, apply_baseline_filters

__all__ = ["run_screener", "_evaluate_ticker", "apply_baseline_filters"]


def _prepare_ticker_frames(tickers: list[str], data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Extract per-ticker OHLCV frames for worker processes."""
    multi_ticker = len(tickers) > 1
    ticker_frames: dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        if ticker == settings.SPY_SYMBOL:
            continue
        try:
            if multi_ticker:
                if ticker not in data:
                    continue
                df = data[ticker].dropna()
            else:
                df = data.dropna()
            ticker_frames[ticker] = df
        except (KeyError, AttributeError) as e:
            print(f"  [skip {ticker}] extract failed: {type(e).__name__}: {e}",
                  file=sys.stderr)

    return ticker_frames


def _evaluate_frames(ticker_frames: dict[str, pd.DataFrame],
                     spy_6m_return: float,
                     breadth_pct: float | None) -> list[dict]:
    """Run per-ticker evaluation across worker processes with progress output."""
    results: list[dict] = []
    worker_count = min(os.cpu_count() or 4, len(ticker_frames)) if ticker_frames else 1

    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_evaluate_ticker, ticker, df, spy_6m_return, breadth_pct): ticker
            for ticker, df in ticker_frames.items()
        }

        total = len(futures)
        completed = 0
        last_reported = 0
        for future in as_completed(futures):
            completed += 1
            pct = completed / total * 100
            if pct - last_reported >= 2 or completed == total:
                print(f'Evaluating: {pct:.1f}% Complete ({completed}/{total})', flush=True)
                last_reported = pct

            result = future.result()
            if result is not None:
                results.append(result)

    return results


def run_screener() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Execute the full Wyckoff VCP/LPS screening pipeline.

    Returns:
        (results_df, market_data, tickers)
        - results_df: ranked per-ticker setup DataFrame (possibly empty)
        - market_data: raw OHLCV DataFrame used by the dashboard
        - tickers: list of tickers that were evaluated
    """
    tickers = get_tickers()
    data = fetch_data(tickers)
    ticker_frames = _prepare_ticker_frames(tickers, data)

    spy_6m_return, breadth_pct = get_market_context(data, ticker_frames)

    print("\nStarting quantitative scans (V2 - Strict Equilibrium Models)...")
    print(f"Evaluating {len(ticker_frames)} tickers across multiple CPU cores...\n")

    results = _evaluate_frames(ticker_frames, spy_6m_return, breadth_pct)

    print()

    if results:
        results_df = pd.DataFrame(results).sort_values(by='Score', ascending=False)
    else:
        results_df = pd.DataFrame()

    return results_df, data, tickers
