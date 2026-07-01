"""Health watchdog for scheduled scan + forward-return maturation runs."""
from __future__ import annotations

from datetime import datetime, timezone

from services import scan_status
from services.scan_runner import alert_if_needed

# A run left 'running' longer than this almost certainly means the process was
# killed between start_run and finish_run (crash / OOM / power loss). Scans and
# maturation both complete in minutes, so surface a hang promptly instead of
# letting the generic staleness path mislabel it as stale_data ~a day later.
HUNG_RUNNING_HOURS = 2.0
# A kind is "stale" once its newest run is older than this. Both the scan and the
# maturation tick are expected at least once per weekday; 26h spans a normal
# overnight gap without false alarms.
STALE_AFTER_HOURS = 26.0


def run_scan_health_watchdog() -> None:
    """Alert when the latest scan OR forward-return maturation failed, hung, or
    went stale (and, for scans, never ran at all).

    Maturation is checked as its OWN kind so a night where the scan succeeds but
    the forward-return backfill throws or never ticks can no longer hide — that
    silent decoupling was the historical stall root cause. Absent maturation
    history is NOT alerted (a fresh install has none yet); a failed/hung/stale one
    is.
    """
    _check_kind("scan", alert_when_absent=True)
    _check_kind("maturation", alert_when_absent=False)


def _check_kind(kind: str, *, alert_when_absent: bool) -> None:
    latest = scan_status.latest_run(kind=kind)
    if not latest:
        if alert_when_absent:
            alert_if_needed("watchdog", "failed", None, f"no {kind} runs recorded at all")
        return

    status = latest.get("status")
    if status in {"failed", "stale_data"}:
        alert_if_needed("watchdog", status, latest.get("n_setups"), latest.get("error"))
        return

    age_hours = _scan_age_hours(latest)

    if status == "running":
        # A run stuck 'running' well past any plausible duration was almost
        # certainly killed mid-flight. The boot reconcile clears these on the next
        # backend restart; the watchdog surfaces one that is hanging RIGHT NOW.
        if age_hours is not None and age_hours > HUNG_RUNNING_HOURS:
            alert_if_needed(
                "watchdog",
                "failed",
                latest.get("n_setups"),
                f"{kind} stuck 'running' for {age_hours:.0f}h (process likely died mid-run)",
            )
        return

    if age_hours is None or age_hours <= STALE_AFTER_HOURS:
        return

    alert_if_needed(
        "watchdog",
        "stale_data",
        latest.get("n_setups"),
        f"no fresh {kind} in {age_hours:.0f}h (last status={status})",
    )


def _scan_age_hours(scan_run: dict) -> float | None:
    # A completed run has finished_at; a still-'running' row has only started_at,
    # which is exactly the age we want for hung detection.
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
