"""
Archive analysis tool - the measuring stick for the screener.

A standalone, read-only CLI that reads the `setup_archive` table and produces a
human-readable report answering the questions that actually matter for tuning:

  1. SAMPLE COMPOSITION & BIAS - what kind of data do we have, and which
     analyses are currently *valid*? (Critical: a seed-only archive is a
     winners-only gallery - trigger/win rates are meaningless until live
     non-winners accrue. The tool detects this and says so loudly.)
  2. WINNER FINGERPRINT - the structural profile of the setups in the archive
     (median / IQR / range of every structural feature, segmented by tier and
     setup_type). On seed data this is the "what does a clean tight setup look
     like" profile to bias toward. This is the analysis that IS valid now.
  3. SEGMENTED PERFORMANCE - forward returns / R-multiples / trigger rate by
     tier, setup_type, zone, inner-vs-outer, tightness bucket, breadth regime,
     SPY trend. Becomes discriminative as losers accrue; shown now with caveat.
  4. PREDICTOR CORRELATIONS - every sub-score AND structural feature correlated
     against fwd_20d / fwd_60d / r_multiple_20d, ranked by |corr|. Extends the
     webapp /calibration endpoint (7 core sub-scores) to the full feature set,
     including the Phase-1 additions.
  5. PRIME-DIRECTIVE TEST - is TIGHTNESS predictive? Isolates box_width /
     atr_ratio / tightness_ratio / lps_descent_frac. When losers exist, splits
     tight-tertile vs loose-tertile and compares mean forward return.
  6. SIGNAL EDGE & SUBTRACTION CANDIDATES (Stage 1) - rank-associates every
     scoring sub-score with realized outcome (barrier_win / r_multiple / fwd
     return) and flags each as BENEFICIAL / INERT / HARMFUL via an n-aware
     noise floor. The actionable shortlist for "subtract harmful signals".
     Read-only: flags candidates, never changes a weight.

This module loads the archive and runs the report. The columns it reads are
named in ``analyze_features``, the numbers come from ``analyze_stats`` and the
text from ``analyze_report``.

Usage:
    python -m core.archive.analyze                 # full report to stdout
    python -m core.archive.analyze --md report.md  # also write a markdown copy
    python -m core.archive.analyze --source screener   # restrict to live scans
    python -m core.archive.analyze --min-rows 30   # raise the stat-validity bar

Read-only: never writes to the DB.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from typing import Optional

import pandas as pd

from core.archive.analyze_report import (
    _LINES,
    emit,
    header,
    section_composition,
    section_correlations,
    section_fingerprint,
    section_performance,
    section_signal_edge,
    section_tightness,
)
from core.archive.db_path import archive_db_path
from core.archive.episodes import SetupRow, build_episodes, canonical_ids
from core.pipeline.universe.descriptor import DEFAULT_UNIVERSE_TYPE

# Names importers take from this module; they live in the modules named in the
# docstring and stay importable here.
from core.archive.analyze_features import (  # noqa: F401  (re-export for import compatibility)
    PHASE_A_ANCHOR_FEATURES,
    STRUCTURAL_FEATURES,
    SUB_SCORES,
    anchor_seam,
    current_epoch,
    engine_epochs,
)
from core.archive.analyze_stats import (  # noqa: F401  (re-export for import compatibility)
    EDGE_MIN_MINORITY,
    EDGE_MIN_N,
    EDGE_TARGETS,
    MAGNITUDE_TARGET,
    MAGNITUDE_THRESHOLD,
    _perf_row,
    derive_outcomes,
    safe_rank_corr,
    signal_edge,
    suggested_weights,
)
from core.backtest.edge_report import TAIL_MFE_COL  # noqa: F401  (re-export for import compatibility)

# ------------------------------------------------------------------
# Paths & loading
# ------------------------------------------------------------------
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_DB_PATH = archive_db_path()


def load_archive(source: Optional[str] = None,
                 universe_type: Optional[str] = DEFAULT_UNIVERSE_TYPE) -> pd.DataFrame:
    """Read the setup_archive table into a DataFrame (read-only).

    universe_type: scope to one universe ('us_equities' / 'us_sectors' /
        'commodities_etf'). Defaults to 'us_equities' so the ETF/sector rows that
        also archive under source='screener' can't contaminate the headline stats
        (matches the backend + core/backtest/loader.py scoping). Ignored on a
        pre-migration DB that lacks the column.
    """
    if not os.path.exists(_DB_PATH):
        raise FileNotFoundError(f"Archive DB not found at {_DB_PATH}")
    # mode=ro URI: the tool's read-only contract enforced by the connection
    # itself (same pattern as seed_recall.load_seed_rows) — a future write
    # attempt errors loudly instead of holding by discipline alone.
    con = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query("SELECT * FROM setup_archive", con)
    finally:
        con.close()
    if source:
        df = df[df["source"] == source].copy()
    if universe_type is not None and "universe_type" in df.columns:
        df = df[df["universe_type"] == universe_type].copy()
    return df


def dedup_to_episodes(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse continuation re-flags to one canonical (first-seen) row per episode.

    The screener re-flags a persisting base every day it holds, so the raw
    setup_archive carries many continuation rows for one logical setup. Counting
    each as an independent observation inflates n and biases every correlation /
    edge verdict toward whatever the long-persisting bases happened to do — a base
    seen 15 days that then ran contributes 15 correlated points, not 1. (The
    inflation is real but often modest: e.g. score_rs_bonus vs durable_win moves
    only ~-0.20 -> -0.18 under dedup and stays HARMFUL; the larger swing to INERT
    that some cuts show is target/cohort-specific — notably vs fwd_return_20d on a
    single matured cohort — not a general guarantee that dedup neutralizes a
    signal. Dedup fixes n-inflation; it does not by itself de-confound regime.)

    Reuses the SAME first-seen grouper the archive episode table and the
    ``/calibration`` canonical path use (``core.archive.episodes``), so this stays
    in lock-step with them. The kept row is each episode's first-seen anchor — the
    correct entry date, carrying its own (non-stale) forward returns.

    Degrades gracefully: returns the frame unchanged if it is empty or lacks the
    identity columns episodes needs (an older/partial DB).
    """
    needed = {"id", "ticker", "scan_date", "setup_type"}
    if df.empty or not needed.issubset(df.columns):
        return df
    universe = (df["universe_type"].fillna(DEFAULT_UNIVERSE_TYPE)
                if "universe_type" in df.columns
                else pd.Series(DEFAULT_UNIVERSE_TYPE, index=df.index))
    rows = [
        SetupRow(id=int(i), ticker=str(t), scan_date=str(d),
                 setup_type=str(s), universe_type=str(u))
        for i, t, d, s, u in zip(df["id"], df["ticker"], df["scan_date"],
                                 df["setup_type"], universe)
    ]
    keep = canonical_ids(build_episodes(rows))
    return df[df["id"].isin(keep)].copy()


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------
def run(source: Optional[str] = None, min_rows: int = 30, md_path: Optional[str] = None,
        dedup: bool = True) -> None:
    _LINES.clear()
    raw = load_archive(source=source)
    df = dedup_to_episodes(raw) if dedup else raw

    _preamble(raw, df, source, dedup)
    comp = section_composition(df, min_rows)
    section_fingerprint(df)
    section_performance(df, comp["valid_outcome"])
    section_correlations(df, comp["valid_corr"])
    section_tightness(df, comp["valid_outcome"])
    section_signal_edge(df, comp["valid_corr"])

    header("END OF REPORT")

    report = "\n".join(_LINES)
    print(report)
    if md_path:
        _write_markdown(report, md_path)


