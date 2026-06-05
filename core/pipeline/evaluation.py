"""Per-ticker evaluation pass for the screener pipeline."""
from __future__ import annotations

import sys
from typing import Optional

import pandas as pd

from config import settings
from core.scoring import calculate_tier, score_setup
from core.structure import (
    adr_pct,
    calculate_atr,
    detect_lps,
    find_consolidation,
    measure_bar_compression,
    measure_bins,
    measure_contractions,
    measure_support_slope,
    measure_touch_volume,
    scope_consolidation,
    trend_template,
)
from core.structure.segmentation import segment_swings

# Lead-in window (bars before the detected base) searched for the trend->range
# root swing when reconnecting a drifted BC anchor (see _evaluate_ticker).
_SEG_LEAD_IN = 60
# How close the root swing's AR (its end) must land to the detected base start
# to count as the descent INTO this base.
_SEG_AR_TOL = 10


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


def _reconnect_bc_anchor(df, atr_for_zone, base_len, phase_b_start_bar, bc_anchor_bar):
    """Reconnect a drifted BC anchor to the recent trend->range bridge."""
    phase_b_start = len(df) - base_len
    seg = segment_swings(df, atr_for_zone, lookback=base_len + _SEG_LEAD_IN)
    dom = seg.get("dominant_direction", 0)
    bridge = None
    if dom != 0:
        for swing in seg.get("swings", []):
            if (swing["direction"] == -dom
                    and abs(swing["end_bar"] - phase_b_start_bar) <= _SEG_AR_TOL
                    and phase_b_start_bar - _SEG_LEAD_IN <= swing["start_bar"] < phase_b_start_bar):
                if bridge is None or swing["abs_disp_atr"] > bridge["abs_disp_atr"]:
                    bridge = swing
    if bridge is not None:
        return bridge["start_bar"]
    return bc_anchor_bar


