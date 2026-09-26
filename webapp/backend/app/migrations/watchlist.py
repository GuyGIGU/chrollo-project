"""Upgrade watchlist identity into a dated review ledger."""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text
import archive_models
import models

_log = logging.getLogger("chrollo.migrate")

def migrate_watchlist_ledger(bind) -> bool:
    """One-off: rebuild ``watchlist`` from ticker-PK rows to the dated event ledger.

    The old grain (ticker PRIMARY KEY, created_at) cannot express history, so
    this rebuilds the table under the ``migrate_universe_type`` precedent: WAL
    checkpoint + file backup -> rename old -> create new from the model (with
    every constraint: UNIQUE(ticker, save_date), the partial one-active-per-
    ticker unique, the full-pin and snapshot CHECKs — the rebuild is the only
    path that gets the LIVE DB these assertions, SQLite cannot retrofit them)
    -> copy each legacy row as an ACTIVE watch (save_date from created_at's
    date part, migration day when NULL; origin 'legacy'; pins/snapshot NULL —
    never fabricate what the operator saw) -> row-count check -> drop old.
    One transaction; any failure rolls back to the original table.

    Idempotent: a no-op on a fresh DB (create_all built the ledger shape) and
    on a re-run — detection keys on the surrogate ``id`` column only the new
    grain has. Returns True if it rebuilt, False if already migrated.
    """
    import shutil
    import sqlite3
    from datetime import datetime, timezone

    from sqlalchemy.dialects import sqlite as sqlite_dialect
    from sqlalchemy.schema import CreateIndex, CreateTable

    inspector = inspect(bind)
    if "watchlist" not in inspector.get_table_names():
        return False  # fresh DB — create_all already built the ledger schema
    old_cols = {col["name"] for col in inspector.get_columns("watchlist")}
    if "id" in old_cols:
        return False  # already the event-ledger grain

    dialect = sqlite_dialect.dialect()
    table = models.Watchlist.__table__
    create_table_sql = str(CreateTable(table).compile(dialect=dialect))
    create_index_sqls = [
        str(CreateIndex(ix).compile(dialect=dialect)) for ix in table.indexes
    ]

    db_path = bind.url.database
    # Fold WAL into the main file, then back it up before any structural change.
    with bind.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    backup = db_path + ".prewatchlistledger.bak"
    shutil.copy2(db_path, backup)
    _log.info("watchlist ledger migration: backed up %s -> %s", db_path, backup)

    now = datetime.now(timezone.utc)
    migration_day = now.date().isoformat()
    # Match the DATETIME storage format SQLAlchemy writes (naive UTC text).
    migration_ts = now.strftime("%Y-%m-%d %H:%M:%S.%f")

    raw = sqlite3.connect(db_path, timeout=30)
    raw.isolation_level = None  # manage the transaction ourselves -> transactional DDL
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("BEGIN")
        pre = raw.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        raw.execute("ALTER TABLE watchlist RENAME TO watchlist_old")
        # SQLite keeps an index's NAME when its table is renamed, so the old
        # ix_watchlist_ticker would collide with the new table's. Drop named
        # indexes first; the PK autoindex has NULL sql and drops with the table.
        stale_indexes = [
            row[0] for row in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='watchlist_old' AND sql IS NOT NULL"
            ).fetchall()
        ]
        for name in stale_indexes:
            raw.execute(f'DROP INDEX "{name}"')
        raw.execute(create_table_sql)
        for ix_sql in create_index_sqls:
            raw.execute(ix_sql)
        raw.execute(
            "INSERT INTO watchlist (ticker, save_date, saved_at, unstarred_at, "
            "origin, pin_scan_date, pin_universe_type, pin_setup_type, "
            "pin_engine_config_version, snapshot_json) "
            "SELECT ticker, COALESCE(date(created_at), :day), "
            "COALESCE(created_at, :ts), NULL, 'legacy', "
            "NULL, NULL, NULL, NULL, NULL FROM watchlist_old",
            {"day": migration_day, "ts": migration_ts},
        )
        post = raw.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        if pre != post:
            raise RuntimeError(f"row-count drift during rebuild: {pre} -> {post}")
        raw.execute("DROP TABLE watchlist_old")
        raw.execute("COMMIT")
        _log.info(
            "watchlist ledger migration: rebuilt watchlist (%d rows -> dated event "
            "ledger, legacy rows active); backup at %s", post, backup)
        return True
    except Exception:
        # Log FIRST: on SQLITE_FULL/IOERR sqlite already auto-rolled-back and
        # the explicit ROLLBACK below raises 'no transaction is active', which
        # would otherwise eat the only line naming the backup file.
        _log.exception(
            "watchlist ledger migration failed; rolling back. Restore from %s if needed.",
            backup)
        import contextlib
        with contextlib.suppress(sqlite3.OperationalError):
            raw.execute("ROLLBACK")
        raise
    finally:
        raw.execute("PRAGMA foreign_keys=ON")
        raw.close()