def _preamble(raw: pd.DataFrame, df: pd.DataFrame, source: Optional[str], dedup: bool) -> None:
    """Which archive, which rows, and whether re-flags were collapsed."""
    header("CHROLLO ARCHIVE ANALYSIS")
    emit(f"DB: {_DB_PATH}")
    if source:
        emit(f"Filtered to source = '{source}'")
    if dedup:
        n_removed = len(raw) - len(df)
        emit(f"Episode dedup: {len(raw)} raw rows -> {len(df)} episodes "
             f"({n_removed} continuation re-flags collapsed to the first-seen anchor).")
        emit("All sections below run on EPISODES (one row per logical setup) via the same")
        emit("first-seen grouping the archive episode table + /calibration use — raw")
        emit("continuation re-flags would inflate n and bias every correlation / edge verdict.")
    else:
        emit("!! --no-dedup: continuation re-flags NOT collapsed; stats are inflated (debug only).")


def _write_markdown(report: str, md_path: str) -> None:
    """Write a fenced copy of the report; a relative path lands under the project root."""
    out = md_path if os.path.isabs(md_path) else os.path.join(_PROJECT_ROOT, md_path)
    with open(out, "w", encoding="utf-8") as f:
        f.write("```\n" + report + "\n```\n")
    print(f"\n[report written to {out}]")


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze the Chrollo setup archive.")
    ap.add_argument("--source", default=None,
                    help="Restrict to a source: screener / seed / manual")
    ap.add_argument("--min-rows", type=int, default=30,
                    help="Min live rows for correlation/outcome validity (default 30)")
    ap.add_argument("--md", default=None, help="Also write a markdown copy to this path")
    ap.add_argument("--no-dedup", action="store_true",
                    help="Do NOT collapse continuation re-flags to episodes (debug; inflates stats)")
    args = ap.parse_args()
    run(source=args.source, min_rows=args.min_rows, md_path=args.md, dedup=not args.no_dedup)


if __name__ == "__main__":
    main()
