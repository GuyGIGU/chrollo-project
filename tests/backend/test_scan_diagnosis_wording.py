"""The exact words the scan-failure diagnosis puts on the operator's screen.

tests/backend/test_scan_diagnosis.py pins the RULES (which cause, which
verdict, which job's noun). This file pins the TEXT, byte for byte and in wire
key order, on representative inputs: the registry, the health pill's tooltip
and the missed-night notice render these strings verbatim, so a restructure
that moves one character of them is a visible change, not a refactor. When the
wording is changed ON PURPOSE, this file is the one to edit alongside it.

Every expected string below is a literal: nothing is read back from the module
under test, or the pin would agree with any edit.
"""
from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import services.scan_diagnosis as diag  # noqa: E402

SCAN_RERUN = ("To rebuild today's list now: open the Screener page, open the Data "
              "menu and press the download button, then press Evaluate.")
BACKFILL_RERUN = "To run it now: open the Archive tab and press Update returns."
DOWNLOAD_RERUN = ("To run it now: open the Screener page, open the Data menu and "
                  "press the download button.")
FOR_THE_DEVELOPER = (" If it keeps happening, that one is for the developer — the "
                     "dashboard's own log records what it was doing at the time.")
PROGRAM_ERROR_CLUE = " If it fails again, the developer detail below is the clue."
NOT_WORKED_OUT = " stopped before it finished. Chrollo has not worked out why yet."
STOPPED_BY_YOU = ("Nothing is broken — start it again. (Leaving the page no longer "
                  "stops a run; it keeps going and the page picks it back up.)")
RESTART_THE_DASHBOARD = "Restart the dashboard with update_dashboard.bat."


def stay_awake(job):
    return (f"The computer has to stay awake until {job} finishes. The nightly scan "
            "runs at 17:00 New York time — either leave the computer on past it, or "
            "move it earlier. ")


@pytest.fixture(autouse=True)
def _slot_at_five_pm(monkeypatch):
    """The slot is read live from settings; pin it so the text is deterministic."""
    monkeypatch.setattr(diag, "scan_slot", lambda: (17, 0))


# ------------------------------------------------------------------ runs ----

