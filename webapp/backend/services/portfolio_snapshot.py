"""Portfolio snapshot shaping helpers."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

import models
from core.pipeline.json_safety import to_json_safe
from database import SessionLocal
from ibkr import get_ibkr_service

_CACHE_KEY = "last_known"
_log = logging.getLogger("chrollo.portfolio")

SUMMARY_KEYS = (
    "NetLiquidation",
    "TotalCashValue",
    "AvailableFunds",
    "BuyingPower",
    "Cushion",
    "ExcessLiquidity",
    "GrossPositionValue",
    "Leverage-S",
    "MaintMarginReq",
    "UnrealizedPnL",
    "RealizedPnL",
    "SMA",
)


def flatten_summary(summary: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Collapse account buckets into one summary used by the Portfolio UI."""
    values: Dict[str, Any] = {}
    currency: Dict[str, str] = {}
    for bucket in summary.values():
        for tag, entry in bucket.items():
            if tag not in SUMMARY_KEYS:
                continue
            value = entry.get("value")
            try:
                numeric_value = float(value)
                values[tag] = values.get(tag, 0.0) + numeric_value
                currency.setdefault(tag, entry.get("currency") or "")
            except (TypeError, ValueError):
                values.setdefault(tag, value)
    return {"values": values, "currency": currency, "raw": summary}


def portfolio_snapshot_payload() -> Dict[str, Any]:
    svc = get_ibkr_service()
    snap = svc.snapshot()
    payload = {
        "connected": snap["connected"],
        "mode": snap["mode"],
        "stale": snap.get("stale", False),
        "daily_restart": snap.get("daily_restart", False),
        "session_competition": snap.get("session_competition", False),
        "last_update": snap["last_update"],
        "account_summary": flatten_summary(snap["account_summary"]),
        "positions": snap["portfolio"] or snap["positions"],
        "open_orders": snap["open_orders"],
        "recent_executions": snap["recent_executions"][-50:],
    }
    if has_portfolio_data(payload):
        try:
            save_snapshot_cache(payload)
        except Exception:
            _log.warning("failed to save portfolio snapshot cache", exc_info=True)
        return payload
    try:
        cached = load_snapshot_cache()
    except Exception:
        _log.warning("failed to load portfolio snapshot cache", exc_info=True)
        cached = None
    return with_cached_snapshot(payload, cached)


def has_portfolio_data(snapshot: Dict[str, Any]) -> bool:
    summary = snapshot.get("account_summary") or {}
    if summary.get("values"):
        return True
    raw = summary.get("raw") or {}
    if any(bucket for bucket in raw.values()):
        return True
    return any(snapshot.get(key) for key in ("positions", "open_orders", "recent_executions"))


def with_cached_snapshot(current: Dict[str, Any], cached: Dict[str, Any] | None) -> Dict[str, Any]:
    if not cached:
        return current
    return {
        **current,
        "stale": True,
        "account_summary": cached.get("account_summary") or current["account_summary"],
        "positions": cached.get("positions") or [],
        "open_orders": cached.get("open_orders") or [],
        "recent_executions": cached.get("recent_executions") or [],
        "last_update": cached.get("last_update") or current["last_update"],
        "backend_cached": True,
    }


def save_snapshot_cache(snapshot: Dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        row = db.get(models.PortfolioSnapshotCache, _CACHE_KEY)
        if row is None:
            row = models.PortfolioSnapshotCache(key=_CACHE_KEY)
            db.add(row)
        row.payload_json = json.dumps(to_json_safe(snapshot), allow_nan=False)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def load_snapshot_cache() -> Dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = db.get(models.PortfolioSnapshotCache, _CACHE_KEY)
        if row is None:
            return None
        return json.loads(row.payload_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    finally:
        db.close()


def stored_executions(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    rows = (
        db.query(models.Execution)
        .order_by(models.Execution.time.desc(), models.Execution.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "exec_id": row.exec_id,
            "account": row.account,
            "symbol": row.symbol,
            "sec_type": row.sec_type,
            "side": row.side,
            "quantity": row.quantity,
            "price": row.price,
            "commission": row.commission,
            "realized_pnl": row.realized_pnl,
            "time": row.time.isoformat() if row.time else None,
            "trade_log_id": row.trade_log_id,
        }
        for row in rows
    ]
