"""Cached access to the screener dashboard JSON."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

_cache: dict[str, Any] = {"mtime": 0, "data": None}
log = logging.getLogger("chrollo.screener_data")


def read_screener_data(path: str) -> dict:
    if not os.path.exists(path):
        return {"ordered_tickers": [], "chart_data": {}}

    current_mtime = os.path.getmtime(path)
    if _cache["data"] is None or current_mtime != _cache["mtime"]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                _cache["data"] = json.load(handle)
            _cache["mtime"] = current_mtime
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("failed to read screener data %s: %s", path, exc)
            if _cache["data"] is None:
                return {"ordered_tickers": [], "chart_data": {}}

    return _cache["data"]


def invalidate_screener_cache() -> None:
    _cache["mtime"] = 0
    _cache["data"] = None
