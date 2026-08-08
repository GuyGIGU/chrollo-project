import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.routers.position_calculator import calculate_position
from webapp.backend.routers import ibkr as ibkr_router
from webapp.backend.routers import portfolio, portfolio_streams
from webapp.backend.routers.archive_schemas import SetupOut
from core.archive import forward_returns as archive_forward_returns
from core.archive import writer as archive_writer
import archive_models
import broker_config
from webapp.backend.ibkr import service as ibkr_service
from webapp.backend.services.journal_stats import calculate_journal_stats
from webapp.backend.services import portfolio_snapshot, screener_data, startup
from webapp.backend.services import health as health_service
from webapp.backend.services import scan_runner
from core.pipeline import cache_status as cache_status_module
from core.pipeline import downloads as downloads_module
from core.pipeline import scan_job as scan_job_module


def trade(pnl, entry_price=10, stop_loss=9, quantity=100):
    return SimpleNamespace(
        pnl=pnl,
        entry_price=entry_price,
        stop_loss=stop_loss,
        quantity=quantity,
    )


def test_get_trade_or_404_returns_row_and_raises(tmp_path):
    """E2: the shared trade-lookup dependency returns the row by id and raises a
    404 for a missing id — the identical behavior the trades and journal routers
    previously duplicated in _get_trade / _ensure_trade."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import database
    import models

    eng = create_engine(f"sqlite:///{tmp_path / 'trades.db'}")
    # Create the full schema so TradeLog's relationships resolve.
    database.Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng)
    db = Session()
    try:
        row = models.TradeLog(ticker="AAA", direction="L", entry_price=10.0)
        db.add(row)
        db.commit()
        trade_id = row.id

        found = database.get_trade_or_404(db, trade_id)
        assert found.id == trade_id and found.ticker == "AAA"

        with pytest.raises(HTTPException) as exc:
            database.get_trade_or_404(db, 999999)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Trade not found"
    finally:
        db.close()


def test_trade_routers_share_the_lookup_dependency():
    """E2: both routers route their per-trade lookup through the one shared
    helper — neither still defines its own copy."""
    from routers import journal as journal_router
    from routers import trades as trades_router

    assert trades_router.get_trade_or_404 is journal_router.get_trade_or_404
    # The old per-router duplicates are gone.
    assert not hasattr(trades_router, "_get_trade")
    assert not hasattr(journal_router, "_ensure_trade")


def test_calculate_journal_stats_handles_empty_list():
    stats = calculate_journal_stats([])

    assert stats["total_trades"] == 0
    assert stats["total_pnl"] == 0
    assert stats["profit_factor"] == 0


def test_calculate_journal_stats_summarizes_wins_losses_and_r_multiple():
    stats = calculate_journal_stats([
        trade(200, entry_price=10, stop_loss=9, quantity=100),
        trade(-50, entry_price=20, stop_loss=19, quantity=50),
        trade(None),
    ])

    assert stats["total_pnl"] == 150
    assert stats["win_rate"] == pytest.approx(33.33)
    assert stats["profit_factor"] == 4
    assert stats["r_multiple_total"] == 1
    assert stats["avg_win"] == 200
    assert stats["avg_loss"] == -50
    assert stats["winning_trades"] == 1
    assert stats["losing_trades"] == 1


def test_calculate_position_returns_size_from_risk_distance():
    result = calculate_position(risk_amount=100, entry_price=20, stop_price=18)

    assert result == {
        "shares": 50,
        "stop_distance": 2,
        "position_size": 1000,
    }


@pytest.mark.parametrize(
    ("risk_amount", "entry_price", "stop_price"),
    [(0, 20, 18), (100, 0, 18), (100, 20, 20)],
)
def test_calculate_position_rejects_invalid_inputs(risk_amount, entry_price, stop_price):
    with pytest.raises(HTTPException):
        calculate_position(risk_amount=risk_amount, entry_price=entry_price, stop_price=stop_price)


def test_portfolio_routes_are_registered_after_split():
    rest_paths = {route.path for route in portfolio.router.routes}
    stream_paths = {route.path for route in portfolio_streams.router.routes}

    assert "/portfolio/account-summary" in rest_paths
    assert "/ibkr/import-csv" in rest_paths
    assert "/stream/portfolio" in stream_paths
    assert "/stream/executions" in stream_paths


def test_broker_config_defaults_to_live_without_autoconnect(monkeypatch):
    monkeypatch.delenv("IBKR_MODE", raising=False)
    monkeypatch.delenv("IBKR_PORT", raising=False)
    monkeypatch.delenv("IBKR_AUTO_CONNECT", raising=False)

    cfg = broker_config.Settings.from_env()

    assert cfg.ibkr_mode == "live"
    assert cfg.ibkr_client == "gateway"
    assert cfg.ibkr_port == 4001
    assert cfg.ibkr_auto_connect is False


def test_broker_config_treats_unknown_mode_as_live_default(monkeypatch):
    monkeypatch.setenv("IBKR_MODE", "typo")
    monkeypatch.delenv("IBKR_PORT", raising=False)

    cfg = broker_config.Settings.from_env()

    assert cfg.ibkr_mode == "live"
    assert cfg.ibkr_port == 4001


def test_live_ibkr_start_requires_runtime_click(monkeypatch):
    monkeypatch.setattr(ibkr_service, "_IB_AVAILABLE", True)
    monkeypatch.setattr(ibkr_service.settings, "ibkr_mode", "live")

    svc = ibkr_service.IBKRService()
    svc.start(confirmed=False)

    assert svc.snapshot()["last_error"] == "live start blocked: runtime confirmation required"
    assert svc._thread is None


def test_live_ibkr_client_switch_requires_runtime_click(monkeypatch):
    monkeypatch.setattr(broker_config.settings, "ibkr_mode", "live")

    with pytest.raises(HTTPException) as exc:
        ibkr_router.set_ibkr_client(ibkr_router.ClientPayload(client="tws"))

    assert exc.value.status_code == 400
    assert exc.value.detail == "switching live IBKR client requires confirm=true"


def test_archive_writer_columns_are_modeled_and_migrated():
    model_columns = set(archive_models.SetupArchive.__table__.columns.keys())
    migration_sql = "\n".join(startup._MIGRATIONS)
    migration_columns = {
        statement.split(" ADD COLUMN ", 1)[1].split()[0]
        for statement in startup._MIGRATIONS
        if "ALTER TABLE setup_archive ADD COLUMN " in statement
    }

    assert set(archive_writer._NEW_COLUMNS) <= model_columns
    assert set(archive_writer._NEW_COLUMNS) <= migration_columns
    for field in archive_writer._NEW_COLUMNS:
        assert f"ADD COLUMN {field} " in migration_sql


def test_engine_config_version_is_modeled_and_auto_migrated():
    """The frozen-config stamp column is a MODEL-ONLY add: it must be a real
    SetupArchive column, must NOT be hand-listed in the legacy writer _NEW_COLUMNS
    (it relies on Track B + model-diff instead), and Track B's model-derived
    auto-migration must emit its ADD on an existing table that lacks it."""
    import sqlalchemy as sa
    from sqlalchemy import inspect, text

    model_columns = set(archive_models.SetupArchive.__table__.columns.keys())
    assert "engine_config_version" in model_columns
    # deliberately not in the hand-listed writer column SQL (model-only add)
    assert "engine_config_version" not in archive_writer._NEW_COLUMNS

    # Track B auto-migration emits the ADD on an existing pre-change table.
    eng = sa.create_engine("sqlite:///:memory:")
    cols = [c for c in archive_models.SetupArchive.__table__.columns
            if c.name != "engine_config_version"]
    coldefs = ", ".join(f"{c.name} {c.type}" for c in cols)
    with eng.begin() as conn:
        conn.execute(text(f"CREATE TABLE setup_archive ({coldefs})"))
    stmts = startup.model_add_column_migrations(eng)
    assert any("engine_config_version" in s for s in stmts)


def test_event_map_columns_are_modeled_and_auto_migrated():
    """The Event Map tape-summary family (Task 7) is declared ONCE in
    engine_alpha.structure.event_map (EVENT_MAP_COLUMN_SQL) and enters the schema as
    MODEL-ONLY adds (the engine_config_version precedent): every declared column
    is a real SetupArchive column, none is hand-listed in the writer's
    _NEW_COLUMNS or startup._MIGRATIONS, and Track B's model-derived
    auto-migration emits their ADDs on an existing table that lacks them."""
    import sqlalchemy as sa
    from sqlalchemy import text

    from engine_alpha.structure.event_map import EVENT_MAP_COLUMN_SQL

    model_columns = set(archive_models.SetupArchive.__table__.columns.keys())
    assert set(EVENT_MAP_COLUMN_SQL) <= model_columns
    assert not set(EVENT_MAP_COLUMN_SQL) & set(archive_writer._NEW_COLUMNS)
    migration_sql = "\n".join(startup._MIGRATIONS)
    assert not any(f"ADD COLUMN {c} " in migration_sql for c in EVENT_MAP_COLUMN_SQL)

    eng = sa.create_engine("sqlite:///:memory:")
    cols = [c for c in archive_models.SetupArchive.__table__.columns
            if c.name not in EVENT_MAP_COLUMN_SQL]
    coldefs = ", ".join(f"{c.name} {c.type}" for c in cols)
    with eng.begin() as conn:
        conn.execute(text(f"CREATE TABLE setup_archive ({coldefs})"))
    stmts = startup.model_add_column_migrations(eng)
    for col in EVENT_MAP_COLUMN_SQL:
        assert any(f"ADD COLUMN {col} " in s for s in stmts), f"missing ADD for {col}"


def test_ensure_new_columns_adds_model_only_columns(tmp_path):
    """The writer/seed self-sufficiency helper (_ensure_new_columns) brings an
    existing table up to the MODEL even for columns absent from _NEW_COLUMNS, so
    the standalone seed CLI can stamp engine_config_version before the backend's
    Track B migration has run. Idempotent on re-run."""
    import sqlalchemy as sa
    from sqlalchemy import inspect, text

    db = tmp_path / "seed.db"
    eng = sa.create_engine(f"sqlite:///{db}")
    cols = [c for c in archive_models.SetupArchive.__table__.columns
            if c.name != "engine_config_version"]
    coldefs = ", ".join(f"{c.name} {c.type}" for c in cols)
    with eng.begin() as conn:
        conn.execute(text(f"CREATE TABLE setup_archive ({coldefs})"))

    archive_writer._ensure_new_columns(eng)
    present = {c["name"] for c in inspect(eng).get_columns("setup_archive")}
    assert "engine_config_version" in present

    # A row carrying the stamp inserts and round-trips.
    from engine_alpha.freeze.manifest import manifest_hash
    h = manifest_hash()
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO setup_archive "
            "(ticker, scan_date, setup_type, tier, score, engine_config_version, source) "
            "VALUES ('TST', '2026-06-29', 'LPS', 'A', 1.0, :h, 'seed')"
        ), {"h": h})
        got = conn.execute(
            text("SELECT engine_config_version FROM setup_archive WHERE ticker='TST'")
        ).scalar()
    assert got == h

    archive_writer._ensure_new_columns(eng)  # idempotent, must not raise
    eng.dispose()


def test_archive_outcome_columns_are_modeled_and_migrated():
    model_columns = set(archive_models.SetupArchive.__table__.columns.keys())
    schema_fields = set(SetupOut.model_fields)
    migration_sql = "\n".join(startup._MIGRATIONS)
    migration_columns = {
        statement.split(" ADD COLUMN ", 1)[1].split()[0]
        for statement in startup._MIGRATIONS
        if "ALTER TABLE setup_archive ADD COLUMN " in statement
    }

    assert set(archive_forward_returns._OUTCOME_COLUMNS) <= model_columns
    assert set(archive_forward_returns._OUTCOME_COLUMNS) <= schema_fields
    assert set(archive_forward_returns._OUTCOME_COLUMNS) <= migration_columns
    for field in archive_forward_returns._OUTCOME_COLUMNS:
        assert f"ADD COLUMN {field} " in migration_sql


# Frozen snapshot of the SetupOut response field set. SetupArchive.__table__ is
# the single source of truth for the schema: SetupOut is a *curated projection*
# (subset) of those columns, deliberately NOT exposing internal columns such as
# score_traversal_quality, breadth_pct, the regime_*/scope_*/stage2_* context, or
# the trav_last_support_frac / trav_coil_floor_pos descent-tail internals. The two
# guards below enforce (a) every exposed field maps to a real column — so a stale
# or typo'd field name fails the build — and (b) the API shape itself does not drift
# silently: changing SetupOut must update this snapshot, which forces a deliberate
# review. Regenerate with:
#   python -c "import routers.archive_schemas as s; print(tuple(s.SetupOut.model_fields))"
_SETUP_OUT_FIELDS = (
    'id', 'ticker', 'scan_date', 'setup_type',
    'tier', 'score', 'current_price', 'r_level',
    's_level', 'trigger_price', 'base_length', 'box_width',
    'touches', 'r_touches', 's_touches', 'r_anchor',
    's_anchor', 'atr_ratio', 'lps_length', 'breach_days',
    'vol_contraction', 'tightness_ratio', 'score_box_tightness', 'score_touch_density',
    'score_traversal_quality', 'score_atr_squeeze', 'score_lps_tightness', 'score_vol_contraction',
    'score_base_age', 'score_uptrend_bonus', 'triggered', 'trigger_date',
    'fwd_return_1d', 'fwd_return_5d', 'fwd_return_10d', 'fwd_return_20d',
    'fwd_return_60d', 'mfe_20d', 'mae_20d', 'mfe_60d',
    'mae_60d', 'mfe_20d_date', 'mae_20d_date', 'r_multiple_20d',
    'r_multiple_60d', 'trigger_volume_ratio', 'days_to_trigger', 'days_to_2_5r',
    'days_to_15pct', 'days_to_stop', 'barrier_label', 'win_barrier',
    'mfe_to_date', 'mae_to_date', 'ret_to_date', 'bars_to_date',
    'abnormal_ret_to_date', 'spy_trend', 'vix_level', 'sector_etf',
    'sector_trend', 'rs_vs_sector_pct', 'dist_52w_high_pct', 'regime_state',
    'regime_breadth_50_pct', 'regime_breadth_200_pct', 'regime_distribution_days', 'regime_spy_above_50',
    'regime_spy_above_200', 'regime_spy_50d_slope_pct', 'regime_qqq_above_50', 'regime_qqq_above_200',
    'regime_qqq_50d_slope_pct', 'phase_d_inner', 'lps_in_inner', 'inner_source',
    'inner_search_start_bar', 'inner_climax_bar', 'inner_reaction_bar', 'inner_reaction_pct',
    'inner_reaction_bars', 'htf_w_stage2', 'htf_w_trend_state', 'htf_w_in_consol',
    'htf_w_phase', 'htf_w_box_r', 'htf_w_box_s', 'htf_w_box_width',
    'htf_w_reaccum', 'htf_w_daily_nested', 'htf_m_stage2', 'htf_m_trend_state',
    'htf_m_in_consol', 'htf_m_phase', 'htf_m_box_r', 'htf_m_box_s',
    'htf_m_box_width', 'htf_m_reaccum', 'htf_m_daily_nested', 'r_touch_vol_z',
    's_touch_vol_z', 'lps_descent_frac', 'lps_zone_type', 'score_high_proximity',
    'score_breadth_bonus', 'score_rs_bonus', 'contraction_count', 'contraction_quality',
    'final_contraction_depth', 'contraction_vol_trend', 'score_contraction', 'base_median_spread_atr',
    'base_p80_spread_atr', 'base_median_spread_pct_box', 'base_tight_bar_pct', 'support_slope_atr',
    'ascending_support_quality', 'score_ascending_support', 'eq_r_touches', 'eq_s_touches',
    'eq_r_touch_thirds', 'eq_s_touch_thirds', 'eq_lower_dwell', 'eq_mid_dwell',
    'eq_upper_dwell', 'eq_coverage', 'bin_a_bars', 'bin_a_range_pct',
    'bin_a_volume_ratio', 'bin_b_bars', 'bin_b_range_pct', 'bin_b_volume_ratio',
    'bin_b_cog_end', 'bin_b_cog_crossings', 'bin_b_cog_rng', 'bin_b_cog_corr',
    'bin_c_present', 'bin_c_type', 'bin_c_event_date', 'bin_c_event_bar',
    'bin_c_undercut_atr', 'bin_c_recovery_bars', 'bin_c_recovery_bar', 'bin_c_time_loc',
    'bin_c_spring_vol_z', 'bin_d_bars', 'bin_d_start_bar', 'bin_d_range_pct',
    'bin_d_volume_ratio', 'bin_d_support_slope_atr', 'bin_d_higher_low_frac', 'bin_d_ascending_support_quality',
    'bin_d_boundary_source', 'phase_d_evidence_json', 'bin_lps_bars', 'lps_position_in_box',
    'bin_d_vs_b_range_ratio', 'bin_d_vs_b_volume_ratio', 'bin_d_vs_b_support_quality_delta', 'lps_stretch_atr',
    'lps_stretch_box', 'lps_swing_type', 'lps_anchor_bar', 'lps_anchor_date',
    'lps_low_bar', 'lps_low_date', 'lps_swing_depth_pct', 'lps_swing_depth_atr',
    'lps_swing_depth_box', 'last_supper_pullback_from_extension_pct', 'last_supper_source_box_age', 'last_supper_reclaim_quality',
    'adr_pct', 'score_adr', 'quality_label', 'notes',
    'source', 'universe_type', 'engine_config_version', 'elected_pool',
    'story_admission_profile', 'event_map_n_swings', 'event_map_pre_box_trend', 'event_map_n_labels',
    'event_map_n_committed', 'event_map_completed_s', 'event_map_completed_r', 'event_map_alternations',
    'event_map_terminal_posture', 'event_map_terminal_drift', 'event_map_story_admitted', 'event_map_episode_nan_bars',
    'event_map_episode_profile', 'event_map_episodes', 'election_trace', 'ta_grade',
    'ta_grade_raw', 'setup_completeness', 'setup_chronology', 'setup_upthrust_terminal',
    'score_setup_quality', 'score_spring', 'score_story_s_tests', 'score_story_r_rejections',
    'score_story_alternations', 'score_story_terminal_posture', 'lps_shrink_frac', 'lps_window_classification',
    'story_richness_rate', 'trend_base_count', 'inter_base_width_ratio', 'fired_tags',
)


def test_archive_row_from_result_maps_passthrough_and_respects_overrides():
    """Round-trip guard for the manual-add row mapping (B2).

    archive_row_from_result must: (a) flat-map every model column from
    result.get(col); (b) let the caller's `overrides` win over the flat value;
    (c) never emit `id` or any column in _MANUAL_UNMAPPED_COLUMNS (those are
    filled by the route's **fwd_returns splat or left NULL); and (d) build a
    valid SetupArchive whose column values match. This pins the byte-parity of
    the refactor that replaced the ~80-line inline result.get(...) block."""
    from services.archive_queries import (
        archive_row_from_result,
        _MANUAL_UNMAPPED_COLUMNS,
    )

    columns = [c.name for c in archive_models.SetupArchive.__table__.columns]
    # Unique sentinel per column so a mis-key would surface as a value mismatch.
    result = {c: f"R:{c}" for c in columns}

    overrides = {
        "ticker": "ABCD",
        "scan_date": "2026-06-01",
        "source": "manual",
        # An override must beat the flat result.get for the same column.
        "bin_a_bars": 99,
        # A forward-return splat column (in _MANUAL_UNMAPPED) the route supplies.
        "triggered": 1,
    }

    kwargs = archive_row_from_result(result, overrides=overrides)

    # id is never set by the mapping (auto-increment).
    assert "id" not in kwargs
    # _MANUAL_UNMAPPED columns are not auto-filled from result; only those the
    # caller explicitly passed in overrides appear.
    for name in _MANUAL_UNMAPPED_COLUMNS:
        if name in overrides:
            assert kwargs[name] == overrides[name]
        else:
            assert name not in kwargs, f"{name} should not be auto-filled"
    # Overrides win over the flat pass-through.
    assert kwargs["ticker"] == "ABCD"
    assert kwargs["bin_a_bars"] == 99
    assert kwargs["triggered"] == 1
    # A representative flat column is pulled straight from result.
    assert kwargs["lps_swing_type"] == "R:lps_swing_type"
    assert kwargs["eq_coverage"] == "R:eq_coverage"
    # The kwargs build a real SetupArchive without unexpected/unknown columns.
    row = archive_models.SetupArchive(**kwargs)
    assert row.ticker == "ABCD"
    assert row.bin_a_bars == 99
    assert row.lps_swing_type == "R:lps_swing_type"


def test_archive_row_partition_is_exhaustive():
    """Every SetupArchive column is accounted for: it is either auto-mapped by
    archive_row_from_result, or explicitly in _MANUAL_UNMAPPED_COLUMNS, or the
    auto-increment id. Guards against a new column being silently neither — which
    would otherwise mean a flat column the route stops populating, or an unmapped
    column with no documented reason."""
    from services.archive_queries import (
        archive_row_from_result,
        _MANUAL_UNMAPPED_COLUMNS,
    )

    columns = {c.name for c in archive_models.SetupArchive.__table__.columns}
    # With empty overrides, the helper auto-fills exactly the flat columns.
    auto_mapped = set(archive_row_from_result({}, overrides={}))

    accounted = auto_mapped | set(_MANUAL_UNMAPPED_COLUMNS) | {"id"}
    assert accounted == columns, (
        f"unaccounted columns: {sorted(columns - accounted)}; "
        f"stale entries: {sorted(accounted - columns)}"
    )
    # The two groups are disjoint — a column is auto-mapped XOR unmapped.
    assert not (auto_mapped & set(_MANUAL_UNMAPPED_COLUMNS))


def test_setup_out_fields_are_all_real_archive_columns():
    """Single-source guard: SetupArchive.__table__ is the source of truth, and
    every SetupOut response field must be a column-backed projection of it. A field
    that names no model column (a typo, or a column renamed/removed under it) fails
    here — so the response model can never silently drift away from the table.
    The EpisodeOut subclass adds nested non-column fields (episode_key, scan_count,
    …); those are intentionally excluded by testing the base SetupOut only."""
    model_columns = set(archive_models.SetupArchive.__table__.columns.keys())
    schema_fields = set(SetupOut.model_fields)

    orphan_fields = schema_fields - model_columns
    assert not orphan_fields, (
        "SetupOut fields with no backing SetupArchive column "
        f"(schema drifted from the model): {sorted(orphan_fields)}"
    )


def test_setup_out_shape_is_unchanged():
    """API shape tripwire: the SetupOut field set must match the frozen snapshot
    exactly — same names, same order. Adding/removing/renaming a response field
    (the day someone exposes a new column, or drops one) must update _SETUP_OUT_FIELDS
    in the same commit, making the public-API change deliberate and reviewable."""
    assert tuple(SetupOut.model_fields) == _SETUP_OUT_FIELDS


def test_model_add_column_migrations_empty_when_db_matches_model(tmp_path):
    """B3: against a DB created from the current model, the generator proposes
    ZERO ALTERs — it is idempotent and emits no spurious ADD COLUMN."""
    from sqlalchemy import create_engine

    eng = create_engine(f"sqlite:///{tmp_path / 'match.db'}")
    archive_models.SetupArchive.__table__.create(bind=eng)

    assert startup.model_add_column_migrations(eng) == []


def test_model_add_column_migrations_proposes_exactly_the_missing_column(tmp_path):
    """B3: against a DB missing one column, the generator proposes exactly that
    one ADD COLUMN (ADD-only, model-typed) and nothing else."""
    from sqlalchemy import Column, MetaData, Table, create_engine

    eng = create_engine(f"sqlite:///{tmp_path / 'missing.db'}")
    full = archive_models.SetupArchive.__table__
    dropped = "adr_pct"  # a real, late-added FLOAT column
    # Build a table identical to the model but lacking exactly one column, using
    # fresh Column objects on a throwaway MetaData (no clobbering the model).
    partial = Table(
        full.name,
        MetaData(),
        *[
            Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable)
            for c in full.columns
            if c.name != dropped
        ],
    )
    partial.create(bind=eng)

    statements = startup.model_add_column_migrations(eng)

    assert statements == [f"ALTER TABLE setup_archive ADD COLUMN {dropped} FLOAT"]


def test_model_add_column_migrations_empty_when_table_absent(tmp_path):
    """B3: with no setup_archive table yet, the generator is a no-op (create_all
    builds the fresh table; the generator never tries to CREATE)."""
    from sqlalchemy import create_engine

    eng = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")

    assert startup.model_add_column_migrations(eng) == []


def test_scan_run_kind_column_is_migrated():
    migration_sql = "\n".join(startup._MIGRATIONS)

    assert "kind VARCHAR DEFAULT 'scan'" in migration_sql
    assert "ALTER TABLE scan_runs ADD COLUMN kind " in migration_sql


def test_portfolio_stream_listens_to_snapshot_changing_channels():
    assert portfolio_streams._PORTFOLIO_CHANNELS == (
        "portfolio",
        "ibkr_status",
        "orders",
        "executions",
    )


def test_screener_summary_strips_heavy_cells_and_keeps_narrative_scalars(monkeypatch):
    """Council review 2026-08-05 (finding 15 / beck B4): the /screener-summary
    denylist is the ONE mechanism keeping the bar arrays AND the two deep
    narrative cells (the episode tape, the election trace) off the light wire
    the Home tiles poll — a key typo here would ship the tape on every
    freshness check with nothing going red."""
    from types import SimpleNamespace

    from routers import screener as sr

    payload = {
        "chart_data": {"AAA": {
            "score": 91.0,
            "candles": [1], "volumes": [1], "weekly_candles": [1],
            "weekly_volumes": [1], "monthly_candles": [1], "monthly_volumes": [1],
            "event_map_episodes": [{"rail": "S"}],
            "election_trace": {"roots": []},
            "event_map_completed_s": 2,
            "event_map_episode_profile": "S+ S+",
            "elected_pool": "strict",
        }},
        "ordered_tickers": ["AAA"],
        "market_context": {},
    }
    monkeypatch.setattr(
        sr, "_artifact_state",
        lambda universe: (SimpleNamespace(key="us-stocks"), "unused.json", "ready", "t"))
    monkeypatch.setattr(sr, "read_screener_data", lambda path: payload)

    row = sr.get_screener_summary()["setups"]["AAA"]
    for heavy in ("candles", "volumes", "weekly_candles", "weekly_volumes",
                  "monthly_candles", "monthly_volumes",
                  "event_map_episodes", "election_trace"):
        assert heavy not in row
    # The scalars + the sentence + the pool ride the light wire deliberately.
    assert row["event_map_completed_s"] == 2
    assert row["event_map_episode_profile"] == "S+ S+"
    assert row["elected_pool"] == "strict"
    assert row["score"] == 91.0


def test_screener_data_serves_last_good_payload_on_bad_json(tmp_path):
    path = tmp_path / "screener_data.json"
    screener_data.invalidate_screener_cache()
    path.write_text('{"ordered_tickers": ["AAA"], "chart_data": {"AAA": {}}}', encoding="utf-8")

    assert screener_data.read_screener_data(str(path))["ordered_tickers"] == ["AAA"]

    path.write_text('{"ordered_tickers": [', encoding="utf-8")
    os.utime(path, (path.stat().st_atime + 5, path.stat().st_mtime + 5))

    assert screener_data.read_screener_data(str(path))["ordered_tickers"] == ["AAA"]


def test_screener_data_bad_first_read_returns_empty(tmp_path):
    path = tmp_path / "screener_data.json"
    screener_data.invalidate_screener_cache()
    path.write_text('{"ordered_tickers": [', encoding="utf-8")

    assert screener_data.read_screener_data(str(path)) == {
        "ordered_tickers": [],
        "chart_data": {},
    }


def test_run_all_universe_scans_isolates_failures(monkeypatch):
    from core.pipeline import scan_job as sj

    calls = []

    def fake_scan(mode="download", universe=None):
        calls.append(universe.key)
        if universe.key == "us_sectors":
            raise RuntimeError("boom")
        return sj.ScanExportResult(n_setups=1, n_archived=0)

    monkeypatch.setattr(sj, "run_scan_and_export", fake_scan)
    results = sj.run_all_universe_scans(mode="cache")

    assert calls[0] == "us_stocks"  # stocks first (context source)
    assert results["us_sectors"] is None  # failure isolated, did not abort the run
    assert results["us_stocks"].n_setups == 1
    assert results["commodities_etf"].n_setups == 1  # ran despite sectors failing


def test_screener_data_endpoint_rejects_unknown_universe():
    from fastapi import HTTPException
    from routers import screener as screener_router

    with pytest.raises(HTTPException) as exc:
        screener_router.get_screener_data(universe="../../etc/passwd")
    assert exc.value.status_code == 422


def test_screener_data_endpoint_status_never_scanned(monkeypatch):
    from routers import screener as screener_router

    monkeypatch.setattr(screener_router, "read_screener_data",
                        lambda path: {"ordered_tickers": [], "chart_data": {}})
    monkeypatch.setattr(screener_router.os.path, "exists", lambda path: False)
    out = screener_router.get_screener_data(universe="commodities_etf")
    assert out["universe"] == "commodities_etf"
    assert out["status"] == "never_scanned"  # no artifact -> distinct sentinel
    assert out["scanned_at"] is None


def test_screener_data_endpoint_status_ready(monkeypatch):
    from routers import screener as screener_router

    monkeypatch.setattr(screener_router, "read_screener_data",
                        lambda path: {"ordered_tickers": ["AAA"], "chart_data": {"AAA": {}}})
    monkeypatch.setattr(screener_router.os.path, "exists", lambda path: True)
    monkeypatch.setattr(screener_router.os.path, "getmtime", lambda path: 1_700_000_000.0)
    out = screener_router.get_screener_data(universe="us_stocks")
    assert out["universe"] == "us_stocks"
    assert out["status"] == "ready"  # artifact present -> ready, with a timestamp
    assert out["scanned_at"] is not None


def _valid_health_member(**overrides):
    member = {
        "ticker": "XLE", "name": "Energy", "state": "near_resistance",
        "box_pos": 0.92, "breakout_extension": None, "distance_to_high_pct": -0.03,
        "R": 100.0, "S": 90.0, "base_len": 60, "candles": [], "volumes": [],
    }
    member.update(overrides)
    return member


def test_screener_data_endpoint_passes_valid_health_board_through(monkeypatch):
    from routers import screener as screener_router

    hb = {"members": [_valid_health_member()], "unreadable": [], "member_count": 1}
    monkeypatch.setattr(screener_router, "read_screener_data",
                        lambda path: {"ordered_tickers": [], "chart_data": {}, "health_board": hb})
    monkeypatch.setattr(screener_router.os.path, "exists", lambda path: True)
    monkeypatch.setattr(screener_router.os.path, "getmtime", lambda path: 1_700_000_000.0)
    out = screener_router.get_screener_data(universe="us_sectors")
    assert out["health_board"] == hb  # passes straight through, unmodified
    assert out["status"] == "ready"


def test_screener_data_endpoint_surfaces_buy_language_in_health(monkeypatch):
    # A stray score/tier/trigger on a member violates the "no buy language" contract;
    # extra='forbid' makes the boundary SURFACE it (raise) rather than serve it.
    from pydantic import ValidationError
    from routers import screener as screener_router

    hb = {"members": [_valid_health_member(score=88, tier="S")], "unreadable": [], "member_count": 1}
    monkeypatch.setattr(screener_router, "read_screener_data",
                        lambda path: {"ordered_tickers": [], "chart_data": {}, "health_board": hb})
    monkeypatch.setattr(screener_router.os.path, "exists", lambda path: True)
    monkeypatch.setattr(screener_router.os.path, "getmtime", lambda path: 1_700_000_000.0)
    with pytest.raises(ValidationError):
        screener_router.get_screener_data(universe="us_sectors")


def test_screener_data_endpoint_surfaces_unknown_health_state(monkeypatch):
    from pydantic import ValidationError
    from routers import screener as screener_router

    hb = {"members": [_valid_health_member(state="buy_now")], "unreadable": [], "member_count": 1}
    monkeypatch.setattr(screener_router, "read_screener_data",
                        lambda path: {"ordered_tickers": [], "chart_data": {}, "health_board": hb})
    monkeypatch.setattr(screener_router.os.path, "exists", lambda path: True)
    monkeypatch.setattr(screener_router.os.path, "getmtime", lambda path: 1_700_000_000.0)
    with pytest.raises(ValidationError):
        screener_router.get_screener_data(universe="us_sectors")


def test_health_state_literal_matches_engine_taxonomy():
    # The serve-boundary Literal must stay equal to the engine's closed set.
    from typing import get_args
    from routers import screener as screener_router
    from core.pipeline.health_board import HEALTH_STATE_ORDER

    assert get_args(screener_router.HealthStateName) == HEALTH_STATE_ORDER


def test_drilldown_resolves_sector_commodity_and_none(monkeypatch):
    from routers import screener as screener_router

    us = {
        "ordered_tickers": ["AAA", "BBB", "CCC"],
        "chart_data": {
            "AAA": {"sector_etf": "XLK"},
            "BBB": {"sector_etf": "XLF"},
            "CCC": {"sector_etf": "XLK"},
        },
    }
    monkeypatch.setattr(screener_router, "read_screener_data", lambda path: us)

    sector = screener_router.get_drilldown(etf="xlk")  # case-insensitive
    assert sector["basis"] == "sector"
    assert set(sector["ordered_tickers"]) == {"AAA", "CCC"}
    assert sector["source_universe"] == "us_stocks"

    commodity = screener_router.get_drilldown(etf="GLD")  # in the curated map
    assert commodity["basis"] == "commodity"  # mapped; no gold miners in this scan -> empty
    assert commodity["ordered_tickers"] == []

    unmapped = screener_router.get_drilldown(etf="ZZZZ")
    assert unmapped["basis"] == "none"
    assert unmapped["ordered_tickers"] == []


def test_portfolio_sse_data_is_strict_json_safe():
    event = portfolio_streams._sse_data({
        "value": np.float32(0.5),
        "bad": np.inf,
    })

    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload == {"value": 0.5, "bad": None}


def test_portfolio_snapshot_saves_useful_payload(monkeypatch):
    saved = []
    monkeypatch.setattr(portfolio_snapshot, "save_snapshot_cache", saved.append)

    monkeypatch.setattr(
        portfolio_snapshot,
        "get_ibkr_service",
        lambda: SimpleNamespace(snapshot=lambda: {
            "connected": True,
            "mode": "paper",
            "stale": False,
            "daily_restart": False,
            "session_competition": False,
            "last_update": 123,
            "account_summary": {},
            "positions": [],
            "portfolio": [{"symbol": "AAPL"}],
            "open_orders": [],
            "recent_executions": [],
        }),
    )

    payload = portfolio_snapshot.portfolio_snapshot_payload()

    assert payload["positions"] == [{"symbol": "AAPL"}]
    assert saved == [payload]


def test_portfolio_stream_starts_with_snapshot(monkeypatch):
    monkeypatch.setattr(
        portfolio_streams,
        "portfolio_snapshot_payload",
        lambda: {"connected": False, "positions": [{"symbol": "AAPL"}]},
    )
    request = SimpleNamespace(is_disconnected=lambda: False)

    first_event = asyncio.run(_first_stream_event(request))

    assert first_event.startswith("data: ")
    assert '"symbol": "AAPL"' in first_event


async def _first_stream_event(request):
    stream = portfolio_streams._stream_snapshot_events(request)
    try:
        return await anext(stream)
    finally:
        await stream.aclose()


def _status_panel(symbols, day):
    return pd.concat(
        {
            symbol: pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[pd.Timestamp(day)])
            for symbol in symbols
        },
        axis=1,
    )


def _wire_cache_status(tmp_path, monkeypatch, panel=None, tickers=None,
                       expected="2026-06-25", meta=None, admission=None):
    from core.pipeline.downloads import _price_regime

    cache_file = tmp_path / "market_cache.parquet"
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text(
        json.dumps(meta or {
            "last_full_refresh": datetime.now(timezone.utc).isoformat(),
            # current-regime tag: an untagged meta now classifies regime_mismatch
            "price_series": _price_regime(),
        }),
        encoding="utf-8",
    )
    if admission is not None:
        (tmp_path / "ticker_admission.json").write_text(
            json.dumps(admission),
            encoding="utf-8",
        )
    if panel is not None:
        panel.to_parquet(cache_file)
    monkeypatch.setattr(cache_status_module, "_cache_paths", lambda: (str(cache_file), str(meta_file)))
    monkeypatch.setattr(cache_status_module, "get_cached_tickers", lambda: tickers or ["AAA"])
    monkeypatch.setattr(cache_status_module, "latest_completed_session", lambda now_et=None: pd.Timestamp(expected))
    monkeypatch.setattr(
        cache_status_module,
        "next_session_close",
        lambda now_et=None: (
            pd.Timestamp("2026-06-26"),
            datetime(2026, 6, 26, 16, 0, tzinfo=timezone.utc),
        ),
    )
    monkeypatch.setattr(cache_status_module, "market_closed_reason", lambda now_et=None: None)
    monkeypatch.setattr(cache_status_module, "is_early_close_session", lambda day: False)
    monkeypatch.setattr(cache_status_module.settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)


def test_market_data_status_reports_missing_cache(tmp_path, monkeypatch):
    _wire_cache_status(tmp_path, monkeypatch, panel=None)

    status = cache_status_module.build_market_data_status()

    assert status["status"] == "cache_missing"
    assert status["can_download"] is True
    assert status["can_evaluate"] is False


def test_market_data_status_reports_current_cache(tmp_path, monkeypatch):
    _wire_cache_status(
        tmp_path,
        monkeypatch,
        panel=_status_panel(["AAA", "SPY", "QQQ"], "2026-06-25"),
    )

    status = cache_status_module.build_market_data_status()

    assert status["status"] == "healthy"
    assert status["can_download"] is False
    assert status["can_evaluate"] is True
    assert status["coverage"]["text"] == "3/3 (100.0%)"


def test_market_data_status_reports_new_data_available(tmp_path, monkeypatch):
    """One session behind with a COMPLETE panel reads as session_lag, not stale.

    Operator ruling 2026-07-27, after 2026-07-24 (which the static NYSE rule calendar
    calls a session and Yahoo has no bar for): a cache complete through its own last
    session is readable. Downloading is still offered and archiving stays shut.
    """
    _wire_cache_status(
        tmp_path,
        monkeypatch,
        panel=_status_panel(["AAA", "SPY", "QQQ"], "2026-06-24"),
    )

    status = cache_status_module.build_market_data_status()

    assert status["status"] == "session_lag"
    assert status["can_download"] is True
    assert status["can_evaluate"] is True
    assert status["can_archive"] is False


def test_market_data_status_blocks_when_lag_exceeds_tolerance(tmp_path, monkeypatch):
    """The lag tolerance is BOUNDED. Beyond MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS a
    complete-but-old panel is still refused, so a real outage can never read as
    usable just because the bars it does have are internally complete."""
    _wire_cache_status(
        tmp_path,
        monkeypatch,
        panel=_status_panel(["AAA", "SPY", "QQQ"], "2026-06-17"),
    )

    status = cache_status_module.build_market_data_status()

    assert status["status"] == "stale_session"
    assert status["can_evaluate"] is False
    assert status["can_archive"] is False


def test_market_data_status_reports_low_coverage(tmp_path, monkeypatch):
    _wire_cache_status(
        tmp_path,
        monkeypatch,
        panel=_status_panel(["AAA", "SPY", "QQQ"], "2026-06-25"),
        tickers=["AAA", "BBB"],
    )

    status = cache_status_module.build_market_data_status()

    assert status["status"] == "needs_repair"
    assert status["can_download"] is True
    assert status["can_evaluate"] is False
    assert status["coverage"]["text"] == "3/4 (75.0%)"


def test_market_data_status_uses_eligible_coverage_for_raw_partial_cache(tmp_path, monkeypatch):
    next_check = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    _wire_cache_status(
        tmp_path,
        monkeypatch,
        panel=_status_panel(["AAA", "SPY", "QQQ"], "2026-06-25"),
        tickers=["AAA", "YNG"],
        admission={
            "YNG": {
                "status": "active_young",
                "next_check": next_check,
            },
        },
    )

    status = cache_status_module.build_market_data_status()

    assert status["status"] == "healthy"
    assert status["can_download"] is False
    assert status["can_evaluate"] is True
    assert status["can_archive"] is True
    assert status["coverage"]["raw"]["text"] == "3/4 (75.0%)"
    assert status["coverage"]["eligible"]["text"] == "3/3 (100.0%)"
    assert status["missing_summary"]["skipped_missing_count"] == 1


def test_market_data_status_cools_down_repair_and_blocks_low_eligible_eval(tmp_path, monkeypatch):
    cooldown_until = datetime(2026, 6, 25, 14, 30, tzinfo=timezone.utc)
    _wire_cache_status(
        tmp_path,
        monkeypatch,
        panel=_status_panel(["AAA", "SPY", "QQQ"], "2026-06-25"),
        tickers=["AAA", "BBB"],
        meta={
            "last_full_refresh": datetime.now(timezone.utc).isoformat(),
            "price_series": downloads_module._price_regime(),
            "repair_state": {
                "next_retry_at": cooldown_until.isoformat(),
                "retry_reason": "1 symbol(s) still missing the latest close",
                "error_class": "sparse_symbols",
                "attempt_count": 1,
            },
        },
    )

    status = cache_status_module.build_market_data_status(
        datetime(2026, 6, 25, 14, 10, tzinfo=timezone.utc)
    )

    assert status["status"] == "needs_repair"
    assert status["can_download"] is False
    assert status["can_evaluate"] is False
    assert status["download_label"] == "Cooldown 20m"


def test_download_only_refresh_does_not_evaluate_or_archive(tmp_path, monkeypatch):
    expected = "2026-06-25"
    panel = _status_panel(["AAA", "SPY", "QQQ"], expected)
    meta_file = tmp_path / "cache_meta.json"
    # The fake provider below never writes the meta the real fetch_data would,
    # so pin the current-regime tag (untagged now classifies regime_mismatch).
    meta_file.write_text(
        json.dumps({"price_series": downloads_module._price_regime()}), encoding="utf-8"
    )
    monkeypatch.setattr(scan_job_module, "_cache_paths", lambda: (str(tmp_path / "cache.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_job_module, "get_tickers", lambda: ["AAA"])
    monkeypatch.setattr(
        scan_job_module,
        "get_provider",
        lambda: SimpleNamespace(fetch=lambda tickers: panel),
    )
    monkeypatch.setattr(scan_job_module, "_expected_session_date", lambda: expected)
    monkeypatch.setattr(scan_job_module, "run_screener", lambda *a, **k: (_ for _ in ()).throw(AssertionError("evaluated")))
    monkeypatch.setattr(scan_job_module, "generate_dashboard", lambda *a, **k: (_ for _ in ()).throw(AssertionError("dashboard")))
    monkeypatch.setattr(scan_job_module, "archive_scan_results", lambda *a, **k: (_ for _ in ()).throw(AssertionError("archive")))

    result = scan_job_module.refresh_market_data_cache()

    assert result.n_tickers == 1
    assert result.latest_session == expected
    assert result.coverage == "3/3 (100.0%)"


def test_download_only_partial_coverage_sets_cooldown_without_failing(tmp_path, monkeypatch):
    expected = "2026-06-25"
    panel = _status_panel(["AAA", "SPY", "QQQ"], expected)
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text(
        json.dumps({"price_series": downloads_module._price_regime()}), encoding="utf-8"
    )
    monkeypatch.setattr(scan_job_module, "_cache_paths", lambda: (str(tmp_path / "cache.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_job_module.settings, "MARKET_DATA_REPAIR_FIRST_RETRY_MINUTES", 12)
    monkeypatch.setattr(scan_job_module, "get_tickers", lambda: ["AAA", "BBB"])
    monkeypatch.setattr(
        scan_job_module,
        "get_provider",
        lambda: SimpleNamespace(fetch=lambda tickers: panel),
    )
    monkeypatch.setattr(scan_job_module, "_expected_session_date", lambda: expected)
    monkeypatch.setattr(scan_job_module, "run_screener", lambda *a, **k: (_ for _ in ()).throw(AssertionError("evaluated")))
    monkeypatch.setattr(scan_job_module, "generate_dashboard", lambda *a, **k: (_ for _ in ()).throw(AssertionError("dashboard")))
    monkeypatch.setattr(scan_job_module, "archive_scan_results", lambda *a, **k: (_ for _ in ()).throw(AssertionError("archive")))

    result = scan_job_module.refresh_market_data_cache()

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert result.ready is False
    assert result.partial is True
    assert result.coverage == "3/4 (75.0%)"
    assert result.health_state == "needs_repair"
    assert result.cooldown_until == meta["repair_state"]["next_retry_at"]
    assert meta["repair_state"]["error_class"] == "sparse_symbols"
    assert meta["repair_state"]["retry_reason"] == "1 symbol(s) still missing the latest close"


def test_cached_raw_partial_evaluation_archives_when_eligible_cache_is_healthy(tmp_path, monkeypatch):
    expected = "2026-06-25"
    panel = _status_panel(["AAA", "SPY", "QQQ"], expected)
    results = pd.DataFrame([{"Ticker": "AAA", "Score": 10.0}])
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text(
        json.dumps({
            "last_full_refresh": datetime.now(timezone.utc).isoformat(),
            "price_series": downloads_module._price_regime(),
        }),
        encoding="utf-8",
    )
    (tmp_path / "ticker_admission.json").write_text(
        json.dumps({
            "YNG": {
                "status": "active_young",
                "next_check": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            },
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(scan_job_module, "_cache_paths", lambda *a, **k: (str(tmp_path / "cache.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_job_module, "run_screener", lambda *a, **k: (results, panel, ["AAA", "YNG"], {}))
    monkeypatch.setattr(scan_job_module, "_expected_session_date", lambda: expected)
    monkeypatch.setattr(scan_job_module, "print_results", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scan_job_module, "save_csv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scan_job_module, "print_finviz_url", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scan_job_module, "generate_dashboard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scan_job_module.settings, "ARCHIVE_LIVE_SCANS", True)
    monkeypatch.setattr(scan_job_module, "archive_scan_results", lambda *a, **k: 1)

    result = scan_job_module.run_scan_and_export(mode="cache")

    assert result.n_setups == 1
    assert result.n_archived == 1


def test_canonical_setups_excludes_etf_rows_by_default(tmp_path):
    """Fix ⑤: the archive read surfaces default to universe_type='us_equities', so
    ETF/sector screener rows (same source='screener') no longer pool into the
    equities population. Passing universe_type=None opts back into every universe."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import archive_models
    from services.archive_queries import _canonical_setups

    eng = create_engine(f"sqlite:///{tmp_path / 'arch.db'}")
    archive_models.SetupArchive.__table__.create(bind=eng)
    db = sessionmaker(bind=eng)()

    # Fill every NOT NULL column with a type-appropriate benign placeholder, then
    # override the identity fields the test asserts on.
    required_cols = [c for c in archive_models.SetupArchive.__table__.columns
                     if not c.nullable and not c.primary_key]

    def _placeholder(col):
        try:
            pt = col.type.python_type
        except Exception:
            return "x"
        if pt is bool:
            return False
        if pt is int:
            return 0
        if pt is float:
            return 0.0
        return "x"

    def _row(ticker, universe_type):
        kw = {c.name: _placeholder(c) for c in required_cols}
        kw.update(ticker=ticker, scan_date="2026-06-01", setup_type="LPS",
                  source="screener", universe_type=universe_type)
        return archive_models.SetupArchive(**kw)

    try:
        db.add_all([
            _row("AAA", "us_equities"),
            _row("BBB", "us_equities"),
            _row("GLD", "commodities_etf"),
        ])
        db.commit()

        default_scope = _canonical_setups(db)
        assert {r.ticker for r in default_scope} == {"AAA", "BBB"}  # ETF excluded

        live_screener = _canonical_setups(db, source="screener")
        assert {r.ticker for r in live_screener} == {"AAA", "BBB"}  # still equities-only

        all_universes = _canonical_setups(db, universe_type=None)
        assert {r.ticker for r in all_universes} == {"AAA", "BBB", "GLD"}  # opt-in to all
    finally:
        db.close()
        eng.dispose()


def test_empty_results_on_stale_data_does_not_clobber_dashboard(tmp_path, monkeypatch):
    """Fix ③: an empty result on DEGRADED/stale data must NOT overwrite the live
    dashboard with an empty payload — it raises (reported stale), not a clean
    'matched nothing' ok-day that wipes the prior scan's setups off the screen."""
    expected = "2026-06-25"
    stale_panel = _status_panel(["AAA", "SPY", "QQQ"], "2026-06-20")  # behind expected
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text(  # regime-tagged so the STALE path (not the regime guard) is what raises
        json.dumps({"price_series": downloads_module._price_regime()}), encoding="utf-8"
    )
    dashboard_calls = []
    monkeypatch.setattr(scan_job_module, "_cache_paths", lambda *a, **k: (str(tmp_path / "c.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_job_module, "run_screener", lambda *a, **k: (pd.DataFrame(), stale_panel, ["AAA"], {}))
    monkeypatch.setattr(scan_job_module, "_expected_session_date", lambda: expected)
    monkeypatch.setattr(scan_job_module, "generate_dashboard", lambda *a, **k: dashboard_calls.append(1))
    monkeypatch.setattr(scan_job_module.settings, "ARCHIVE_LIVE_SCANS", True)

    with pytest.raises(scan_job_module.StaleMarketDataError):
        scan_job_module.run_scan_and_export(mode="download")
    assert dashboard_calls == []  # the live artifact was NOT clobbered


def test_empty_results_on_healthy_data_writes_empty_artifact(tmp_path, monkeypatch):
    """A genuine zero-setup day on HEALTHY data still writes the valid empty
    artifact, so the universe reads 'scanned, matched nothing' (not 'never scanned')."""
    expected = "2026-06-25"
    panel = _status_panel(["AAA", "SPY", "QQQ"], expected)
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text(
        json.dumps({"price_series": downloads_module._price_regime()}), encoding="utf-8"
    )
    dashboard_calls = []
    monkeypatch.setattr(scan_job_module, "_cache_paths", lambda *a, **k: (str(tmp_path / "c.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_job_module, "run_screener", lambda *a, **k: (pd.DataFrame(), panel, ["AAA"], {}))
    monkeypatch.setattr(scan_job_module, "_expected_session_date", lambda: expected)
    monkeypatch.setattr(scan_job_module, "generate_dashboard", lambda *a, **k: dashboard_calls.append(1))
    monkeypatch.setattr(scan_job_module.settings, "ARCHIVE_LIVE_SCANS", True)

    result = scan_job_module.run_scan_and_export(mode="download")
    assert result.n_setups == 0
    assert dashboard_calls == [1]  # empty artifact written exactly once


@pytest.mark.parametrize(
    ("stream_name", "expected_args", "expected_trigger", "expected_kind", "output", "expected_setups"),
    [
        (
            "stream_cached_evaluation",
            ["--cached"],
            "manual_evaluation",
            "scan",
            'SCAN_RESULT_JSON:{"n_setups": 7, "n_archived": 7}\n',
            7,
        ),
        (
            "stream_data_download",
            ["--download-only"],
            "manual_download",
            "download",
            'DOWNLOAD_RESULT_JSON:{"n_tickers": 3}\n',
            None,
        ),
    ],
)
def test_manual_job_streams_use_args_kind_and_release_lock(monkeypatch, stream_name,
                                                           expected_args, expected_trigger,
                                                           expected_kind, output,
                                                           expected_setups):
    import services.scan_status as scan_status_mod

    calls = {}

    class FakeStdout:
        def __iter__(self):
            return iter([output])

        def close(self):
            calls["stdout_closed"] = True

    class FakeProcess:
        stdout = FakeStdout()
        returncode = 0

        def wait(self):
            calls["waited"] = True

    def fake_create_process(args=None):
        calls["args"] = args
        return FakeProcess()

    def fake_start_run(trigger, kind="scan"):
        calls["trigger"] = trigger
        calls["kind"] = kind
        return 42

    def fake_finish_run(run_id, status, n_setups=None, error=None):
        calls["finish"] = (run_id, status, n_setups, error)

    monkeypatch.setattr(scan_runner, "_create_process", fake_create_process)
    monkeypatch.setattr(scan_status_mod, "start_run", fake_start_run)
    monkeypatch.setattr(scan_status_mod, "finish_run", fake_finish_run)
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)

    events = list(getattr(scan_runner, stream_name)())

    assert calls["args"] == expected_args
    assert calls["trigger"] == expected_trigger
    assert calls["kind"] == expected_kind
    assert calls["finish"] == (42, "ok", expected_setups, None)
    assert any("[DONE]" in event for event in events)
    assert not scan_runner.SCAN_LOCK.locked()


def test_stream_abort_on_client_disconnect_terminates_child_and_records_aborted(monkeypatch):
    """P1 regression: a browser disconnect closes the SSE generator, raising
    GeneratorExit at the yield — a BaseException the `except Exception` path
    never saw. The stream must terminate the run_screener child BEFORE
    SCAN_LOCK is released (the lock's guarantee is one child at a time) and
    must finish the scan_runs row as 'aborted' instead of leaving it 'running'
    forever."""
    import services.scan_status as scan_status_mod

    calls = {}

    class FakeStdout:
        def __init__(self):
            self._lines = iter(["line one\n", "line two\n", "line three\n"])

        def __iter__(self):
            return self._lines

        def close(self):
            calls["stdout_closed"] = True

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout()
            self.returncode = None
            self._alive = True

        def poll(self):
            return None if self._alive else -15

        def terminate(self):
            calls["terminated"] = True
            self._alive = False
            self.returncode = -15

        def kill(self):
            calls["killed"] = True
            self._alive = False

        def wait(self, timeout=None):
            return self.returncode

    proc = FakeProcess()
    finishes = []
    alerts = []
    monkeypatch.setattr(scan_runner, "_create_process", lambda args=None: proc)
    monkeypatch.setattr(scan_status_mod, "start_run", lambda trigger, kind="scan": 42)
    monkeypatch.setattr(
        scan_status_mod, "finish_run",
        lambda run_id, status, n_setups=None, error=None: finishes.append((run_id, status)),
    )
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: alerts.append(a))

    stream = scan_runner._stream_process("manual")
    assert next(stream).startswith("data: ")  # child spawned, first line streamed
    stream.close()  # browser disconnect -> GeneratorExit at the yield

    assert calls.get("terminated") is True
    assert calls.get("stdout_closed") is True
    assert finishes == [(42, "aborted")]
    assert alerts == []  # a user-initiated abort is not an alertable failure
    assert not scan_runner.SCAN_LOCK.locked()


def test_stream_disconnect_at_final_yield_keeps_recorded_status(monkeypatch):
    """A disconnect while suspended at the trailing [DONE] yield arrives AFTER
    finish_run already recorded the outcome — the abort handler must not
    relabel a completed run 'aborted'."""
    import services.scan_status as scan_status_mod

    class FakeStdout:
        def __iter__(self):
            return iter(['SCAN_RESULT_JSON:{"n_setups": 3}\n'])

        def close(self):
            pass

    class FakeProcess:
        stdout = FakeStdout()
        returncode = 0

        def poll(self):
            return 0  # already exited by the time the abort lands

        def terminate(self):
            raise AssertionError("must not terminate an exited child")

        def wait(self, timeout=None):
            return 0

    finishes = []
    monkeypatch.setattr(scan_runner, "_create_process", lambda args=None: FakeProcess())
    monkeypatch.setattr(scan_status_mod, "start_run", lambda trigger, kind="scan": 42)
    monkeypatch.setattr(
        scan_status_mod, "finish_run",
        lambda run_id, status, n_setups=None, error=None: finishes.append((run_id, status)),
    )
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)

    stream = scan_runner._stream_process("manual")
    for event in stream:
        if "[DONE]" in event:
            break  # generator now suspended at the final yield
    stream.close()  # disconnect lands after the outcome was recorded

    assert finishes == [(42, "ok")]  # not overwritten by 'aborted'
    assert not scan_runner.SCAN_LOCK.locked()


def test_manual_job_stream_releases_lock_when_status_start_fails(monkeypatch):
    import services.scan_status as scan_status_mod

    monkeypatch.setattr(scan_status_mod, "start_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)

    events = list(scan_runner.stream_cached_evaluation())

    assert any("ERROR:" in event and "db down" in event for event in events)
    assert any("[DONE]" in event for event in events)
    assert not scan_runner.SCAN_LOCK.locked()


# ---- health: scan freshness must degrade on every non-productive terminal status ----
def test_scan_freshness_degrades_on_aborted():
    # An SSE-disconnect abort produces no artifact; a fresh 'aborted' run must
    # not read as a healthy scan (regression: integration review of WP-D).
    fresh = datetime.now(timezone.utc).isoformat()
    for status in ("failed", "stale_data", "aborted"):
        ok, _age, detail = health_service._scan_freshness(
            {"status": status, "finished_at": fresh}
        )
        assert ok is False
        assert status in detail


# ---- scan-runner alert decision (fetch-health degradation early warning) ----
def test_alert_decision_failed_and_stale_always_alert():
    assert scan_runner._alert_decision("failed", 5, None, True, True) == "failed"
    assert scan_runner._alert_decision("stale_data", 5, None, True, True) == "stale_data"


def test_alert_decision_zero_results_respects_toggle():
    assert scan_runner._alert_decision("ok", 0, None, True, True) == "zero scan results"
    assert scan_runner._alert_decision("ok", 0, None, False, True) is None


def test_alert_decision_degraded_fetch_is_early_warning():
    unhealthy = {"mode": "incremental", "return_ratio": 0.42, "healthy": False}
    reason = scan_runner._alert_decision("ok", 120, unhealthy, True, True)
    assert reason is not None
    assert "degraded data fetch" in reason and "0.42" in reason


def test_alert_decision_degraded_fetch_toggle_off():
    unhealthy = {"return_ratio": 0.42, "healthy": False}
    assert scan_runner._alert_decision("ok", 120, unhealthy, True, False) is None


def test_alert_decision_healthy_ok_scan_is_silent():
    healthy = {"mode": "incremental", "return_ratio": 0.999, "healthy": True}
    assert scan_runner._alert_decision("ok", 120, healthy, True, True) is None
    assert scan_runner._alert_decision("ok", 120, None, True, True) is None


def test_last_fetch_health_reads_record(tmp_path, monkeypatch):
    (tmp_path / "cache_meta.json").write_text(
        json.dumps({"fetch_health": {"healthy": False, "return_ratio": 0.1}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(scan_runner, "ROOT_DIR", str(tmp_path))
    assert scan_runner._last_fetch_health() == {"healthy": False, "return_ratio": 0.1}


def test_last_fetch_health_missing_or_malformed(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_runner, "ROOT_DIR", str(tmp_path))
    assert scan_runner._last_fetch_health() is None  # no file
    (tmp_path / "cache_meta.json").write_text("{not json", encoding="utf-8")
    assert scan_runner._last_fetch_health() is None  # malformed
    (tmp_path / "cache_meta.json").write_text("null", encoding="utf-8")
    assert scan_runner._last_fetch_health() is None  # valid JSON, not an object


def test_scheduled_run_backfills_forward_returns_even_when_scan_fails(monkeypatch):
    # Regression: a failing scan must NOT skip the forward-return backfill. The
    # backfill matures already-archived rows and is independent of the scan, so a
    # crashing scan can no longer silently starve outcome maturation.
    import services.scan_status as scan_status_mod
    import services.core_settings as core_settings_mod

    calls = {"backfill": 0, "finish_status": None}
    result = SimpleNamespace(output="boom", returncode=1, n_setups=None, n_errored=0)

    monkeypatch.setattr(scan_runner, "_run_scan_process_unlocked", lambda *a, **k: result)
    monkeypatch.setattr(scan_runner, "_result_status", lambda r: "failed")
    monkeypatch.setattr(scan_runner, "_tail_error", lambda out: "scan failed: boom")
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)
    finishes = []

    def fake_start_run(trigger, kind="scan"):
        # scan run -> id 1; the maturation backfill now records its OWN run -> id 2.
        return 1 if kind == "scan" else 2

    def _finish(run_id, status, n_setups=None, error=None):
        finishes.append((run_id, status))

    monkeypatch.setattr(scan_status_mod, "start_run", fake_start_run)
    monkeypatch.setattr(scan_status_mod, "finish_run", _finish)
    monkeypatch.setattr(
        core_settings_mod, "load_core_settings",
        lambda: SimpleNamespace(FORWARD_RETURNS_MIN_AGE_DAYS=5),
    )

    def _backfill(min_age_days=5):
        calls["backfill"] += 1
        return 7

    monkeypatch.setattr(archive_forward_returns, "update_forward_returns", _backfill)

    scan_runner.run_scheduled_scan_and_forward_returns()

    assert calls["backfill"] == 1          # backfill ran despite the failed scan
    assert (1, "failed") in finishes       # scan run still recorded as failed
    assert (2, "ok") in finishes           # maturation recorded as its OWN run (now visible)
    assert not scan_runner.SCAN_LOCK.locked()  # lock released on every path


# ── Read-verdict write path (Surface the Read; council review 2026-08-05 F1) ──
# The concordance corpus is born through this endpoint — every leg of the
# conjunctive guard is asserted distinctly (EC-27), and the closed verdict set
# carries all three EC-19 legs (model CHECK / router assertion / these tests).


def _verdict_db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import database

    eng = create_engine(f"sqlite:///{tmp_path / 'verdicts.db'}")
    database.Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng)()


def _verdict_in(**overrides):
    from routers.archive_schemas import ReadVerdictIn

    base = {"ticker": "AAA", "scan_date": "2026-08-05"}
    base.update(overrides)
    return ReadVerdictIn(**base)


def test_read_verdict_agree_lands_and_get_serves_it(tmp_path):
    from routers.archive_reviews import get_read_verdict, set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        out = set_read_verdict(_verdict_in(verdict="agree", note="rails"), db=db)
        assert out["verdict"] == "agree" and out["note"] == "rails"
        got = get_read_verdict(ticker="AAA", scan_date="2026-08-05",
                               universe_type=None, db=db)
        # grade_verdict serves alongside — the GET's old two-key shape WAS
        # review finding 6 (a stored grade verdict was unreadable).
        assert got == {"verdict": "agree", "grade_verdict": None,
                       "note": "rails"}
    finally:
        db.close()


def test_read_verdict_disagree_overwrites_in_place_one_row(tmp_path):
    from models import ReadVerdict
    from routers.archive_reviews import set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        set_read_verdict(_verdict_in(verdict="agree"), db=db)
        set_read_verdict(_verdict_in(verdict="disagree", note="posture"), db=db)
        rows = db.query(ReadVerdict).all()
        assert len(rows) == 1
        assert rows[0].verdict == "disagree" and rows[0].note == "posture"
    finally:
        db.close()


def test_read_verdict_null_clears_the_row(tmp_path):
    from models import ReadVerdict
    from routers.archive_reviews import set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        set_read_verdict(_verdict_in(verdict="agree"), db=db)
        out = set_read_verdict(_verdict_in(verdict=None), db=db)
        assert out["verdict"] is None
        assert db.query(ReadVerdict).count() == 0
    finally:
        db.close()


def test_read_verdict_empty_string_is_422_never_a_clear(tmp_path):
    """council F7: '' must be a malformed verdict, not the clear sentinel — a
    client bug that sends verdict '' must never silently DELETE a verdict."""
    from fastapi import HTTPException

    from models import ReadVerdict
    from routers.archive_reviews import set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        set_read_verdict(_verdict_in(verdict="agree"), db=db)
        with pytest.raises(HTTPException) as exc:
            set_read_verdict(_verdict_in(verdict=""), db=db)
        assert exc.value.status_code == 422
        assert db.query(ReadVerdict).count() == 1   # the verdict survived
    finally:
        db.close()


def test_read_verdict_unknown_vocabulary_is_422(tmp_path):
    from fastapi import HTTPException

    from routers.archive_reviews import set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        with pytest.raises(HTTPException) as exc:
            set_read_verdict(_verdict_in(verdict="maybe"), db=db)
        assert exc.value.status_code == 422
    finally:
        db.close()


def test_read_verdict_blank_ticker_is_400(tmp_path):
    from fastapi import HTTPException

    from routers.archive_reviews import set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        with pytest.raises(HTTPException) as exc:
            set_read_verdict(_verdict_in(ticker=" ", verdict="agree"), db=db)
        assert exc.value.status_code == 400
    finally:
        db.close()


def test_read_verdict_malformed_identity_refused_at_the_schema():
    """council F7: the write contract is at least as strict as the GET twin —
    a scan_date the read path can't serve is refused at construction."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _verdict_in(scan_date="2026-8-5", verdict="agree")       # not date-shaped
    with pytest.raises(pydantic.ValidationError):
        _verdict_in(scan_date="2026-08-05T18:00", verdict="agree")  # datetime leak
    with pytest.raises(pydantic.ValidationError):
        _verdict_in(ticker="WAYTOOLONGTICKER", verdict="agree")  # > GET's 12-char cap


def test_read_verdict_mixed_case_ticker_normalizes(tmp_path):
    from routers.archive_reviews import get_read_verdict, set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        set_read_verdict(_verdict_in(ticker="aApl", verdict="agree"), db=db)
        got = get_read_verdict(ticker="AAPL", scan_date="2026-08-05",
                               universe_type=None, db=db)
        assert got["verdict"] == "agree"
    finally:
        db.close()


def test_read_verdict_get_serves_nulls_when_absent(tmp_path):
    from routers.archive_reviews import get_read_verdict

    db = _verdict_db(tmp_path)
    try:
        got = get_read_verdict(ticker="AAA", scan_date="2026-08-05",
                               universe_type=None, db=db)
        assert got == {"verdict": None, "grade_verdict": None, "note": None}
    finally:
        db.close()


def test_read_verdict_universe_type_separates_same_day_rows(tmp_path):
    """council F6: the identity is the archive TRIPLE — the same ticker+date in
    two universes must hold two independent verdicts, and the omitted-universe
    default must resolve to the equities scope (EC-1 one source)."""
    from core.pipeline.universe import default_universe_type

    from models import ReadVerdict
    from routers.archive_reviews import get_read_verdict, set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        set_read_verdict(_verdict_in(verdict="agree"), db=db)
        set_read_verdict(_verdict_in(verdict="disagree",
                                     universe_type="us_sectors"), db=db)
        assert db.query(ReadVerdict).count() == 2
        assert get_read_verdict(ticker="AAA", scan_date="2026-08-05",
                                universe_type="us_sectors", db=db)["verdict"] == "disagree"
        # Omitted universe on the read resolves to the same default the write used.
        assert get_read_verdict(ticker="AAA", scan_date="2026-08-05",
                                universe_type=None, db=db)["verdict"] == "agree"
        default_row = (db.query(ReadVerdict)
                       .filter(ReadVerdict.verdict == "agree").one())
        assert default_row.universe_type == default_universe_type()
    finally:
        db.close()


def test_read_verdict_stamps_and_refreshes_engine_config_version(tmp_path):
    """council F6: the verdict carries the evidence version the operator SAW;
    re-recording re-stamps it (the archive row may have been upserted since)."""
    from models import ReadVerdict
    from routers.archive_reviews import set_read_verdict

    db = _verdict_db(tmp_path)
    try:
        set_read_verdict(_verdict_in(verdict="agree",
                                     engine_config_version="cbd7df83"), db=db)
        assert db.query(ReadVerdict).one().engine_config_version == "cbd7df83"
        set_read_verdict(_verdict_in(verdict="disagree",
                                     engine_config_version="deadbeef"), db=db)
        row = db.query(ReadVerdict).one()
        assert row.verdict == "disagree"
        assert row.engine_config_version == "deadbeef"
    finally:
        db.close()


def test_read_verdict_model_check_refuses_illegal_label(tmp_path):
    """EC-19 leg 3: a writer that is NOT the router (seed tool, manual session)
    cannot land an out-of-vocabulary verdict — the model CHECK refuses it."""
    from sqlalchemy.exc import IntegrityError

    from models import ReadVerdict

    db = _verdict_db(tmp_path)
    try:
        db.add(ReadVerdict(ticker="AAA", scan_date="2026-08-05",
                           universe_type="us_equities", verdict="maybe"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
