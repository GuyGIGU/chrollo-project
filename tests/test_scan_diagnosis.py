"""Guards for the scan-failure diagnosis: WHY a run died, and what to do.

The rule these pin is the anti-lie rule. "The computer was shut down" may only
be said when a Windows machine-down record actually falls inside the run's own
live window; every other branch must land somewhere honest and DIFFERENT.

Tests 1-8 are pure-function tests, so they run on a CI box that has neither
wevtutil nor a Windows event log.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import services.scan_diagnosis as diag  # noqa: E402
from services.startup import _MIGRATIONS  # noqa: E402

UTC = timezone.utc

# The real 2026-09-05 incident, to the microsecond: scan_runs row 277 started
# 22:00:01.53Z, the orphan was detected 29s later at 22:00:30.46Z, and the
# Windows User32 1074 "power off initiated" record sits at 22:00:25.51Z.
INCIDENT_START = "2026-09-04T22:00:01.532328+00:00"
INCIDENT_DETECTED = "2026-09-04T22:00:30.462683+00:00"
INCIDENT_1074 = datetime(2026, 9, 4, 22, 0, 25, 507976, tzinfo=UTC)
INCIDENT_NOW = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
# The last machine boot as it stood at reconcile time: the MORNING BEFORE the
# run started. This is the value the brief's original rule would have compared.
INCIDENT_BOOT = datetime(2026, 9, 4, 6, 49, tzinfo=UTC)


def ev(event_id, when):
    return {"event_id": event_id, "time": when}


# ------------------------------------------------------------ the rule ----

def test_shutdown_inside_the_window_names_the_power_off():
    """THE REGRESSION PIN for the falsified boot-time design.

    A classifier written as the brief first proposed it — "did the machine boot
    AFTER the run started?" — returns FALSE here (INCIDENT_BOOT precedes
    INCIDENT_START, because NSSM restarted uvicorn inside the dying Windows
    session and the reconcile ran on the SAME boot). Replacing the body of
    classify_interrupted with that rule must turn this test red.
    """
    kind = diag.classify_interrupted(
        INCIDENT_START, INCIDENT_DETECTED,
        [ev(1074, INCIDENT_1074)], INCIDENT_BOOT, INCIDENT_NOW,
    )
    assert kind == "interrupted_shutdown"
    assert INCIDENT_BOOT < datetime.fromisoformat(INCIDENT_START)  # the falsified premise

    described = diag.describe_run({"status": "failed", "failure_kind": kind})
    assert "shut down" in described["reason"]
    assert "process died" not in described["reason"]
    assert described["solution"]


def test_readable_log_with_no_shutdown_never_claims_the_computer_was_off():
    """THE ANTI-LIE GUARD. An empty (but successfully read) log plus a machine
    that has not rebooted since the run began = the service restarted."""
    start = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)
    kind = diag.classify_interrupted(
        start.isoformat(), (start + timedelta(seconds=30)).isoformat(),
        [], start - timedelta(hours=12), start + timedelta(hours=1),
    )
    assert kind == "interrupted_service_only"
    reason = diag.describe_run({"status": "failed", "failure_kind": kind})["reason"]
    assert "shut down" not in reason
    assert "power" not in reason


def test_unreadable_log_is_a_distinct_refusal_from_an_empty_one():
    """events=None (could not look) and events=[] (looked, found nothing) are
    different facts; collapsing them is the most dangerous mutation here."""
    start = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)
    args = ((start + timedelta(seconds=30)).isoformat(),)
    unreadable = diag.classify_interrupted(
        start.isoformat(), *args, None, start - timedelta(hours=12), start + timedelta(hours=1))
    empty = diag.classify_interrupted(
        start.isoformat(), *args, [], start - timedelta(hours=12), start + timedelta(hours=1))
    assert unreadable == "interrupted_unknown"
    assert empty != unreadable


def test_no_shutdown_but_rebooted_since_refuses_the_stayed_on_claim():
    """The boot clock may only REFUSE. If the machine has restarted since the
    run began we cannot say it stayed on, so the row reads 'not recorded'."""
    start = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)
    kind = diag.classify_interrupted(
        start.isoformat(), (start + timedelta(seconds=30)).isoformat(),
        [], start + timedelta(hours=9), start + timedelta(hours=10),
    )
    assert kind == "interrupted_unrecorded"


def test_shutdown_outside_the_bounded_window_is_ignored():
    """The false positive the boot-time rule would have produced: the scan
    crashed alone at 01:00, the machine stayed up all night, and a normal
    reboot at 09:00 must NOT be reported as killing it."""
    start = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)
    kind = diag.classify_interrupted(
        start.isoformat(), (start + timedelta(days=6)).isoformat(),
        [ev(1074, start + timedelta(hours=8))],
        start - timedelta(hours=12), start + timedelta(days=6, hours=1),
    )
    assert kind != "interrupted_shutdown"


def test_power_loss_events_are_not_reported_as_a_deliberate_shutdown():
    start = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)
    for event_id in (6008, 41):
        kind = diag.classify_interrupted(
            start.isoformat(), (start + timedelta(seconds=30)).isoformat(),
            [ev(event_id, start + timedelta(seconds=20))], None, start + timedelta(hours=1),
        )
        assert kind == "interrupted_power_loss", event_id


def test_evidence_horizon_closes_an_old_row_without_asking_windows():
    calls = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    kind = diag.classify_interrupted(
        start.isoformat(), (start + timedelta(seconds=30)).isoformat(),
        calls, None, start + timedelta(days=400),
    )
    assert kind == "interrupted_unrecorded"


def test_unparseable_started_at_never_raises():
    assert diag.classify_interrupted(
        "not-a-date", None, [], None, datetime.now(UTC)) == "interrupted_unknown"


def test_window_grants_grace_past_the_detection_stamp_but_caps_a_late_one():
    start = datetime.fromisoformat(INCIDENT_START)
    detected = datetime.fromisoformat(INCIDENT_DETECTED)
    end = diag.evidence_window_end(start, detected)
    # The 1074 is inside, and the end sits past the detection stamp (Windows'
    # own "shutting down" record landed a second AFTER it).
    assert start <= INCIDENT_1074 <= end
    assert end > detected
    # A reconcile six days late (live rows 47/48) may not borrow six days of
    # unrelated evening shutdowns.
    late = diag.evidence_window_end(start, start + timedelta(days=6))
    assert late - start <= timedelta(hours=diag.HUNG_RUNNING_HOURS, seconds=120)


# --------------------------------------------------------------- prose ----

def test_every_failure_kind_has_a_reason_and_a_solution():
    for kind in diag.FAILURE_KINDS:
        described = diag.describe_run({"status": "failed", "failure_kind": kind})
        assert described["reason"], kind
        assert described["solution"], kind


def test_unrecognised_legacy_error_still_gets_a_remedy():
    # Two live rows carry this string; its writer no longer exists in the code.
    described = diag.describe_run(
        {"status": "expired", "error": "scan status expired before completion"})
    assert described["reason"]
    assert described["solution"]


def test_a_reported_program_error_never_reaches_the_interruption_ladder():
    described = diag.describe_run(
        {"status": "failed", "error": 'a(tickers) /   File "...data.py", line 573'})
    assert described["reason"] == "The scan hit a program error and stopped."
    assert "computer" not in described["reason"]


def test_legacy_reconcile_text_bridges_to_the_pending_kind():
    described = diag.describe_run(
        {"status": "failed",
         "error": "process died before completion (reconciled at boot)"})
    assert described["reason"] == diag.REASONS[diag.PENDING_KIND]


def test_describe_run_is_pure(monkeypatch):
    """It rides the /health poll and both scan-status routes, so a future edit
    must not be able to put a subprocess or a query on that path."""
    import subprocess

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("describe_run must not shell out")

    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(diag, "collect_machine_down_events", explode)
    monkeypatch.setattr(diag, "_pending_rows", explode)
    for kind in diag.FAILURE_KINDS:
        assert diag.describe_run({"status": "failed", "failure_kind": kind})["reason"]


def test_ok_and_running_rows_carry_no_reason():
    for status in ("ok", "running", "never"):
        assert diag.describe_run({"status": status}) == {"reason": None, "solution": None}


# ------------------------------------------------------------ evidence ----

def test_events_are_parsed_from_xml_in_utc():
    """/f:text prints its Date header in LOCAL time with a bogus 'Z' suffix;
    parsing that shape instead would mis-window every event by the machine's
    UTC offset (three hours here)."""
    xml = (
        "<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'>"
        "<System><Provider Name='User32'/><EventID Qualifiers='32768'>1074</EventID>"
        "<TimeCreated SystemTime='2026-09-04T22:00:25.5079768Z'/>"
        "<Channel>System</Channel></System>"
        "<EventData><Data Name='param5'>power off</Data></EventData></Event>"
    )
    events = diag.parse_events(xml)
    assert len(events) == 1
    assert events[0]["event_id"] == 1074
    assert events[0]["time"] == INCIDENT_1074


def test_unparseable_event_output_is_unreadable_not_empty():
    assert diag.parse_events("<Event><broken") is None


def test_collector_degrades_when_wevtutil_is_missing(monkeypatch):
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("wevtutil")))
    now = datetime.now(UTC)
    assert diag.collect_machine_down_events(now, now) is None


def test_collector_degrades_on_timeout(monkeypatch):
    import subprocess

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("wevtutil", 3)

    monkeypatch.setattr(subprocess, "run", timeout)
    now = datetime.now(UTC)
    assert diag.collect_machine_down_events(now, now) is None


# ---------------------------------------------------------- resolution ----

@pytest.fixture()
def runs_engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'runs.db'}")
    create = next(s for s in _MIGRATIONS if "CREATE TABLE IF NOT EXISTS scan_runs" in s)
    with eng.begin() as conn:
        conn.execute(text(create))
    return eng


def _insert(eng, started_at, finished_at, failure_kind=diag.PENDING_KIND):
    with eng.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO scan_runs (started_at, finished_at, status, trigger, "
                "kind, failure_kind, error) VALUES (:s, :f, 'failed', 'scheduled', "
                "'scan', :k, :e)"
            ),
            {"s": started_at, "f": finished_at, "k": failure_kind,
             "e": diag.RECONCILE_MARKER},
        )
        return int(result.lastrowid)


def _kind_of(eng, run_id):
    with eng.connect() as conn:
        return conn.execute(
            text("SELECT failure_kind FROM scan_runs WHERE id = :id"), {"id": run_id}
        ).scalar()


def test_resolution_is_stamped_once_and_survives_the_evidence_rolling(runs_engine, monkeypatch):
    """The System log is circular. The evidence rots; the ANSWER must not."""
    now = datetime.now(UTC)
    start = now - timedelta(hours=3)
    run_id = _insert(runs_engine, start.isoformat(), (start + timedelta(seconds=30)).isoformat())

    monkeypatch.setattr(
        diag, "collect_machine_down_events",
        lambda *a: [ev(1074, start + timedelta(seconds=20))])
    assert diag.resolve_pending(runs_engine) == 1
    assert _kind_of(runs_engine, run_id) == "interrupted_shutdown"

    # Same row, later, with the record gone from the log.
    monkeypatch.setattr(diag, "collect_machine_down_events", lambda *a: [])
    assert diag.resolve_pending(runs_engine) == 0
    assert _kind_of(runs_engine, run_id) == "interrupted_shutdown"


def test_a_resolved_row_is_never_offered_for_re_resolution(runs_engine):
    """Layer one of the stamp-once guarantee: the pending SELECT."""
    now = datetime.now(UTC)
    start = now - timedelta(hours=3)
    _insert(runs_engine, start.isoformat(), start.isoformat(),
            failure_kind="interrupted_shutdown")

    assert diag._pending_rows(runs_engine, 10) == []


def test_stamping_never_overwrites_a_row_that_already_has_a_cause(runs_engine):
    """Layer two, pinned on its own so it cannot rot behind layer one: even
    handed a resolved row directly, the UPDATE refuses to rewrite it."""
    now = datetime.now(UTC)
    start = now - timedelta(hours=3)
    run_id = _insert(runs_engine, start.isoformat(), start.isoformat(),
                     failure_kind="interrupted_shutdown")

    assert diag._stamp_kind(runs_engine, run_id, "interrupted_unrecorded") == 0
    assert _kind_of(runs_engine, run_id) == "interrupted_shutdown"


def test_resolution_leaves_a_row_pending_when_the_log_cannot_be_read(runs_engine, monkeypatch):
    now = datetime.now(UTC)
    start = now - timedelta(hours=3)
    run_id = _insert(runs_engine, start.isoformat(), (start + timedelta(seconds=30)).isoformat())
    monkeypatch.setattr(diag, "collect_machine_down_events", lambda *a: None)

    assert diag.resolve_pending(runs_engine) == 0
    assert _kind_of(runs_engine, run_id) == diag.PENDING_KIND


def test_resolution_never_raises_when_the_collector_throws(runs_engine, monkeypatch):
    now = datetime.now(UTC)
    start = now - timedelta(hours=3)
    run_id = _insert(runs_engine, start.isoformat(), (start + timedelta(seconds=30)).isoformat())

    def boom(*a):
        raise RuntimeError("event log service is stopped")

    monkeypatch.setattr(diag, "collect_machine_down_events", boom)
    assert diag.resolve_pending(runs_engine) == 0
    assert _kind_of(runs_engine, run_id) == diag.PENDING_KIND


def test_an_old_pending_row_is_closed_out_without_reading_the_log(runs_engine, monkeypatch):
    start = datetime.now(UTC) - timedelta(days=400)
    run_id = _insert(runs_engine, start.isoformat(), (start + timedelta(seconds=30)).isoformat())

    def explode(*a):  # pragma: no cover - must never run
        raise AssertionError("an out-of-horizon row must not query the event log")

    monkeypatch.setattr(diag, "collect_machine_down_events", explode)
    assert diag.resolve_pending(runs_engine) == 1
    assert _kind_of(runs_engine, run_id) == "interrupted_unrecorded"


# --------------------------------------------------------- missed slot ----

def test_missed_slot_notice_speaks_up_when_no_run_covers_the_passed_slot():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    now = datetime(2026, 9, 7, 10, 0, tzinfo=ny)  # Monday morning
    notice = diag.missed_slot_notice("2026-09-03T22:05:00+00:00", now, 18, 0)
    assert notice and "No scan ran" in notice


def test_missed_slot_notice_is_silent_when_the_slot_was_served():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    now = datetime(2026, 9, 7, 10, 0, tzinfo=ny)
    # Friday 2026-09-04 18:05 ET == 22:05 UTC — after the last passed slot.
    assert diag.missed_slot_notice("2026-09-04T22:05:00+00:00", now, 18, 0) is None


# -------------------------------------------------------- health checks ----

def test_every_non_ibkr_health_check_has_plain_words():
    for name in ("db", "last_scan", "screener_data", "scheduler"):
        described = diag.describe_health_check(name, {"ok": False})
        assert described["label"] and described["label"] != name
        assert described["reason"] and described["solution"]
