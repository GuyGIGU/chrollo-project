import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def get_tickers(csv_path="tickers.csv"):
    """
    Attempts to read tickers from a CSV file (like an export from Finviz or Nasdaq).
    If the file is not found, it falls back to our sample list.
    """
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].dropna().tolist()
            elif 'Symbol' in df.columns:
                tickers = df['Symbol'].dropna().tolist()
            else:
                tickers = df.iloc[:, 0].dropna().tolist()
                
            print(f"✅ Loaded {len(tickers)} tickers from {csv_path}")
            return tickers
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")
            
    # FREE HACK: S&P 1500
    print("⚠️ No 'tickers.csv' file found. Automatically downloading S&P 1500 tickers from Wikipedia for free...")
    try:
        urls = [
            'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
            'https://en.wikipedia.org/wiki/List_of_S%26P_400_companies',
            'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'
        ]
        tickers = []
        for url in urls:
            tables = pd.read_html(url, storage_options={'User-Agent': 'Mozilla/5.0'})
            df_table = tables[0]
            col = 'Symbol' if 'Symbol' in df_table.columns else 'Ticker symbol'
            t = df_table[col].str.replace('.', '-').tolist()
            tickers.extend(t)
            
        print(f"✅ Successfully fetched {len(tickers)} S&P 1500 market leaders!")
        return list(set(tickers))
    except Exception as e:
        print(f"⚠️ Could not fetch from Wikipedia: {e}. (You might need to run 'pip install lxml')")
        print("Falling back to the 15-stock sample list.")
        return [
            'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD', 'META', 'AMZN', 'GOOGL', 
            'PLTR', 'SNOW', 'CRWD', 'UBER', 'NFLX', 'SMCI', 'ARM'
        ]

import pickle
import time

def fetch_data(tickers):
    """
    Downloads 1 year of daily data for all tickers, using a local cache if recent.
    """
    cache_file = "market_data_cache_1y.pkl"
    # Check if cache exists and is less than 12 hours old
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < 12 * 3600:
            print("⚡ Loading market data from local cache (super fast!)...")
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
                
    print(f"Downloading data for {len(tickers)} tickers. This may take a moment...")
    data = yf.download(tickers, period='1y', group_by='ticker', threads=False, progress=True)
    
    # Save to cache
    with open(cache_file, 'wb') as f:
        pickle.dump(data, f)
        
    return data

