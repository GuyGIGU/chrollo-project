"""Scheduler misfire + boot catch-up guards.

APScheduler's default misfire_grace_time is 1 second, so a machine asleep (or
the service mid-restart) at the 18:00 ET slot silently lost the night's scan.
Two complementary fixes are pinned here: hours of misfire grace on the cron
jobs (process alive but late), and a boot-time catch-up that re-runs today's
slot when the process was fully down at slot time (in-memory jobs have no
misfire to fire on restart).
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import services.scheduler as scheduler_mod

NY = ZoneInfo("America/New_York")

# 2026-07-02 is a Thursday; the default slot is 18:00 ET.
AFTER_SLOT = datetime(2026, 7, 2, 21, 30, tzinfo=NY)
BEFORE_SLOT = datetime(2026, 7, 2, 9, 0, tzinfo=NY)
SATURDAY = datetime(2026, 7, 4, 21, 30, tzinfo=NY)


# ---- _missed_todays_slot (pure decision) ----
def test_missed_when_slot_passed_and_no_run_ever():
    assert scheduler_mod._missed_todays_slot(AFTER_SLOT, None, 18, 0) is True


def test_missed_when_latest_run_predates_todays_slot():
    # Last run was yesterday evening (UTC ISO, as scan_status writes it).
    assert scheduler_mod._missed_todays_slot(
        AFTER_SLOT, "2026-07-01T22:05:00+00:00", 18, 0) is True


def test_not_missed_when_a_run_started_at_or_after_the_slot():
    # 18:05 ET == 22:05 UTC on 2026-07-02: the slot was served (any trigger —
    # a manual scan after the slot counts too).
    assert scheduler_mod._missed_todays_slot(
        AFTER_SLOT, "2026-07-02T22:05:00+00:00", 18, 0) is False


def test_not_missed_before_todays_slot():
    # The cron will handle today's slot; a morning boot must not double-run.
    assert scheduler_mod._missed_todays_slot(BEFORE_SLOT, None, 18, 0) is False


def test_not_missed_on_weekends():
    # The cron is mon-fri; Saturday has no slot to have missed.
    assert scheduler_mod._missed_todays_slot(SATURDAY, None, 18, 0) is False


def test_naive_started_at_is_treated_as_utc():
    # Legacy rows may lack tzinfo; scan_status always wrote UTC.
    assert scheduler_mod._missed_todays_slot(
        AFTER_SLOT, "2026-07-02T22:05:00", 18, 0) is False
    assert scheduler_mod._missed_todays_slot(
        AFTER_SLOT, "2026-07-01T22:05:00", 18, 0) is True


def test_unparseable_started_at_counts_as_missed():
    assert scheduler_mod._missed_todays_slot(AFTER_SLOT, "not-a-date", 18, 0) is True


# ---- wiring ----
class FakeScheduler:
    running = True

    def __init__(self, timezone=None):
        self.jobs = []

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append(kwargs)

    def start(self):
        pass


def test_start_scheduler_sets_hours_of_misfire_grace_on_both_jobs(monkeypatch):
    catchup_calls = []
    monkeypatch.setattr(scheduler_mod, "BackgroundScheduler", FakeScheduler)
    monkeypatch.setattr(scheduler_mod, "_scheduler", None)
    monkeypatch.setattr(scheduler_mod, "_schedule_boot_catchup",
                        lambda *a, **k: catchup_calls.append(a))

    scheduler_mod.start_scheduler()

    by_id = {kw["id"]: kw for kw in scheduler_mod._scheduler.jobs}
    assert by_id["daily-scan-and-forward-returns"]["misfire_grace_time"] >= 3600
    assert by_id["scan-health-watchdog"]["misfire_grace_time"] >= 3600
    assert len(catchup_calls) == 1  # the boot catch-up check always runs


def test_boot_catchup_schedules_one_shot_scan_when_slot_missed(monkeypatch):
    monkeypatch.setattr(scheduler_mod, "_missed_todays_slot", lambda *a, **k: True)
    monkeypatch.setattr(scheduler_mod.scan_status, "latest_run", lambda kind=None: None)
    sched = FakeScheduler()

    scheduler_mod._schedule_boot_catchup(sched, 18, 0, NY)

    assert len(sched.jobs) == 1
    assert sched.jobs[0]["id"] == "boot-catchup-scan"
    assert sched.jobs[0]["misfire_grace_time"] >= 3600


def test_boot_catchup_is_a_noop_when_slot_was_served(monkeypatch):
    monkeypatch.setattr(scheduler_mod, "_missed_todays_slot", lambda *a, **k: False)
    monkeypatch.setattr(scheduler_mod.scan_status, "latest_run", lambda kind=None: None)
    sched = FakeScheduler()

    scheduler_mod._schedule_boot_catchup(sched, 18, 0, NY)

    assert sched.jobs == []


def test_boot_catchup_never_blocks_scheduler_start(monkeypatch):
    # A DB hiccup while checking the last run must not take down the scheduler.
    def _boom(kind=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(scheduler_mod.scan_status, "latest_run", _boom)
    sched = FakeScheduler()

    scheduler_mod._schedule_boot_catchup(sched, 18, 0, NY)  # must not raise

    assert sched.jobs == []
