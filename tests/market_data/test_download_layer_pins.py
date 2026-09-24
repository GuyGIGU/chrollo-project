"""Behaviour pins for the market-data download layer, driven at the yfinance boundary.

Every test runs the real download, repair and cache code against a fake Yahoo
(``yfinance.Ticker`` and ``yfinance.download``) under a frozen market clock. Inside
the layer only ``fetch_data``'s cache location and market-hours check are patched,
so the pins bind to behaviour, not to which module a helper lives in: the data that
comes out, the files written, the requests sent to Yahoo, the retries and cooldowns,
and the log lines the operator reads.

The clock is frozen at Thursday 2026-06-18, noon in New York. The latest COMPLETED
session is 2026-06-17, and a period fetch also returns 2026-06-18's forming bar.
"""
import json
import re
import threading
import time
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
import yfinance as yf
from yfinance import shared as yf_shared

from config import settings
from core.pipeline.market_data import downloads, market_calendar, rate_limit
from core.pipeline.market_data.cache import _atomic_write_parquet, _optimize_market_data_for_cache

# Where the code under test lives. Only these handles move when the layer is split.
yahoo = downloads   # one Yahoo request: retry, backoff, rate limit, the download pool
panel = downloads   # building and repairing the price panel

MARKET_TZ = market_calendar.MARKET_TZ
NOW_ET = datetime(2026, 6, 18, 12, 0, tzinfo=MARKET_TZ)
EXPECTED = pd.Timestamp("2026-06-17")
FORMING = pd.Timestamp("2026-06-18")
SESSIONS = pd.date_range("2025-05-01", FORMING, freq=market_calendar.NYSE_BUSINESS_DAY)

# Every setting the pinned paths read, fixed here so a config default change cannot
# move a pin. Jitter is off so each retry wait is exact.
_SETTINGS = {
    "DATA_DIVIDEND_ADJUSTED": False,
    "DOWNLOAD_PERIOD": "5y",
    "INDEX_SYMBOLS": ["SPY", "QQQ"],
    "TTL_FRESH_HOURS_OFFHOURS": 12,
    "FULL_REFRESH_INTERVAL_DAYS": 7,
    "INCREMENTAL_OVERLAP_BDAYS": 5,
    "INCREMENTAL_MAX_GAP_BDAYS": 10,
    "MARKET_DATA_MIN_LATEST_COVERAGE": 0.95,
    "MARKET_DATA_MIN_HISTORY_BARS": 100,
    "MARKET_DATA_MIN_HISTORY_COVERAGE": 0.5,
    "ADMISSION_MIN_HISTORY_BARS": 200,
    "TICKER_ADMISSION_ENABLED": True,
    "QUARANTINE_ENABLED": True,
    "QUARANTINE_EMPTY_STREAK": 2,
    "QUARANTINE_MIN_HEALTHY_RATIO": 0.85,
    "LATEST_REPAIR_BATCH_SIZE": 100,
    "LATEST_REPAIR_SLEEP_SECONDS": 2.0,
    "LATEST_REPAIR_MAX_MISSING_FRACTION": 0.98,
    "PROVIDER_ABSENT_SESSION_MAX_COVERAGE": 0.02,
    "ABSENT_SESSION_LEDGER_MAX": 20,
    "SPLIT_PROBE_DRIFT_THRESHOLD": 0.005,
    "SPLIT_PROBE_UNIVERSE_DRIFT_PCT": 0.02,
    "YAHOO_DOWNLOAD_WORKERS": 4,
    "YAHOO_RATE_LIMIT_BACKOFF_SECONDS": 45.0,
    "YAHOO_BACKOFF_JITTER": 0.0,
}

_VOLATILE_KEYS = {"ts", "at", "last_modified", "last_full_refresh", "duration_s",
                  "last_checked", "next_check", "first_empty", "last_empty",
                  "quarantined_until"}


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW_ET.astimezone(tz) if tz is not None else NOW_ET.replace(tzinfo=None)


def _history(base, sessions=SESSIONS, scale=1.0):
    """A yfinance-shaped daily history: tz-aware index, OHLCV plus 'Adj Close'.
    Prices are multiples of 1/8 so the float32 parquet round trip is exact."""
    step = np.arange(len(sessions))
    close = (base + 0.25 * (step % 16)) * scale
    return pd.DataFrame(
        {"Open": close - 0.25 * scale, "High": close + 0.5 * scale,
         "Low": close - 0.5 * scale, "Close": close, "Adj Close": close - 0.125,
         "Volume": 1000 + step},
        index=pd.DatetimeIndex(sessions, name="Date").tz_localize(MARKET_TZ),
    )


def _lost_session(history, day=EXPECTED):
    """The history with one session missing, the way Yahoo lost 2026-07-24."""
    return history.loc[history.index.tz_localize(None) != day]


def _panel(histories, until=EXPECTED):
    """The cache-shaped panel of ``histories``: tz-naive, OHLCV only, capped."""
    frames = {}
    for ticker, frame in histories.items():
        frame = frame.drop(columns="Adj Close")
        frame.index = frame.index.tz_localize(None)
        frames[ticker] = frame.loc[frame.index <= until]
    return pd.concat(frames, axis=1)


