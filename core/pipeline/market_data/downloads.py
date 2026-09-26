"""The market-data parquet cache: serve it, patch it, or refetch it cold.

``fetch_data`` is the state machine (lock, scope, fresh?, current?, incremental?, cold;
conventions.md AP-2). This module owns the cache and meta writes, the quarantine and
admission bookkeeping around a fetch, and the ledger of sessions the provider lacks.
The panels themselves come from ``panel_fetch``, which requests them through
``yahoo_download``; ``price_regime`` names the price series the cache holds.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pandas as pd

from config import settings
from core.pipeline.market_data.cache import (
    _atomic_write_parquet,
    _cache_paths,
    _is_market_hours,
    _now_iso,
    _read_meta,
    _weekly_refresh_due,
    _write_meta,
)
from core.pipeline.market_data.data_freshness import (
    CloseCoverage,
    close_coverage_on,
    has_all_closes_on,
    history_too_shallow,
    last_complete_reference_date,
)
from core.pipeline.market_data.file_lock import cache_lock
from core.pipeline.market_data.fetch_health import (
    count_quarantined,
    is_healthy,
    load_quarantine,
    present_tickers,
    record_results,
    save_quarantine,
    split_active,
    summarize,
)
from core.pipeline.market_data.market_calendar import latest_completed_session, session_gap
from core.pipeline.market_data.panel_fetch import (
    _drop_forming_rows,
    _full_refetch,
    _incremental_fetch,
    _repair_latest_session,
)
from core.pipeline.market_data.price_regime import _meta_regime_mismatch, _price_regime
from core.pipeline.universe.ticker_admission import (
    count_active_skips,
    load_admission,
    record_history_results,
    save_admission,
    split_downloadable,
)
# The daily-structure trim is ENGINE-owned (it defines what the reader sees);
# re-exported here so existing download/cache callers keep their import path.
from engine_alpha.frames import _trim_to_period

# Callers outside this module (the archive downloads, the candle cache, the
# calibration workbench) import these from here; they now live beside it.
from core.pipeline.market_data.price_regime import price_auto_adjust  # noqa: F401
from core.pipeline.market_data.yahoo_download import (  # noqa: F401
    _batched_download,
    _is_yahoo_rate_limit_text,
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


def _has_all_symbols(data: pd.DataFrame, symbols: list[str]) -> bool:
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return False
    present = set(data.columns.get_level_values(0))
    return all(symbol in present for symbol in symbols)


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


def _admission_meta(scope: _FetchScope, updates: dict[str, int]) -> dict:
    """The ``ticker_admission`` block a fetch writes into the cache meta."""
    return {
        "skipped": len(scope.skipped_admission),
        "skip_counts": scope.admission_skip_counts,
        "updates": updates,
        "active_skip_counts": count_active_skips(scope.admission),
    }


def _symbols_with_indexes(tickers: list[str], universe=None) -> tuple[list[str], list[str]]:
    # Per-universe regime symbols: us_stocks/us_sectors carry SPY/QQQ; the
    # commodities universe carries none (its regime is borrowed from the broad
    # market), so it doesn't redundantly re-pull SPY/QQQ. Defaults to the
    # US-Stocks index set, byte-identical to the prior global read.
    from core.pipeline.universe.descriptor import resolve_universe
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
    meta['ticker_admission'] = _admission_meta(scope, admission_updates)
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
    meta['ticker_admission'] = _admission_meta(scope, {})
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
        'ticker_admission': _admission_meta(scope, admission_updates),
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
