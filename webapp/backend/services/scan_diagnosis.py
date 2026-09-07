"""Why a scan run ended badly, in plain words, plus what to do about it.

Two moments, deliberately kept apart:

* The boot reconcile (``services/startup.py``) STAMPS A FACT — a row left
  'running' becomes failed and is tagged ``interrupted_unknown``. It claims no
  cause, because at that instant the cause is usually unknowable. Measured
  2026-09-05: NSSM restarted uvicorn *inside* the dying Windows session, so the
  reconcile ran five seconds after the operator pressed Shut Down and one second
  AFTER the Windows Event Log service had already stopped. Comparing the
  machine's boot time against the run's start at that moment reads FALSE for
  exactly the incident this module exists to explain — so we do not.
* ``resolve_pending`` runs later (backend lifespan startup), when the Event Log
  service is up, reads the Windows System log for the run's own live window, and
  stamps a TERMINAL kind ONCE. The System log is a size-capped circular log, so
  the evidence rots; the ANSWER must not. A resolved row is never re-examined,
  and a row older than the evidence horizon is closed out as "not recorded"
  rather than re-asked forever against a decaying log.

The PROSE is derived at the publisher from the stamped kind, never stored — so
improving the wording is a code change with no data migration, and a stored
sentence can never contradict a later read.

``describe_run`` is PURE: no subprocess, no database, no clock. That is what
makes it safe to call from the /health poll and from both scan-status routes.
"""
from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

from sqlalchemy import text

_log = logging.getLogger("chrollo.diagnosis")

# The error text the boot reconcile writes. It lives HERE, imported by
# startup.py, so the reconcile's wording and the migration's backfill predicate
# cannot drift apart silently (a test pins the handshake).
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
    "interrupted_power_loss",
    "interrupted_service_only",
    "interrupted_unrecorded",
)
# What the reconcile stamps: "interrupted, cause not yet determined".
PENDING_KIND = "interrupted_unknown"

# A run left 'running' this long was already hung by any measure, so a machine
# shutdown later than this cannot honestly be blamed for killing it. Same
# constant the watchdog uses to call a run hung (services/scan_watchdog.py).
HUNG_RUNNING_HOURS = 2.0
# Grace past the moment the orphan was DETECTED: on the 2026-09-05 incident the
# "operating system is shutting down" record landed 1.03s after the reconcile
# stamped finished_at.
DETECTION_GRACE_SECONDS = 90
# How far back we will still ask Windows about a run. The System log here is
# circular and currently holds ~5 months, so 30 days deliberately UNDER-claims:
# past it we close the row out as "not recorded" instead of letting a rolled log
# turn an old shutdown into a false "the computer stayed on".
EVIDENCE_HORIZON_DAYS = 30
# wevtutil is fast (measured 0.06s for a windowed query); a longer wait only
# stalls the caller when the Event Log service is dying.
WEVTUTIL_TIMEOUT_SECONDS = 3

# User32 1074 = a shutdown/restart was initiated. EventLog 6008 = the previous
# shutdown was unexpected. Kernel-Power 41 = the system rebooted without a clean
# shutdown. Only the event id and its timestamp are ever read: the 1074 payload
# embeds a process path, a user name and a free-text comment field, and none of
# that is ever spliced into text the operator reads.
_SHUTDOWN_EVENT_ID = 1074
_POWER_LOSS_EVENT_IDS = (6008, 41)
_WATCHED_EVENT_IDS = (_SHUTDOWN_EVENT_ID,) + _POWER_LOSS_EVENT_IDS


# ---------------------------------------------------------------- prose ----

_RE_RUN_IT = (
    "To rebuild today's list now: open the Screener page, open the Data menu "
    "and press the download button, then press Evaluate."
)
_LEAVE_IT_ON = (
    "The nightly scan starts at 18:00 New York time (SCAN_SCHEDULE_HOUR_ET in "
    "config/settings.py sets that hour) and needs the computer awake until it "
    "finishes. Either leave the computer on past the scan, or move that hour "
    "earlier. "
) + _RE_RUN_IT
_CHECK_THE_LOG = (
    _RE_RUN_IT
    + " If it keeps happening, output/chrollo-service-error.log around the "
    "start time shows what the dashboard was doing."
)

REASONS = {
    "interrupted_unknown":
        "The scan stopped before it finished. Chrollo has not worked out why yet.",
    "interrupted_shutdown":
        "The computer was shut down while the scan was still running, so the "
        "scan never finished.",
    "interrupted_power_loss":
        "The computer went down unexpectedly — a power cut or a hard reset — "
        "while the scan was still running.",
    "interrupted_service_only":
        "The Chrollo dashboard restarted while the scan was running. The "
        "computer stayed on, as far as Windows recorded.",
    "interrupted_unrecorded":
        "The scan stopped before it finished, and Windows has no record of why.",
}

