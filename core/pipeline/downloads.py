"""Market-data download, split-drift checks, and parquet cache orchestration."""
from __future__ import annotations

import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from config import settings
from core.pipeline.cache import (
    _atomic_write_parquet,
    _cache_paths,
    _is_market_hours,
    _now_iso,
    _read_meta,
    _weekly_refresh_due,
    _write_meta,
)
from core.pipeline.data_freshness import (
    CloseCoverage,
    close_coverage_on,
    has_all_closes_on,
    history_too_shallow,
    last_complete_reference_date,
    symbols_missing_closes_on,
)
from core.pipeline.file_lock import cache_lock
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
from core.pipeline import rate_limit
from core.pipeline.ticker_admission import (
    count_active_skips,
    load_admission,
    record_history_results,
    save_admission,
    split_downloadable,
)


@dataclass
class _FetchScope:
    tickers_with_indexes: list[str]
    index_symbols: list[str]
    quarantine_path: str
    quarantine: dict
    skipped_quarantined: list[str]
    admission_path: str
    admission: dict
    skipped_admission: list[str]
    admission_skip_counts: dict[str, int]
    requested_non_index: list[str]


def _is_yahoo_rate_limit_text(text: str) -> bool:
    text = str(text).lower()
    return (
        "yfratelimiterror" in text
        or "too many requests" in text
        or "rate limited" in text
    )


def _is_yahoo_rate_limit_error(exc: Exception) -> bool:
    return _is_yahoo_rate_limit_text(f"{type(exc).__name__}: {exc}")


def _is_yahoo_no_history_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return (
        "yftzmissingerror" in text
        or "possibly delisted" in text
        or "no price data found" in text
        or "no timezone found" in text
    )


def _apply_backoff_jitter(wait: float) -> float:
    """Randomize the lower part of a backoff so many workers that got rate-limited
    at once don't retry in a synchronized burst (which just re-trips Yahoo). Keeps
    ``(1 - jitter)`` of the wait fixed and randomizes the rest, so the result is in
    ``[wait*(1-jitter), wait]``. The *base* backoff (``2**attempt``) still grows across
    retries; the jitter only spreads each attempt's wait within its own band, so a lucky
    low draw on a later attempt can dip below an earlier one — intended (it de-syncs the
    workers; the shared cooldown still enforces the real floor)."""
    jitter = min(max(float(getattr(settings, "YAHOO_BACKOFF_JITTER", 0.5)), 0.0), 1.0)
    if jitter <= 0.0:
        return wait
    return wait * (1.0 - jitter) + random.uniform(0.0, wait * jitter)


def _retry_wait_seconds(attempt: int, exc: Exception | None = None, error_text: str = "") -> float:
    wait = float(2 ** attempt)
    if ((exc is not None and _is_yahoo_rate_limit_error(exc))
            or (error_text and _is_yahoo_rate_limit_text(error_text))):
        wait = max(wait, float(getattr(settings, "YAHOO_RATE_LIMIT_BACKOFF_SECONDS", 30.0)))
        # Invariant: the shared cooldown gets the FULL un-jittered wait; the per-worker retry
        # sleep (the jittered return below) is shorter and may end BEFORE the shared window does.
        # That is fine — rate_limit._respect_cooldown() is the authoritative gate that re-parks a
        # worker whose local sleep ended early. Do NOT drop that second cooldown check thinking the
        # local sleep already covered it, or lockstep bursts come back.
        rate_limit.note_rate_limit(wait)
    return _apply_backoff_jitter(wait)


def _last_yahoo_batch_error_text(batch: list[str]) -> str:
    """Return yfinance's latest batch errors after a sequential yf.download call."""
    try:
        from yfinance import shared as yf_shared
        errors = getattr(yf_shared, "_ERRORS", {}) or {}
    except Exception:
        return ""
    parts = [str(errors.get(ticker.upper(), "")) for ticker in batch]
    return " | ".join(part for part in parts if part)


def price_auto_adjust() -> bool:
    """The ONE source for every price download's ``auto_adjust`` flag.

    False (the shipped default via ``DATA_DIVIDEND_ADJUSTED = False``) =
    as-traded OHLC, split-adjusted only — what TradingView shows and what the
    operator trades. Seed / forward-returns / writer downloads must import this
    so their series can never diverge from the cache regime (eval-twin rule).
    The getattr fallback matches the settings default (as-traded) so a process
    with a shadowed/stale config degrades to the SAME regime, never a mix."""
    return bool(getattr(settings, "DATA_DIVIDEND_ADJUSTED", False))


def _price_regime() -> str:
    """The regime tag stamped into cache meta for the current settings."""
    return "div_adjusted" if price_auto_adjust() else "as_traded"


def _meta_regime_mismatch(meta: dict) -> bool:
    """True when the on-disk cache was fetched under a DIFFERENT price regime.

    Caches written before the tag existed are dividend-adjusted (the old
    default). A mismatched cache must never be served fresh, returned current,
    or incrementally patched — mixing regimes in one panel corrupts every
    structural read. Only a full cold refetch may replace it."""
    return meta.get("price_series", "div_adjusted") != _price_regime()


