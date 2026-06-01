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

from core.pipeline.scan_job import run_scan_and_export


def main() -> None:
    result = run_scan_and_export()
    print(
        "SCAN_RESULT_JSON:"
        + json.dumps({"n_setups": result.n_setups, "n_archived": result.n_archived}),
        flush=True,
    )


if __name__ == '__main__':
    main()
