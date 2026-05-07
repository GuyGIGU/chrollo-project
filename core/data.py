"""
Data acquisition module — ticker loading, market data download, and caching.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

from config import settings


def get_tickers(csv_path: str | None = None) -> list[str]:
    """
    Load ticker universe from CSV. Falls back to the NASDAQ Trader FTP dump
    (common-stock filter applied), then caches result to CSV for future runs.
    """
    if csv_path is None:
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'tickers.csv'
        )
        csv_path = os.path.normpath(csv_path)

    if os.path.exists(csv_path):
        file_age_days = (time.time() - os.path.getmtime(csv_path)) / (24 * 3600)
        if file_age_days < settings.TICKER_CACHE_MAX_AGE_DAYS:
            try:
                df = pd.read_csv(csv_path)
                if 'Ticker' in df.columns:
                    tickers = df['Ticker'].dropna().tolist()
                elif 'Symbol' in df.columns:
                    tickers = df['Symbol'].dropna().tolist()
                else:
                    tickers = df.iloc[:, 0].dropna().tolist()
    
                print(f"Loaded {len(tickers)} tickers from {csv_path} (Age: {file_age_days:.1f} days)", flush=True)
                return tickers
            except Exception as e:
                print(f"Error reading {csv_path}: {e}")
        else:
            print(f"Ticker cache {csv_path} is {file_age_days:.1f} days old. Refreshing master list...", flush=True)

    print("Downloading master universe from NASDAQ FTP...", flush=True)
    try:
        url = 'ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt'
        df_table = pd.read_csv(url, sep='|')
        
        # Filter purely common stocks
        if 'Test Issue' in df_table.columns and 'ETF' in df_table.columns:
            df_table = df_table[(df_table['Test Issue'] == 'N') & (df_table['ETF'] == 'N')]
            
        tickers: list[str] = []
        target_col = next((col for col in df_table.columns if col.lower() in ['symbol', 'ticker symbol', 'ticker']), None)
        if target_col:
            raw_tickers = df_table[target_col].dropna().astype(str).tolist()
            for t in raw_tickers:
                # Accept plain-alpha tickers up to 5 chars (covers GOOGL, COST, etc.);
                # dotted/class-share symbols like BRK.B are skipped because yfinance
                # handles them inconsistently.
                if t.isalpha() and len(t) <= 5:
                    tickers.append(t)

        # Preserve original order while deduping — stable for reproducible runs.
        tickers = list(dict.fromkeys(tickers))
        print(f"Successfully fetched and filtered {len(tickers)} common US equities!", flush=True)

        # Save to static CSV
        pd.DataFrame({'Ticker': tickers}).to_csv(csv_path, index=False)
        print(f"Saved primary universe to '{csv_path}'. It will be cached for {settings.TICKER_CACHE_MAX_AGE_DAYS} day(s).")
        return tickers
    except Exception as e:
        print(f"Could not fetch from NASDAQ FTP: {e}.")
        print("Falling back to the 15-stock sample list.")
        return [
            'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD', 'META', 'AMZN', 'GOOGL',
            'PLTR', 'SNOW', 'CRWD', 'UBER', 'NFLX', 'SMCI', 'ARM'
        ]


def _download_batch_with_retry(batch: list[str], period: str, max_retries: int = 3) -> pd.DataFrame:
    """
    Download a batch of tickers with automatic retry on failure.
    Returns the downloaded DataFrame (possibly empty on total failure).
    """
    for attempt in range(1, max_retries + 1):
        try:
            batch_data = yf.download(
                batch,
                period=period,
                group_by='ticker',
                threads=True,
                progress=False,
                timeout=30,  # 30s timeout to handle slow connections
            )
            if not batch_data.empty:
                # If only 1 ticker in batch, it doesn't return a MultiIndex, so we force it
                if len(batch) == 1 and not isinstance(batch_data.columns, pd.MultiIndex):
                    batch_data.columns = pd.MultiIndex.from_product([batch, batch_data.columns])
                return batch_data
        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                print(f"    Attempt {attempt}/{max_retries} failed ({e}). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"    Batch failed after {max_retries} retries: {e}")

    return pd.DataFrame()


def _recover_missing_data(data: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """
    Check for missing or incomplete data (<200 bars) and attempt to re-download.
    Returns the corrected DataFrame.
    """
    missing_or_short = []
    for ticker in tickers:
        if ticker in data:
            df_ticker = data[ticker].dropna()
            if len(df_ticker) < 200:
                missing_or_short.append(ticker)
        else:
            missing_or_short.append(ticker)

    if not missing_or_short:
        return data

    if len(missing_or_short) > len(tickers) * 0.5:
        print(f"Warning: {len(missing_or_short)} dropouts detected. Rate limit severe. Skipping individual fallback to avoid IP ban.")
        return data

    print(f"Validating {len(missing_or_short)} tickers with missing or suspiciously short data (<200 bars) — per-ticker fallback...")
    recovered_count = 0
    fallback_frames = []

    # Per-ticker recovery via ThreadPoolExecutor: each ticker is downloaded
    # independently, so a single bad symbol no longer taints a 50-batch.
    # max_workers=10 keeps pressure on Yahoo low enough to avoid 429s.
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {
            ex.submit(_download_batch_with_retry, [t], settings.DOWNLOAD_PERIOD, 2): t
            for t in missing_or_short
        }
        for fut in as_completed(futs):
            ticker = futs[fut]
            fb_data = fut.result()
            if fb_data.empty:
                continue
            if not isinstance(fb_data.columns, pd.MultiIndex):
                fb_data.columns = pd.MultiIndex.from_product([[ticker], fb_data.columns])
            new_len = len(fb_data[ticker].dropna()) if ticker in fb_data else 0
            old_len = len(data[ticker].dropna()) if ticker in data else 0
            if new_len > old_len:
                recovered_count += 1
            fallback_frames.append(fb_data)

    if fallback_frames:
        recovered_tickers = set()
        for fb_df in fallback_frames:
            if isinstance(fb_df.columns, pd.MultiIndex):
                recovered_tickers.update(fb_df.columns.get_level_values(0).unique())

        bad_cols = [c for c in data.columns if c[0] in recovered_tickers]
        data = data.drop(columns=bad_cols, errors='ignore')

        if hasattr(data.index, 'tz') and data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        
        for i in range(len(fallback_frames)):
            if hasattr(fallback_frames[i].index, 'tz') and fallback_frames[i].index.tz is not None:
                fallback_frames[i].index = fallback_frames[i].index.tz_localize(None)

        data = pd.concat([data] + fallback_frames, axis=1)

    if recovered_count > 0:
        print(f"Successfully recovered full data for {recovered_count} tickers using fallback batches!")
    else:
        print("Fallback pass complete. No additional tickers could be recovered (likely delisted or too new).")

    return data


def fetch_data(tickers: list[str]) -> pd.DataFrame:
    """
    Download market data via yfinance with PyArrow Parquet caching.
    Cache expires after CACHE_MAX_AGE_HOURS.
    """
    project_root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    cache_file = os.path.join(project_root, settings.CACHE_FILENAME)

    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < settings.CACHE_MAX_AGE_HOURS * 3600:
            print("Loading market data from local cache (super fast!)...", flush=True)
            return pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)

    # Note: Legacy PKL cache is ignored in V2 to enforce transition to Parquet
    print(f"Downloading data for {len(tickers)} tickers in batches to prevent rate limits...", flush=True)

    batch_size = 500
    all_data_frames = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = ((len(tickers) - 1) // batch_size) + 1
        print(f"Downloading batch {batch_num}/{total_batches} ({len(batch)} tickers)...", flush=True)

        batch_data = _download_batch_with_retry(batch, settings.DOWNLOAD_PERIOD)
        if not batch_data.empty:
            all_data_frames.append(batch_data)

        time.sleep(1.5)  # Pause to avoid 429 Too Many Requests

    if not all_data_frames:
        print("All downloads failed, returning empty DataFrame.")
        return pd.DataFrame()

    for i in range(len(all_data_frames)):
        if hasattr(all_data_frames[i].index, 'tz') and all_data_frames[i].index.tz is not None:
            all_data_frames[i].index = all_data_frames[i].index.tz_localize(None)

    data = pd.concat(all_data_frames, axis=1)

    if not data.empty and isinstance(data.columns, pd.MultiIndex):
        data = _recover_missing_data(data, tickers)

    # Ensure no duplicate columns before saving to parquet
    if isinstance(data.columns, pd.MultiIndex):
        data = data.loc[:, ~data.columns.duplicated(keep='last')]

    # Ensure column names are explicitly strings if they aren't, to keep pyarrow perfectly happy
    # PyArrow inherently handles MultiIndex now, but just checking type consistency isn't bad.
    data.to_parquet(cache_file, engine=settings.PARQUET_ENGINE)
    print(f"Saved optimized cache to {cache_file}.")

    return data