def _drop_adj_close(data: pd.DataFrame) -> pd.DataFrame:
    """Strip yfinance's extra 'Adj Close' field — the cache schema (and every
    downstream reader) is strictly OHLCV.

    Needed on BOTH download shapes when auto_adjust=False: the pinned yfinance
    1.2.1 emits 'Adj Close' from ``Ticker().history`` too (even with
    ``actions=False``), and every production download goes through the
    single-ticker path. An asymmetric drop would also poison repair patches:
    frames with mismatched field sets combine into NaN-striped rows that
    ``dropna`` then silently eats."""
    if (data is not None and not data.empty
            and isinstance(data.columns, pd.MultiIndex)):
        return data.drop(columns="Adj Close", level=1, errors="ignore")
    return data


def _single_ticker_history(ticker: str, period_or_dates: dict) -> pd.DataFrame:
    """Fetch one symbol without yf.download's process-global multi-ticker state."""
    # These are DEFAULTS the caller may override via period_or_dates. Merging (rather
    # than splatting alongside fixed kwargs) avoids "got multiple values for keyword
    # argument 'auto_adjust'" when a caller passes auto_adjust in the dict (seed /
    # forward-returns / archive paths all do).
    params = {"actions": False, "auto_adjust": price_auto_adjust(), "timeout": 30}
    params.update(period_or_dates)
    data = yf.Ticker(ticker).history(**params)
    if data is None or data.empty:
        return pd.DataFrame()
    if not isinstance(data.columns, pd.MultiIndex):
        data.columns = pd.MultiIndex.from_product([[ticker], data.columns])
    return _drop_adj_close(data)


def _download_once(batch: list[str], period_or_dates: dict) -> pd.DataFrame:
    if len(batch) == 1:
        return _single_ticker_history(batch[0], period_or_dates)
    # no uncontrolled yfinance inner threads; pool + throttle govern concurrency.
    # Defaults overridable by period_or_dates (same anti-collision reason as above).
    params = {"group_by": "ticker", "threads": False, "progress": False, "timeout": 30,
              "auto_adjust": price_auto_adjust()}
    params.update(period_or_dates)
    return _drop_adj_close(yf.download(batch, **params))


def _download_batch_with_retry(batch: list[str], period_or_dates: dict | str,
                               max_retries: int = 3) -> pd.DataFrame:
    """
    Download a batch of tickers with automatic retry on failure.
    ``period_or_dates`` is either a period string ('5y') or a dict of yfinance
    window kwargs ({'period': ...} / {'start': ..., 'end': ...}).
    Returns the downloaded DataFrame (possibly empty on total failure).
    """
    if isinstance(period_or_dates, str):
        period_or_dates = {"period": period_or_dates}
    for attempt in range(1, max_retries + 1):
        try:
            rate_limit.throttle(len(batch))  # shared global outbound-rate ceiling
            batch_data = _download_once(batch, period_or_dates)
            if not batch_data.empty:
                if len(batch) > 1:
                    error_text = _last_yahoo_batch_error_text(batch)
                    if _is_yahoo_rate_limit_text(error_text):
                        rate_limit.note_rate_limit(
                            float(getattr(settings, "YAHOO_RATE_LIMIT_BACKOFF_SECONDS", 30.0))
                        )
                # If only 1 ticker in batch, it doesn't return a MultiIndex, so we force it
                if len(batch) == 1 and not isinstance(batch_data.columns, pd.MultiIndex):
                    batch_data.columns = pd.MultiIndex.from_product([batch, batch_data.columns])
                return batch_data
            error_text = _last_yahoo_batch_error_text(batch) if len(batch) > 1 else ""
            if attempt < max_retries and _is_yahoo_rate_limit_text(error_text):
                wait = _retry_wait_seconds(attempt, error_text=error_text)
                print(f"    Attempt {attempt}/{max_retries} rate-limited. Retrying in {wait:g}s...")
                time.sleep(wait)
                continue
            return pd.DataFrame()
        except Exception as e:
            if _is_yahoo_no_history_error(e):
                return pd.DataFrame()
            if attempt < max_retries:
                wait = _retry_wait_seconds(attempt, e)
                print(f"    Attempt {attempt}/{max_retries} failed ({e}). Retrying in {wait:g}s...")
                time.sleep(wait)
            else:
                print(f"    Batch failed after {max_retries} retries: {e}")

    return pd.DataFrame()


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
    missing_or_short = []
    current_but_short = []
    min_history_bars = int(getattr(settings, "ADMISSION_MIN_HISTORY_BARS", 200))
    expected_session = latest_completed_session()
    for ticker in tickers:
        if ticker in data:
            try:
                closes = data[ticker]["Close"].dropna()
            except KeyError:
                closes = pd.Series(dtype="float64")
            if len(closes) < min_history_bars:
                latest_close = closes.index.max().normalize() if not closes.empty else None
                if (skip_current_short
                        and latest_close is not None
                        and latest_close >= expected_session):
                    current_but_short.append(ticker)
                else:
                    missing_or_short.append(ticker)
        else:
            missing_or_short.append(ticker)

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

        data = pd.concat([data] + fallback_frames, axis=1, sort=True)

    if recovered_count > 0:
        print(f"Successfully recovered full data for {recovered_count} tickers using fallback batches!")
    else:
        print("Fallback pass complete. No additional tickers could be recovered (likely delisted or too new).")

    return data


