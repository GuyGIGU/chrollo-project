"""Read-only archive load + episode collapse for the backtest harness.

Loads the ``setup_archive`` table into a DataFrame **read-only** (never mutates
the production DB) and collapses persisting-base re-flags into one row per logical
setup using ``core.archive.episodes.build_episodes`` (REUSED verbatim).

The production DB is opened with a sqlite ``file:...?mode=ro`` URI so a write is
impossible by construction. Tests pass their own in-memory connection or a fixture
DataFrame, so this module is exercised without touching any real file.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional

import pandas as pd

from core.archive.episodes import (
    SetupRow,
    build_episodes,
    canonical_ids,
    episode_by_member_id,
)

# Absolute path to the production archive. Read-only here; the harness never
# writes. Mirrors core/archive/analyze._DB_PATH but resolved independently so a
# cwd change can't rebind it.
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "webapp", "backend", "trading_journal.db")


def _connect_readonly(db_path: str) -> sqlite3.Connection:
    """Open ``db_path`` strictly read-only via a sqlite URI.

    ``mode=ro`` makes any write raise, so the production archive cannot be
    mutated even by accident. ``immutable=1`` is deliberately NOT used — the
    daily forward-return job may be writing concurrently, and ro tolerates that.
    """
    uri = f"file:{db_path.replace(os.sep, '/')}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_archive(
    db_path: Optional[str] = None,
    source: Optional[str] = None,
    con: Optional[sqlite3.Connection] = None,
) -> pd.DataFrame:
    """Read the ``setup_archive`` table into a DataFrame (read-only).

    Args:
        db_path: path to the sqlite archive; defaults to the production DB.
        source: optional ``source`` filter ('screener' / 'seed' / 'manual').
            For an UNBIASED standalone-edge read, pass 'screener' — seed rows are
            a hand-picked winners gallery and re-scans carry survivorship bias.
        con: an already-open connection (e.g. an in-memory fixture in tests). When
            given, ``db_path`` is ignored and the connection is NOT closed here.
    """
    own_con = con is None
    if own_con:
        path = db_path or DEFAULT_DB_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"Archive DB not found at {path}")
        con = _connect_readonly(path)
    try:
        df = pd.read_sql_query("SELECT * FROM setup_archive", con)
    finally:
        if own_con:
            con.close()

    if source is not None and "source" in df.columns:
        df = df[df["source"] == source].copy()
    return df


def _setup_rows(df: pd.DataFrame) -> list[SetupRow]:
    """Project archive rows into the minimal ``SetupRow`` episodes needs."""
    rows: list[SetupRow] = []
    for r in df.itertuples(index=False):
        sid = getattr(r, "id", None)
        ticker = getattr(r, "ticker", None)
        scan_date = getattr(r, "scan_date", None)
        setup_type = getattr(r, "setup_type", None)
        if sid is None or ticker is None or scan_date is None:
            continue
        rows.append(
            SetupRow(
                id=int(sid),
                ticker=str(ticker),
                scan_date=str(scan_date),
                setup_type=str(setup_type) if setup_type is not None else "",
            )
        )
    return rows


def collapse_to_episodes(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per logical setup (the episode's first-seen / entry anchor).

    REUSES ``core.archive.episodes.build_episodes`` verbatim. A persisting base
    re-flagged on consecutive days collapses to its first-seen row — the correct
    entry date for forward returns and the de-duplicated unit for honest stats.

    Adds an ``episode_scan_count`` column (how many daily scans flagged the base)
    for transparency. Rows without an ``id`` are dropped (can't be anchored).
    """
    if df.empty or "id" not in df.columns:
        out = df.copy()
        out["episode_scan_count"] = pd.Series(dtype="int64")
        return out

    rows = _setup_rows(df)
    episodes = build_episodes(rows)
    keep_ids = canonical_ids(episodes)
    by_member = episode_by_member_id(episodes)

    out = df[df["id"].isin(keep_ids)].copy()
    out["episode_scan_count"] = out["id"].map(
        lambda i: by_member[int(i)].scan_count if int(i) in by_member else 1
    )
    return out


def load_episodes(
    db_path: Optional[str] = None,
    source: Optional[str] = None,
    con: Optional[sqlite3.Connection] = None,
) -> pd.DataFrame:
    """Convenience: load the archive then collapse to one row per episode."""
    return collapse_to_episodes(load_archive(db_path=db_path, source=source, con=con))
