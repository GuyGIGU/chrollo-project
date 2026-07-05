import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core.pipeline.downloads as downloads_module

from core.pipeline.fetch_health import (
    count_quarantined,
    is_healthy,
    load_quarantine,
    present_tickers,
    record_results,
    save_quarantine,
    split_active,
    summarize,
)

UTC = timezone.utc
NOW = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---- split_active (the filter) ----
def test_split_active_skips_quarantined_in_cooldown():
    store = {
        "DEAD": {"quarantined_until": _iso(NOW + timedelta(days=3))},
        "ALIVE_AGAIN": {"quarantined_until": _iso(NOW - timedelta(days=1))},  # cooldown expired
    }
    active, skipped = split_active(
        ["DEAD", "ALIVE_AGAIN", "FRESH"], store, now=NOW, index_symbols=["SPY"]
    )
    assert skipped == ["DEAD"]
    assert active == ["ALIVE_AGAIN", "FRESH"]


def test_split_active_never_skips_index():
    store = {"SPY": {"quarantined_until": _iso(NOW + timedelta(days=30))}}
    active, skipped = split_active(["SPY", "AAA"], store, now=NOW, index_symbols=["SPY"])
    assert "SPY" in active
    assert skipped == []


def test_split_active_handles_naive_timestamp():
    # A stored timestamp without an offset must not crash the aware comparison.
    store = {"X": {"quarantined_until": datetime(2026, 6, 25, 12, 0).isoformat()}}
    active, skipped = split_active(["X"], store, now=NOW, index_symbols=[])
    assert skipped == ["X"]  # 2026-06-25 (coerced UTC) is still ahead of NOW


# ---- record_results (the recorder) ----
def test_record_results_rehabilitates_returned():
    store = {"AAA": {"empty_streak": 5, "quarantined_until": _iso(NOW + timedelta(days=3))}}
    store, newly = record_results(store, ["AAA"], {"AAA"}, now=NOW)
    assert "AAA" not in store
    assert newly == []


def test_record_results_quarantines_at_threshold():
    store: dict = {}
    store, newly = record_results(store, ["X"], set(), now=NOW, streak_threshold=2, cooldown_days=7)
    assert store["X"]["empty_streak"] == 1 and newly == []  # below threshold
    store, newly = record_results(store, ["X"], set(), now=NOW, streak_threshold=2, cooldown_days=7)
    assert store["X"]["empty_streak"] == 2 and newly == ["X"]  # hits threshold
    assert store["X"]["quarantined_until"]


def test_record_results_requarantine_not_double_counted():
    store = {"X": {"empty_streak": 2, "quarantined_until": _iso(NOW + timedelta(days=1))}}
    store, newly = record_results(store, ["X"], set(), now=NOW, streak_threshold=2)
    assert newly == []  # already quarantined — extended, not newly added
    assert store["X"]["empty_streak"] == 3


# ---- present_tickers ----
def _panel(close_by_ticker: dict) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    frames = {
        t: pd.DataFrame({"Close": c, "Volume": 1.0}, index=idx)
        for t, c in close_by_ticker.items()
    }
    return pd.concat(frames, axis=1)


def test_present_tickers_excludes_all_nan():
    panel = _panel({"GOOD": np.linspace(10, 11, 10), "DEAD": [np.nan] * 10})
    assert present_tickers(panel) == {"GOOD"}


# ---- health helpers ----
def test_is_healthy_ratio_gate():
    assert is_healthy(10, 6, min_healthy_ratio=0.5)
    assert not is_healthy(10, 4, min_healthy_ratio=0.5)
    assert not is_healthy(0, 0, min_healthy_ratio=0.5)


def test_count_quarantined_active_only():
    store = {
        "A": {"quarantined_until": _iso(NOW + timedelta(days=1))},
        "B": {"quarantined_until": _iso(NOW - timedelta(days=1))},  # expired
        "C": {"empty_streak": 1},  # streak but not yet quarantined
    }
    assert count_quarantined(store, now=NOW) == 1


def test_summarize_shape():
    h = summarize("cold", 100, 95, 4, 1, 7, 12.34, now=NOW, min_healthy_ratio=0.5)
    assert h["mode"] == "cold"
    assert h["requested"] == 100 and h["returned"] == 95
    assert h["return_ratio"] == 0.95 and h["healthy"] is True
    assert h["skipped_quarantined"] == 4 and h["newly_quarantined"] == 1
    assert h["quarantined_total"] == 7 and h["duration_s"] == 12.3


# ---- store IO ----
def test_quarantine_store_roundtrip(tmp_path):
    path = str(tmp_path / "q.json")
    assert load_quarantine(path) == {}  # missing file -> {}
    save_quarantine(path, {"X": {"empty_streak": 2}})
    assert load_quarantine(path) == {"X": {"empty_streak": 2}}


