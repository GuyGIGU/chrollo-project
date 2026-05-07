"""
Data export module for Wyckoff VCP/LPS Screener.
Generates a JSON data file for the React dashboard to consume.
"""
import os
import json

from config import settings

OUTPUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output'))

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
                )
            }

            chart_data[ticker] = {
                'candles': candles,
                'volumes': volumes,
                'R': round(float(row['_R']), 2),
                'S': round(float(row['_S']), 2),
                'base_len': int(row['_base_len']),
                'lps_len': int(row['_lps_len']),
                'lps_offset': int(row['_lps_offset']),
                'r_anchor': int(row['_r_anchor_bar']),
                's_anchor': int(row['_s_anchor_bar']),
                'tier': row['Tier'],
                'score': row['Score'],
                'setup': row['Setup'],
                'sub_scores': sub_payload,
                'phase_d_inner': bool(row.get('_phase_d_inner', False)),
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
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "chart_data": chart_data,
            "ordered_tickers": ordered_tickers
        }, f)
    
    print(f"Data exported to: {json_path}")
    print("UI update available on local webapp.")