def _evaluate_ticker(ticker: str, df: pd.DataFrame,
                     spy_6m_return: float = 0.0,
                     breadth_pct: Optional[float] = None,
                     select: str = "earliest") -> Optional[dict]:
    """
    Evaluate a single ticker through all screening phases.
    Returns a result dict if the ticker passes, or None if filtered out.
    This is a top-level function so it can be pickled by ProcessPoolExecutor.
    """
    try:
        baseline = apply_baseline_filters(df)
        if baseline is None:
            return None
        df, yearly_return = baseline

        latest = df.iloc[-1]

        df['ATR_10'] = calculate_atr(df, 10)
        df['ATR_50'] = calculate_atr(df, 50)

        base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
            r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
            is_inner_box = \
            find_consolidation(df, min_days=settings.MIN_BASE_DAYS, select=select)

        if base_len == 0:
            return None

        atr_eval = df.iloc[-6]
        atr_ratio = atr_eval['ATR_10'] / atr_eval['ATR_50']

        if latest['Close'] < (sup_avg * settings.CRASH_FILTER_MULT):
            return None
        if latest['Close'] >= (res_avg * settings.EXTENSION_FILTER_MULT):
            return None

        base_df = df.iloc[-base_len:]
        atr_for_zone = float(atr_eval['ATR_10'])
        base_range_threshold = max(
            float(base_df['Spread'].quantile(settings.LPS_RANGE_PERCENTILE)),
            1.2 * atr_for_zone,
        )

        phase_b_start = len(df) - base_len
        swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)

        lps_result = detect_lps(
            df, latest, sup_avg, res_avg,
            atr_for_zone, base_range_threshold, base_len, swing_complete_idx,
        )

        if not lps_result:
            return None

        setup_state = lps_result['setup_type']
        lps_length = lps_result['length']
        lps_offset = lps_result['offset']
        trigger_price = lps_result['trigger_price']
        vol_contraction = lps_result['vol_contraction']
        tightness_ratio = lps_result['tightness_ratio']

        current_price = latest['Close']
        distance_to_trigger = (trigger_price - current_price) / current_price
        if distance_to_trigger <= 0:
            return None

        last_252 = df['High'].iloc[-min(252, len(df)):]
        max_252 = float(last_252.max()) if len(last_252) else 0.0
        dist_52w_high_pct = (
            (float(current_price) - max_252) / max_252 if max_252 > 0 else None
        )

        rs_lookback = settings.RS_LOOKBACK_BARS
        if len(df) > rs_lookback:
            stock_6m_return = (float(current_price) / float(df['Close'].iloc[-rs_lookback - 1]) - 1.0)
        else:
            stock_6m_return = 0.0
        excess_return_6m = stock_6m_return - spy_6m_return

        r_touch_vol_z, s_touch_vol_z = measure_touch_volume(
            base_df, res_avg, sup_avg, atr_for_zone
        )
        contraction = measure_contractions(base_df)
        bar_compression = measure_bar_compression(
            base_df, res_avg - sup_avg, atr_for_zone
        )
        support = measure_support_slope(base_df, atr_for_zone)

        bc_anchor_bar = _reconnect_bc_anchor(
            df, atr_for_zone, base_len, phase_b_start_bar, bc_anchor_bar
        )

        scope = scope_consolidation(
            df,
            bc_anchor_bar=bc_anchor_bar,
            phase_b_start_bar=phase_b_start_bar,
            base_len=base_len,
            is_inner_box=is_inner_box,
            lps_offset=lps_offset,
            lps_length=lps_length,
            lps_zone_type=lps_result.get("zone_type", "INSIDE"),
            atr_val=atr_for_zone,
        )

        bins = measure_bins(
            df,
            bc_anchor_bar=bc_anchor_bar,
            phase_b_start_bar=phase_b_start_bar,
            base_len=base_len,
            is_inner_box=is_inner_box,
            lps_offset=lps_offset,
            lps_length=lps_length,
            R=res_avg,
            S=sup_avg,
            atr_val=atr_for_zone,
        )

        trend = trend_template(df, dist_52w_high_pct=dist_52w_high_pct)

        adr_value = adr_pct(df, settings.ADR_WINDOW)
        adr_quality = (
            min(adr_value / settings.ADR_FULL_PCT, 1.0)
            if settings.ADR_FULL_PCT else 0.0
        )

        score_result = score_setup(
            box_width, r_touches, s_touches, res_avg, sup_avg, base_df,
            atr_ratio, tightness_ratio, vol_contraction, base_len, yearly_return,
            excess_return_6m, dist_52w_high_pct, breadth_pct,
            contraction['quality'], support['quality'], adr_quality,
        )
        score = score_result['total']
        tier = calculate_tier(score)

        return {
            'Ticker': ticker,
            'Tier': tier,
            'Setup': setup_state,
            'Score': score,
            'Current Price': round(float(current_price), 2),

            'Base Len': int(base_len),
            'Box Width': float(box_width),
            'Touches': int(r_touches + s_touches),
            'ATR Ratio': float(atr_ratio),
            'LPS Length': int(lps_length),
            'Breach Days': int(breach_days),

            '_r_touches': int(r_touches),
            '_s_touches': int(s_touches),
            '_vol_contraction': float(vol_contraction),
            '_tightness_ratio': float(tightness_ratio),
            '_trigger_price': float(trigger_price),
            '_sub_scores': score_result,
            '_R': float(res_avg),
            '_S': float(sup_avg),
            '_base_len': int(base_len),
            '_lps_len': int(lps_length),
            '_lps_offset': int(lps_offset),
            '_r_anchor_bar': int(r_anchor_bar),
            '_s_anchor_bar': int(s_anchor_bar),
            '_bars_since_BC': int(len(df) - bc_anchor_bar),
            '_descent_length': int(phase_b_start_bar - bc_anchor_bar),
            '_phase_d_inner': bool(is_inner_box),
            '_dist_52w_high_pct': float(dist_52w_high_pct) if dist_52w_high_pct is not None else None,
            '_excess_return_6m': float(excess_return_6m),
            '_breadth_pct': float(breadth_pct) if breadth_pct is not None else None,
            '_r_touch_vol_z': r_touch_vol_z,
            '_s_touch_vol_z': s_touch_vol_z,
            '_lps_descent_frac': float(lps_result.get('descent_frac', 1.0)),
            '_lps_zone_type': lps_result.get('zone_type', 'INSIDE'),
            '_contraction_count': int(contraction['n_contractions']),
            '_contraction_quality': float(contraction['quality']),
            '_final_contraction_depth': (float(contraction['final_depth'])
                                         if contraction['final_depth'] is not None else None),
            '_base_median_spread_atr': bar_compression['median_spread_atr'],
            '_base_p80_spread_atr': bar_compression['p80_spread_atr'],
            '_base_median_spread_pct_box': bar_compression['median_spread_pct_box'],
            '_base_tight_bar_pct': float(bar_compression['tight_bar_pct']),
            '_support_slope_atr': (float(support['slope_atr'])
                                   if support['slope_atr'] is not None else None),
            '_support_higher_low_frac': float(support['higher_low_frac']),
            '_ascending_support_quality': float(support['quality']),
            '_adr_pct': float(adr_value),
            '_adr_quality': float(adr_quality),
            '_phase_a_start_date': scope['phase_a_start_date'],
            '_phase_b_start_date': scope['phase_b_start_date'],
            '_phase_d_start_date': scope['phase_d_start_date'],
            '_phase_c_event_date': scope['phase_c_event_date'],
            '_lps_zone_low': scope['lps_zone_low'],
            '_lps_zone_high': scope['lps_zone_high'],
            '_lps_zone_start_date': scope['lps_zone_start_date'],
            '_lps_zone_end_date': scope['lps_zone_end_date'],
            '_has_mini_consolidation': bool(scope['has_mini_consolidation']),
            '_scope_confidence': float(scope['scope_confidence']),
            '_bin_a_bars': bins['bin_a_bars'],
            '_bin_a_range_pct': bins['bin_a_range_pct'],
            '_bin_a_volume_ratio': bins['bin_a_volume_ratio'],
            '_bin_b_bars': bins['bin_b_bars'],
            '_bin_b_range_pct': bins['bin_b_range_pct'],
            '_bin_b_volume_ratio': bins['bin_b_volume_ratio'],
            '_bin_d_bars': bins['bin_d_bars'],
            '_bin_d_range_pct': bins['bin_d_range_pct'],
            '_bin_d_volume_ratio': bins['bin_d_volume_ratio'],
            '_bin_d_boundary_source': bins['bin_d_boundary_source'],
            '_bin_lps_bars': bins['bin_lps_bars'],
            '_lps_position_in_box': bins['lps_position_in_box'],
            '_bin_d_vs_b_range_ratio': bins['bin_d_vs_b_range_ratio'],
            '_bin_d_vs_b_volume_ratio': bins['bin_d_vs_b_volume_ratio'],
            '_lps_stretch_atr': bins['lps_stretch_atr'],
            '_lps_stretch_box': bins['lps_stretch_box'],
            '_stage2_ma_stack_pass': trend['stage2_ma_stack_pass'],
            '_stage2_ma200_slope_1m_pct': trend['stage2_ma200_slope_1m_pct'],
            '_stage2_52w_low_pct': trend['stage2_52w_low_pct'],
            '_stage2_trend_pass_count': trend['stage2_trend_pass_count'],
            '_stage2_trend_pass': trend['stage2_trend_pass'],
            '_base_close_start': float(base_df['Close'].iloc[0]),
            '_base_close_end': float(base_df['Close'].iloc[-1]),
            '_base_date_start': str(base_df.index[0])[:10],
            '_base_date_end': str(base_df.index[-1])[:10],
        }

    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError, AttributeError) as e:
        print(f"  [skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)
        return None
