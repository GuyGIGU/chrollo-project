"""Build the price panel from Yahoo, and repair what comes back.

``_full_refetch`` downloads every ticker's whole ``DOWNLOAD_PERIOD``;
``_incremental_fetch`` downloads the last few sessions, probes the overlap for split
drift and merges them over the cached panel. The repairs both paths use live here
too: per-ticker recovery of missing or short histories, the batched repair of the
latest session's closes, and the cap that drops a forming bar. Reading and writing
the cache is ``downloads``'s job; every request goes through ``yahoo_download``.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from config import settings
from core.pipeline.market_data.data_freshness import (
    close_coverage_on,
    has_all_closes_on,
    last_complete_reference_date,
    symbols_missing_closes_on,
)
from core.pipeline.market_data.market_calendar import latest_completed_session
from core.pipeline.market_data.yahoo_download import (
    _batched_download,
    _download_batch_with_retry,
    _drop_index_tz,
)


def _drop_tickers(frame: pd.DataFrame, tickers) -> pd.DataFrame:
    """``frame`` without any column of ``tickers``."""
    columns = [c for c in frame.columns if isinstance(c, tuple) and c[0] in tickers]
    return frame.drop(columns=columns, errors='ignore')


def _window_through(start: pd.Timestamp, last_session: pd.Timestamp) -> dict:
    """yfinance window kwargs from ``start`` through ``last_session`` (yfinance's end is exclusive)."""
    end = (last_session + pd.Timedelta(days=1)).normalize()
    return {'start': start.strftime('%Y-%m-%d'), 'end': end.strftime('%Y-%m-%d')}


def _short_histories(
    data: pd.DataFrame,
    tickers: list[str],
    min_history_bars: int,
    expected_session: pd.Timestamp,
    skip_current_short: bool,
) -> tuple[list[str], list[str]]:
    """Sort the tickers ``data`` lacks, or holds with fewer than ``min_history_bars``
    closes, into ``(missing_or_short, current_but_short)``. A short history that
    already reaches the expected session is a young listing, not a gap, so it goes
    in the second list, unless ``skip_current_short`` is off."""
    missing_or_short = []
    current_but_short = []
    for ticker in tickers:
        if ticker not in data:
            missing_or_short.append(ticker)
            continue
        try:
            closes = data[ticker]["Close"].dropna()
        except KeyError:
            closes = pd.Series(dtype="float64")
        if len(closes) >= min_history_bars:
            continue
        latest_close = closes.index.max().normalize() if not closes.empty else None
        if (skip_current_short
                and latest_close is not None
                and latest_close >= expected_session):
            current_but_short.append(ticker)
        else:
            missing_or_short.append(ticker)
    return missing_or_short, current_but_short


def _fetch_full_histories(data: pd.DataFrame, tickers: list[str]) -> tuple[list[pd.DataFrame], int]:
    """Download each ticker's full ``DOWNLOAD_PERIOD`` history on its own request, so
    one bad symbol cannot taint the rest. Returns the non-empty frames and how many
    of them hold more bars than ``data`` did."""
    frames: list[pd.DataFrame] = []
    recovered_count = 0
    # max_workers=10 keeps pressure on Yahoo low enough to avoid 429s.
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_download_batch_with_retry, [t], settings.DOWNLOAD_PERIOD, 2): t
            for t in tickers
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            frame = fut.result()
            if frame.empty:
                continue
            new_len = len(frame[ticker].dropna()) if ticker in frame else 0
            old_len = len(data[ticker].dropna()) if ticker in data else 0
            if new_len > old_len:
                recovered_count += 1
            frames.append(frame)
    return frames, recovered_count


def _replace_ticker_columns(data: pd.DataFrame, frames: list[pd.DataFrame]) -> pd.DataFrame:
    """``data`` with every fetched ticker's columns swapped for its fetched frame's.
    The fetched frames go after ``data``'s other columns, on the sorted union of dates."""
    fetched = set()
    for frame in frames:
        fetched.update(frame.columns.get_level_values(0).unique())
    data = _drop_index_tz(_drop_tickers(data, fetched))
    return pd.concat([data] + [_drop_index_tz(frame) for frame in frames], axis=1, sort=True)


