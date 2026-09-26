"""Market-data cache status helpers for the dashboard."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from config import settings
from core.pipeline.market_data.cache import _cache_paths, _read_meta, _weekly_refresh_due
from core.pipeline.market_data.market_calendar import (
    MARKET_TZ,
    is_early_close_session,
    latest_completed_session,
    market_closed_reason,
    next_session_close,
)
from core.pipeline.market_data.market_data_health import compute_market_data_health
from core.pipeline.universe.tickers import get_cached_tickers


def build_market_data_status(now_et: datetime | None = None) -> dict:
    status_now = _as_market_time(now_et)
    cache_file, meta_file = _cache_paths()
    expected = latest_completed_session(status_now)
    next_session, next_close = next_session_close(status_now)
    closed_reason = market_closed_reason(status_now)
    meta = _read_meta(meta_file)

    base = {
        "cache_exists": os.path.exists(cache_file),
        "cache_file": cache_file,
        "expected_session": _date_str(expected),
        "next_session": _date_str(next_session),
        "next_close_at": next_close.isoformat(),
        "closed_reason": closed_reason,
        "market_open": closed_reason is None,
        "early_close_today": bool(is_early_close_session(pd.Timestamp(status_now).date())),
        "min_coverage": float(getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)),
        "last_full_refresh": meta.get("last_full_refresh"),
        "weekly_refresh_due": _weekly_refresh_due(meta),
    }

    if not os.path.exists(cache_file):
        return _finish(base, "cache_missing", "blocked", True, False, False,
                       "Download cache", "No market-data cache found.")

    tickers, ticker_error = _load_cached_tickers_for_status()
    if ticker_error:
        return _finish(base, "cache_missing", "blocked", True, False, False,
                       "Refresh universe", ticker_error)

    try:
        data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
    except Exception as exc:
        return _finish(base, "cache_unreadable", "blocked", True, False, False,
                       "Rebuild cache", f"Market-data cache cannot be read: {exc}",
                       help_needed=True)

    health = compute_market_data_health(
        data,
        tickers,
        expected_session=expected,
        meta=meta,
        meta_file=meta_file,
        now_utc=status_now.astimezone(timezone.utc),
        closed_reason=closed_reason,
        weekly_refresh_due=base["weekly_refresh_due"],
    )
    health.update(base)
    health["cache_modified_at"] = _mtime_iso(cache_file)
    health["min_coverage"] = health["coverage"]["archive_target"]
    return health


def _load_cached_tickers_for_status() -> tuple[list[str], str | None]:
    try:
        return get_cached_tickers(), None
    except Exception as exc:
        return [], f"Cached ticker universe is unavailable: {exc}"


def _as_market_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(MARKET_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=MARKET_TZ)
    return value.astimezone(MARKET_TZ)


def _finish(base: dict, health_state: str, severity: str, can_download: bool,
            can_evaluate: bool, can_archive: bool, download_label: str,
            diagnosis: str, help_needed: bool = False) -> dict:
    base.update({
        "health_state": health_state,
        "status": health_state,
        "severity": severity,
        "can_download": can_download,
        "can_evaluate": can_evaluate,
        "can_archive": can_archive,
        "download_label": download_label,
        "message": diagnosis,
        "diagnosis": diagnosis,
        "help_needed": help_needed,
        "coverage": {
            "raw": None,
            "eligible": None,
            "archive_target": base["min_coverage"],
            "text": "none",
            "ratio": 0,
            "present": 0,
            "total": 0,
        },
        "missing_summary": {},
        "next_retry_at": None,
        "retry_seconds": 0,
        "retry_reason": None,
    })
    return base


def _date_str(value) -> str | None:
    if value is None:
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _mtime_iso(path: str) -> str | None:
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
    except OSError:
        return None
