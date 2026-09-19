"""In-process broker-free scheduler for unattended scans."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services import scan_status
from services.core_settings import load_core_settings
from services.scan_runner import run_scheduled_scan_and_forward_returns
from services.scan_watchdog import run_scan_health_watchdog

log = logging.getLogger("chrollo.scheduler")
_scheduler: BackgroundScheduler | None = None

# APScheduler's default misfire_grace_time is 1 second: a machine asleep (or a
# service mid-restart) at the slot time silently LOSES that run. With hours of
# grace, a wake/late tick still fires the missed job. This covers "process
# alive but couldn't fire on time"; a process that was fully DOWN at slot time
# has no job memory at all, and a scan killed mid-flight leaves only a 'failed'
# row — both of those are covered by the boot catch-up below.
MISFIRE_GRACE_SECONDS = 4 * 3600


def is_running() -> bool:
    """True if the background scheduler is alive (used by /health)."""
    return bool(_scheduler and _scheduler.running)


def last_weekday_slot(now: datetime, hour: int, minute: int) -> datetime:
    """The most recent weekday scan slot at/before ``now``: today's if it has
    already passed, otherwise the previous weekday's. The cron is mon-fri, so a
    weekend boot looks back at Friday's slot. Pure; ``now`` must be
    timezone-aware in the scheduler's America/New_York tz.

    PUBLIC because it is the one home for "when should a scan have started"
    (EC-3): the boot catch-up below and the diagnostics registry's missed-slot
    notice must agree, and they answered it separately before this merge."""
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if slot > now:
        slot -= timedelta(days=1)
    while slot.weekday() >= 5:  # Sat/Sun have no slot — step back to Friday
        slot -= timedelta(days=1)
    return slot


def _started_at_or_after(started_at: str | None, slot: datetime) -> bool:
    """True when a run's ``started_at`` (UTC ISO, as scan_status writes it) is
    at/after ``slot``. An absent or unparseable stamp cannot vouch for the slot."""
    if not started_at:
        return False
    try:
        started = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        return False
    if started.tzinfo is None:  # legacy rows may lack tzinfo; they were UTC
        started = started.replace(tzinfo=timezone.utc)
    return started >= slot


def _missed_last_weekday_slot(now: datetime, runs: list[dict],
                              hour: int, minute: int) -> bool:
    """True when the most recent weekday scan slot has no SUCCESSFUL scan run
    at/after it — the service was down (or the machine off) at slot time, or a
    scan started and died mid-flight. Only status 'ok' vouches for the slot;
    'failed', 'aborted', 'stale_data' and a total absence of runs all count as
    missed. ``runs`` is scan_status.recent_runs(kind='scan') — the newest rows
    are enough because only runs at/after the slot can vouch for it. Pure (no
    I/O) for testability; ``now`` must be timezone-aware in America/New_York."""
    slot = last_weekday_slot(now, hour, minute)
    return not any(
        run.get("status") == "ok" and _started_at_or_after(run.get("started_at"), slot)
        for run in runs
    )


def _schedule_boot_catchup(scheduler: BackgroundScheduler, hour: int, minute: int,
                           tz: ZoneInfo) -> None:
    """If the service boots with the last weekday slot unserved, run the missed
    scan once, shortly after boot. Never blocks scheduler start."""
    try:
        now = datetime.now(tz)
        runs = scan_status.recent_runs(limit=20, kind="scan")
        if not _missed_last_weekday_slot(now, runs, hour, minute):
            return
        log.warning(
            "boot catch-up: the %s %02d:%02d ET scan slot has no successful run "
            "— scheduling the missed scan",
            last_weekday_slot(now, hour, minute).date().isoformat(), hour, minute,
        )
        scheduler.add_job(
            run_scheduled_scan_and_forward_returns,
            "date",
            # A short delay lets the service finish booting before the scan
            # subprocess spawns.
            run_date=datetime.now(tz) + timedelta(minutes=2),
            id="boot-catchup-scan",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )
    except Exception:
        log.exception("boot catch-up check failed (scheduler continues without it)")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    settings = load_core_settings()
    hour = int(getattr(settings, "SCAN_SCHEDULE_HOUR_ET", 17))
    minute = int(getattr(settings, "SCAN_SCHEDULE_MINUTE_ET", 0))
    tz = ZoneInfo("America/New_York")

    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        run_scheduled_scan_and_forward_returns,
        CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute, timezone=tz),
        id="daily-scan-and-forward-returns",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=MISFIRE_GRACE_SECONDS,
    )
    # Self-healing heartbeat: each weekday morning (Tue–Sat) verify the prior
    # evening's scan actually ran and succeeded. Scans only alert reactively
    # when they run, so this catches the case where a run never happened at all
    # (service was down, scheduler died) — alerting via the same webhook plumbing.
    scheduler.add_job(
        run_scan_health_watchdog,
        CronTrigger(day_of_week="tue-sat", hour=8, minute=0, timezone=tz),
        id="scan-health-watchdog",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=MISFIRE_GRACE_SECONDS,
    )
    _schedule_boot_catchup(scheduler, hour, minute, tz)
    scheduler.start()
    _scheduler = scheduler
    log.info("scheduled scan enabled for %02d:%02d America/New_York (+ morning health watchdog)", hour, minute)


def stop_scheduler() -> None:
    global _scheduler
    if not _scheduler:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
    log.info("scheduled scan stopped")
