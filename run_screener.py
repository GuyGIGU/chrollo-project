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
from pathlib import Path

# Ensure project root is on the Python path so all imports resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pipeline.scan_job import StaleMarketDataError, run_scan_and_export


def _print_result_json(n_setups: int, n_archived: int) -> None:
    print(
        "SCAN_RESULT_JSON:"
        + json.dumps({"n_setups": n_setups, "n_archived": n_archived}),
        flush=True,
    )


def main() -> None:
    try:
        result = run_scan_and_export()
    except StaleMarketDataError as exc:
        _print_result_json(exc.n_setups or 0, 0)
        raise
    _print_result_json(result.n_setups, result.n_archived)


if __name__ == '__main__':
    main()
