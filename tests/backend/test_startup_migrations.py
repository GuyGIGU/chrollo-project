"""Trigger migration: registered, idempotent ADD, backward-load (Task 6 spec).

SQLite can't retrofit a CHECK, but the two trigger COLUMNS arrive via idempotent
`_MIGRATIONS` ALTERs (Task 3 target). This pins three things the build must keep
true: the migration is registered, a re-run is a clean duplicate-column skip
(the runner's idempotency contract), and a pre-trigger row still loads with NULL
triggers after it applies. Hermetic — a throwaway sqlite file, never the live DB,
and no backend boot (importing `app.startup` builds only a lazy engine).
"""
import sqlite3
import sys

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402  (resolves via BACKEND_DIR)
from sqlalchemy import create_engine  # noqa: E402
from app import startup  # noqa: E402  (lazy engine only; no connection)

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


# ── The drawn-event vocabulary rebuild (2026-08-26) ──────────────────
# Widening EVENT_TYPES cannot be an ALTER — SQLite freezes a CHECK into the
# table's DDL — so migrate_calibration_event_types REBUILDS the table. These
# drive it on a throwaway file carrying the live shape, never the real DB.

_OLD_EVENTS_DDL = (
    "CREATE TABLE calibration_mark_events ("
    " id INTEGER NOT NULL PRIMARY KEY,"
    " mark_id INTEGER NOT NULL,"
    " event_type VARCHAR NOT NULL,"
    " start_date VARCHAR NOT NULL,"
    " end_date VARCHAR NOT NULL,"
    " tip_date VARCHAR,"
    " tip_price FLOAT,"
    " source VARCHAR NOT NULL,"
    " CONSTRAINT ck_calibration_event_type"
    "  CHECK (event_type IN ('phase_c', 'lps', 'spring_test')),"
    " CONSTRAINT ck_calibration_event_span CHECK (start_date <= end_date),"
    " FOREIGN KEY(mark_id) REFERENCES calibration_marks (id) ON DELETE CASCADE)"
)

# Shaped like the live corpus: several LPS, a Phase C with a tip, a spring test.
_LEGACY_ROWS = [
    (1, 1, "lps", "2026-04-09", "2026-04-15", None, None, "operator"),
    (2, 1, "phase_c", "2026-02-10", "2026-03-20", "2026-03-02", 6.77, "operator"),
    (3, 2, "lps", "2026-01-05", "2026-01-09", None, None, "extraction"),
    (4, 2, "spring_test", "2026-01-20", "2026-01-22", None, None, "operator"),
]

_INSERT_EVENT = (
    "INSERT INTO calibration_mark_events (mark_id, event_type, start_date, "
    "end_date, source) VALUES (?, ?, ?, ?, 'operator')"
)


def _live_shaped_db(tmp_path, name="live.db"):
    db = tmp_path / name
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE calibration_marks (id INTEGER PRIMARY KEY, ticker VARCHAR)")
    con.execute(_OLD_EVENTS_DDL)
    con.executemany(
        "INSERT INTO calibration_mark_events (id, mark_id, event_type, start_date, "
        "end_date, tip_date, tip_price, source) VALUES (?,?,?,?,?,?,?,?)", _LEGACY_ROWS)
    con.commit()
    con.close()
    return db


def _engine_for(db):
    # as_posix(): a Windows path with backslashes does not survive URL parsing.
    return create_engine(f"sqlite:///{db.as_posix()}")


def test_event_vocabulary_rebuild_preserves_every_drawn_mark(tmp_path):
    """The rebuild is the ONLY path that reaches the live table, so it must
    carry every operator row across byte-for-byte — ids included."""
    db = _live_shaped_db(tmp_path)
    engine = _engine_for(db)
    try:
        assert startup.migrate_calibration_event_types(engine) is True
    finally:
        engine.dispose()

    con = sqlite3.connect(db)
    assert sorted(con.execute(
        "SELECT id, mark_id, event_type, start_date, end_date, tip_date, tip_price, "
        "source FROM calibration_mark_events").fetchall()) == sorted(_LEGACY_ROWS)
    # The new columns arrive NULL on every pre-existing row.
    assert con.execute("SELECT COUNT(*) FROM calibration_mark_events "
                       "WHERE band_high IS NULL AND band_low IS NULL").fetchone()[0] == 4
    # The widened vocabulary now reaches the LIVE table...
    con.execute(_INSERT_EVENT, (1, "sos", "2026-03-02", "2026-03-13"))
    # ...and so does the mini-consolidation's band requirement, which is the
    # whole reason this is a rebuild and not an ALTER.
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(_INSERT_EVENT, (1, "mini_consolidation", "2026-04-01", "2026-04-10"))
    con.close()
    # The pre-change file is kept — the real net under a structural change.
    assert (tmp_path / "live.db.precalibevents.bak").exists()


def test_event_vocabulary_rebuild_is_idempotent(tmp_path):
    db = _live_shaped_db(tmp_path, "twice.db")
    engine = _engine_for(db)
    try:
        assert startup.migrate_calibration_event_types(engine) is True
        # Second boot: the live vocabulary already matches the model.
        assert startup.migrate_calibration_event_types(engine) is False
    finally:
        engine.dispose()


def test_event_vocabulary_rebuild_skips_a_fresh_database(tmp_path):
    """create_all already built the current shape — no rebuild, no backup."""
    db = tmp_path / "fresh.db"
    engine = _engine_for(db)
    try:
        models.Base.metadata.create_all(bind=engine)
        assert startup.migrate_calibration_event_types(engine) is False
    finally:
        engine.dispose()
    assert not (tmp_path / "fresh.db.precalibevents.bak").exists()


def test_the_rebuild_is_wired_into_boot():
    """A migration nobody calls is inert — the calibration tables are NOT in
    _MIGRATED_ARCHIVE_MODELS, so nothing else would ever carry this."""
    import inspect as _inspect

    source = _inspect.getsource(startup.initialize_database)
    assert "migrate_calibration_event_types(engine)" in source
