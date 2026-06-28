import math
import json
from datetime import datetime, timezone
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from config import settings

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.pipeline.cache import _atomic_write_parquet, _write_meta
from core.pipeline.json_safety import to_json_safe
from core.pipeline.market_context import get_market_context
import core.pipeline.downloads as downloads_module
import core.pipeline.market_calendar as market_calendar_module
import core.pipeline.market_context as market_context_module
import core.pipeline.scan_job as scan_job_module
import output.dashboard as dashboard_module
import webapp.backend.routers.prices as prices_module
from webapp.backend.routers.market_data import _clean_symbol, _is_number
from webapp.backend.services.portfolio_snapshot import (
    flatten_summary,
    has_portfolio_data,
    with_cached_snapshot,
)
from webapp.backend.services.scan_runner import _parse_n_setups, _tail_error


def test_cache_writer_optimizes_market_panel_roundtrip(tmp_path):
    idx = pd.date_range("2026-01-01", periods=3, freq="B")
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    cols = pd.MultiIndex.from_product([["AAA", "BBB"], fields])
    data = pd.DataFrame(index=idx, columns=cols, dtype="float64")

    for ticker in ["AAA", "BBB"]:
        data[(ticker, "Open")] = [10.123456, 10.5, 10.7]
        data[(ticker, "High")] = [10.5, 10.8, 11.0]
        data[(ticker, "Low")] = [9.9, 10.2, 10.4]
        data[(ticker, "Close")] = [10.2, 10.6, 10.9]
        data[(ticker, "Adj Close")] = [10.2, 10.6, 10.9]
        data[(ticker, "Volume")] = [1000, None, 1200]

    path = tmp_path / "market_cache.parquet"
    _atomic_write_parquet(data, str(path))
    out = pd.read_parquet(path)

    assert out[("AAA", "Close")].dtype == "float32"
    assert out[("AAA", "Volume")].dtype == "Int64"
    assert abs(float(out[("AAA", "Close")].iloc[0]) - 10.2) < 1e-5
    assert pd.isna(out[("AAA", "Volume")].iloc[1])


def test_json_safe_handles_scan_payload_scalars():
    payload = {
        "chart_data": {
            "RSVR": {
                "lps_tests": [{
                    "window_range_pct_box": np.float32(0.42),
                    "length": np.int64(3),
                    "valid": np.bool_(True),
                    "missing": pd.NA,
                    "when": pd.Timestamp("2026-06-14"),
                }],
                "bad": np.float64(float("nan")),
                "array": np.array([np.float32(1.2), np.inf]),
            },
        },
        ("tuple", "key"): "ok",
    }

    safe = to_json_safe(payload)

    json.dumps(safe, allow_nan=False)
    test = safe["chart_data"]["RSVR"]["lps_tests"][0]
    assert test["window_range_pct_box"] == pytest.approx(0.42)
    assert test["length"] == 3
    assert test["valid"] is True
    assert test["missing"] is None
    assert test["when"] == "2026-06-14T00:00:00"
    assert safe["chart_data"]["RSVR"]["bad"] is None
    assert safe["chart_data"]["RSVR"]["array"][1] is None
    assert safe["['tuple', 'key']"] == "ok"


