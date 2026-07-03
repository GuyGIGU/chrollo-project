"""Filesystem, metadata, and market-clock helpers for pipeline data caching."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from config import settings
from core.pipeline.json_safety import to_json_safe
from core.pipeline.universe import resolve_universe


def _project_root() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def _cache_paths(universe=None) -> tuple[str, str]:
    """(market-data parquet, cache-meta json) for a universe.

    ``universe=None`` resolves to US-Stocks, so every existing call is unchanged
    and the returned paths are byte-identical to the previous hardcoded tuple.
    """
    return resolve_universe(universe).cache_paths()


def _read_meta(meta_path: str) -> dict:
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _replace_with_retry(tmp: str, path: str, attempts: int = 5, wait_s: float = 0.2) -> None:
    """``os.replace`` with a short bounded retry. On Windows, replacing a file a
    concurrent reader has open (an unlocked cache-status ``read_parquet``) raises
    PermissionError — a multi-minute download must not die at its final step over
    a transient read, so wait the reader out briefly before giving up."""
    for attempt in range(1, attempts + 1):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(wait_s)


def _write_meta(meta_path: str, meta: dict) -> None:
    # PID-suffixed temp so two processes writing the same meta can't share one
    # .tmp and tear each other's write (the cross-process cache_lock serializes
    # the real window; this is belt-and-suspenders for the os.replace target).
    tmp = f'{meta_path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(to_json_safe(meta), f, indent=2, allow_nan=False)
    _replace_with_retry(tmp, meta_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _optimize_market_data_for_cache(data: pd.DataFrame) -> pd.DataFrame:
    optimized = data.copy()
    for column in optimized.columns:
        field = column[1] if isinstance(column, tuple) and len(column) > 1 else column
        if field in {'Open', 'High', 'Low', 'Close', 'Adj Close'}:
            optimized[column] = pd.to_numeric(optimized[column], errors='coerce').astype('float32')
        elif field == 'Volume':
            optimized[column] = pd.to_numeric(optimized[column], errors='coerce').round().astype('Int64')
    return optimized


def _is_market_hours() -> bool:
    """US equity market hours: 09:30–16:00 ET, Monday–Friday."""
    ny = datetime.now(ZoneInfo("America/New_York"))
    if ny.weekday() >= 5:
        return False
    minutes = ny.hour * 60 + ny.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def _atomic_write_parquet(data: pd.DataFrame, path: str) -> None:
    tmp = f'{path}.{os.getpid()}.tmp'
    optimized = _optimize_market_data_for_cache(data)
    optimized.to_parquet(
        tmp,
        engine=settings.PARQUET_ENGINE,
        compression=settings.PARQUET_COMPRESSION,
    )
    _replace_with_retry(tmp, path)
