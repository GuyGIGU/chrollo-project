"""
The Conductor -- runs the whole screen end to end.

This is the piece that knows the order of operations for a scan:

    1. load the ticker universe and market data
    2. prepare one DataFrame per ticker
    3. broadcast market context to worker processes
    4. evaluate tickers in parallel and rank the passing setups

Per-ticker structure/scoring lives in ``engine_alpha.evaluation``. Display and
persistence live further out (``output/`` and ``core.archive``); this module
just returns the ranked DataFrame plus the raw market data.
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial

import pandas as pd

from config import settings
from core.pipeline.cache import _cache_paths
from core.pipeline.data import get_market_context, get_provider, get_tickers
from engine_alpha.evaluation import (
    EVAL_ERROR,
    _evaluate_ticker,
    apply_baseline_filters,
    evaluate_ticker_with_near_miss,
    evaluate_ticker_with_watch,
)
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
                     breadth_pct: float | None,
                     near_miss_sink: dict | None = None,
                     watch_sink: dict | None = None) -> tuple[list[dict], int]:
    """Run per-ticker evaluation across worker processes with progress output.

    ``near_miss_sink``: optional ``{"rows": [], "stats": {}}`` collector for
    the refusal lane. When given AND ``NEAR_MISS_LANE_ENABLED`` is on (read
    lazily at call time), workers run the lane-carrying evaluation twin and
    the deduped ruled rows + counters accumulate here; otherwise the exact
    legacy submission runs (flag-off stays byte-identical and sink-empty).

    ``watch_sink``: the watch lane's ``{"rows": [], "stats": {}}`` (build step
    8, ``LPS_LEAVES_ELECTION_ENABLED``): its twin wraps whatever rung the ladder
    picked, so the state word is typed off the one paying read.

    Returns ``(results, errored)`` where ``errored`` is the number of tickers
    whose eval chain THREW (and was swallowed by the skip-guard) — distinct from a
    structural reject (``None``). Both are dropped from ``results`` identically;
    only the error count is tracked separately, returned in-band so there is no
    stale-read hazard across calls.
    """
    results: list[dict] = []
    errored = 0
    worker_count = min(os.cpu_count() or 4, len(ticker_frames)) if ticker_frames else 1

    lane_on = near_miss_sink is not None and settings.NEAR_MISS_LANE_ENABLED
    worker_fn = evaluate_ticker_with_near_miss if lane_on else _evaluate_ticker
    watch_on = watch_sink is not None and settings.LPS_LEAVES_ELECTION_ENABLED
    if watch_on:
        worker_fn = partial(evaluate_ticker_with_watch, inner=worker_fn)

    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(worker_fn, ticker, df, spy_6m_return, breadth_pct): ticker
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
            if watch_on:
                result, watch_row, watch_stats = result
                if watch_row is not None:
                    watch_sink["rows"].append(watch_row)
                wstats = watch_sink.setdefault("stats", {})
                for k, v in watch_stats.items():
                    wstats[k] = wstats.get(k, 0) + v
            if lane_on:
                result, lane_rows, lane_stats = result
                near_miss_sink["rows"].extend(lane_rows)
                stats = near_miss_sink.setdefault("stats", {})
                for k, v in lane_stats.items():
                    stats[k] = stats.get(k, 0) + v
            if result is EVAL_ERROR:
                # Swallowed eval crash — NOT a structural reject. Counted, not appended.
                errored += 1
            elif result is not None:
                results.append(result)

    return results, errored


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

    # Regime guard (mirrors fetch_data): cache-mode evaluation must never feed
    # the engine an old-regime panel — the archive would stamp rows with a
    # manifest hash claiming the new regime over data from the old one.
    from core.pipeline.cache import _read_meta  # noqa: PLC0415 — lazy, matches module style
    from core.pipeline.downloads import _meta_regime_mismatch, _price_regime  # noqa: PLC0415
    meta = _read_meta(meta_file)
    if _meta_regime_mismatch(meta):
        raise CachedMarketDataError(
            "stale market data: cache price-series regime "
            f"({meta.get('price_series', 'div_adjusted')}) differs from settings "
            f"({_price_regime()}); run a download scan to rebuild the cache")

    print(f"Loading market data from local cache for evaluation: {cache_file}", flush=True)
    data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
    if hasattr(data.index, 'tz') and data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    health = compute_market_data_health(
        data, tickers, meta_file=meta_file,
        index_symbols=list(resolve_universe(universe).index_symbols),
    )
    if not health["can_evaluate"]:
        raise CachedMarketDataError(f"stale market data: {health['diagnosis']}")
    if health["coverage"]["raw"]["ratio"] < health["coverage"]["eligible"]["ratio"]:
        print(f"Cached market-data health: {health['diagnosis']}", flush=True)
    return data


def run_screener(mode: str = "download",
                 universe=None,
                 near_miss_sink: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    """
    Execute the full Wyckoff VCP/LPS screening pipeline.

    ``universe`` selects which market to scan (a :class:`Universe`, a key string,
    or ``None`` for US-Stocks). The default resolves to the exact current ticker
    source / cache / index set, so the US-Stocks run is byte-identical.

    ``near_miss_sink``: optional ``{"rows": [], "stats": {}}`` collector the
    refusal lane fills when ``NEAR_MISS_LANE_ENABLED`` is on (scan_job passes
    one and hands the rows to the cohort writer behind the SAME archive
    freshness gate as the fires; no sink or flag off = untouched legacy path).

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
        data = _read_cached_market_data(tickers, uni) if mode == "cache" else get_provider().fetch(tickers, uni)
    with timer.phase("frame_prep"):
        # Judge eligibility against THIS universe's own admission/quarantine ledger
        # and regime set — not the US-Stocks ledger (the universe-blind bug ⑥).
        _, meta_file = _cache_paths(uni)
        evaluation_tickers = eligible_tickers_for(
            tickers, meta_file=meta_file, index_symbols=list(uni.index_symbols)
        )
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

    # The watch lane's sink (build step 8): rows and counts ride the payload
    # through market_context["watch"]; absent flag-off (byte-identical).
    watch_sink = ({"rows": [], "stats": {}}
                  if settings.LPS_LEAVES_ELECTION_ENABLED else None)
    with timer.phase("evaluation"):
        # Number of tickers whose eval chain THREW and was swallowed (distinct from
        # a structural reject) is returned in-band alongside the results, so there
        # is no cross-call stale-read hazard.
        # The watch sink rides as a kwarg only when it exists (flag-on), so an
        # injected fake without the parameter keeps working flag-off (the
        # near-miss floor's own rule).
        watch_kw = {"watch_sink": watch_sink} if watch_sink is not None else {}
        results, errored_tickers = _evaluate_frames(ticker_frames, spy_6m_return,
                                                    breadth_pct,
                                                    near_miss_sink=near_miss_sink,
                                                    **watch_kw)
    if watch_sink is not None:
        market_context["watch"] = {
            "candidates": sorted(watch_sink["rows"], key=lambda r: r["ticker"]),
            "counts": {k: int(v) for k, v in sorted(watch_sink["stats"].items())},
        }

    # Conductor-level fundamentals/RS-line post-pass (species program Task 12):
    # ONE process, the provider's one throttle, the FIRING set only — the
    # in-worker attach point is retired. None when every advisory flag is off
    # (byte-identical scans); else the attempted-vs-populated counters ride the
    # scan metrics (the health surface) and the structured result line. The
    # phase records ONLY when the pass ran — a dark scan's persisted metrics
    # stay byte-identical (EC-8; 2026-08-17 review, Ramírez) — and the
    # passenger gets its own narrow seam catch (EC-20/21): a pass-level crash
    # surfaces as a counter on the health surface, never as the scan night.
    from core.fundamentals.post_pass import attach_fundamentals_post_pass
    t0_fund = time.perf_counter()
    try:
        fundamentals_counts = attach_fundamentals_post_pass(results, ticker_frames)
    except Exception as e:  # noqa: BLE001 — the passenger never owns the job
        print(f"  [fundamentals post-pass errored] {type(e).__name__}: {e}",
              file=sys.stderr)
        fundamentals_counts = {"pass_errored": 1}
    if fundamentals_counts is not None:
        timer.phases["fundamentals"] = round(time.perf_counter() - t0_fund, 2)
        market_context["fundamentals"] = fundamentals_counts

    # Universe-level ADVISORY post-pass: turn each firing setup's trailing return
    # into a universe-relative in-house RS rating (percentile across the firing
    # set). No-op + zero added fields when FUNDAMENTALS_ENABLED is OFF, so the
    # flags-OFF scan output stays byte-identical. Never changes Score/Tier.
    from core.regime.scan_context import attach_rs_ratings
    attach_rs_ratings(results)

    print()

    if results:
        with timer.phase("result_assembly"):
            # RANK BY THE GRADE (council 2026-08-22, three seats independently):
            # the tier badge and the lens number derive from ta_grade, so the
            # ordering must come from the same verdict — ranking by the legacy
            # raw sum survived the 2026-08-09 flip only because every
            # divergence knob was still neutral. Tiebreak: the raw sum (still
            # stamped as an archived fact), then ticker for determinism.
            results_df = pd.DataFrame(results).sort_values(
                by=['_ta_grade', 'Score', 'Ticker'],
                ascending=[False, False, True])
            for key, value in _regime_archive_fields(market_context).items():
                results_df[key] = value
    else:
        results_df = pd.DataFrame()

    # ``errored_tickers`` is included in counts ONLY when non-zero so a clean scan's
    # counts stay byte-identical to before (the common case, and what the metrics
    # shape test pins); a swallowed eval crash surfaces the count for the alerting
    # decision and the operator-visible formatter.
    finish_counts = dict(
        universe_tickers=len(tickers),
        evaluated_tickers=len(ticker_frames),
        setups=len(results_df),
    )
    if errored_tickers:
        finish_counts["errored_tickers"] = errored_tickers
    if fundamentals_counts is not None:
        # The attempted-vs-populated alarm rides the health surface: "flag
        # off" = key absent; "attempted, all failed" = populated 0, visibly.
        finish_counts["fundamentals"] = fundamentals_counts
    metrics = timer.finish(**finish_counts)
    market_context["_scan_metrics"] = metrics
    persist_scan_metrics(metrics, universe=uni)
    print(format_scan_metrics(metrics), flush=True)

    return results_df, data, evaluation_tickers, market_context
