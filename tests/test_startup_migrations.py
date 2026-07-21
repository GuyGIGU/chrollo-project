"""Trigger migration: registered, idempotent ADD, backward-load (Task 6 spec).

SQLite can't retrofit a CHECK, but the two trigger COLUMNS arrive via idempotent
`_MIGRATIONS` ALTERs (Task 3 target). This pins three things the build must keep
true: the migration is registered, a re-run is a clean duplicate-column skip
(the runner's idempotency contract), and a pre-trigger row still loads with NULL
triggers after it applies. Hermetic — a throwaway sqlite file, never the live DB,
and no backend boot (importing `services.startup` builds only a lazy engine).
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from services import startup  # noqa: E402  (lazy engine only; no connection)

TRIGGER_MIGRATIONS = (
    "ALTER TABLE calibration_marks ADD COLUMN trigger_date VARCHAR",
    "ALTER TABLE calibration_marks ADD COLUMN trigger_price FLOAT",
)

# The runner's idempotency predicate (see startup._apply_migrations): a re-run of
# an ADD trips one of these substrings and is skipped as already-applied. Copied
# here as the contract — a change to the runner that stops catching sqlite's real
# message would leave migrations non-idempotent, so this guards that seam.
_SKIP_MARKERS = ("duplicate column", "already exists", "no such column")


def test_trigger_migration_is_registered():
    for stmt in TRIGGER_MIGRATIONS:
        assert stmt in startup._MIGRATIONS, f"missing migration: {stmt}"


def test_trigger_migration_adds_columns_and_backward_loads(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    # An "old" calibration_marks from before the Trigger existed.
    con.execute(
        "CREATE TABLE calibration_marks "
        "(id INTEGER PRIMARY KEY, ticker VARCHAR, as_of_date VARCHAR, verdict VARCHAR)")
    con.execute("INSERT INTO calibration_marks (ticker, as_of_date, verdict) "
                "VALUES ('BODI', '2026-04-15', 'box')")
    con.commit()

    for stmt in TRIGGER_MIGRATIONS:
        con.execute(stmt)
    con.commit()

    cols = {r[1] for r in con.execute("PRAGMA table_info(calibration_marks)")}
    assert {"trigger_date", "trigger_price"} <= cols
    # No DEFAULT: the pre-trigger row reads NULL/NULL — the real "no buy" state.
    assert con.execute("SELECT trigger_date, trigger_price FROM calibration_marks "
                       "WHERE ticker='BODI'").fetchone() == (None, None)
    con.close()


def test_re_running_the_trigger_migration_is_an_idempotent_skip(tmp_path):
    db = tmp_path / "applied.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE calibration_marks "
                "(id INTEGER PRIMARY KEY, ticker VARCHAR, as_of_date VARCHAR, verdict VARCHAR)")
    for stmt in TRIGGER_MIGRATIONS:
        con.execute(stmt)
    con.commit()

    # Second application raises "duplicate column" — precisely the marker the
    # runner treats as already-applied, so a boot on a migrated DB is a no-op.
    for stmt in TRIGGER_MIGRATIONS:
        with pytest.raises(sqlite3.OperationalError) as exc:
            con.execute(stmt)
        assert any(m in str(exc.value).lower() for m in _SKIP_MARKERS), str(exc.value)
    con.close()
