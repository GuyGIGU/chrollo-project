import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.routers.position_calculator import calculate_position
from webapp.backend.routers import portfolio, portfolio_streams
from webapp.backend.routers.archive_schemas import SetupOut
from core.archive import forward_returns as archive_forward_returns
from core.archive import writer as archive_writer
import archive_models
from webapp.backend.services.journal_stats import calculate_journal_stats
from webapp.backend.services import portfolio_snapshot, screener_data, startup
from webapp.backend.services import scan_runner


def trade(pnl, entry_price=10, stop_loss=9, quantity=100):
    return SimpleNamespace(
        pnl=pnl,
        entry_price=entry_price,
        stop_loss=stop_loss,
        quantity=quantity,
    )


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


def test_portfolio_stream_listens_to_snapshot_changing_channels():
    assert portfolio_streams._PORTFOLIO_CHANNELS == (
        "portfolio",
        "ibkr_status",
        "orders",
        "executions",
    )


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
    result = SimpleNamespace(output="boom", returncode=1, n_setups=None)

    monkeypatch.setattr(scan_runner, "_run_scan_process_unlocked", lambda: result)
    monkeypatch.setattr(scan_runner, "_result_status", lambda r: "failed")
    monkeypatch.setattr(scan_runner, "_tail_error", lambda out: "scan failed: boom")
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)
    monkeypatch.setattr(scan_status_mod, "start_run", lambda trigger: 1)

    def _finish(run_id, status, n_setups=None, error=None):
        calls["finish_status"] = status

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

    assert calls["backfill"] == 1              # backfill ran despite the failed scan
    assert calls["finish_status"] == "failed"  # scan run still recorded as failed
    assert not scan_runner.SCAN_LOCK.locked()  # lock released on every path
