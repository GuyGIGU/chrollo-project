import json
import sys
from contextlib import nullcontext

import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

import core.pipeline.telemetry.scan_metrics as scan_metrics
import core.pipeline.screening.screener as screener_module
import pytest


@pytest.fixture(autouse=True)
def _no_vendor_post_pass(monkeypatch):
    # These test the conductor with a fake provider. The live fundamentals
    # post-pass (2026-10-03) fetches through the real one, so it stays off here.
    from config import settings
    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", False)


def test_persist_scan_metrics_updates_meta_and_appends_history(tmp_path, monkeypatch):
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text('{"fetch_health": {"healthy": true}}', encoding="utf-8")
    monkeypatch.setattr(scan_metrics, "_cache_paths", lambda *a, **k: (str(tmp_path / "cache.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_metrics, "_project_root", lambda: str(tmp_path))

    metrics = {"total_s": 1.23, "phases_s": {"evaluation": 0.5}, "counts": {"setups": 2}}
    scan_metrics.persist_scan_metrics(metrics)

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["fetch_health"] == {"healthy": True}
    assert meta["scan_metrics"] == metrics
    history = (tmp_path / "output" / "scan_metrics.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(history) == metrics


def test_persist_scan_metrics_routes_to_the_scanned_universe(tmp_path, monkeypatch):
    """Council #11: an ETF scan must write ITS OWN universe's cache_meta, not the
    default US-Stocks one — the per-universe routing the universe arg exists for.
    _cache_paths actually branches on the universe here (the prior test swallowed
    it), so a regression that drops the arg would leave the ETF metrics in the
    default meta and fail this."""
    default_meta = tmp_path / "cache_meta.json"
    etf_meta = tmp_path / "cache_meta_us_sectors.json"

    def fake_cache_paths(universe=None):
        if universe == "us_sectors":
            return (str(tmp_path / "cache_us_sectors.parquet"), str(etf_meta))
        return (str(tmp_path / "cache.parquet"), str(default_meta))

    monkeypatch.setattr(scan_metrics, "_cache_paths", fake_cache_paths)
    monkeypatch.setattr(scan_metrics, "cache_lock", lambda *a, **k: nullcontext())
    monkeypatch.setattr(scan_metrics, "_project_root", lambda: str(tmp_path))

    metrics = {"total_s": 2.0, "phases_s": {}, "counts": {"setups": 1}}
    scan_metrics.persist_scan_metrics(metrics, universe="us_sectors")

    assert json.loads(etf_meta.read_text(encoding="utf-8"))["scan_metrics"] == metrics
    assert not default_meta.exists()  # the US-Stocks meta is untouched


def test_run_screener_records_phase_metrics(monkeypatch, tmp_path):
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=dates),
        },
        axis=1,
    )

    class FakeProvider:
        def fetch(self, tickers, universe=None):
            assert tickers == ["AAA"]
            return panel

    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: FakeProvider())
    monkeypatch.setattr(
        screener_module,
        "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0},
    )
    monkeypatch.setattr(
        screener_module,
        "_evaluate_frames",
        lambda frames, spy, breadth, not_read_sink=None: ([{"Ticker": "AAA", "Score": 10, "_ta_grade": 50.0}], 0),
    )
    saved = {}
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics, universe=None: saved.update(metrics))

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


def test_a_crashing_rs_rating_pass_costs_the_ratings_not_the_scan(monkeypatch):
    import core.regime.scan_context as scan_context

    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    panel = pd.concat(
        {"AAA": pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=dates)},
        axis=1,
    )

    class FakeProvider:
        def fetch(self, tickers, universe=None):
            return panel

    def crash(results, ticker_frames):
        raise RuntimeError("rs pass blew up")

    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: FakeProvider())
    monkeypatch.setattr(
        screener_module,
        "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0},
    )
    monkeypatch.setattr(
        screener_module,
        "_evaluate_frames",
        lambda frames, spy, breadth, not_read_sink=None: ([{"Ticker": "AAA", "Score": 10, "_ta_grade": 50.0}], 0),
    )
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics, universe=None: None)
    monkeypatch.setattr(scan_context, "attach_rs_ratings", crash)

    results_df, _, _, _ = screener_module.run_screener()

    assert list(results_df["Ticker"]) == ["AAA"]


def _one_fire_scan(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    panel = pd.concat(
        {"AAA": pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=dates)},
        axis=1,
    )

    class FakeProvider:
        def fetch(self, tickers, universe=None):
            return panel

    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: FakeProvider())
    monkeypatch.setattr(
        screener_module, "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0})
    monkeypatch.setattr(
        screener_module, "_evaluate_frames",
        lambda frames, spy, breadth, not_read_sink=None: ([{"Ticker": "AAA", "Score": 10, "_ta_grade": 50.0}], 0),
    )
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics, universe=None: None)


