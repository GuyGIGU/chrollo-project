"""Reusable scan -> dashboard -> archive job."""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from config import settings
from core.archive.writer import archive_scan_results
from core.pipeline import run_screener
from core.pipeline.cache import _cache_paths, _read_meta
from core.pipeline.data import get_provider, get_tickers
from core.pipeline.downloads import repair_latest_session_cache
from core.pipeline.market_data_health import (
    clear_repair_state,
    compute_market_data_health,
    record_repair_attempt,
)
from core.pipeline.market_calendar import latest_completed_session
from core.pipeline.screener import CachedMarketDataError
from output.dashboard import generate_dashboard
from output.terminal import print_finviz_url, print_results, save_csv

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
log = logging.getLogger("chrollo.scan_job")


class StaleMarketDataError(RuntimeError):
    """Raised when a scan should not be archived because data is stale."""

    def __init__(self, message: str, n_setups: int | None = None):
        super().__init__(message)
        self.n_setups = n_setups


@dataclass
class ScanExportResult:
    n_setups: int
    n_archived: int


@dataclass
class DownloadOnlyResult:
    n_tickers: int
    latest_session: str | None
    expected_session: str
    coverage: str
    health_state: str = "healthy"
    coverage_detail: dict | None = None
    ready: bool = True
    partial: bool = False
    cooldown_until: str | None = None
    retry_reason: str | None = None
    help_needed: bool = False
    message: str | None = None


def _expected_session_date(now_et: datetime | None = None) -> str:
    expected = latest_completed_session(now_et)
    return expected.strftime("%Y-%m-%d")


def _last_bar_date(data: pd.DataFrame, tickers: list[str]) -> str | None:
    if data is None or data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        symbols = list(data.columns.get_level_values(0).unique())
        preferred = settings.SPY_SYMBOL if settings.SPY_SYMBOL in symbols else None
        symbol = preferred or next((ticker for ticker in tickers if ticker in symbols), None)
        if symbol:
            try:
                close = data[symbol]["Close"].dropna()
                if not close.empty:
                    return pd.Timestamp(close.index[-1]).strftime("%Y-%m-%d")
            except Exception:
                pass

    valid = data.dropna(how="all")
    if valid.empty:
        return None
    return pd.Timestamp(valid.index[-1]).strftime("%Y-%m-%d")


def _assert_fresh_for_archive(data: pd.DataFrame, tickers: list[str]) -> None:
    expected = _expected_session_date()
    last_bar = _last_bar_date(data, tickers)
    # Stale only if the data is OLDER than the latest completed session — i.e.
    # the feed is missing a session it should have. A bar that is current or
    # newer (e.g. today's forming bar during an intraday manual scan) is fine.
    # ISO "YYYY-MM-DD" strings compare chronologically, so "<" is correct here.
    if last_bar is None or last_bar < expected:
        msg = f"stale market data: last bar {last_bar or 'none'}, expected >= {expected}"
        log.warning("Aborting archive write: %s", msg)
        raise StaleMarketDataError(msg)

    _, meta_file = _cache_paths()
    health = compute_market_data_health(
        data, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file
    )
    if not health["can_archive"]:
        msg = (
            f"stale market data: {health['diagnosis']} "
            f"(eligible coverage {health['coverage']['eligible']['text']}, "
            f"raw coverage {health['coverage']['raw']['text']})"
        )
        log.warning("Aborting archive write: %s", msg)
        raise StaleMarketDataError(msg)


def _is_latest_coverage_error(exc: Exception) -> bool:
    return "latest-session close coverage" in str(exc).lower()


def run_scan_and_export(mode: str = "download") -> ScanExportResult:
    """Run the screener and write every non-broker output artifact."""
    try:
        results_df, data, tickers, market_context = run_screener(mode=mode)
    except CachedMarketDataError as exc:
        raise StaleMarketDataError(str(exc), n_setups=0) from exc

    if results_df.empty:
        print("\nNo setups found today. Filters are running tight, wait for the right pitch!")
        return ScanExportResult(n_setups=0, n_archived=0)

    print_results(results_df)

    output_dir = os.path.join(PROJECT_ROOT, "output", "watchlists")
    os.makedirs(output_dir, exist_ok=True)
    save_csv(results_df, output_dir)
    print_finviz_url(results_df)

    generate_dashboard(results_df, data, tickers, market_context)

    # Persist every setup to setup_archive (idempotent upsert by ticker+scan_date).
    # Forward returns are filled in later by core/archive/forward_returns.py.
    # Gated by settings.ARCHIVE_LIVE_SCANS so the behavior is config-visible.
    n_archived = 0
    if settings.ARCHIVE_LIVE_SCANS:
        try:
            _assert_fresh_for_archive(data, tickers)
        except StaleMarketDataError as exc:
            if mode == "cache" and _is_latest_coverage_error(exc):
                print(
                    "\nCached evaluation used partial latest-session coverage; "
                    "dashboard updated, archive write skipped.",
                    flush=True,
                )
                return ScanExportResult(n_setups=len(results_df), n_archived=0)
            exc.n_setups = len(results_df)
            raise
        n_archived = archive_scan_results(results_df, enable=True)
        print(f"\nArchived {n_archived} live setups to setup_archive (source='screener').")

    return ScanExportResult(n_setups=len(results_df), n_archived=n_archived)