# ---- integration: fetch_data wiring (cold path, monkeypatched network) ----
def _wire_cold_path(tmp_path, monkeypatch, full_panel):
    """Point fetch_data at tmp cache/meta and a fake cold refetch returning full_panel."""
    cache_file = tmp_path / "cache.parquet"
    meta_file = tmp_path / "cache_meta.json"
    monkeypatch.setattr(downloads_module, "_cache_paths", lambda *a, **k: (str(cache_file), str(meta_file)))
    monkeypatch.setattr(downloads_module, "_is_market_hours", lambda: False)
    monkeypatch.setattr(downloads_module, "_repair_latest_session", lambda data, *a, **k: data)

    called = {}

    def fake_full_refetch(symbols):
        called["symbols"] = symbols
        return full_panel

    monkeypatch.setattr(downloads_module, "_full_refetch", fake_full_refetch)
    return cache_file, meta_file, called


def _one_bar_panel(tickers_to_close):
    last_bar = downloads_module.latest_completed_session()
    frames = {
        t: pd.DataFrame({"Close": [c], "Volume": [1000]}, index=[last_bar])
        for t, c in tickers_to_close.items()
    }
    return pd.concat(frames, axis=1)


def test_fetch_data_filters_quarantined_and_writes_health(tmp_path, monkeypatch):
    full_panel = _one_bar_panel({"AAA": 10.0, "SPY": 100.0, "QQQ": 120.0})
    cache_file, meta_file, called = _wire_cold_path(tmp_path, monkeypatch, full_panel)

    quar_file = tmp_path / "ticker_quarantine.json"
    quar_file.write_text(
        json.dumps({"DEAD": {"empty_streak": 5,
                             "quarantined_until": (datetime.now(UTC) + timedelta(days=3)).isoformat()}}),
        encoding="utf-8",
    )

    out = downloads_module.fetch_data(["AAA", "DEAD"])

    # DEAD was filtered out before any fetch happened.
    assert "DEAD" not in called["symbols"]
    assert called["symbols"] == ["AAA", "SPY", "QQQ"]
    assert set(out.columns.get_level_values(0)) == {"AAA", "SPY", "QQQ"}

    health = json.loads(meta_file.read_text(encoding="utf-8"))["fetch_health"]
    assert health["mode"] == "cold"
    assert health["requested"] == 1 and health["returned"] == 1  # AAA only (indexes excluded)
    assert health["skipped_quarantined"] == 1
    assert health["quarantined_total"] == 1

    # DEAD is still quarantined (it was never fetched, so never rehabilitated).
    assert "DEAD" in json.loads(quar_file.read_text(encoding="utf-8"))


def test_fetch_data_filters_admission_skips_before_download(tmp_path, monkeypatch):
    full_panel = _one_bar_panel({"AAA": 10.0, "SPY": 100.0, "QQQ": 120.0})
    _, meta_file, called = _wire_cold_path(tmp_path, monkeypatch, full_panel)

    admission_file = tmp_path / "ticker_admission.json"
    admission_file.write_text(
        json.dumps({
            "YOUNG": {
                "status": "active_young",
                "next_check": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
            }
        }),
        encoding="utf-8",
    )

    downloads_module.fetch_data(["AAA", "YOUNG"])

    assert called["symbols"] == ["AAA", "SPY", "QQQ"]
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["ticker_admission"]["skipped"] == 1
    assert meta["ticker_admission"]["skip_counts"] == {"active_young": 1}


def test_fetch_data_accrues_empty_streak_on_healthy_cold_run(tmp_path, monkeypatch):
    # full_panel is missing BBB; relax coverage so the run still reaches the success path.
    full_panel = _one_bar_panel({"AAA": 10.0, "SPY": 100.0, "QQQ": 120.0})
    _wire_cold_path(tmp_path, monkeypatch, full_panel)
    monkeypatch.setattr(downloads_module.settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.4)
    # The 1-of-2 return ratio (BBB absent) must count as healthy for the streak to accrue.
    monkeypatch.setattr(downloads_module.settings, "QUARANTINE_MIN_HEALTHY_RATIO", 0.5)

    downloads_module.fetch_data(["AAA", "BBB"])

    quar = json.loads((tmp_path / "ticker_quarantine.json").read_text(encoding="utf-8"))
    assert quar["BBB"]["empty_streak"] == 1  # absent -> streak started (threshold 2, not yet quarantined)
    assert "AAA" not in quar                  # returned -> kept clean


