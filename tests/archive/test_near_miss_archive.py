"""The near-miss cohort store: read-only history since the old engine retired (Fri 30/10/2026).

The lane, its writer and its outcomes refresh are gone; the table stays for the rows the lane
wrote. What this still pins: the fresh-DB CHECKs that close the label sets, the retired
would-be pair's one-off DROP, and the generalized model-diff migrator covering the table.
Hermetic: throwaway sqlite files, never the live DB.
"""
from __future__ import annotations

import sqlite3
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
from app import startup  # noqa: E402

pytestmark = pytest.mark.regression


def test_fresh_db_checks_close_the_label_sets(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    archive_models.NearMissArchive.__table__.create(bind=eng)
    db = sessionmaker(bind=eng)()

    def _model(ticker, leg, pool):
        return archive_models.NearMissArchive(
            ticker=ticker, universe_type="us_equities", r_level=10.0,
            s_level=9.0, r_anchor_date="2026-01-02",
            s_anchor_date="2026-01-06", first_seen="2026-02-02",
            last_seen="2026-02-02", nights_seen=1, fired_first_night=0,
            fired_any_night=0, pool=pool, kill_stage=leg, failing_leg=leg,
            lane_ruleset="2026-07-26.A", engine_config_version="x",
            judged_n=20, window_start_date="2026-01-02",
            window_end_date="2026-02-02", nm_width=0.1, nm_respect_share=1,
            nm_respect_run=1, nm_crash=0.1, nm_r_touches=1, nm_s_touches=1,
            nm_r_touch_thirds=1, nm_s_touch_thirds=1, nm_lower_dwell=1,
            nm_upper_dwell=1, nm_mid_dwell=1, nm_coverage=1,
            nm_traversal_count=1, nm_traversal_density=0.1,
            would_be_trigger=10.0, scan_close=9.5)

    db.add(_model("OK1", "occupancy", "strict"))
    db.commit()
    db.add(_model("BAD1", "typo_leg", "strict"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(_model("BAD2", "occupancy", "story"))   # story is policy, never a pool here
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


_WOULD_BE_DROPS = (
    "ALTER TABLE near_miss_archive DROP COLUMN would_be_score",
    "ALTER TABLE near_miss_archive DROP COLUMN would_be_tier",
)

# The runner's idempotency predicate (see startup._apply_migrations) — the
# same contract test_startup_migrations pins for the ADD side.
_SKIP_MARKERS = ("duplicate column", "already exists", "no such column")


def test_would_be_pair_is_retired_model_and_migration():
    """would_be_score/would_be_tier were declared, rendered, and unwritable —
    no writer ever existed, and a refused framing has no election context to
    score (council review 2026-08-22). The model must not re-grow the pair,
    and the one-off DROP must be registered so a DB restored from a pre-drop
    backup converges instead of resurrecting the columns permanently."""
    cols = {c.name for c in archive_models.NearMissArchive.__table__.columns}
    assert "would_be_score" not in cols and "would_be_tier" not in cols
    for stmt in _WOULD_BE_DROPS:
        assert stmt in startup._MIGRATIONS, f"missing migration: {stmt}"


def test_would_be_drop_converges_a_predrop_db_and_rerun_is_idempotent(tmp_path):
    """A pre-drop DB (columns present) converges on one application; a re-run
    on the already-clean DB raises exactly a skip-marker error — the runner's
    already-applied contract, so a boot on a migrated DB is a no-op."""
    db = tmp_path / "predrop.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE near_miss_archive "
                "(id INTEGER PRIMARY KEY, ticker VARCHAR, "
                "would_be_score FLOAT, would_be_tier VARCHAR)")
    con.commit()

    for stmt in _WOULD_BE_DROPS:
        con.execute(stmt)
    con.commit()
    cols = {r[1] for r in con.execute("PRAGMA table_info(near_miss_archive)")}
    assert "would_be_score" not in cols and "would_be_tier" not in cols

    for stmt in _WOULD_BE_DROPS:
        with pytest.raises(sqlite3.OperationalError) as exc:
            con.execute(stmt)
        assert any(m in str(exc.value).lower() for m in _SKIP_MARKERS), str(exc.value)
    con.close()


def test_model_diff_migrator_covers_the_new_table_at_birth(tmp_path):
    assert any(t == "near_miss_archive"
               for t, _m in startup._MIGRATED_ARCHIVE_MODELS)
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE near_miss_archive "
                "(id INTEGER PRIMARY KEY, ticker VARCHAR)")
    con.commit()
    con.close()
    eng = create_engine(f"sqlite:///{db}")
    statements = startup.model_add_column_migrations(eng)
    added = {s.split(" ADD COLUMN ")[1].split(" ")[0]
             for s in statements if "near_miss_archive" in s}
    model_cols = {c.name for c in
                  archive_models.NearMissArchive.__table__.columns
                  if not c.primary_key}
    assert added == model_cols - {"ticker"}, (
        "the generalized migrator must surface every model-only column")
