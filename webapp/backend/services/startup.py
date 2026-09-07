"""Startup database setup and idempotent migrations (mostly additive ALTERs, plus
the occasional one-off retired-column DROP)."""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text

import archive_models
import models
from database import engine
from services.scan_diagnosis import (
    LEGACY_RECONCILE_PREFIX,
    PENDING_KIND,
    RECONCILE_MARKER,
)

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
        kind VARCHAR DEFAULT 'scan',
        failure_kind VARCHAR
    )
    """,
    "ALTER TABLE scan_runs ADD COLUMN kind VARCHAR DEFAULT 'scan'",
    # Why a run that was killed mid-flight died (services/scan_diagnosis.py owns
    # the closed set). Both forms are needed: the CREATE covers a fresh db, the
    # idempotent ALTER covers an existing one.
    "ALTER TABLE scan_runs ADD COLUMN failure_kind VARCHAR",
    # Rows reconciled before 2026-09-07 carry only the old generic message and no
    # kind. Tag them pending so the lazy resolver can still explain the recent
    # ones (the old ones age out to "not recorded"). Idempotent by construction.
    f"UPDATE scan_runs SET failure_kind = '{PENDING_KIND}' "
    "WHERE failure_kind IS NULL AND status = 'failed' "
    f"AND error LIKE '{LEGACY_RECONCILE_PREFIX}%'",
    "ALTER TABLE trade_logs ADD COLUMN actions_json TEXT",
    "ALTER TABLE trade_logs ADD COLUMN source VARCHAR DEFAULT 'manual'",
    "ALTER TABLE trade_logs ADD COLUMN ibkr_account VARCHAR",
    "ALTER TABLE trade_logs ADD COLUMN perm_id VARCHAR",
    "ALTER TABLE trade_logs ADD COLUMN planned_stop FLOAT",
    "ALTER TABLE trade_logs ADD COLUMN conviction INTEGER",
    "ALTER TABLE trade_logs ADD COLUMN exit_reason TEXT",
    # Folded in from the retired standalone migrate.py that sat in this backend
    # folder (deleted 2026-08-20, commit 680917c): models.py declares target_r,
    # so create_all covers a FRESH db but never an existing one. Idempotent here
    # like every other ADD ("duplicate column").
    "ALTER TABLE trade_logs ADD COLUMN target_r FLOAT DEFAULT 3.0",
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
    # Retired vocabulary — "puzzle quality" became "setup quality" (operator
    # ruling 2026-08-09). The four pre-rename columns were added 2026-08-08 and
    # never carried a value: no scan ran between the add and the rename, so the
    # retirement destroys nothing (verified 0 non-NULL across all 9,575 rows and
    # all three sources). Their replacements are the model-declared setup_*
    # columns the ADD-only pass below supplies — and it runs after this list, so
    # a pre-rename DB lands on the right schema in one boot. Recorded here rather
    # than only hand-run because a DB restored from a pre-rename backup (the kept
    # pre-journal-wipe file still carries them) would otherwise resurrect them
    # permanently — the ADD-only auto-migrator can never remove a column.
    # Idempotent: "no such column" on an already-clean DB reads as applied.
    "ALTER TABLE setup_archive DROP COLUMN puzzle_completeness",
    "ALTER TABLE setup_archive DROP COLUMN puzzle_chronology",
    "ALTER TABLE setup_archive DROP COLUMN puzzle_upthrust_terminal",
    "ALTER TABLE setup_archive DROP COLUMN score_puzzle_quality",
    # Retired near-miss counterfactual pair (council review 2026-08-22) —
    # declared, rendered, and unwritable: no writer ever existed, and the
    # lane's own model docstring conceded a refused framing has no election
    # context to score, so the pair was unfillable by design. Verified
    # 2026-08-23 via mode=ro: the live cohort table (1,123 rows) never even
    # materialized the columns, so the DROP destroys nothing and reads as
    # already-applied there. Recorded anyway (not just model removal) because
    # any DB where the model-diff migrators DID materialize the empty pair
    # would otherwise carry it forever — the ADD-only auto-migrator can never
    # remove a column.
    # Idempotent: "no such column" on an already-clean DB reads as applied.
    "ALTER TABLE near_miss_archive DROP COLUMN would_be_score",
    "ALTER TABLE near_miss_archive DROP COLUMN would_be_tier",
]

_log = logging.getLogger("chrollo.migrate")


def initialize_database() -> None:
    models.Base.metadata.create_all(bind=engine)
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    _apply_migrations()
    # Non-additive one-off (widen the identity key); must run BEFORE the ADD-only
    # auto-migrator so the latter sees universe_type already present and skips it.
    migrate_universe_type(engine)
    # Non-additive one-off: watchlist ticker-PK -> dated event ledger (rebuild).
    migrate_watchlist_ledger(engine)
    # Non-additive one-off: take the rail PRICES out of the near-miss episode
    # identity (rebuild + dedupe to the date-anchored framing key).
    migrate_near_miss_framing_identity(engine)
    # Non-additive, self-renewing: widen the drawn-event vocabulary / add its
    # columns (the calibration tables are not in _MIGRATED_ARCHIVE_MODELS, so the
    # ADD-only pass below can never reach them).
    migrate_calibration_event_types(engine)
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

    This RECORDS A FACT and claims no cause. The row is tagged with the pending
    failure kind; services/scan_diagnosis.resolve_pending works out WHY later,
    from the backend's lifespan startup, when the Windows Event Log service is
    actually up. Measured 2026-09-05: this reconcile can run seconds INTO a
    shutdown (NSSM restarts uvicorn as Windows stops the service), one second
    after the Event Log service has already stopped — so no evidence read and no
    boot-time comparison belongs on this path. ``finished_at`` is stamped as the
    moment the orphan was DETECTED, which is what makes the later diagnosis
    possible; it is not a completion time.
    """
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with bind.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE scan_runs SET status = 'failed', "
                    "finished_at = COALESCE(finished_at, :now), "
                    "error = COALESCE(error, :marker), "
                    "failure_kind = COALESCE(failure_kind, :pending) "
                    "WHERE status = 'running'"
                ),
                {"now": now_iso, "marker": RECONCILE_MARKER, "pending": PENDING_KIND},
            )
            n = result.rowcount
        if n:
            _log.warning(
                "reconciled %d orphaned 'running' scan_runs row(s) at boot "
                "(cause pending: %s)", n, PENDING_KIND,
            )
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
    rolls the whole rebuild back and re-raises with the backup named.
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
    missing = model_cols - set(old_cols)
    if missing:
        # Fail closed rather than rebuild into NOT NULL columns we cannot fill.
        # (_ensure_table / _apply_model_add_columns own adding them first.)
        raise RuntimeError(
            f"near_miss_archive is missing model column(s) {sorted(missing)}; "
            "refusing to rebuild the framing identity on an out-of-date table")
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


# Every archive model the ADD-only auto-migrator covers. A NEW archive table
# registers HERE at birth (near-miss lane Task 9 generalization) — otherwise
# its first model-only column silently never reaches the live DB.
_MIGRATED_ARCHIVE_MODELS = (
    ("setup_archive", lambda: archive_models.SetupArchive),
    ("near_miss_archive", lambda: archive_models.NearMissArchive),
    # Registered when it gained its first model-only column (grade_verdict,
    # TA-grade build task 14).
    ("read_verdicts", lambda: models.ReadVerdict),
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
