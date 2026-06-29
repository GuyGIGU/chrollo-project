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
