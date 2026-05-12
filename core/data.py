"""
Data acquisition module — ticker loading, market data download, and caching.
"""
from __future__ import annotations

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from config import settings


# ────────────────────────────────────────────────────────────────
# Cache path helpers
# ────────────────────────────────────────────────────────────────
def _project_root() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def _cache_paths() -> tuple[str, str]:
    root = _project_root()
    return (
        os.path.join(root, settings.CACHE_FILENAME),
        os.path.join(root, settings.CACHE_META_FILENAME),
    )


def _read_meta(meta_path: str) -> dict:
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_meta(meta_path: str, meta: dict) -> None:
    tmp = meta_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    os.replace(tmp, meta_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_market_hours() -> bool:
    """US equity market hours: 09:30–16:00 ET, Monday–Friday."""
    ny = datetime.now(ZoneInfo("America/New_York"))
    if ny.weekday() >= 5:
        return False
    minutes = ny.hour * 60 + ny.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def _atomic_write_parquet(data: pd.DataFrame, path: str) -> None:
    tmp = path + '.tmp'
    data.to_parquet(tmp, engine=settings.PARQUET_ENGINE)
    os.replace(tmp, path)


def _market_context_path() -> str:
    return os.path.join(_project_root(), settings.MARKET_CONTEXT_FILENAME)


def get_market_context(data: pd.DataFrame,
                       ticker_frames: dict[str, pd.DataFrame]) -> tuple[float, float | None]:
    """
    Return ``(spy_6m_return, breadth_pct)``. Cached in a JSON sidecar with a
    TTL of 1h during market hours, 12h otherwise. Recomputed if the cached
    SPY-last-bar-date doesn't match the parquet's current SPY last bar.

    Inputs:
    - ``data``: full parquet panel (must include SPY as a top-level column key
      if SPY 6m return is to be computed). If SPY is missing, returns 0.0 for
      the RS reference (consistent with the previous fallback behavior).
    - ``ticker_frames``: per-ticker DataFrames used to compute breadth.
    """
    path = _market_context_path()
    cached = _read_meta(path)  # JSON read/write helpers are general-purpose

    spy = settings.SPY_SYMBOL
    spy_last_bar = None
    if isinstance(data.columns, pd.MultiIndex) and spy in data.columns.get_level_values(0):
        try:
            spy_close_series = data[spy]['Close'].dropna()
            if not spy_close_series.empty:
                spy_last_bar = spy_close_series.index[-1].strftime('%Y-%m-%d')
        except KeyError:
            spy_last_bar = None

    ttl_hours = (settings.MARKET_CONTEXT_TTL_HOURS_MARKET if _is_market_hours()
                 else settings.MARKET_CONTEXT_TTL_HOURS_OFFHOURS)

    if cached and 'computed_at' in cached:
        try:
            cached_ts = datetime.fromisoformat(cached['computed_at'])
            age_hours = (datetime.now(timezone.utc) - cached_ts).total_seconds() / 3600.0
            if (age_hours < ttl_hours
                    and cached.get('spy_last_bar_date') == spy_last_bar
                    and 'spy_6m_return' in cached
                    and 'breadth_pct' in cached):
                spy_ret = float(cached['spy_6m_return'])
                bp = cached['breadth_pct']
                bp_val = float(bp) if bp is not None else None
                print(f"Market context loaded from cache (age {age_hours:.2f}h, "
                      f"TTL {ttl_hours}h): SPY 6m={spy_ret*100:.2f}%, "
                      f"breadth={'n/a' if bp_val is None else f'{bp_val*100:.1f}%'}",
                      flush=True)
                return spy_ret, bp_val
        except Exception:
            pass

    # Compute fresh.
    spy_6m_return = 0.0
    if spy_last_bar is not None:
        try:
            spy_close = data[spy]['Close'].dropna()
            if len(spy_close) > settings.RS_LOOKBACK_BARS:
                spy_6m_return = float(
                    spy_close.iloc[-1] / spy_close.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0
                )
                print(f"SPY 6m return: {spy_6m_return*100:.2f}% (RS reference)")
        except Exception as e:
            print(f"  [SPY compute failed: {type(e).__name__}: {e}] — RS bonus disabled this run")

    breadth_pct: float | None = None
    if ticker_frames:
        breadth_count = 0
        breadth_total = 0
        for tdf in ticker_frames.values():
            close = tdf['Close']
            if len(close) >= 50:
                last_50_mean = float(close.iloc[-50:].mean())
                if pd.notna(last_50_mean):
                    breadth_total += 1
                    if float(close.iloc[-1]) > last_50_mean:
                        breadth_count += 1
        if breadth_total > 0:
            breadth_pct = breadth_count / breadth_total
            print(f"Market breadth (Close > SMA_50): {breadth_pct*100:.1f}% "
                  f"({breadth_count}/{breadth_total})")

    _write_meta(path, {
        'spy_6m_return': spy_6m_return,
        'breadth_pct': breadth_pct,
        'spy_last_bar_date': spy_last_bar,
        'computed_at': _now_iso(),
    })
    return spy_6m_return, breadth_pct


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


def _batched_download(tickers: list[str], period_or_dates: dict, label: str) -> pd.DataFrame:
    """
    Download a list of tickers in 500-batches with retries and rate-limit
    sleeps. ``period_or_dates`` is either ``{'period': '2y'}`` (full refetch)
    or ``{'start': date, 'end': date}`` (incremental).
    """
    batch_size = 500
    frames: list[pd.DataFrame] = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = ((len(tickers) - 1) // batch_size) + 1
        print(f"  {label} batch {batch_num}/{total_batches} ({len(batch)} tickers)...", flush=True)

        batch_data = _download_batch_with_retry_kwargs(batch, period_or_dates)
        if not batch_data.empty:
            frames.append(batch_data)

        time.sleep(1.5)  # Avoid 429s

    if not frames:
        return pd.DataFrame()

    for j in range(len(frames)):
        if hasattr(frames[j].index, 'tz') and frames[j].index.tz is not None:
            frames[j].index = frames[j].index.tz_localize(None)

    return pd.concat(frames, axis=1)


def _download_batch_with_retry_kwargs(batch: list[str], period_or_dates: dict,
                                      max_retries: int = 3) -> pd.DataFrame:
    """Variant of _download_batch_with_retry that accepts either period= or start/end=."""
    for attempt in range(1, max_retries + 1):
        try:
            batch_data = yf.download(
                batch,
                group_by='ticker',
                threads=True,
                progress=False,
                timeout=30,
                **period_or_dates,
            )
            if not batch_data.empty:
                if len(batch) == 1 and not isinstance(batch_data.columns, pd.MultiIndex):
                    batch_data.columns = pd.MultiIndex.from_product([batch, batch_data.columns])
                return batch_data
        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"    Attempt {attempt}/{max_retries} failed ({e}). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"    Batch failed after {max_retries} retries: {e}")

    return pd.DataFrame()


def _detect_splits(cached: pd.DataFrame, fresh: pd.DataFrame,
                   cached_tickers: list[str]) -> tuple[bool, list[str]]:
    """
    Probe a random sample of cached tickers for split-induced price drift on
    the overlap window.

    Returns ``(force_full_refetch, drifted_tickers)``:
    - ``force_full_refetch=True`` if a high enough fraction of probed tickers
      drift to suggest broad corporate-action issues (cold path recommended).
    - ``drifted_tickers`` is the per-ticker list that drifted; if force is
      False these can be re-fetched individually.
    """
    sample_size = min(settings.SPLIT_PROBE_SAMPLE_SIZE, len(cached_tickers))
    # Seed by today's date so the sample rotates daily but is reproducible
    # within a single day — gives broad coverage across the universe over time
    # while keeping a single day's run debuggable.
    seed = int(datetime.now(timezone.utc).strftime('%Y%m%d'))
    rng = random.Random(seed)
    sample = rng.sample(cached_tickers, sample_size) if sample_size else []

    ref = settings.SPLIT_PROBE_REFERENCE_SYMBOL
    if ref in cached_tickers and ref not in sample:
        sample.append(ref)

    drifted: list[str] = []
    probed = 0

    for ticker in sample:
        if ticker not in cached or ticker not in fresh:
            continue
        try:
            cached_close = cached[ticker]['Close'].dropna()
            fresh_close = fresh[ticker]['Close'].dropna()
        except KeyError:
            continue

        overlap_idx = cached_close.index.intersection(fresh_close.index)
        if len(overlap_idx) < 2:
            continue

        c = cached_close.loc[overlap_idx]
        f = fresh_close.loc[overlap_idx]
        # Compare ratio across the overlap window. A split shows up as a
        # consistent constant ratio (e.g., 0.5 for a 2:1) across every bar.
        # Random noise won't be consistent. We flag if mean relative diff
        # exceeds the threshold AND the ratio is roughly constant.
        ratios = (f / c).dropna()
        if ratios.empty:
            continue
        ratio_mean = float(ratios.mean())
        ratio_std = float(ratios.std()) if len(ratios) > 1 else 0.0
        rel_drift = abs(ratio_mean - 1.0)
        # Constant-ratio fingerprint: low std relative to drift magnitude
        is_constant = ratio_std < max(0.001, 0.2 * rel_drift)

        probed += 1
        if rel_drift > settings.SPLIT_PROBE_DRIFT_THRESHOLD and is_constant:
            drifted.append(ticker)

    if probed == 0:
        return (False, [])

    drift_pct = len(drifted) / probed
    force_full = drift_pct > settings.SPLIT_PROBE_UNIVERSE_DRIFT_PCT
    if drifted:
        print(f"  Split-probe: {len(drifted)}/{probed} tickers show price drift "
              f"({drift_pct*100:.1f}%); force_full_refetch={force_full}", flush=True)
    else:
        print(f"  Split-probe: clean ({probed} tickers checked).", flush=True)
    return (force_full, drifted)


def _full_refetch(tickers_to_fetch: list[str]) -> pd.DataFrame:
    """Cold path: download full DOWNLOAD_PERIOD history for every ticker."""
    print(f"Downloading data for {len(tickers_to_fetch)} tickers in batches to prevent rate limits...", flush=True)
    data = _batched_download(tickers_to_fetch, {'period': settings.DOWNLOAD_PERIOD}, "Download")
    if data.empty:
        print("All downloads failed, returning empty DataFrame.")
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        data = _recover_missing_data(data, tickers_to_fetch)
        data = data.loc[:, ~data.columns.duplicated(keep='last')]
    return data


def _trim_to_period(data: pd.DataFrame, period: str) -> pd.DataFrame:
    """Trim DataFrame index to the trailing period window (e.g., '2y')."""
    if data.empty:
        return data
    if period.endswith('y'):
        years = int(period[:-1])
        cutoff = data.index.max() - pd.Timedelta(days=365 * years + 5)
    elif period.endswith('mo'):
        months = int(period[:-2])
        cutoff = data.index.max() - pd.Timedelta(days=30 * months + 2)
    else:
        return data
    return data.loc[data.index >= cutoff]


def fetch_data(tickers: list[str]) -> pd.DataFrame:
    """
    Download market data via yfinance with PyArrow Parquet caching.

    Daily-run strategy:
    - If cache is fresh (< TTL_FRESH_HOURS), return it as-is.
    - If cache is stale but recent (gap ≤ INCREMENTAL_MAX_GAP_BDAYS) and last
      full refresh is within FULL_REFRESH_INTERVAL_DAYS, do an incremental
      fetch of just the missing bars + an overlap window. Probe the overlap
      for split-induced price drift; re-fetch any drifted tickers in full.
    - Otherwise (or on first run / corruption / weekly refresh due), do a
      full cold refetch of the entire DOWNLOAD_PERIOD.

    SPY is always included in the download so the screener can read it from
    the same parquet without a separate yfinance call.
    """
    cache_file, meta_file = _cache_paths()

    spy = settings.SPY_SYMBOL
    tickers_with_spy = list(tickers) + ([spy] if spy not in tickers else [])

    # ── Fast path: fresh cache ─────────────────────────────────────────────
    meta = _read_meta(meta_file)
    if os.path.exists(cache_file):
        cache_age_hours = (time.time() - os.path.getmtime(cache_file)) / 3600.0
        ttl = (settings.TTL_FRESH_HOURS_MARKET if _is_market_hours()
               else settings.TTL_FRESH_HOURS_OFFHOURS)
        if cache_age_hours < ttl:
            print(f"Loading market data from local cache ({cache_age_hours:.2f}h old, "
                  f"TTL {ttl}h)...", flush=True)
            return pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)

    # ── Decide cold vs. incremental ────────────────────────────────────────
    cached: pd.DataFrame | None = None
    if os.path.exists(cache_file):
        try:
            cached = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
            if hasattr(cached.index, 'tz') and cached.index.tz is not None:
                cached.index = cached.index.tz_localize(None)
        except Exception as e:
            print(f"  Cached parquet unreadable ({e}); falling back to full refetch.")
            cached = None

    last_full_refresh = meta.get('last_full_refresh')
    weekly_refresh_due = True
    if last_full_refresh:
        try:
            ts = datetime.fromisoformat(last_full_refresh)
            age_days = (datetime.now(timezone.utc) - ts).days
            weekly_refresh_due = age_days >= settings.FULL_REFRESH_INTERVAL_DAYS
        except Exception:
            weekly_refresh_due = True

    gap_bdays = None
    if cached is not None and not cached.empty:
        last_cached_date = cached.index.max().normalize()
        today = pd.Timestamp.now().normalize()
        gap_bdays = len(pd.bdate_range(last_cached_date, today)) - 1

    # Cache exists, weekly refresh not due, and we already have the latest
    # trading day's bar → just refresh mtime and return. This avoids a full
    # refetch when the cache is "stale" only by clock-time (e.g., we ran 13h
    # ago but it's still the same trading day).
    if (cached is not None and not cached.empty and gap_bdays == 0
            and not weekly_refresh_due):
        print(f"Cache last bar is current ({cached.index.max().date()}); "
              f"touching mtime and returning.", flush=True)
        _atomic_write_parquet(cached, cache_file)
        meta['last_modified'] = _now_iso()
        _write_meta(meta_file, meta)
        return cached

    do_incremental = (
        cached is not None
        and not cached.empty
        and gap_bdays is not None
        and 1 <= gap_bdays <= settings.INCREMENTAL_MAX_GAP_BDAYS
        and not weekly_refresh_due
    )

    if do_incremental:
        data = _incremental_fetch(cached, tickers_with_spy, gap_bdays)
        if data is not None and not data.empty:
            data = _trim_to_period(data, settings.DOWNLOAD_PERIOD)
            data = data.loc[:, ~data.columns.duplicated(keep='last')]
            _atomic_write_parquet(data, cache_file)
            meta['last_modified'] = _now_iso()
            # Preserve last_full_refresh on incremental writes.
            _write_meta(meta_file, meta)
            print(f"Saved incremental update to {cache_file}. New last bar: "
                  f"{data.index.max().date()}.", flush=True)
            return data
        # Fall through to cold path if incremental returned nothing usable.
        print("  Incremental fetch yielded no usable data; falling back to full refetch.")

    # ── Cold path ──────────────────────────────────────────────────────────
    data = _full_refetch(tickers_with_spy)
    if data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data = data.loc[:, ~data.columns.duplicated(keep='last')]

    _atomic_write_parquet(data, cache_file)
    meta = {
        'last_full_refresh': _now_iso(),
        'last_modified': _now_iso(),
    }
    _write_meta(meta_file, meta)
    print(f"Saved optimized cache to {cache_file}.")
    return data


def _incremental_fetch(cached: pd.DataFrame, tickers_with_spy: list[str],
                       gap_bdays: int) -> pd.DataFrame | None:
    """
    Fetch only the last (overlap + gap) business days, probe for splits, then
    merge into the cached panel. Returns the merged DataFrame on success or
    None on a soft failure that should fall through to the cold path.
    """
    last_cached_date = cached.index.max().normalize()
    today = pd.Timestamp.now().normalize()
    overlap = settings.INCREMENTAL_OVERLAP_BDAYS
    start = (last_cached_date - pd.tseries.offsets.BDay(overlap)).normalize()
    end = (today + pd.Timedelta(days=1)).normalize()  # yfinance end is exclusive

    print(f"Incremental update: gap={gap_bdays} bday(s), fetching "
          f"{start.date()} → {end.date()} ({len(tickers_with_spy)} tickers)...",
          flush=True)

    fresh = _batched_download(
        tickers_with_spy,
        {'start': start.strftime('%Y-%m-%d'), 'end': end.strftime('%Y-%m-%d')},
        "Incremental",
    )
    if fresh.empty or not isinstance(fresh.columns, pd.MultiIndex):
        print("  Incremental download returned empty/malformed data.")
        return None

    cached_tickers = list({c[0] for c in cached.columns if isinstance(c, tuple)})

    # Split probe on the overlap window.
    force_full, drifted = _detect_splits(cached, fresh, cached_tickers)
    if force_full:
        return None  # Caller will fall through to cold path

    # Drop drifted tickers' columns from both cached and fresh; we'll re-fetch
    # their full 2y individually after the merge.
    if drifted:
        drop_cols = [c for c in cached.columns if isinstance(c, tuple) and c[0] in drifted]
        cached = cached.drop(columns=drop_cols, errors='ignore')
        fresh_drop = [c for c in fresh.columns if isinstance(c, tuple) and c[0] in drifted]
        fresh = fresh.drop(columns=fresh_drop, errors='ignore')

    # Merge: keep only fresh rows strictly after last_cached_date, then concat.
    new_rows = fresh.loc[fresh.index > last_cached_date]
    if new_rows.empty:
        print("  No new bars beyond cached last date (market closed today?).")
        merged = cached
    else:
        # Align columns: take union, fill NaN where needed.
        merged = pd.concat([cached, new_rows], axis=0)
        merged = merged[~merged.index.duplicated(keep='last')]
        merged = merged.sort_index()

    # New listings: tickers in universe but absent from the cached columns
    # → fetch their full history via the existing recovery path.
    cached_ticker_set = set(cached_tickers)
    new_listings = [t for t in tickers_with_spy if t not in cached_ticker_set]
    if new_listings:
        print(f"  Fetching full history for {len(new_listings)} new listing(s)...", flush=True)
        merged = _recover_missing_data(merged, new_listings)

    # Drifted tickers: fetch their full 2y individually.
    if drifted:
        print(f"  Refetching {len(drifted)} split-drifted ticker(s) in full...", flush=True)
        merged = _recover_missing_data(merged, drifted)

    return merged
