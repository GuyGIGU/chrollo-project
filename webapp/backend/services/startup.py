"""Startup database setup and idempotent migrations (mostly additive ALTERs, plus
the occasional one-off retired-column DROP)."""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text

import archive_models
import models
from database import engine

_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS scan_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at VARCHAR NOT NULL,
        finished_at VARCHAR,
        status VARCHAR NOT NULL,
        n_setups INTEGER,
        error TEXT,
        trigger VARCHAR NOT NULL,
        kind VARCHAR DEFAULT 'scan'
    )
    """,
    "ALTER TABLE scan_runs ADD COLUMN kind VARCHAR DEFAULT 'scan'",
    "ALTER TABLE trade_logs ADD COLUMN actions_json TEXT",
    "ALTER TABLE trade_logs ADD COLUMN source VARCHAR DEFAULT 'manual'",
    "ALTER TABLE trade_logs ADD COLUMN ibkr_account VARCHAR",
    "ALTER TABLE trade_logs ADD COLUMN perm_id VARCHAR",
    "ALTER TABLE trade_logs ADD COLUMN planned_stop FLOAT",
    "ALTER TABLE trade_logs ADD COLUMN conviction INTEGER",
    "ALTER TABLE trade_logs ADD COLUMN exit_reason TEXT",
    "ALTER TABLE setup_archive ADD COLUMN r_anchor INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN s_anchor INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN score_uptrend_bonus FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN score_rs_bonus FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN mfe_20d_date VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN mae_20d_date VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN r_multiple_20d FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN r_multiple_60d FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN trigger_volume_ratio FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN days_to_trigger INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN days_to_2_5r INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN days_to_15pct INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN days_to_stop INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN barrier_label VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN win_barrier VARCHAR",
    # Elapsed-window outcome (window-agnostic edge metric) — recomputed each run.
    "ALTER TABLE setup_archive ADD COLUMN mfe_to_date FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN mae_to_date FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN ret_to_date FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bars_to_date INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN abnormal_ret_to_date FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN rs_vs_sector_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN dist_52w_high_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN excess_return_6m FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN breadth_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN r_touch_vol_z FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN s_touch_vol_z FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN lps_descent_frac FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN lps_zone_type VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN score_high_proximity FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN score_breadth_bonus FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN contraction_count INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN contraction_quality FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN final_contraction_depth FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN contraction_vol_trend FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN score_contraction FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN base_median_spread_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN base_p80_spread_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN base_median_spread_pct_box FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN base_tight_bar_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN support_slope_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN ascending_support_quality FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN score_ascending_support FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_r_touches INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN eq_s_touches INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN eq_r_touch_thirds INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN eq_s_touch_thirds INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN eq_lower_dwell FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_mid_dwell FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_upper_dwell FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_coverage FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_respect_frac FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_engagement_respect_frac FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_max_excursion_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_close_lower_dwell FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_close_mid_dwell FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN eq_close_upper_dwell FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN trav_n_full_traversals INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN trav_n_swings INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN trav_top_dead_space FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN trav_bottom_dead_space FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN trav_rail_reaches_high INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN trav_rail_reaches_low INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN trav_max_swing_frac FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN trav_last_support_frac FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN trav_coil_floor_pos FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN score_traversal_quality FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN adr_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN score_adr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN phase_d_inner INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN lps_in_inner INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bars_since_bc INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN descent_length INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN inner_source VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN inner_search_start_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN inner_climax_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN inner_reaction_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN inner_reaction_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN inner_reaction_bars INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_b_cog_end FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_b_cog_crossings INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_b_cog_rng FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_b_cog_corr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN scope_phase_a_date TEXT",
    "ALTER TABLE setup_archive ADD COLUMN scope_phase_b_date TEXT",
    "ALTER TABLE setup_archive ADD COLUMN scope_phase_d_date TEXT",
    "ALTER TABLE setup_archive ADD COLUMN scope_phase_c_date TEXT",
    "ALTER TABLE setup_archive ADD COLUMN scope_has_mini INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN scope_confidence FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_a_bars INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_a_range_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_a_volume_ratio FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_b_bars INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_b_range_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_b_volume_ratio FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_present INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_type TEXT",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_event_date TEXT",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_event_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_undercut_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_recovery_bars INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_recovery_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_time_loc FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_c_spring_vol_z FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_bars INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_start_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_range_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_volume_ratio FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_boundary_source TEXT",
    "ALTER TABLE setup_archive ADD COLUMN bin_lps_bars INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN lps_position_in_box FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_vs_b_range_ratio FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_vs_b_volume_ratio FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN lps_stretch_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN lps_stretch_box FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN lps_swing_type TEXT",
    "ALTER TABLE setup_archive ADD COLUMN lps_anchor_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN lps_anchor_date TEXT",
    "ALTER TABLE setup_archive ADD COLUMN lps_low_bar INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN lps_low_date TEXT",
    "ALTER TABLE setup_archive ADD COLUMN lps_swing_depth_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN lps_swing_depth_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN lps_swing_depth_box FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN last_supper_pullback_from_extension_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN last_supper_source_box_age INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN last_supper_reclaim_quality FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN last_supper_pivot_stretch_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN last_supper_pivot_stretch_box FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN last_supper_pullback_from_pivot_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN last_supper_pivot_bars_back INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN regime_state VARCHAR",
    "ALTER TABLE setup_archive ADD COLUMN regime_breadth_50_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN regime_breadth_200_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN regime_distribution_days INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN regime_spy_above_50 INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN regime_spy_above_200 INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN regime_spy_50d_slope_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN regime_qqq_above_50 INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN regime_qqq_above_200 INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN regime_qqq_50d_slope_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_support_slope_atr FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_higher_low_frac FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_ascending_support_quality FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN bin_d_vs_b_support_quality_delta FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN phase_d_evidence_json TEXT",
    "ALTER TABLE setup_archive ADD COLUMN stage2_ma_stack_pass INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN stage2_ma200_slope_1m_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN stage2_52w_low_pct FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN stage2_trend_pass_count INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN stage2_trend_pass INTEGER",
    # HTF (higher-timeframe) context — same Trend+Box engine on weekly/monthly bars
    "ALTER TABLE setup_archive ADD COLUMN htf_w_stage2 INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_trend_state TEXT",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_in_consol INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_phase TEXT",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_box_r FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_box_s FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_box_width FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_reaccum INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN htf_w_daily_nested INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_stage2 INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_trend_state TEXT",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_in_consol INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_phase TEXT",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_box_r FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_box_s FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_box_width FLOAT",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_reaccum INTEGER",
    "ALTER TABLE setup_archive ADD COLUMN htf_m_daily_nested INTEGER",
    # Retired sub-score — the rail-blind oscillation term, replaced by
    # score_traversal_quality. Drop the column so the live schema matches the
    # model; its pre-retirement values measured a flawed (rail-blind) quantity
    # and are preserved in the dated DB backup. Idempotent: a re-run on a DB that
    # never had the column raises "no such column", which the runner treats as
    # already-applied.
    "ALTER TABLE setup_archive DROP COLUMN score_oscillation",
    # Calibration marks: rail anchors + first-marked rail (2026-07-11) — the
    # swing bar each rail was placed on carries the operator's root-swing
    # intent; nullable, so pre-anchor marks stay valid.
    "ALTER TABLE calibration_marks ADD COLUMN r_anchor_date VARCHAR",
    "ALTER TABLE calibration_marks ADD COLUMN s_anchor_date VARCHAR",
    "ALTER TABLE calibration_marks ADD COLUMN first_rail VARCHAR",
    # Calibration marks: the Trigger (2026-07-21) — the operator's buy, a forward-
    # of-as-of point (the LPS-high breakout). Nullable, NO default: a null trigger
    # is the real "no buy marked yet" state. Its cross-column + requires-LPS rules
    # live in marks_validity (SQLite can't retrofit CHECKs onto the live corpus DB).
    "ALTER TABLE calibration_marks ADD COLUMN trigger_date VARCHAR",
    "ALTER TABLE calibration_marks ADD COLUMN trigger_price FLOAT",
]

_log = logging.getLogger("chrollo.migrate")


def initialize_database() -> None:
    models.Base.metadata.create_all(bind=engine)
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    _apply_migrations()
    # Non-additive one-off (widen the identity key); must run BEFORE the ADD-only
    # auto-migrator so the latter sees universe_type already present and skips it.
    migrate_universe_type(engine)
    _apply_model_add_columns(engine)
    # Clear any scan_runs row orphaned in 'running' by a prior hard kill, so
    # latest_run() reflects reality and the live-price fallback gate unsticks.
    _reconcile_orphaned_runs(engine)


def _apply_migrations() -> None:
    with engine.connect() as conn:
        for statement in _MIGRATIONS:
            try:
                conn.execute(text(statement))
                conn.commit()
                _log.info("applied: %s", statement)
            except Exception as exc:
                message = str(exc).lower()
                # Idempotency: a re-run of an ADD hits "duplicate column"/"already
                # exists"; a re-run of a DROP hits "no such column". All mean the
                # migration's end state already holds — skip quietly.
                if ("duplicate column" in message or "already exists" in message
                        or "no such column" in message):
                    continue
                _log.warning("migration skipped (%s): %s", exc.__class__.__name__, statement)


def _reconcile_orphaned_runs(bind) -> None:
    """Mark any scan_runs row left status='running' as failed on boot.

    start_run() inserts status='running' and finish_run() only runs if the process
    survives; a hard kill (SIGKILL / OOM / power loss / container stop) between them
    orphans the row forever. Nothing else ever rewrites it, so latest_run() would
    keep returning 'running' — mislabeling a crash and, worse, pinning
    _scan_is_running() True, which silently suppresses the live-price fallback until
    a new run completes. Reconciling at boot is safe: the scheduler has not started
    and no scan/maturation is in flight yet, so every 'running' row here is genuinely
    orphaned. Idempotent and best-effort — a missing table or transient error must
    never block backend boot.
    """
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with bind.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE scan_runs SET status = 'failed', "
                    "finished_at = COALESCE(finished_at, :now), "
                    "error = COALESCE(error, 'process died before completion "
                    "(reconciled at boot)') "
                    "WHERE status = 'running'"
                ),
                {"now": now_iso},
            )
            n = result.rowcount
        if n:
            _log.warning("reconciled %d orphaned 'running' scan_runs row(s) at boot", n)
    except Exception as exc:  # pragma: no cover - defensive; boot must not fail
        _log.warning("orphaned scan_runs reconcile skipped (%s)", exc.__class__.__name__)


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


# Every archive model the ADD-only auto-migrator covers. A NEW archive table
# registers HERE at birth (near-miss lane Task 9 generalization) — otherwise
# its first model-only column silently never reaches the live DB.
_MIGRATED_ARCHIVE_MODELS = (
    ("setup_archive", lambda: archive_models.SetupArchive),
    ("near_miss_archive", lambda: archive_models.NearMissArchive),
)


def model_add_column_migrations(bind) -> list[str]:
    """ADD-only migrations to bring every registered archive table up to its
    model's columns (``_MIGRATED_ARCHIVE_MODELS`` — generalized from the
    setup_archive-only pass, near-miss lane Task 9).

    Diffs each model's ``__table__.columns`` against the live table (via
    ``PRAGMA table_info``, exposed through SQLAlchemy's inspector) and returns one
    ``ALTER TABLE ... ADD COLUMN`` per column a model declares but the DB lacks.
    The model is the single source of truth: a new column flows into the DB on
    the next boot with no hand-written migration.

    ADD-only by design — Brandur/SQLite: there is no safe in-place DROP/ALTER, so
    a removed-from-model column is left in place (its retirement is an explicit
    one-off DROP in _MIGRATIONS, never inferred here). Returns [] when the DB is
    already at the models (idempotent, no spurious ALTERs); a table that does
    not exist yet is skipped (create_all handles a fresh DB). The auto-increment
    ``id`` PK is never ADDed.
    """
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    statements: list[str] = []
    for table_name, model_fn in _MIGRATED_ARCHIVE_MODELS:
        if table_name not in tables:
            continue
        existing = {col["name"] for col in inspector.get_columns(table_name)}
        for column in model_fn().__table__.columns:
            if column.primary_key or column.name in existing:
                continue
            statements.append(
                f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column.type}"
            )
    return statements


def _apply_model_add_columns(bind) -> None:
    """Execute the model-derived ADD COLUMN migrations (see above). Idempotent and
    safe on every boot: an empty diff is a no-op."""
    statements = model_add_column_migrations(bind)
    if not statements:
        return
    with bind.connect() as conn:
        for statement in statements:
            try:
                conn.execute(text(statement))
                conn.commit()
                _log.info("applied (model-derived): %s", statement)
            except Exception as exc:
                message = str(exc).lower()
                if "duplicate column" in message or "already exists" in message:
                    continue
                _log.warning("model migration skipped (%s): %s",
                             exc.__class__.__name__, statement)