def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', printEnd="\r"):
    """
    Call in a loop to create terminal progress bar
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=printEnd)
    if iteration == total: 
        print()

def calculate_atr(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def calculate_adx(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    plus_dm = high.diff()
    minus_dm = low.diff()
    
    # +DM and -DM logic
    plus_dm_condition = (plus_dm > -minus_dm) & (plus_dm > 0)
    minus_dm_condition = (-minus_dm > plus_dm) & (-minus_dm > 0)
    
    plus_dm_val = np.where(plus_dm_condition, plus_dm, 0.0)
    minus_dm_val = np.where(minus_dm_condition, -minus_dm, 0.0)
    
    plus_dm_series = pd.Series(plus_dm_val, index=df.index)
    minus_dm_series = pd.Series(minus_dm_val, index=df.index)
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm_series.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm_series.ewm(alpha=1/period, adjust=False).mean() / atr)
    
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return adx

def find_consolidation_window(df, min_days=20, max_days=150):
    """
    Scans backward using horizontal parallel lines to find Resistance and Support Zones.
    A high quality consolidation consists of plenty of touches on both Support and Resistance,
    and a Zigzag of at least 3 points at the start of the structure.
    """
    if len(df) < max_days + 5:
        max_days = len(df) - 5
    if max_days < min_days:
        return 0, 0, 0, 1.0, 0
        
    window_df = df.iloc[-(max_days+5):-5]
    highs = window_df['High'].values
    lows = window_df['Low'].values
    
    ORDER = 2
    peaks_idx = []
    valleys_idx = []
    for i in range(ORDER, len(window_df) - ORDER):
        if all(highs[i] > highs[i-j] for j in range(1, ORDER+1)) and \
           all(highs[i] > highs[i+j] for j in range(1, ORDER+1)):
            peaks_idx.append(i)
        if all(lows[i] < lows[i-j] for j in range(1, ORDER+1)) and \
           all(lows[i] < lows[i+j] for j in range(1, ORDER+1)):
            valleys_idx.append(i)
            
    pivots = [(p, 1, highs[p]) for p in peaks_idx] + [(v, -1, lows[v]) for v in valleys_idx]
    pivots.sort(key=lambda x: x[0])
    
    filt_pivots = []
    if pivots:
        filt_pivots.append(pivots[0])
        for i in range(1, len(pivots)):
            curr = pivots[i]
            prev = filt_pivots[-1]
            if curr[1] == prev[1]:
                if curr[1] == 1 and curr[2] > prev[2]:
                    filt_pivots[-1] = curr
                elif curr[1] == -1 and curr[2] < prev[2]:
                    filt_pivots[-1] = curr
            else:
                filt_pivots.append(curr)
                
    best_len = 0
    best_R = 0
    best_S = 0
    best_touches = 0
    best_box_width = 1.0
    
    for i in range(len(filt_pivots) - 2):
        start_idx = filt_pivots[i][0]
        base_length = len(window_df) - start_idx
        
        if base_length < min_days:
            continue
            
        sub_pivots = filt_pivots[i:]
        peaks = [p[2] for p in sub_pivots if p[1] == 1]
        valleys = [p[2] for p in sub_pivots if p[1] == -1]
        
        if len(peaks) < 2 or len(valleys) < 2:
            continue
            
        r_counts = []
        for p_ref in peaks:
            cluster = [p for p in peaks if abs(p - p_ref)/p_ref <= 0.03]
            r_counts.append((len(cluster), np.mean(cluster)))
        r_counts.sort(key=lambda x: (x[0], x[1]), reverse=True)
        R_count, R_val = r_counts[0]
        
        s_counts = []
        for v_ref in valleys:
            cluster = [v for v in valleys if abs(v - v_ref)/v_ref <= 0.03]
            s_counts.append((len(cluster), -np.mean(cluster)))
        s_counts.sort(key=lambda x: (x[0], x[1]), reverse=True)
        S_count, S_val = s_counts[0][0], -s_counts[0][1]
        
        if R_count >= 2 and S_count >= 2:
            if R_val <= S_val: continue
            
            box_width = (R_val - S_val) / S_val
            if box_width > 0.20:
                continue
                
            midline = (R_val + S_val) / 2
            base_closes = window_df['Close'].iloc[start_idx:]
            
            crosses = 0
            if len(base_closes) > 1:
                prev_above = base_closes.iloc[0] > midline
                for price in base_closes.iloc[1:]:
                    curr_above = price > midline
                    if curr_above != prev_above:
                        crosses += 1
                        prev_above = curr_above
                        
            if crosses < 3:
                continue
                
            total_touches = R_count + S_count
            
            if total_touches > best_touches or (total_touches == best_touches and box_width < best_box_width):
                best_len = base_length
                best_R = R_val
                best_S = S_val
                best_box_width = box_width
                best_touches = total_touches
                
    return best_len, best_R, best_S, best_box_width, best_touches



def run_screener():
    tickers = get_tickers()
    data = fetch_data(tickers)
    
    results = []
    total_tickers = len(tickers)
    
    print("\nStarting quantitative scans...")
    print_progress(0, total_tickers, prefix='Evaluating:', suffix='Complete', length=50)

    for i, ticker in enumerate(tickers):
        print_progress(i + 1, total_tickers, prefix='Evaluating:', suffix='Complete', length=50)
        try:
            # Extract the specific ticker's dataframe
            if len(tickers) > 1:
                if ticker not in data:
                    continue
                df = data[ticker].dropna()
            else:
                df = data.dropna()
            
            if len(df) < 200:
                continue
                
            # ----------------------------------------------------
            # PHASE 1: UNIVERSE BASELINE FILTER
            # ----------------------------------------------------
            # We copy to avoid SettingWithCopy warnings
            df = df.copy() 
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            df['Vol_50'] = df['Volume'].rolling(window=50).mean()
            
            # Candle Spread (High - Low) and 20-day average for Tightness check
            df['Spread'] = df['High'] - df['Low']
            df['Avg_Spread_20'] = df['Spread'].rolling(window=20).mean()
            
            latest = df.iloc[-1]
            one_year_ago = df.iloc[0]
            
            yearly_return = (latest['Close'] - one_year_ago['Close']) / one_year_ago['Close']
            
            if latest['Close'] < 3.0: continue
            if latest['Vol_50'] < 50000: continue
            if latest['Close'] < latest['SMA_50']: continue
            if latest['Close'] < latest['SMA_200']: continue
            if yearly_return < 0.30: continue
            
            # ----------------------------------------------------
            # PHASE 2: CONSOLIDATION BASE (Structural Support/Resistance)
            # ----------------------------------------------------
            base_len, res_avg, sup_avg, box_width, touches = find_consolidation_window(df, min_days=20, max_days=150)
            
            # RULE 1: Must have a valid valid consolidation base identified
            if base_len == 0 or box_width > 0.20: continue
            
            df_with_indicators = df.copy()
            df_with_indicators['ATR_10'] = calculate_atr(df_with_indicators, 10)
            df_with_indicators['ATR_50'] = calculate_atr(df_with_indicators, 50)
            df_with_indicators['ADX_14'] = calculate_adx(df_with_indicators, 14)
            
            atr_eval = df_with_indicators.iloc[-6]
            atr_ratio = atr_eval['ATR_10'] / atr_eval['ATR_50']
            adx_val = atr_eval['ADX_14']
            
            if pd.isna(adx_val) or adx_val > 25: continue
            
            # CRASH FILTER: Evaluate structural failure from minimum body
            if latest['Close'] < (sup_avg * 0.95): continue
            
            # EXTENSION FILTER: Avoid LPS that is too far extended away
            if latest['Close'] >= (res_avg * 1.15): continue
            
            # ----------------------------------------------------
            # PHASE 3: LPS & BREAKOUT DETECTION
            # ----------------------------------------------------
            last_5 = df.tail(5)
            
            is_lps = False
            is_breakout = False
            setup_state = ""
            lps_length = 0
            trigger_price = 0
            vol_contraction = 0
            tightness_ratio = 1.0
            
            for length in [2, 3, 4, 5]:
                pullback_period = last_5.tail(length)
                
                start_lps = pullback_period.iloc[0]
                end_lps = pullback_period.iloc[-1]
                
                # Measure true down-vector: sequence maximum high to final day low
                max_high_lps = pullback_period['High'].max()
                min_low_lps = end_lps['Low']
                drop_pct = (max_high_lps - min_low_lps) / max_high_lps
                
                # Drop slightly relaxed but enforced 2-15% range
                if 0.02 <= drop_pct <= 0.15:
                    avg_pullback_vol = pullback_period['Volume'].mean()
                    if avg_pullback_vol < latest['Vol_50']:
                        # Measure tight candles limit sellers
                        tight_spread = end_lps['Spread']
                        avg_spread_20 = end_lps['Avg_Spread_20']
                        
                        # RULE: Candle spread must be tighter than 95% of normal. True dry-up!
                        if tight_spread < avg_spread_20 * 0.95:
                            is_lps = True
                            setup_state = "LPS"
                            lps_length = length
                            trigger_price = pullback_period['High'].max()
                            vol_contraction = (latest['Vol_50'] - avg_pullback_vol) / latest['Vol_50']
                            tightness_ratio = tight_spread / avg_spread_20
                            break
                            
            if not is_lps and latest['Close'] > res_avg and latest['Volume'] > (latest['Vol_50'] * 1.5):
                is_breakout = True
                setup_state = "BREAKOUT"
                trigger_price = res_avg
                vol_contraction = 0.5 # Default score baseline for explosive volume
                tightness_ratio = 0.7 # Default score baseline for extreme push
                
            # ----------------------------------------------------
            # PHASE 4: RANKING SCORE PREPARATION
            # ----------------------------------------------------
            if is_lps or is_breakout:
                current_price = latest['Close']
                distance_to_trigger = (trigger_price - current_price) / current_price if is_lps else 0
                
                if is_breakout or distance_to_trigger > 0: 
                    # -- COMPUTE SCORE (MAX ~100) --
                    score = 0
                    
                    # 1. Box Tightness (Up to 10 pts. Tighter = higher score, 20% width = 0 pts)
                    box_score = max(0, min(10, (0.20 - box_width) * (10 / 0.20)))
                    score += box_score
                    
                    # 2. Consolidation Touches (Max 10 pts for more touches)
                    touch_score = max(0, min(10, touches * 1.5))
                    score += touch_score
                    
                    # 3. ATR Squeeze (Up to 10 pts)
                    atr_score = max(0, min(10, (1.0 - atr_ratio) * 10))
                    score += atr_score
                    
                    # 4. LPS Candle Tightness (Super heavily weighted. Up to 60 pts. Tighter = higher score)
                    tight_score = min(60, (1 - tightness_ratio) * 120)
                    score += max(0, tight_score)
                    
                    # 5. Volume Contraction (Up to 10 pts)
                    vol_score = min(10, vol_contraction * 20)
                    score += max(0, vol_score)
                    
                    results.append({
                        'Ticker': ticker,
                        'Setup': setup_state,
                        'Score': round(score, 1),
                        'Current Price': round(current_price, 2),
                        'Trigger Price': round(trigger_price, 2),
                        'Base Len': f"{base_len}d",
                        'Box Width': f"{round(box_width * 100, 1)}%",
                        'Touches': f"{touches}",
                        'ATR Ratio': f"{round(atr_ratio * 100, 1)}%",
                        'LPS Length': f"{lps_length}d" if is_lps else "-"
                    })
                    

                    
        except Exception as e:
            pass
            
    # Output the results in a formatted console table
    if results:
        results_df = pd.DataFrame(results)
        
        # Sort by BEST SCORE DESCENDING
        results_df = results_df.sort_values(by='Score', ascending=False)
        
        print("\n=== WYCKOFF LPS SCREENER RESULTS (RANKED) ===")
        print(results_df.to_string(index=False))
        results_df.to_csv("lps_watchlist.csv", index=False)
        print("\n✅ Results saved to lps_watchlist.csv!")
        
        # ----------------------------------------------------
        # FINVIZ URL GENERATOR
        # ----------------------------------------------------
        passed_tickers = results_df['Ticker'].tolist()
        finviz_url = f"https://finviz.com/screener.ashx?v=211&t={','.join(passed_tickers)}"
        print("\n📈 Open these exact charts instantly in Finviz (Ctrl+Click):")
        print(finviz_url)
        print("-" * 50)
        
    else:
        print("\nNo setups found today. Filters are running tight, wait for the right pitch!")

if __name__ == "__main__":
    run_screener()