def test_recover_missing_data_does_not_retry_current_short_history(monkeypatch):
    latest = pd.Timestamp("2026-06-25")
    monkeypatch.setattr(downloads_module, "latest_completed_session", lambda: latest)
    monkeypatch.setattr(downloads_module.settings, "ADMISSION_MIN_HISTORY_BARS", 200)

    panel = pd.concat({
        "YOUNG": pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[latest])
    }, axis=1)
    called = []
    monkeypatch.setattr(
        downloads_module,
        "_download_batch_with_retry",
        lambda batch, period, max_retries=3: called.append(batch) or pd.DataFrame(),
    )

    out = downloads_module._recover_missing_data(panel, ["YOUNG"])

    assert out is panel
    assert called == []


def test_recover_missing_data_can_force_retry_current_short_history(monkeypatch):
    latest = pd.Timestamp("2026-06-25")
    monkeypatch.setattr(downloads_module, "latest_completed_session", lambda: latest)
    monkeypatch.setattr(downloads_module.settings, "ADMISSION_MIN_HISTORY_BARS", 200)

    panel = pd.concat({
        "YOUNG": pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[latest])
    }, axis=1)
    recovered_idx = pd.date_range("2026-06-23", periods=3, freq="B")
    recovered_panel = pd.concat({
        "YOUNG": pd.DataFrame(
            {"Close": [8.0, 9.0, 10.0], "Volume": [900, 950, 1000]},
            index=recovered_idx,
        )
    }, axis=1)
    called = []

    def fake_download(batch, period, max_retries=3):
        called.append((batch, period, max_retries))
        return recovered_panel

    monkeypatch.setattr(downloads_module, "_download_batch_with_retry", fake_download)

    out = downloads_module._recover_missing_data(
        panel, ["YOUNG"], skip_current_short=False, dropout_guard=False
    )

    assert called == [(["YOUNG"], downloads_module.settings.DOWNLOAD_PERIOD, 2)]
    assert out[("YOUNG", "Close")].dropna().tolist() == [8.0, 9.0, 10.0]


def test_incremental_fetch_forces_full_recovery_for_new_listings(monkeypatch):
    dates = pd.to_datetime(["2026-06-24", "2026-06-25"])
    cached_panel = pd.concat(
        {
            symbol: pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[dates[0]])
            for symbol in ["AAA", "SPY", "QQQ"]
        },
        axis=1,
    )
    fresh_panel = pd.concat(
        {
            symbol: pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[dates[-1]])
            for symbol in ["AAA", "YOUNG", "SPY", "QQQ"]
        },
        axis=1,
    )

    monkeypatch.setattr(downloads_module, "latest_completed_session", lambda: dates[-1])
    monkeypatch.setattr(downloads_module.settings, "INCREMENTAL_OVERLAP_BDAYS", 1)
    monkeypatch.setattr(downloads_module, "_batched_download", lambda *_args, **_kwargs: fresh_panel)
    monkeypatch.setattr(downloads_module, "_repair_latest_session", lambda data, *_args: data)
    monkeypatch.setattr(downloads_module, "_detect_splits", lambda *_args, **_kwargs: (False, []))
    calls = []

    def fake_recover(data, tickers, *, skip_current_short=True, dropout_guard=True):
        calls.append((tickers, skip_current_short, dropout_guard))
        return data

    monkeypatch.setattr(downloads_module, "_recover_missing_data", fake_recover)

    out = downloads_module._incremental_fetch(
        cached_panel, ["AAA", "YOUNG", "SPY", "QQQ"], 1
    )

    assert out is not None
    assert calls == [(["YOUNG"], False, False)]


def test_incremental_fetch_forces_full_recovery_for_split_drift(monkeypatch):
    dates = pd.to_datetime(["2026-06-24", "2026-06-25"])
    cached_panel = pd.concat(
        {
            symbol: pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[dates[0]])
            for symbol in ["AAA", "SPLT", "SPY", "QQQ"]
        },
        axis=1,
    )
    fresh_panel = pd.concat(
        {
            symbol: pd.DataFrame({"Close": [11.0], "Volume": [1100]}, index=[dates[-1]])
            for symbol in ["AAA", "SPLT", "SPY", "QQQ"]
        },
        axis=1,
    )

    monkeypatch.setattr(downloads_module, "latest_completed_session", lambda: dates[-1])
    monkeypatch.setattr(downloads_module.settings, "INCREMENTAL_OVERLAP_BDAYS", 1)
    monkeypatch.setattr(downloads_module.settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.7)
    monkeypatch.setattr(downloads_module, "_batched_download", lambda *_args, **_kwargs: fresh_panel)
    monkeypatch.setattr(downloads_module, "_repair_latest_session", lambda data, *_args: data)
    monkeypatch.setattr(downloads_module, "_detect_splits", lambda *_args, **_kwargs: (False, ["SPLT"]))
    calls = []

    def fake_recover(data, tickers, *, skip_current_short=True, dropout_guard=True):
        calls.append((tickers, skip_current_short, dropout_guard))
        return data

    monkeypatch.setattr(downloads_module, "_recover_missing_data", fake_recover)

    out = downloads_module._incremental_fetch(
        cached_panel, ["AAA", "SPLT", "SPY", "QQQ"], 1
    )

    assert out is not None
    assert calls == [(["SPLT"], False, False)]


