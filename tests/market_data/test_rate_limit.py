"""Tests for the global Yahoo download throttle (core.pipeline.market_data.rate_limit).

Hermetic — no live network. The timing tests prove the bucket enforces the rate
and that the throttle is ONE global ceiling shared across threads (not per-thread);
the download test proves the gate is wired into _batched_download with yfinance's
inner threading disabled.
"""
import threading
import time

import pandas as pd

from _paths import REPO_ROOT
from config import settings
from core.pipeline.market_data import rate_limit


def teardown_function():
    rate_limit.reset_for_test()  # restore the lazy-from-settings bucket


def test_token_bucket_enforces_rate():
    rate_limit.reset_for_test(rate=100.0, capacity=5.0)
    bucket = rate_limit.yahoo_rate_limiter()
    bucket.acquire(5)                      # drain the burst instantly
    start = time.monotonic()
    bucket.acquire(10)                     # 10 more at 100/s -> ~0.1s
    elapsed = time.monotonic() - start
    assert 0.06 <= elapsed <= 0.7, elapsed


def test_acquire_larger_than_capacity_does_not_deadlock():
    rate_limit.reset_for_test(rate=500.0, capacity=4.0)
    start = time.monotonic()
    rate_limit.yahoo_rate_limiter().acquire(20)   # chunked; ~20/500 = 0.04s
    assert time.monotonic() - start < 1.0


def test_throttle_is_one_global_ceiling_across_threads():
    # 8 threads x 8 = 64 requests. Burst 10, rate 200/s => the remaining 54 drain
    # at 200/s = >= 0.27s of wall time. A PER-THREAD limiter would let all 8 burst
    # through in well under that — so this lower bound proves a single shared bucket.
    rate_limit.reset_for_test(rate=200.0, capacity=10.0)
    assert getattr(settings, "YAHOO_RATE_LIMIT_ENABLED", True) is True

    def worker():
        for _ in range(8):
            rate_limit.throttle(1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.2, elapsed


def test_throttle_is_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "YAHOO_RATE_LIMIT_ENABLED", False)
    rate_limit.reset_for_test(rate=0.001, capacity=1.0)   # would block ~forever if used
    start = time.monotonic()
    rate_limit.throttle(1000)
    assert time.monotonic() - start < 0.2


def test_batched_download_gates_each_ticker_and_uses_single_history(monkeypatch):
    from core.pipeline.market_data import downloads

    seen = []
    history_calls = []
    monkeypatch.setattr(rate_limit, "throttle", lambda n=1: seen.append(n))

    idx = pd.date_range("2024-01-01", periods=3)

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, **kwargs):
            history_calls.append((self.ticker, kwargs))
            return pd.DataFrame(
                {"Open": [1.0, 2.0, 3.0], "High": [1.0, 2.0, 3.0], "Low": [1.0, 2.0, 3.0],
                 "Close": [1.0, 2.0, 3.0], "Volume": [10, 20, 30]},
                index=idx,
            )  # single-ticker frame; downloads forces the MultiIndex

    def fail_download(*_args, **_kwargs):
        raise AssertionError("yf.download should not be used for single-ticker workers")

    monkeypatch.setattr(downloads.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(downloads.yf, "download", fail_download)

    out = downloads._batched_download(["AAA", "BBB", "CCC"], {"period": "2y"}, "Test")
    assert not out.empty
    level0 = set(out.columns.get_level_values(0))
    assert {"AAA", "BBB", "CCC"} <= level0
    assert len(seen) == 3            # throttle invoked once per single-ticker download
    assert [ticker for ticker, _ in history_calls] == ["AAA", "BBB", "CCC"]
    assert all(kwargs["actions"] is False for _, kwargs in history_calls)


def test_batched_download_dedupes_duplicate_ohlcv_columns(monkeypatch):
    from core.pipeline.market_data import downloads

    monkeypatch.setattr(rate_limit, "throttle", lambda n=1: None)

    idx = pd.date_range("2024-01-01", periods=3)

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, **kwargs):
            columns = pd.MultiIndex.from_tuples(
                [(self.ticker, field) for field in ("Open", "High", "Low", "Close", "Volume")]
                + [(self.ticker, field) for field in ("Open", "High", "Low", "Close", "Volume")]
            )
            return pd.DataFrame(
                [[1.0, 2.0, 0.5, 1.5, 100, 1.1, 2.1, 0.6, 1.6, 110]] * len(idx),
                index=idx,
                columns=columns,
            )

    monkeypatch.setattr(downloads.yf, "Ticker", FakeTicker)

    out = downloads._batched_download(["AAA"], {"period": "2y"}, "Test")

    assert list(out["AAA"].columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert out["AAA"]["Close"].tolist() == [1.6, 1.6, 1.6]


def test_archive_download_paths_use_shared_batched_downloader():
    root = REPO_ROOT
    for rel in (
        "core/archive/forward_returns.py",
        "core/archive/seed.py",
        "webapp/backend/domains/archive/actions.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "yf.download" not in text
        assert "_yf.download" not in text
        assert "_batched_download" in text
