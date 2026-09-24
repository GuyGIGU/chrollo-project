"""Guards for the scan-failure diagnosis: WHY a run died, and what to do.

The rule these pin is the anti-lie rule. "The computer was shut down" may only
be said when a Windows machine-down record actually falls inside the run's own
live window; every other branch must land somewhere honest and DIFFERENT.

Tests 1-8 are pure-function tests, so they run on a CI box that has neither
wevtutil nor a Windows event log.
"""
from __future__ import annotations

import re
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
from app.startup import _MIGRATIONS  # noqa: E402

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


def _shutdown_solution():
    return diag.describe_run(
        {"status": "failed", "failure_kind": "interrupted_shutdown"})["solution"]


def test_no_solution_hardcodes_the_scan_hour(monkeypatch):
    """The slot is a setting the operator is being asked to move (docs/asks.md).

    This started as "no solution may contain a clock time at all", which was
    right about the numeral and wrong about the cure: the sentence then named
    SCAN_SCHEDULE_HOUR_ET in config/settings.py instead, which is worse — he
    reads this on a dashboard and does not edit Python. So the sentence DOES
    speak a clock time now, and the proof that it is not hardcoded is that
    moving the hour moves the sentence.
    """
    monkeypatch.setattr(diag, "scan_slot", lambda: (17, 0))
    assert "17:00 New York time" in _shutdown_solution()

    monkeypatch.setattr(diag, "scan_slot", lambda: (9, 30))
    moved = _shutdown_solution()
    assert "09:30 New York time" in moved
    assert "17:00" not in moved


def test_the_scan_hour_in_the_prose_is_the_one_config_actually_holds():
    """The half the monkeypatch above cannot prove: the live read is the SAME
    setting the scheduler builds its cron from, not a second copy that could
    drift from it."""
    from app.core_settings import load_core_settings

    settings = load_core_settings()
    assert diag.scan_slot() == (int(settings.SCAN_SCHEDULE_HOUR_ET),
                                int(settings.SCAN_SCHEDULE_MINUTE_ET))
    hour, minute = diag.scan_slot()
    assert f"{hour:02d}:{minute:02d} New York time" in _shutdown_solution()


# The ONE filename the operator himself runs. AGENTS.md makes it his gesture
# ("tell them to run update_dashboard.bat"), and two other surfaces already say
# it by name (CalibrationTab.jsx, useEngineRead.js) — a different word here
# would only teach him a second name for one shortcut. Everything ELSE that
# looks like code is a leak.
OPERATOR_GESTURES = ("update_dashboard.bat",)