RUNS = {
    "scan/interrupted_unknown": (
        {"status": "failed", "kind": "scan", "failure_kind": "interrupted_unknown"},
        {"reason": "The scan" + NOT_WORKED_OUT,
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER,
         "verdict": "rerunnable"}),
    "scan/interrupted_shutdown": (
        {"status": "failed", "kind": "scan", "failure_kind": "interrupted_shutdown"},
        {"reason": "The computer was shut down while the scan was still running, so "
                   "the scan never finished.",
         "solution": stay_awake("the scan") + SCAN_RERUN,
         "verdict": "rerunnable"}),
    "scan/interrupted_service_only": (
        {"status": "failed", "kind": "scan", "failure_kind": "interrupted_service_only"},
        {"reason": "The Chrollo dashboard restarted while the scan was running. The "
                   "computer stayed on, as far as Windows recorded.",
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER,
         "verdict": "rerunnable"}),
    "scan/interrupted_unrecorded": (
        {"status": "failed", "kind": "scan", "failure_kind": "interrupted_unrecorded"},
        {"reason": "The scan stopped before it finished, and Windows has no record of "
                   "the computer going down while it was running.",
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER,
         "verdict": "rerunnable"}),
    "scan/program_error": (
        {"status": "failed", "kind": "scan", "error": 'File "...data.py", line 573'},
        {"reason": "The scan hit a program error and stopped.",
         "solution": SCAN_RERUN + PROGRAM_ERROR_CLUE,
         "verdict": "needs_attention"}),
    # The lower-case opening is what ships today ({job}, not {Job}); pinned as-is.
    "scan/aborted": (
        {"status": "aborted", "kind": "scan"},
        {"reason": "the scan was stopped before it finished.",
         "solution": STOPPED_BY_YOU,
         "verdict": "rerunnable"}),
    # The recorded detail is shown verbatim: its braces are never template fields.
    "scan/stale_data_with_detail": (
        {"status": "stale_data", "kind": "scan", "error": " prices {x} are 3 days behind "},
        {"reason": "prices {x} are 3 days behind",
         "solution": "The prices on disk were behind. " + SCAN_RERUN,
         "verdict": "needs_attention"}),
    "scan/stale_data_without_detail": (
        {"status": "stale_data", "kind": "scan"},
        {"reason": "The market data was not current, so the scan stopped.",
         "solution": "The prices on disk were behind. " + SCAN_RERUN,
         "verdict": "needs_attention"}),
    "scan/unrecognised_with_detail": (
        {"status": "expired", "kind": "scan",
         "error": "scan status expired before completion"},
        {"reason": "The scan did not finish. Recorded detail: scan status expired "
                   "before completion",
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER,
         "verdict": "needs_attention"}),
    "scan/unrecognised_without_detail": (
        {"status": "expired", "kind": "scan"},
        {"reason": "The scan did not finish. Recorded detail: none",
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER,
         "verdict": "needs_attention"}),
    "maturation/interrupted_shutdown": (
        {"status": "failed", "kind": "maturation", "failure_kind": "interrupted_shutdown"},
        {"reason": "The computer was shut down while the outcome backfill was still "
                   "running, so the outcome backfill never finished.",
         "solution": stay_awake("the outcome backfill") + BACKFILL_RERUN,
         "verdict": "rerunnable"}),
    "maturation/program_error": (
        {"status": "failed", "kind": "maturation", "error": "boom"},
        {"reason": "The outcome backfill hit a program error and stopped.",
         "solution": BACKFILL_RERUN + PROGRAM_ERROR_CLUE,
         "verdict": "needs_attention"}),
    "maturation/stale_data_blank_detail": (
        {"status": "stale_data", "kind": "maturation", "error": "   "},
        {"reason": "The market data was not current, so the outcome backfill stopped.",
         "solution": "The prices on disk were behind. " + BACKFILL_RERUN,
         "verdict": "needs_attention"}),
    "download/interrupted_unknown": (
        {"status": "failed", "kind": "download", "failure_kind": "interrupted_unknown"},
        {"reason": "The market-data download" + NOT_WORKED_OUT,
         "solution": DOWNLOAD_RERUN + FOR_THE_DEVELOPER,
         "verdict": "rerunnable"}),
    "download/interrupted_service_only": (
        {"status": "failed", "kind": "download",
         "failure_kind": "interrupted_service_only"},
        {"reason": "The Chrollo dashboard restarted while the market-data download was "
                   "running. The computer stayed on, as far as Windows recorded.",
         "solution": DOWNLOAD_RERUN + FOR_THE_DEVELOPER,
         "verdict": "rerunnable"}),
    "download/aborted": (
        {"status": "aborted", "kind": "download"},
        {"reason": "the market-data download was stopped before it finished.",
         "solution": STOPPED_BY_YOU,
         "verdict": "rerunnable"}),
    # Rows the migration has not reached: the reconcile's own text, today's and
    # the pre-2026-09-07 one, bridge to the pending kind. No kind = the scan.
    "no_kind/reconcile_marker": (
        {"status": "failed",
         "error": "The scan stopped before it finished (recorded when the dashboard "
                  "restarted)."},
        {"reason": "The scan" + NOT_WORKED_OUT,
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER,
         "verdict": "rerunnable"}),
    "scan/legacy_reconcile_text": (
        {"status": "failed", "kind": "scan",
         "error": "process died before completion (reconciled at boot)"},
        {"reason": "The scan" + NOT_WORKED_OUT,
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER,
         "verdict": "rerunnable"}),
    "unknown_job/interrupted_shutdown": (
        {"status": "failed", "kind": "weird", "failure_kind": "interrupted_shutdown"},
        {"reason": "The computer was shut down while the scan was still running, so "
                   "the scan never finished.",
         "solution": stay_awake("the scan") + SCAN_RERUN,
         "verdict": "rerunnable"}),
    # A kind outside the closed set (the dropped power-loss arm) is not an
    # interruption at all: it reads as the program error its status says.
    "scan/dropped_kind": (
        {"status": "failed", "kind": "scan", "failure_kind": "interrupted_power_loss"},
        {"reason": "The scan hit a program error and stopped.",
         "solution": SCAN_RERUN + PROGRAM_ERROR_CLUE,
         "verdict": "needs_attention"}),
    # A stamped kind decides the VERDICT; the status still decides the words.
    "scan/aborted_with_stamped_kind": (
        {"status": "aborted", "kind": "scan", "failure_kind": "interrupted_shutdown"},
        {"reason": "the scan was stopped before it finished.",
         "solution": STOPPED_BY_YOU,
         "verdict": "rerunnable"}),
    "scan/stale_data_with_stamped_kind": (
        {"status": "stale_data", "kind": "scan", "failure_kind": "interrupted_shutdown"},
        {"reason": "The market data was not current, so the scan stopped.",
         "solution": "The prices on disk were behind. " + SCAN_RERUN,
         "verdict": "rerunnable"}),
}


