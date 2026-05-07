#!/usr/bin/env python3
"""
Entry point for the Wyckoff VCP/LPS Screener.

Usage:
    python run_screener.py

All configuration lives in config/settings.py.

This script is the seam between the pure screening engine (``core/``)
and the output layer (``output/``): ``core`` stays unaware of how results
are displayed or persisted.
"""
import os
import sys

# Ensure project root is on the Python path so all imports resolve cleanly
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.archive_writer import archive_scan_results
from core.screener_v2 import run_screener
from output.dashboard import generate_dashboard
from output.terminal import print_finviz_url, print_results, save_csv


def main() -> None:
    results_df, data, tickers = run_screener()

    if results_df.empty:
        print("\nNo setups found today. Filters are running tight, wait for the right pitch!")
        return

    print_results(results_df)

    output_dir = os.path.join(PROJECT_ROOT, 'output', 'watchlists')
    os.makedirs(output_dir, exist_ok=True)
    save_csv(results_df, output_dir)
    print_finviz_url(results_df)

    generate_dashboard(results_df, data, tickers)

    # Persist every setup to setup_archive (idempotent upsert by ticker+scan_date).
    # Forward returns are filled in later by core/update_forward_returns.py.
    archive_scan_results(results_df)


if __name__ == '__main__':
    main()
