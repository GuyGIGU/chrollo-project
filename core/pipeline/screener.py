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
    index_symbols = set(getattr(settings, 'INDEX_SYMBOLS', [settings.SPY_SYMBOL]))
    ticker_frames: dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        if ticker in index_symbols:
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


def _regime_archive_fields(market_context: dict) -> dict:
    regime = market_context.get('regime') or {}
    indexes = regime.get('indexes') or {}
    spy = indexes.get(settings.SPY_SYMBOL) or {}
    qqq = indexes.get('QQQ') or {}
    return {
        '_regime_state': regime.get('state'),
        '_regime_breadth_50_pct': regime.get('breadth_50_pct'),
        '_regime_breadth_200_pct': regime.get('breadth_200_pct'),
        '_regime_distribution_days': regime.get('distribution_days'),
        '_regime_spy_above_50': spy.get('above_sma_50'),
        '_regime_spy_above_200': spy.get('above_sma_200'),
        '_regime_spy_50d_slope_pct': spy.get('sma_50_slope_pct'),
        '_regime_qqq_above_50': qqq.get('above_sma_50'),
        '_regime_qqq_above_200': qqq.get('above_sma_200'),
        '_regime_qqq_50d_slope_pct': qqq.get('sma_50_slope_pct'),
    }


def run_screener() -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    """
    Execute the full Wyckoff VCP/LPS screening pipeline.

    Returns:
        (results_df, market_data, tickers, market_context)
        - results_df: ranked per-ticker setup DataFrame (possibly empty)
        - market_data: raw OHLCV DataFrame used by the dashboard
        - tickers: list of tickers that were evaluated
        - market_context: run-level context for dashboard/archive
    """
    tickers = get_tickers()
    data = fetch_data(tickers)
    ticker_frames = _prepare_ticker_frames(tickers, data)

    market_context = get_market_context(data, ticker_frames)
    spy_6m_return = float(market_context.get('spy_6m_return') or 0.0)
    breadth_pct = market_context.get('breadth_pct')

    print("\nStarting quantitative scans (V2 - Strict Equilibrium Models)...")
    print(f"Evaluating {len(ticker_frames)} tickers across multiple CPU cores...\n")

    results = _evaluate_frames(ticker_frames, spy_6m_return, breadth_pct)

    print()

    if results:
        results_df = pd.DataFrame(results).sort_values(by='Score', ascending=False)
        for key, value in _regime_archive_fields(market_context).items():
            results_df[key] = value
    else:
        results_df = pd.DataFrame()

    return results_df, data, tickers, market_context
