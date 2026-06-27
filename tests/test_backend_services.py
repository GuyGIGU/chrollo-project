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
from webapp.backend.services import scan_runner
from core.pipeline import cache_status as cache_status_module
from core.pipeline import scan_job as scan_job_module


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
    cache_file = tmp_path / "market_cache.parquet"
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text(
        json.dumps(meta or {"last_full_refresh": datetime.now(timezone.utc).isoformat()}),
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
    _wire_cache_status(
        tmp_path,
        monkeypatch,
        panel=_status_panel(["AAA", "SPY", "QQQ"], "2026-06-24"),
    )

    status = cache_status_module.build_market_data_status()

    assert status["status"] == "stale_session"
    assert status["can_download"] is True
    assert status["can_evaluate"] is False


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
        json.dumps({"last_full_refresh": datetime.now(timezone.utc).isoformat()}),
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

    monkeypatch.setattr(scan_job_module, "_cache_paths", lambda: (str(tmp_path / "cache.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_job_module, "run_screener", lambda mode="download": (results, panel, ["AAA", "YNG"], {}))
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


def test_manual_job_stream_releases_lock_when_status_start_fails(monkeypatch):
    import services.scan_status as scan_status_mod

    monkeypatch.setattr(scan_status_mod, "start_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)

    events = list(scan_runner.stream_cached_evaluation())

    assert any("ERROR:" in event and "db down" in event for event in events)
    assert any("[DONE]" in event for event in events)
    assert not scan_runner.SCAN_LOCK.locked()


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
