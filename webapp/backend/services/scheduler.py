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
# has no job memory at all — that case is covered by the boot catch-up below.
MISFIRE_GRACE_SECONDS = 4 * 3600


def is_running() -> bool:
    """True if the background scheduler is alive (used by /health)."""
    return bool(_scheduler and _scheduler.running)


def _missed_todays_slot(now: datetime, latest_started_at: str | None,
                        hour: int, minute: int) -> bool:
    """True when today's weekday scan slot has already passed and no scan run
    was recorded at/after it — i.e. the service was down (or the machine off)
    at slot time and the night's scan was lost. Pure (no I/O) for testability;
    ``now`` must be timezone-aware in the scheduler's America/New_York tz."""
    if now.weekday() >= 5:  # Sat/Sun: no slot today (cron is mon-fri)
        return False
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < slot:
        return False  # today's slot is still ahead; the cron will handle it
    if not latest_started_at:
        return True
    try:
        started = datetime.fromisoformat(latest_started_at)
    except ValueError:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return started < slot


def _schedule_boot_catchup(scheduler: BackgroundScheduler, hour: int, minute: int,
                           tz: ZoneInfo) -> None:
    """If the service boots after today's slot with no run recorded, run the
    missed scan once, shortly after boot. Never blocks scheduler start."""
    try:
        latest = scan_status.latest_run(kind="scan")
        started_at = latest.get("started_at") if latest else None
        if not _missed_todays_slot(datetime.now(tz), started_at, hour, minute):
            return
        log.warning(
            "boot catch-up: today's %02d:%02d ET scan slot passed with no run "
            "recorded — scheduling the missed scan", hour, minute,
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
    hour = int(getattr(settings, "SCAN_SCHEDULE_HOUR_ET", 18))
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