def test_the_us_stocks_scan_carries_the_leadership_read(monkeypatch):
    import core.fundamentals.industry as industry
    import core.regime.scan_context as scan_context

    _one_fire_scan(monkeypatch)
    monkeypatch.setattr(scan_context, "attach_rs_ratings",
                        lambda results, frames: {"AAA": 90.0, "BBB": 50.0, "CCC": 10.0})
    monkeypatch.setattr(industry, "load_cache", lambda path: {
        t: {"sector": "Technology", "industry": "Semis"} for t in ("AAA", "BBB", "CCC")})
    _, _, _, market_context = screener_module.run_screener()
    assert market_context["leadership"]["stocks"]["AAA"] == {"group": "Semis", "rs": 90.0, "place": 1, "of": 3}
    assert market_context["leadership"]["groups"]["Semis"]["rank"] == 1


def test_a_crashing_leadership_read_costs_the_read_not_the_scan(monkeypatch):
    import core.regime.leadership as leadership
    import core.regime.scan_context as scan_context

    _one_fire_scan(monkeypatch)
    monkeypatch.setattr(scan_context, "attach_rs_ratings", lambda results, frames: {"AAA": 90.0})

    def crash(ratings, cache):
        raise RuntimeError("leadership blew up")

    monkeypatch.setattr(leadership, "read_leadership", crash)
    results_df, _, _, market_context = screener_module.run_screener()
    assert list(results_df["Ticker"]) == ["AAA"]
    assert "leadership" not in market_context


def test_run_screener_cache_mode_does_not_fetch_provider(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=dates),
        },
        axis=1,
    )

    # Cache mode never fetches PRICES. The market-cap floor (2026-10-03) still
    # asks the provider for the fires' market caps — no price data has that.
    class CapsOnlyProvider:
        def fetch(self, tickers, universe=None):
            raise AssertionError("prices fetched in cache mode")

        def market_cap(self, ticker):
            return 2e9

    monkeypatch.setattr(screener_module, "get_cached_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "_read_cached_market_data", lambda *a, **k: panel)
    monkeypatch.setattr(screener_module, "get_provider", lambda: CapsOnlyProvider())
    monkeypatch.setattr(
        screener_module,
        "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0},
    )
    monkeypatch.setattr(
        screener_module,
        "_evaluate_frames",
        lambda frames, spy, breadth, not_read_sink=None: ([{"Ticker": "AAA", "Score": 10, "_ta_grade": 50.0}], 0),
    )
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics, universe=None: None)

    results_df, data, tickers, market_context = screener_module.run_screener(mode="cache")

    assert tickers == ["AAA"]
    assert data is panel
    assert len(results_df) == 1
    assert market_context["market_cap_floor"]["refused"] == 0
    assert results_df.iloc[0]["_market_cap"] == 2e9


def _scan_with_caps(monkeypatch, caps):
    """run_screener over fires AAA..CCC with a provider that knows ``caps``."""
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    tickers = ["AAA", "BBB", "CCC"]
    panel = pd.concat(
        {t: pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=dates)
         for t in tickers},
        axis=1,
    )

    class Provider:
        def fetch(self, tickers, universe=None):
            return panel

        def market_cap(self, ticker):
            return caps.get(ticker)

    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: tickers)
    monkeypatch.setattr(screener_module, "get_provider", lambda: Provider())
    monkeypatch.setattr(
        screener_module,
        "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0},
    )
    monkeypatch.setattr(
        screener_module,
        "_evaluate_frames",
        lambda frames, spy, breadth, not_read_sink=None: (
            [{"Ticker": t, "Score": 10, "_ta_grade": 50.0} for t in tickers], 0),
    )
    monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics, universe=None: None)
    return screener_module.run_screener()


def test_a_fire_under_the_market_cap_floor_leaves_the_scan(monkeypatch):
    # AAA sits under $300M, BBB above it, CCC's cap cannot be read: a missing
    # number never refuses (the entry gate's own NaN rule).
    results_df, _, _, market_context = _scan_with_caps(
        monkeypatch, {"AAA": 250e6, "BBB": 300e6})
    assert list(results_df["Ticker"]) == ["BBB", "CCC"]
    assert market_context["market_cap_floor"] == {
        "checked": 3, "refused": 1, "unknown": 1, "refused_tickers": ["AAA"]}
    assert results_df.set_index("Ticker")["_market_cap"].get("BBB") == 300e6


def test_the_floor_reads_the_setting(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "MIN_MARKET_CAP", 200e6)
    results_df, _, _, _ = _scan_with_caps(monkeypatch, {"AAA": 250e6, "BBB": 300e6})
    assert list(results_df["Ticker"]) == ["AAA", "BBB", "CCC"]


def test_an_etf_universe_skips_the_floor(monkeypatch):
    from core.pipeline.screening.market_cap_floor import apply_market_cap_floor

    class Untouchable:
        def market_cap(self, ticker):
            raise AssertionError("an ETF universe looked up a market cap")

    results = [{"Ticker": "XLK"}]
    etf_universe = type("U", (), {"ticker_source": "csv"})()
    assert apply_market_cap_floor(results, etf_universe, provider=Untouchable()) is None
    assert results == [{"Ticker": "XLK"}]
