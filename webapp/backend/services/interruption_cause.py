"""Why an interrupted run died, worked out once from the Windows event log.

Two moments, deliberately kept apart:

* The boot reconcile (``app/reconciliation.py``) STAMPS A FACT — a row left
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

This module only ever WRITES a kind. The closed set it writes from, and the
words the operator reads for each member, belong to ``services/scan_diagnosis.py``.
"""
from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

from sqlalchemy import text

from services.scan_diagnosis import (
    FAILURE_KINDS,
    HUNG_RUNNING_HOURS,
    PENDING_KIND,
    parse_iso,
)

_log = logging.getLogger("chrollo.diagnosis")

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

# User32 1074 = a shutdown/restart was initiated. It is the ONLY record read.
# EventLog 6008 / Kernel-Power 41 ("the last shutdown was unexpected") were
# dropped after review: Windows stamps both at the NEXT boot, so their timestamp
# is the reboot moment and an overnight power cut lands them hours outside any
# window anchored on the run — the arm was near-dead, and its absence is covered
# honestly by "Windows has no record of the computer going down while it was
# running". Only the event id and its timestamp are ever read: the 1074 payload
# embeds a process path, a user name and a free-text comment field, and none of
# that is ever spliced into text the operator reads.
_SHUTDOWN_EVENT_ID = 1074


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

    ``detected_at`` is the anchor for the shutdown claim, not merely its upper
    bound — see the comment on the window below.
    """
    start = parse_iso(started_at)
    if start is None:
        return "interrupted_unknown"
    if now - start > timedelta(days=EVIDENCE_HORIZON_DAYS):
        return "interrupted_unrecorded"
    if events is None:
        return "interrupted_unknown"

    detected = parse_iso(detected_at)
    window_end = evidence_window_end(start, detected)
    # The shutdown claim is anchored on detected_at — the one moment we can
    # PROVE the run was still alive, because the reconcile found the row still
    # marked running. Anchoring anywhere after started_at was measured to
    # swallow this machine's habitual nightly power-off: all eight recent 1074s
    # sit inside the 18:00 scan's own two-hour cap, so a scan that died at 22:05
    # for an unrelated reason, with the usual power-off at 22:42 and the orphan
    # detected at next boot, was stamped "the computer was shut down while the
    # scan was still running" — a confident wrong cause with a remedy that would
    # not have helped (review 2026-09-07).
    grace = timedelta(seconds=DETECTION_GRACE_SECONDS)
    blamable = [] if detected is None else [
        e for e in events
        if start <= e["time"] <= window_end and abs(e["time"] - detected) <= grace
    ]
    if any(e["event_id"] == _SHUTDOWN_EVENT_ID for e in blamable):
        return "interrupted_shutdown"

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
    query = (
        f"*[System[(EventID={_SHUTDOWN_EVENT_ID}) and "
        f"TimeCreated[@SystemTime>='{_to_z(window_start)}'"
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
        stamp = parse_iso(created.get("SystemTime")) if created is not None else None
        if event_id is None or stamp is None:
            continue
        try:
            events.append({"event_id": int(event_id), "time": stamp})
        except ValueError:
            continue
    return events


def _to_z(stamp: datetime) -> str:
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


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
        events = _read_evidence(rows, now)
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


def _read_evidence(rows: list[dict], now: datetime):
    """ONE event-log read spanning every in-horizon row's window, or None.

    A row past the horizon, or with no readable start, widens nothing: the
    classifier closes the first out and leaves the second pending without the
    log, so reading for them would only stretch the query.
    """
    horizon = now - timedelta(days=EVIDENCE_HORIZON_DAYS)
    windows = []
    for row in rows:
        start = parse_iso(row["started_at"])
        if start is not None and start > horizon:
            detected = parse_iso(row["finished_at"])
            windows.append((start, evidence_window_end(start, detected)))
    if not windows:
        return None
    return collect_machine_down_events(
        min(start for start, _ in windows), max(end for _, end in windows)
    )


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
