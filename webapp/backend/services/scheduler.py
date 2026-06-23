"""In-process broker-free scheduler for unattended scans."""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.pipeline.market_calendar import is_trading_session
from services.core_settings import load_core_settings
from services.scan_runner import run_scheduled_scan_and_forward_returns
from services.scan_watchdog import run_scan_health_watchdog
from services.trade_alerts import (
    record_trade_alert_error,
    record_trade_alert_skip,
    run_trade_alert_sweep,
)

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
    trade_alerts_enabled = bool(getattr(settings, "TRADE_ALERTS_ENABLED", False))
    if trade_alerts_enabled:
        poll_minutes = max(1, int(getattr(settings, "TRADE_ALERT_POLL_MINUTES", 5) or 5))
        scheduler.add_job(
            run_trade_alert_sweep_if_due,
            IntervalTrigger(minutes=poll_minutes, timezone=tz),
            id="trade-alert-sweep",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
    _scheduler = scheduler
    log.info("scheduled scan enabled for %02d:%02d America/New_York (+ morning health watchdog)", hour, minute)
    if trade_alerts_enabled:
        log.info("trade alert sweep enabled every %d minute(s) during regular market hours", poll_minutes)


def stop_scheduler() -> None:
    global _scheduler
    if not _scheduler:
        return
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
    log.info("scheduled scan stopped")


def run_trade_alert_sweep_if_due() -> None:
    settings = load_core_settings()
    enabled = bool(getattr(settings, "TRADE_ALERTS_ENABLED", False))
    if not enabled:
        record_trade_alert_skip("disabled", enabled=False, market_window=False)
        return
    market_window = _is_trade_alert_window()
    if not market_window:
        record_trade_alert_skip("outside_market_hours", enabled=True, market_window=False)
        return
    try:
        sent = run_trade_alert_sweep()
        if sent:
            log.info("trade alert sweep sent %d alert(s)", sent)
    except Exception as exc:
        record_trade_alert_error(exc, enabled=True, market_window=True)
        log.exception("trade alert sweep failed")


def _is_trade_alert_window(now_et: datetime | None = None) -> bool:
    tz = ZoneInfo("America/New_York")
    now_et = now_et or datetime.now(tz)
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=tz)
    else:
        now_et = now_et.astimezone(tz)

    if not is_trading_session(now_et.date()):
        return False
    minutes = now_et.hour * 60 + now_et.minute
    return 9 * 60 + 30 <= minutes < 16 * 60
