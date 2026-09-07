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


def test_a_shutdown_far_from_the_detection_stamp_is_not_blamed_for_the_death():
    """THE OVER-CLAIM PIN, from this machine's real habit (review 2026-09-07).

    All eight of the operator's recent power-offs land inside the 18:00 scan's
    own two-hour cap, so a window anchored on started_at alone blamed the
    nightly shutdown for ANY orphan detected late. Here the scan dies alone at
    22:05, the dashboard stays up, the operator powers off at 22:42 as he does
    every night, and the orphan is only detected at next morning's boot. The
    shutdown is real, but it is not what killed the run, and the remedy ("leave
    the computer on past the scan") would not have helped.
    """
    start = datetime(2026, 9, 6, 22, 0, 1, tzinfo=UTC)
    detected = datetime(2026, 9, 7, 6, 10, tzinfo=UTC)  # next boot's reconcile
    habitual_power_off = datetime(2026, 9, 6, 22, 42, 27, tzinfo=UTC)

    kind = diag.classify_interrupted(
        start.isoformat(), detected.isoformat(),
        [ev(1074, habitual_power_off)],
        datetime(2026, 9, 7, 6, 9, tzinfo=UTC),  # rebooted since: cannot say it stayed on
        detected + timedelta(hours=1),
    )
    assert kind == "interrupted_unrecorded"
    reason = diag.describe_run({"status": "failed", "failure_kind": kind})["reason"]
    assert "shut down" not in reason


def test_a_machine_down_record_is_never_called_a_deliberate_shutdown_on_its_own():
    """6008 / Kernel-Power 41 are stamped at the NEXT boot, so their timestamp is
    the reboot moment, not the crash. They are no longer read at all — and they
    must never be announced as "the computer was shut down"."""
    start = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)
    for event_id in (6008, 41):
        kind = diag.classify_interrupted(
            start.isoformat(), (start + timedelta(seconds=30)).isoformat(),
            [ev(event_id, start + timedelta(seconds=20))], None, start + timedelta(hours=1),
        )
        assert kind != "interrupted_shutdown", event_id
        reason = diag.describe_run({"status": "failed", "failure_kind": kind})["reason"]
        assert "shut down" not in reason, event_id


def test_a_run_past_the_evidence_horizon_is_closed_out_as_unrecorded():
    """The System log is circular, so an old row is closed out rather than
    re-asked against a decaying log. The shutdown record below is squarely
    inside the run's own window: the HORIZON is the only thing that may
    suppress the claim."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    detected = start + timedelta(seconds=30)
    kind = diag.classify_interrupted(
        start.isoformat(), detected.isoformat(),
        [ev(1074, start + timedelta(seconds=20))], None, start + timedelta(days=400),
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

def test_every_failure_kind_has_a_reason_and_a_solution_for_every_job():
    """Crossed on BOTH axes. The boot reconcile stamps outcome-backfill and
    download rows exactly as it stamps scans, and the registry lists all three —
    so each row must name ITS job and carry the instruction that re-runs THAT
    job, not "press Evaluate" under a row headed Outcome backfill."""
    for job in diag.JOB_NAMES:
        for kind in diag.FAILURE_KINDS:
            described = diag.describe_run(
                {"status": "failed", "kind": job, "failure_kind": kind})
            assert described["reason"] and described["solution"], (job, kind)
            assert diag.JOB_NAMES[job] in described["reason"].lower(), (job, kind)
            assert diag.JOB_RERUN[job] in described["solution"], (job, kind)


def test_every_job_kind_has_a_name_and_a_way_to_re_run_it():
    assert set(diag.JOB_NAMES) == set(diag.JOB_RERUN)


def test_no_solution_hardcodes_the_scan_hour():
    """The slot is a setting the operator is being asked to move (docs/asks.md),
    and the missed-slot notice reads it live. A clock time copied into this
    prose starts lying the moment he moves it."""
    import re

    for kind in diag.FAILURE_KINDS:
        solution = diag.describe_run(
            {"status": "failed", "failure_kind": kind})["solution"]
        assert not re.search(r"\d{1,2}:\d{2}", solution), kind


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
    assert described["reason"].startswith("The scan stopped before it finished")
    assert "has not worked out why yet" in described["reason"]


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


def test_collector_refuses_when_wevtutil_exits_non_zero(monkeypatch):
    """THE ANTI-LIE GUARD AT THE COLLECTOR. wevtutil writes its failure to
    STDERR, so a failed read leaves stdout EMPTY — and empty stdout parses
    cleanly to [], the value that means "we looked and the machine stayed up".
    The return code is the only thing between those two facts, and its removal
    makes the feature's one negative claim fire on a read that never happened:
    the Event Log service is measured to be already stopped in exactly the
    dying-session path resolve_pending runs in."""
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0] if a else [], 1, "", "Failed to open log System. Access is denied."))
    now = datetime.now(UTC)
    assert diag.collect_machine_down_events(now, now) is None


def test_empty_wevtutil_output_means_found_nothing_not_unreadable(monkeypatch):
    """The other half of that pair, pinned explicitly: a successful read with no
    matching record is [], never None."""
    import subprocess

    assert diag.parse_events("") == []
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0] if a else [], 0, "", ""))
    now = datetime.now(UTC)
    assert diag.collect_machine_down_events(now, now) == []


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


def test_the_last_scan_check_describes_its_own_state():
    """THE FALSE-SENTENCE PIN. The last-scan check fails in four shapes and in
    three of them the scan itself finished perfectly. The worst is the
    morning-after state of the operator's own incident: the machine was off, so
    NO scan ran, and the newest row is yesterday's clean scan aged past its
    allowance. Saying "the most recent scan did not finish cleanly" there
    describes a run that wrote 12 setups."""
    stale = diag.describe_health_check(
        "last_scan", {"ok": False, "status": "ok",
                      "detail": "last successful scan 39h ago"})["reason"]
    assert "did not finish cleanly" not in stale
    assert "finished cleanly" in stale and "no scan has run since" in stale
    assert "39h ago" in stale  # the measured detail still travels

    never = diag.describe_health_check(
        "last_scan", {"ok": False, "status": "never", "detail": "no scan recorded"})["reason"]
    assert "did not finish cleanly" not in never
    assert "No scan has ever been recorded" in never

    hung = diag.describe_health_check(
        "last_scan", {"ok": False, "status": "running",
                      "detail": "scan running too long (likely hung)"})["reason"]
    assert "did not finish cleanly" not in hung
    assert "hung" in hung

    # The one state where the sentence is TRUE keeps it.
    for status in ("failed", "stale_data", "aborted"):
        broke = diag.describe_health_check(
            "last_scan", {"ok": False, "status": status})["reason"]
        assert "did not finish cleanly" in broke, status
