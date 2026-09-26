"""Archive identity rebuilds with transactional backup and copy."""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text
import archive_models
import models

_log = logging.getLogger("chrollo.migrate")

def _has_universe_identity(bind) -> bool:
    """True iff setup_archive carries the widened (ticker, scan_date, universe_type)
    UNIQUE identity — not merely a universe_type column added out-of-band (the scan
    writer / forward-returns ADD-COLUMN passes can materialize the column without
    the constraint). Read via PRAGMA for reliable SQLite unique-index reflection."""
    target = {"ticker", "scan_date", "universe_type"}
    with bind.connect() as conn:
        for row in conn.exec_driver_sql("PRAGMA index_list('setup_archive')").fetchall():
            name, unique = row[1], row[2]
            if not unique:
                continue
            cols = {r[2] for r in conn.exec_driver_sql(f"PRAGMA index_info('{name}')").fetchall()}
            if cols == target:
                return True
    return False


def migrate_universe_type(bind) -> bool:
    """One-off: widen the setup_archive identity to (ticker, scan_date, universe_type).

    SQLite cannot ALTER a UNIQUE constraint in place, so this rebuilds the table:
    rename old -> create new from the model (3-col UNIQUE + CHECK + index) ->
    INSERT…SELECT copying every shared column and backfilling universe_type to
    'us_equities' -> drop old. The whole rebuild runs in ONE transaction
    (isolation_level=None + explicit BEGIN gives transactional DDL, so any failure
    rolls back to the original table), and a checkpoint+file backup is taken first.
    A post-rebuild row-count check rolls back on any drift.

    Idempotent: a no-op once the full identity is in place (the universe_type
    column AND the 3-col UNIQUE) — so a fresh DB (create_all built it) and a re-run
    are both skipped, but a column added out-of-band WITHOUT the constraint still
    triggers the rebuild. Returns True if it rebuilt, False if already migrated.
    """
    import shutil
    import sqlite3

    from sqlalchemy.dialects import sqlite as sqlite_dialect
    from sqlalchemy.schema import CreateIndex, CreateTable

    inspector = inspect(bind)
    if "setup_archive" not in inspector.get_table_names():
        return False  # fresh DB — create_all already built the new schema
    old_cols = [col["name"] for col in inspector.get_columns("setup_archive")]
    if "universe_type" in old_cols and _has_universe_identity(bind):
        return False  # fully migrated: the column AND the 3-col unique are present

    db_path = bind.url.database
    model_cols = {c.name for c in archive_models.SetupArchive.__table__.columns}
    # Always exclude universe_type from the copied set — it is supplied by the
    # backfill below. This keeps the rebuild correct even when universe_type was
    # already added out-of-band (as a plain nullable column) but the widened
    # constraint is still missing.
    has_ut_col = "universe_type" in old_cols
    copy_cols = [c for c in old_cols if c in model_cols and c != "universe_type"]
    col_sql = ", ".join(copy_cols)
    # Literal for a clean add; COALESCE preserves any out-of-band values (a plain
    # ADD COLUMN with no default leaves NULLs) while still backfilling the rest.
    # Local import keeps the equities-scope literal sourced from the one constant
    # (conventions.md EC-1) without a module-level universe import at backend boot.
    from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
    ut_select = (f"COALESCE(universe_type, '{DEFAULT_UNIVERSE_TYPE}')"
                 if has_ut_col else f"'{DEFAULT_UNIVERSE_TYPE}'")
    dialect = sqlite_dialect.dialect()
    create_table_sql = str(CreateTable(archive_models.SetupArchive.__table__).compile(dialect=dialect))
    create_index_sqls = [
        str(CreateIndex(ix).compile(dialect=dialect))
        for ix in archive_models.SetupArchive.__table__.indexes
    ]

    # Fold WAL into the main file, then back it up before any structural change.
    with bind.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    backup = db_path + ".premigration.bak"
    shutil.copy2(db_path, backup)
    _log.info("universe_type migration: backed up %s -> %s", db_path, backup)

    raw = sqlite3.connect(db_path, timeout=30)
    raw.isolation_level = None  # manage the transaction ourselves -> transactional DDL
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("BEGIN")
        pre = raw.execute("SELECT COUNT(*) FROM setup_archive").fetchone()[0]
        raw.execute("ALTER TABLE setup_archive RENAME TO setup_archive_old")
        # SQLite keeps an index's NAME when its table is renamed, so the old
        # table's explicit ix_* indexes would collide with the new table's. Drop
        # them first (they're not needed for the INSERT…SELECT scan). Autoindexes
        # for the UNIQUE constraint have NULL sql and are dropped with the table.
        stale_indexes = [
            row[0] for row in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='setup_archive_old' AND sql IS NOT NULL"
            ).fetchall()
        ]
        for name in stale_indexes:
            raw.execute(f'DROP INDEX "{name}"')
        raw.execute(create_table_sql)
        for ix_sql in create_index_sqls:
            raw.execute(ix_sql)
        raw.execute(
            f"INSERT INTO setup_archive ({col_sql}, universe_type) "
            f"SELECT {col_sql}, {ut_select} FROM setup_archive_old"
        )
        post = raw.execute("SELECT COUNT(*) FROM setup_archive").fetchone()[0]
        if pre != post:
            raise RuntimeError(f"row-count drift during rebuild: {pre} -> {post}")
        raw.execute("DROP TABLE setup_archive_old")
        raw.execute("COMMIT")
        _log.info("universe_type migration: rebuilt setup_archive (%d rows, +universe_type, "
                  "3-col unique key); backup at %s", post, backup)
        return True
    except Exception:
        raw.execute("ROLLBACK")
        _log.exception("universe_type migration failed; rolled back. Restore from %s if needed.", backup)
        raise
    finally:
        raw.execute("PRAGMA foreign_keys=ON")
        raw.close()