def test_dashboard_exports_phase_c_and_d_bar_indices(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=10, freq="B", name="Date")
    data = pd.DataFrame({
        "Open": np.linspace(10, 11, len(dates)),
        "High": np.linspace(10.5, 11.5, len(dates)),
        "Low": np.linspace(9.5, 10.5, len(dates)),
        "Close": np.linspace(10.2, 11.2, len(dates)),
        "Volume": np.linspace(1000, 1100, len(dates)),
    }, index=dates)
    results = pd.DataFrame([{
        "Ticker": "AAA",
        "Tier": "A",
        "Score": 100,
        "Setup": "LPS",
        "Current Price": 11.2,
        "_trigger_price": 11.6,
        "_R": 11.5,
        "_S": 9.5,
        "_base_len": 8,
        "_lps_len": 2,
        "_lps_offset": 0,
        "_r_anchor_bar": 2,
        "_s_anchor_bar": 3,
        "_bin_c_event_bar": 7,
        "_bin_c_recovery_bar": 8,
        "_bin_d_start_bar": 6,
        "_lps_swing_type": "clean_downswing",
        "_lps_anchor_bar": 6,
        "_lps_anchor_date": "2026-01-07",
        "_lps_low_bar": 8,
        "_lps_low_date": "2026-01-09",
        "_lps_swing_depth_pct": 0.05,
        "_lps_stretch_box": 0.25,
        "_last_supper_pullback_from_extension_pct": 0.05,
        "_last_supper_source_box_age": 2,
        "_last_supper_reclaim_quality": 0.75,
    }])
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker", lambda *_args: None)

    chart = dashboard_module._extract_chart_data(data, results, ["AAA"])["AAA"]

    assert chart["bin_c_event_bar"] == 7
    assert chart["bin_c_recovery_bar"] == 8
    assert chart["bin_d_start_bar"] == 6
    assert chart["lps_swing_type"] == "clean_downswing"
    assert chart["lps_anchor_bar"] == 6
    assert chart["lps_low_bar"] == 8
    assert chart["lps_swing_depth_pct"] == 0.05
    assert chart["lps_stretch_box"] == 0.25
    assert chart["last_supper_pullback_from_extension_pct"] == 0.05
    assert chart["last_supper_source_box_age"] == 2
    assert chart["last_supper_reclaim_quality"] == 0.75


def test_dashboard_keeps_lps_raw_bars_when_chart_window_is_trimmed(monkeypatch):
    dates = pd.date_range("2025-01-01", periods=30, freq="B", name="Date")
    data = pd.DataFrame({
        "Open": np.linspace(10, 13, len(dates)),
        "High": np.linspace(10.5, 13.5, len(dates)),
        "Low": np.linspace(9.5, 12.5, len(dates)),
        "Close": np.linspace(10.2, 13.2, len(dates)),
        "Volume": np.linspace(1000, 1300, len(dates)),
    }, index=dates)
    results = pd.DataFrame([{
        "Ticker": "AAA",
        "Tier": "A",
        "Score": 100,
        "Setup": "LPS",
        "Current Price": 13.2,
        "_trigger_price": 13.6,
        "_R": 13.5,
        "_S": 9.5,
        "_base_len": 20,
        "_lps_len": 2,
        "_lps_offset": 0,
        "_r_anchor_bar": 24,
        "_s_anchor_bar": 25,
        "_bin_c_event_bar": 26,
        "_bin_c_recovery_bar": 27,
        "_bin_d_start_bar": 25,
        "_lps_anchor_bar": 6,
        "_lps_anchor_date": "2025-01-09",
        "_lps_low_bar": 8,
        "_lps_low_date": "2025-01-13",
    }])
    monkeypatch.setattr(dashboard_module.settings, "DASHBOARD_CHART_DAYS", 10)
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker", lambda *_args: None)

    chart = dashboard_module._extract_chart_data(data, results, ["AAA"])["AAA"]

    assert chart["candles"][0]["time"] == "2025-01-29"
    assert chart["bin_c_event_bar"] == 6
    assert chart["bin_c_recovery_bar"] == 7
    assert chart["bin_d_start_bar"] == 5
    assert chart["lps_anchor_bar"] == 6
    assert chart["lps_anchor_date"] == "2025-01-09"
    assert chart["lps_low_bar"] == 8
    assert chart["lps_low_date"] == "2025-01-13"


def test_meta_writer_sanitizes_scan_context(tmp_path):
    path = tmp_path / "market_context.json"

    _write_meta(str(path), {
        "spy_6m_return": np.float32(0.123),
        "breadth_pct": np.float64(float("nan")),
        "computed_at": pd.Timestamp("2026-06-14T12:00:00"),
    })

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["spy_6m_return"] == pytest.approx(0.123)
    assert written["breadth_pct"] is None
    assert written["computed_at"] == "2026-06-14T12:00:00"


