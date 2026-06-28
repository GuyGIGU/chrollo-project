"""Offline unit tests for the YahooProvider capability methods (Track C / C1).

These methods wrap yfinance's hang-prone single-symbol surfaces (``.download``,
``.info``, ``.calendar``) behind a hard daemon-thread wall-clock bound. The tests
mock yfinance entirely — they must NEVER touch the network — and assert (a) the
output shaping each web bypass call site depends on and (b) that a simulated hang
falls back promptly to the empty/None default instead of stalling.
"""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402  (resolved via BACKEND_DIR above)
import core.pipeline.providers as providers_module
from core.pipeline.providers import YahooProvider


# ── Fake yfinance plumbing ────────────────────────────────────────────────
def _multiindex_ohlcv(symbol="AAA", n=3):
    """A yfinance-style download frame with a (field, ticker) MultiIndex — the
    exact shape the chart routes flatten before reading single-level columns."""
    idx = pd.date_range("2026-06-01", periods=n, freq="D")
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], [symbol]]
    )
    data = {
        ("Open", symbol): [10.0] * n,
        ("High", symbol): [11.0] * n,
        ("Low", symbol): [9.0] * n,
        ("Close", symbol): [10.5] * n,
        ("Volume", symbol): [1000] * n,
    }
    return pd.DataFrame(data, index=idx)[cols]


class _FakeYF:
    """Minimal stand-in for the ``yfinance`` module, injected via sys.modules."""

    def __init__(self, *, download=None, ticker=None):
        self._download = download or (lambda *a, **k: _multiindex_ohlcv())
        self._ticker = ticker

    def download(self, *args, **kwargs):
        return self._download(*args, **kwargs)

    def Ticker(self, symbol):  # noqa: N802 — mirror yfinance's capitalization
        return self._ticker(symbol)


@pytest.fixture
def fake_yf(monkeypatch):
    def _install(*, download=None, ticker=None):
        fake = _FakeYF(download=download, ticker=ticker)
        monkeypatch.setitem(sys.modules, "yfinance", fake)
        return fake
    return _install


# ── daily_candles ─────────────────────────────────────────────────────────
def test_daily_candles_flattens_multiindex(fake_yf):
    fake_yf(download=lambda *a, **k: _multiindex_ohlcv("AAA"))
    out = YahooProvider().daily_candles("AAA", 180)

    assert not out.empty
    # MultiIndex flattened to single-level fields the chart routes read directly.
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert float(out.iloc[0]["Close"]) == 10.5


def test_daily_candles_period_vs_window_args(fake_yf):
    captured = {}

    def _dl(symbol, **kwargs):
        captured.update(kwargs)
        return _multiindex_ohlcv(symbol)

    fake_yf(download=_dl)
    # Period mode (UI chart panel): period=f"{days}d", auto_adjust=False.
    YahooProvider().daily_candles("AAA", 200)
    assert captured["period"] == "200d"
    assert captured["auto_adjust"] is False
    assert "start" not in captured

    captured.clear()
    # Window mode (archive overlay): start/end + auto_adjust=True.
    YahooProvider().daily_candles(
        "AAA", 0, start="2026-01-01", end="2026-06-01", auto_adjust=True
    )
    assert captured["start"] == "2026-01-01"
    assert captured["end"] == "2026-06-01"
    assert captured["auto_adjust"] is True
    assert "period" not in captured


def test_daily_candles_empty_download_returns_empty_frame(fake_yf):
    fake_yf(download=lambda *a, **k: pd.DataFrame())
    out = YahooProvider().daily_candles("ZZZ", 180)
    assert isinstance(out, pd.DataFrame)
    assert out.empty


def test_daily_candles_hang_returns_empty_promptly(fake_yf, monkeypatch):
    monkeypatch.setattr(providers_module, "_DOWNLOAD_TIMEOUT_S", 0.05)

    def _hang(*a, **k):
        time.sleep(5)
        return _multiindex_ohlcv()

    fake_yf(download=_hang)
    started = time.monotonic()
    out = YahooProvider().daily_candles("AAA", 180)
    elapsed = time.monotonic() - started

    assert out.empty
    assert elapsed < 2.0  # bounded — did not wait for the 5s hang