def refresh_market_data_cache() -> DownloadOnlyResult:
    """Refresh ticker universe + market-data cache without evaluating setups."""
    tickers = get_tickers()
    cache_file, meta_file = _cache_paths()
    expected = _expected_session_date()
    before_health = _cached_health(cache_file, meta_file, tickers, expected)
    if before_health and before_health["can_archive"] and not before_health.get("weekly_refresh_due"):
        clear_repair_state(meta_file)
        print(f"\nMarket-data cache already healthy: {before_health['diagnosis']}", flush=True)
        return _download_result(tickers, before_health)

    if before_health and not before_health["can_download"] and not before_health["can_archive"]:
        print(f"\nMarket-data repair is not ready: {before_health['diagnosis']}", flush=True)
        return _download_result(tickers, before_health)

    if (before_health
            and before_health["health_state"] == "needs_repair"
            and before_health["can_download"]):
        data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
        min_coverage = before_health["coverage"]["archive_target"]
        symbols = before_health["missing_summary"]["eligible_missing_symbols"]
        repaired = repair_latest_session_cache(
            data,
            cache_file,
            meta_file,
            before_health["missing_summary"]["eligible_missing_symbols"],
            pd.Timestamp(expected),
            min_coverage,
            "Manual repair",
        )
        after_health = compute_market_data_health(
            repaired, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
            meta=_read_meta(meta_file)
        )
        if after_health["can_archive"]:
            clear_repair_state(meta_file)
        else:
            record_repair_attempt(meta_file, before_health, after_health)
            after_health = compute_market_data_health(
                repaired, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
                meta=_read_meta(meta_file)
            )
        print(f"\nManual repair checked {len(symbols)} eligible laggard(s).")
        print(after_health["diagnosis"], flush=True)
        return _download_result(tickers, after_health)

    try:
        data = get_provider().fetch(tickers)
    except Exception as exc:
        state = record_repair_attempt(meta_file, before_health, None, error_text=str(exc))
        msg = f"market-data provider failed: {exc}"
        log.warning("Download-only cache refresh failed: %s", msg)
        raise StaleMarketDataError(
            f"{msg}; retry {state.get('next_retry_at') or 'later'}",
            n_setups=None,
        ) from exc

    after_health = compute_market_data_health(
        data, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
        meta=_read_meta(meta_file)
    )
    if after_health["can_archive"]:
        clear_repair_state(meta_file)
    else:
        record_repair_attempt(meta_file, before_health, after_health)
        after_health = compute_market_data_health(
            data, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
            meta=_read_meta(meta_file)
        )

    if after_health["health_state"] == "stale_session":
        msg = f"stale market data: {after_health['diagnosis']}"
        log.warning("Download-only cache refresh did not reach current data: %s", msg)
        raise StaleMarketDataError(msg, n_setups=None)

    print(f"\nMarket-data cache health: {after_health['diagnosis']}", flush=True)
    return _download_result(tickers, after_health)


def _cached_health(cache_file: str, meta_file: str, tickers: list[str],
                   expected: str) -> dict | None:
    if not os.path.exists(cache_file):
        return None
    try:
        data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
    except Exception:
        return None
    return compute_market_data_health(
        data,
        tickers,
        expected_session=pd.Timestamp(expected),
        meta_file=meta_file,
        meta=_read_meta(meta_file),
        weekly_refresh_due=_weekly_refresh_due(_read_meta(meta_file)),
    )


def _weekly_refresh_due(meta: dict) -> bool:
    value = meta.get("last_full_refresh")
    if not value:
        return True
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return True
    age_days = (datetime.now(ts.tzinfo) - ts).days if ts.tzinfo else (datetime.now() - ts).days
    return age_days >= int(getattr(settings, "FULL_REFRESH_INTERVAL_DAYS", 7))


def _download_result(tickers: list[str], health: dict) -> DownloadOnlyResult:
    return DownloadOnlyResult(
        n_tickers=len(tickers),
        latest_session=health.get("cache_last_session"),
        expected_session=health.get("expected_session"),
        coverage=health["coverage"]["eligible"]["text"],
        health_state=health["health_state"],
        coverage_detail=health["coverage"],
        ready=bool(health["can_archive"]),
        partial=not bool(health["can_archive"]),
        cooldown_until=health.get("next_retry_at"),
        retry_reason=health.get("retry_reason"),
        help_needed=bool(health.get("help_needed")),
        message=health["diagnosis"],
    )