def test_market_context_computes_regime_state(tmp_path, monkeypatch):
    monkeypatch.setattr(
        market_context_module,
        "_market_context_path",
        lambda: str(tmp_path / "market_context.json"),
    )
    monkeypatch.setattr(market_context_module, "_is_market_hours", lambda: False)

    idx = pd.date_range("2025-01-01", periods=220, freq="B")

    def frame(start, step):
        close = pd.Series([start + step * i for i in range(len(idx))], index=idx)
        return pd.DataFrame({
            "Open": close - 0.1,
            "High": close + 0.2,
            "Low": close - 0.2,
            "Close": close,
            "Volume": [1_000_000 + i for i in range(len(idx))],
        }, index=idx)

    panel = pd.concat(
        {"SPY": frame(100, 0.2), "QQQ": frame(120, 0.3)},
        axis=1,
    )
    ticker_frames = {
        "AAA": frame(20, 0.05),
        "BBB": frame(30, 0.04),
        "CCC": frame(40, 0.03),
    }

    context = get_market_context(panel, ticker_frames)
    regime = context["regime"]

    assert context["spy_6m_return"] > 0
    assert context["breadth_pct"] == 1.0
    assert regime["state"] == "UPTREND"
    assert regime["breadth_50_pct"] == 1.0
    assert regime["breadth_200_pct"] == 1.0
    assert regime["indexes"]["SPY"]["above_sma_50"] is True
    assert regime["indexes"]["QQQ"]["sma_50_rising"] is True


def test_market_context_short_history_stays_neutral(tmp_path, monkeypatch):
    monkeypatch.setattr(
        market_context_module,
        "_market_context_path",
        lambda: str(tmp_path / "market_context.json"),
    )
    monkeypatch.setattr(market_context_module, "_is_market_hours", lambda: False)

    idx = pd.date_range("2026-01-01", periods=100, freq="B")
    close = pd.Series([100 + i for i in range(len(idx))], index=idx)
    frame = pd.DataFrame({
        "Open": close - 0.1,
        "High": close + 0.2,
        "Low": close - 0.2,
        "Close": close,
    }, index=idx)
    panel = pd.concat({"SPY": frame, "QQQ": frame}, axis=1)

    context = get_market_context(panel, {"AAA": frame})

    assert context["regime"]["state"] == "NEUTRAL"
    assert context["regime"]["indexes"]["SPY"]["above_sma_200"] is None


def test_market_context_cache_missing_configured_index_recomputes(tmp_path, monkeypatch):
    context_path = tmp_path / "market_context.json"
    monkeypatch.setattr(market_context_module, "_market_context_path", lambda: str(context_path))
    monkeypatch.setattr(market_context_module, "_is_market_hours", lambda: False)

    idx = pd.date_range("2025-01-01", periods=220, freq="B")
    close = pd.Series([100 + i for i in range(len(idx))], index=idx)
    frame = pd.DataFrame({
        "Open": close - 0.1,
        "High": close + 0.2,
        "Low": close - 0.2,
        "Close": close,
        "Volume": [1_000_000 + i for i in range(len(idx))],
    }, index=idx)
    panel = pd.concat({"SPY": frame, "QQQ": frame}, axis=1)
    context_path.write_text(
        json.dumps({
            "spy_6m_return": 0.1,
            "breadth_pct": 1.0,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "spy_last_bar_date": idx[-1].strftime("%Y-%m-%d"),
            "index_last_bar_dates": {
                "SPY": idx[-1].strftime("%Y-%m-%d"),
                "QQQ": idx[-1].strftime("%Y-%m-%d"),
            },
            "regime": {
                "state": "UPTREND",
                "indexes": {"SPY": {"close": 100.0}},
            },
        }),
        encoding="utf-8",
    )

    context = get_market_context(panel, {"AAA": frame})

    assert set(context["regime"]["indexes"]) == {"SPY", "QQQ"}


def test_fetch_data_refetches_current_cache_missing_regime_index(tmp_path, monkeypatch):
    cache_file = tmp_path / "market_cache.parquet"
    meta_file = tmp_path / "cache_meta.json"

    last_bar = downloads_module.latest_completed_session()
    cached_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[last_bar]),
            "SPY": pd.DataFrame({"Close": [100.0], "Volume": [1000]}, index=[last_bar]),
        },
        axis=1,
    )
    full_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[last_bar]),
            "SPY": pd.DataFrame({"Close": [100.0], "Volume": [1000]}, index=[last_bar]),
            "QQQ": pd.DataFrame({"Close": [120.0], "Volume": [1000]}, index=[last_bar]),
        },
        axis=1,
    )
    _atomic_write_parquet(cached_panel, str(cache_file))
    meta_file.write_text(
        f'{{"last_full_refresh": "{datetime.now(timezone.utc).isoformat()}"}}',
        encoding="utf-8",
    )

    called = {}
    monkeypatch.setattr(downloads_module, "_cache_paths", lambda: (str(cache_file), str(meta_file)))
    monkeypatch.setattr(downloads_module, "_is_market_hours", lambda: False)
    monkeypatch.setattr(downloads_module.settings, "TTL_FRESH_HOURS_OFFHOURS", 0)
    def fake_full_refetch(symbols):
        called["symbols"] = symbols
        return full_panel

    monkeypatch.setattr(downloads_module, "_full_refetch", fake_full_refetch)

    out = downloads_module.fetch_data(["AAA"])

    assert called["symbols"] == ["AAA", "SPY", "QQQ"]
    assert set(out.columns.get_level_values(0)) == {"AAA", "SPY", "QQQ"}


