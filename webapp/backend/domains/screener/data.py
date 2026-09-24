"""Cached access to the screener dashboard JSON."""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

# Keyed per artifact path so the three universes' payloads coexist — switching
# universes in the cockpit no longer evicts the others (the large US-Stocks JSON
# stays parsed in memory across toggles).
_cache: dict[str, dict[str, Any]] = {}
# Readers run in FastAPI's threadpool while a scan stream invalidates: dict
# access goes through the lock, and the read path serves its LOCAL entry so a
# clear landing between store and return can never KeyError.
_lock = threading.Lock()
log = logging.getLogger("chrollo.screener_data")


def read_screener_data(path: str) -> dict:
    if not os.path.exists(path):
        return {"ordered_tickers": [], "chart_data": {}}

    current_mtime = os.path.getmtime(path)
    with _lock:
        entry = _cache.get(path)
    if entry is None or entry["mtime"] != current_mtime:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            entry = {"mtime": current_mtime, "data": data}
            with _lock:
                _cache[path] = entry
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("failed to read screener data %s: %s", path, exc)
            if entry is None:
                return {"ordered_tickers": [], "chart_data": {}}

    return entry["data"]


def invalidate_screener_cache(path: str | None = None) -> None:
    """Drop the cached payload. ``path=None`` clears every universe (safe default
    used after a scan stream); a path clears just that universe."""
    with _lock:
        if path is None:
            _cache.clear()
        else:
            _cache.pop(path, None)