def _batched_download(tickers: list[str], period_or_dates: dict, label: str) -> pd.DataFrame:
    """Download ``tickers`` one request at a time through a BOUNDED, rate-limited
    pool. ``period_or_dates`` is either ``{'period': '2y'}`` (full refetch) or
    ``{'start': date, 'end': date}`` (incremental).

    Each ticker is a single-ticker ``yf.download`` gated by the shared token bucket
    (``core.pipeline.rate_limit``), and the pool size caps simultaneous
    connections — so the concurrent workers collectively respect ONE outbound-rate
    ceiling instead of bursting Yahoo into 429s. This replaces the old 500-batch
    ``threads=True`` path whose uncontrolled inner threads (one per ticker, each
    throttling independently) were the root cause of the rate-limit storms.
    """
    if not tickers:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    total = len(tickers)
    done = 0
    workers = min(rate_limit.download_workers(), total)
    print(f"  {label}: {total} tickers via {workers} rate-limited workers...", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_download_batch_with_retry, [ticker], period_or_dates): ticker
            for ticker in tickers
        }
        for fut in as_completed(futures):
            frame = fut.result()
            done += 1
            if not frame.empty:
                frames.append(frame)
            if done % 500 == 0 or done == total:
                print(f"    {label}: {done}/{total} fetched ({len(frames)} non-empty)...", flush=True)

    if not frames:
        return pd.DataFrame()

    for j in range(len(frames)):
        if hasattr(frames[j].index, 'tz') and frames[j].index.tz is not None:
            frames[j].index = frames[j].index.tz_localize(None)

    data = pd.concat(frames, axis=1)
    if isinstance(data.columns, pd.MultiIndex):
        data = data.loc[:, ~data.columns.duplicated(keep='last')]
    return data


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


# The daily-structure trim is ENGINE-owned (it defines what the reader sees);
# re-exported here so existing download/cache callers keep their import path.
from engine_alpha.frames import _trim_to_period  # noqa: E402,F401


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