def test_expected_session_date_skips_juneteenth_market_holiday():
    now = datetime(2026, 6, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))

    assert scan_job_module._expected_session_date(now) == "2026-06-18"


def test_market_calendar_reports_weekend_and_holiday_closures():
    weekend = datetime(2026, 6, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    thanksgiving = datetime(2026, 11, 26, 12, 0, tzinfo=ZoneInfo("America/New_York"))

    assert market_calendar_module.market_closed_reason(weekend) == "weekend"
    assert market_calendar_module.latest_completed_session(weekend) == pd.Timestamp("2026-06-18")
    assert market_calendar_module.market_closed_reason(thanksgiving) == "holiday"
    assert market_calendar_module.latest_completed_session(thanksgiving) == pd.Timestamp("2026-11-25")


def test_market_calendar_uses_early_close_for_black_friday():
    before_close = datetime(2026, 11, 27, 12, 59, tzinfo=ZoneInfo("America/New_York"))
    after_close = datetime(2026, 11, 27, 13, 1, tzinfo=ZoneInfo("America/New_York"))

    assert market_calendar_module.is_early_close_session("2026-11-27")
    assert market_calendar_module.latest_completed_session(before_close) == pd.Timestamp("2026-11-25")
    assert market_calendar_module.latest_completed_session(after_close) == pd.Timestamp("2026-11-27")
    assert market_calendar_module.session_close_at("2026-11-27").hour == 13


def test_incremental_fetch_replaces_sparse_latest_reference_row(monkeypatch):
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    cached_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0, 11.0], "Volume": [1000, 1000]}, index=dates),
            "SPY": pd.DataFrame({"Close": [100.0, None], "Volume": [1000, None]}, index=dates),
            "QQQ": pd.DataFrame({"Close": [120.0, None], "Volume": [1000, None]}, index=dates),
        },
        axis=1,
    )
    fresh_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[dates[-1]]),
            "SPY": pd.DataFrame({"Close": [101.0], "Volume": [1100]}, index=[dates[-1]]),
            "QQQ": pd.DataFrame({"Close": [121.0], "Volume": [1100]}, index=[dates[-1]]),
        },
        axis=1,
    )

    monkeypatch.setattr(downloads_module, "latest_completed_session", lambda: dates[-1])
    monkeypatch.setattr(downloads_module.settings, "INCREMENTAL_OVERLAP_BDAYS", 1)
    monkeypatch.setattr(downloads_module, "_batched_download", lambda *_args, **_kwargs: fresh_panel)
    monkeypatch.setattr(downloads_module, "_detect_splits", lambda *_args, **_kwargs: (False, []))

    out = downloads_module._incremental_fetch(cached_panel, ["AAA", "SPY", "QQQ"], 1)

    assert out is not None
    assert out.loc[dates[-1], ("SPY", "Close")] == 101.0
    assert out.loc[dates[-1], ("QQQ", "Close")] == 121.0


