"""Price-series regime (DATA_DIVIDEND_ADJUSTED) — the as-traded cutover contract.

Three invariants:
  1. One flag source: every download's auto_adjust comes from price_auto_adjust().
  2. The cache meta is regime-tagged, and a mismatched meta demands a cold
     refetch (legacy caches without the tag are dividend-adjusted).
  3. As-traded multi-ticker downloads drop yfinance's extra 'Adj Close' field
     so the cache schema stays strictly OHLCV.
"""
import pandas as pd

from config import settings
from core.pipeline import downloads as dl


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

    monkeypatch.setattr(dl.yf, "download", fake_download)
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)

    out = dl._download_once(["AAA", "BBB"], {"period": "5y"})
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

    monkeypatch.setattr(dl.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)

    out = dl._single_ticker_history("AAA", {"period": "5y"})
    assert captured["auto_adjust"] is False
    fields = set(out.columns.get_level_values(1))
    assert "Adj Close" not in fields
    assert fields == {"Open", "High", "Low", "Close", "Volume"}
    assert set(out.columns.get_level_values(0)) == {"AAA"}