class _FakeYahoo:
    """Serves ``histories`` through yfinance's two entry points and records every
    request. A ticker listed in ``failures`` raises its queued errors first; a
    ticker mapped to ``None`` gets ``None`` back, as yfinance sometimes returns."""

    def __init__(self):
        self.histories: dict[str, pd.DataFrame | None] = {}
        self.failures: dict[str, list[Exception]] = {}
        self.requests: list[tuple] = []
        self.cooldowns: list[float] = []
        self.sleeps: list[float] = []
        self._lock = threading.Lock()

    def _serve(self, ticker, params):
        with self._lock:
            queued = self.failures.get(ticker)
            if queued:
                raise queued.pop(0)
        if ticker not in self.histories:
            return pd.DataFrame()
        frame = self.histories[ticker]
        if frame is None:
            return None
        if "start" in params:
            dates = frame.index.tz_localize(None)
            keep = (dates >= pd.Timestamp(params["start"])) & (dates < pd.Timestamp(params["end"]))
            return frame.loc[keep].copy()
        return frame.copy()

    def ticker(self, symbol):
        fake = self

        class _Ticker:
            def history(self, **params):
                with fake._lock:
                    fake.requests.append(("history", (symbol,), tuple(sorted(params.items()))))
                return fake._serve(symbol, params)

        return _Ticker()

    def download(self, batch, **params):
        with self._lock:
            self.requests.append(("download", tuple(batch), tuple(sorted(params.items()))))
        frames = {t: self._serve(t, params) for t in batch}
        frames = {t: f for t, f in frames.items() if f is not None and not f.empty}
        return pd.concat(frames, axis=1) if frames else pd.DataFrame()

    def sorted_requests(self):
        return sorted(self.requests)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    fake = _FakeYahoo()
    monkeypatch.setattr(yf, "Ticker", fake.ticker)
    monkeypatch.setattr(yf, "download", fake.download)
    monkeypatch.setattr(yf_shared, "_ERRORS", {})
    monkeypatch.setattr(market_calendar, "datetime", _FrozenDatetime)
    monkeypatch.setattr(rate_limit, "throttle", lambda n=1: None)
    monkeypatch.setattr(rate_limit, "note_rate_limit", fake.cooldowns.append)
    monkeypatch.setattr(time, "sleep", fake.sleeps.append)
    for name, value in _SETTINGS.items():
        monkeypatch.setattr(settings, name, value, raising=False)
    fake.dir = tmp_path
    fake.cache_file = tmp_path / "cache.parquet"
    fake.meta_file = tmp_path / "cache_meta.json"
    monkeypatch.setattr(downloads, "_cache_paths",
                        lambda universe=None: (str(fake.cache_file), str(fake.meta_file)))
    monkeypatch.setattr(downloads, "_is_market_hours", lambda: False)
    return fake


def _log(capsys, fake=None):
    out = capsys.readouterr().out
    if fake is not None:
        out = out.replace(str(fake.cache_file), "<cache>")
    out = re.sub(r"\(\d+\.\d\dh old", "(<age>h old", out)
    return out.splitlines()


