"""In-process broker-free scheduler for unattended scans."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services.core_settings import load_core_settings
from services.scan_runner import run_scheduled_scan_and_forward_returns
from services.scan_watchdog import run_scan_health_watchdog

log = logging.getLogger("chrollo.scheduler")
_scheduler: BackgroundScheduler | None = None


def is_running() -> bool:
    """True if the background scheduler is alive (used by /health)."""
    return bool(_scheduler and _scheduler.running)


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
    )
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
