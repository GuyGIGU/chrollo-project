"""Tiny versioned in-memory cache for the (expensive) episode grouping.

The episode grouping (``core.archive.episodes.build_episodes``) is an O(rows)
pass with an ``np.busday_count`` per consecutive same-base pair. It runs on every
``/archive/episodes`` request — including every sort-header click, which only
changes ordering, not the grouping. As the archive grows (~140 rows/trading-day)
that rebuild gets wasteful.

The grouping depends ONLY on immutable identity columns (ticker, scan_date,
setup_type) — those never change after a row is inserted — so a coarse
``(max(id), row_count)`` version of ``setup_archive`` fully captures whether
episode membership could have changed. Cache the grouping keyed by
``(filter signature, version)``; rebuild only when rows are added/removed. Row
*values* (forward returns, labels) are fetched fresh by the caller, so nothing
the cache serves can go stale.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Hashable


class VersionedCache:
    """Small thread-safe cache that invalidates a key when its version changes.

    Bounded to ``max_entries`` keys (oldest-touched evicted first) so distinct
    filter combinations can't grow memory without bound.
    """

    def __init__(self, max_entries: int = 32):
        self._lock = threading.Lock()
        self._store: dict[Hashable, tuple[Any, Any]] = {}   # key -> (version, value)
        self._order: list[Hashable] = []                    # LRU-ish touch order
        self._max = max_entries

    def get_or_compute(self, key: Hashable, version: Any, compute: Callable[[], Any]) -> Any:
        """Return the cached value for ``key`` if it was stored at ``version``,
        otherwise call ``compute()``, store, and return it."""
        with self._lock:
            hit = self._store.get(key)
            if hit is not None and hit[0] == version:
                self._touch(key)
                return hit[1]

        # Compute outside the lock — build_episodes can be slow, and a rare
        # double-compute on a cold key is harmless (same deterministic result).
        value = compute()

        with self._lock:
            self._store[key] = (version, value)
            self._touch(key)
            while len(self._order) > self._max:
                evicted = self._order.pop(0)
                self._store.pop(evicted, None)
        return value

    def _touch(self, key: Hashable) -> None:
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()
