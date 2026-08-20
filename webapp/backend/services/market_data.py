"""Web-layer market-data service — single doorway onto the provider for the UI.

The chart/quote routes used to call ``yfinance`` raw (``yf.download`` /
``yf.Ticker``), each re-implementing the same MultiIndex-flatten and candle
shaping, and one of them (the live-price poll) had an *untimed* ``.info`` fall
back that could stall the open-position dashboard. This service centralizes
those reads behind ``get_provider()`` so:

  * the single-symbol fetch and the field-validation/candle shaping live in one
    place (used by both ``/market-data/chart`` and the archive setup chart), and
  * every hang-prone vendor call inherits the provider's daemon-thread timeout.

It deliberately does NOT touch the engine's ``provider.fetch`` panel read — only
the UI-facing capability methods added in C1.

Phase 2: a persistent reference cache for sector/earnings would attach here
(read-through in front of the provider's ``sector``/``earnings_date``).
"""
from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from core.pipeline.providers import get_provider

logger = logging.getLogger("chrollo.market_data")

# Read-through TTL cache for the UI candle reads.
#
# Every ``/market-data/chart`` call went straight to the vendor, so each visit to
# Home re-downloaded the same index histories — and the three-pane market strip
# turns that into the surface's first-paint cost. Daily bars only move on the
# forming session, so a few minutes of staleness is invisible here while the
# repeat round-trips disappear. Deliberately in-process and unshared: this is a
# latency cache for one operator's UI, not a store of record (the engine's own
# parquet cache remains the substrate for anything that gets archived).
_CANDLE_TTL_SECONDS = 300
_CANDLE_CACHE_MAX = 64
_candle_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
# Routes run in FastAPI's threadpool: _cache_put iterates the dict while
# another request may mutate it, so every compound cache operation takes the
# lock (the earnings/candle_cache/episode sibling discipline).
_CANDLE_LOCK = threading.Lock()


def _cache_get(key: Tuple[Any, ...], now: float):
    with _CANDLE_LOCK:
        entry = _candle_cache.get(key)
        if entry is None:
            return None
        stamped_at, frame = entry
        if now - stamped_at > _CANDLE_TTL_SECONDS:
            _candle_cache.pop(key, None)
            return None
        return frame


def _cache_put(key: Tuple[Any, ...], frame, now: float) -> None:
    with _CANDLE_LOCK:
        if len(_candle_cache) >= _CANDLE_CACHE_MAX:
            # Drop what has already expired; if the whole set is live, start over
            # rather than growing without bound (a hover sweep can touch many names).
            for stale in [k for k, (at, _) in _candle_cache.items() if now - at > _CANDLE_TTL_SECONDS]:
                _candle_cache.pop(stale, None)
            if len(_candle_cache) >= _CANDLE_CACHE_MAX:
                _candle_cache.clear()
        _candle_cache[key] = (now, frame)


def clear_candle_cache() -> None:
    """Drop every cached frame (tests, and any deliberate operator refresh)."""
    with _CANDLE_LOCK:
        _candle_cache.clear()


def _is_number(value: Any) -> bool:
    """True iff ``value`` is a finite real number (NaN/inf/None rejected)."""
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def daily_candle_frame(
    symbol: str,
    days: int = 180,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    auto_adjust: bool = False,
):
    """Return a flattened single-level OHLCV frame for ``symbol`` via the provider.

    Read-through cached (``_CANDLE_TTL_SECONDS``) in front of
    ``provider.daily_candles`` (which flattens the MultiIndex and is hard-bounded
    against a yfinance hang). Returns an empty frame when the vendor yields
    nothing, so callers branch on ``.empty`` for their 404 — empty results are
    NOT cached, so a provider hiccup doesn't pin a blank chart for five minutes.

    Callers get a copy: the cached frame is shared across threadpool requests and
    must never be mutated underneath another reader.
    """
    key = (symbol, days, start, end, auto_adjust)
    now = time.monotonic()

    cached = _cache_get(key, now)
    if cached is not None:
        return cached.copy()

    frame = get_provider().daily_candles(
        symbol, days, start=start, end=end, auto_adjust=auto_adjust
    )
    if frame is not None and not frame.empty:
        _cache_put(key, frame.copy(), now)
    return frame


def chart_candles(
    raw,
    *,
    up_color: str,
    down_color: str,
    require_finite: bool,
    volume_as_int: bool,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Shape a flattened OHLCV frame into ``(candles, volumes)`` payload lists.

    Centralizes the per-row candle/volume building the two chart routes shared.
    Non-finite rows are ALWAYS skipped — the provider never drops NaN rows, so
    ``int(NaN)`` raised on the archive path and NaN OHLC 500'd at Starlette's
    allow_nan=False JSON boundary (EC-6). On finite rows each route's payload
    is byte-identical to before:

      * ``require_finite`` — retained for the routes' keyword calls; the
        finite skip no longer varies by route.
      * ``volume_as_int`` — cast volume to ``int`` (archive route) vs ``float``
        (UI chart route).
      * ``up_color`` / ``down_color`` — per-route volume bar colors.
    """
    candles: List[Dict[str, Any]] = []
    volumes: List[Dict[str, Any]] = []
    for timestamp, row in raw.iterrows():
        ohlc = {name: row.get(name) for name in ("Open", "High", "Low", "Close")}
        if not all(_is_number(v) for v in ohlc.values()):
            continue
        date = timestamp.strftime("%Y-%m-%d")
        close = float(ohlc["Close"])
        open_ = float(ohlc["Open"])
        candles.append({
            "time": date,
            "open": open_,
            "high": float(ohlc["High"]),
            "low": float(ohlc["Low"]),
            "close": close,
        })
        volume = row.get("Volume")
        if not _is_number(volume):
            continue
        value = int(volume) if volume_as_int else float(volume)
        volumes.append({
            "time": date,
            "value": value,
            "color": up_color if close >= open_ else down_color,
        })
    return candles, volumes


def latest_prices(symbols: List[str]) -> Dict[str, float]:
    """Per-symbol last price via the provider (each lookup timeout-bounded)."""
    return get_provider().latest_price(symbols)