@pytest.mark.parametrize("case", sorted(RUNS))
def test_every_run_ending_reads_exactly_as_shipped(case):
    row, expected = RUNS[case]
    assert list(diag.describe_run(row).items()) == list(expected.items())


@pytest.mark.parametrize("status", ["ok", "running", "never", None])
def test_a_clean_run_carries_three_empty_fields_in_wire_order(status):
    assert list(diag.describe_run({"status": status, "kind": "scan"}).items()) == [
        ("verdict", None), ("reason", None), ("solution", None)]


def test_the_registry_row_is_the_run_then_its_diagnosis():
    row = {"id": 7, "kind": "scan", "status": "failed", "failure_kind": None,
           "error": "boom"}
    described = diag.describe_runs([row])[0]
    assert list(described) == ["id", "kind", "status", "failure_kind", "error",
                               "reason", "solution", "verdict"]
    assert described["reason"] == "The scan hit a program error and stopped."


def test_the_same_pending_failure_under_three_spellings_escalates():
    """The streak compares the BRIDGED kind, so a stamped pending row and two
    rows still carrying the reconcile's text are one failure, three times. Only
    the newest row's headline moves; every sentence stays as it was."""
    rows = [
        {"id": 3, "kind": "scan", "status": "failed", "failure_kind": "interrupted_unknown"},
        {"id": 2, "kind": "scan", "status": "failed",
         "error": "The scan stopped before it finished (recorded when the dashboard "
                  "restarted)."},
        {"id": 1, "kind": "scan", "status": "failed",
         "error": "process died before completion (x)"},
    ]
    described = diag.describe_runs(rows)
    assert [r["verdict"] for r in described] == [
        "needs_attention", "rerunnable", "rerunnable"]
    for run in described:
        assert run["reason"] == "The scan" + NOT_WORKED_OUT
        assert run["solution"] == SCAN_RERUN + FOR_THE_DEVELOPER


# ---------------------------------------------------------- health checks ----

