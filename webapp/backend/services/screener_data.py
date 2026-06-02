"""Cached access to the screener dashboard JSON."""
from __future__ import annotations

import json
import os
from typing import Any

_cache: dict[str, Any] = {"mtime": 0, "data": None}


def read_screener_data(path: str) -> dict:
    if not os.path.exists(path):
        return {"ordered_tickers": [], "chart_data": {}}

    current_mtime = os.path.getmtime(path)
    if _cache["data"] is None or current_mtime != _cache["mtime"]:
        with open(path, "r", encoding="utf-8") as handle:
            _cache["data"] = json.load(handle)
        _cache["mtime"] = current_mtime

    return _cache["data"]


def invalidate_screener_cache() -> None:
    _cache["mtime"] = 0
    _cache["data"] = None
