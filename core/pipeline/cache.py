"""Filesystem, metadata, and market-clock helpers for pipeline data caching."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from config import settings


def _project_root() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def _cache_paths() -> tuple[str, str]:
    root = _project_root()
    return (
        os.path.join(root, settings.CACHE_FILENAME),
        os.path.join(root, settings.CACHE_META_FILENAME),
    )


def _read_meta(meta_path: str) -> dict:
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_meta(meta_path: str, meta: dict) -> None:
    tmp = meta_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    os.replace(tmp, meta_path)


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
    tmp = path + '.tmp'
    optimized = _optimize_market_data_for_cache(data)
    optimized.to_parquet(
        tmp,
        engine=settings.PARQUET_ENGINE,
        compression=settings.PARQUET_COMPRESSION,
    )
    os.replace(tmp, path)
