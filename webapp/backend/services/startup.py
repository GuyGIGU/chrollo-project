"""Startup database setup and idempotent migrations (mostly additive ALTERs, plus
the occasional one-off retired-column DROP)."""
from __future__ import annotations

import logging

from sqlalchemy import text

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
        trigger VARCHAR NOT NULL
    )
    """,
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
    # Retired sub-score — the rail-blind oscillation term, replaced by
    # score_traversal_quality. Drop the column so the live schema matches the
    # model; its pre-retirement values measured a flawed (rail-blind) quantity
    # and are preserved in the dated DB backup. Idempotent: a re-run on a DB that
    # never had the column raises "no such column", which the runner treats as
    # already-applied.
    "ALTER TABLE setup_archive DROP COLUMN score_oscillation",
]

_log = logging.getLogger("chrollo.migrate")


def initialize_database() -> None:
    models.Base.metadata.create_all(bind=engine)
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    _apply_migrations()


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
