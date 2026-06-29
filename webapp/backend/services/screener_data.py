"""Cached access to the screener dashboard JSON."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

# Keyed per artifact path so the three universes' payloads coexist — switching
# universes in the cockpit no longer evicts the others (the large US-Stocks JSON
# stays parsed in memory across toggles).
_cache: dict[str, dict[str, Any]] = {}
log = logging.getLogger("chrollo.screener_data")


def read_screener_data(path: str) -> dict:
    if not os.path.exists(path):
        return {"ordered_tickers": [], "chart_data": {}}

    current_mtime = os.path.getmtime(path)
    entry = _cache.get(path)
    if entry is None or entry["mtime"] != current_mtime:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            _cache[path] = {"mtime": current_mtime, "data": data}
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("failed to read screener data %s: %s", path, exc)
            if entry is None:
                return {"ordered_tickers": [], "chart_data": {}}

    return _cache[path]["data"]


def invalidate_screener_cache(path: str | None = None) -> None:
    """Drop the cached payload. ``path=None`` clears every universe (safe default
    used after a scan stream); a path clears just that universe."""
    if path is None:
        _cache.clear()
    else:
        _cache.pop(path, None)
