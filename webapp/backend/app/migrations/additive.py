"""Ordered historical SQL and model-derived additive migrations."""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text
import archive_models
import models

_log = logging.getLogger("chrollo.migrate")

from services.scan_diagnosis import LEGACY_RECONCILE_PREFIX, PENDING_KIND

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

def _apply_migrations(bind) -> None:
    with bind.connect() as conn:
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
