"""Market-data download, split-drift checks, and parquet cache orchestration."""
from __future__ import annotations

import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from config import settings
from core.pipeline.cache import (
    _atomic_write_parquet,
    _cache_paths,
    _is_market_hours,
    _now_iso,
    _read_meta,
    _write_meta,
)
from core.pipeline.data_freshness import (
    close_coverage_on,
    has_all_closes_on,
    last_complete_reference_date,
    symbols_missing_closes_on,
)
from core.pipeline.fetch_health import (
    count_quarantined,
    is_healthy,
    load_quarantine,
    present_tickers,
    record_results,
    save_quarantine,
    split_active,
    summarize,
)
from core.pipeline.market_calendar import latest_completed_session, session_gap


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


def _has_all_symbols(data: pd.DataFrame, symbols: list[str]) -> bool:
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return False
    present = set(data.columns.get_level_values(0))
    return all(symbol in present for symbol in symbols)


def _patch_market_data(base: pd.DataFrame, patch: pd.DataFrame) -> pd.DataFrame:
    if patch.empty:
        return base
    merged = base.reindex(base.index.union(patch.index)).sort_index()
    for column in patch.columns:
        if column in merged.columns:
            merged[column] = patch[column].combine_first(merged[column])
        else:
            merged[column] = patch[column]
    return merged


