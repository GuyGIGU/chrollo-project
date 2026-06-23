import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from services import live_quotes


def test_fetch_live_quotes_prioritizes_ibkr_then_alpaca_then_yfinance():
    yfinance_called = []

    out = live_quotes.fetch_live_quotes(
        ["aapl", "AAPL", "UNG 22MAY26 12.5 C", "MSFT", "GOOG"],
        ibkr_quote_fn=lambda tickers: {"AAPL": 100.0},
        alpaca_fn=lambda tickers: {"MSFT": 201.0},
        scan_running_fn=lambda: False,
        yfinance_fn=lambda ticker: yfinance_called.append(ticker) or 301.0,
    )

    assert out == {"AAPL": 100.0, "MSFT": 201.0, "GOOG": 301.0}
    assert yfinance_called == ["GOOG"]


def test_fetch_live_quotes_skips_yfinance_when_scan_is_running():
    yfinance_called = []

    out = live_quotes.fetch_live_quotes(
        ["GOOG"],
        ibkr_quote_fn=lambda tickers: {},
        alpaca_fn=lambda tickers: {},
        scan_running_fn=lambda: True,
        yfinance_fn=lambda ticker: yfinance_called.append(ticker) or 301.0,
    )

    assert out == {}
    assert yfinance_called == []


def test_fetch_ibkr_quote_prices_requires_connected_fresh_snapshot(monkeypatch):
    class FakeService:
        def __init__(self, connected=True, stale=False):
            self.connected = connected
            self.stale = stale

        def snapshot(self):
            return {
                "connected": self.connected,
                "stale": self.stale,
                "portfolio": [{"symbol": "MSFT", "market_price": 123.45}],
                "positions": [],
            }

    monkeypatch.setattr(live_quotes, "get_ibkr_service", lambda: FakeService())
    assert live_quotes.fetch_ibkr_quote_prices(["MSFT"]) == {"MSFT": 123.45}

    monkeypatch.setattr(live_quotes, "get_ibkr_service", lambda: FakeService(connected=False))
    assert live_quotes.fetch_ibkr_quote_prices(["MSFT"]) == {}

    monkeypatch.setattr(live_quotes, "get_ibkr_service", lambda: FakeService(stale=True))
    assert live_quotes.fetch_ibkr_quote_prices(["MSFT"]) == {}
