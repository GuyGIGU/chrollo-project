"""Price-series regime (DATA_DIVIDEND_ADJUSTED) — the as-traded cutover contract.

Four invariants:
  1. One flag source: every download's auto_adjust comes from price_auto_adjust().
  2. The cache meta is regime-tagged, and a mismatched meta demands a cold
     refetch (legacy caches without the tag are dividend-adjusted).
  3. As-traded multi-ticker downloads drop yfinance's extra 'Adj Close' field
     so the cache schema stays strictly OHLCV.
  4. The needs_repair path honors the regime guard too: a mismatched cache is
     never patched in place with current-regime bars.
"""
import json
import os

import pandas as pd

from config import settings
from core.pipeline.market_data import downloads as dl
from core.pipeline.market_data import yahoo_download


def test_price_regime_flag_source_and_tags(monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)
    assert dl.price_auto_adjust() is False
    assert dl._price_regime() == "as_traded"

    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", True, raising=False)
    assert dl.price_auto_adjust() is True
    assert dl._price_regime() == "div_adjusted"


def test_regime_mismatch_detects_legacy_and_foreign_caches(monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)
    # A cache written before the tag existed is dividend-adjusted -> mismatch.
    assert dl._meta_regime_mismatch({}) is True
    assert dl._meta_regime_mismatch({"price_series": "div_adjusted"}) is True
    assert dl._meta_regime_mismatch({"price_series": "as_traded"}) is False

    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", True, raising=False)
    assert dl._meta_regime_mismatch({}) is False          # legacy == legacy
    assert dl._meta_regime_mismatch({"price_series": "as_traded"}) is True


def test_download_once_uses_flag_and_drops_adj_close(monkeypatch):
    idx = pd.date_range("2026-01-02", periods=3)
    cols = pd.MultiIndex.from_product(
        [["AAA", "BBB"], ["Open", "High", "Low", "Close", "Adj Close", "Volume"]]
    )
    frame = pd.DataFrame(1.0, index=idx, columns=cols)

    captured = {}

    def fake_download(batch, **params):
        captured.update(params)
        return frame.copy()

    monkeypatch.setattr(yahoo_download.yf, "download", fake_download)
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)

    out = yahoo_download._download_once(["AAA", "BBB"], {"period": "5y"})
    assert captured["auto_adjust"] is False
    assert "Adj Close" not in out.columns.get_level_values(1)
    assert set(out.columns.get_level_values(1)) == {"Open", "High", "Low", "Close", "Volume"}


def test_single_ticker_history_drops_adj_close(monkeypatch):
    # THE production path: _batched_download submits 1-element batches, and the
    # pinned yfinance 1.2.1 emits 'Adj Close' from Ticker().history when
    # auto_adjust=False (even with actions=False). The cache schema must stay
    # strictly OHLCV or repair patches NaN-stripe and eat the latest bar.
    idx = pd.date_range("2026-01-02", periods=3)
    frame = pd.DataFrame(
        1.0, index=idx,
        columns=["Open", "High", "Low", "Close", "Adj Close", "Volume"],
    )

    captured = {}

    class _FakeTicker:
        def __init__(self, symbol):
            captured["symbol"] = symbol

        def history(self, **params):
            captured.update(params)
            return frame.copy()

    monkeypatch.setattr(yahoo_download.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)

    out = yahoo_download._single_ticker_history("AAA", {"period": "5y"})
    assert captured["auto_adjust"] is False
    fields = set(out.columns.get_level_values(1))
    assert "Adj Close" not in fields
    assert fields == {"Open", "High", "Low", "Close", "Volume"}
    assert set(out.columns.get_level_values(0)) == {"AAA"}


def _panel(tickers=("AAA",)):
    idx = pd.date_range("2026-01-02", periods=3)
    cols = pd.MultiIndex.from_product(
        [list(tickers), ["Open", "High", "Low", "Close", "Volume"]]
    )
    return pd.DataFrame(1.0, index=idx, columns=cols)


def test_repair_skips_regime_mismatched_cache(tmp_path, monkeypatch):
    # THE deploy-day scenario: legacy div-adjusted cache (untagged meta) +
    # DATA_DIVIDEND_ADJUSTED=False. A needs_repair tick must NOT patch
    # as-traded latest closes into the div-adjusted parquet — if the follow-up
    # cold refetch comes back unhealthy, that mixed panel would be served to
    # the run's evaluation.
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)

    cache_file = str(tmp_path / "cache.parquet")
    meta_file = str(tmp_path / "cache_meta.json")
    (tmp_path / "cache_meta.json").write_text("{}", encoding="utf-8")

    def _must_not_repair(*args, **kwargs):
        raise AssertionError("mismatched-regime cache was patched in place")

    monkeypatch.setattr(dl, "_repair_latest_session", _must_not_repair)

    data = _panel()
    out = dl.repair_latest_session_cache(
        data, cache_file, meta_file, ["AAA"],
        pd.Timestamp("2026-01-06"), 1.0,
    )

    assert out is data                          # panel returned unchanged
    assert not os.path.exists(cache_file)       # nothing persisted
    assert json.loads((tmp_path / "cache_meta.json").read_text()) == {}


def test_repair_proceeds_when_regime_matches(tmp_path, monkeypatch):
    # Control: with a regime-tagged meta the guard must not block the repair.
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)

    cache_file = str(tmp_path / "cache.parquet")
    meta_file = str(tmp_path / "cache_meta.json")
    (tmp_path / "cache_meta.json").write_text(
        json.dumps({"price_series": "as_traded"}), encoding="utf-8"
    )

    data = _panel()
    repaired = data * 2.0
    monkeypatch.setattr(
        dl, "_repair_latest_session", lambda *args, **kwargs: repaired
    )

    out = dl.repair_latest_session_cache(
        data, cache_file, meta_file, ["AAA"],
        pd.Timestamp("2026-01-06"), 1.0,
    )

    assert out is repaired
    assert os.path.exists(cache_file)           # patched panel persisted
    meta = json.loads((tmp_path / "cache_meta.json").read_text())
    assert meta["price_series"] == "as_traded"
    assert "last_modified" in meta
