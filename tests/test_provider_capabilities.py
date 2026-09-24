"""Offline unit tests for the YahooProvider capability methods (Track C / C1).

These methods wrap yfinance's hang-prone single-symbol surfaces (``.download``,
``.info``, ``.calendar``) behind a hard daemon-thread wall-clock bound. The tests
mock yfinance entirely — they must NEVER touch the network — and assert (a) the
output shaping each web bypass call site depends on and (b) that a simulated hang
falls back promptly to the empty/None default instead of stalling.
"""
import sys
import threading
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
import core.pipeline.market_data.providers as providers_module
from core.pipeline.market_data.providers import YahooProvider


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


def _single_level_ohlcv(symbol="AAA", n=3, close=10.5, tz=None):
    """A yfinance ``Ticker.history`` frame: single-level OHLCV columns — the exact
    shape ``daily_candles`` hands the chart / regime readers."""
    idx = pd.date_range("2026-06-01", periods=n, freq="D", tz=tz)
    return pd.DataFrame(
        {"Open": [10.0] * n, "High": [11.0] * n, "Low": [9.0] * n,
         "Close": [close] * n, "Volume": [1000] * n},
        index=idx,
    )


def _history_ticker(history_fn):
    """Wrap a ``history(symbol, **kwargs)`` callable as a fake ``yf.Ticker``
    factory, so each symbol gets its OWN instance (mirroring the real
    per-instance result store that makes ``Ticker.history`` thread-safe)."""
    def _factory(symbol):
        return SimpleNamespace(history=lambda **kwargs: history_fn(symbol, **kwargs))
    return _factory


# ── daily_candles ─────────────────────────────────────────────────────────
# daily_candles fetches via ``yf.Ticker(symbol).history`` (NOT ``yf.download``):
# download stashes each call's result in module-level globals that collide under
# FastAPI's threadpool, returning one symbol's candles under another's label.
def test_daily_candles_returns_single_level_ohlcv(fake_yf):
    fake_yf(ticker=_history_ticker(lambda s, **k: _single_level_ohlcv(s)))
    out = YahooProvider().daily_candles("AAA", 180)

    assert not out.empty
    # Single-level fields the chart / regime readers index directly.
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert float(out.iloc[0]["Close"]) == 10.5


def test_daily_candles_flattens_history_multiindex(fake_yf):
    # Defensive: if a yfinance version returns a (ticker, field) MultiIndex from
    # history, daily_candles flattens to the inner field level.
    def _hist(symbol, **kwargs):
        idx = pd.date_range("2026-06-01", periods=3, freq="D")
        cols = pd.MultiIndex.from_product(
            [[symbol], ["Open", "High", "Low", "Close", "Volume"]]
        )
        data = {
            (symbol, "Open"): [10.0] * 3, (symbol, "High"): [11.0] * 3,
            (symbol, "Low"): [9.0] * 3, (symbol, "Close"): [10.5] * 3,
            (symbol, "Volume"): [1000] * 3,
        }
        return pd.DataFrame(data, index=idx)[cols]

    fake_yf(ticker=_history_ticker(_hist))
    out = YahooProvider().daily_candles("AAA", 180)
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert float(out.iloc[0]["Close"]) == 10.5


def test_daily_candles_period_vs_window_args(fake_yf):
    captured = {}

    def _hist(symbol, **kwargs):
        captured.clear()
        captured.update(kwargs)
        return _single_level_ohlcv(symbol)

    fake_yf(ticker=_history_ticker(_hist))
    # Period mode (UI chart panel): period=f"{days}d", interval/auto_adjust/actions.
    YahooProvider().daily_candles("AAA", 200)
    assert captured["period"] == "200d"
    assert captured["interval"] == "1d"
    assert captured["auto_adjust"] is False
    assert captured["actions"] is False
    assert "start" not in captured

    # Window mode (archive overlay): start/end + auto_adjust=True.
    YahooProvider().daily_candles(
        "AAA", 0, start="2026-01-01", end="2026-06-01", auto_adjust=True
    )
    assert captured["start"] == "2026-01-01"
    assert captured["end"] == "2026-06-01"
    assert captured["auto_adjust"] is True
    assert captured["actions"] is False
    assert "period" not in captured


def test_daily_candles_empty_returns_empty_frame(fake_yf):
    fake_yf(ticker=_history_ticker(lambda s, **k: pd.DataFrame()))
    out = YahooProvider().daily_candles("ZZZ", 180)
    assert isinstance(out, pd.DataFrame)
    assert out.empty


def test_daily_candles_index_is_tz_naive(fake_yf):
    # history() localizes the daily index to the exchange tz; daily_candles must
    # return a tz-naive index so the archive overlay's tz-naive date comparisons
    # (_adjustment_ratio / forward_bars) don't raise TypeError.
    fake_yf(ticker=_history_ticker(
        lambda s, **k: _single_level_ohlcv(s, tz="America/New_York")
    ))
    out = YahooProvider().daily_candles("AAA", 180)
    assert out.index.tz is None
    assert out.index[0].strftime("%Y-%m-%d") == "2026-06-01"