_NEAR_MISS_IDENTITY = ("ticker", "universe_type", "r_anchor_date", "s_anchor_date")


def _has_near_miss_framing_identity(bind) -> bool:
    """True iff ``near_miss_archive`` carries the DATE-anchored framing identity
    (ticker, universe_type, r_anchor_date, s_anchor_date) as its UNIQUE key —
    i.e. the rail PRICES have been taken out of it. Read via PRAGMA, the reliable
    SQLite unique-index reflection."""
    target = set(_NEAR_MISS_IDENTITY)
    with bind.connect() as conn:
        for row in conn.exec_driver_sql(
                "PRAGMA index_list('near_miss_archive')").fetchall():
            name, unique = row[1], row[2]
            if not unique:
                continue
            cols = {r[2] for r in conn.exec_driver_sql(
                f"PRAGMA index_info('{name}')").fetchall()}
            if cols == target:
                return True
    return False


def migrate_near_miss_framing_identity(bind) -> bool:
    """One-off: take the rail PRICES out of the near-miss episode identity.

    ``uq_near_miss_framing_identity`` was (ticker, universe_type, r_level,
    s_level, r_anchor_date, s_anchor_date) with both rails FLOAT. A price is the
    wrong type for an identity twice over: it carried 4dp off a float32 panel, so
    APH held one framing as two rows (s_level 77.68 vs 77.6801); and it is not
    invariant under a corporate action, so APH's 2-for-1 split re-minted every one
    of its framings as a NEW episode with ``first_seen`` and the forward clock
    reset. Measured on the live archive 2026-09-07: 4 duplicate groups, all APH,
    every one an exact 2x rail pair — 5 spurious rows in 1,483, and zero
    legitimately distinct framings sharing a pair of anchor dates. The anchor
    dates name the zigzag pivot bars the rails are read from
    (``box_primitives._oriented_pairs`` yields the rail and its anchor as one
    pair), so they name the same box on either side of a split.

    SQLite cannot ALTER a UNIQUE constraint in place, so this rebuilds the table
    under the ``migrate_universe_type`` recipe: WAL checkpoint + file backup ->
    rename old -> create new from the model -> INSERT…SELECT -> row-count
    assertion -> drop old, all in ONE transaction so any failure rolls back to
    the original table.

    The copy DEDUPES to the new identity, keeping the EARLIEST ``first_seen`` row
    of each group whole — that row is the first-refusal record the schema
    documents, and its rails / ``would_be_trigger`` / ``scan_close`` are mutually
    consistent on one price scale. Only the three recurrence counters are folded
    across the group: ``last_seen`` = max, ``nights_seen`` = sum (the duplicates
    counted disjoint nights of the same framing), ``fired_any_night`` = max.
    Ties on ``first_seen`` break on the lowest id, so the result is deterministic.

    Idempotent: a no-op on a fresh DB (create_all built the new key) and on every
    later boot. Fails CLOSED — an unexpected row count, or any error at all,
    rolls the whole rebuild back and re-raises with the backup named, and it
    refuses outright rather than rebuild a table missing a NOT NULL model column
    it could not fill (a missing NULLABLE one is copied as NULL, which is what
    the model permits).
    Returns True if it rebuilt, False if already migrated.
    """
    import shutil
    import sqlite3

    from sqlalchemy.dialects import sqlite as sqlite_dialect
    from sqlalchemy.schema import CreateIndex, CreateTable

    inspector = inspect(bind)
    if "near_miss_archive" not in inspector.get_table_names():
        return False  # the lane has never written here — nothing to rebuild
    if _has_near_miss_framing_identity(bind):
        return False  # already on the date-anchored identity

    table = archive_models.NearMissArchive.__table__
    model_cols = {c.name for c in table.columns}
    old_cols = [col["name"] for col in inspector.get_columns("near_miss_archive")]
    # Fail closed on a column the rebuild could not fill — but only on those.
    # A missing NULLABLE column is simply absent from copy_cols, so the INSERT
    # omits it and it lands NULL, which is what the model already permits; every
    # column the SELECT names by hand (the identity legs, first_seen/id for the
    # tie-break, the three folded counters) is NOT NULL, so this covers them.
    # Refusing on ANY gap instead would brick boot on the first future release
    # that adds a plain nullable outcome column against a DB restored from an
    # older backup — and reordering behind _apply_model_add_columns is no fix,
    # since that pass adds a column WITHOUT its NOT NULL or its DEFAULT, so a
    # NOT NULL column it "closed" would arrive full of NULLs and fail inside the
    # rebuild instead (council review 2026-09-07, fix review F4).
    unfillable = sorted(c.name for c in table.columns
                        if c.name not in old_cols and not c.nullable)
    if unfillable:
        raise RuntimeError(
            f"near_miss_archive is missing model column(s) {unfillable} that "
            "the rebuild cannot fill; refusing to rebuild the framing identity "
            "on an out-of-date table")
    folded = {"last_seen", "nights_seen", "fired_any_night"}
    copy_cols = [c for c in old_cols if c in model_cols and c not in folded]
    col_sql = ", ".join(f'"{c}"' for c in copy_cols)
    o_col_sql = ", ".join(f'o."{c}"' for c in copy_cols)
    key_sql = ", ".join(f'"{c}"' for c in _NEAR_MISS_IDENTITY)
    key_join = " AND ".join(f'g."{c}" = o."{c}"' for c in _NEAR_MISS_IDENTITY)
    key_self = " AND ".join(f'x."{c}" = o."{c}"' for c in _NEAR_MISS_IDENTITY)

    dialect = sqlite_dialect.dialect()
    create_table_sql = str(CreateTable(table).compile(dialect=dialect))
    create_index_sqls = [
        str(CreateIndex(ix).compile(dialect=dialect)) for ix in table.indexes
    ]

    db_path = bind.url.database
    # Fold WAL into the main file, then back it up before any structural change.
    with bind.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    backup = db_path + ".prenearmissidentity.bak"
    shutil.copy2(db_path, backup)
    _log.info("near-miss identity migration: backed up %s -> %s", db_path, backup)

    raw = sqlite3.connect(db_path, timeout=30)
    raw.isolation_level = None  # manage the transaction ourselves -> transactional DDL
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("BEGIN")
        pre = raw.execute("SELECT COUNT(*) FROM near_miss_archive").fetchone()[0]
        expected = raw.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM near_miss_archive "
            f"GROUP BY {key_sql})").fetchone()[0]
        raw.execute("ALTER TABLE near_miss_archive RENAME TO near_miss_archive_old")
        # SQLite keeps an index's NAME when its table is renamed, so the old
        # table's explicit ix_* indexes would collide with the new table's.
        stale_indexes = [
            row[0] for row in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='near_miss_archive_old' AND sql IS NOT NULL"
            ).fetchall()
        ]
        for name in stale_indexes:
            raw.execute(f'DROP INDEX "{name}"')
        raw.execute(create_table_sql)
        for ix_sql in create_index_sqls:
            raw.execute(ix_sql)
        raw.execute(
            f'INSERT INTO near_miss_archive ({col_sql}, "last_seen", '
            f'"nights_seen", "fired_any_night") '
            f'SELECT {o_col_sql}, g.folded_last_seen, g.folded_nights, '
            f'g.folded_fired_any '
            f'FROM near_miss_archive_old o '
            f'JOIN (SELECT {key_sql}, MIN(first_seen) AS anchor_first, '
            f'             MAX(last_seen) AS folded_last_seen, '
            f'             SUM(nights_seen) AS folded_nights, '
            f'             MAX(fired_any_night) AS folded_fired_any '
            f'      FROM near_miss_archive_old GROUP BY {key_sql}) g '
            f'  ON {key_join} '
            f'WHERE o.id = (SELECT MIN(x.id) FROM near_miss_archive_old x '
            f'              WHERE {key_self} AND x.first_seen = g.anchor_first)'
        )
        post = raw.execute("SELECT COUNT(*) FROM near_miss_archive").fetchone()[0]
        if post != expected:
            raise RuntimeError(
                f"dedupe drift during rebuild: {pre} rows -> {post}, "
                f"expected {expected} distinct framings")
        raw.execute("DROP TABLE near_miss_archive_old")
        raw.execute("COMMIT")
        _log.info("near-miss identity migration: rebuilt near_miss_archive "
                  "(%d rows -> %d episodes, %d duplicate framing(s) folded; the "
                  "rail prices are no longer identity); backup at %s",
                  pre, post, pre - post, backup)
        return True
    except Exception:
        # Log FIRST: on SQLITE_FULL/IOERR sqlite already auto-rolled-back and the
        # explicit ROLLBACK raises 'no transaction is active', which would eat the
        # only line naming the backup file.
        _log.exception("near-miss identity migration failed; rolling back. "
                       "Restore from %s if needed.", backup)
        import contextlib
        with contextlib.suppress(sqlite3.OperationalError):
            raw.execute("ROLLBACK")
        raise
    finally:
        raw.execute("PRAGMA foreign_keys=ON")
        raw.close()


