"""Reusable scan -> dashboard -> archive job."""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from config import settings
from core.archive.writer import archive_scan_results
from core.pipeline import run_screener
from output.dashboard import generate_dashboard
from output.terminal import print_finviz_url, print_results, save_csv

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
log = logging.getLogger("chrollo.scan_job")


class StaleMarketDataError(RuntimeError):
    """Raised when a scan should not be archived because data is stale."""


@dataclass
class ScanExportResult:
    n_setups: int
    n_archived: int


def _previous_business_day(day: pd.Timestamp) -> pd.Timestamp:
    return (day - pd.tseries.offsets.BDay(1)).normalize()


def _expected_session_date() -> str:
    now_et = datetime.now(ZoneInfo("America/New_York"))
    today = pd.Timestamp(now_et.date())
    after_close = (now_et.hour, now_et.minute) >= (16, 0)
    if now_et.weekday() < 5 and after_close:
        expected = today
    else:
        expected = _previous_business_day(today)
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


def run_scan_and_export() -> ScanExportResult:
    """Run the screener and write every non-broker output artifact."""
    results_df, data, tickers = run_screener()

    if results_df.empty:
        print("\nNo setups found today. Filters are running tight, wait for the right pitch!")
        return ScanExportResult(n_setups=0, n_archived=0)

    print_results(results_df)

    output_dir = os.path.join(PROJECT_ROOT, "output", "watchlists")
    os.makedirs(output_dir, exist_ok=True)
    save_csv(results_df, output_dir)
    print_finviz_url(results_df)

    generate_dashboard(results_df, data, tickers)

    # Persist every setup to setup_archive (idempotent upsert by ticker+scan_date).
    # Forward returns are filled in later by core/archive/forward_returns.py.
    # Gated by settings.ARCHIVE_LIVE_SCANS so the behavior is config-visible.
    n_archived = 0
    if settings.ARCHIVE_LIVE_SCANS:
        _assert_fresh_for_archive(data, tickers)
        n_archived = archive_scan_results(results_df, enable=True)
        print(f"\nArchived {n_archived} live setups to setup_archive (source='screener').")

    return ScanExportResult(n_setups=len(results_df), n_archived=n_archived)