SOLUTIONS = {
    "interrupted_unknown": _CHECK_THE_LOG,
    "interrupted_shutdown": _LEAVE_IT_ON,
    "interrupted_power_loss": _LEAVE_IT_ON,
    "interrupted_service_only": _CHECK_THE_LOG,
    "interrupted_unrecorded": _CHECK_THE_LOG,
}


# ------------------------------------------------------------ the rule ----

def classify_interrupted(started_at, detected_at, events, boot_time, now) -> str:
    """Why a run that was killed mid-flight died. PURE — every input is passed in.

    ``events`` is the Windows System-log answer for the run's window: ``None``
    means the log could NOT be read (claim nothing), ``[]`` means it WAS read
    and held no machine-down record (positive evidence the machine stayed up).
    Collapsing those two is the single most dangerous mutation in this module.

    ``boot_time`` is when the machine last started, and it may only REFUSE a
    claim, never grant one: "the computer stayed on" is asserted only when the
    machine has not rebooted since the run began.
    """
    start = _parse_iso(started_at)
    if start is None:
        return "interrupted_unknown"
    if now - start > timedelta(days=EVIDENCE_HORIZON_DAYS):
        return "interrupted_unrecorded"
    if events is None:
        return "interrupted_unknown"

    detected = _parse_iso(detected_at)
    window_end = evidence_window_end(start, detected)
    in_window = [e for e in events if start <= e["time"] <= window_end]
    if any(e["event_id"] == _SHUTDOWN_EVENT_ID for e in in_window):
        return "interrupted_shutdown"
    if any(e["event_id"] in _POWER_LOSS_EVENT_IDS for e in in_window):
        return "interrupted_power_loss"

    stayed_up = boot_time is not None and boot_time < start
    detected_promptly = (
        detected is not None
        and detected - start <= timedelta(hours=HUNG_RUNNING_HOURS)
    )
    if stayed_up and detected_promptly:
        return "interrupted_service_only"
    return "interrupted_unrecorded"


def evidence_window_end(start: datetime, detected: datetime | None) -> datetime:
    """The last instant a machine-down record may still be blamed on this run.

    Capped at ``start + HUNG_RUNNING_HOURS`` because ``finished_at`` on a
    reconciled row is the DETECTION moment, not the death moment — live rows
    exist where that gap is six days, and an uncapped window would borrow an
    unrelated evening's shutdown.
    """
    cap = start + timedelta(hours=HUNG_RUNNING_HOURS)
    end = min(detected, cap) if detected is not None else cap
    return end + timedelta(seconds=DETECTION_GRACE_SECONDS)


# -------------------------------------------------------------- prose out --

def describe_run(row: dict) -> dict:
    """The operator-facing reason + proposed solution for one scan_runs row.

    PURE and total: any surprise degrades to no reason rather than raising, so a
    diagnostics passenger can never break the surface it rides on.
    """
    try:
        return _describe_run(row)
    except Exception:  # pragma: no cover - defensive
        _log.warning("run diagnosis skipped for row %s", (row or {}).get("id"))
        return {"reason": None, "solution": None}


def describe_runs(rows: list[dict]) -> list[dict]:
    """Both scan-status routes resolve every row through this ONE function, so
    the topbar's status line and the diagnostics registry cannot disagree."""
    return [{**row, **describe_run(row)} for row in rows]


