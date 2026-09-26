"""Scheduler misfire + boot catch-up guards.

APScheduler's default misfire_grace_time is 1 second, so a machine asleep (or
the service mid-restart) at the 18:00 ET slot silently lost the night's scan.
Two complementary fixes are pinned here: hours of misfire grace on the cron
jobs (process alive but late), and a boot-time catch-up that re-runs the last
weekday slot when it was never served (in-memory jobs have no misfire to fire
on restart).

"Served" means a scan run with status 'ok'. Measured 2026-09-05: the Thursday
18:00 ET scan was killed 27 seconds in by the operator's nightly power-off, and
the boot reconcile turned that row into 'failed'. The old catch-up saw a row
started at/after the slot and called the slot served, and the Saturday boot bailed
out on the weekday check — so the scan stayed lost the whole weekend.
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import services.scheduler as scheduler_mod

NY = ZoneInfo("America/New_York")

# 2026-07-02 is a Thursday; the default slot is 18:00 ET.
AFTER_SLOT = datetime(2026, 7, 2, 21, 30, tzinfo=NY)
BEFORE_SLOT = datetime(2026, 7, 2, 9, 0, tzinfo=NY)
SATURDAY = datetime(2026, 7, 4, 5, 19, tzinfo=NY)   # the real 2026-09-05 boot hour
SUNDAY = datetime(2026, 7, 5, 21, 30, tzinfo=NY)
MONDAY_MORNING = datetime(2026, 7, 6, 9, 0, tzinfo=NY)

# 18:00/18:05 ET == 22:00/22:05 UTC (EDT). scan_status writes UTC ISO stamps.
WED_SLOT_RUN = "2026-07-01T22:05:00+00:00"
THU_SLOT_RUN = "2026-07-02T22:05:00+00:00"
FRI_SLOT_RUN = "2026-07-03T22:05:00+00:00"


def run(started_at, status="ok"):
    return {"started_at": started_at, "status": status}


# ---- last_weekday_slot (pure) ----
def test_last_slot_is_today_once_todays_slot_has_passed():
    slot = scheduler_mod.last_weekday_slot(AFTER_SLOT, 18, 0)
    assert slot == datetime(2026, 7, 2, 18, 0, tzinfo=NY)


def test_last_slot_is_yesterday_before_todays_slot():
    slot = scheduler_mod.last_weekday_slot(BEFORE_SLOT, 18, 0)
    assert slot == datetime(2026, 7, 1, 18, 0, tzinfo=NY)


def test_last_slot_from_a_weekend_boot_is_friday():
    # The cron is mon-fri: Saturday and Sunday both look back at Friday.
    assert scheduler_mod.last_weekday_slot(SATURDAY, 18, 0) == datetime(
        2026, 7, 3, 18, 0, tzinfo=NY)
    assert scheduler_mod.last_weekday_slot(SUNDAY, 18, 0) == datetime(
        2026, 7, 3, 18, 0, tzinfo=NY)


def test_last_slot_from_a_monday_morning_boot_is_friday():
    assert scheduler_mod.last_weekday_slot(MONDAY_MORNING, 18, 0) == datetime(
        2026, 7, 3, 18, 0, tzinfo=NY)


# ---- _missed_last_weekday_slot (pure decision) ----
def test_missed_when_no_run_was_ever_recorded():
    assert scheduler_mod._missed_last_weekday_slot(AFTER_SLOT, [], 18, 0) is True


def test_missed_when_latest_run_predates_the_slot():
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run(WED_SLOT_RUN)], 18, 0) is True


def test_not_missed_when_a_successful_run_started_at_or_after_the_slot():
    # Any trigger counts — a manual scan after the slot serves it too.
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run(THU_SLOT_RUN)], 18, 0) is False


def test_a_run_started_exactly_at_the_slot_serves_it():
    # 22:00:00 UTC == 18:00:00 ET, the slot second itself.
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run("2026-07-02T22:00:00+00:00")], 18, 0) is False


def test_missed_when_the_slot_run_died_mid_flight():
    # The 2026-09-05 case on a weekday: the row IS at/after the slot, but the
    # power-off + boot reconcile left it 'failed'. It never produced setups.
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run(THU_SLOT_RUN, "failed")], 18, 0) is True


def test_missed_for_aborted_and_stale_data_too():
    for status in ("aborted", "stale_data", "running"):
        assert scheduler_mod._missed_last_weekday_slot(
            AFTER_SLOT, [run(THU_SLOT_RUN, status)], 18, 0) is True, status


def test_saturday_boot_after_a_killed_friday_run_is_missed():
    # The real bug: PC off at 01:00 local kills the Friday scan, next boot is
    # Saturday morning. The weekend must not swallow Friday's slot.
    assert scheduler_mod._missed_last_weekday_slot(
        SATURDAY, [run(FRI_SLOT_RUN, "failed")], 18, 0) is True


def test_saturday_boot_after_a_successful_friday_run_is_not_missed():
    assert scheduler_mod._missed_last_weekday_slot(
        SATURDAY, [run(FRI_SLOT_RUN)], 18, 0) is False


def test_sunday_boot_follows_the_same_friday_slot():
    assert scheduler_mod._missed_last_weekday_slot(
        SUNDAY, [run(FRI_SLOT_RUN, "failed")], 18, 0) is True
    assert scheduler_mod._missed_last_weekday_slot(
        SUNDAY, [run(FRI_SLOT_RUN)], 18, 0) is False


def test_weekend_boot_with_no_runs_at_all_is_missed():
    assert scheduler_mod._missed_last_weekday_slot(SATURDAY, [], 18, 0) is True


def test_monday_morning_boot_is_not_missed_when_friday_succeeded():
    # Before today's slot the cron still owns tonight's run; Friday's 'ok' is
    # the last weekday slot and it was served, so no catch-up may fire.
    assert scheduler_mod._missed_last_weekday_slot(
        MONDAY_MORNING, [run(FRI_SLOT_RUN)], 18, 0) is False


def test_morning_boot_is_missed_when_yesterdays_slot_was_never_served():
    # Same morning boot, but last night's scan died: catch it up now rather
    # than waiting out the day for tonight's cron.
    assert scheduler_mod._missed_last_weekday_slot(
        BEFORE_SLOT, [run(WED_SLOT_RUN, "failed")], 18, 0) is True


def test_a_later_failed_manual_run_does_not_unserve_a_successful_slot():
    # Rows arrive newest-first. The newest is a failed manual scan, but the
    # slot itself succeeded — looking only at the newest row would re-run it.
    runs = [run(THU_SLOT_RUN, "failed"), run(THU_SLOT_RUN)]
    assert scheduler_mod._missed_last_weekday_slot(AFTER_SLOT, runs, 18, 0) is False


def test_naive_started_at_is_treated_as_utc():
    # Legacy rows may lack tzinfo; scan_status always wrote UTC.
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run("2026-07-02T22:05:00")], 18, 0) is False
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run("2026-07-01T22:05:00")], 18, 0) is True


def test_unparseable_or_absent_started_at_counts_as_missed():
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run("not-a-date")], 18, 0) is True
    assert scheduler_mod._missed_last_weekday_slot(
        AFTER_SLOT, [run(None)], 18, 0) is True


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
    monkeypatch.setattr(scheduler_mod, "_missed_last_weekday_slot", lambda *a, **k: True)
    monkeypatch.setattr(scheduler_mod.scan_status, "recent_runs",
                        lambda limit=20, kind=None: [])
    sched = FakeScheduler()

    scheduler_mod._schedule_boot_catchup(sched, 18, 0, NY)

    assert len(sched.jobs) == 1
    assert sched.jobs[0]["id"] == "boot-catchup-scan"
    assert sched.jobs[0]["misfire_grace_time"] >= 3600
    # One fixed id + replace_existing = at most ONE catch-up job per boot, so a
    # slot that keeps failing (e.g. a provider outage) is retried once per boot,
    # never in a loop.
    assert sched.jobs[0]["replace_existing"] is True


def test_boot_catchup_is_a_noop_when_slot_was_served(monkeypatch):
    monkeypatch.setattr(scheduler_mod, "_missed_last_weekday_slot", lambda *a, **k: False)
    monkeypatch.setattr(scheduler_mod.scan_status, "recent_runs",
                        lambda limit=20, kind=None: [])
    sched = FakeScheduler()

    scheduler_mod._schedule_boot_catchup(sched, 18, 0, NY)

    assert sched.jobs == []


class _FrozenDatetime(datetime):
    """datetime with now() pinned to the Saturday-morning boot."""

    @classmethod
    def now(cls, tz=None):
        return SATURDAY


def test_boot_catchup_reads_scan_runs_and_decides_from_them(monkeypatch):
    # End-to-end through the real decision: a killed Friday run, weekend boot.
    monkeypatch.setattr(scheduler_mod.scan_status, "recent_runs",
                        lambda limit=20, kind=None: [run(FRI_SLOT_RUN, "failed")])
    monkeypatch.setattr(scheduler_mod, "datetime", _FrozenDatetime)
    sched = FakeScheduler()

    scheduler_mod._schedule_boot_catchup(sched, 18, 0, NY)

    assert [j["id"] for j in sched.jobs] == ["boot-catchup-scan"]


def test_boot_catchup_never_blocks_scheduler_start(monkeypatch):
    # A DB hiccup while checking the last run must not take down the scheduler.
    def _boom(limit=20, kind=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(scheduler_mod.scan_status, "recent_runs", _boom)
    sched = FakeScheduler()

    scheduler_mod._schedule_boot_catchup(sched, 18, 0, NY)  # must not raise

    assert sched.jobs == []
