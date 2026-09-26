"""Why a scan run ended badly, in plain words, plus what to do about it.

This is the PUBLISHER: it turns a scan_runs row, or a failing /health check,
into the operator's two-state verdict, a reason and a proposed solution. WHY an
interrupted run died is worked out elsewhere, once, by
``services/interruption_cause.py``, and stamped on the row as a member of
``FAILURE_KINDS``. The closed set, the reconcile's marker text and the hang
threshold live HERE because every side reads them — the boot reconcile, the
migration backfill, the resolver, the watchdog and /health — and this module
imports nothing beyond the standard library at load, so reading them costs
those callers nothing.

The PROSE is derived at the publisher from the stamped kind, never stored — so
improving the wording is a code change with no data migration, and a stored
sentence can never contradict a later read.

``describe_run`` is PURE: no subprocess, no database, no clock. Its one reach
outside is the nightly slot's hour, read from config by the two sentences that
speak it (measured 0.39ms a read) — a remedy that names an hour has to name the
LIVE one. That is what makes it safe to call from the /health poll and from both
scan-status routes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

_log = logging.getLogger("chrollo.diagnosis")

# The error text the boot reconcile writes. It lives HERE, imported by
# app/reconciliation.py, so the reconcile's wording and the migration's backfill
# predicate cannot drift apart silently (a test pins the handshake).
RECONCILE_MARKER = (
    "The scan stopped before it finished (recorded when the dashboard restarted)."
)
# What the reconcile wrote before 2026-09-07. Ten live rows carry it; the
# migration backfills them to the pending kind so they can still be explained.
LEGACY_RECONCILE_PREFIX = "process died before completion"

# The closed set stored in scan_runs.failure_kind. Every consumer derives
# membership from this tuple; the reason/solution maps are built from it, so a
# new kind without prose fails a test instead of rendering blank.
FAILURE_KINDS = (
    "interrupted_unknown",
    "interrupted_shutdown",
    "interrupted_service_only",
    "interrupted_unrecorded",
)
# What the reconcile stamps: "interrupted, cause not yet determined".
PENDING_KIND = "interrupted_unknown"

# ------------------------------------------------------------- verdict ----

# THE headline, and the only decision this surface exists to support: do I press
# re-scan, or do I ping the developer? Operator's ruling 2026-09-07 — "I just
# need to know 2 states either the Scan failed because of a technical issue
# (meaning, I need to run the scan manually and everything works), or there is a
# real issue that needs to be tended by you!". So a verdict is named for the
# ACTION it implies, never for the cause. The cause did not go away: it is the
# second line now, not the headline.
RERUNNABLE = "rerunnable"
NEEDS_ATTENTION = "needs_attention"

# ONE home for the mapping (EC-3). An interrupted run is keyed on its stamped
# failure_kind; every other ending on its run status. A kind or a status with no
# row here fails a test rather than reaching the operator with no headline.
KIND_VERDICTS = {
    # Every interruption kind is re-runnable by construction: the machinery is
    # fine, the run simply did not get to the end. A manual scan is the whole fix.
    "interrupted_unknown": RERUNNABLE,
    "interrupted_shutdown": RERUNNABLE,
    "interrupted_service_only": RERUNNABLE,
    "interrupted_unrecorded": RERUNNABLE,
}
STATUS_VERDICTS = {
    # You closed the page mid-run. Nothing is broken.
    "aborted": RERUNNABLE,
    # A deliberate engine refusal — the prices on disk were behind, so it stopped
    # rather than scan stale data. Running the same scan again meets the same
    # refusal, so this one is mine to look at.
    "stale_data": NEEDS_ATTENTION,
    # A program error / non-zero exit.
    "failed": NEEDS_ATTENTION,
}
# Anything unrecognised fails CLOSED, to the side that gets a human to look:
# quietly telling him to re-run something we cannot explain is the exact trap.
DEFAULT_VERDICT = NEEDS_ATTENTION

# A re-runnable failure that keeps coming back is not re-runnable. THREE
# consecutive runs of one job ending the same way is a pattern, not an accident:
# one is noise, two can be two nights of the same habit (he powers the PC off
# most nights), three means re-running it nightly is not fixing it. Server-side,
# like every other judgment on this wire (EC-28).
REPEAT_ESCALATION = 3

# A run left 'running' this long was already hung by any measure, so a machine
# shutdown later than this cannot honestly be blamed for killing it. THE one
# home for that judgment: services/scan_watchdog.py, services/health.py and
# services/interruption_cause.py import it from here (this module is
# dependency-free, so importing it costs them nothing), and a test pins that
# they share the object. Tuning it in one place used to leave the other two on
# the old number.
HUNG_RUNNING_HOURS = 2.0


# ---------------------------------------------------------------- prose ----

# Every sentence below is a TEMPLATE keyed on the job as well as on the failure.
# The boot reconcile stamps maturation and download rows exactly as it stamps
# scans (the ten live reconciled rows split scan 4 / maturation 5 / download 1),
# and the registry lists all three — so "the scan hit a program error" with a
# "press Evaluate" remedy was being printed under a row headed "Outcome
# backfill", where that remedy cannot help (review 2026-09-07).
JOB_NAMES = {
    "scan": "the scan",
    "maturation": "the outcome backfill",
    "download": "the market-data download",
}
# The ONE instruction that re-runs each job.
JOB_RERUN = {
    "scan": "To rebuild today's list now: open the Screener page, open the Data "
            "menu and press the download button, then press Evaluate.",
    "maturation": "To run it now: open the Archive tab and press Update returns.",
    "download": "To run it now: open the Screener page, open the Data menu and "
                "press the download button.",
}
DEFAULT_JOB = "scan"

# No numeral typed into this sentence, and no setting NAMED in it either. The
# hour is a setting, and docs/asks.md asks the operator to move it — a clock
# time copied into prose starts lying the moment he does, and naming the setting
# instead is worse than useless to a man who reads this on a dashboard and does
# not edit Python. {slot} renders the LIVE hour as a time he reads on a clock.
_LEAVE_IT_ON = (
    "The computer has to stay awake until {job} finishes. The nightly scan runs "
    "at {slot} — either leave the computer on past it, or move it earlier. "
    "{rerun}"
)
# Where the log lives is the developer's business: the path is in docs/deploy.md,
# and that file is mostly HTTP request lines anyway (decisions.md 2026-08-24), so
# sending him to it was a wrong errand as well as a leaked path.
_CHECK_THE_LOG = (
    "{rerun} If it keeps happening, that one is for the developer — the "
    "dashboard's own log records what it was doing at the time."
)

REASONS = {
    "interrupted_unknown":
        "{Job} stopped before it finished. Chrollo has not worked out why yet.",
    "interrupted_shutdown":
        "The computer was shut down while {job} was still running, so {job} "
        "never finished.",
    "interrupted_service_only":
        "The Chrollo dashboard restarted while {job} was running. The "
        "computer stayed on, as far as Windows recorded.",
    "interrupted_unrecorded":
        "{Job} stopped before it finished, and Windows has no record of the "
        "computer going down while it was running.",
}

SOLUTIONS = {
    "interrupted_unknown": _CHECK_THE_LOG,
    "interrupted_shutdown": _LEAVE_IT_ON,
    "interrupted_service_only": _CHECK_THE_LOG,
    "interrupted_unrecorded": _CHECK_THE_LOG,
}


def _job_kind(value) -> str:
    """Which job a row belongs to, defaulted. ONE home: the prose filler and the
    repeat streak must agree on which job a row is, or a streak counts runs the
    sentences call by different names."""
    return value if value in JOB_NAMES else DEFAULT_JOB


# The shipped slot, used ONLY when the settings file cannot be read at all —
# the same pair services/scheduler.py falls back to when it builds the cron.
_DEFAULT_SLOT = (17, 0)


def scan_slot() -> tuple[int, int]:
    """The nightly scan slot as (hour, minute) in New York, read LIVE.

    ONE home for that read (EC-3): the missed-slot notice and the "leave it on"
    remedy must not be able to name two different hours, and neither may carry
    the number in its own text. Raises if the settings file cannot be read —
    both callers already handle that, and the render path goes through
    ``scan_slot_in_words``, which degrades.
    """
    # Local import for the same reason the rest of this module uses them: it
    # keeps scan_diagnosis standalone-importable.
    from app.core_settings import load_core_settings

    settings = load_core_settings()
    return (
        int(getattr(settings, "SCAN_SCHEDULE_HOUR_ET", _DEFAULT_SLOT[0])),
        int(getattr(settings, "SCAN_SCHEDULE_MINUTE_ET", _DEFAULT_SLOT[1])),
    )


def scan_slot_in_words() -> str:
    """The slot as a clock time the operator reads: ``17:00 New York time``.

    Total: this sits on the /health poll path, so an unreadable settings file
    falls back to the shipped default rather than blanking a whole remedy.
    """
    try:
        hour, minute = scan_slot()
    except Exception:  # pragma: no cover - defensive
        hour, minute = _DEFAULT_SLOT
    return f"{hour:02d}:{minute:02d} New York time"


def _in_words(template: str, job_kind: str | None) -> str:
    """Fill one prose template for one job kind.

    Every operator-facing sentence in this module goes through here, so a job
    kind can never reach the operator with the wrong noun or with a remedy that
    does not run it.
    """
    kind = _job_kind(job_kind)
    job = JOB_NAMES[kind]
    # Only the sentences that SPEAK the slot pay for reading it (measured
    # 0.39ms a read, and this fills every sentence on the /health poll).
    slot = scan_slot_in_words() if "{slot}" in template else ""
    return template.format(
        job=job,
        Job=job[:1].upper() + job[1:],
        rerun=JOB_RERUN[kind],
        slot=slot,
    )


# -------------------------------------------------------------- prose out --

def describe_run(row: dict) -> dict:
    """The verdict, reason and proposed solution for one scan_runs row.

    PURE and total: any surprise degrades to no verdict rather than raising, so a
    diagnostics passenger can never break the surface it rides on.
    """
    try:
        return _describe_run(row)
    except Exception:  # pragma: no cover - defensive
        _log.warning("run diagnosis skipped for row %s", (row or {}).get("id"))
        return {"verdict": None, "reason": None, "solution": None}


def describe_runs(rows: list[dict]) -> list[dict]:
    """Both scan-status routes and /health resolve every row through this ONE
    function, so the topbar's status line, the health pill and the diagnostics
    registry cannot disagree about the same run.

    Rows arrive NEWEST-FIRST. The repeat escalation reads the runs behind each
    row, so callers give this a short window rather than a single row.
    """
    described = [{**row, **describe_run(row)} for row in rows]
    return [_escalate_repeat(described, i) for i in range(len(described))]


def _escalate_repeat(rows: list[dict], index: int) -> dict:
    """A re-runnable failure that has come back REPEAT_ESCALATION runs in a row
    is no longer re-runnable — re-running the same broken thing every night is
    the trap this whole surface exists to prevent."""
    row = rows[index]
    if row.get("verdict") != RERUNNABLE:
        return row
    job = _job_kind(row.get("kind"))
    signature = _failure_signature(row)
    repeats = 1
    for older in rows[index + 1:]:
        if _job_kind(older.get("kind")) != job:
            continue  # another job's run in between does not break the streak
        if _failure_signature(older) != signature:
            break
        repeats += 1
    if repeats < REPEAT_ESCALATION:
        return row
    return {**row, "verdict": NEEDS_ATTENTION}


def _failure_signature(row: dict) -> tuple:
    """What makes two endings 'the same failure, again'."""
    return (row.get("status"), _interruption_kind(row))


def _describe_run(row: dict) -> dict:
    row = row or {}
    status = row.get("status")
    if status in (None, "ok", "running", "never"):
        return {"verdict": None, "reason": None, "solution": None}
    kind = _interruption_kind(row)
    verdict = (KIND_VERDICTS.get(kind, DEFAULT_VERDICT) if kind
               else STATUS_VERDICTS.get(status, DEFAULT_VERDICT))
    return {**_explain(row, status, kind), "verdict": verdict}


def _explain(row: dict, status: str, kind: str | None) -> dict:
    # Which JOB this row is: the registry lists scans, outcome backfills and
    # market-data downloads side by side, and each needs its own noun and its
    # own way to be run again.
    job = row.get("kind")
    if status == "aborted":
        # Two populations read the same row: HISTORIC rows where closing the
        # page terminated the child (council review 2026-09-07, finding 4), and
        # rows the operator's own Stop button writes now that a job outlives its
        # reader (review A3). Both are "it was stopped", neither is broken, so
        # one line covers them — and the parenthetical corrects the old advice
        # ("leave the tab open") that the historic rows were written under.
        return _prose(
            "{job} was stopped before it finished.",
            "Nothing is broken — start it again. (Leaving the page no longer "
            "stops a run; it keeps going and the page picks it back up.)",
            job,
        )
    if status == "stale_data":
        # The recorded detail is rendered verbatim — never through the template
        # filler, whose braces it does not obey.
        recorded = (row.get("error") or "").strip()
        return {
            "reason": recorded or _in_words(
                "The market data was not current, so {job} stopped.", job),
            "solution": _in_words("The prices on disk were behind. {rerun}", job),
        }

    if kind:
        return _prose(REASONS[kind], SOLUTIONS[kind], job)

    if status == "failed":
        return _prose(
            "{Job} hit a program error and stopped.",
            "{rerun} If it fails again, the developer detail below is the clue.",
            job,
        )
    # Unrecognised historical text (two live rows carry a string whose writer no
    # longer exists in the codebase) still gets a remedy, never a blank cell.
    return {
        "reason": _in_words("{Job} did not finish. Recorded detail: ", job)
        + (row.get("error") or "none"),
        "solution": _in_words(_CHECK_THE_LOG, job),
    }


def _prose(reason: str, solution: str, job_kind: str | None) -> dict:
    return {
        "reason": _in_words(reason, job_kind),
        "solution": _in_words(solution, job_kind),
    }


def _interruption_kind(row: dict) -> str | None:
    """The stamped kind, bridging rows the migration has not reached yet."""
    kind = row.get("failure_kind")
    if kind in FAILURE_KINDS:
        return kind
    error = (row.get("error") or "").strip()
    if error == RECONCILE_MARKER or error.startswith(LEGACY_RECONCILE_PREFIX):
        return PENDING_KIND
    return None


# -------------------------------------------------------- health checks ----

# (label, reason, solution, VERDICT) — the same two-state headline the runs
# carry, decided in the same module, so a failing check and a failed run cannot
# tell the operator to do two different things.
_HEALTH_CHECKS = {
    "db": (
        "Database",
        "Chrollo could not read its own database file.",
        "Restart the dashboard with update_dashboard.bat. If it still fails, the "
        "database file may be locked by another copy of the app.",
        NEEDS_ATTENTION,
    ),
    "screener_data": (
        "Screener results file",
        "{Job} never wrote its results file, so the Screener page has nothing "
        "fresh to show.",
        "{rerun}",
        RERUNNABLE,
    ),
    "scheduler": (
        "Nightly scan timer",
        "The timer that starts the nightly scan is not running, so tonight's scan "
        "would not start on its own.",
        "Restart the dashboard with update_dashboard.bat.",
        NEEDS_ATTENTION,
    ),
}

# The last-scan check fails in FOUR shapes, and in three of them the scan itself
# finished perfectly — so one fixed "the most recent scan did not finish
# cleanly" was false in three states, including the morning after this
# operator's own incident: the machine was off, no scan ran, and the newest row
# is yesterday's clean scan aged past its allowance (review 2026-09-07). Keyed
# on the status the freshness check already worked out, and kept HERE so the
# topbar pill and the diagnostics registry stay one sentence.
_LAST_SCAN_STATES = {
    "never": (
        "No scan has ever been recorded.",
        "{rerun}",
        RERUNNABLE,
    ),
    "ok": (
        "The last scan finished cleanly, but no scan has run since, so this "
        "list is out of date.",
        _LEAVE_IT_ON,
        RERUNNABLE,
    ),
    "running": (
        "A scan has been running for hours, so it has almost certainly hung.",
        "Restart the dashboard with update_dashboard.bat — the restart marks a "
        "stuck run as finished. Then {rerun}",
        RERUNNABLE,
    ),
}
# failed / stale_data / aborted: the run itself really did end badly, and its
# own resolved reason and verdict (describe_run) are what the caller shows in
# their place — so this arm is the defensive fallback, and it fails closed.
_LAST_SCAN_FAILED = (
    "The most recent scan did not finish cleanly.", "{rerun}", NEEDS_ATTENTION)


def describe_health_check(name: str, check: dict) -> dict:
    """verdict + label + reason + solution for one failing /health check.

    Every non-ibkr check has an entry, so the pill tooltip and the registry never
    show a raw check key (``last_scan``), an empty remedy or no headline.
    """
    check = check or {}
    if name == "last_scan":
        label = "Last scan"
        reason, solution, verdict = _LAST_SCAN_STATES.get(
            check.get("status") or "never", _LAST_SCAN_FAILED
        )
    else:
        label, reason, solution, verdict = _HEALTH_CHECKS.get(
            name, (name, "This check is failing.", _CHECK_THE_LOG, DEFAULT_VERDICT)
        )
    reason = _in_words(reason, DEFAULT_JOB)
    detail = check.get("detail") or check.get("error")
    return {
        "label": label,
        "verdict": verdict,
        "reason": f"{reason} ({detail})" if detail else reason,
        "solution": _in_words(solution, DEFAULT_JOB),
    }


def overall_verdict(failing: list[dict]) -> str | None:
    """The pill's one word, for the whole app. A healthy app has no verdict at
    all; re-runnable is claimed only when EVERY failing check is re-runnable,
    because one thing a re-run cannot fix is one thing I have to look at."""
    if not failing:
        return None
    if all(check.get("verdict") == RERUNNABLE for check in failing):
        return RERUNNABLE
    return NEEDS_ATTENTION


# ----------------------------------------------------------- missed slot ---

def missed_slot_notice(latest_started_at, now_et, hour: int, minute: int) -> str | None:
    """One line for the night the scan never STARTED — the second failure shape.

    A slot that passed with NO scan_runs row at all leaves the registry nothing
    to render: every other sentence in this module explains a row, and here
    there is no row. This is the only place that night gets words.

    Its territory is NARROWER than it once was, and the old justification here
    ("the boot catch-up only ever re-runs TODAY's slot, and a morning boot is
    always before the evening slot") is dead. The catch-up now resolves the
    MOST RECENT weekday slot — stepping back a day when today's has not passed,
    and back over the weekend — so a morning boot and a Saturday boot each
    recover the previous weekday's night on their own. What is left for this
    notice is the night no boot followed: the machine slept through the slot
    and woke past APScheduler's misfire grace, so the cron dropped the run and
    nothing restarted to notice it; the couple of minutes between a boot and
    the catch-up scan actually starting; and a boot whose catch-up never got
    scheduled at all (the scheduler failed to start, or its own check threw and
    logged).

    Two limits worth stating, because they are not defects to be fixed here.
    It speaks only about the MOST RECENT slot, so the second and older of two
    consecutive missed nights is never named — and the single catch-up cannot
    recover one either. And ANY run at/after the slot silences it, whatever
    that run's status: the catch-up demands a successful one, but a run that
    exists and ended badly already has its own reason and remedy from
    ``describe_run``, which is the more specific answer.
    """
    # Local import: services.scheduler pulls in the scan runner, and this module
    # sits on the scan-status read path. Keeping the edge inside the function
    # avoids a module-load cycle.
    from services.scheduler import last_weekday_slot

    slot = last_weekday_slot(now_et, hour, minute)
    started = parse_iso(latest_started_at)
    if started is not None and started >= slot.astimezone(timezone.utc):
        return None
    return (
        f"No scan ran for the {slot.strftime('%A %d %b')} "
        f"{hour:02d}:{minute:02d} New York slot — the computer was most likely "
        "off at that time. Nothing re-runs a missed slot on its own. "
        + JOB_RERUN["scan"]
    )


def current_missed_slot_notice() -> str | None:
    """``missed_slot_notice`` for right now, reading the live slot + latest run.

    Best-effort: the registry must render even when this cannot be answered.
    """
    try:
        from zoneinfo import ZoneInfo

        from services import scan_status

        hour, minute = scan_slot()
        latest = scan_status.latest_run(kind="scan")
        return missed_slot_notice(
            (latest or {}).get("started_at"),
            datetime.now(ZoneInfo("America/New_York")),
            hour,
            minute,
        )
    except Exception as exc:  # pragma: no cover - defensive
        _log.info("missed-slot notice skipped (%s)", exc.__class__.__name__)
        return None


# ---------------------------------------------------------------- shared ---

def parse_iso(value) -> datetime | None:
    """A scan_runs or event-log timestamp as an aware datetime, or None.

    The one reader of those stamps for this module and the resolver: naive text
    is taken as UTC, and anything unreadable is None, never an exception.
    """
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp
