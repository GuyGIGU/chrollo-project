"""
Data export module for Wyckoff VCP/LPS Screener.
Generates a JSON data file for the React dashboard to consume.
"""
import os
import json
import math
import sys

from config import settings
from core.pipeline.json_safety import to_json_safe
from core.structure.htf import HTF_COLUMNS, chart_box, resample_ohlc

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "webapp", "backend")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
SECTOR_ETF_CACHE_PATH = os.path.join(OUTPUT_DIR, "sector_etf_cache.json")

SECTOR_ETF_NAMES = {
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}


def _load_sector_etf_cache():
    try:
        with open(SECTOR_ETF_CACHE_PATH, "r", encoding="utf-8") as handle:
            cache = json.load(handle)
            return cache if isinstance(cache, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_sector_etf_cache(cache):
    try:
        os.makedirs(os.path.dirname(SECTOR_ETF_CACHE_PATH), exist_ok=True)
        with open(SECTOR_ETF_CACHE_PATH, "w", encoding="utf-8") as handle:
            json.dump(cache, handle)
    except OSError:
        pass


def _resolve_sector_etf(ticker):
    try:
        if BACKEND_DIR not in sys.path:
            sys.path.append(BACKEND_DIR)
        from archive_models import get_sector_etf
        return get_sector_etf(ticker) or ""
    except Exception:
        return ""


def _sector_etf_for_ticker(ticker, sector_etf_cache):
    normalized = str(ticker).upper()
    if normalized not in sector_etf_cache:
        sector_etf_cache[normalized] = _resolve_sector_etf(normalized)
        _save_sector_etf_cache(sector_etf_cache)
    return sector_etf_cache.get(normalized) or None


def _json_safe(obj):
    """Recursively coerce NumPy/Pandas scalars and replace NaN/Inf with None.

    Starlette's JSONResponse serves /screener-data/ with allow_nan=False, so a
    single NaN/Inf anywhere in the payload makes the endpoint 500 — and the
    frontend silently stays on "Loading Screener Data...". Sanitizing here, at
    the one place the file is written, guarantees the served file is always
    serveable regardless of which metric produced a degenerate value.
    """
    return to_json_safe(obj)

def _tf_candles(df, tf, cap):
    """Resample the daily frame to weekly/monthly and return (candles, volumes)
    for the higher-timeframe charts, capped to the last ``cap`` bars."""
    resampled = resample_ohlc(df, tf)
    if resampled is None or resampled.empty:
        return [], []
    resampled = resampled.tail(cap)
    dates = [str(idx)[:10] for idx in resampled.index]
    opens = resampled['Open'].round(2).values
    highs = resampled['High'].round(2).values
    lows = resampled['Low'].round(2).values
    closes = resampled['Close'].round(2).values
    vols = resampled['Volume'].round(0).values
    candles = [
        {'time': d, 'open': float(o), 'high': float(h), 'low': float(l), 'close': float(c)}
        for d, o, h, l, c in zip(dates, opens, highs, lows, closes)
    ]
    volumes = [
        {'time': d, 'value': float(v),
         'color': 'rgba(38,166,154,0.5)' if c >= o else 'rgba(239,83,80,0.5)'}
        for d, o, c, v in zip(dates, opens, closes, vols)
    ]
    return candles, volumes


def _extract_chart_data(data, results_df, tickers):
    """Extract OHLCV data as JSON-serializable dicts for each chartable ticker."""
    chart_data = {}
    chart_candidates = results_df[results_df['Tier'].isin(settings.DASHBOARD_CHART_TIERS)]
    sector_etf_cache = _load_sector_etf_cache()
    
    for _, row in chart_candidates.iterrows():
        ticker = row['Ticker']
        try:
            if len(tickers) > 1:
                df = data[ticker].dropna()
            else:
                df = data.dropna()
            
            show_days = min(settings.DASHBOARD_CHART_DAYS, len(df))
            plot_df = df.tail(show_days).copy().reset_index()
            
            # Vectorized extraction — avoid per-row iloc overhead
            if 'Date' in plot_df.columns:
                dates = plot_df['Date'].dt.strftime('%Y-%m-%d').values
            else:
                dates = [str(idx)[:10] for idx in plot_df.index]
            
            opens = plot_df['Open'].round(2).values
            highs = plot_df['High'].round(2).values
            lows = plot_df['Low'].round(2).values
            closes = plot_df['Close'].round(2).values
            vols = plot_df['Volume'].round(0).values
            
            candles = [
                {'time': d, 'open': float(o), 'high': float(h), 'low': float(l), 'close': float(c)}
                for d, o, h, l, c in zip(dates, opens, highs, lows, closes)
            ]
            volumes = [
                {'time': d, 'value': float(v),
                 'color': 'rgba(38,166,154,0.5)' if c >= o else 'rgba(239,83,80,0.5)'}
                for d, o, c, v in zip(dates, opens, closes, vols)
            ]
            # Weekly + monthly candles for the higher-timeframe charts, resampled
            # from the FULL daily history (not the 300-bar daily window).
            weekly_candles, weekly_volumes = _tf_candles(df, "weekly", 110)
            monthly_candles, monthly_volumes = _tf_candles(df, "monthly", 60)
            # Worked box geometry (R/S + start date) so the chart can anchor the
            # rails to the bars the box is born from, like the daily chart.
            weekly_box = chart_box(df, "weekly")
            monthly_box = chart_box(df, "monthly")
            window_start_bar = len(df) - show_days
            def _local_bar(value):
                try:
                    return (
                        int(float(value)) - window_start_bar
                        if value is not None and math.isfinite(float(value))
                        else None
                    )
                except (TypeError, ValueError):
                    return None

            inner_start_local = _local_bar(row.get('_inner_start_bar'))
            
            # Sub-scores power the "why ranked" tag chips on the frontend
            # card. Emit the raw point values; the JS helper compares each
            # against its cap (config.settings.SCORE_*) to decide which
            # tags fire.
            sub = row.get('_sub_scores') or {}
            sub_payload = {
                k: round(float(sub.get(k, 0) or 0), 2)
                for k in (
                    'box_tightness', 'touch_density', 'traversal_quality',
                    'atr_squeeze', 'lps_tightness', 'vol_contraction',
                    'base_age', 'uptrend_bonus', 'rs_bonus',
                    'high_proximity', 'breadth_bonus', 'contraction',
                    'ascending_support', 'adr',
                )
            }

            sector_etf = _sector_etf_for_ticker(ticker, sector_etf_cache)

            chart_data[ticker] = {
                'candles': candles,
                'volumes': volumes,
                'weekly_candles': weekly_candles,
                'weekly_volumes': weekly_volumes,
                'weekly_box': weekly_box,
                'monthly_candles': monthly_candles,
                'monthly_volumes': monthly_volumes,
                'monthly_box': monthly_box,
                'R': round(float(row['_R']), 2),
                'S': round(float(row['_S']), 2),
                'inner_R': row.get('_inner_R'),
                'inner_S': row.get('_inner_S'),
                'inner_box_width': row.get('_inner_box_width'),
                'inner_start_bar': inner_start_local,
                'inner_source': row.get('_inner_source'),
                'inner_search_start_bar': _local_bar(row.get('_inner_search_start_bar')),
                'inner_climax_bar': _local_bar(row.get('_inner_climax_bar')),
                'inner_reaction_bar': _local_bar(row.get('_inner_reaction_bar')),
                'inner_reaction_pct': row.get('_inner_reaction_pct'),
                'inner_reaction_bars': row.get('_inner_reaction_bars'),
                'lps_in_inner': bool(row.get('_lps_in_inner', False)),
                'base_len': int(row['_base_len']),
                'lps_len': int(row['_lps_len']),
                'lps_offset': int(row['_lps_offset']),
                'r_anchor': int(row['_r_anchor_bar']),
                's_anchor': int(row['_s_anchor_bar']),
                'tier': row['Tier'],
                'score': row['Score'],
                'setup': row['Setup'],
                'sector_etf': sector_etf,
                'sector_name': SECTOR_ETF_NAMES.get(sector_etf) if sector_etf else None,
                # Price vs. breakout trigger — lets the frontend show / sort by
                # "% to trigger" (how much room is left before the entry fires).
                'price': round(float(row['Current Price']), 2),
                'trigger': round(float(row['_trigger_price']), 2),
                'sub_scores': sub_payload,
                'phase_d_inner': bool(row.get('_phase_d_inner', False)),
                # Volume-around-touches signature → drives no_supply /
                # spring_strength / heavy_resistance tags on the card.
                'r_touch_vol_z': row.get('_r_touch_vol_z'),
                's_touch_vol_z': row.get('_s_touch_vol_z'),
                # LPS shape detail (for tooltips / future analysis)
                'lps_descent_frac': row.get('_lps_descent_frac'),
                'lps_high_descent_frac': row.get('_lps_high_descent_frac'),
                'lps_window_range_pct_box': row.get('_lps_window_range_pct_box'),
                'lps_high_extension_box': row.get('_lps_high_extension_box'),
                'lps_high_extension_atr': row.get('_lps_high_extension_atr'),
                'lps_profile_unit': row.get('_lps_profile_unit'),
                'lps_profile_unit_pct': row.get('_lps_profile_unit_pct'),
                'lps_pullback_profile': row.get('_lps_pullback_profile'),
                'lps_terminal_low_tolerance': row.get('_lps_terminal_low_tolerance'),
                'lps_spread_expansion_profile': row.get('_lps_spread_expansion_profile'),
                'lps_first_high': row.get('_lps_first_high'),
                'lps_last_low': row.get('_lps_last_low'),
                'lps_window_high': row.get('_lps_window_high'),
                'lps_window_low': row.get('_lps_window_low'),
                'lps_swing_type': row.get('_lps_swing_type'),
                'lps_anchor_bar': row.get('_lps_anchor_bar'),
                'lps_anchor_date': row.get('_lps_anchor_date'),
                'lps_low_bar': row.get('_lps_low_bar'),
                'lps_low_date': row.get('_lps_low_date'),
                'lps_swing_depth_pct': row.get('_lps_swing_depth_pct'),
                'lps_swing_depth_atr': row.get('_lps_swing_depth_atr'),
                'lps_swing_depth_box': row.get('_lps_swing_depth_box'),
                'lps_tests': row.get('_lps_tests') or [],
                'lps_zone_type': row.get('_lps_zone_type'),
                # VCP contraction footprint (for tooltips / tag)
                'contraction_count': row.get('_contraction_count'),
                'contraction_quality': row.get('_contraction_quality'),
                'final_contraction_depth': row.get('_final_contraction_depth'),
                'contraction_vol_trend': row.get('_contraction_vol_trend'),
                # Ascending-support / higher-lows footprint (for tooltips / tag)
                'support_slope_atr': row.get('_support_slope_atr'),
                'ascending_support_quality': row.get('_ascending_support_quality'),
                'higher_low_frac': row.get('_support_higher_low_frac'),
                'adr_pct': row.get('_adr_pct'),
                # Bin-B interior trajectory ("eyes inside the base") → drives the
                # interior CoG tooltip on the card. (The worked_equilibrium chip now
                # fires off traversal_density below, not these close-based crossings.)
                'bin_b_cog_end': row.get('_bin_b_cog_end'),
                'bin_b_cog_crossings': row.get('_bin_b_cog_crossings'),
                'bin_b_cog_rng': row.get('_bin_b_cog_rng'),
                'bin_b_cog_corr': row.get('_bin_b_cog_corr'),
                # Limb-traversal density (rail-to-rail swings / significant swings) →
                # drives the worked_equilibrium chip; the real two-sidedness signal.
                'traversal_density': (
                    round(row['_trav_n_full_traversals'] / row['_trav_n_swings'], 3)
                    if row.get('_trav_n_swings') else None
                ),
                # HTF (higher-timeframe) context — weekly/monthly Trend+Box read,
                # surfaced to the Screener Grid. Bare keys (htf_w_* / htf_m_*).
                **{c: row.get('_' + c) for c in HTF_COLUMNS},
                'bin_c_present': row.get('_bin_c_present'),
                'bin_c_type': row.get('_bin_c_type'),
                'bin_c_event_date': row.get('_bin_c_event_date'),
                'bin_c_event_bar': _local_bar(row.get('_bin_c_event_bar')),
                'bin_c_undercut_atr': row.get('_bin_c_undercut_atr'),
                'bin_c_recovery_bars': row.get('_bin_c_recovery_bars'),
                'bin_c_recovery_bar': _local_bar(row.get('_bin_c_recovery_bar')),
                'bin_c_time_loc': row.get('_bin_c_time_loc'),
                'bin_c_spring_vol_z': row.get('_bin_c_spring_vol_z'),
                'bin_d_start_bar': _local_bar(row.get('_bin_d_start_bar')),
                'bin_d_support_slope_atr': row.get('_bin_d_support_slope_atr'),
                'bin_d_higher_low_frac': row.get('_bin_d_higher_low_frac'),
                'bin_d_ascending_support_quality': row.get('_bin_d_ascending_support_quality'),
                'bin_d_vs_b_support_quality_delta': row.get('_bin_d_vs_b_support_quality_delta'),
                'bin_d_boundary_source': row.get('_bin_d_boundary_source'),
                'lps_stretch_atr': row.get('_lps_stretch_atr'),
                'lps_stretch_box': row.get('_lps_stretch_box'),
                'last_supper_pullback_from_extension_pct': row.get('_last_supper_pullback_from_extension_pct'),
                'last_supper_source_box_age': row.get('_last_supper_source_box_age'),
                'last_supper_reclaim_quality': row.get('_last_supper_reclaim_quality'),
                'phase_d_evidence_json': row.get('_phase_d_evidence_json'),
                # Phase-D scoping bands — consumed by the chart phase overlay.
                # Underscore-prefixed to match the keys chartPhaseOverlay.js reads.
                '_phase_a_start_date': row.get('_phase_a_start_date'),
                '_phase_a_end_date': row.get('_phase_a_end_date'),
                '_phase_b_start_date': row.get('_phase_b_start_date'),
                '_phase_d_start_date': row.get('_phase_d_start_date'),
                '_phase_c_event_date': row.get('_phase_c_event_date'),
                '_lps_zone_low': row.get('_lps_zone_low'),
                '_lps_zone_high': row.get('_lps_zone_high'),
                '_lps_zone_start_date': row.get('_lps_zone_start_date'),
                '_lps_zone_end_date': row.get('_lps_zone_end_date'),
                '_has_mini_consolidation': bool(row.get('_has_mini_consolidation', False)),
                '_scope_confidence': row.get('_scope_confidence'),
                # Advisory metadata (Lane E) — graded tag-chip data, NOT scored /
                # NOT a veto. Only present when the relevant flag is ON (else the
                # eval result carries no such key and these read None -> no chip).
                # Fundamentals are point-in-time (filing-lag gated). The held
                # frontend lane maps these to ⚡ RS Leader / Earnings Accel /
                # days-to-earnings chips.
                'fund_eps_growth_yoy': row.get('_fund_eps_growth_yoy'),
                'fund_sales_growth_yoy': row.get('_fund_sales_growth_yoy'),
                'fund_eps_growth_accel': row.get('_fund_eps_growth_accel'),
                'fund_earnings_surprise': row.get('_fund_earnings_surprise'),
                'days_to_earnings': row.get('_days_to_earnings'),
                'rs_rating': row.get('_rs_rating'),
                'rs_line_latest': row.get('_rs_line_latest'),
                'rs_line_new_high': row.get('_rs_line_new_high'),
            }
        except Exception as e:
            print(f"  Chart data error on {ticker}: {e}")
    
    return chart_data


def generate_dashboard(results_df, data=None, tickers=None, market_context=None):
    """Extract chart data and export it as JSON for the React frontend."""
    
    # Extract chart data if market data is provided
    chart_data = {}
    if data is not None and tickers is not None:
        chart_data = _extract_chart_data(data, results_df, tickers)
        print(f"\nExtracted {len(chart_data)} interactive chart models for React dashboard...", flush=True)
    
    ordered_tickers = []
    for _, row in results_df.iterrows():
        if row['Ticker'] in chart_data:
            ordered_tickers.append(row['Ticker'])
            
    json_path = os.path.join(OUTPUT_DIR, "screener_data.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
        
    payload = _json_safe({
        "chart_data": chart_data,
        "ordered_tickers": ordered_tickers,
        "market_context": market_context or {},
    })
    tmp_path = json_path + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, allow_nan=False)
        os.replace(tmp_path, json_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
    
    # flush=True so the webapp's scan stream receives these sentinels immediately
    # — the frontend reveals results on "UI update available" without waiting for
    # the slow archive step that runs after this.
    print(f"Data exported to: {json_path}", flush=True)
    print("UI update available on local webapp.", flush=True)
