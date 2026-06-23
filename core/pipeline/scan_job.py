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
from core.pipeline.data_freshness import close_coverage_on, unique_symbols
from core.pipeline.market_calendar import latest_completed_session
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
    # The canonical fetch path trims forming bars before scans/cache writes.
    # This archive guard rejects older data, and defensively rejects newer data
    # when completed-session trimming is enabled.
    if last_bar is None or last_bar < expected:
        msg = f"stale market data: last bar {last_bar or 'none'}, expected >= {expected}"
        log.warning("Aborting archive write: %s", msg)
        raise StaleMarketDataError(msg)
    if getattr(settings, "TRIM_MARKET_DATA_TO_COMPLETED_SESSION", True) and last_bar > expected:
        msg = f"immature market data: last bar {last_bar}, expected completed session {expected}"
        log.warning("Aborting archive write: %s", msg)
        raise StaleMarketDataError(msg)

    index_symbols = getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL])
    coverage_symbols = unique_symbols(list(tickers) + list(index_symbols))
    min_latest_coverage = getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)
    coverage = close_coverage_on(data, coverage_symbols, pd.Timestamp(expected))
    if coverage.ratio < min_latest_coverage:
        msg = (
            f"stale market data: latest-session close coverage {coverage.format()} "
            f"on {expected}, required >= {min_latest_coverage:.0%}"
        )
        log.warning("Aborting archive write: %s", msg)
        raise StaleMarketDataError(msg)


def run_scan_and_export() -> ScanExportResult:
    """Run the screener and write every non-broker output artifact."""
    results_df, data, tickers, market_context = run_screener()

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
            exc.n_setups = len(results_df)
            raise
        n_archived = archive_scan_results(results_df, enable=True)
        print(f"\nArchived {n_archived} live setups to setup_archive (source='screener').")

    return ScanExportResult(n_setups=len(results_df), n_archived=n_archived)