def _describe_run(row: dict) -> dict:
    status = (row or {}).get("status")
    if status in (None, "ok", "running", "never"):
        return {"reason": None, "solution": None}

    if status == "aborted":
        return {
            "reason": "You closed the page while the scan was running, so it was stopped.",
            "solution": "Nothing is broken — start it again and leave the tab open "
                        "until it finishes.",
        }
    if status == "stale_data":
        return {
            "reason": (row.get("error") or "").strip()
            or "The market data was not current, so the scan stopped.",
            "solution": "The prices on disk were behind. Open the Screener page, open "
                        "the Data menu and press the download button, then press "
                        "Evaluate.",
        }

    kind = _interruption_kind(row)
    if kind:
        return {"reason": REASONS[kind], "solution": SOLUTIONS[kind]}

    if status == "failed":
        return {
            "reason": "The scan hit a program error and stopped.",
            "solution": "Re-run it from the Screener page. If it fails again, the "
                        "developer detail below is the clue.",
        }
    # Unrecognised historical text (two live rows carry a string whose writer no
    # longer exists in the codebase) still gets a remedy, never a blank cell.
    return {
        "reason": f"The scan did not finish. Recorded detail: {row.get('error') or 'none'}",
        "solution": _CHECK_THE_LOG,
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

_HEALTH_CHECKS = {
    "db": (
        "Database",
        "Chrollo could not read its own database file.",
        "Restart the dashboard with update_dashboard.bat. If it still fails, the "
        "database file may be locked by another copy of the app.",
    ),
    "last_scan": (
        "Last scan",
        "The most recent scan did not finish cleanly.",
        _RE_RUN_IT,
    ),
    "screener_data": (
        "Screener results file",
        "The scan never wrote its results file, so the Screener page has nothing "
        "fresh to show.",
        _RE_RUN_IT,
    ),
    "scheduler": (
        "Nightly scan timer",
        "The timer that starts the nightly scan is not running, so tonight's scan "
        "would not start on its own.",
        "Restart the dashboard with update_dashboard.bat.",
    ),
}


def describe_health_check(name: str, check: dict) -> dict:
    """label + reason + solution for one failing /health check, in plain words.

    Every non-ibkr check has an entry, so the pill tooltip and the registry never
    show a raw check key (``last_scan``) or an empty remedy.
    """
    label, reason, solution = _HEALTH_CHECKS.get(
        name, (name, "This check is failing.", _CHECK_THE_LOG)
    )
    detail = (check or {}).get("detail") or (check or {}).get("error")
    return {
        "label": label,
        "reason": f"{reason} ({detail})" if detail else reason,
        "solution": solution,
    }


# ------------------------------------------------------------- evidence ----

def boot_time() -> datetime | None:
    """When this machine last started, or None. Needs no dependency (psutil is
    not installed here) and imports safely on any platform. Only ever used to
    REFUSE a claim, so a clock that fails to reset can make it inert but can
    never make it lie."""
    try:
        return datetime.fromtimestamp(time.time() - time.monotonic(), tz=timezone.utc)
    except Exception:  # pragma: no cover - defensive
        return None


def collect_machine_down_events(window_start: datetime, window_end: datetime):
    """Machine-down records from the Windows System log, or None if unreadable.

    None (non-Windows, wevtutil missing, non-zero exit, timeout, unparseable
    output) means "we could not look" and must never be read as "nothing
    happened". ``/f:xml`` is mandatory: ``/f:text`` prints its Date header in
    LOCAL time with a bogus 'Z' suffix, which would silently mis-window every
    event by the machine's UTC offset.
    """
    ids = " or ".join(f"EventID={i}" for i in _WATCHED_EVENT_IDS)
    query = (
        f"*[System[({ids}) and TimeCreated[@SystemTime>='{_to_z(window_start)}'"
        f" and @SystemTime<='{_to_z(window_end)}']]]"
    )
    try:
        proc = subprocess.run(
            ["wevtutil", "qe", "System", f"/q:{query}", "/f:xml", "/c:50"],
            capture_output=True,
            text=True,
            timeout=WEVTUTIL_TIMEOUT_SECONDS,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        _log.info("Windows event log not readable (%s)", exc.__class__.__name__)
        return None
    if proc.returncode != 0:
        _log.info("wevtutil exited %s; no shutdown evidence read", proc.returncode)
        return None
    return parse_events(proc.stdout)


def parse_events(xml_text: str):
    """Parse wevtutil ``/f:xml`` output into [{'event_id', 'time'}], or None.

    wevtutil emits a bare sequence of <Event> elements with no document root, so
    they are wrapped before parsing.
    """
    try:
        root = ElementTree.fromstring(f"<Events>{xml_text}</Events>")
    except ElementTree.ParseError:
        _log.info("wevtutil output did not parse; no shutdown evidence read")
        return None

    ns = "{http://schemas.microsoft.com/win/2004/08/events/event}"
    events = []
    for event in root.iter(f"{ns}Event"):
        system = event.find(f"{ns}System")
        if system is None:
            continue
        event_id = system.findtext(f"{ns}EventID")
        created = system.find(f"{ns}TimeCreated")
        stamp = _parse_iso(created.get("SystemTime")) if created is not None else None
        if event_id is None or stamp is None:
            continue
        try:
            events.append({"event_id": int(event_id), "time": stamp})
        except ValueError:
            continue
    return events


# ------------------------------------------------------------ resolution ---

def resolve_pending(bind=None, limit: int = 10) -> int:
    """Give every still-pending interrupted run a terminal cause, once.

    Called from the backend's lifespan startup (never from the import-time boot
    migrations, where the Event Log service is measured to be already stopped).
    One event-log read covers every pending row's window; each row is then
    classified against its OWN window. Best-effort: any failure leaves the rows
    pending for the next start.
    """
    try:
        if bind is None:
            from database import engine as bind  # local: keeps this module standalone-importable
        rows = _pending_rows(bind, limit)
        if not rows:
            return 0

        now = datetime.now(timezone.utc)
        horizon = now - timedelta(days=EVIDENCE_HORIZON_DAYS)
        fresh = [
            r for r in rows
            if (_parse_iso(r["started_at"]) or horizon) > horizon
        ]
        events = None
        if fresh:
            starts = [_parse_iso(r["started_at"]) for r in fresh]
            ends = [
                evidence_window_end(_parse_iso(r["started_at"]), _parse_iso(r["finished_at"]))
                for r in fresh
            ]
            events = collect_machine_down_events(min(starts), max(ends))

        boot = boot_time()
        resolved = 0
        for row in rows:
            kind = classify_interrupted(
                row["started_at"], row["finished_at"], events, boot, now
            )
            if kind == PENDING_KIND:
                continue
            resolved += _stamp_kind(bind, row["id"], kind)
        if resolved:
            _log.info("resolved the cause of %d interrupted run(s)", resolved)
        return resolved
    except Exception as exc:  # pragma: no cover - defensive; startup must not fail
        _log.warning("interrupted-run resolution skipped (%s)", exc.__class__.__name__)
        return 0


def _pending_rows(bind, limit: int) -> list[dict]:
    with bind.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, started_at, finished_at
                FROM scan_runs
                WHERE failure_kind = :pending
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"pending": PENDING_KIND, "limit": max(1, int(limit))},
        ).mappings().all()
    return [dict(r) for r in rows]


