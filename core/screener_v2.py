"""
Main screener pipeline — orchestrates data loading, filtering, consolidation
detection, LPS/breakout signal identification, and scoring.

This module is a pure engine: it returns the ranked results DataFrame plus
the downloaded market data. Output/display concerns live in ``output/``.
"""
from __future__ import annotations

import math
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional, Union

import numpy as np
import pandas as pd

from config import settings
from core.consolidation import find_consolidation
from core.data import fetch_data, get_tickers
from core.indicators import calculate_atr


# ────────────────────────────────────────────────────────────────
# PHASE 1: Universe Baseline Filter
# ────────────────────────────────────────────────────────────────
def _apply_baseline_filters(df: pd.DataFrame) -> Optional[tuple[pd.DataFrame, float]]:
    """
    Enrich the DataFrame with rolling indicators and apply universe-level
    filters (price, volume, trend, yearly return).

    Returns ``(df, yearly_return)`` if the ticker passes, or ``None`` if
    filtered out. yearly_return is returned (not recomputed downstream) so
    the scorer reuses the exact same value the gate used.

    Vol_50 sample timing: this gate samples Vol_50 at the latest bar, while
    `_detect_lps` re-samples at `eval_idx` (offset 0..3 bars back). The
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
# PHASE 3: LPS & Breakout Detection
# ────────────────────────────────────────────────────────────────
def _detect_lps(df: pd.DataFrame, latest: pd.Series,
                sup_avg: float, res_avg: float,
                atr_val: float, base_range_threshold: float,
                base_len: int, swing_complete_idx: int,
                diagnose: bool = False
                ) -> Union[Optional[dict], tuple[Optional[dict], Counter]]:
    """
    Scan backward through recent bars looking for valid LPS formations.

    Strategy rules (aligned with the user's Wyckoff spec):
      - Zone gate: LPS low must sit in one of three zones relative to the box —
        INSIDE (S..R), OVERSHOOT_R (R..R+k*ATR = backtest of breakout),
        or UNDERCUT_S (S-k*ATR..S = spring).
      - Window bound: the LPS must sit inside the consolidation +
        post-breakout reaction window (base_len + AR_MAX_BARS) so we never
        match an LPS that pre-dates the structural box.
      - Staleness cap: pullback depth from the pivot high stays within
        [LPS_DROP_MIN, LPS_DROP_MAX] so we enter close to the last energy
        gain, not after a stretched move.
      - Spread (core): EVERY bar in the LPS formation must be tighter
        than the P-percentile of all bar ranges across the base (default
        median — "price moves less than most bars in consolidation").
        Plus declining spread (last <= prior) if LPS_SPREAD_MUST_DECLINE.
      - Volume (bare minimum): the pullback's average volume must undercut
        the 50-day average at the LPS evaluation bar — that's the only
        volume gate, because real-life dry-up is too noisy to make a core
        signal.

    Candidates are ranked by volume contraction × spread compression.

    diagnose=True returns (best_candidate_or_None, Counter of rejection
    reasons across all (offset, length) tries) — used by the watchlist
    backtest harnesses to explain misses. Live screener calls with
    diagnose=False (default) and gets the same Optional[dict] as before.
    """
    n = len(df)
    candidates: list[dict] = []
    rejects: Counter = Counter()

    # Tight-box zone-tolerance floor. For Phase D launchpads (bw < 0.10),
    # half-ATR can shrink below half-box-height, suffocating a textbook
    # spring/retest. Floor zone_tol at 0.5 * box_height in that regime.
    # Self-gating: wider boxes keep the flat ATR rule (half-box-height would
    # otherwise let the LPS land mid-box).
    box_height = res_avg - sup_avg
    bw = box_height / sup_avg if sup_avg > 0 else 0.0
    if bw < 0.10:
        zone_tol = max(settings.LPS_ZONE_ATR_MULT * atr_val, 0.5 * box_height)
    else:
        zone_tol = settings.LPS_ZONE_ATR_MULT * atr_val
    r_ceiling = res_avg + zone_tol     # OVERSHOOT_R upper bound
    s_floor = sup_avg - zone_tol       # UNDERCUT_S lower bound

    # LPS must land inside the base + reaction window. Without this guard,
    # bumping LPS_SCAN_OFFSET_MAX during backtests could match an LPS that
    # pre-dates the consolidation entirely.
    max_window = base_len + settings.AR_MAX_BARS

    for offset in range(0, settings.LPS_SCAN_OFFSET_MAX):
        end = n - offset
        eval_idx = end - 1

        # Swing-complete gate: the LPS must sit AFTER the swing that
        # established BOTH R and S. Before that bar there is no
        # consolidation yet — only the leg that defined the box.
        if eval_idx <= swing_complete_idx:
            if diagnose: rejects['swing_complete'] += 1
            continue

        for length in range(settings.LPS_LENGTH_MIN, settings.LPS_LENGTH_MAX + 1):
            start = end - length
            if start < 0:
                if diagnose: rejects['start_underflow'] += 1
                continue
            if offset + length > max_window:
                if diagnose: rejects['window_overflow'] += 1
                continue

            pullback_period = df.iloc[start:end]
            end_lps = pullback_period.iloc[-1]

            high_vals = pullback_period['High'].values
            low_vals = pullback_period['Low'].values
            max_high_lps = float(high_vals.max())
            min_low_lps = float(low_vals.min())

            if max_high_lps <= 0:
                if diagnose: rejects['max_high_nonpos'] += 1
                continue

            # Shape gate: window must descend from peak to trough — the
            # highest high must occur AT OR BEFORE the lowest low. Without
            # this, an up-march (each bar a higher high AND higher low)
            # trivially passes drop_pct because the prior end_lps['Low']
            # was the *highest* low, collapsing drop_pct to one bar's
            # intrabar range. Pure shape check, no retest semantic.
            high_idx_in_win = int(np.argmax(high_vals))
            low_idx_in_win = int(np.argmin(low_vals))
            if high_idx_in_win > low_idx_in_win:
                if diagnose: rejects['shape_up_march'] += 1
                continue

            # Zone gate: LPS low must sit in one of the 3 valid zones.
            if min_low_lps < s_floor or min_low_lps > r_ceiling:
                if diagnose: rejects['zone_gate'] += 1
                continue
            if min_low_lps < sup_avg:
                zone_type = "UNDERCUT_S"
            elif min_low_lps > res_avg:
                zone_type = "OVERSHOOT_R"
            else:
                zone_type = "INSIDE"

            drop_pct = (max_high_lps - min_low_lps) / max_high_lps
            if not (settings.LPS_DROP_MIN <= drop_pct <= settings.LPS_DROP_MAX):
                if diagnose: rejects[f'drop_pct({drop_pct:.3f})'] += 1
                continue

            # Spread (core quality): every bar in the formation must be
            # tighter than most base bars — rejects LPS windows that
            # contain a single wild swing bar even if the tail tightens.
            if base_range_threshold <= 0:
                if diagnose: rejects['base_range_nonpos'] += 1
                continue
            if pullback_period['Spread'].max() >= base_range_threshold:
                if diagnose: rejects['spread_quantile'] += 1
                continue
            tight_spread = end_lps['Spread']

            # Declining spread — final bar is no wider than the prior bar.
            if settings.LPS_SPREAD_MUST_DECLINE and length >= 2:
                prev_bar = pullback_period.iloc[-2]
                if tight_spread > prev_bar['Spread']:
                    if diagnose: rejects['spread_decline'] += 1
                    continue

            # Volume: bare-minimum floor — pullback avg volume < max threshold.
            # Vol_50 is sampled at the LPS evaluation bar (not `latest`) so the
            # gate and the score below reference the same denominator.
            vol_50_at_lps = float(df.iloc[eval_idx]['Vol_50'])
            if vol_50_at_lps <= 0:
                if diagnose: rejects['vol50_nonpos'] += 1
                continue
            avg_pullback_vol = pullback_period['Volume'].mean()
            if avg_pullback_vol >= vol_50_at_lps * settings.LPS_VOL_CONTRACTION_MAX:
                if diagnose: rejects['vol_contraction'] += 1
                continue

            if latest['Close'] < (min_low_lps * settings.LPS_HOLD_TOLERANCE):
                if diagnose: rejects['hold_tolerance'] += 1
                continue

            # Post-LPS continuation guard: bars after the LPS evaluation bar
            # must hold above the LPS low and stay tight. Catches cases like
            # MSGM where a tight 2-bar pullback is followed by widening
            # down-bars that turn the formation into another down-leg.
            if offset > 0:
                post_lps = df.iloc[end:n]
                if post_lps['Low'].min() < min_low_lps * settings.LPS_HOLD_TOLERANCE:
                    if diagnose: rejects['post_lps_low_breach'] += 1
                    continue
                if post_lps['Spread'].max() >= base_range_threshold:
                    if diagnose: rejects['post_lps_spread'] += 1
                    continue

            vol_contraction = (vol_50_at_lps - avg_pullback_vol) / vol_50_at_lps
            assert vol_contraction > 0, f"vol_contraction non-positive after gate: {vol_contraction}"
            tightness_ratio = tight_spread / base_range_threshold
            quality = vol_contraction * (1 - tightness_ratio)

            # REBOUND = undercut-support zone (spring); LPS = the other two.
            setup_type = "REBOUND" if zone_type == "UNDERCUT_S" else "LPS"

            candidates.append({
                'length': length,
                'offset': offset,
                'trigger_price': max_high_lps,
                'vol_contraction': vol_contraction,
                'tightness_ratio': tightness_ratio,
                'setup_type': setup_type,
                'zone_type': zone_type,
                '_quality': quality,
            })

    if not candidates:
        return (None, rejects) if diagnose else None

    candidates.sort(key=lambda c: c['_quality'], reverse=True)
    best = candidates[0]
    del best['_quality']
    return (best, rejects) if diagnose else best




# ────────────────────────────────────────────────────────────────
# PHASE 4: Scoring & Tier Assignment
# ────────────────────────────────────────────────────────────────
def _clamp(value: float, cap: float) -> float:
    """Clamp ``value`` into ``[0, cap]``. Used consistently across the scorer."""
    return max(0.0, min(cap, value))


def _score_setup(box_width: float, r_touches: int, s_touches: int,
                 res_avg: float, sup_avg: float, base_df: pd.DataFrame,
                 atr_ratio: float, tightness_ratio: float,
                 vol_contraction: float, base_len: int,
                 yearly_return: float, excess_return: float = 0.0) -> dict:
    """
    Calculate a composite quality score (0–158) from structural metrics.

    Returns a dict with the total score and each sub-score component,
    enabling downstream regression analysis in the setup archive.

    excess_return: stock 6m return − SPY 6m return. Drives the soft RS bonus.
    """
    touches = r_touches + s_touches

    # Box tightness — flat linear scale, removing exponential penalty for wider boxes
    box_tightness_ratio = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
    s_box = _clamp(box_tightness_ratio * settings.SCORE_BOX_TIGHTNESS,
                    settings.SCORE_BOX_TIGHTNESS)

    # Touch density
    base_touch_max = settings.SCORE_TOUCH_DENSITY - settings.TOUCH_BONUS_POINTS
    touch_score = _clamp(touches * 2.0, base_touch_max)
    if (r_touches >= settings.TOUCH_BONUS_INDIVIDUAL and s_touches >= settings.TOUCH_BONUS_INDIVIDUAL) \
       or (touches >= settings.TOUCH_BONUS_TOTAL):
        touch_score += settings.TOUCH_BONUS_POINTS
    s_touch = touch_score

    # Oscillation quality
    midline = (res_avg + sup_avg) / 2
    box_height = res_avg - sup_avg
    osc_ratio = np.mean(np.abs(base_df['Close'] - midline)) / box_height if box_height > 0 else 0.5
    s_osc = _clamp((0.3 - osc_ratio) * (settings.SCORE_OSCILLATION * 5),
                    settings.SCORE_OSCILLATION)

    # ATR squeeze
    s_atr = _clamp((1.0 - atr_ratio) * settings.SCORE_ATR_SQUEEZE,
                    settings.SCORE_ATR_SQUEEZE)

    # LPS candle tightness
    s_lps = _clamp((1 - tightness_ratio) * (settings.SCORE_LPS_TIGHTNESS * 2),
                    settings.SCORE_LPS_TIGHTNESS)

    # Volume contraction
    s_vol = _clamp(vol_contraction * (settings.SCORE_VOL_CONTRACTION * 2),
                    settings.SCORE_VOL_CONTRACTION)

    # Base age — Wyckoff "cause" reward. Sqrt-scaled so very long bases still
    # earn incremental credit past the saturation point without dominating the
    # total: a 30d base earns ~50% of cap, a 60d base ~71%, a 120d base 100%.
    s_age = 0.0
    if base_len > settings.MIN_BASE_DAYS:
        age_factor = math.sqrt(base_len / settings.BASE_AGE_CAP_DAYS)
        s_age = _clamp(age_factor * settings.SCORE_BASE_AGE, settings.SCORE_BASE_AGE)

    # Strong-uptrend bonus — re-accumulation in an established uptrend
    # breaks out more reliably than the same structure on a flat YoY chart.
    # Linear ramp from MIN_STRONG_YEARLY_RETURN to MAX_STRONG_YEARLY_RETURN.
    if yearly_return >= settings.MIN_STRONG_YEARLY_RETURN:
        span = settings.MAX_STRONG_YEARLY_RETURN - settings.MIN_STRONG_YEARLY_RETURN
        progress = min(1.0, (yearly_return - settings.MIN_STRONG_YEARLY_RETURN) / span)
        s_uptrend = progress * settings.SCORE_UPTREND_BONUS
    else:
        s_uptrend = 0.0

    # Soft RS bonus — additive points for outperforming SPY over 6 months.
    # No filter, just leadership reward; saturates at RS_MAX_EXCESS_RETURN.
    if excess_return > 0:
        rs_progress = min(1.0, excess_return / settings.RS_MAX_EXCESS_RETURN)
        s_rs = rs_progress * settings.SCORE_RS_BONUS
    else:
        s_rs = 0.0

    total = round(s_box + s_touch + s_osc + s_atr + s_lps + s_vol + s_age + s_uptrend + s_rs, 1)

    return {
        'total': total,
        'box_tightness': round(s_box, 2),
        'touch_density': round(s_touch, 2),
        'oscillation': round(s_osc, 2),
        'atr_squeeze': round(s_atr, 2),
        'lps_tightness': round(s_lps, 2),
        'vol_contraction': round(s_vol, 2),
        'base_age': round(s_age, 2),
        'uptrend_bonus': round(s_uptrend, 2),
        'rs_bonus': round(s_rs, 2),
    }



def _calculate_tier(score: float) -> str:
    """Map a numeric score to a letter tier grade."""
    if score >= settings.TIER_S:
        return 'S'
    elif score >= settings.TIER_A:
        return 'A'
    elif score >= settings.TIER_B:
        return 'B'
    elif score >= settings.TIER_C:
        return 'C'
    return 'D'


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
        baseline = _apply_baseline_filters(df)
        if baseline is None:
            return None
        df, yearly_return = baseline

        latest = df.iloc[-1]

        df_with_indicators = df.copy()
        df_with_indicators['ATR_10'] = calculate_atr(df_with_indicators, 10)
        df_with_indicators['ATR_50'] = calculate_atr(df_with_indicators, 50)

        # PHASE 2: Consolidation base (extreme-anchored, BC or SC)
        base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
            r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
            is_inner_box = \
            find_consolidation(df_with_indicators, min_days=settings.MIN_BASE_DAYS)

        if base_len == 0:
            return None

        # ATR snapshot at bar -6 aligns with the `:-5` exclusion inside the
        # consolidation detector — the last 5 bars are treated as edge noise
        # and not used for structural regime classification.
        atr_eval = df_with_indicators.iloc[-6]
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
        phase_b_start = len(df_with_indicators) - base_len
        swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)

        lps_result = _detect_lps(
            df_with_indicators, latest, sup_avg, res_avg,
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

        score_result = _score_setup(
            box_width, r_touches, s_touches, res_avg, sup_avg, base_df,
            atr_ratio, tightness_ratio, vol_contraction, base_len, yearly_return,
            excess_return_6m,
        )
        score = score_result['total']
        tier = _calculate_tier(score)

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
            # Base-window endpoints for RS-vs-sector computation in the writer
            # (avoids fetching sector ETF data inside per-ticker workers).
            '_base_close_start': float(base_df['Close'].iloc[0]),
            '_base_close_end': float(base_df['Close'].iloc[-1]),
            '_base_date_start': str(base_df.index[0])[:10],
            '_base_date_end': str(base_df.index[-1])[:10],
        }

    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError) as e:
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

    # Pre-extract per-ticker DataFrames (serializable for worker processes)
    ticker_frames: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
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

    # SPY 6m return — used for the soft RS bonus. Computed once and broadcast
    # to every worker. SPY isn't in the NASDAQ universe so we fetch it standalone.
    spy_6m_return = 0.0
    try:
        import yfinance as yf
        spy_df = yf.download('SPY', period=settings.DOWNLOAD_PERIOD,
                             progress=False, auto_adjust=True, threads=True)
        if not spy_df.empty and len(spy_df) > settings.RS_LOOKBACK_BARS:
            spy_close = spy_df['Close']
            if hasattr(spy_close, 'columns'):
                spy_close = spy_close.iloc[:, 0]
            spy_6m_return = float(
                spy_close.iloc[-1] / spy_close.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0
            )
            print(f"SPY 6m return: {spy_6m_return*100:.2f}% (RS reference)")
    except Exception as e:
        print(f"  [SPY fetch failed: {type(e).__name__}: {e}] — RS bonus disabled this run",
              file=sys.stderr)

    # Market breadth — % of universe with Close > 50d SMA. Observation only.
    breadth_pct = None
    if ticker_frames:
        breadth_count = 0
        breadth_total = 0
        for tdf in ticker_frames.values():
            if len(tdf) >= 50:
                sma_50 = tdf['Close'].rolling(window=50).mean().iloc[-1]
                if pd.notna(sma_50):
                    breadth_total += 1
                    if tdf['Close'].iloc[-1] > sma_50:
                        breadth_count += 1
        if breadth_total > 0:
            breadth_pct = breadth_count / breadth_total
            print(f"Market breadth (Close > SMA_50): {breadth_pct*100:.1f}% "
                  f"({breadth_count}/{breadth_total})")

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
