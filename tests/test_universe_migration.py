"""Task 3 — the universe_type migration is idempotent: a DB already carrying the
column (a fresh DB from the current model, or a re-run after the one-off rebuild)
is a no-op. The full rebuild + backfill is verified against real data separately;
this pins the guard that keeps it from running twice."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
from database import make_sqlite_engine  # noqa: E402
from services.startup import migrate_universe_type  # noqa: E402


def test_migration_is_noop_when_universe_type_present(tmp_path):
    db = str(tmp_path / "current_schema.db")
    eng = make_sqlite_engine(db)
    # create_all from the current model -> table already has universe_type.
    archive_models.SetupArchive.__table__.create(bind=eng)
    assert migrate_universe_type(eng) is False
    eng.dispose()


def test_migration_is_noop_on_missing_table(tmp_path):
    db = str(tmp_path / "empty.db")
    eng = make_sqlite_engine(db)
    # No setup_archive table at all (fresh DB before create_all) -> no-op.
    assert migrate_universe_type(eng) is False
    eng.dispose()


def test_migration_rebuilds_and_backfills_a_legacy_db(tmp_path):
    """Exercise the actual rebuild body on a legacy-schema DB (no universe_type,
    2-col unique): row count preserved, column added, every row backfilled to
    'us_equities', and the widened 3-col identity in place. This is the behavioral
    coverage the live one-time rehearsal couldn't provide as a repeatable check."""
    import sqlite3

    # The NOT NULL columns the rebuilt schema requires (minus PK + universe_type,
    # which the backfill supplies) — so INSERT…SELECT can't hit a NOT NULL wall.
    required = [c.name for c in archive_models.SetupArchive.__table__.columns
                if not c.nullable and not c.primary_key and c.name != "universe_type"]
    assert "ticker" in required and "scan_date" in required

    db = str(tmp_path / "legacy.db")
    con = sqlite3.connect(db)
    cols_ddl = ", ".join(f"{c} TEXT" for c in required)
    con.execute(
        f"CREATE TABLE setup_archive (id INTEGER PRIMARY KEY, {cols_ddl}, "
        f"UNIQUE(ticker, scan_date))"  # the OLD 2-col identity
    )

    def _row(i):
        return tuple(
            f"TICK{i}" if c == "ticker" else f"2026-01-0{i}" if c == "scan_date" else "1"
            for c in required
        )

    placeholders = ", ".join("?" for _ in required)
    con.executemany(
        f"INSERT INTO setup_archive ({', '.join(required)}) VALUES ({placeholders})",
        [_row(1), _row(2)],
    )
    con.commit()
    con.close()

    assert migrate_universe_type(make_sqlite_engine(db)) is True   # performed rebuild
    assert migrate_universe_type(make_sqlite_engine(db)) is False  # now idempotent

    con = sqlite3.connect(db)
    try:
        assert con.execute("SELECT COUNT(*) FROM setup_archive").fetchone()[0] == 2  # no loss
        cols = [r[1] for r in con.execute("PRAGMA table_info(setup_archive)").fetchall()]
        assert "universe_type" in cols
        # backfill value is LOCKED (engine_edge/load_archive filter on exactly this)
        distinct = {r[0] for r in con.execute("SELECT DISTINCT universe_type FROM setup_archive").fetchall()}
        assert distinct == {"us_equities"}
        # the widened 3-col identity exists
        uniques = []
        for idx in con.execute("PRAGMA index_list(setup_archive)").fetchall():
            if idx[2]:
                uniques.append({r[2] for r in con.execute(f"PRAGMA index_info('{idx[1]}')").fetchall()})
        assert {"ticker", "scan_date", "universe_type"} in uniques
    finally:
        con.close()