# ── latest_price ──────────────────────────────────────────────────────────
def _price_ticker_factory(prices):
    def _make(symbol):
        px = prices.get(symbol)
        return SimpleNamespace(
            fast_info={"lastPrice": px},
            info={"currentPrice": px},
        )
    return _make


def test_latest_price_returns_resolved_only(fake_yf):
    fake_yf(ticker=_price_ticker_factory({"AAA": 12.345, "BBB": None}))
    out = YahooProvider().latest_price(["AAA", "BBB", "CCC"])

    assert out == {"AAA": 12.35}  # rounded; BBB(None)/CCC(missing) absent


def test_latest_price_failure_is_absent_not_raised(fake_yf):
    def _make(symbol):
        if symbol == "BAD":
            raise RuntimeError("yahoo blew up")
        return SimpleNamespace(fast_info={"lastPrice": 5.0}, info={})

    fake_yf(ticker=_make)
    out = YahooProvider().latest_price(["GOOD", "BAD"])

    assert out == {"GOOD": 5.0}  # BAD swallowed to absence, never propagated


def test_latest_price_hang_skips_symbol_promptly(fake_yf, monkeypatch):
    monkeypatch.setattr(providers_module, "_INFO_TIMEOUT_S", 0.05)

    class _Hang:
        @property
        def fast_info(self):
            time.sleep(5)
            return {"lastPrice": 1.0}

    fake_yf(ticker=lambda s: _Hang())
    started = time.monotonic()
    out = YahooProvider().latest_price(["AAA"])
    elapsed = time.monotonic() - started

    assert out == {}
    assert elapsed < 2.0


# ── sector ────────────────────────────────────────────────────────────────
def test_sector_returns_raw_label(fake_yf):
    fake_yf(ticker=lambda s: SimpleNamespace(info={"sector": "Technology"}))
    assert YahooProvider().sector("AAA") == "Technology"


def test_sector_missing_returns_none(fake_yf):
    fake_yf(ticker=lambda s: SimpleNamespace(info={}))
    assert YahooProvider().sector("AAA") is None


# ── earnings_date ─────────────────────────────────────────────────────────
def test_earnings_date_from_dict_calendar(fake_yf):
    cal = {"Earnings Date": [pd.Timestamp("2026-08-01")]}
    fake_yf(ticker=lambda s: SimpleNamespace(calendar=cal))
    assert YahooProvider().earnings_date("AAA") == "2026-08-01"


def test_earnings_date_none_calendar(fake_yf):
    fake_yf(ticker=lambda s: SimpleNamespace(calendar=None))
    assert YahooProvider().earnings_date("AAA") is None


def test_earnings_date_failure_is_none(fake_yf):
    def _boom(s):
        raise RuntimeError("calendar fetch failed")

    fake_yf(ticker=_boom)
    assert YahooProvider().earnings_date("AAA") is None


# ── index_context / sector_trend ──────────────────────────────────────────
def _trend_frame(closes, day0="2026-01-01"):
    idx = pd.date_range(day0, periods=len(closes), freq="D")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_index_context_bullish_spy_and_vix(fake_yf):
    # 300 sessions rising; the last bar sits well above its 200-SMA → BULLISH.
    spy = _trend_frame([100.0 + i for i in range(300)])
    vix = _trend_frame([18.0, 19.0, 20.0])

    def _dl(symbol, **k):
        return spy if symbol == "SPY" else vix

    fake_yf(download=_dl)
    ctx = YahooProvider().index_context("2026-09-30")
    assert ctx["spy_trend"] == "BULLISH"
    assert ctx["vix_level"] == 20.0