def _recover_missing_data(
    data: pd.DataFrame,
    tickers: list[str],
    *,
    skip_current_short: bool = True,
    dropout_guard: bool = True,
) -> pd.DataFrame:
    """
    Check for missing or incomplete data (<200 bars) and attempt to re-download.
    By default, current-but-short histories are left to the admission ledger
    instead of hammering Yahoo every run; new listings and split-drift recovery
    can force a full retry with ``skip_current_short=False`` and
    ``dropout_guard=False``.
    Returns the corrected DataFrame.
    """
    min_history_bars = int(getattr(settings, "ADMISSION_MIN_HISTORY_BARS", 200))
    missing_or_short, current_but_short = _short_histories(
        data, tickers, min_history_bars, latest_completed_session(), skip_current_short
    )

    if current_but_short:
        print(f"Skipping fallback for {len(current_but_short)} current but <{min_history_bars}-bar "
              "ticker(s); admission will recheck later.",
              flush=True)

    if not missing_or_short:
        return data

    if dropout_guard and len(missing_or_short) > len(tickers) * 0.5:
        print(f"Warning: {len(missing_or_short)} dropouts detected. Rate limit severe. Skipping individual fallback to avoid IP ban.")
        return data

    print(f"Validating {len(missing_or_short)} tickers with missing or suspiciously short data (<200 bars) — per-ticker fallback...")
    fallback_frames, recovered_count = _fetch_full_histories(data, missing_or_short)
    if fallback_frames:
        data = _replace_ticker_columns(data, fallback_frames)

    if recovered_count > 0:
        print(f"Successfully recovered full data for {recovered_count} tickers using fallback batches!")
    else:
        print("Fallback pass complete. No additional tickers could be recovered (likely delisted or too new).")

    return data


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


def _drop_forming_rows(data: pd.DataFrame, expected_session: pd.Timestamp) -> pd.DataFrame:
    """Drop bars newer than the latest COMPLETED session.

    A period-based fetch during market hours (an afternoon 'Refresh Data' click)
    includes the current day's PARTIAL bar; once persisted it is
    indistinguishable from a real close, so the evening scan would evaluate and
    permanently archive a mid-session snapshot. The windowed incremental/repair
    fetches already cap via their end date; this is the same cap for the
    period-based cold and per-ticker recovery fetches."""
    if data.empty:
        return data
    return data.loc[data.index <= expected_session]


def _patch_market_data(base: pd.DataFrame, patch: pd.DataFrame) -> pd.DataFrame:
    if patch.empty:
        return base
    # Both frames must have unique column labels — combine_first aligns on
    # labels and a duplicate makes the alignment ambiguous. The incremental
    # merge upstream can leave duplicate (ticker, field) columns in ``base``,
    # so dedupe both sides here (mirrors the patch-side dedupe in
    # _repair_latest_session) before the combine.
    base = base.loc[:, ~base.columns.duplicated(keep='last')]
    patch = patch.loc[:, ~patch.columns.duplicated(keep='last')]
    # ONE whole-frame combine (patch wins on overlap; a NaN patch cell keeps the
    # base value) instead of a per-column loop — ~27,500 getitem/setitem round
    # trips at the full-universe call site, measured 75s -> 29s. combine_first
    # sorts the column union, so reindex back to the loop's order convention:
    # base's columns first, patch-only columns appended in patch order. The
    # merged parquet feeds every structural read — order must not drift.
    merged = patch.combine_first(base)
    base_columns = set(base.columns)
    extra = [column for column in patch.columns if column not in base_columns]
    return merged.reindex(index=base.index.union(patch.index),
                          columns=list(base.columns) + extra)