def test_rate_limit_error_triggers_shared_backoff(monkeypatch):
    idx = pd.date_range("2026-06-01", periods=5, freq="B")
    recovered = pd.DataFrame({"Close": [10, 11, 12, 13, 14], "Volume": 1000}, index=idx)
    calls = []

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, **kwargs):
            calls.append((self.ticker, kwargs))
            if len(calls) == 1:
                raise RuntimeError("YFRateLimitError('Too Many Requests. Rate limited.')")
            return recovered

    noted = []
    monkeypatch.setattr(downloads_module.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(downloads_module.rate_limit, "throttle", lambda n=1: None)
    monkeypatch.setattr(downloads_module.rate_limit, "note_rate_limit", lambda seconds: noted.append(seconds))
    monkeypatch.setattr(downloads_module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(downloads_module.settings, "YAHOO_RATE_LIMIT_BACKOFF_SECONDS", 45.0)

    out = downloads_module._download_batch_with_retry(
        ["AAA"], {"period": "1mo"}, max_retries=2
    )

    assert noted == [45.0]
    assert len(calls) == 2
    assert "AAA" in out


def test_backoff_jitter_stays_within_bounds(monkeypatch):
    """Equal-jitter randomizes the retry wait into [wait*(1-j), wait] so
    concurrently rate-limited workers don't retry in lockstep — but the backoff
    still grows (never collapses below wait*(1-j)), and jitter=0 is exact."""
    # attempt=2 => base wait 2**2 = 4.0 (no rate-limit boost without exc/text).
    monkeypatch.setattr(downloads_module.settings, "YAHOO_BACKOFF_JITTER", 0.5)
    monkeypatch.setattr(downloads_module.random, "uniform", lambda a, b: b)   # max draw
    assert downloads_module._retry_wait_seconds(2) == 4.0
    monkeypatch.setattr(downloads_module.random, "uniform", lambda a, b: a)   # min draw
    assert downloads_module._retry_wait_seconds(2) == 2.0
    monkeypatch.setattr(downloads_module.settings, "YAHOO_BACKOFF_JITTER", 0.0)
    assert downloads_module._retry_wait_seconds(2) == 4.0                     # off = exact


def test_backoff_jitter_preserves_shared_cooldown_value(monkeypatch):
    """The shared cooldown (note_rate_limit) gets the UN-jittered wait, so the
    global 429 backoff window is the full duration even though each worker's own
    retry sleep is jittered shorter."""
    noted = []
    monkeypatch.setattr(downloads_module.rate_limit, "note_rate_limit", lambda s: noted.append(s))
    monkeypatch.setattr(downloads_module.settings, "YAHOO_RATE_LIMIT_BACKOFF_SECONDS", 45.0)
    monkeypatch.setattr(downloads_module.settings, "YAHOO_BACKOFF_JITTER", 0.5)
    monkeypatch.setattr(downloads_module.random, "uniform", lambda a, b: a)   # min jitter
    wait = downloads_module._retry_wait_seconds(1, error_text="Too Many Requests. Rate limited.")
    assert noted == [45.0]        # cooldown = full 45s
    assert wait < 45.0            # this worker's own retry sleep is jittered shorter


def test_no_history_error_does_not_retry(monkeypatch):
    calls = []

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, **kwargs):
            calls.append((self.ticker, kwargs))
            raise RuntimeError("YFPricesMissingError: possibly delisted; no price data found")

    monkeypatch.setattr(downloads_module.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(downloads_module.rate_limit, "throttle", lambda n=1: None)
    monkeypatch.setattr(downloads_module.time, "sleep", lambda seconds: None)

    out = downloads_module._download_batch_with_retry(
        ["DEAD"], {"period": "1mo"}, max_retries=3
    )

    assert out.empty
    assert len(calls) == 1


def test_transient_price_error_can_retry(monkeypatch):
    idx = pd.date_range("2026-06-01", periods=5, freq="B")
    recovered = pd.DataFrame({"Close": [10, 11, 12, 13, 14], "Volume": 1000}, index=idx)
    calls = []

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, **kwargs):
            calls.append((self.ticker, kwargs))
            if len(calls) == 1:
                raise RuntimeError("YFPricesMissingError: (Yahoo status_code = 502)")
            return recovered

    monkeypatch.setattr(downloads_module.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(downloads_module.rate_limit, "throttle", lambda n=1: None)
    monkeypatch.setattr(downloads_module.time, "sleep", lambda seconds: None)

    out = downloads_module._download_batch_with_retry(
        ["AAA"], {"period": "1mo"}, max_retries=2
    )

    assert len(calls) == 2
    assert "AAA" in out