def _has_all_symbols(data: pd.DataFrame, symbols: list[str]) -> bool:
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return False
    present = set(data.columns.get_level_values(0))
    return all(symbol in present for symbol in symbols)


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
        repaired = _download_batch_with_retry(
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


def repair_latest_session_cache(
    data: pd.DataFrame,
    cache_file: str,
    meta_file: str,
    symbols: list[str],
    expected_session: pd.Timestamp,
    min_latest_coverage: float,
    label: str = "Manual repair",
) -> pd.DataFrame:
    """Patch latest-session closes for ``symbols`` and persist the cache if changed."""
    # Regime guard: never patch NEW-regime bars into an old-regime panel — a
    # mixed parquet corrupts every structural read. Skip the repair unchanged;
    # the health machinery keeps reporting the gap and the next download-mode
    # fetch_data run replaces the cache cold.
    meta = _read_meta(meta_file)
    if _meta_regime_mismatch(meta):
        print(f"  {label}: cache price-series regime "
              f"({meta.get('price_series', 'div_adjusted')}) differs from settings "
              f"({_price_regime()}); skipping repair — a full cold refetch must "
              "replace this cache first.", flush=True)
        return data
    repaired = _repair_latest_session(
        data, symbols, expected_session, min_latest_coverage, label
    )
    if repaired is not data:
        _atomic_write_parquet(repaired, cache_file)
        meta = _read_meta(meta_file)
        meta["last_modified"] = _now_iso()
        _write_meta(meta_file, meta)
    return repaired


def _record_admission_history(admission: dict, admission_path: str, requested: list[str],
                              data: pd.DataFrame, label: str, *,
                              mark_missing: bool = True,
                              only_untracked: bool = False) -> dict[str, int]:
    if not getattr(settings, "TICKER_ADMISSION_ENABLED", True) or not requested:
        return {}
    if only_untracked:
        requested = [ticker for ticker in requested if ticker not in admission]
        if not requested:
            return {}
    admission, summary = record_history_results(
        admission, requested, data, mark_missing=mark_missing
    )
    if summary:
        save_admission(admission_path, admission)
        detail = ", ".join(f"{status}={count}" for status, count in sorted(summary.items()))
        print(f"  Admission: {label} updated {sum(summary.values())} ticker(s)"
              f"{f' ({detail})' if detail else ''}.",
              flush=True)
    return summary


def _symbols_with_indexes(tickers: list[str], universe=None) -> tuple[list[str], list[str]]:
    # Per-universe regime symbols: us_stocks/us_sectors carry SPY/QQQ; the
    # commodities universe carries none (its regime is borrowed from the broad
    # market), so it doesn't redundantly re-pull SPY/QQQ. Defaults to the
    # US-Stocks index set, byte-identical to the prior global read.
    from core.pipeline.universe import resolve_universe
    index_symbols = list(resolve_universe(universe).index_symbols)
    tickers_with_indexes = list(tickers)
    for symbol in index_symbols:
        if symbol not in tickers_with_indexes:
            tickers_with_indexes.append(symbol)
    return tickers_with_indexes, index_symbols


def _state_path(meta_file: str, setting_name: str, default_name: str) -> str:
    return os.path.join(os.path.dirname(meta_file), getattr(settings, setting_name, default_name))


def _prepare_fetch_scope(tickers: list[str], meta_file: str, universe=None) -> _FetchScope:
    tickers_with_indexes, index_symbols = _symbols_with_indexes(tickers, universe)

    quarantine_path = _state_path(meta_file, "QUARANTINE_FILENAME", "ticker_quarantine.json")
    quarantine = (
        load_quarantine(quarantine_path)
        if getattr(settings, "QUARANTINE_ENABLED", True)
        else {}
    )
    tickers_with_indexes, skipped_quarantined = split_active(
        tickers_with_indexes, quarantine, index_symbols=index_symbols
    )
    if skipped_quarantined:
        print(f"  Quarantine: skipping {len(skipped_quarantined)} repeatedly-empty "
              f"ticker(s); re-probe in <= {getattr(settings, 'QUARANTINE_COOLDOWN_DAYS', 7)}d.",
              flush=True)

    admission_path = _state_path(
        meta_file, "TICKER_ADMISSION_FILENAME", "ticker_admission.json"
    )
    admission = (
        load_admission(admission_path)
        if getattr(settings, "TICKER_ADMISSION_ENABLED", True)
        else {}
    )
    tickers_with_indexes, skipped_admission, admission_skip_counts = split_downloadable(
        tickers_with_indexes, admission, index_symbols=index_symbols
    )
    if skipped_admission:
        detail = ", ".join(
            f"{status}={count}" for status, count in sorted(admission_skip_counts.items())
        )
        print(f"  Admission: skipping {len(skipped_admission)} ticker(s)"
              f"{f' ({detail})' if detail else ''}.",
              flush=True)

    requested_non_index = [t for t in tickers_with_indexes if t not in index_symbols]
    return _FetchScope(
        tickers_with_indexes=tickers_with_indexes,
        index_symbols=index_symbols,
        quarantine_path=quarantine_path,
        quarantine=quarantine,
        skipped_quarantined=skipped_quarantined,
        admission_path=admission_path,
        admission=admission,
        skipped_admission=skipped_admission,
        admission_skip_counts=admission_skip_counts,
        requested_non_index=requested_non_index,
    )


def _try_fresh_cache(
    cache_file: str,
    scope: _FetchScope,
    expected_session: pd.Timestamp,
    min_latest_coverage: float,
    weekly_refresh_due: bool = False,
) -> pd.DataFrame | None:
    if not os.path.exists(cache_file):
        return None
    if weekly_refresh_due:
        # The weekly cold refetch outranks the TTL fast path — otherwise a refresh
        # requested inside the 12h TTL returns the cache untouched, last_full_refresh
        # never advances, and the button keeps asking for the refresh it just
        # appeared to perform. (_try_current_cache and do_incremental already defer.)
        return None

    cache_age_hours = (time.time() - os.path.getmtime(cache_file)) / 3600.0
    ttl = (settings.TTL_FRESH_HOURS_MARKET if _is_market_hours()
           else settings.TTL_FRESH_HOURS_OFFHOURS)
    if cache_age_hours >= ttl:
        return None

    cached_data = _read_cached_panel(cache_file)
    if cached_data is None:  # corrupt parquet routes to the cold rebuild
        return None
    if _history_too_shallow(cached_data, scope.tickers_with_indexes):
        print("Local cache is fresh by mtime but its deep history is truncated "
              "(most symbols missing their multi-year bars); forcing a full refetch.",
              flush=True)
        return None
    last_reference_date = last_complete_reference_date(cached_data, scope.index_symbols)
    coverage = close_coverage_on(cached_data, scope.tickers_with_indexes, expected_session)
    if (_has_all_symbols(cached_data, scope.index_symbols)
            and last_reference_date is not None
            and last_reference_date >= expected_session
            and coverage.ratio >= min_latest_coverage):
        _record_admission_history(
            scope.admission, scope.admission_path, scope.requested_non_index, cached_data,
            "cache", mark_missing=False, only_untracked=True
        )
        print(f"Loading market data from local cache ({cache_age_hours:.2f}h old, "
              f"TTL {ttl}h)...", flush=True)
        return cached_data

    print(f"Local cache is fresh by mtime but latest-session coverage is "
          f"{coverage.format()} for {expected_session.date()} "
          f"(required >= {min_latest_coverage:.0%}); updating cache.", flush=True)
    return None


def _history_too_shallow(panel: pd.DataFrame | None, symbols: list[str]) -> bool:
    """True when the cached panel spans years but most symbols lost their deep
    history (the NaN-wipe corruption shape). Judged ONLY when the panel itself has
    >= MIN_HISTORY_BARS rows, so a short/new cache is never falsely flagged — and
    a HEALTHY cache (deep history intact) returns False, leaving the fast paths
    byte-identical. When True, the caller forces a full cold refetch (self-repair),
    so a corrupted cache no longer blocks its own recovery via the latest-session
    freshness check that is blind to depth.

    Delegates the bar-floor + coverage predicate to the shared
    ``data_freshness.history_too_shallow`` so the downloader and the health
    classifier can never drift on the depth logic (they intentionally differ only
    in which symbol set they judge)."""
    min_bars = int(getattr(settings, "MARKET_DATA_MIN_HISTORY_BARS", 100))
    min_cov = float(getattr(settings, "MARKET_DATA_MIN_HISTORY_COVERAGE", 0.5))
    return history_too_shallow(panel, symbols, min_bars=min_bars, min_cov=min_cov)


def _read_cached_panel(cache_file: str) -> pd.DataFrame | None:
    if not os.path.exists(cache_file):
        return None
    try:
        cached = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
        if hasattr(cached.index, 'tz') and cached.index.tz is not None:
            cached.index = cached.index.tz_localize(None)
        return cached
    except Exception as e:
        print(f"  Cached parquet unreadable ({e}); falling back to full refetch.")
        return None


ABSENT_SESSIONS_KEY = "absent_sessions"


def absent_sessions(meta: dict) -> set[str]:
    """The sessions a full fetch has PROVEN the provider does not carry.

    Fails OPEN (empty set) on anything malformed: every consumer uses this only to
    SKIP work or to forgive a gap, so a corrupt ledger must degrade toward doing the
    work, never toward raising out of the download path.
    """
    try:
        return {str(day) for day in (meta.get(ABSENT_SESSIONS_KEY) or []) if day}
    except Exception:
        return set()


def record_absent_session(meta: dict, session: pd.Timestamp) -> None:
    """Append ``session`` to the ledger, newest last, de-duplicated and capped."""
    day = str(pd.Timestamp(session).date())
    ledger = [d for d in sorted(absent_sessions(meta)) if d != day]
    ledger.append(day)
    cap = max(1, int(getattr(settings, "ABSENT_SESSION_LEDGER_MAX", 20)))
    meta[ABSENT_SESSIONS_KEY] = ledger[-cap:]


def _is_provider_absent_session(coverage) -> bool:
    """True when a FRESH full-universe fetch came back with essentially no closes for
    the expected session — the shape that means "the provider does not have this day",
    as opposed to a thin or throttled response, which is a repair target."""
    if coverage is None:
        return False
    bar = float(getattr(settings, "PROVIDER_ABSENT_SESSION_MAX_COVERAGE", 0.02))
    return float(coverage.ratio) <= bar


def _cold_retry_blocked(meta: dict, expected_session: pd.Timestamp) -> bool:
    """True when a full fetch already proved this expected session absent upstream.

    A cold fetch that misses its coverage gate persists nothing and leaves
    ``last_full_refresh`` untouched (see ``_write_unhealthy_cold_result``), so every
    input to the next run's decision tree is unchanged — the run repeats verbatim.
    When the expected session is simply absent upstream (measured 2026-07-24: Yahoo
    carries no bar for that Friday for any symbol, while the static NYSE rule calendar
    calls it a session) that costs ~30 minutes per attempt to re-learn the same fact.

    Keyed on the SESSION rather than a wall clock. A time window is dead exactly when
    it is needed: the two measured repeats were ~24h apart and a Friday loss spans the
    weekend, so any cooldown short enough to be safe is too short to catch them. A
    newly completed session is not in the ledger and always gets a fresh attempt, and
    the operator's Refresh click clears the ledger — the human override is intact.
    Only ESSENTIALLY-ZERO coverage lands here (see ``_is_provider_absent_session``), so
    a throttled or thin response stays retryable, as does a shallow-history failure.
    """
    return str(pd.Timestamp(expected_session).date()) in absent_sessions(meta)


def _cache_status(
    cached: pd.DataFrame | None,
    scope: _FetchScope,
    expected_session: pd.Timestamp,
) -> tuple[pd.Timestamp | None, int | None, object | None]:
    if cached is None or cached.empty:
        return None, None, None
    last_cached_date = (
        last_complete_reference_date(cached, scope.index_symbols)
        or cached.index.max().normalize()
    )
    gap_bdays = session_gap(last_cached_date, expected_session)
    latest_coverage = close_coverage_on(cached, scope.tickers_with_indexes, expected_session)
    return last_cached_date, gap_bdays, latest_coverage


def _try_current_cache(
    cached: pd.DataFrame | None,
    cache_file: str,
    meta_file: str,
    meta: dict,
    scope: _FetchScope,
    last_cached_date: pd.Timestamp | None,
    gap_bdays: int | None,
    latest_coverage,
    weekly_refresh_due: bool,
    min_latest_coverage: float,
) -> pd.DataFrame | None:
    if cached is None or cached.empty or gap_bdays != 0 or weekly_refresh_due:
        return None
    if _history_too_shallow(cached, scope.tickers_with_indexes):
        print("Cache last bar is current but its deep history is truncated; "
              "forcing a full refetch.", flush=True)
        return None

    if (_has_all_symbols(cached, scope.index_symbols)
            and latest_coverage is not None
            and latest_coverage.ratio >= min_latest_coverage):
        print(f"Cache last market-regime bar is current ({last_cached_date.date()}); "
              f"touching mtime and returning.", flush=True)
        # mtime bump only (feeds the TTL fresh-path check) — rewriting the whole
        # multi-hundred-MB parquet just for this wasted minutes per no-op run.
        # Best-effort: a concurrent Windows reader can deny the attribute write,
        # and a failed bump only means the next run re-checks freshness.
        try:
            os.utime(cache_file)
        except OSError:
            pass
        meta['last_modified'] = _now_iso()
        _record_admission_history(
            scope.admission, scope.admission_path, scope.requested_non_index, cached,
            "cache", mark_missing=False, only_untracked=True
        )
        _write_meta(meta_file, meta)
        return cached

    coverage_text = latest_coverage.format() if latest_coverage else "none"
    print(f"Cache last market-regime bar is current but latest-session coverage is "
          f"{coverage_text} (required >= {min_latest_coverage:.0%}); "
          "falling back to full refetch.", flush=True)
    return None


def _write_incremental_result(
    data: pd.DataFrame,
    cache_file: str,
    meta_file: str,
    meta: dict,
    scope: _FetchScope,
    started_at: float,
) -> pd.DataFrame:
    data = _trim_to_period(data, settings.DOWNLOAD_PERIOD)
    data = data.loc[:, ~data.columns.duplicated(keep='last')]
    _atomic_write_parquet(data, cache_file)
    meta['last_modified'] = _now_iso()
    meta['price_series'] = _price_regime()   # reachable only when regimes match
    # Progress made — drop the failure telemetry and the absent-session ledger so a
    # recovered cache never carries a skip that would suppress a later fetch.
    meta.pop('last_cold_failure', None)
    meta.pop(ABSENT_SESSIONS_KEY, None)
    # Health only: the cold full-refetch owns quarantine updates. A ticker
    # absent from a small incremental window is not necessarily dead.
    returned_active = present_tickers(data) & set(scope.requested_non_index)
    admission_updates = _record_admission_history(
        scope.admission, scope.admission_path, scope.requested_non_index, data, "incremental"
    )
    meta['fetch_health'] = summarize(
        "incremental", scope.requested_non_index, returned_active,
        len(scope.skipped_quarantined), 0, count_quarantined(scope.quarantine),
        time.time() - started_at,
    )
    meta['ticker_admission'] = {
        "skipped": len(scope.skipped_admission),
        "skip_counts": scope.admission_skip_counts,
        "updates": admission_updates,
        "active_skip_counts": count_active_skips(scope.admission),
    }
    # Preserve last_full_refresh on incremental writes.
    _write_meta(meta_file, meta)
    print(f"Saved incremental update to {cache_file}. New last bar: "
          f"{data.index.max().date()}.", flush=True)
    return data


def _try_incremental_update(
    cached: pd.DataFrame,
    cache_file: str,
    meta_file: str,
    meta: dict,
    scope: _FetchScope,
    gap_bdays: int,
    started_at: float,
) -> pd.DataFrame | None:
    data = _incremental_fetch(cached, scope.tickers_with_indexes, gap_bdays, scope.index_symbols)
    if data is not None and not data.empty:
        return _write_incremental_result(data, cache_file, meta_file, meta, scope, started_at)

    print("  Incremental fetch yielded no usable data; falling back to full refetch.")
    return None


def _write_unhealthy_cold_result(
    data: pd.DataFrame,
    cached: pd.DataFrame | None,
    meta_file: str,
    meta: dict,
    scope: _FetchScope,
    coverage,
    expected_session: pd.Timestamp,
    min_latest_coverage: float,
    started_at: float,
    reason: str | None = None,
    failure_kind: str = "coverage",
) -> pd.DataFrame:
    # Unhealthy cold run (rate-limited OR came back shallow): record health for
    # observability but do not persist the panel, do not touch quarantine, and
    # preserve last_full_refresh in meta. The new panel is NOT written, so the
    # existing (possibly deeper) cache on disk is left intact.
    returned_active = present_tickers(data) & set(scope.requested_non_index)
    meta['fetch_health'] = summarize(
        "cold", scope.requested_non_index, returned_active, len(scope.skipped_quarantined),
        0, count_quarantined(scope.quarantine), time.time() - started_at,
    )
    meta['ticker_admission'] = {
        "skipped": len(scope.skipped_admission),
        "skip_counts": scope.admission_skip_counts,
        "updates": {},
        "active_skip_counts": count_active_skips(scope.admission),
    }
    # The one record that this expensive run happened at all: fetch_health above
    # reports the DOWNLOAD (returned/requested, healthy by quarantine ratio) and
    # reads fine even when the panel is discarded, so without this the next run — and
    # the operator — have no way to know it would be repeating itself.
    meta['last_cold_failure'] = {
        'at': _now_iso(),
        'expected_session': str(pd.Timestamp(expected_session).date()),
        'coverage_ratio': round(float(coverage.ratio), 4) if coverage is not None else None,
        'duration_s': round(time.time() - started_at, 1),
        'kind': failure_kind,
    }
    # ...but only an essentially-empty COVERAGE failure proves the provider lacks the
    # session. A shallow-history failure is a thin/throttled response the next fetch can
    # repair, and arming the skip from it would suppress the retry that fixes it — the
    # caller's exemption cannot recover this, because it inspects the healthy panel
    # preserved on disk rather than the thin one just fetched.
    if failure_kind == "coverage" and _is_provider_absent_session(coverage):
        record_absent_session(meta, expected_session)
        print(f"  Recorded {pd.Timestamp(expected_session).date()} as absent upstream "
              f"(coverage {coverage.format()}); further full fetches for that session "
              "are skipped until it changes or you press Download.", flush=True)
    _write_meta(meta_file, meta)
    print(reason or (
        f"Full refetch latest-session coverage is {coverage.format()} for "
        f"{expected_session.date()} (required >= {min_latest_coverage:.0%}); "
        "keeping existing cache if possible."), flush=True)
    # On a regime-mismatch run the kept cache is the WRONG price series — the
    # guard that forced this cold fetch must not be undone by its failure path.
    # Serve the (unhealthy but right-regime) fresh panel instead; health gating
    # downstream still blocks archiving from it.
    if cached is not None and not cached.empty and not _meta_regime_mismatch(meta):
        return cached
    return data


def _write_successful_cold_result(
    data: pd.DataFrame,
    cache_file: str,
    meta_file: str,
    scope: _FetchScope,
    started_at: float,
) -> pd.DataFrame:
    _atomic_write_parquet(data, cache_file)
    returned = present_tickers(data)
    returned_active = returned & set(scope.requested_non_index)
    newly: list[str] = []
    if (getattr(settings, "QUARANTINE_ENABLED", True)
            and is_healthy(scope.requested_non_index, returned_active)):
        scope.quarantine, newly = record_results(
            scope.quarantine, scope.requested_non_index, returned
        )
        save_quarantine(scope.quarantine_path, scope.quarantine)
    admission_updates = _record_admission_history(
        scope.admission, scope.admission_path, scope.requested_non_index, data, "cold"
    )
    health = summarize(
        "cold", scope.requested_non_index, returned_active, len(scope.skipped_quarantined),
        len(newly), count_quarantined(scope.quarantine), time.time() - started_at,
    )
    meta = {
        'last_full_refresh': _now_iso(),
        'last_modified': _now_iso(),
        'price_series': _price_regime(),
        'fetch_health': health,
        'ticker_admission': {
            "skipped": len(scope.skipped_admission),
            "skip_counts": scope.admission_skip_counts,
            "updates": admission_updates,
            "active_skip_counts": count_active_skips(scope.admission),
        },
    }
    _write_meta(meta_file, meta)
    if newly:
        print(f"  Quarantine: +{len(newly)} ticker(s) after "
              f"{getattr(settings, 'QUARANTINE_EMPTY_STREAK', 2)} empty refetch(es); "
              f"{health['quarantined_total']} total quarantined.", flush=True)
    print(f"Saved optimized cache to {cache_file} "
          f"(returned {health['returned']}/{health['requested']}).")
    return data


def _cold_fetch(
    cache_file: str,
    meta_file: str,
    meta: dict,
    cached: pd.DataFrame | None,
    scope: _FetchScope,
    expected_session: pd.Timestamp,
    min_latest_coverage: float,
    started_at: float,
) -> pd.DataFrame:
    data = _full_refetch(scope.tickers_with_indexes)
    if data.empty:
        # An empty full-universe pass costs the same request volume as a successful
        # one, so it must leave the same record — otherwise the most expensive failure
        # mode is the one the brake cannot see. Deliberately NOT an absent session:
        # nobody returning anything is a total provider/network failure, and marking
        # the session absent from it would suppress the retry that recovers.
        return _write_unhealthy_cold_result(
            data, cached, meta_file, meta, scope,
            CloseCoverage(day=expected_session, present=0,
                          total=len(scope.tickers_with_indexes)),
            expected_session, min_latest_coverage, started_at,
            reason=("Full refetch returned no data for any symbol; keeping the existing "
                    "cache. This is a total provider failure, not an absent session — "
                    "the next run retries."),
            failure_kind="empty",
        )

    if isinstance(data.columns, pd.MultiIndex):
        data = data.loc[:, ~data.columns.duplicated(keep='last')]

    # Cap BEFORE the coverage checks: both the persisted panel and the
    # unhealthy-path return value must be free of the current day's partial bar.
    data = _drop_forming_rows(data, expected_session)

    data = _repair_latest_session(
        data,
        scope.tickers_with_indexes,
        expected_session,
        min_latest_coverage,
        "Full refetch",
        # The ONLY full-universe caller that measured the 55-serial-batch cost.
        # _incremental_fetch's repair is the CHEAP retry (a ~6-bar window); skipping
        # it there would just drop through to this 5y × ~5.5k-symbol path instead.
        dropout_guard=True,
    )
    coverage = close_coverage_on(data, scope.tickers_with_indexes, expected_session)
    if (not has_all_closes_on(data, scope.index_symbols, expected_session)
            or coverage.ratio < min_latest_coverage):
        return _write_unhealthy_cold_result(
            data, cached, meta_file, meta, scope, coverage, expected_session,
            min_latest_coverage, started_at
        )

    # Depth chokepoint: the cold path is where the deep-history guard routes a
    # corrupted/truncated cache for repair, so a full refetch that comes back
    # current-but-shallow (a thin Yahoo response — recent bars only) must NOT be
    # persisted as the cache. Writing it would clobber the deeper on-disk history
    # and ping-pong with the depth guard that keeps re-triggering the refetch.
    # Treat it as unhealthy so the existing cache is preserved.
    if _history_too_shallow(data, scope.tickers_with_indexes):
        return _write_unhealthy_cold_result(
            data, cached, meta_file, meta, scope, coverage, expected_session,
            min_latest_coverage, started_at,
            reason=("Full refetch came back current but its deep history is still "
                    f"truncated for {expected_session.date()} (thin provider "
                    "response); not persisting the shallow panel — keeping the "
                    "existing cache if possible."),
            failure_kind="shallow_history",
        )

    return _write_successful_cold_result(data, cache_file, meta_file, scope, started_at)


def fetch_data(tickers: list[str], universe=None) -> pd.DataFrame:
    """
    Download market data via yfinance with PyArrow Parquet caching.

    ``universe`` selects which per-universe cache + regime index set to use
    (``None`` = US-Stocks, byte-identical to before). Each universe reads and
    writes ONLY its own cache file, so an ETF scan can never corrupt the
    US-Stocks parquet / cache_meta.

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
    cache_file, meta_file = _cache_paths(universe)

    # Serialize the whole read-fetch-write window across processes (CLI scan vs
    # in-process scheduler vs manual SSE) so they cannot interleave and clobber
    # this universe's parquet/meta. Re-entrant within a process.
    with cache_lock(cache_file):
        scope = _prepare_fetch_scope(tickers, meta_file, universe)

        expected_session = latest_completed_session()
        min_latest_coverage = getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)

        # ── Price-regime guard ─────────────────────────────────────────────────
        # A cache fetched under a different DATA_DIVIDEND_ADJUSTED regime must
        # never be served, returned current, or incrementally patched — mixed
        # regimes in one panel corrupt every structural read. Cold refetch only.
        meta = _read_meta(meta_file)
        regime_mismatch = _meta_regime_mismatch(meta)
        if regime_mismatch:
            print(f"Cache price-series regime "
                  f"({meta.get('price_series', 'div_adjusted')}) differs from "
                  f"settings ({_price_regime()}); forcing a full cold refetch.",
                  flush=True)

        weekly_refresh_due = _weekly_refresh_due(meta)

        # ── Fast path: fresh cache ─────────────────────────────────────────────
        fresh_cache = None if regime_mismatch else _try_fresh_cache(
            cache_file, scope, expected_session, min_latest_coverage, weekly_refresh_due
        )
        if fresh_cache is not None:
            return fresh_cache

        # ── Decide cold vs. incremental ────────────────────────────────────────
        cached = _read_cached_panel(cache_file)
        last_cached_date, gap_bdays, latest_coverage = _cache_status(
            cached, scope, expected_session
        )

        current_cache = None if regime_mismatch else _try_current_cache(
            cached, cache_file, meta_file, meta, scope, last_cached_date, gap_bdays,
            latest_coverage, weekly_refresh_due, min_latest_coverage
        )
        if current_cache is not None:
            return current_cache

        # "The cache on disk is usable as-is" — needed by BOTH the incremental decision
        # and the absent-session skip below. Computed once: the two spellings had to
        # agree or the skip could park a fetch on a cache the incremental path had
        # already rejected, and _history_too_shallow scans the whole ~5.5k-symbol panel.
        cached_usable = (
            not regime_mismatch
            and cached is not None
            and not cached.empty
            # A truncated cache must NOT be incrementally patched (that only adds
            # recent rows, leaving the deep history hollow) — go cold to rebuild it.
            and not _history_too_shallow(cached, scope.tickers_with_indexes)
        )

        do_incremental = (
            cached_usable
            and gap_bdays is not None
            and 1 <= gap_bdays <= settings.INCREMENTAL_MAX_GAP_BDAYS
            and not weekly_refresh_due
        )

        if do_incremental:
            incremental = _try_incremental_update(
                cached, cache_file, meta_file, meta, scope, gap_bdays, t_fetch_start
            )
            if incremental is not None:
                return incremental

        # A full fetch already proved this expected session absent upstream, and a cold
        # fetch persists nothing — repeating it re-pays the full-universe download to
        # reach the identical verdict. Only honoured with a usable cache in hand; a
        # regime mismatch or truncated history still goes cold, because those a refetch
        # CAN repair.
        if cached_usable and _cold_retry_blocked(meta, expected_session):
            failure = meta.get('last_cold_failure') or {}
            print(f"Skipping cold refetch: {expected_session.date()} is recorded absent "
                  f"upstream (a full fetch reached coverage {failure.get('coverage_ratio')} "
                  f"in {failure.get('duration_s')}s). Serving the cached panel; the next "
                  "completed session retries automatically, and Download New Data forces "
                  "a retry now.", flush=True)
            return cached

        return _cold_fetch(
            cache_file, meta_file, meta, cached, scope, expected_session,
            min_latest_coverage, t_fetch_start
        )


def _incremental_fetch(cached: pd.DataFrame, tickers_with_spy: list[str],
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
        # Also a full-universe caller, so the guard applies. The earlier reasoning
        # ("skipping here just drops through to the cold path anyway") stopped being
        # true once the absent-session skip made that fallback cheap: without this the
        # leg pays ~59 serial batches plus ~118s of inter-batch sleep chasing a bar that
        # does not exist, and returns the cache regardless.
        dropout_guard=True,
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
    new_listings = [t for t in tickers_with_spy if t not in cached_ticker_set]
    if new_listings:
        print(f"  Fetching full history for {len(new_listings)} new listing(s)...", flush=True)
        merged = _recover_missing_data(
            merged, new_listings, skip_current_short=False, dropout_guard=False
        )

    # Drifted tickers: fetch their full 2y individually.
    if drifted:
        print(f"  Refetching {len(drifted)} split-drifted ticker(s) in full...", flush=True)
        merged = _recover_missing_data(
            merged, drifted, skip_current_short=False, dropout_guard=False
        )

    # The recovery fetches above are period-based, so during market hours they
    # can carry today's partial bar into the merge — apply the same forming-bar
    # cap the windowed fetch already gets from its end date.
    merged = _drop_forming_rows(merged, expected_session)

    merged_coverage = close_coverage_on(merged, tickers_with_spy, expected_session)
    if (last_cached_date < expected_session
            and (not has_all_closes_on(merged, index_symbols, expected_session)
                 or merged_coverage.ratio < min_latest_coverage)):
        print(f"  Merged cache latest-session coverage is {merged_coverage.format()} "
              f"for {expected_session.date()} (required >= {min_latest_coverage:.0%}); "
              "falling back to full refetch.")
        return None

    return merged
