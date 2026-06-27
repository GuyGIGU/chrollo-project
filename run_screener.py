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
import sys
import json
import argparse
from pathlib import Path

# Ensure project root is on the Python path so all imports resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pipeline.scan_job import StaleMarketDataError, refresh_market_data_cache, run_scan_and_export


def _print_result_json(n_setups: int, n_archived: int) -> None:
    print(
        "SCAN_RESULT_JSON:"
        + json.dumps({"n_setups": n_setups, "n_archived": n_archived}),
        flush=True,
    )


def _print_download_json(result) -> None:
    print(
        "DOWNLOAD_RESULT_JSON:"
        + json.dumps({
            "n_tickers": result.n_tickers,
            "latest_session": result.latest_session,
            "expected_session": result.expected_session,
            "coverage": result.coverage,
            "health_state": result.health_state,
            "coverage_detail": result.coverage_detail,
            "ready": result.ready,
            "partial": result.partial,
            "cooldown_until": result.cooldown_until,
            "retry_reason": result.retry_reason,
            "help_needed": result.help_needed,
            "message": result.message,
        }),
        flush=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Chrollo screener jobs.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cached", action="store_true",
                       help="evaluate the existing market-data cache without downloading")
    group.add_argument("--download-only", action="store_true",
                       help="refresh ticker universe and market-data cache without evaluation")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        if args.download_only:
            download_result = refresh_market_data_cache()
            _print_download_json(download_result)
            return
        result = run_scan_and_export(mode="cache" if args.cached else "download")
    except StaleMarketDataError as exc:
        _print_result_json(exc.n_setups or 0, 0)
        raise
    _print_result_json(result.n_setups, result.n_archived)


if __name__ == '__main__':
    main()
