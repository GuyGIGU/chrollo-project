import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core.pipeline.scan_metrics as scan_metrics
import core.pipeline.screener as screener_module


def test_persist_scan_metrics_updates_meta_and_appends_history(tmp_path, monkeypatch):
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text('{"fetch_health": {"healthy": true}}', encoding="utf-8")
    monkeypatch.setattr(scan_metrics, "_cache_paths", lambda: (str(tmp_path / "cache.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_metrics, "_project_root", lambda: str(tmp_path))

    metrics = {"total_s": 1.23, "phases_s": {"evaluation": 0.5}, "counts": {"setups": 2}}
    scan_metrics.persist_scan_metrics(metrics)

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["fetch_health"] == {"healthy": True}
    assert meta["scan_metrics"] == metrics
    history = (tmp_path / "output" / "scan_metrics.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(history) == metrics


def test_run_screener_records_phase_metrics(monkeypatch, tmp_path):
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=dates),
        },
        axis=1,
    )

    class FakeProvider:
        def fetch(self, tickers):
            assert tickers == ["AAA"]
            return panel

    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: FakeProvider())
    monkeypatch.setattr(
        screener_module,
        "get_market_context",
        lambda data, frames: {"spy_6m_return": 0.0, "breadth_pct": 1.0},
    )
    monkeypatch.setattr(
        screener_module,
        "_evaluate_frames",
        lambda frames, spy, breadth: [{"Ticker": "AAA", "Score": 10}],
    )
    saved = {}
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics: saved.update(metrics))

    results_df, _, tickers, market_context = screener_module.run_screener()

    assert tickers == ["AAA"]
    assert len(results_df) == 1
    metrics = market_context["_scan_metrics"]
    assert saved == metrics
    assert metrics["counts"] == {
        "universe_tickers": 1,
        "evaluated_tickers": 1,
        "setups": 1,
    }
    for phase in ("ticker_universe", "market_data_fetch", "frame_prep", "market_context", "evaluation"):
        assert phase in metrics["phases_s"]


def test_run_screener_cache_mode_does_not_fetch_provider(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=dates),
        },
        axis=1,
    )

    monkeypatch.setattr(screener_module, "get_cached_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "_read_cached_market_data", lambda *a, **k: panel)
    monkeypatch.setattr(
        screener_module,
        "get_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider fetched")),
    )
    monkeypatch.setattr(
        screener_module,
        "get_market_context",
        lambda data, frames: {"spy_6m_return": 0.0, "breadth_pct": 1.0},
    )
    monkeypatch.setattr(
        screener_module,
        "_evaluate_frames",
        lambda frames, spy, breadth: [{"Ticker": "AAA", "Score": 10}],
    )
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics: None)

    results_df, data, tickers, _ = screener_module.run_screener(mode="cache")

    assert tickers == ["AAA"]
    assert data is panel
    assert len(results_df) == 1
