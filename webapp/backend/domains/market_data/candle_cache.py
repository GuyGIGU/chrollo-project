"""Session candle cache + resilient fetch for the calibration workbench (WP-0).

An EPHEMERAL, regenerable, in-memory speed store — strictly separate from the
immutable ``frame_store`` replay corpus. It exists to keep a marking session
snappy and to survive transient Yahoo rate-limiting:

  * one raw fetch per ticker per session serves every day-scrub step as a local
    slice (no re-pull of ~900 bars per step), because the fetch pads the window
    generously and the endpoint slices back to what it displays, and
  * an already-fetched ticker keeps loading straight from cache even while Yahoo
    is throttling, so a rate-limit blip never dead-ends the session.

It NEVER feeds grading — the harness / engine-test always read the digest-
verified frozen frame, never this cache. Bounded to the session's distinct
tickers (a single-operator local app pulls tens, not thousands); no eviction by
design (Performance seat P5: don't build an LRU for a corpus this small).

Vendor-heavy imports are lazy inside the functions: the backend cwd shadows the
repo-root ``config`` package, so a module-level ``domains.market_data.service`` /
``core.pipeline.market_data.downloads`` import would risk the boot-crash trap (AP-3).
"""
from __future__ import annotations

import threading
import time

import pandas as pd

from core.pipeline.market_data import rate_limit

# ticker -> {"frame": DataFrame, "start": Timestamp, "end": Timestamp, "auto_adjust": bool}
_CACHE: dict = {}
_LOCK = threading.Lock()

# Cache a wider window than the chart exposes so day-scrubbing stays a local
# slice instead of a fresh ~900-bar pull each step. Pure speed pad — the caller
# still slices to its own [start, end] for display and freezes only <= as-of.
_CACHE_FORWARD_PAD_DAYS = 120
_CACHE_BACK_PAD_DAYS = 30

# Bounded + fast (P4 budget the request): a bare transient empty (no rate-limit
# signal) gets ONE quick retry; a detected throttle returns immediately (calm)
# and never loop-waits the full cooldown inside the request.
_TRANSIENT_RETRY_WAIT_S = 1.0


def _covers(entry, start_ts: pd.Timestamp, end_ts: pd.Timestamp, auto_adjust: bool) -> bool:
    return (entry is not None
            and entry["auto_adjust"] == auto_adjust
            and entry["start"] <= start_ts
            and entry["end"] >= end_ts)


def _slice(frame: pd.DataFrame, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    return frame[(frame.index >= start_ts) & (frame.index <= end_ts)]


def _last_yahoo_error_text(symbol: str) -> str:
    """Best-effort read of yfinance's per-symbol error after a ``Ticker.history``
    call (populated on some failures, absent on others). Never raises."""
    try:
        from yfinance import shared as yf_shared  # noqa: PLC0415
        return str((getattr(yf_shared, "_ERRORS", {}) or {}).get(symbol.upper(), ""))
    except Exception:
        return ""


def _looks_rate_limited(symbol: str) -> bool:
    """True when there is positive evidence Yahoo is throttling — an active
    shared cooldown, or a rate-limit-flavoured vendor error. Reuses the ONE
    rate-limit text detector from the download path (EC-3), never a fork."""
    if rate_limit.in_cooldown():
        return True
    try:
        from core.pipeline.market_data.downloads import _is_yahoo_rate_limit_text  # noqa: PLC0415
    except Exception:
        return False
    return _is_yahoo_rate_limit_text(_last_yahoo_error_text(symbol))


def _fetch(symbol: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp,
           auto_adjust: bool) -> pd.DataFrame:
    """Fetch a padded window through the single market-data doorway. The pad is
    cache-only; the caller slices back to its own [start, end]."""
    from datetime import datetime, timezone  # noqa: PLC0415

    from domains.market_data.service import daily_candle_frame  # noqa: PLC0415 — vendor chain, lazy
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    fetch_start = start_ts - pd.Timedelta(days=_CACHE_BACK_PAD_DAYS)
    fetch_end = end_ts + pd.Timedelta(days=_CACHE_FORWARD_PAD_DAYS)
    if fetch_end > today:
        fetch_end = max(end_ts, today)
    return daily_candle_frame(symbol, 0,
                              start=fetch_start.strftime("%Y-%m-%d"),
                              end=fetch_end.strftime("%Y-%m-%d"),
                              auto_adjust=auto_adjust)


def load_candles(symbol: str, start: str, end: str, auto_adjust: bool):
    """Return ``(raw_frame_slice, status)`` for the window [start, end].

    ``status`` is one of:
      * ``"ok"``          — frame is the requested slice (served from cache or a
                            fresh fetch);
      * ``"rate_limited"``— transient Yahoo throttle (an active cooldown, or a
                            rate-limit-flavoured empty) — the caller degrades to
                            a calm retry notice, keeping any loaded chart up;
      * ``"no_data"``     — the vendor returned nothing with no throttle signal
                            (unknown / delisted, or a plain hiccup).

    ``symbol`` is already validated against the strict grammar by the caller, so
    it is only ever a cache key here, never a path. The cache never feeds
    grading — only the frozen frame does.
    """
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

    with _LOCK:
        entry = _CACHE.get(symbol)
    if _covers(entry, start_ts, end_ts, auto_adjust):
        return _slice(entry["frame"], start_ts, end_ts), "ok"

    # A cache miss while Yahoo is in a known cooldown: don't add pressure —
    # surface the calm throttle status instead of hammering into the 429.
    if rate_limit.in_cooldown():
        return pd.DataFrame(), "rate_limited"

    frame = _fetch(symbol, start_ts, end_ts, auto_adjust)
    if frame.empty and not _looks_rate_limited(symbol):
        # A bare transient blip (no throttle signal): one quick retry.
        if _TRANSIENT_RETRY_WAIT_S > 0:
            time.sleep(_TRANSIENT_RETRY_WAIT_S)
        frame = _fetch(symbol, start_ts, end_ts, auto_adjust)

    if frame.empty:
        return frame, ("rate_limited" if _looks_rate_limited(symbol) else "no_data")

    with _LOCK:
        _CACHE[symbol] = {"frame": frame, "start": frame.index[0],
                          "end": frame.index[-1], "auto_adjust": auto_adjust}
    return _slice(frame, start_ts, end_ts), "ok"


def reset() -> None:
    """Drop the whole session cache (tests; a manual 'refetch everything')."""
    with _LOCK:
        _CACHE.clear()