CODE_SHAPED = (
    (r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", "a settings key or constant name"),
    (r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", "a snake_case identifier"),
    (r"[\w-]+\.(?:py|js|jsx|json|log|md|db|sqlite|bat|ps1|txt|ya?ml|csv)\b", "a filename"),
    (r"[\w.-]+/[\w./-]+", "a repo path"),
)

# Every check webapp/backend/services/health.py actually builds, read from its
# source rather than imported — importing it drags in the database engine.
HEALTH_SOURCE = (BACKEND_DIR / "services" / "health.py").read_text(encoding="utf-8")
BUILT_CHECKS = set(re.findall(r'checks\["(\w+)"\]', HEALTH_SOURCE))


def operator_sentences():
    """(where, sentence) for everything this module can put on his screen."""
    for job in diag.JOB_NAMES:
        for kind in diag.FAILURE_KINDS:
            row = {"status": "failed", "kind": job, "failure_kind": kind}
            yield from _sentences(f"{job}/{kind}", diag.describe_run(row))
        for status in ("failed", "aborted", "stale_data", "expired"):
            yield from _sentences(f"{job}/{status}",
                                  diag.describe_run({"status": status, "kind": job}))
    for name in sorted(BUILT_CHECKS - {"ibkr"}):
        yield from _sentences(f"check/{name}",
                              diag.describe_health_check(name, {"ok": False}))
    for status in ("never", "ok", "running", "failed", "stale_data", "aborted"):
        yield from _sentences(
            f"last_scan/{status}",
            diag.describe_health_check("last_scan", {"ok": False, "status": status}))


def _sentences(where, described):
    for field in ("label", "reason", "solution"):
        value = described.get(field)
        if value:
            yield f"{where}.{field}", value


def test_no_operator_sentence_names_a_code_identifier():
    """He is a discretionary trader glancing at a dashboard, not someone who
    edits Python. A constant name, a settings key, a source filename or a repo
    path on that screen is worse than useless — it names a thing he cannot act
    on, in a vocabulary that is not his. The ONE allowed filename is the
    shortcut he himself double-clicks.
    """
    for where, sentence in operator_sentences():
        scrubbed = sentence
        for gesture in OPERATOR_GESTURES:
            scrubbed = scrubbed.replace(gesture, "")
        for pattern, what in CODE_SHAPED:
            hit = re.search(pattern, scrubbed)
            assert hit is None, f"{where} shows {what}: {hit.group(0)!r}"


def test_every_health_check_the_report_builds_has_plain_words():
    """describe_health_check's label FALLBACK is the raw check key — exactly the
    leak the sweep above forbids. It stays unreachable only while every check
    health.py emits has an entry, so pin that here: a new check without prose
    fails in pytest instead of putting its key on his screen."""
    assert BUILT_CHECKS == {"db", "last_scan", "screener_data", "scheduler", "ibkr"}
    for name in BUILT_CHECKS - {"ibkr"}:
        assert diag.describe_health_check(name, {"ok": False})["label"] != name


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
        assert diag.describe_run({"status": status}) == {
            "verdict": None, "reason": None, "solution": None}


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


# --------------------------------------------------------------- verdict ---
#
# The operator's 2026-09-07 cut: "I just need to know 2 states either the Scan
# failed because of a technical issue (meaning, I need to run the scan manually
# and everything works), or there is a real issue that needs to be tended by
# you!". The taxonomy above survives as the SECOND line; these pin the headline.

VERDICTS = (diag.RERUNNABLE, diag.NEEDS_ATTENTION)


def test_every_failure_kind_maps_to_exactly_one_verdict():
    """THE COVERAGE GATE. A kind the module can stamp but cannot judge would
    reach the operator with no headline at all — so the two sets must be EQUAL,
    and a newly added kind fails here rather than rendering blank."""
    assert set(diag.KIND_VERDICTS) == set(diag.FAILURE_KINDS)
    for kind, verdict in diag.KIND_VERDICTS.items():
        assert verdict in VERDICTS, kind
    # And the same answer through the public door, for every job.
    for job in diag.JOB_NAMES:
        for kind in diag.FAILURE_KINDS:
            described = diag.describe_run(
                {"status": "failed", "kind": job, "failure_kind": kind})
            assert described["verdict"] in VERDICTS, (job, kind)


def test_every_interrupted_run_is_re_runnable():
    """The whole point of the interruption taxonomy: shutdown, service-only,
    unrecorded and not-yet-known all imply the same THING TO DO — the machinery
    is fine, the run just did not reach the end, so run it again."""
    for kind in diag.FAILURE_KINDS:
        assert diag.KIND_VERDICTS[kind] == diag.RERUNNABLE, kind


def test_a_needs_attention_ending_never_reports_as_re_runnable():
    """A deliberate engine refusal (stale data) and a program error are NOT
    fixed by pressing the button again; saying so sends him round a loop."""
    assert set(diag.STATUS_VERDICTS) == {"aborted", "stale_data", "failed"}
    for job in diag.JOB_NAMES:
        for status, error in (("stale_data", "prices are 3 days behind"),
                              ("failed", 'File "...data.py", line 573')):
            described = diag.describe_run(
                {"status": status, "kind": job, "error": error})
            assert described["verdict"] == diag.NEEDS_ATTENTION, (job, status)
            # The detail he said he did not need UP FRONT is still there.
            assert described["reason"] and described["solution"], (job, status)


def test_you_closing_the_page_is_re_runnable():
    assert diag.describe_run({"status": "aborted"})["verdict"] == diag.RERUNNABLE


def test_an_unrecognised_ending_fails_closed_to_needs_attention():
    """Two live rows carry a string whose writer no longer exists. We cannot say
    a re-run fixes what we cannot explain, so the default gets a human."""
    assert diag.DEFAULT_VERDICT == diag.NEEDS_ATTENTION
    described = diag.describe_run(
        {"status": "expired", "error": "scan status expired before completion"})
    assert described["verdict"] == diag.NEEDS_ATTENTION


def test_a_clean_run_carries_no_verdict_at_all():
    for status in ("ok", "running", "never", None):
        assert diag.describe_run({"status": status})["verdict"] is None, status


# ------------------------------------------------------------ escalation ---

def shutdown_run(run_id, kind="scan"):
    return {"id": run_id, "kind": kind, "status": "failed",
            "failure_kind": "interrupted_shutdown"}


def test_a_re_runnable_failure_that_repeats_escalates_to_needs_attention():
    """THE ESCALATION PIN. One interrupted night is "press the button". The same
    interruption three nights running means pressing the button is not fixing it
    — and someone re-running the same broken thing nightly is the exact trap
    this surface exists to prevent. Rows arrive newest-first."""
    rows = [shutdown_run(3), shutdown_run(2), shutdown_run(1)]
    assert diag.REPEAT_ESCALATION == 3

    two = diag.describe_runs(rows[1:])
    assert two[0]["verdict"] == diag.RERUNNABLE  # a streak of two is still noise

    three = diag.describe_runs(rows)
    assert three[0]["verdict"] == diag.NEEDS_ATTENTION
    # The row that was only second in the streak keeps its own honest answer.
    assert three[1]["verdict"] == diag.RERUNNABLE
    # The reason and remedy underneath are untouched — only the headline moved.
    assert "shut down" in three[0]["reason"]


def test_a_different_failure_in_between_breaks_the_streak():
    rows = [shutdown_run(4), shutdown_run(3),
            {"id": 2, "kind": "scan", "status": "aborted"}, shutdown_run(1)]
    assert diag.describe_runs(rows)[0]["verdict"] == diag.RERUNNABLE


def test_another_jobs_run_in_between_does_not_break_the_streak():
    """The registry interleaves scans, outcome backfills and downloads. A
    backfill sitting between two interrupted scans is not a scan that worked."""
    rows = [shutdown_run(4), shutdown_run(3),
            {"id": 2, "kind": "maturation", "status": "ok"}, shutdown_run(1)]
    assert diag.describe_runs(rows)[0]["verdict"] == diag.NEEDS_ATTENTION


def test_the_streak_counts_one_job_not_the_whole_registry():
    """Three DIFFERENT jobs each interrupted once is three separate one-offs."""
    rows = [shutdown_run(3, "scan"), shutdown_run(2, "maturation"),
            shutdown_run(1, "download")]
    assert [r["verdict"] for r in diag.describe_runs(rows)] == [diag.RERUNNABLE] * 3


def test_escalation_only_ever_hardens_a_verdict():
    """It may promote re-runnable to needs-attention; never the reverse, or a
    repeated real error would be softened into "just re-run it"."""
    rows = [{"id": i, "kind": "scan", "status": "failed", "error": "boom"}
            for i in (3, 2, 1)]
    assert [r["verdict"] for r in diag.describe_runs(rows)] == [diag.NEEDS_ATTENTION] * 3


# ------------------------------------------------- health-check verdicts ---

def test_every_non_ibkr_health_check_carries_a_verdict():
    for name in ("db", "last_scan", "screener_data", "scheduler", "something_new"):
        assert diag.describe_health_check(name, {"ok": False})["verdict"] in VERDICTS, name


def test_the_last_scan_check_verdict_follows_its_own_state():
    """The three states where the scan itself is fine are all "run one"; the
    fallback arm, reached only by a run with no resolved cause, fails closed."""
    for status in ("never", "ok", "running"):
        described = diag.describe_health_check("last_scan", {"ok": False, "status": status})
        assert described["verdict"] == diag.RERUNNABLE, status
    assert diag.describe_health_check(
        "last_scan", {"ok": False, "status": "failed"})["verdict"] == diag.NEEDS_ATTENTION


def test_a_check_a_re_run_cannot_fix_never_says_re_run_the_scan():
    """A dead database or a stopped nightly timer is mine, not his: no number of
    manual scans starts the timer or unlocks the file."""
    for name in ("db", "scheduler"):
        assert diag.describe_health_check(
            name, {"ok": False})["verdict"] == diag.NEEDS_ATTENTION, name


def test_the_app_verdict_is_re_runnable_only_when_every_failure_is():
    """One thing a re-run cannot fix makes the whole app need attention, and a
    healthy app has no verdict at all."""
    rerun = {"verdict": diag.RERUNNABLE}
    attention = {"verdict": diag.NEEDS_ATTENTION}
    assert diag.overall_verdict([]) is None
    assert diag.overall_verdict([rerun, rerun]) == diag.RERUNNABLE
    assert diag.overall_verdict([rerun, attention]) == diag.NEEDS_ATTENTION
    # A check that somehow carries no verdict must not be counted as harmless.
    assert diag.overall_verdict([rerun, {}]) == diag.NEEDS_ATTENTION
