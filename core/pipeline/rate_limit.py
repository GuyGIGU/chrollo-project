"""Process-global token-bucket throttle for outbound Yahoo Finance requests.

WHY a token bucket and not a rate-limited session: yfinance 1.2.1 moved its HTTP
layer to curl_cffi and REJECTS a stdlib ``requests.Session`` outright (see
yfinance/data.py: ``raise YFDataException("Yahoo API requires curl_cffi
session...")`` and the request-cache rejection). So the classic
``requests-ratelimiter`` ``LimiterSession`` cannot be injected. Instead every
``yf.download`` call passes through ONE shared token bucket here, so the many
concurrent download workers (the screener's ThreadPoolExecutor) collectively
respect a single request-rate ceiling instead of each throttling independently
and bursting Yahoo into 429s — the root cause of the 2%-coverage stale-data days.

Pure stdlib (threading + time) — no new dependency. In-process is sufficient: the
scan runs in ONE subprocess under SCAN_LOCK, so all its downloads share this
module's bucket; there is no second concurrent fetcher to coordinate with across
processes.

Settings are read LAZILY (the backend's cwd shadows the repo-root ``config``
package, so a module-level settings read would crash the service at boot).
"""
from __future__ import annotations

import threading
import time


class TokenBucket:
    """Classic monotonic token bucket. ``acquire(n)`` blocks until ``n`` tokens
    are available, refilling at ``rate`` tokens/sec up to ``capacity`` (the burst
    ceiling). Thread-safe; an ``acquire`` larger than ``capacity`` is satisfied in
    capacity-sized chunks so it can never deadlock."""

    def __init__(self, rate: float, capacity: float):
        self.rate = max(float(rate), 1e-6)
        self.capacity = max(float(capacity), 1.0)
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _take_up_to_capacity(self, n: float) -> None:
        # n <= capacity. Block (sleeping outside the lock) until n tokens exist.
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                if elapsed > 0:
                    self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                    self._last = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                wait = (n - self._tokens) / self.rate
            time.sleep(min(max(wait, 0.0), 1.0))

    def acquire(self, n: int = 1) -> None:
        remaining = float(max(int(n), 1))
        while remaining > 0:
            chunk = min(remaining, self.capacity)
            self._take_up_to_capacity(chunk)
            remaining -= chunk


_bucket: "TokenBucket | None" = None
_bucket_lock = threading.Lock()


def yahoo_rate_limiter() -> TokenBucket:
    """The process-global bucket, built lazily from settings on first use."""
    global _bucket
    if _bucket is None:
        with _bucket_lock:
            if _bucket is None:
                from config import settings  # lazy — avoid the cwd-shadow boot crash
                rate = float(getattr(settings, "YAHOO_RATE_LIMIT_PER_SEC", 8.0))
                burst = float(getattr(settings, "YAHOO_RATE_LIMIT_BURST", 15.0))
                _bucket = TokenBucket(rate, burst)
    return _bucket


def throttle(n: int = 1) -> None:
    """Block until ``n`` request tokens are available from the global bucket.

    A no-op when ``YAHOO_RATE_LIMIT_ENABLED`` is false, so the throttle can be
    switched off without code changes."""
    from config import settings  # lazy
    if not getattr(settings, "YAHOO_RATE_LIMIT_ENABLED", True):
        return
    yahoo_rate_limiter().acquire(n)


def download_workers(default: int = 10) -> int:
    """Bounded worker count for the download pool (caps concurrent connections)."""
    from config import settings  # lazy
    try:
        return max(1, int(getattr(settings, "YAHOO_DOWNLOAD_WORKERS", default)))
    except (TypeError, ValueError):
        return default


def reset_for_test(rate: "float | None" = None, capacity: "float | None" = None) -> None:
    """Rebuild (or clear) the global bucket. Tests only."""
    global _bucket
    with _bucket_lock:
        if rate is None:
            _bucket = None
        else:
            _bucket = TokenBucket(rate, capacity if capacity is not None else rate)
