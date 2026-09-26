"""Session candle cache + resilient-fetch behaviour (Calibration workbench WP-0).

Pure unit tests against ``domains.market_data.candle_cache`` with the market-data doorway
and the rate-limit cooldown mocked — never a live network call, never a booted
app. The three outcomes the calibration chart endpoint depends on (served,
throttled, genuinely empty) are pinned here so the endpoint tests can stay
focused on chart shaping.
"""
import sys

import pandas as pd

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from domains.market_data import candle_cache  # noqa: E402


def _wide_frame():
    # Spans well past a 900-day lookback so a nearby second window is covered.
    idx = pd.bdate_range("2023-01-02", "2025-10-01")
    n = len(idx)
    return pd.DataFrame({"Open": [10.0] * n, "High": [11.0] * n, "Low": [9.0] * n,
                         "Close": [10.0] * n, "Volume": [1_000_000.0] * n}, index=idx)


def test_covered_window_is_served_from_cache_without_refetch(monkeypatch):
    import domains.market_data.service as market_data
    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return _wide_frame()

    monkeypatch.setattr(candle_cache, "_CACHE", {})
    monkeypatch.setattr(market_data, "daily_candle_frame", counting)
    monkeypatch.setattr("core.pipeline.market_data.rate_limit.in_cooldown", lambda: False)

    f1, s1 = candle_cache.load_candles("KLAC", "2023-06-01", "2025-08-01", False)
    f2, s2 = candle_cache.load_candles("KLAC", "2023-07-01", "2025-08-15", False)

    assert (s1, s2) == ("ok", "ok")
    assert calls["n"] == 1            # the day-scrub was served locally
    assert not f1.empty and not f2.empty
    # The returned slice is bounded to the requested window, not the wide fetch.
    assert f2.index.min() >= pd.Timestamp("2023-07-01")
    assert f2.index.max() <= pd.Timestamp("2025-08-15")


def test_cache_miss_during_cooldown_is_rate_limited_and_never_fetches(monkeypatch):
    import domains.market_data.service as market_data
    monkeypatch.setattr(candle_cache, "_CACHE", {})
    monkeypatch.setattr("core.pipeline.market_data.rate_limit.in_cooldown", lambda: True)
    monkeypatch.setattr(market_data, "daily_candle_frame",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("must not hit the vendor during a cooldown")))

    frame, status = candle_cache.load_candles("KLAC", "2025-06-01", "2025-08-01", False)
    assert status == "rate_limited"
    assert frame.empty


def test_empty_without_throttle_signal_is_no_data(monkeypatch):
    import domains.market_data.service as market_data
    monkeypatch.setattr(candle_cache, "_CACHE", {})
    monkeypatch.setattr(candle_cache, "_TRANSIENT_RETRY_WAIT_S", 0.0)
    monkeypatch.setattr("core.pipeline.market_data.rate_limit.in_cooldown", lambda: False)
    monkeypatch.setattr(market_data, "daily_candle_frame", lambda *a, **k: pd.DataFrame())

    frame, status = candle_cache.load_candles("ZZZZ", "2025-06-01", "2025-08-01", False)
    assert status == "no_data"
    assert frame.empty


def test_a_regime_change_is_a_miss_not_a_stale_hit(monkeypatch):
    # auto_adjust is part of the cache identity: a frame fetched as-traded must
    # never be served to a dividend-adjusted request (regime mixing corrupts reads).
    import domains.market_data.service as market_data
    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return _wide_frame()

    monkeypatch.setattr(candle_cache, "_CACHE", {})
    monkeypatch.setattr(market_data, "daily_candle_frame", counting)
    monkeypatch.setattr("core.pipeline.market_data.rate_limit.in_cooldown", lambda: False)

    candle_cache.load_candles("KLAC", "2023-06-01", "2025-08-01", False)
    candle_cache.load_candles("KLAC", "2023-06-01", "2025-08-01", True)
    assert calls["n"] == 2            # the auto_adjust flip forced a refetch
