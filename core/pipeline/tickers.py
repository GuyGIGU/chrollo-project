"""Ticker-universe loading and refresh helpers."""
from __future__ import annotations

import os
import time

import pandas as pd

from config import settings


MAX_TICKER_LENGTH = 4


def _screened_tickers(raw_tickers) -> list[str]:
    """Return unique plain-alpha tickers that belong in the screener universe."""
    tickers: list[str] = []
    seen: set[str] = set()
    for raw in raw_tickers:
        ticker = str(raw).strip().upper()
        if not ticker or not ticker.isalpha() or len(ticker) > MAX_TICKER_LENGTH:
            continue
        if ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def _cache_needs_rewrite(raw_tickers, tickers: list[str]) -> bool:
    cached = [str(t).strip().upper() for t in raw_tickers if str(t).strip()]
    return cached != tickers


def get_tickers(csv_path: str | None = None) -> list[str]:
    """
    Load ticker universe from CSV. Falls back to the NASDAQ Trader FTP dump
    (common-stock filter applied), then caches result to CSV for future runs.
    """
    if csv_path is None:
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config', 'tickers.csv'
        )
        csv_path = os.path.normpath(csv_path)

    if os.path.exists(csv_path):
        file_age_days = (time.time() - os.path.getmtime(csv_path)) / (24 * 3600)
        if file_age_days < settings.TICKER_CACHE_MAX_AGE_DAYS:
            try:
                df = pd.read_csv(csv_path)
                if 'Ticker' in df.columns:
                    raw_tickers = df['Ticker'].dropna().tolist()
                elif 'Symbol' in df.columns:
                    raw_tickers = df['Symbol'].dropna().tolist()
                else:
                    raw_tickers = df.iloc[:, 0].dropna().tolist()

                tickers = _screened_tickers(raw_tickers)
                if _cache_needs_rewrite(raw_tickers, tickers):
                    pd.DataFrame({'Ticker': tickers}).to_csv(csv_path, index=False)
    
                print(f"Loaded {len(tickers)} <=4-letter tickers from {csv_path} (Age: {file_age_days:.1f} days)", flush=True)
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
            # Accept plain-alpha tickers up to 4 chars. Longer symbols are a
            # common source of stale/delisted Yahoo lookups that slow scans down.
            # Dotted/class-share symbols like BRK.B remain skipped because
            # yfinance handles them inconsistently.
            tickers = _screened_tickers(raw_tickers)

        print(f"Successfully fetched and filtered {len(tickers)} <=4-letter common US equities!", flush=True)

        # Save to static CSV
        pd.DataFrame({'Ticker': tickers}).to_csv(csv_path, index=False)
        print(f"Saved primary universe to '{csv_path}'. It will be cached for {settings.TICKER_CACHE_MAX_AGE_DAYS} day(s).")
        return tickers
    except Exception as e:
        print(f"Could not fetch from NASDAQ FTP: {e}.")
        print("Falling back to the 15-stock sample list.")
        return [
            'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD', 'META', 'AMZN', 'GOOG',
            'PLTR', 'SNOW', 'CRWD', 'UBER', 'NFLX', 'SMCI', 'ARM'
        ]