def _repair_latest_session(
    data: pd.DataFrame,
    symbols: list[str],
    expected_session: pd.Timestamp,
    min_latest_coverage: float,
    label: str,
) -> pd.DataFrame:
    coverage = close_coverage_on(data, symbols, expected_session)
    if coverage.ratio >= min_latest_coverage:
        return data

    missing = symbols_missing_closes_on(data, symbols, expected_session)
    if not missing:
        return data

    batch_size = max(1, int(getattr(settings, "LATEST_REPAIR_BATCH_SIZE", 100)))
    sleep_seconds = max(0.0, float(getattr(settings, "LATEST_REPAIR_SLEEP_SECONDS", 2.0)))
    start = (expected_session - pd.tseries.offsets.BDay(settings.INCREMENTAL_OVERLAP_BDAYS)).normalize()
    end = (expected_session + pd.Timedelta(days=1)).normalize()
    frames: list[pd.DataFrame] = []

    print(f"  {label} latest-session coverage is {coverage.format()} for "
          f"{expected_session.date()} (required >= {min_latest_coverage:.0%}); "
          f"repairing {len(missing)} missing symbol(s) in {batch_size}-batches...",
          flush=True)

    total_batches = ((len(missing) - 1) // batch_size) + 1
    for i in range(0, len(missing), batch_size):
        batch = missing[i:i + batch_size]
        batch_num = i // batch_size + 1
        print(f"  {label} repair batch {batch_num}/{total_batches} ({len(batch)} tickers)...",
              flush=True)
        repaired = _download_batch_with_retry_kwargs(
            batch,
            {'start': start.strftime('%Y-%m-%d'), 'end': end.strftime('%Y-%m-%d')},
            max_retries=2,
        )
        if not repaired.empty and isinstance(repaired.columns, pd.MultiIndex):
            if hasattr(repaired.index, 'tz') and repaired.index.tz is not None:
                repaired.index = repaired.index.tz_localize(None)
            frames.append(repaired)
        time.sleep(sleep_seconds)

    if not frames:
        print(f"  {label} repair yielded no usable data.", flush=True)
        return data

    repaired_panel = pd.concat(frames, axis=1)
    repaired_panel = repaired_panel.loc[:, ~repaired_panel.columns.duplicated(keep='last')]
    repaired = _patch_market_data(data, repaired_panel)
    repaired_coverage = close_coverage_on(repaired, symbols, expected_session)
    print(f"  {label} repair coverage after patch: {repaired_coverage.format()}.",
          flush=True)
    return repaired


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

    Index symbols are always included in the download so the screener can read
    market context from the same parquet without separate yfinance calls.
    """
    t_fetch_start = time.time()
    cache_file, meta_file = _cache_paths()

    index_symbols = getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL])
    tickers_with_indexes = list(tickers)
    for symbol in index_symbols:
        if symbol not in tickers_with_indexes:
            tickers_with_indexes.append(symbol)

    # Dead-ticker quarantine: skip symbols that keep returning nothing (re-probed
    # after a cooldown). Cheap, runs every fetch; index symbols are never skipped.
    quar_path = os.path.join(os.path.dirname(meta_file),
                             getattr(settings, "QUARANTINE_FILENAME", "ticker_quarantine.json"))
    quarantine = load_quarantine(quar_path) if getattr(settings, "QUARANTINE_ENABLED", True) else {}
    active_symbols, skipped_quarantined = split_active(
        tickers_with_indexes, quarantine, index_symbols=index_symbols
    )
    if skipped_quarantined:
        print(f"  Quarantine: skipping {len(skipped_quarantined)} repeatedly-empty "
              f"ticker(s); re-probe in <= {getattr(settings, 'QUARANTINE_COOLDOWN_DAYS', 7)}d.",
              flush=True)
    tickers_with_indexes = active_symbols
    requested_non_index = [t for t in tickers_with_indexes if t not in index_symbols]

    expected_session = latest_completed_session()
    min_latest_coverage = getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)

    # ── Fast path: fresh cache ─────────────────────────────────────────────
    meta = _read_meta(meta_file)
    if os.path.exists(cache_file):
        cache_age_hours = (time.time() - os.path.getmtime(cache_file)) / 3600.0
        ttl = (settings.TTL_FRESH_HOURS_MARKET if _is_market_hours()
               else settings.TTL_FRESH_HOURS_OFFHOURS)
        if cache_age_hours < ttl:
            cached_data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
            last_reference_date = last_complete_reference_date(cached_data, index_symbols)
            coverage = close_coverage_on(cached_data, tickers_with_indexes, expected_session)
            if (_has_all_symbols(cached_data, index_symbols)
                    and last_reference_date is not None
                    and last_reference_date >= expected_session
                    and coverage.ratio >= min_latest_coverage):
                print(f"Loading market data from local cache ({cache_age_hours:.2f}h old, "
                      f"TTL {ttl}h)...", flush=True)
                return cached_data
            print(f"Local cache is fresh by mtime but latest-session coverage is "
                  f"{coverage.format()} for {expected_session.date()} "
                  f"(required >= {min_latest_coverage:.0%}); updating cache.", flush=True)

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
    last_cached_date = None
    if cached is not None and not cached.empty:
        last_cached_date = (
            last_complete_reference_date(cached, index_symbols)
            or cached.index.max().normalize()
        )
        gap_bdays = session_gap(last_cached_date, expected_session)
        latest_coverage = close_coverage_on(cached, tickers_with_indexes, expected_session)
    else:
        latest_coverage = None

    # Cache exists, weekly refresh not due, and we already have the latest
    # trading day's bar → just refresh mtime and return. This avoids a full
    # refetch when the cache is "stale" only by clock-time (e.g., we ran 13h
    # ago but it's still the same trading day).
    if (cached is not None and not cached.empty and gap_bdays == 0
            and not weekly_refresh_due
            and _has_all_symbols(cached, index_symbols)
            and latest_coverage is not None
            and latest_coverage.ratio >= min_latest_coverage):
        print(f"Cache last market-regime bar is current ({last_cached_date.date()}); "
              f"touching mtime and returning.", flush=True)
        _atomic_write_parquet(cached, cache_file)
        meta['last_modified'] = _now_iso()
        _write_meta(meta_file, meta)
        return cached
    if (cached is not None and not cached.empty and gap_bdays == 0
            and not weekly_refresh_due):
        coverage_text = latest_coverage.format() if latest_coverage else "none"
        print(f"Cache last market-regime bar is current but latest-session coverage is "
              f"{coverage_text} (required >= {min_latest_coverage:.0%}); "
              "falling back to full refetch.", flush=True)

    do_incremental = (
        cached is not None
        and not cached.empty
        and gap_bdays is not None
        and 1 <= gap_bdays <= settings.INCREMENTAL_MAX_GAP_BDAYS
        and not weekly_refresh_due
    )

    if do_incremental:
        data = _incremental_fetch(cached, tickers_with_indexes, gap_bdays)
        if data is not None and not data.empty:
            data = _trim_to_period(data, settings.DOWNLOAD_PERIOD)
            data = data.loc[:, ~data.columns.duplicated(keep='last')]
            _atomic_write_parquet(data, cache_file)
            meta['last_modified'] = _now_iso()
            # Health only — the cold full-refetch owns quarantine updates (a ticker
            # absent from a small incremental window is not necessarily dead).
            returned_active = present_tickers(data) & set(requested_non_index)
            meta['fetch_health'] = summarize(
                "incremental", requested_non_index, returned_active,
                len(skipped_quarantined), 0, count_quarantined(quarantine),
                time.time() - t_fetch_start,
            )
            # Preserve last_full_refresh on incremental writes.
            _write_meta(meta_file, meta)
            print(f"Saved incremental update to {cache_file}. New last bar: "
                  f"{data.index.max().date()}.", flush=True)
            return data
        # Fall through to cold path if incremental returned nothing usable.
        print("  Incremental fetch yielded no usable data; falling back to full refetch.")

    # ── Cold path ──────────────────────────────────────────────────────────
    data = _full_refetch(tickers_with_indexes)
    if data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data = data.loc[:, ~data.columns.duplicated(keep='last')]

    data = _repair_latest_session(
        data,
        tickers_with_indexes,
        expected_session,
        min_latest_coverage,
        "Full refetch",
    )
    coverage = close_coverage_on(data, tickers_with_indexes, expected_session)
    if (not has_all_closes_on(data, index_symbols, expected_session)
            or coverage.ratio < min_latest_coverage):
        # Unhealthy cold run (likely rate-limited): record health for observability
        # but DON'T touch quarantine, and preserve last_full_refresh in meta.
        returned_active = present_tickers(data) & set(requested_non_index)
        meta['fetch_health'] = summarize(
            "cold", requested_non_index, returned_active, len(skipped_quarantined),
            0, count_quarantined(quarantine), time.time() - t_fetch_start,
        )
        _write_meta(meta_file, meta)
        print(f"Full refetch latest-session coverage is {coverage.format()} for "
              f"{expected_session.date()} (required >= {min_latest_coverage:.0%}); "
              "keeping existing cache if possible.", flush=True)
        if cached is not None and not cached.empty:
            return cached
        return data

    _atomic_write_parquet(data, cache_file)
    returned = present_tickers(data)
    returned_active = returned & set(requested_non_index)
    newly: list[str] = []
    if getattr(settings, "QUARANTINE_ENABLED", True) and is_healthy(requested_non_index, returned_active):
        quarantine, newly = record_results(quarantine, requested_non_index, returned)
        save_quarantine(quar_path, quarantine)
    health = summarize(
        "cold", requested_non_index, returned_active, len(skipped_quarantined),
        len(newly), count_quarantined(quarantine), time.time() - t_fetch_start,
    )
    meta = {
        'last_full_refresh': _now_iso(),
        'last_modified': _now_iso(),
        'fetch_health': health,
    }
    _write_meta(meta_file, meta)
    if newly:
        print(f"  Quarantine: +{len(newly)} ticker(s) after "
              f"{getattr(settings, 'QUARANTINE_EMPTY_STREAK', 2)} empty refetch(es); "
              f"{health['quarantined_total']} total quarantined.", flush=True)
    print(f"Saved optimized cache to {cache_file} "
          f"(returned {health['returned']}/{health['requested']}).")
    return data


def _incremental_fetch(cached: pd.DataFrame, tickers_with_spy: list[str],
                       gap_bdays: int) -> pd.DataFrame | None:
    """
    Fetch only the last (overlap + gap) business days, probe for splits, then
    merge into the cached panel. Returns the merged DataFrame on success or
    None on a soft failure that should fall through to the cold path.
    """
    index_symbols = getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL])
    expected_session = latest_completed_session()
    min_latest_coverage = getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)
    last_cached_date = (
        last_complete_reference_date(cached, index_symbols)
        or cached.index.max().normalize()
    )
    overlap = settings.INCREMENTAL_OVERLAP_BDAYS
    start = (last_cached_date - pd.tseries.offsets.BDay(overlap)).normalize()
    end = (expected_session + pd.Timedelta(days=1)).normalize()  # yfinance end is exclusive

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

    fresh = _repair_latest_session(
        fresh,
        tickers_with_spy,
        expected_session,
        min_latest_coverage,
        "Incremental",
    )
    fresh_coverage = close_coverage_on(fresh, tickers_with_spy, expected_session)
    if (last_cached_date < expected_session
            and (not has_all_closes_on(fresh, index_symbols, expected_session)
                 or fresh_coverage.ratio < min_latest_coverage)):
        print(f"  Incremental latest-session coverage is {fresh_coverage.format()} "
              f"for {expected_session.date()} (required >= {min_latest_coverage:.0%}); "
              "falling back to full refetch.")
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

    merged_coverage = close_coverage_on(merged, tickers_with_spy, expected_session)
    if (last_cached_date < expected_session
            and (not has_all_closes_on(merged, index_symbols, expected_session)
                 or merged_coverage.ratio < min_latest_coverage)):
        print(f"  Merged cache latest-session coverage is {merged_coverage.format()} "
              f"for {expected_session.date()} (required >= {min_latest_coverage:.0%}); "
              "falling back to full refetch.")
        return None

    return merged