def test_daily_candles_hang_returns_empty_promptly(fake_yf, monkeypatch):
    monkeypatch.setattr(providers_module, "_DOWNLOAD_TIMEOUT_S", 0.05)

    def _hang(symbol, **kwargs):
        time.sleep(5)
        return _single_level_ohlcv(symbol)

    fake_yf(ticker=_history_ticker(_hang))
    started = time.monotonic()
    out = YahooProvider().daily_candles("AAA", 180)
    elapsed = time.monotonic() - started

    assert out.empty
    assert elapsed < 2.0  # bounded — did not wait for the 5s hang


def test_daily_candles_concurrent_distinct_symbols(fake_yf):
    """Regression for the candle cross-contamination bug: several daily_candles
    calls fired CONCURRENTLY for distinct symbols must EACH return their own last
    close, never a shared one.

    A barrier forces every call to be in-flight at once — the exact condition
    under which ``yf.download``'s module-level result store collided and every
    caller got whichever symbol finished last. Routing through per-symbol
    ``Ticker.history`` keeps each call isolated. ``download`` is wired to raise so
    a regression back to it fails this test loudly rather than silently passing.
    """
    closes = {"SPY": 600.12, "QQQ": 706.52, "IWM": 220.34, "DIA": 430.01}
    symbols = list(closes)
    barrier = threading.Barrier(len(symbols))

    def _hist(symbol, **kwargs):
        frame = _single_level_ohlcv(symbol, close=closes[symbol])
        # Hold every concurrent call here until all have built their OWN frame; a
        # shared-state impl would clobber across this window, instance-local data
        # cannot.
        try:
            barrier.wait(timeout=5)
        except threading.BrokenBarrierError:
            pass
        return frame

    def _fail_download(*a, **k):
        raise AssertionError("daily_candles must not use yf.download (shared-global race)")

    fake_yf(ticker=_history_ticker(_hist), download=_fail_download)

    results: dict = {}
    errors: list = []

    def _call(sym):
        try:
            out = YahooProvider().daily_candles(sym, 180)
            results[sym] = float(out.iloc[-1]["Close"])
        except Exception as exc:  # noqa: BLE001 — surface any failure to the assert
            errors.append((sym, repr(exc)))

    threads = [threading.Thread(target=_call, args=(s,)) for s in symbols]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, errors
    assert results == closes  # each symbol returned ITS OWN last close


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
# Both the provider and its archive_models twin fetch these through
# ``yf.Ticker(symbol).history`` — NOT ``yf.download``, whose module-global result
# stash collides across FastAPI's threadpool. Mock the TICKER surface: a
# download-only mock would leave the real code path unfed, and the "no data"
# assertions below would pass on an unmocked-surface exception rather than on
# the behavior they name.
def _trend_frame(closes, day0="2026-01-01"):
    idx = pd.date_range(day0, periods=len(closes), freq="D")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_index_context_bullish_spy_and_vix(fake_yf):
    # 300 sessions rising; the last bar sits well above its 200-SMA → BULLISH.
    spy = _trend_frame([100.0 + i for i in range(300)])
    vix = _trend_frame([18.0, 19.0, 20.0])

    fake_yf(ticker=_history_ticker(
        lambda symbol, **k: spy if symbol == "SPY" else vix))
    ctx = YahooProvider().index_context("2026-09-30")
    assert ctx["spy_trend"] == "BULLISH"
    assert ctx["vix_level"] == 20.0


def test_index_context_hang_returns_neutral_default(fake_yf, monkeypatch):
    monkeypatch.setattr(providers_module, "_DOWNLOAD_TIMEOUT_S", 0.05)

    def _hang(symbol, **k):
        time.sleep(5)
        return _trend_frame([1.0])

    fake_yf(ticker=_history_ticker(_hang))
    ctx = YahooProvider().index_context("2026-09-30")
    assert ctx == {"spy_trend": None, "vix_level": None}


def test_sector_trend_bearish_below_sma(fake_yf):
    # 80 sessions falling; last bar below the 50-SMA → BEARISH.
    data = _trend_frame([200.0 - i for i in range(80)])
    fake_yf(ticker=_history_ticker(lambda symbol, **k: data))
    assert YahooProvider().sector_trend("XLK", "2026-03-21") == "BEARISH"


def test_sector_trend_empty_returns_none(fake_yf):
    fake_yf(ticker=_history_ticker(lambda symbol, **k: pd.DataFrame()))
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

    fake_yf(ticker=_history_ticker(
        lambda symbol, **k: spy if symbol == "SPY" else vix))
    as_of = "2026-09-30"
    assert (
        YahooProvider().index_context(as_of)
        == archive_models.get_market_context(as_of)
    )


def test_provider_sector_trend_matches_archive_get_sector_trend(fake_yf):
    # 80 sessions falling → BEARISH; both impls read the same mocked frame.
    data = _trend_frame([200.0 - i for i in range(80)])
    fake_yf(ticker=_history_ticker(lambda symbol, **k: data))
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