def _stamp_kind(bind, run_id: int, kind: str) -> int:
    # The WHERE clause makes a resolution permanent: a row that already carries a
    # terminal kind is never re-examined, so a later read against a rolled event
    # log cannot rewrite the answer.
    if kind not in FAILURE_KINDS:
        raise ValueError(f"unknown failure kind {kind!r}")
    with bind.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE scan_runs SET failure_kind = :kind "
                "WHERE id = :id AND failure_kind = :pending"
            ),
            {"kind": kind, "id": run_id, "pending": PENDING_KIND},
        )
    return int(result.rowcount or 0)


# ----------------------------------------------------------- missed slot ---

def missed_slot_notice(latest_started_at, now_et, hour: int, minute: int) -> str | None:
    """One line for the night the scan never STARTED — the second failure shape.

    A computer switched off a minute before the slot leaves no scan_runs row at
    all, and the boot catch-up cannot recover it (it only ever re-runs TODAY's
    slot, and a morning boot is always before the evening slot). Without this the
    registry renders that night as blank space.
    """
    # Local import: services.scheduler pulls in the scan runner, and this module
    # sits on the scan-status read path. Keeping the edge inside the function
    # avoids a module-load cycle.
    from services.scheduler import last_weekday_slot

    slot = last_weekday_slot(now_et, hour, minute)
    if slot is None:
        return None
    started = _parse_iso(latest_started_at)
    if started is not None and started >= slot.astimezone(timezone.utc):
        return None
    return (
        f"No scan ran for the {slot.strftime('%A %d %b')} "
        f"{hour:02d}:{minute:02d} New York slot — the computer was most likely "
        "off at that time. Nothing re-runs a missed slot on its own. " + _RE_RUN_IT
    )


def current_missed_slot_notice() -> str | None:
    """``missed_slot_notice`` for right now, reading the live slot + latest run.

    Best-effort: the registry must render even when this cannot be answered.
    """
    try:
        from zoneinfo import ZoneInfo

        from services import scan_status
        from services.core_settings import load_core_settings

        settings = load_core_settings()
        latest = scan_status.latest_run(kind="scan")
        return missed_slot_notice(
            (latest or {}).get("started_at"),
            datetime.now(ZoneInfo("America/New_York")),
            int(getattr(settings, "SCAN_SCHEDULE_HOUR_ET", 18)),
            int(getattr(settings, "SCAN_SCHEDULE_MINUTE_ET", 0)),
        )
    except Exception as exc:  # pragma: no cover - defensive
        _log.info("missed-slot notice skipped (%s)", exc.__class__.__name__)
        return None


# ---------------------------------------------------------------- shared ---

def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _to_z(stamp: datetime) -> str:
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