def test_incremental_fetch_rejects_missing_latest_reference_bar(monkeypatch):
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    cached_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[dates[0]]),
            "SPY": pd.DataFrame({"Close": [100.0], "Volume": [1000]}, index=[dates[0]]),
            "QQQ": pd.DataFrame({"Close": [120.0], "Volume": [1000]}, index=[dates[0]]),
        },
        axis=1,
    )
    fresh_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[dates[-1]]),
            "SPY": pd.DataFrame({"Close": [None], "Volume": [None]}, index=[dates[-1]]),
            "QQQ": pd.DataFrame({"Close": [121.0], "Volume": [1100]}, index=[dates[-1]]),
        },
        axis=1,
    )

    monkeypatch.setattr(downloads_module, "latest_completed_session", lambda: dates[-1])
    monkeypatch.setattr(downloads_module.settings, "INCREMENTAL_OVERLAP_BDAYS", 1)
    monkeypatch.setattr(downloads_module, "_batched_download", lambda *_args, **_kwargs: fresh_panel)
    monkeypatch.setattr(downloads_module, "_repair_latest_session", lambda data, *_args: data)

    out = downloads_module._incremental_fetch(cached_panel, ["AAA", "SPY", "QQQ"], 1)

    assert out is None


def test_incremental_fetch_rejects_low_latest_coverage_with_fresh_indexes(monkeypatch):
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    cached_panel = pd.concat(
        {
            symbol: pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[dates[0]])
            for symbol in ["AAA", "BBB", "CCC", "SPY", "QQQ"]
        },
        axis=1,
    )
    fresh_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[dates[-1]]),
            "SPY": pd.DataFrame({"Close": [101.0], "Volume": [1100]}, index=[dates[-1]]),
            "QQQ": pd.DataFrame({"Close": [121.0], "Volume": [1100]}, index=[dates[-1]]),
        },
        axis=1,
    )

    monkeypatch.setattr(downloads_module, "latest_completed_session", lambda: dates[-1])
    monkeypatch.setattr(downloads_module.settings, "INCREMENTAL_OVERLAP_BDAYS", 1)
    monkeypatch.setattr(downloads_module.settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.8)
    monkeypatch.setattr(downloads_module, "_batched_download", lambda *_args, **_kwargs: fresh_panel)
    monkeypatch.setattr(downloads_module, "_repair_latest_session", lambda data, *_args: data)

    out = downloads_module._incremental_fetch(cached_panel, ["AAA", "BBB", "CCC", "SPY", "QQQ"], 1)

    assert out is None


def test_latest_session_repair_patches_missing_closes_without_dropping_history(monkeypatch):
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    base = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0, None], "Volume": [1000, None]}, index=dates),
            "SPY": pd.DataFrame({"Close": [100.0, 101.0], "Volume": [1000, 1100]}, index=dates),
        },
        axis=1,
    )
    patch = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[dates[-1]]),
        },
        axis=1,
    )

    monkeypatch.setattr(downloads_module.settings, "INCREMENTAL_OVERLAP_BDAYS", 1)
    monkeypatch.setattr(downloads_module.settings, "LATEST_REPAIR_BATCH_SIZE", 10)
    monkeypatch.setattr(downloads_module.settings, "LATEST_REPAIR_SLEEP_SECONDS", 0)
    monkeypatch.setattr(downloads_module, "_download_batch_with_retry_kwargs", lambda *_args, **_kwargs: patch)

    out = downloads_module._repair_latest_session(
        base,
        ["AAA", "SPY"],
        dates[-1],
        1.0,
        "test",
    )

    assert out.loc[dates[0], ("AAA", "Close")] == 10.0
    assert out.loc[dates[-1], ("AAA", "Close")] == 11.0
    assert out.loc[dates[-1], ("SPY", "Close")] == 101.0


def test_patch_market_data_tolerates_duplicate_base_columns():
    # Regression: the incremental merge upstream can leave a duplicate
    # (ticker, field) column in ``base``. Before the dedupe fix ``merged[col]``
    # returned a DataFrame and ``Series.combine_first(DataFrame)`` crashed with
    # "'DataFrame' object has no attribute 'dtype'", failing the scheduled scan
    # — and silently starving the forward-return backfill chained after it.
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    base = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0, None], "Volume": [1000, None]}, index=dates),
            "SPY": pd.DataFrame({"Close": [100.0, 101.0], "Volume": [1000, 1100]}, index=dates),
        },
        axis=1,
    )
    # Inject the duplicate (AAA, Close) column that triggers the crash.
    base = pd.concat([base, base[[("AAA", "Close")]]], axis=1)
    assert base.columns.duplicated().any()  # precondition: corrupted base

    patch = pd.concat(
        {"AAA": pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[dates[-1]])},
        axis=1,
    )

    out = downloads_module._patch_market_data(base, patch)

    assert not out.columns.duplicated().any()            # dedupe happened
    assert out.loc[dates[0], ("AAA", "Close")] == 10.0   # history preserved
    assert out.loc[dates[-1], ("AAA", "Close")] == 11.0  # latest patched in
    assert out.loc[dates[-1], ("SPY", "Close")] == 101.0