def _stable(value):
    if isinstance(value, dict):
        return {k: "<volatile>" if k in _VOLATILE_KEYS else _stable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def _read_json(path):
    return _stable(json.loads(path.read_text(encoding="utf-8")))


def _same_panel(actual, expected):
    """Equal values up to column order, which the download pool leaves to thread timing."""
    assert not actual.columns.duplicated().any()
    assert actual.index.tz is None
    pd.testing.assert_frame_equal(actual.sort_index(axis=1), expected.sort_index(axis=1),
                                  check_dtype=False, check_freq=False)


def _dtypes(frame):
    return {f"{ticker}.{field}": str(dtype) for (ticker, field), dtype in frame.dtypes.items()}


def _volume_dtypes(frame):
    """Volume dtype per ticker; every price column is asserted float64 alongside."""
    dtypes = _dtypes(frame)
    prices = {k: v for k, v in dtypes.items() if not k.endswith(".Volume")}
    assert set(prices.values()) <= {"float64"}, prices
    return {k[:-len(".Volume")]: v for k, v in dtypes.items() if k.endswith(".Volume")}


def _assert_persisted(fake, out):
    persisted = pd.read_parquet(fake.cache_file, engine=settings.PARQUET_ENGINE)
    pd.testing.assert_frame_equal(persisted, _optimize_market_data_for_cache(out),
                                  check_freq=False)


def _seed_cache(fake, histories, until, meta):
    _atomic_write_parquet(_panel(histories, until=until), str(fake.cache_file))
    fake.meta_file.write_text(json.dumps(meta), encoding="utf-8")


def _recent_meta(**extra):
    stamp = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat()
    return {"price_series": "as_traded", "last_full_refresh": stamp, **extra}


def _history_request(ticker, **window):
    params = {"actions": False, "auto_adjust": False, "timeout": 30, **window}
    return ("history", (ticker,), tuple(sorted(params.items())))


def _download_request(batch, **window):
    params = {"group_by": "ticker", "threads": False, "progress": False, "timeout": 30,
              "auto_adjust": False, **window}
    return ("download", tuple(batch), tuple(sorted(params.items())))


_FIVE_YEARS = {"period": "5y"}


# ---- fetch_data: the cache state machine, end to end ----

def test_first_cold_fetch_writes_the_cache_ledgers_and_health(fake, capsys):
    for i, ticker in enumerate(["AAA", "BBB", "SPY", "QQQ"]):
        fake.histories[ticker] = _history(10.0 + 10 * i)
    fake.histories["YNG"] = _history(5.0, sessions=SESSIONS[-50:])   # current but young
    settings.MARKET_DATA_MIN_LATEST_COVERAGE = 0.8                   # DEAD leaves 5/6
    settings.QUARANTINE_MIN_HEALTHY_RATIO = 0.5                      # 3/4 is healthy

    out = downloads.fetch_data(["AAA", "BBB", "YNG", "DEAD"])

    assert _log(capsys, fake) == [
        "Cache price-series regime (div_adjusted) differs from settings (as_traded); "
        "forcing a full cold refetch.",
        "Downloading data for 6 tickers in batches to prevent rate limits...",
        "  Download: 6 tickers via 4 rate-limited workers...",
        "    Download: 6/6 fetched (5 non-empty)...",
        "Skipping fallback for 1 current but <200-bar ticker(s); admission will recheck later.",
        "Validating 1 tickers with missing or suspiciously short data (<200 bars) — "
        "per-ticker fallback...",
        "Fallback pass complete. No additional tickers could be recovered "
        "(likely delisted or too new).",
        "  Admission: cold updated 4 ticker(s) (active_ready=2, active_young=1, yahoo_empty=1).",
        "Saved optimized cache to <cache> (returned 3/4).",
    ]
    # The forming 2026-06-18 bar is cut, Adj Close is dropped, the index is tz-naive.
    _same_panel(out, _panel({t: fake.histories[t] for t in ["AAA", "BBB", "YNG", "SPY", "QQQ"]}))
    assert out.index.name == "Date"
    assert _volume_dtypes(out) == {"AAA": "int64", "BBB": "int64", "SPY": "int64",
                                   "QQQ": "int64", "YNG": "float64"}
    _assert_persisted(fake, out)
    # DEAD is asked twice: the pooled download, then the per-ticker fallback.
    assert fake.sorted_requests() == sorted(
        [_history_request(t, **_FIVE_YEARS) for t in ["AAA", "BBB", "YNG", "DEAD", "SPY", "QQQ"]]
        + [_history_request("DEAD", **_FIVE_YEARS)])
    assert fake.sleeps == [] and fake.cooldowns == []
    assert _read_json(fake.meta_file) == {
        "last_full_refresh": "<volatile>",
        "last_modified": "<volatile>",
        "price_series": "as_traded",
        "fetch_health": {
            "ts": "<volatile>", "mode": "cold", "requested": 4, "returned": 3,
            "return_ratio": 0.75, "skipped_quarantined": 0, "newly_quarantined": 0,
            "quarantined_total": 0, "duration_s": "<volatile>", "healthy": True,
        },
        "ticker_admission": {
            "skipped": 0, "skip_counts": {},
            "updates": {"active_ready": 2, "active_young": 1, "yahoo_empty": 1},
            "active_skip_counts": {"active_young": 1, "yahoo_empty": 1},
        },
    }
    assert _read_json(fake.dir / "ticker_quarantine.json") == {
        "DEAD": {"empty_streak": 1, "first_empty": "<volatile>", "last_empty": "<volatile>"},
    }
    admission = _read_json(fake.dir / "ticker_admission.json")
    assert {t: (row["status"], row["bars"]) for t, row in admission.items()} == {
        "AAA": ("active_ready", 284), "BBB": ("active_ready", 284),
        "YNG": ("active_young", 49), "DEAD": ("yahoo_empty", 0),
    }


def test_incremental_fetch_merges_new_bars_and_refetches_splits_and_listings(fake, capsys):
    for i, ticker in enumerate(["AAA", "BBB", "SPY", "QQQ"]):
        fake.histories[ticker] = _history(10.0 + 10 * i)
    fake.histories["SPL"] = _history(50.0)                            # split: cache holds 2x
    fake.histories["NEW"] = _history(7.0, sessions=SESSIONS[-260:])   # not in the cache yet
    cached = {t: fake.histories[t] for t in ["AAA", "BBB", "SPY", "QQQ"]}
    cached["SPL"] = _history(50.0, scale=2.0)
    _seed_cache(fake, cached, pd.Timestamp("2026-06-12"), _recent_meta())
    settings.SPLIT_PROBE_UNIVERSE_DRIFT_PCT = 0.5                     # 1 of 5 is not broad

    out = downloads.fetch_data(["AAA", "BBB", "SPL", "NEW"])

    assert _log(capsys, fake) == [
        "Local cache is fresh by mtime but latest-session coverage is 0/6 (0.0%) for "
        "2026-06-17 (required >= 95%); updating cache.",
        "Incremental update: gap=3 bday(s), fetching 2026-06-05 → 2026-06-18 (6 tickers)...",
        "  Incremental: 6 tickers via 4 rate-limited workers...",
        "    Incremental: 6/6 fetched (6 non-empty)...",
        "  Split-probe: 1/5 tickers show price drift (20.0%); force_full_refetch=False",
        "  +3 new bar(s); refreshing the 5-bday overlap window in place.",
        "  Fetching full history for 1 new listing(s)...",
        "Validating 1 tickers with missing or suspiciously short data (<200 bars) — "
        "per-ticker fallback...",
        "Successfully recovered full data for 1 tickers using fallback batches!",
        "  Refetching 1 split-drifted ticker(s) in full...",
        "Validating 1 tickers with missing or suspiciously short data (<200 bars) — "
        "per-ticker fallback...",
        "Successfully recovered full data for 1 tickers using fallback batches!",
        "  Admission: incremental updated 4 ticker(s) (active_ready=4).",
        "Saved incremental update to <cache>. New last bar: 2026-06-17.",
    ]
    # SPL is the post-split series throughout; nothing of the 2x cache survives.
    _same_panel(out, _panel({t: fake.histories[t]
                             for t in ["AAA", "BBB", "SPY", "QQQ", "SPL", "NEW"]}))
    assert list(out.columns.get_level_values(0).unique()) == [
        "AAA", "BBB", "SPY", "QQQ", "NEW", "SPL"]
    assert _volume_dtypes(out) == {"AAA": "Int64", "BBB": "Int64", "SPY": "Int64",
                                   "QQQ": "Int64", "NEW": "float64", "SPL": "int64"}
    _assert_persisted(fake, out)
    window = {"start": "2026-06-05", "end": "2026-06-18"}
    assert fake.sorted_requests() == sorted(
        [_history_request(t, **window) for t in ["AAA", "BBB", "SPL", "NEW", "SPY", "QQQ"]]
        + [_history_request(t, **_FIVE_YEARS) for t in ["NEW", "SPL"]])
    meta = _read_json(fake.meta_file)
    assert meta == {
        "price_series": "as_traded",
        "last_full_refresh": "<volatile>",
        "last_modified": "<volatile>",
        "fetch_health": {
            "ts": "<volatile>", "mode": "incremental", "requested": 4, "returned": 4,
            "return_ratio": 1.0, "skipped_quarantined": 0, "newly_quarantined": 0,
            "quarantined_total": 0, "duration_s": "<volatile>", "healthy": True,
        },
        "ticker_admission": {
            "skipped": 0, "skip_counts": {}, "updates": {"active_ready": 4},
            "active_skip_counts": {},
        },
    }


def test_incremental_write_clears_the_failure_ledger(fake, capsys):
    for i, ticker in enumerate(["AAA", "SPY", "QQQ"]):
        fake.histories[ticker] = _history(10.0 + 10 * i)
    _seed_cache(fake, dict(fake.histories), pd.Timestamp("2026-06-16"),
                _recent_meta(absent_sessions=["2026-06-12"],
                             last_cold_failure={"kind": "coverage"}))

    downloads.fetch_data(["AAA"])

    meta = json.loads(fake.meta_file.read_text(encoding="utf-8"))
    assert "absent_sessions" not in meta and "last_cold_failure" not in meta
    assert meta["fetch_health"]["mode"] == "incremental"


def test_fresh_cache_is_served_without_touching_yahoo(fake, capsys):
    for i, ticker in enumerate(["AAA", "SPY", "QQQ"]):
        fake.histories[ticker] = _history(10.0 + 10 * i)
    _seed_cache(fake, dict(fake.histories), EXPECTED, _recent_meta())
    meta_before = fake.meta_file.read_text(encoding="utf-8")

    out = downloads.fetch_data(["AAA"])

    assert _log(capsys, fake) == [
        "  Admission: cache updated 1 ticker(s) (active_ready=1).",
        "Loading market data from local cache (<age>h old, TTL 12h)...",
    ]
    _same_panel(out, _panel(fake.histories))
    assert set(_dtypes(out).values()) == {"float32", "Int64"}   # straight off the parquet
    assert fake.requests == []
    assert fake.meta_file.read_text(encoding="utf-8") == meta_before
    assert list(json.loads((fake.dir / "ticker_admission.json").read_text())) == ["AAA"]


def test_current_cache_past_its_ttl_is_touched_and_served(fake, capsys):
    for i, ticker in enumerate(["AAA", "SPY", "QQQ"]):
        fake.histories[ticker] = _history(10.0 + 10 * i)
    _seed_cache(fake, dict(fake.histories), EXPECTED, _recent_meta())
    settings.TTL_FRESH_HOURS_OFFHOURS = 0

    out = downloads.fetch_data(["AAA"])

    assert _log(capsys, fake) == [
        "Cache last market-regime bar is current (2026-06-17); touching mtime and returning.",
        "  Admission: cache updated 1 ticker(s) (active_ready=1).",
    ]
    _same_panel(out, _panel(fake.histories))
    assert fake.requests == []
    assert _read_json(fake.meta_file) == {
        "price_series": "as_traded", "last_full_refresh": "<volatile>",
        "last_modified": "<volatile>",
    }


def test_a_session_proven_absent_serves_the_cache_instead_of_going_cold(fake, capsys):
    for i, ticker in enumerate(["AAA", "BBB", "SPY", "QQQ"]):
        fake.histories[ticker] = _lost_session(_history(10.0 + 10 * i))
    _seed_cache(fake, dict(fake.histories), pd.Timestamp("2026-06-16"),
                _recent_meta(absent_sessions=["2026-06-17"],
                             last_cold_failure={"coverage_ratio": 0.0, "duration_s": 12.5}))
    meta_before = fake.meta_file.read_text(encoding="utf-8")

    out = downloads.fetch_data(["AAA", "BBB"])

    assert _log(capsys, fake) == [
        "Local cache is fresh by mtime but latest-session coverage is 0/4 (0.0%) for "
        "2026-06-17 (required >= 95%); updating cache.",
        "Incremental update: gap=1 bday(s), fetching 2026-06-09 → 2026-06-18 (4 tickers)...",
        "  Incremental: 4 tickers via 4 rate-limited workers...",
        "    Incremental: 4/4 fetched (4 non-empty)...",
        "  Incremental latest-session coverage is 0/4 (0.0%) for 2026-06-17 (required >= 95%); "
        "repairing 4 missing symbol(s) in 100-batches...",
        "  Incremental repair batch 1/1 (4 tickers)...",
        "  Incremental repair coverage after patch: 0/4 (0.0%).",
        "  Incremental latest-session coverage is 0/4 (0.0%) for 2026-06-17 "
        "(required >= 95%); falling back to full refetch.",
        "  Incremental fetch yielded no usable data; falling back to full refetch.",
        "Skipping cold refetch: 2026-06-17 is recorded absent upstream (a full fetch reached "
        "coverage 0.0 in 12.5s). Serving the cached panel; the next completed session retries "
        "automatically, and Download New Data forces a retry now.",
    ]
    _same_panel(out, _panel(fake.histories, until=pd.Timestamp("2026-06-16")))
    assert fake.sorted_requests() == sorted(
        [_history_request(t, start="2026-06-09", end="2026-06-18")
         for t in ["AAA", "BBB", "SPY", "QQQ"]]
        + [_download_request(["AAA", "BBB", "SPY", "QQQ"], start="2026-06-10", end="2026-06-18")])
    assert fake.sleeps == [2.0]                       # the one repair batch's pause
    assert fake.meta_file.read_text(encoding="utf-8") == meta_before


def test_a_cold_fetch_that_finds_the_session_absent_records_it(fake, capsys):
    for i, ticker in enumerate(["AAA", "BBB", "SPY", "QQQ"]):
        fake.histories[ticker] = _lost_session(_history(10.0 + 10 * i))

    out = downloads.fetch_data(["AAA", "BBB"])

    assert _log(capsys, fake) == [
        "Cache price-series regime (div_adjusted) differs from settings (as_traded); "
        "forcing a full cold refetch.",
        "Downloading data for 4 tickers in batches to prevent rate limits...",
        "  Download: 4 tickers via 4 rate-limited workers...",
        "    Download: 4/4 fetched (4 non-empty)...",
        "  Full refetch latest-session coverage is 0/4 (0.0%) for 2026-06-17 (required >= 95%); "
        "repairing 4 missing symbol(s) in 100-batches...",
        "  Full refetch repair batch 1/1 (4 tickers)...",
        "  Full refetch repair coverage after patch: 0/4 (0.0%).",
        "  Recorded 2026-06-17 as absent upstream (coverage 0/4 (0.0%)); further full fetches "
        "for that session are skipped until it changes or you press Download.",
        "Full refetch latest-session coverage is 0/4 (0.0%) for 2026-06-17 (required >= 95%); "
        "keeping existing cache if possible.",
    ]
    # No cache to keep, so the unhealthy panel itself comes back, forming bar cut.
    _same_panel(out, _panel(fake.histories, until=pd.Timestamp("2026-06-16")))
    assert not fake.cache_file.exists()
    assert fake.sleeps == [2.0]
    assert _read_json(fake.meta_file) == {
        "fetch_health": {
            "ts": "<volatile>", "mode": "cold", "requested": 2, "returned": 2,
            "return_ratio": 1.0, "skipped_quarantined": 0, "newly_quarantined": 0,
            "quarantined_total": 0, "duration_s": "<volatile>", "healthy": True,
        },
        "ticker_admission": {"skipped": 0, "skip_counts": {}, "updates": {},
                             "active_skip_counts": {}},
        "last_cold_failure": {"at": "<volatile>", "expected_session": "2026-06-17",
                              "coverage_ratio": 0.0, "duration_s": "<volatile>",
                              "kind": "coverage"},
        "absent_sessions": ["2026-06-17"],
    }


def test_an_empty_cold_fetch_is_a_provider_failure_not_an_absent_session(fake, capsys):
    out = downloads.fetch_data(["AAA", "BBB"])

    assert _log(capsys, fake) == [
        "Cache price-series regime (div_adjusted) differs from settings (as_traded); "
        "forcing a full cold refetch.",
        "Downloading data for 4 tickers in batches to prevent rate limits...",
        "  Download: 4 tickers via 4 rate-limited workers...",
        "    Download: 4/4 fetched (0 non-empty)...",
        "All downloads failed, returning empty DataFrame.",
        "Full refetch returned no data for any symbol; keeping the existing cache. This is a "
        "total provider failure, not an absent session — the next run retries.",
    ]
    assert out.empty
    assert not fake.cache_file.exists()
    meta = _read_json(fake.meta_file)
    assert meta["last_cold_failure"] == {"at": "<volatile>", "expected_session": "2026-06-17",
                                         "coverage_ratio": 0.0, "duration_s": "<volatile>",
                                         "kind": "empty"}
    assert "absent_sessions" not in meta
    assert meta["fetch_health"]["returned"] == 0 and meta["fetch_health"]["healthy"] is False
    assert meta["ticker_admission"]["updates"] == {}


# ---- one Yahoo request: shape, retry, backoff, the shared cooldown ----

def test_a_single_ticker_request_goes_through_ticker_history(fake, capsys):
    fake.histories["AAA"] = _history(10.0)

    out = yahoo._download_batch_with_retry(["AAA"], "1mo")

    assert fake.requests == [_history_request("AAA", period="1mo")]
    assert list(out.columns) == [("AAA", f) for f in ["Open", "High", "Low", "Close", "Volume"]]
    assert out.index.tz is not None          # tz is stripped by the callers, not here
    assert len(out) == len(SESSIONS)
    assert _log(capsys) == []


def test_caller_window_keys_override_the_request_defaults(fake):
    fake.histories["AAA"] = _history(10.0)

    yahoo._download_batch_with_retry(["AAA"], {"period": "5y", "auto_adjust": True})

    assert fake.requests == [("history", ("AAA",), (
        ("actions", False), ("auto_adjust", True), ("period", "5y"), ("timeout", 30)))]


@pytest.mark.parametrize("history", [None, "missing"])
def test_an_empty_single_ticker_answer_is_final(fake, capsys, history):
    if history is None:
        fake.histories["DEAD"] = None

    out = yahoo._download_batch_with_retry(["DEAD"], {"period": "5y"})

    assert out.empty and isinstance(out, pd.DataFrame)
    assert len(fake.requests) == 1
    assert fake.sleeps == [] and fake.cooldowns == [] and _log(capsys) == []


def test_a_multi_ticker_request_goes_through_download(fake):
    fake.histories["AAA"] = _history(10.0)
    fake.histories["BBB"] = _history(20.0)
    window = {"start": "2026-06-10", "end": "2026-06-18"}

    out = yahoo._download_batch_with_retry(["AAA", "BBB"], window)

    assert fake.requests == [_download_request(["AAA", "BBB"], **window)]
    assert set(out.columns.get_level_values(1)) == {"Open", "High", "Low", "Close", "Volume"}
    assert set(out.columns.get_level_values(0)) == {"AAA", "BBB"}
    assert len(out) == 6                     # 06-10 .. 06-17; the end date is exclusive


def test_a_rate_limited_symbol_in_a_good_batch_arms_the_cooldown(fake):
    fake.histories["AAA"] = _history(10.0)
    yf_shared._ERRORS = {"BBB": "YFRateLimitError('Too Many Requests. Rate limited.')"}

    out = yahoo._download_batch_with_retry(["AAA", "BBB"], {"period": "5y"})

    assert set(out.columns.get_level_values(0)) == {"AAA"}
    assert fake.cooldowns == [45.0]
    assert fake.sleeps == [] and len(fake.requests) == 1


def test_an_empty_rate_limited_batch_retries_after_the_shared_cooldown(fake, capsys):
    yf_shared._ERRORS = {"AAA": "Too Many Requests. Rate limited."}

    out = yahoo._download_batch_with_retry(["AAA", "BBB"], {"period": "5y"})

    assert out.empty
    assert len(fake.requests) == 3
    assert fake.sleeps == [45.0, 45.0]
    assert fake.cooldowns == [45.0, 45.0]
    assert _log(capsys) == [
        "    Attempt 1/3 rate-limited. Retrying in 45s...",
        "    Attempt 2/3 rate-limited. Retrying in 45s...",
    ]


def test_an_empty_batch_without_a_rate_limit_is_not_retried(fake, capsys):
    yf_shared._ERRORS = {"AAA": "YFPricesMissingError('possibly delisted')"}

    out = yahoo._download_batch_with_retry(["AAA", "BBB"], {"period": "5y"})

    assert out.empty and len(fake.requests) == 1
    assert fake.sleeps == [] and _log(capsys) == []


def test_errors_retry_with_exponential_backoff_then_give_up(fake, capsys):
    fake.failures["AAA"] = [RuntimeError("HTTP 502") for _ in range(3)]

    out = yahoo._download_batch_with_retry(["AAA"], {"period": "5y"})

    assert out.empty and len(fake.requests) == 3
    assert fake.sleeps == [2.0, 4.0] and fake.cooldowns == []
    assert _log(capsys) == [
        "    Attempt 1/3 failed (HTTP 502). Retrying in 2s...",
        "    Attempt 2/3 failed (HTTP 502). Retrying in 4s...",
        "    Batch failed after 3 retries: HTTP 502",
    ]


def test_a_rate_limit_error_waits_out_the_shared_cooldown_then_succeeds(fake, capsys):
    fake.histories["AAA"] = _history(10.0)
    fake.failures["AAA"] = [RuntimeError("YFRateLimitError('Too Many Requests')")]

    out = yahoo._download_batch_with_retry(["AAA"], {"period": "5y"}, max_retries=2)

    assert "AAA" in out and len(fake.requests) == 2
    assert fake.sleeps == [45.0] and fake.cooldowns == [45.0]
    assert _log(capsys) == [
        "    Attempt 1/2 failed (YFRateLimitError('Too Many Requests')). Retrying in 45s...",
    ]


def test_a_no_history_error_is_final(fake, capsys):
    fake.histories["AAA"] = _history(10.0)
    fake.failures["AAA"] = [RuntimeError("YFTzMissingError: no timezone found")]

    out = yahoo._download_batch_with_retry(["AAA"], {"period": "5y"})

    assert out.empty and len(fake.requests) == 1
    assert fake.sleeps == [] and _log(capsys) == []


class YFRateLimitError(Exception):
    pass


class YFTzMissingError(Exception):
    pass


@pytest.mark.parametrize("error,rate_limited,no_history", [
    (RuntimeError("Too Many Requests"), True, False),
    (RuntimeError("you are rate limited"), True, False),
    (YFRateLimitError(), True, False),
    (RuntimeError("possibly delisted; no price data found"), False, True),
    (RuntimeError("No timezone found, symbol may be delisted"), False, True),
    (YFTzMissingError(), False, True),
    (RuntimeError("HTTP 502 Bad Gateway"), False, False),
])
def test_yahoo_error_classification(error, rate_limited, no_history):
    assert yahoo._is_yahoo_rate_limit_error(error) is rate_limited
    assert yahoo._is_yahoo_no_history_error(error) is no_history


def test_batch_error_text_reads_yfinance_errors_by_upper_case_symbol(monkeypatch):
    monkeypatch.setattr(yf_shared, "_ERRORS", {"AAA": "boom", "CCC": "", "DDD": "bust"})
    assert yahoo._last_yahoo_batch_error_text(["aaa", "bbb", "ccc", "ddd"]) == "boom | bust"
    monkeypatch.setattr(yf_shared, "_ERRORS", None)
    assert yahoo._last_yahoo_batch_error_text(["aaa"]) == ""


def test_the_download_pool_strips_tz_and_reports_progress(fake, capsys):
    fake.histories["AAA"] = _history(10.0)
    fake.histories["BBB"] = _history(20.0, sessions=SESSIONS[-10:])

    out = yahoo._batched_download(["AAA", "BBB", "DEAD"], {"period": "5y"}, "Test")

    assert _log(capsys) == [
        "  Test: 3 tickers via 3 rate-limited workers...",
        "    Test: 3/3 fetched (2 non-empty)...",
    ]
    _same_panel(out, _panel({"AAA": fake.histories["AAA"], "BBB": fake.histories["BBB"]},
                            until=FORMING))
    assert _volume_dtypes(out) == {"AAA": "int64", "BBB": "float64"}


def test_the_download_pool_with_nothing_to_do_or_nothing_back(fake, capsys):
    assert yahoo._batched_download([], {"period": "5y"}, "Test").empty
    assert fake.requests == [] and _log(capsys) == []

    assert yahoo._batched_download(["DEAD"], {"period": "5y"}, "Test").empty
    assert _log(capsys) == ["  Test: 1 tickers via 1 rate-limited workers...",
                            "    Test: 1/1 fetched (0 non-empty)..."]


# ---- building and repairing the panel ----

def test_recovery_leaves_a_complete_panel_untouched(fake, capsys):
    data = _panel({"AAA": _history(10.0), "BBB": _history(20.0)})

    assert panel._recover_missing_data(data, ["AAA", "BBB"]) is data
    assert fake.requests == [] and _log(capsys) == []


def test_recovery_backs_off_when_most_of_the_universe_dropped_out(fake, capsys):
    data = _panel({"AAA": _history(10.0)})

    assert panel._recover_missing_data(data, ["AAA", "GONE1", "GONE2"]) is data
    assert fake.requests == []
    assert _log(capsys) == [
        "Warning: 2 dropouts detected. Rate limit severe. Skipping individual fallback "
        "to avoid IP ban.",
    ]


def test_recovery_replaces_a_short_ticker_with_its_full_history(fake, capsys):
    fake.histories["BBB"] = _history(20.0)
    data = _panel({
        "AAA": _history(10.0),
        "BBB": _history(20.0, sessions=SESSIONS[:150]),   # stale and short: refetch
        "CCC": _history(30.0, sessions=SESSIONS[-31:]),   # current but young: leave
        "EEE": _history(40.0),
    })

    out = panel._recover_missing_data(data, ["AAA", "BBB", "CCC", "DDD", "EEE"])

    assert _log(capsys) == [
        "Skipping fallback for 1 current but <200-bar ticker(s); admission will recheck later.",
        "Validating 2 tickers with missing or suspiciously short data (<200 bars) — "
        "per-ticker fallback...",
        "Successfully recovered full data for 1 tickers using fallback batches!",
    ]
    assert fake.sorted_requests() == [_history_request("BBB", **_FIVE_YEARS),
                                      _history_request("DDD", **_FIVE_YEARS)]
    # The old BBB columns go, the fallback is appended, and the period fetch's
    # forming bar rides along: capping it is the caller's job.
    assert list(out.columns.get_level_values(0).unique()) == ["AAA", "CCC", "EEE", "BBB"]
    assert out.index.tz is None and out.index.max() == FORMING
    pd.testing.assert_frame_equal(out["BBB"], _panel({"BBB": fake.histories["BBB"]},
                                                     until=FORMING)["BBB"], check_freq=False)
    pd.testing.assert_series_equal(out[("AAA", "Close")].loc[:EXPECTED],
                                   data[("AAA", "Close")], check_freq=False)
    assert out[("AAA", "Close")].isna().sum() == 1


def test_latest_session_repair_leaves_a_covered_panel_untouched(fake, capsys):
    data = _panel({"AAA": _history(10.0), "SPY": _history(20.0)})

    assert panel._repair_latest_session(data, ["AAA", "SPY"], EXPECTED, 0.95, "test") is data
    assert fake.requests == [] and _log(capsys) == []


def test_latest_session_repair_patches_in_paced_batches(fake, capsys):
    for i, ticker in enumerate(["AAA", "BBB", "CCC", "SPY"]):
        fake.histories[ticker] = _history(10.0 + 10 * i)
    data = _panel({"AAA": fake.histories["AAA"], "BBB": fake.histories["BBB"],
                   "CCC": fake.histories["CCC"]}, until=pd.Timestamp("2026-06-16"))
    data = pd.concat([data, _panel({"SPY": fake.histories["SPY"]})], axis=1)
    settings.LATEST_REPAIR_BATCH_SIZE = 2

    out = panel._repair_latest_session(data, ["AAA", "BBB", "CCC", "SPY"], EXPECTED,
                                       0.95, "test", dropout_guard=True)

    assert _log(capsys) == [
        "  test latest-session coverage is 1/4 (25.0%) for 2026-06-17 (required >= 95%); "
        "repairing 3 missing symbol(s) in 2-batches...",
        "  test repair batch 1/2 (2 tickers)...",
        "  test repair batch 2/2 (1 tickers)...",
        "  test repair coverage after patch: 4/4 (100.0%).",
    ]
    window = {"start": "2026-06-10", "end": "2026-06-18"}
    assert fake.requests == [_download_request(["AAA", "BBB"], **window),
                             _history_request("CCC", **window)]
    assert fake.sleeps == [2.0, 2.0]
    assert list(out.columns) == list(data.columns)
    assert out.index.tz is None
    pd.testing.assert_frame_equal(out, _panel(fake.histories)[list(data.columns)],
                                  check_dtype=False, check_freq=False)


def test_latest_session_repair_with_nothing_back_returns_the_panel(fake, capsys):
    data = _panel({"AAA": _history(10.0)}, until=pd.Timestamp("2026-06-16"))

    out = panel._repair_latest_session(data, ["AAA"], EXPECTED, 0.95, "test")

    assert out is data
    assert _log(capsys)[-1] == "  test repair yielded no usable data."
    assert fake.sleeps == [2.0]


def test_incremental_fetch_gives_up_on_an_empty_window(fake, capsys):
    cached = _panel({t: _history(10.0) for t in ["AAA", "SPY", "QQQ"]},
                    until=pd.Timestamp("2026-06-16"))

    assert panel._incremental_fetch(cached, ["AAA", "SPY", "QQQ"], 1) is None
    assert _log(capsys) == [
        "Incremental update: gap=1 bday(s), fetching 2026-06-09 → 2026-06-18 (3 tickers)...",
        "  Incremental: 3 tickers via 3 rate-limited workers...",
        "    Incremental: 3/3 fetched (0 non-empty)...",
        "  Incremental download returned empty/malformed data.",
    ]


def test_incremental_fetch_goes_cold_on_broad_split_drift(fake, capsys):
    for i, ticker in enumerate(["AAA", "BBB", "SPY", "QQQ"]):
        fake.histories[ticker] = _history(10.0 + 10 * i)
    cached = dict(fake.histories)
    cached["AAA"] = _history(10.0, scale=2.0)
    cached["BBB"] = _history(20.0, scale=2.0)
    cached = _panel(cached, until=pd.Timestamp("2026-06-16"))

    assert panel._incremental_fetch(cached, ["AAA", "BBB", "SPY", "QQQ"], 1) is None
    assert _log(capsys)[-1] == (
        "  Split-probe: 2/4 tickers show price drift (50.0%); force_full_refetch=True")
    assert all(request[2][2:] == (("end", "2026-06-18"), ("start", "2026-06-09"), ("timeout", 30))
               for request in fake.requests)
    assert len(fake.requests) == 4                     # the window only; no recovery
