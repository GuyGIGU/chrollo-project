"""Keep the persisted calibration-event vocabulary current."""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text
import archive_models
import models

_log = logging.getLogger("chrollo.migrate")

def _live_event_type_vocabulary(bind) -> set | None:
    """The event-type set the LIVE ``calibration_mark_events`` CHECK enforces —
    read out of the stored DDL, because that is the only place it exists once the
    table has been created. None when the table or the CHECK is absent."""
    import re

    with bind.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='calibration_mark_events'"
        ).fetchone()
    if not row or not row[0]:
        return None
    match = re.search(r"event_type\s+IN\s*\(([^)]*)\)", row[0], re.IGNORECASE)
    if match is None:
        return set()  # table exists with NO type CHECK — a rebuild installs one
    return set(re.findall(r"'([^']*)'", match.group(1)))


def migrate_calibration_event_types(bind) -> bool:
    """One-off-shaped, but SELF-RENEWING: rebuild ``calibration_mark_events``
    whenever its live shape has fallen behind the model — a widened
    ``event_type`` vocabulary or a column the model declares and the table lacks.

    SQLite cannot ALTER a CHECK, and the calibration tables are deliberately NOT
    in ``_MIGRATED_ARCHIVE_MODELS``, so neither existing migrator can carry this.
    Follows the ``migrate_watchlist_ledger`` recipe exactly (checkpoint + file
    backup -> transactional rename/create/copy/drop, rollback naming the backup).

    Detection compares the LIVE DDL's vocabulary against the model's, so a future
    event type is migrated by adding it to ``marks_validity.EVENT_TYPES`` and the
    model CHECK — no new migration code. Idempotent: a no-op on a fresh DB
    (``create_all`` built the current shape) and on every later boot. Returns True
    if it rebuilt, False if already current.
    """
    import re
    import shutil
    import sqlite3

    from sqlalchemy.dialects import sqlite as sqlite_dialect
    from sqlalchemy.schema import CreateIndex, CreateTable

    inspector = inspect(bind)
    if "calibration_mark_events" not in inspector.get_table_names():
        return False  # fresh DB — create_all already built the current schema

    table = models.CalibrationMarkEvent.__table__
    model_types = {
        value
        for constraint in table.constraints
        if getattr(constraint, "name", None) == "ck_calibration_event_type"
        for value in re.findall(r"'([^']*)'", str(constraint.sqltext))
    }
    live_types = _live_event_type_vocabulary(bind)
    live_cols = {col["name"] for col in inspector.get_columns("calibration_mark_events")}
    model_cols = {c.name for c in table.columns}
    if live_types == model_types and model_cols <= live_cols:
        return False  # vocabulary and columns already current

    dialect = sqlite_dialect.dialect()
    create_table_sql = str(CreateTable(table).compile(dialect=dialect))
    create_index_sqls = [
        str(CreateIndex(ix).compile(dialect=dialect)) for ix in table.indexes
    ]
    # Copy every column the live table and the model share — derived, never
    # hardcoded, so no operator value can be silently dropped by an omission.
    copy_cols = [col["name"] for col in inspector.get_columns("calibration_mark_events")
                 if col["name"] in model_cols]
    col_sql = ", ".join(f'"{c}"' for c in copy_cols)

    db_path = bind.url.database
    # Fold WAL into the main file, then back it up before any structural change.
    with bind.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    backup = db_path + ".precalibevents.bak"
    shutil.copy2(db_path, backup)
    _log.info("calibration event-type migration: backed up %s -> %s", db_path, backup)

    raw = sqlite3.connect(db_path, timeout=30)
    raw.isolation_level = None  # manage the transaction ourselves -> transactional DDL
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("BEGIN")
        pre = raw.execute("SELECT COUNT(*) FROM calibration_mark_events").fetchone()[0]
        # Per-type census as well as the row count: a row count alone cannot see a
        # dropped COLUMN's values, and event_type is the column that carries the
        # meaning of every one of these rows.
        pre_types = dict(raw.execute(
            "SELECT event_type, COUNT(*) FROM calibration_mark_events "
            "GROUP BY event_type").fetchall())
        raw.execute("ALTER TABLE calibration_mark_events RENAME TO calibration_mark_events_old")
        # A renamed table KEEPS its index names, which would collide with the new
        # table's; drop the named ones first (autoindexes drop with the table).
        stale_indexes = [
            row[0] for row in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='calibration_mark_events_old' AND sql IS NOT NULL"
            ).fetchall()
        ]
        for name in stale_indexes:
            raw.execute(f'DROP INDEX "{name}"')
        raw.execute(create_table_sql)
        for ix_sql in create_index_sqls:
            raw.execute(ix_sql)
        raw.execute(
            f"INSERT INTO calibration_mark_events ({col_sql}) "
            f"SELECT {col_sql} FROM calibration_mark_events_old"
        )
        post = raw.execute("SELECT COUNT(*) FROM calibration_mark_events").fetchone()[0]
        post_types = dict(raw.execute(
            "SELECT event_type, COUNT(*) FROM calibration_mark_events "
            "GROUP BY event_type").fetchall())
        if pre != post:
            raise RuntimeError(f"row-count drift during rebuild: {pre} -> {post}")
        if pre_types != post_types:
            raise RuntimeError(
                f"event-type census drift during rebuild: {pre_types} -> {post_types}")
        raw.execute("DROP TABLE calibration_mark_events_old")
        raw.execute("COMMIT")
        _log.info(
            "calibration event-type migration: rebuilt calibration_mark_events "
            "(%d rows, vocabulary %s); backup at %s",
            post, sorted(model_types), backup)
        return True
    except Exception:
        # Log FIRST: on SQLITE_FULL/IOERR sqlite already auto-rolled-back and the
        # explicit ROLLBACK raises 'no transaction is active', which would
        # otherwise eat the only line naming the backup file.
        _log.exception(
            "calibration event-type migration failed; rolling back. Restore from %s "
            "if needed.", backup)
        import contextlib
        with contextlib.suppress(sqlite3.OperationalError):
            raw.execute("ROLLBACK")
        raise
    finally:
        raw.execute("PRAGMA foreign_keys=ON")
        raw.close()


