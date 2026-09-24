"""The UI candle read's TTL cache.

The three-pane market strip turns ``/market-data/chart`` into Home's first-paint
cost, and every call previously went straight to the vendor. These pin the cache
contract that removes the repeat round-trips WITHOUT letting it lie: a hit must
not reach the provider, an expiry must, empty results must never be cached, and
no caller may receive a frame another thread can mutate underneath it.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from domains.market_data import service as market_data  # noqa: E402


class _CountingProvider:
    """Stands in for the vendor: counts calls, returns a one-row frame."""

    def __init__(self, frame=None):
        self.calls = []
        self._frame = frame if frame is not None else pd.DataFrame(
            {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100]},
            index=pd.to_datetime(["2026-08-07"]),
        )

    def daily_candles(self, symbol, days, *, start=None, end=None, auto_adjust=False):
        self.calls.append((symbol, days, start, end, auto_adjust))
        return self._frame.copy()


@pytest.fixture
def provider(monkeypatch):
    market_data.clear_candle_cache()
    stub = _CountingProvider()
    monkeypatch.setattr(market_data, "get_provider", lambda: stub)
    yield stub
    market_data.clear_candle_cache()


def test_second_read_is_served_from_cache(provider):
    first = market_data.daily_candle_frame("SPY", 400)
    second = market_data.daily_candle_frame("SPY", 400)

    assert len(provider.calls) == 1, "a cache hit must not reach the vendor"
    pd.testing.assert_frame_equal(first, second)


def test_each_distinct_request_shape_is_its_own_entry(provider):
    market_data.daily_candle_frame("SPY", 400)
    market_data.daily_candle_frame("QQQ", 400)          # different symbol
    market_data.daily_candle_frame("SPY", 180)          # different window
    market_data.daily_candle_frame("SPY", 400, auto_adjust=True)  # different adjustment
    market_data.daily_candle_frame("SPY", 400)          # repeat of the first -> hit

    assert len(provider.calls) == 4


def test_expiry_refetches(provider, monkeypatch):
    clock = {"now": 1_000.0}
    monkeypatch.setattr(market_data.time, "monotonic", lambda: clock["now"])

    market_data.daily_candle_frame("SPY", 400)
    clock["now"] += market_data._CANDLE_TTL_SECONDS - 1
    market_data.daily_candle_frame("SPY", 400)
    assert len(provider.calls) == 1, "still inside the TTL"

    clock["now"] += 2
    market_data.daily_candle_frame("SPY", 400)
    assert len(provider.calls) == 2, "past the TTL the vendor is consulted again"


def test_empty_results_are_never_cached(monkeypatch):
    """A provider hiccup must not pin a blank chart for the whole TTL."""
    market_data.clear_candle_cache()
    empty = _CountingProvider(frame=pd.DataFrame())
    monkeypatch.setattr(market_data, "get_provider", lambda: empty)

    assert market_data.daily_candle_frame("SPY", 400).empty
    assert market_data.daily_candle_frame("SPY", 400).empty
    assert len(empty.calls) == 2
    market_data.clear_candle_cache()


def test_callers_cannot_mutate_the_shared_frame(provider):
    """Routes iterate these frames on the threadpool — a caller's edit must not
    travel to the next reader."""
    first = market_data.daily_candle_frame("SPY", 400)
    first.loc[first.index[0], "Close"] = 999.0

    second = market_data.daily_candle_frame("SPY", 400)
    assert second.loc[second.index[0], "Close"] == 1.5
    assert first is not second


def test_cache_stays_bounded(provider):
    """A hover sweep can touch many names; the cache must not grow forever."""
    for index in range(market_data._CANDLE_CACHE_MAX * 2):
        market_data.daily_candle_frame(f"SYM{index}", 400)

    assert len(market_data._candle_cache) <= market_data._CANDLE_CACHE_MAX
