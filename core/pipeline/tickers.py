"""Ticker-universe loading and refresh helpers."""
from __future__ import annotations

import os
import time

import pandas as pd

from config import settings
from core.pipeline.ticker_admission import (
    load_admission,
    record_directory_rejections,
    save_admission,
    screen_directory_rows,
    screen_symbols,
)


def _config_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config')
    )


def _project_root() -> str:
    return os.path.dirname(_config_dir())


def _default_ticker_csv_path() -> str:
    return os.path.join(_config_dir(), 'tickers.csv')


def _default_skiplist_path() -> str:
    filename = getattr(settings, "TICKER_SKIPLIST_FILENAME", "ticker_skiplist.txt")
    if os.path.isabs(filename):
        return filename
    return os.path.join(_config_dir(), filename)


def _default_admission_path() -> str:
    filename = getattr(settings, "TICKER_ADMISSION_FILENAME", "ticker_admission.json")
    if os.path.isabs(filename):
        return filename
    return os.path.join(_project_root(), filename)


def _load_skiplist(path: str | None = None) -> set[str]:
    """Load one-symbol-per-line manual skips; comments start with ``#``."""
    path = path or _default_skiplist_path()
    if not path or not os.path.exists(path):
        return set()
    skiplist: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                symbol = line.split("#", 1)[0].strip().upper()
                if symbol:
                    skiplist.add(symbol)
    except Exception as e:
        print(f"Warning: could not read ticker skip-list {path}: {e}", flush=True)
    return skiplist


def _format_filter_stats(stats: dict[str, int]) -> str:
    parts = []
    if stats.get("special_issue"):
        parts.append(f"{stats['special_issue']} rights/units/warrants")
    if stats.get("invalid_instrument"):
        parts.append(f"{stats['invalid_instrument']} non-common instruments")
    if stats.get("manual_skip"):
        parts.append(f"{stats['manual_skip']} manual skip-list")
    if stats.get("invalid"):
        parts.append(f"{stats['invalid']} invalid")
    if stats.get("duplicate"):
        parts.append(f"{stats['duplicate']} duplicate")
    return f" (filtered {', '.join(parts)})" if parts else ""


def get_tickers(csv_path: str | None = None) -> list[str]:
    """
    Load ticker universe from CSV. Falls back to the NASDAQ Trader FTP dump
    (common-stock filter applied), then caches result to CSV for future runs.
    """
    if csv_path is None:
        csv_path = _default_ticker_csv_path()

    skiplist = _load_skiplist()

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
    
                tickers, stats = screen_symbols(raw_tickers, skiplist)
                print(f"Loaded {len(tickers)} tickers from {csv_path} "
                      f"(Age: {file_age_days:.1f} days)"
                      f"{_format_filter_stats(stats)}",
                      flush=True)
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
            
        tickers, stats, rejected = screen_directory_rows(df_table, skiplist)
        if rejected and getattr(settings, "TICKER_ADMISSION_ENABLED", True):
            path = _default_admission_path()
            admission = load_admission(path)
            record_directory_rejections(admission, rejected)
            save_admission(path, admission)
            print(f"Recorded {len(rejected)} directory reject(s) in {path}.", flush=True)

        # screen_directory_rows preserves original order while deduping.
        print(f"Successfully fetched {len(tickers)} screenable US equities"
              f"{_format_filter_stats(stats)}!",
              flush=True)

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