def test_archive_freshness_rejects_low_latest_coverage(monkeypatch):
    day = pd.Timestamp("2026-06-18")
    panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[day]),
            "BBB": pd.DataFrame({"Close": [None], "Volume": [None]}, index=[day]),
            "SPY": pd.DataFrame({"Close": [101.0], "Volume": [1100]}, index=[day]),
            "QQQ": pd.DataFrame({"Close": [121.0], "Volume": [1100]}, index=[day]),
        },
        axis=1,
    )

    monkeypatch.setattr(scan_job_module, "_expected_session_date", lambda: "2026-06-18")
    monkeypatch.setattr(scan_job_module.settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.8)

    with pytest.raises(scan_job_module.StaleMarketDataError, match="eligible coverage 3/4"):
        scan_job_module._assert_fresh_for_archive(panel, ["AAA", "BBB"])


def test_parse_n_setups_reads_json_before_stale_traceback():
    output = "\n".join([
        "Aborting archive write: stale market data: latest-session close coverage 3/4",
        'SCAN_RESULT_JSON:{"n_setups": 140, "n_archived": 0}',
        "Traceback (most recent call last):",
        "core.pipeline.scan_job.StaleMarketDataError: stale market data",
    ])

    assert _parse_n_setups(output) == 140


def test_scan_tail_error_prefers_stale_market_data_line():
    output = "\n".join([
        "Extracted 46 interactive chart models for React dashboard...",
        "Data exported to: output/screener_data.json",
        "Aborting archive write: stale market data: last bar 2026-06-17, expected >= 2026-06-18",
        "Traceback (most recent call last):",
        "  File \"run_screener.py\", line 36, in <module>",
    ])

    assert _tail_error(output) == (
        "Aborting archive write: stale market data: last bar 2026-06-17, expected >= 2026-06-18"
    )


def test_live_prices_ignores_option_contract_symbol(monkeypatch):
    called = []
    monkeypatch.setattr(prices_module.alpaca_prices, "fetch_quotes", lambda tickers: {})
    monkeypatch.setattr(prices_module, "_scan_is_running", lambda: False)
    monkeypatch.setattr(prices_module, "_fetch_yfinance_price", lambda ticker: called.append(ticker) or 1.0)

    out = prices_module.get_live_prices("JAZZ,UNG 22MAY26 12.5 C")

    assert out == {"JAZZ": 1.0}
    assert called == ["JAZZ"]


def test_live_prices_skips_yfinance_fallback_while_scan_running(monkeypatch):
    called = []
    monkeypatch.setattr(prices_module.alpaca_prices, "fetch_quotes", lambda tickers: {})
    monkeypatch.setattr(prices_module, "_scan_is_running", lambda: True)
    monkeypatch.setattr(prices_module, "_fetch_yfinance_price", lambda ticker: called.append(ticker) or 1.0)

    out = prices_module.get_live_prices("JAZZ")

    assert out == {}
    assert called == []


def test_fetch_yfinance_price_unwraps_provider_result(monkeypatch):
    # C3: the per-symbol fallback now reads through the provider's bounded
    # latest_price and unwraps the single symbol. get_provider is imported
    # lazily inside the function, so patch it at its source module.
    from types import SimpleNamespace

    import core.pipeline.providers as providers_module

    monkeypatch.setattr(
        providers_module,
        "get_provider",
        lambda *a, **k: SimpleNamespace(latest_price=lambda syms: {syms[0]: 12.34}),
    )
    assert prices_module._fetch_yfinance_price("AAA") == 12.34


def test_fetch_yfinance_price_absent_symbol_is_none(monkeypatch):
    from types import SimpleNamespace

    import core.pipeline.providers as providers_module

    monkeypatch.setattr(
        providers_module,
        "get_provider",
        lambda *a, **k: SimpleNamespace(latest_price=lambda syms: {}),
    )
    assert prices_module._fetch_yfinance_price("AAA") is None


