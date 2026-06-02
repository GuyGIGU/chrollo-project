"""Health watchdog for scheduled scan runs."""
from __future__ import annotations

from datetime import datetime, timezone

from services import scan_status
from services.scan_runner import alert_if_needed


def run_scan_health_watchdog() -> None:
    """Alert when the latest scan failed, went stale, or never ran."""
    latest = scan_status.latest_run()
    if not latest:
        alert_if_needed("watchdog", "failed", None, "no scan runs recorded at all")
        return

    status = latest.get("status")
    if status in {"failed", "stale_data"}:
        alert_if_needed("watchdog", status, latest.get("n_setups"), latest.get("error"))
        return

    age_hours = _scan_age_hours(latest)
    if age_hours is None or age_hours <= 26:
        return

    alert_if_needed(
        "watchdog",
        "stale_data",
        latest.get("n_setups"),
        f"no fresh scan in {age_hours:.0f}h (last status={status})",
    )


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
