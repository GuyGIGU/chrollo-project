"""Pins the analyze.py episode-dedup invariant (E0).

dedup_to_episodes is the single point that keeps the standalone analyze CLI in
lock-step with the archive episode table + backend /calibration _canonical_setups
(all three reuse core.archive.episodes). These tests assert the invariant directly
so a future refactor of the grouper can't silently drift analyze's reported
population without a test failing.
"""
import sys

import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.archive.analyze import dedup_to_episodes
from core.archive.episodes import SetupRow, build_episodes, canonical_ids


def _df(rows):
    return pd.DataFrame(rows)


def _row(id, ticker, scan_date, setup_type="LPS", universe_type="us_equities"):
    return {"id": id, "ticker": ticker, "scan_date": scan_date,
            "setup_type": setup_type, "universe_type": universe_type}


def test_keeps_first_seen_anchor_per_episode():
    # one persisting base (3 consecutive days) collapses to its first-seen row.
    df = _df([_row(1, "AAA", "2026-06-01"), _row(2, "AAA", "2026-06-02"),
              _row(3, "AAA", "2026-06-03"), _row(4, "BBB", "2026-06-01")])
    out = dedup_to_episodes(df)
    assert set(out["id"]) == {1, 4}


def test_matches_canonical_ids_exactly():
    # The kept set must equal the grouper's canonical ids — the /calibration lock-step.
    df = _df([_row(1, "AAA", "2026-06-01"), _row(2, "AAA", "2026-06-02"),
              _row(5, "BBB", "2026-06-01"), _row(6, "BBB", "2026-06-02")])
    rows = [SetupRow(id=int(r["id"]), ticker=r["ticker"], scan_date=r["scan_date"],
                     setup_type=r["setup_type"], universe_type=r["universe_type"])
            for _, r in df.iterrows()]
    assert set(dedup_to_episodes(df)["id"]) == canonical_ids(build_episodes(rows))


def test_gap_splits_into_two_episodes():
    # A multi-week gap = base broke and re-formed: two episodes, each keeps its first-seen.
    df = _df([_row(1, "AAA", "2026-05-04"), _row(2, "AAA", "2026-05-05"),
              _row(9, "AAA", "2026-06-01")])
    assert set(dedup_to_episodes(df)["id"]) == {1, 9}


def test_two_universes_do_not_merge():
    # Same ticker+setup in two universes = two distinct setups; both kept.
    df = _df([_row(1, "XLE", "2026-06-01", universe_type="us_equities"),
              _row(2, "XLE", "2026-06-02", universe_type="commodities_etf")])
    assert set(dedup_to_episodes(df)["id"]) == {1, 2}


def test_missing_identity_columns_returns_unchanged():
    # An older/partial DB lacking the grouping columns degrades gracefully (no crash).
    df = _df([{"ticker": "AAA", "scan_date": "2026-06-01"}])
    assert len(dedup_to_episodes(df)) == 1


def test_absent_universe_type_defaults_and_still_dedups():
    # No universe_type column: defaults to us_equities and still collapses re-flags.
    df = _df([{"id": 1, "ticker": "AAA", "scan_date": "2026-06-01", "setup_type": "LPS"},
              {"id": 2, "ticker": "AAA", "scan_date": "2026-06-02", "setup_type": "LPS"}])
    assert set(dedup_to_episodes(df)["id"]) == {1}


def test_empty_frame_is_safe():
    assert dedup_to_episodes(pd.DataFrame()).empty
