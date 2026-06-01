"""Reusable scan -> dashboard -> archive job."""
from __future__ import annotations

import os
from dataclasses import dataclass

from config import settings
from core.archive.writer import archive_scan_results
from core.pipeline import run_screener
from output.dashboard import generate_dashboard
from output.terminal import print_finviz_url, print_results, save_csv

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


@dataclass
class ScanExportResult:
    n_setups: int
    n_archived: int


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
        n_archived = archive_scan_results(results_df, enable=True)
        print(f"\nArchived {n_archived} live setups to setup_archive (source='screener').")

    return ScanExportResult(n_setups=len(results_df), n_archived=n_archived)
