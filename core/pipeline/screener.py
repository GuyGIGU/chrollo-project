"""
The Conductor — runs the whole screen end to end.

This is the only piece that knows the *order of operations*. It wires the
other engines together for each ticker:

    1. apply_baseline_filters  -> is the stock even worth looking at?
    2. core.structure          -> WHERE is the box / LPS, and HOW tight is it?  (measurement)
    3. core.scoring            -> HOW GOOD is it?                                (opinion)
    4. assemble the result row + rank by score

It owns no strategy opinion of its own and draws nothing — it delegates
measurement to ``core.structure`` and grading to ``core.scoring``. Display and
persistence live further out (``output/`` and ``core.archive``); this module
just returns the ranked DataFrame plus the raw market data.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

import pandas as pd

from config import settings
from core.pipeline.data import fetch_data, get_market_context, get_tickers
from core.scoring import calculate_tier, score_setup
from core.structure import (
    calculate_atr,
    detect_lps,
    find_consolidation,
    measure_contractions,
    measure_touch_volume,
)


# ────────────────────────────────────────────────────────────────
# PHASE 1: Universe Baseline Filter
# ────────────────────────────────────────────────────────────────
def apply_baseline_filters(df: pd.DataFrame) -> Optional[tuple[pd.DataFrame, float]]:
    """
    Enrich the DataFrame with rolling indicators and apply universe-level
    filters (price, volume, trend, yearly return).

    Returns ``(df, yearly_return)`` if the ticker passes, or ``None`` if
    filtered out. yearly_return is returned (not recomputed downstream) so
    the scorer reuses the exact same value the gate used.

    Vol_50 sample timing: this gate samples Vol_50 at the latest bar, while
    `detect_lps` re-samples at `eval_idx` (offset 0..3 bars back). The
    values can diverge for low-liquidity tickers; that's intentional so
    each gate has its own consistent denominator.
    """
    if len(df) < 200:
        return None

    df = df.copy()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['Vol_50'] = df['Volume'].rolling(window=50).mean()

    df['Spread'] = df['High'] - df['Low']

    latest = df.iloc[-1]
    one_year_ago_idx = max(0, len(df) - 252)
    one_year_ago = df.iloc[one_year_ago_idx]

    yearly_return = (latest['Close'] - one_year_ago['Close']) / one_year_ago['Close']

    if latest['Close'] < settings.MIN_PRICE: return None
    if latest['Vol_50'] < settings.MIN_VOLUME_50D: return None
    if latest['Close'] < latest['SMA_50']: return None
    if latest['Close'] < latest['SMA_200']: return None
    if yearly_return < settings.MIN_YEARLY_RETURN: return None

    return df, float(yearly_return)


# ────────────────────────────────────────────────────────────────
# Main per-ticker evaluation (used by ProcessPoolExecutor)
# ────────────────────────────────────────────────────────────────
def _evaluate_ticker(ticker: str, df: pd.DataFrame,
                     spy_6m_return: float = 0.0,
                     breadth_pct: Optional[float] = None) -> Optional[dict]:
    """
    Evaluate a single ticker through all screening phases.
    Returns a result dict if the ticker passes, or None if filtered out.
    This is a top-level function so it can be pickled by ProcessPoolExecutor.

    Numeric fields are returned as numbers, not pre-formatted strings, so
    downstream consumers (CSV, dashboard, filters) can sort and compare
    them directly.

    spy_6m_return / breadth_pct are computed once per run by the orchestrator
    and broadcast to every worker (primitives, picklable).
    """
    try:
        # PHASE 1: Universe baseline filter
        baseline = apply_baseline_filters(df)
        if baseline is None:
            return None
        df, yearly_return = baseline

        latest = df.iloc[-1]

        # ATR is computed here (after baseline) so the work parallelizes across
        # ProcessPool workers and is skipped for the ~95% of tickers that fail
        # the baseline filter.
        df['ATR_10'] = calculate_atr(df, 10)
        df['ATR_50'] = calculate_atr(df, 50)

        # PHASE 2: Consolidation base (extreme-anchored, BC or SC)
        base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
            r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
            is_inner_box = \
            find_consolidation(df, min_days=settings.MIN_BASE_DAYS)

        if base_len == 0:
            return None

        # ATR snapshot at bar -6 aligns with the `:-5` exclusion inside the
        # consolidation detector — the last 5 bars are treated as edge noise
        # and not used for structural regime classification.
        atr_eval = df.iloc[-6]
        atr_ratio = atr_eval['ATR_10'] / atr_eval['ATR_50']

        if latest['Close'] < (sup_avg * settings.CRASH_FILTER_MULT):
            return None
        if latest['Close'] >= (res_avg * settings.EXTENSION_FILTER_MULT):
            return None

        # PHASE 3: LPS & Breakout detection
        base_df = df.iloc[-base_len:]

        # Spread-quality reference: P-percentile of all bar ranges in the base.
        # LPS bar range must sit below this (i.e., "tighter than most base bars").
        # Floored at 1.2 * ATR — for tight inner boxes the 50%ile spread can
        # be smaller than a normal-volatility bar, which means a single
        # ATR-sized bar in the LPS window kills detection. Self-gates: bases
        # with chronically wide bars still bind on the percentile.
        atr_for_zone = float(atr_eval['ATR_10'])
        base_range_threshold = max(
            float(base_df['Spread'].quantile(settings.LPS_RANGE_PERCENTILE)),
            1.2 * atr_for_zone,
        )

        # Translate the eq_df-relative anchor positions returned by
        # find_consolidation into df-positional indices so the LPS gate
        # can compare against `eval_idx`. (Dashboard/archive consumers keep
        # using the unconverted, base-relative anchor values via _r/_s_anchor_bar.)
        phase_b_start = len(df) - base_len
        swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)

        lps_result = detect_lps(
            df, latest, sup_avg, res_avg,
            atr_for_zone, base_range_threshold, base_len, swing_complete_idx,
        )

        if not lps_result:
            return None

        setup_state = lps_result['setup_type']
        is_lps = True
        lps_length = lps_result['length']
        lps_offset = lps_result['offset']
        trigger_price = lps_result['trigger_price']
        vol_contraction = lps_result['vol_contraction']
        tightness_ratio = lps_result['tightness_ratio']

        # PHASE 4: Scoring & tier assignment
        current_price = latest['Close']
        distance_to_trigger = (trigger_price - current_price) / current_price

        # Price must still be below trigger (room to run)
        if distance_to_trigger <= 0:
            return None

        # Distance from 52-week high — Wyckoff bases near recent highs are
        # statistically the ones that hold their breakouts. Negative number
        # (e.g. -0.07 = 7% below the 52w high).
        last_252 = df['High'].iloc[-min(252, len(df)):]
        max_252 = float(last_252.max()) if len(last_252) else 0.0
        dist_52w_high_pct = (
            (float(current_price) - max_252) / max_252 if max_252 > 0 else None
        )

        # Soft RS — stock 6m return − SPY 6m return. Bonus only, no filter.
        rs_lookback = settings.RS_LOOKBACK_BARS
        if len(df) > rs_lookback:
            stock_6m_return = (float(current_price) / float(df['Close'].iloc[-rs_lookback - 1]) - 1.0)
        else:
            stock_6m_return = 0.0
        excess_return_6m = stock_6m_return - spy_6m_return

        # Volume signature at R/S touch bars — measured by the structure engine.
        # r_touch_vol_z < 0 -> "No Supply"; r_touch_vol_z > 0 -> heavy resistance
        # (warning); s_touch_vol_z > 0 -> "Demand at S". Stored as underscore-
        # prefixed fields -> archive columns -> tag chips.
        r_touch_vol_z, s_touch_vol_z = measure_touch_volume(
            base_df, res_avg, sup_avg, atr_for_zone
        )

        # VCP progressive-contraction footprint over the base window.
        contraction = measure_contractions(base_df)

        score_result = score_setup(
            box_width, r_touches, s_touches, res_avg, sup_avg, base_df,
            atr_ratio, tightness_ratio, vol_contraction, base_len, yearly_return,
            excess_return_6m, dist_52w_high_pct, breadth_pct,
            contraction['quality'],
        )
        score = score_result['total']
        tier = calculate_tier(score)

        return {
            'Ticker': ticker,
            'Tier': tier,
            'Setup': setup_state,
            'Score': score,
            'Current Price': round(float(current_price), 2),

            # Raw numerics — downstream can filter/sort and format as needed.
            'Base Len': int(base_len),
            'Box Width': float(box_width),
            'Touches': int(r_touches + s_touches),
            'ATR Ratio': float(atr_ratio),
            'LPS Length': int(lps_length),
            'Breach Days': int(breach_days),

            # Archive fields — structural detail for regression
            '_r_touches': int(r_touches),
            '_s_touches': int(s_touches),
            '_vol_contraction': float(vol_contraction),
            '_tightness_ratio': float(tightness_ratio),
            '_trigger_price': float(trigger_price),

            # Sub-scores (for archive decomposition)
            '_sub_scores': score_result,

            # Internal chart data (not displayed in terminal)
            '_R': float(res_avg),
            '_S': float(sup_avg),
            '_base_len': int(base_len),
            '_lps_len': int(lps_length),
            '_lps_offset': int(lps_offset),
            '_r_anchor_bar': int(r_anchor_bar),
            '_s_anchor_bar': int(s_anchor_bar),

            # E4 — structural detail for regression analysis
            '_bars_since_BC': int(len(df) - bc_anchor_bar),
            '_descent_length': int(phase_b_start_bar - bc_anchor_bar),
            # Phase D launchpad flag — True when the inner sub-box detector
            # replaced the outer BC→AR box, False when the outer was kept.
            '_phase_d_inner': bool(is_inner_box),

            # Trader-facing context metrics (persisted to archive)
            '_dist_52w_high_pct': float(dist_52w_high_pct) if dist_52w_high_pct is not None else None,
            '_excess_return_6m': float(excess_return_6m),
            '_breadth_pct': float(breadth_pct) if breadth_pct is not None else None,
            '_r_touch_vol_z': r_touch_vol_z,
            '_s_touch_vol_z': s_touch_vol_z,
            '_lps_descent_frac': float(lps_result.get('descent_frac', 1.0)),
            '_lps_zone_type': lps_result.get('zone_type', 'INSIDE'),
            # VCP progressive-contraction footprint
            '_contraction_count': int(contraction['n_contractions']),
            '_contraction_quality': float(contraction['quality']),
            '_final_contraction_depth': (float(contraction['final_depth'])
                                         if contraction['final_depth'] is not None else None),
            # Base-window endpoints for RS-vs-sector computation in the writer
            # (avoids fetching sector ETF data inside per-ticker workers).
            '_base_close_start': float(base_df['Close'].iloc[0]),
            '_base_close_end': float(base_df['Close'].iloc[-1]),
            '_base_date_start': str(base_df.index[0])[:10],
            '_base_date_end': str(base_df.index[-1])[:10],
        }

    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError, AttributeError) as e:
        # Log and drop so a single malformed ticker doesn't abort the batch,
        # but still surfaces real bugs instead of silently hiding them.
        print(f"  [skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)
        return None


# ────────────────────────────────────────────────────────────────
# Pipeline orchestrator
# ────────────────────────────────────────────────────────────────
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

    multi_ticker = len(tickers) > 1

    # Pre-extract per-ticker DataFrames (serializable for worker processes).
    # ATR is computed inside each worker after the baseline filter — pushing
    # that O(n) EWM work into the ProcessPool keeps the main thread off the
    # critical path and skips it entirely for tickers that fail baseline.
    # SPY lives in the parquet alongside the universe but is never screened.
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
            continue

    # Market context — SPY 6m return + breadth. Cached in a JSON sidecar
    # next to the parquet; SPY data itself rides in the same parquet.
    spy_6m_return, breadth_pct = get_market_context(data, ticker_frames)

    print("\nStarting quantitative scans (V2 - Strict Equilibrium Models)...")
    print(f"Evaluating {len(ticker_frames)} tickers across multiple CPU cores...\n")

    results: list[dict] = []
    completed = 0
    worker_count = min(os.cpu_count() or 4, len(ticker_frames)) if ticker_frames else 1

    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_evaluate_ticker, ticker, df, spy_6m_return, breadth_pct): ticker
            for ticker, df in ticker_frames.items()
        }

        total = len(futures)
        last_reported = 0
        for future in as_completed(futures):
            completed += 1
            pct = completed / total * 100
            # Throttle SSE: report every ~2% or on the very last ticker
            if pct - last_reported >= 2 or completed == total:
                print(f'Evaluating: {pct:.1f}% Complete ({completed}/{total})', flush=True)
                last_reported = pct

            result = future.result()
            if result is not None:
                results.append(result)

    print()  # Newline after progress bar

    if results:
        results_df = pd.DataFrame(results).sort_values(by='Score', ascending=False)
    else:
        results_df = pd.DataFrame()

    return results_df, data, tickers
