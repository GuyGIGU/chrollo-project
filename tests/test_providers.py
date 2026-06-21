import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
import core.pipeline.providers as providers_module
from core.pipeline.providers import (
    MarketDataProvider,
    YahooProvider,
    available_providers,
    get_provider,
)


def test_default_provider_is_yahoo(monkeypatch):
    # No explicit name + default setting → the incumbent.
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "yahoo", raising=False)
    provider = get_provider()
    assert isinstance(provider, YahooProvider)
    assert provider.name == "yahoo"


def test_explicit_name_overrides_setting(monkeypatch):
    # Explicit arg wins over the configured default.
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "does-not-exist", raising=False)
    assert isinstance(get_provider("yahoo"), YahooProvider)


def test_name_is_case_insensitive():
    assert isinstance(get_provider("YAHOO"), YahooProvider)


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown market-data provider"):
        get_provider("polygon")


def test_unknown_setting_falls_through_to_error(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "bogus", raising=False)
    with pytest.raises(ValueError):
        get_provider()


def test_available_providers_lists_yahoo():
    assert "yahoo" in available_providers()


def test_yahoo_provider_delegates_to_fetch_data(monkeypatch):
    # YahooProvider.fetch must be a pure pass-through to the incumbent fetch_data,
    # so moving the screener behind the interface is a behavioral no-op.
    captured = {}

    def fake_fetch_data(tickers):
        captured["tickers"] = tickers
        return "PANEL"

    import core.pipeline.downloads as downloads_module
    monkeypatch.setattr(downloads_module, "fetch_data", fake_fetch_data)

    out = YahooProvider().fetch(["AAA", "BBB"])
    assert out == "PANEL"
    assert captured["tickers"] == ["AAA", "BBB"]


def test_yahoo_provider_satisfies_protocol():
    # Structural-typing sanity: the concrete provider matches the contract.
    provider: MarketDataProvider = YahooProvider()
    assert hasattr(provider, "name") and callable(provider.fetch)