def test_index_context_hang_returns_neutral_default(fake_yf, monkeypatch):
    monkeypatch.setattr(providers_module, "_DOWNLOAD_TIMEOUT_S", 0.05)

    def _hang(*a, **k):
        time.sleep(5)
        return _trend_frame([1.0])

    fake_yf(download=_hang)
    ctx = YahooProvider().index_context("2026-09-30")
    assert ctx == {"spy_trend": None, "vix_level": None}


def test_sector_trend_bearish_below_sma(fake_yf):
    # 80 sessions falling; last bar below the 50-SMA → BEARISH.
    data = _trend_frame([200.0 - i for i in range(80)])
    fake_yf(download=lambda *a, **k: data)
    assert YahooProvider().sector_trend("XLK", "2026-03-21") == "BEARISH"


def test_sector_trend_empty_returns_none(fake_yf):
    fake_yf(download=lambda *a, **k: pd.DataFrame())
    assert YahooProvider().sector_trend("XLK", "2026-03-21") is None


# ── Provider <-> archive_models twin parity (Track C scaffolding guard) ──────
# providers.index_context / sector_trend / sector were added in Track C as
# line-for-line copies of archive_models.get_market_context / get_sector_trend /
# get_sector_etf. They have no production caller yet, so nothing binds the copy
# to its twin — a Phase-2 reroute through the provider could silently drift the
# archived sector_trend / market_context values. These tests feed BOTH the
# provider method and its archive twin the SAME mocked yfinance and assert
# identical output, pinning the pair together so the reroute is safe. The codebase
# guards exactly this eval-twins hazard elsewhere (test_eval_fold,
# tools/provider_parity.py); this extends it to the as-yet-uncalled copies.
#
# Note: provider.sector(ticker) returns the RAW Yahoo label ('Technology'), while
# archive_models.get_sector_etf(ticker) maps that label to its SPDR ETF ('XLK')
# via _SECTOR_TO_ETF. The twin binding is therefore the mapped value:
# _SECTOR_TO_ETF.get(provider.sector(t)) == archive_models.get_sector_etf(t).
def test_provider_index_context_matches_archive_get_market_context(fake_yf):
    spy = _trend_frame([100.0 + i for i in range(300)])
    vix = _trend_frame([18.0, 19.0, 20.0])

    def _dl(symbol, **k):
        return spy if symbol == "SPY" else vix

    fake_yf(download=_dl)
    as_of = "2026-09-30"
    assert (
        YahooProvider().index_context(as_of)
        == archive_models.get_market_context(as_of)
    )


def test_provider_sector_trend_matches_archive_get_sector_trend(fake_yf):
    # 80 sessions falling → BEARISH; both impls read the same mocked frame.
    data = _trend_frame([200.0 - i for i in range(80)])
    fake_yf(download=lambda *a, **k: data)
    etf, as_of = "XLK", "2026-03-21"
    result = YahooProvider().sector_trend(etf, as_of)
    assert result == archive_models.get_sector_trend(etf, as_of)
    assert result == "BEARISH"  # both agree on a real (non-None) classification


def test_provider_sector_matches_archive_get_sector_etf(fake_yf):
    fake_yf(ticker=lambda s: SimpleNamespace(info={"sector": "Technology"}))
    ticker = "AAA"
    raw_label = YahooProvider().sector(ticker)
    assert raw_label == "Technology"
    # The archive twin maps the same raw label to its SPDR ETF.
    assert (
        archive_models._SECTOR_TO_ETF.get(raw_label)
        == archive_models.get_sector_etf(ticker)
        == "XLK"
    )


def test_provider_sector_unmapped_label_matches_archive_none(fake_yf):
    # A label with no SPDR ETF: provider returns the raw label, the archive twin
    # returns None — and the mapping bridges them identically.
    fake_yf(ticker=lambda s: SimpleNamespace(info={"sector": "Conglomerates"}))
    ticker = "ZZZ"
    raw_label = YahooProvider().sector(ticker)
    assert raw_label == "Conglomerates"
    assert archive_models._SECTOR_TO_ETF.get(raw_label) is None
    assert archive_models.get_sector_etf(ticker) is None