def _repair_latest_session(
    data: pd.DataFrame,
    symbols: list[str],
    expected_session: pd.Timestamp,
    min_latest_coverage: float,
    label: str,
    dropout_guard: bool = False,
) -> pd.DataFrame:
    coverage = close_coverage_on(data, symbols, expected_session)
    if coverage.ratio >= min_latest_coverage:
        return data

    missing = symbols_missing_closes_on(data, symbols, expected_session)
    if not missing:
        return data

    batch_size = max(1, int(getattr(settings, "LATEST_REPAIR_BATCH_SIZE", 100)))

    # Blast-radius guard, mirroring the >50% dropout skip in _recover_missing_data.
    # When essentially EVERY symbol lacks the latest close, the cause is the session
    # itself — not published, or not a session at all (measured 2026-07-24: Yahoo
    # carries no bar for that Friday while the static NYSE rule calendar says it is a
    # session). Re-asking for the same bar 100 symbols at a time cannot conjure it,
    # and costs ~55 serial batches.
    #
    # OPT-IN, and only for a full-universe caller. ``repair_latest_session_cache``
    # (the manual "Repair N" button) passes ONLY the already-missing symbols, so
    # there ``missing == symbols`` by construction and any fraction test would fire
    # for every N >= 1 — silently turning that button into a no-op. Same reason
    # _recover_missing_data is called with dropout_guard=False on its
    # known-missing-by-construction paths.
    #
    # Also requires the repair to span more than one batch: the cost this avoids is
    # MANY serial batches, so a small universe (us_sectors is 13 symbols) still gets
    # its single cheap attempt rather than being skipped on a fraction alone.
    if dropout_guard and symbols and len(missing) > batch_size:
        max_missing_fraction = float(
            getattr(settings, "LATEST_REPAIR_MAX_MISSING_FRACTION", 0.5)
        )
        if len(missing) > len(symbols) * max_missing_fraction:
            print(f"  {label}: {len(missing)}/{len(symbols)} symbols missing the "
                  f"{expected_session.date()} close (>{max_missing_fraction:.0%}); that is a "
                  "provider-side absent session, not per-symbol sparseness — skipping the "
                  "batch repair.", flush=True)
            return data

    sleep_seconds = max(0.0, float(getattr(settings, "LATEST_REPAIR_SLEEP_SECONDS", 2.0)))
    window = _window_through(
        (expected_session - pd.tseries.offsets.BDay(settings.INCREMENTAL_OVERLAP_BDAYS)).normalize(),
        expected_session,
    )
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
        repaired = _download_batch_with_retry(batch, window, max_retries=2)
        if not repaired.empty and isinstance(repaired.columns, pd.MultiIndex):
            frames.append(_drop_index_tz(repaired))
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


def _detect_splits(cached: pd.DataFrame, fresh: pd.DataFrame,
                   cached_tickers: list[str]) -> tuple[bool, list[str]]:
    """
    Probe EVERY cached ticker for split-induced price drift on the overlap
    window. The incremental fetch already holds the multi-bday overlap for the
    whole universe in memory, so the check is exhaustive and vectorized — under
    the as-traded regime a split is the ONLY series-shifting corporate action,
    and this probe is the entire defense against a ticker carrying a fake price
    gap until the next weekly cold refetch.

    Returns ``(force_full_refetch, drifted_tickers)``:
    - ``force_full_refetch=True`` if a high enough fraction of probed tickers
      drift to suggest broad corporate-action issues (cold path recommended).
    - ``drifted_tickers`` is the per-ticker list that drifted; if force is
      False these can be re-fetched individually.
    """
    try:
        cached_close = cached.xs('Close', axis=1, level=1)
        fresh_close = fresh.xs('Close', axis=1, level=1)
    except KeyError:
        return (False, [])

    common = cached_close.columns.intersection(fresh_close.columns)
    common = common.intersection(pd.Index(cached_tickers))
    overlap_idx = cached_close.index.intersection(fresh_close.index)
    if common.empty or overlap_idx.empty:
        return (False, [])

    # Compare ratio across the overlap window. A split shows up as a consistent
    # constant ratio (e.g., 0.5 for a 2:1) across every bar; random noise won't
    # be consistent. Flag if mean relative diff exceeds the threshold AND the
    # ratio is roughly constant (low std relative to drift magnitude).
    ratios = (fresh_close.loc[overlap_idx, common]
              / cached_close.loc[overlap_idx, common])  # NaN where either side lacks the bar
    probed_mask = ratios.count() >= 2  # need >= 2 shared bars to judge constancy
    rel_drift = (ratios.mean() - 1.0).abs()
    is_constant = ratios.std().fillna(0.0) < (0.2 * rel_drift).clip(lower=0.001)
    drift_mask = (probed_mask
                  & (rel_drift > settings.SPLIT_PROBE_DRIFT_THRESHOLD)
                  & is_constant)
    drifted = sorted(drift_mask.index[drift_mask])
    probed = int(probed_mask.sum())

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


def _misses_latest_session(
    panel: pd.DataFrame,
    symbols: list[str],
    index_symbols: list[str],
    expected_session: pd.Timestamp,
    min_latest_coverage: float,
    label: str,
) -> bool:
    """True, and says so, when ``panel`` lacks an index close on the expected
    session or too few of ``symbols`` have one."""
    coverage = close_coverage_on(panel, symbols, expected_session)
    if (has_all_closes_on(panel, index_symbols, expected_session)
            and coverage.ratio >= min_latest_coverage):
        return False
    print(f"  {label} latest-session coverage is {coverage.format()} "
          f"for {expected_session.date()} (required >= {min_latest_coverage:.0%}); "
          "falling back to full refetch.")
    return True