def test_fetch_yfinance_price_cannot_stall_on_yahoo_hang(monkeypatch):
    # C3 hazard proof: a hung yfinance .fast_info must NOT block the open-position
    # poll. The provider's daemon-thread timeout bounds the call, so the request
    # path returns None promptly instead of stalling the one worker thread.
    import time

    import core.pipeline.providers as providers_module

    monkeypatch.setattr(providers_module, "_INFO_TIMEOUT_S", 0.05)

    class _Hang:
        @property
        def fast_info(self):
            time.sleep(5)  # simulate Yahoo wedging on the untimed scrape
            return {"lastPrice": 1.0}

    class _FakeYF:
        def Ticker(self, symbol):  # noqa: N802
            return _Hang()

    monkeypatch.setitem(sys.modules, "yfinance", _FakeYF())
    # Real provider path (no get_provider patch) so the bound is actually exercised.

    started = time.monotonic()
    price = prices_module._fetch_yfinance_price("AAA")
    elapsed = time.monotonic() - started

    assert price is None
    assert elapsed < 2.0  # bounded — did not wait for the 5s hang


def test_dashboard_sector_cache_resolves_missing_ticker(tmp_path, monkeypatch):
    cache_path = tmp_path / "sector_etf_cache.json"
    monkeypatch.setattr(dashboard_module, "SECTOR_ETF_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(dashboard_module, "_resolve_sector_etf", lambda ticker: "XLI")

    cache = dashboard_module._load_sector_etf_cache()
    sector = dashboard_module._sector_etf_for_ticker("wcc", cache)
    persisted = json.loads(cache_path.read_text(encoding="utf-8"))

    assert sector == "XLI"
    assert persisted == {"WCC": "XLI"}


def test_flatten_summary_sums_numeric_values_and_ignores_unknown_tags():
    summary = {
        "DU1": {
            "NetLiquidation": {"value": "1000.50", "currency": "USD"},
            "AvailableFunds": {"value": "250", "currency": "USD"},
            "Ignored": {"value": "999", "currency": "USD"},
        },
        "DU2": {
            "NetLiquidation": {"value": "99.50", "currency": "USD"},
            "AvailableFunds": {"value": "not-ready", "currency": "USD"},
        },
    }

    flattened = flatten_summary(summary)

    assert flattened["values"]["NetLiquidation"] == 1100
    assert flattened["values"]["AvailableFunds"] == 250
    assert "Ignored" not in flattened["values"]
    assert flattened["currency"]["NetLiquidation"] == "USD"
    assert flattened["raw"] == summary


def test_cached_portfolio_snapshot_preserves_last_known_data():
    current = {
        "connected": False,
        "mode": "paper",
        "stale": True,
        "last_update": 200,
        "account_summary": {"values": {}, "currency": {}, "raw": {}},
        "positions": [],
        "open_orders": [],
        "recent_executions": [],
    }
    cached = {
        "last_update": 100,
        "account_summary": {"values": {"NetLiquidation": 1234}, "currency": {}, "raw": {}},
        "positions": [{"symbol": "AAPL"}],
        "open_orders": [{"symbol": "MSFT"}],
        "recent_executions": [{"symbol": "NVDA"}],
    }

    snapshot = with_cached_snapshot(current, cached)

    assert has_portfolio_data(snapshot)
    assert snapshot["backend_cached"] is True
    assert snapshot["last_update"] == 100
    assert snapshot["positions"] == cached["positions"]


@pytest.mark.parametrize(
    ("raw_symbol", "clean_symbol"),
    [("pep", "PEP"), (" brk.b ", "BRK.B"), ("abc-1", "ABC-1")],
)
def test_clean_symbol_accepts_supported_ticker_shapes(raw_symbol, clean_symbol):
    assert _clean_symbol(raw_symbol) == clean_symbol


@pytest.mark.parametrize("raw_symbol", ["", "../secrets", "AAPL$", "TOO-LONG-SYMBOL-123"])
def test_clean_symbol_rejects_unsafe_values(raw_symbol):
    with pytest.raises(HTTPException):
        _clean_symbol(raw_symbol)


@pytest.mark.parametrize("value", [0, "12.5", 7.0])
def test_is_number_accepts_finite_numeric_values(value):
    assert _is_number(value)


@pytest.mark.parametrize("value", [None, "nope", math.inf, math.nan])
def test_is_number_rejects_non_finite_values(value):
    assert not _is_number(value)
