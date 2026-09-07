"""Health report helpers for the FastAPI readiness endpoint."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from database import engine
from ibkr import get_ibkr_service
from services import scan_diagnosis, scan_status, scheduler


def build_health_report(screener_json_path: str) -> dict:
    checks = {}

    _add_db_check(checks)
    _add_scan_check(checks)
    _add_screener_data_check(checks, screener_json_path)
    _add_scheduler_check(checks)
    _add_ibkr_check(checks)
    failing = _describe_failing_checks(checks)

    return {
        "status": "ok" if not failing else "degraded",
        "app": "Chrollo API",
        "time": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        # WHICH checks are wrong, in order, already in plain words. The topbar
        # pill's tooltip and the diagnostics registry render this list verbatim
        # (EC-28): membership is a judgment, and it is made here once, not
        # re-derived from `checks` in frontend JS.
        "failing": failing,
        # The BINARY headline the operator actually decides on — re-run it, or
        # ping me. Resolved server-side for the same reason: the frontend renders
        # this word, it may never work it out (EC-28).
        "verdict": scan_diagnosis.overall_verdict(failing),
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
        # A short WINDOW, not one row: the repeat escalation has to see whether
        # this same failure already came back, and the pill must reach the same
        # verdict the registry shows for that run.
        recent = scan_status.recent_runs(scan_diagnosis.REPEAT_ESCALATION)
    except Exception:
        recent = []
    # The run's own resolved verdict/reason, through the SAME function both
    # scan-status routes use, so the pill's tooltip and the diagnostics registry
    # cannot tell the operator two different stories.
    latest = scan_diagnosis.describe_runs(recent)[0] if recent else {}

    scan_ok, age_hours, detail = _scan_freshness(latest)
    checks["last_scan"] = {
        "ok": scan_ok,
        "status": latest.get("status", "never"),
        "finished_at": latest.get("finished_at"),
        "n_setups": latest.get("n_setups"),
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "detail": detail,
        "verdict": latest.get("verdict"),
        "reason": latest.get("reason"),
        "solution": latest.get("solution"),
    }


def _describe_failing_checks(checks: dict) -> list[dict]:
    """Give every failing non-ibkr check a verdict plus a plain-words label,
    reason and proposed solution, resolved HERE so no frontend has to derive one.

    Returns the same checks as an ordered list for the wire.
    """
    failing = []
    for name, check in _operator_relevant_failures(checks).items():
        described = scan_diagnosis.describe_health_check(name, check)
        # A run-level reason already resolved above is more specific than the
        # generic check reason, so it wins — and it brings its verdict with it,
        # or an escalated repeat would be softened back by the generic table.
        if check.get("reason"):
            described.pop("reason")
            described.pop("solution", None)
            described.pop("verdict", None)
        check.update(described)
        failing.append({
            "key": name,
            "label": check.get("label", name),
            "verdict": check.get("verdict"),
            "reason": check.get("reason") or check.get("detail"),
            "solution": check.get("solution"),
        })
    return failing


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
    if status in ("failed", "stale_data", "aborted"):
        return False, age_hours, f"last scan {status}"
    if status == "running":
        # The watchdog's hang threshold, imported — not a third copy of "2".
        if age_hours is not None and age_hours > scan_diagnosis.HUNG_RUNNING_HOURS:
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


def _operator_relevant_failures(checks: dict) -> dict:
    """The failing checks that make the app Degraded — the ONE place that rule
    is written. ibkr is exempt: the broker link is manual and read-only, so a
    disconnected session is a normal state, not a fault.

    Both the degraded verdict and the plain-words descriptions resolve through
    this, so a newly exempted check cannot end up degrading the app while
    carrying no reason, or carrying prose while degrading nothing.
    """
    return {
        name: check for name, check in checks.items()
        if name != "ibkr" and not check.get("ok", True)
    }