def _incremental_fetch(cached: pd.DataFrame, tickers_with_indexes: list[str],
                       gap_bdays: int, index_symbols=None) -> pd.DataFrame | None:
    """
    Fetch only the last (overlap + gap) business days, probe for splits, then
    merge into the cached panel. Returns the merged DataFrame on success or
    None on a soft failure that should fall through to the cold path.

    ``index_symbols`` is the universe's regime set (the caller passes
    ``scope.index_symbols``); defaults to the US-Stocks global set.
    """
    index_symbols = (list(index_symbols) if index_symbols is not None
                     else getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL]))
    expected_session = latest_completed_session()
    min_latest_coverage = getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)
    last_cached_date = (
        last_complete_reference_date(cached, index_symbols)
        or cached.index.max().normalize()
    )
    overlap = settings.INCREMENTAL_OVERLAP_BDAYS
    window = _window_through(
        (last_cached_date - pd.tseries.offsets.BDay(overlap)).normalize(), expected_session
    )

    print(f"Incremental update: gap={gap_bdays} bday(s), fetching "
          f"{window['start']} → {window['end']} ({len(tickers_with_indexes)} tickers)...",
          flush=True)

    fresh = _batched_download(tickers_with_indexes, window, "Incremental")
    if fresh.empty or not isinstance(fresh.columns, pd.MultiIndex):
        print("  Incremental download returned empty/malformed data.")
        return None

    fresh = _repair_latest_session(
        fresh,
        tickers_with_indexes,
        expected_session,
        min_latest_coverage,
        "Incremental",
        # Also a full-universe caller, so the guard applies. The earlier reasoning
        # ("skipping here just drops through to the cold path anyway") stopped being
        # true once the absent-session skip made that fallback cheap: without this the
        # leg pays ~59 serial batches plus ~118s of inter-batch sleep chasing a bar that
        # does not exist, and returns the cache regardless.
        dropout_guard=True,
    )
    # Only a cache that is behind the expected session needs the fetch to reach it.
    if last_cached_date < expected_session and _misses_latest_session(
            fresh, tickers_with_indexes, index_symbols, expected_session,
            min_latest_coverage, "Incremental"):
        return None

    cached_tickers = list({c[0] for c in cached.columns if isinstance(c, tuple)})

    # Split probe on the overlap window.
    force_full, drifted = _detect_splits(cached, fresh, cached_tickers)
    if force_full:
        return None  # Caller will fall through to cold path

    # Drop drifted tickers' columns from both cached and fresh; we'll re-fetch
    # their full history individually after the merge.
    if drifted:
        cached = _drop_tickers(cached, drifted)
        fresh = _drop_tickers(fresh, drifted)

    # OVERWRITE-merge the trailing overlap window (not append-only). ``fresh`` spans
    # [last_cached - overlap, expected]; letting it WIN over the cached rows in that
    # window (combine_first via _patch_market_data) CORRECTS a previously
    # partial/stale bar -- e.g. a mid-session snapshot that missed the last-hour move --
    # instead of freezing it in the cache until the weekly cold refetch. A NaN cell in
    # ``fresh`` (a sparse ticker, or a ticker only in the cache) keeps the cached value,
    # so overwriting never deletes data; the split probe above already guarded drift.
    new_beyond = fresh.loc[fresh.index > last_cached_date]
    if new_beyond.empty:
        print("  No new bars beyond cached last date; refreshing the overlap window in place.")
    else:
        print(f"  +{len(new_beyond)} new bar(s); refreshing the {overlap}-bday overlap window in place.")
    merged = _patch_market_data(cached, fresh)

    # New listings: tickers in universe but absent from the cached columns
    # → fetch their full history via the existing recovery path.
    cached_ticker_set = set(cached_tickers)
    new_listings = [t for t in tickers_with_indexes if t not in cached_ticker_set]
    if new_listings:
        print(f"  Fetching full history for {len(new_listings)} new listing(s)...", flush=True)
        merged = _recover_missing_data(
            merged, new_listings, skip_current_short=False, dropout_guard=False
        )

    # Drifted tickers: fetch their full history individually.
    if drifted:
        print(f"  Refetching {len(drifted)} split-drifted ticker(s) in full...", flush=True)
        merged = _recover_missing_data(
            merged, drifted, skip_current_short=False, dropout_guard=False
        )

    # The recovery fetches above are period-based, so during market hours they
    # can carry today's partial bar into the merge — apply the same forming-bar
    # cap the windowed fetch already gets from its end date.
    merged = _drop_forming_rows(merged, expected_session)

    if last_cached_date < expected_session and _misses_latest_session(
            merged, tickers_with_indexes, index_symbols, expected_session,
            min_latest_coverage, "Merged cache"):
        return None

    return merged
