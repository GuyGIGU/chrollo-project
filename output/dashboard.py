"""
Data export module for Wyckoff VCP/LPS Screener.
Generates a JSON data file for the React dashboard to consume.
"""
import os
import json
import math

from config import settings

OUTPUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output'))


def _json_safe(obj):
    """Recursively replace NaN/Inf floats with None so the written JSON is
    strictly RFC-compliant.

    Starlette's JSONResponse serves /screener-data/ with allow_nan=False, so a
    single NaN/Inf anywhere in the payload makes the endpoint 500 — and the
    frontend silently stays on "Loading Screener Data...". Sanitizing here, at
    the one place the file is written, guarantees the served file is always
    serveable regardless of which metric produced a degenerate value.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj

def _extract_chart_data(data, results_df, tickers):
    """Extract OHLCV data as JSON-serializable dicts for each chartable ticker."""
    chart_data = {}
    chart_candidates = results_df[results_df['Tier'].isin(settings.DASHBOARD_CHART_TIERS)]
    
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
            window_start_bar = len(df) - show_days
            inner_start = row.get('_inner_start_bar')
            try:
                inner_start_local = (
                    int(float(inner_start)) - window_start_bar
                    if inner_start is not None and math.isfinite(float(inner_start))
                    else None
                )
            except (TypeError, ValueError):
                inner_start_local = None
            
            # Sub-scores power the "why ranked" tag chips on the frontend
            # card. Emit the raw point values; the JS helper compares each
            # against its cap (config.settings.SCORE_*) to decide which
            # tags fire.
            sub = row.get('_sub_scores') or {}
            sub_payload = {
                k: round(float(sub.get(k, 0) or 0), 2)
                for k in (
                    'box_tightness', 'touch_density', 'oscillation',
                    'atr_squeeze', 'lps_tightness', 'vol_contraction',
                    'base_age', 'uptrend_bonus', 'rs_bonus',
                    'high_proximity', 'breadth_bonus', 'contraction',
                    'ascending_support', 'adr',
                )
            }

            chart_data[ticker] = {
                'candles': candles,
                'volumes': volumes,
                'R': round(float(row['_R']), 2),
                'S': round(float(row['_S']), 2),
                'inner_R': row.get('_inner_R'),
                'inner_S': row.get('_inner_S'),
                'inner_box_width': row.get('_inner_box_width'),
                'inner_start_bar': inner_start_local,
                'lps_in_inner': bool(row.get('_lps_in_inner', False)),
                'base_len': int(row['_base_len']),
                'lps_len': int(row['_lps_len']),
                'lps_offset': int(row['_lps_offset']),
                'r_anchor': int(row['_r_anchor_bar']),
                's_anchor': int(row['_s_anchor_bar']),
                'tier': row['Tier'],
                'score': row['Score'],
                'setup': row['Setup'],
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
                # two_sided_range tag + interior tooltip on the card.
                'bin_b_cog_end': row.get('_bin_b_cog_end'),
                'bin_b_cog_crossings': row.get('_bin_b_cog_crossings'),
                'bin_b_cog_rng': row.get('_bin_b_cog_rng'),
                'bin_b_cog_corr': row.get('_bin_b_cog_corr'),
                # Phase-D scoping bands — consumed by the chart phase overlay.
                # Underscore-prefixed to match the keys chartPhaseOverlay.js reads.
                '_phase_a_start_date': row.get('_phase_a_start_date'),
                '_phase_b_start_date': row.get('_phase_b_start_date'),
                '_phase_d_start_date': row.get('_phase_d_start_date'),
                '_phase_c_event_date': row.get('_phase_c_event_date'),
                '_lps_zone_low': row.get('_lps_zone_low'),
                '_lps_zone_high': row.get('_lps_zone_high'),
                '_lps_zone_start_date': row.get('_lps_zone_start_date'),
                '_lps_zone_end_date': row.get('_lps_zone_end_date'),
                '_has_mini_consolidation': bool(row.get('_has_mini_consolidation', False)),
                '_scope_confidence': row.get('_scope_confidence'),
            }
        except Exception as e:
            print(f"  Chart data error on {ticker}: {e}")
    
    return chart_data


def generate_dashboard(results_df, data=None, tickers=None):
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
    })
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f)
    
    # flush=True so the webapp's scan stream receives these sentinels immediately
    # — the frontend reveals results on "UI update available" without waiting for
    # the slow archive step that runs after this.
    print(f"Data exported to: {json_path}", flush=True)
    print("UI update available on local webapp.", flush=True)
