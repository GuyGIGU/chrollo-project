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
from core.pipeline.cache import _cache_paths
from core.pipeline.data import get_market_context, get_provider, get_tickers
from core.pipeline.evaluation import _evaluate_ticker, apply_baseline_filters
from core.pipeline.market_data_health import (
    compute_market_data_health,
    eligible_tickers_for,
)
from core.pipeline.scan_metrics import ScanTimer, format_scan_metrics, persist_scan_metrics
from core.pipeline.tickers import get_cached_tickers
from core.pipeline.universe import resolve_universe

__all__ = ["CachedMarketDataError", "run_screener", "_evaluate_ticker", "apply_baseline_filters"]


class CachedMarketDataError(RuntimeError):
    """Raised when cached evaluation cannot safely use the local market-data panel."""


def _prepare_ticker_frames(tickers: list[str], data: pd.DataFrame,
                           universe=None) -> dict[str, pd.DataFrame]:
    """Extract per-ticker OHLCV frames for worker processes."""
    multi_ticker = len(tickers) > 1
    index_symbols = set(resolve_universe(universe).index_symbols)
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


def _read_cached_market_data(tickers: list[str], universe=None) -> pd.DataFrame:
    cache_file, meta_file = _cache_paths(universe)
    if not os.path.exists(cache_file):
        raise CachedMarketDataError(f"stale market data: cache file not found at {cache_file}")

    print(f"Loading market data from local cache for evaluation: {cache_file}", flush=True)
    data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
    if hasattr(data.index, 'tz') and data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    health = compute_market_data_health(data, tickers, meta_file=meta_file)
    if not health["can_evaluate"]:
        raise CachedMarketDataError(f"stale market data: {health['diagnosis']}")
    if health["coverage"]["raw"]["ratio"] < health["coverage"]["eligible"]["ratio"]:
        print(f"Cached market-data health: {health['diagnosis']}", flush=True)
    return data


def run_screener(mode: str = "download",
                 universe=None) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    """
    Execute the full Wyckoff VCP/LPS screening pipeline.

    ``universe`` selects which market to scan (a :class:`Universe`, a key string,
    or ``None`` for US-Stocks). The default resolves to the exact current ticker
    source / cache / index set, so the US-Stocks run is byte-identical.

    Returns:
        (results_df, market_data, tickers, market_context)
        - results_df: ranked per-ticker setup DataFrame (possibly empty)
        - market_data: raw OHLCV DataFrame used by the dashboard
        - tickers: list of tickers that were evaluated
        - market_context: run-level context for dashboard/archive
    """
    if mode not in {"download", "cache"}:
        raise ValueError(f"unknown screener data mode: {mode}")

    uni = resolve_universe(universe)

    timer = ScanTimer()
    with timer.phase("ticker_universe"):
        if uni.ticker_source == "csv":
            # Curated universes (sector / commodity ETFs) read their fixed list
            # directly — never the NASDAQ FTP pull or the young/dead admission gate.
            tickers = get_cached_tickers(uni.ticker_csv)
        else:
            tickers = get_cached_tickers(uni.ticker_csv) if mode == "cache" else get_tickers(uni.ticker_csv)
    with timer.phase("market_data_fetch"):
        data = _read_cached_market_data(tickers, uni) if mode == "cache" else get_provider().fetch(tickers)
    with timer.phase("frame_prep"):
        evaluation_tickers = eligible_tickers_for(tickers)
        skipped = len(tickers) - len(evaluation_tickers)
        if skipped > 0:
            print(f"Evaluating eligible cache universe ({len(evaluation_tickers)} tickers; skipped {skipped}).",
                  flush=True)
        ticker_frames = _prepare_ticker_frames(evaluation_tickers, data, uni)

    with timer.phase("market_context"):
        market_context = get_market_context(data, ticker_frames, uni)
    spy_6m_return = float(market_context.get('spy_6m_return') or 0.0)
    breadth_pct = market_context.get('breadth_pct')

    print("\nStarting quantitative scans (V2 - Strict Equilibrium Models)...")
    print(f"Evaluating {len(ticker_frames)} tickers across multiple CPU cores...\n")

    with timer.phase("evaluation"):
        results = _evaluate_frames(ticker_frames, spy_6m_return, breadth_pct)

    # Universe-level ADVISORY post-pass: turn each firing setup's trailing return
    # into a universe-relative in-house RS rating (percentile across the firing
    # set). No-op + zero added fields when FUNDAMENTALS_ENABLED is OFF, so the
    # flags-OFF scan output stays byte-identical. Never changes Score/Tier.
    from core.regime.scan_context import attach_rs_ratings
    attach_rs_ratings(results)

    print()

    if results:
        with timer.phase("result_assembly"):
            results_df = pd.DataFrame(results).sort_values(by='Score', ascending=False)
            for key, value in _regime_archive_fields(market_context).items():
                results_df[key] = value
    else:
        results_df = pd.DataFrame()

    metrics = timer.finish(
        universe_tickers=len(tickers),
        evaluated_tickers=len(ticker_frames),
        setups=len(results_df),
    )
    market_context["_scan_metrics"] = metrics
    persist_scan_metrics(metrics)
    print(format_scan_metrics(metrics), flush=True)

    return results_df, data, evaluation_tickers, market_context