HEALTH_CHECKS = {
    "db/with_error": (
        "db", {"ok": False, "error": "disk I/O error"},
        {"label": "Database",
         "verdict": "needs_attention",
         "reason": "Chrollo could not read its own database file. (disk I/O error)",
         "solution": "Restart the dashboard with update_dashboard.bat. If it still "
                     "fails, the database file may be locked by another copy of the "
                     "app."}),
    "screener_data": (
        "screener_data", {"ok": False, "exists": False},
        {"label": "Screener results file",
         "verdict": "rerunnable",
         "reason": "The scan never wrote its results file, so the Screener page has "
                   "nothing fresh to show.",
         "solution": SCAN_RERUN}),
    "scheduler": (
        "scheduler", {"ok": False},
        {"label": "Nightly scan timer",
         "verdict": "needs_attention",
         "reason": "The timer that starts the nightly scan is not running, so "
                   "tonight's scan would not start on its own.",
         "solution": RESTART_THE_DASHBOARD}),
    # A check with no prose falls back to its key; the detail beats the error.
    "unknown_check": (
        "something_new", {"ok": False, "detail": "d", "error": "e"},
        {"label": "something_new",
         "verdict": "needs_attention",
         "reason": "This check is failing. (d)",
         "solution": SCAN_RERUN + FOR_THE_DEVELOPER}),
    "last_scan/never": (
        "last_scan", {"ok": False, "status": "never", "detail": "no scan recorded"},
        {"label": "Last scan",
         "verdict": "rerunnable",
         "reason": "No scan has ever been recorded. (no scan recorded)",
         "solution": SCAN_RERUN}),
    "last_scan/ok_but_old": (
        "last_scan", {"ok": False, "status": "ok",
                      "detail": "last successful scan 39h ago"},
        {"label": "Last scan",
         "verdict": "rerunnable",
         "reason": "The last scan finished cleanly, but no scan has run since, so this "
                   "list is out of date. (last successful scan 39h ago)",
         "solution": stay_awake("the scan") + SCAN_RERUN}),
    # "Then To rebuild ..." is what ships today; pinned as-is.
    "last_scan/hung": (
        "last_scan", {"ok": False, "status": "running",
                      "detail": "scan running too long (likely hung)"},
        {"label": "Last scan",
         "verdict": "rerunnable",
         "reason": "A scan has been running for hours, so it has almost certainly "
                   "hung. (scan running too long (likely hung))",
         "solution": "Restart the dashboard with update_dashboard.bat — the restart "
                     "marks a stuck run as finished. Then " + SCAN_RERUN}),
    "last_scan/failed": (
        "last_scan", {"ok": False, "status": "failed", "detail": "last scan failed"},
        {"label": "Last scan",
         "verdict": "needs_attention",
         "reason": "The most recent scan did not finish cleanly. (last scan failed)",
         "solution": SCAN_RERUN}),
    "last_scan/unknown_status": (
        "last_scan", {"ok": False, "status": "weird"},
        {"label": "Last scan",
         "verdict": "needs_attention",
         "reason": "The most recent scan did not finish cleanly.",
         "solution": SCAN_RERUN}),
    "last_scan/no_status": (
        "last_scan", {"ok": False, "status": None},
        {"label": "Last scan",
         "verdict": "rerunnable",
         "reason": "No scan has ever been recorded.",
         "solution": SCAN_RERUN}),
    "last_scan/no_check": (
        "last_scan", None,
        {"label": "Last scan",
         "verdict": "rerunnable",
         "reason": "No scan has ever been recorded.",
         "solution": SCAN_RERUN}),
}


@pytest.mark.parametrize("case", sorted(HEALTH_CHECKS))
def test_every_failing_health_check_reads_exactly_as_shipped(case):
    name, check, expected = HEALTH_CHECKS[case]
    assert list(diag.describe_health_check(name, check).items()) == list(expected.items())


# ------------------------------------------------------------ missed slot ----

NY = ZoneInfo("America/New_York")
MISSED_TAIL = (" New York slot — the computer was most likely off at that time. "
               "Nothing re-runs a missed slot on its own. " + SCAN_RERUN)


def test_the_missed_night_notice_reads_exactly_as_shipped():
    monday_morning = datetime(2026, 9, 7, 10, 0, tzinfo=NY)
    assert diag.missed_slot_notice(
        "2026-09-03T22:05:00+00:00", monday_morning, 18, 0,
    ) == "No scan ran for the Friday 04 Sep 18:00" + MISSED_TAIL

    wednesday_evening = datetime(2026, 9, 9, 20, 0, tzinfo=NY)
    assert diag.missed_slot_notice(
        None, wednesday_evening, 17, 30,
    ) == "No scan ran for the Wednesday 09 Sep 17:30" + MISSED_TAIL


def test_a_run_at_the_slot_itself_silences_the_notice():
    # Friday 2026-09-04 18:00 New York is 22:00 UTC exactly.
    monday_morning = datetime(2026, 9, 7, 10, 0, tzinfo=NY)
    assert diag.missed_slot_notice(
        "2026-09-04T22:00:00+00:00", monday_morning, 18, 0) is None
    assert diag.missed_slot_notice(
        "2026-09-04T21:59:59+00:00", monday_morning, 18, 0) is not None
