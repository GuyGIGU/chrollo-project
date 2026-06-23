"""Health report helpers for the FastAPI readiness endpoint."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from database import engine
from ibkr import get_ibkr_service
from services.core_settings import load_core_settings
from services import scan_status, scheduler, trade_alerts


def build_health_report(screener_json_path: str) -> dict:
    checks = {}

    _add_db_check(checks)
    _add_scan_check(checks)
    _add_screener_data_check(checks, screener_json_path)
    _add_scheduler_check(checks)
    _add_trade_alerts_check(checks)
    _add_ibkr_check(checks)

    return {
        "status": "ok" if _checks_are_ok(checks) else "degraded",
        "app": "Chrollo API",
        "time": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


def _add_db_check(checks: dict) -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = {"ok": True}
    except Exception as exc:
        checks["db"] = {"ok": False, "error": str(exc)[:200]}


def _add_scan_check(checks: dict) -> None:
    try:
        latest = scan_status.latest_run()
    except Exception:
        latest = None

    scan_ok, age_hours, detail = _scan_freshness(latest)
    checks["last_scan"] = {
        "ok": scan_ok,
        "status": (latest or {}).get("status", "never"),
        "finished_at": (latest or {}).get("finished_at"),
        "n_setups": (latest or {}).get("n_setups"),
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "detail": detail,
    }


def _add_screener_data_check(checks: dict, screener_json_path: str) -> None:
    try:
        data_age_hours = (time.time() - os.path.getmtime(screener_json_path)) / 3600.0
        checks["screener_data"] = {"ok": True, "exists": True, "age_hours": round(data_age_hours, 1)}
    except OSError:
        checks["screener_data"] = {"ok": False, "exists": False}


def _add_scheduler_check(checks: dict) -> None:
    try:
        scheduler_ok = scheduler.is_running()
    except Exception:
        scheduler_ok = False
    checks["scheduler"] = {"ok": scheduler_ok}


def _add_trade_alerts_check(checks: dict) -> None:
    try:
        status = trade_alerts.get_trade_alert_status()
        settings = load_core_settings()
        configured_enabled = bool(getattr(settings, "TRADE_ALERTS_ENABLED", False))
    except Exception as exc:
        checks["trade_alerts"] = {"ok": False, "status": "error", "last_error": str(exc)[:200]}
        return

    checks["trade_alerts"] = {
        "ok": status.get("status") != "error",
        "configured_enabled": configured_enabled,
        **status,
    }


def _add_ibkr_check(checks: dict) -> None:
    try:
        snapshot = get_ibkr_service().snapshot()
        checks["ibkr"] = {"connected": bool(snapshot.get("connected")), "mode": snapshot.get("mode")}
    except Exception:
        checks["ibkr"] = {"connected": False}


def _scan_freshness(latest: dict | None) -> tuple[bool, float | None, str]:
    if not latest or latest.get("status") in (None, "never"):
        return False, None, "no scan recorded"

    status = latest.get("status")
    age_hours = _scan_age_hours(latest)
    if status in ("failed", "stale_data"):
        return False, age_hours, f"last scan {status}"
    if status == "running":
        if age_hours is not None and age_hours > 2:
            return False, age_hours, "scan running too long (likely hung)"
        return True, age_hours, "scan running"
    if age_hours is not None and age_hours > _scan_age_allowance_hours():
        return False, age_hours, f"last successful scan {age_hours:.0f}h ago"
    return True, age_hours, "ok"


def _scan_age_hours(scan_run: dict) -> float | None:
    finished_at = scan_run.get("finished_at") or scan_run.get("started_at")
    if not finished_at:
        return None

    try:
        scan_time = datetime.fromisoformat(finished_at)
    except ValueError:
        return None

    if scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - scan_time).total_seconds() / 3600.0


def _scan_age_allowance_hours() -> int:
    weekday = datetime.now(ZoneInfo("America/New_York")).weekday()
    if weekday == 0:
        return 74
    if weekday >= 5:
        return 80
    return 26


def _checks_are_ok(checks: dict) -> bool:
    return all(check.get("ok", True) for name, check in checks.items() if name != "ibkr")
