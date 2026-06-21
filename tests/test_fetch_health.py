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
    monkeypatch.setattr(downloads_module, "_cache_paths", lambda: (str(cache_file), str(meta_file)))
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
