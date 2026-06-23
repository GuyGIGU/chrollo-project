"""Turnkey edge-read runner for the live screener archive.

This script intentionally keeps the archive analysis tool read-only. It does
the one write step first (maturing forward returns), then calls the existing
report generator unchanged.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime

from core.archive import analyze
from core.archive.forward_returns import update_forward_returns

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _populated_20d_count(source: str | None) -> int:
    df = analyze.load_archive(source=source)
    if "fwd_return_20d" not in df.columns:
        return 0
    return int(df["fwd_return_20d"].notna().sum())


def run_edge_report(
    report_date: str,
    source: str | None = "screener",
    mature: bool = True,
    min_rows: int = 30,
) -> str:
    """Mature outcomes, run archive analysis, and return the report path."""
    before = _populated_20d_count(source)
    updated = 0
    if mature:
        updated = update_forward_returns()
    after = _populated_20d_count(source)
    newly_20d = max(0, after - before)

    source_label = source or "all"
    print(
        f"Forward-return maturation ({source_label} report scope): "
        f"fwd_return_20d {before} -> {after} (+{newly_20d}); "
        f"updater touched {updated} archive row(s) across all sources."
    )

    report_path = os.path.join("docs", f"edge_read_{report_date}.md")
    analyze.run(source=source, min_rows=min_rows, md_path=report_path)
    return os.path.join(PROJECT_ROOT, report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mature returns and write a Chrollo edge report.")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"),
                        help="Report date stamp, e.g. 20260629")
    parser.add_argument("--source", default="screener",
                        help="Archive source to analyze; default screener")
    parser.add_argument("--all", action="store_true",
                        help="Include all archive sources instead of only screener rows")
    parser.add_argument("--no-mature", action="store_true",
                        help="Skip forward-return maturation and only write the report")
    parser.add_argument("--min-rows", type=int, default=30,
                        help="Min live rows for correlation/outcome validity")
    args = parser.parse_args()

    source = None if args.all else args.source
    report_path = run_edge_report(
        report_date=args.date,
        source=source,
        mature=not args.no_mature,
        min_rows=args.min_rows,
    )
    print(f"Edge report written to {report_path}")


if __name__ == "__main__":
    main()
