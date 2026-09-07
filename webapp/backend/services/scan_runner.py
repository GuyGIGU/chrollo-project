"""Broker-free scan runner shared by manual SSE and scheduled jobs."""
from __future__ import annotations

import logging
import os
import json
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass, field
from typing import Iterator

log = logging.getLogger("chrollo.scan")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCREENER_SCRIPT = os.path.join(ROOT_DIR, "run_screener.py")
SCAN_LOCK = threading.Lock()

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


# Alert when strictly MORE than this many tickers had their eval chain throw and
# get swallowed by the skip-guard. 0 = any swallowed eval crash alerts. A crash on
# a SUBSET of setups silently drops real winners on an otherwise-green (exit 0)
# build, so this is the tripwire that makes that visible.
ERRORED_TICKERS_ALERT_THRESHOLD = 0


@dataclass
class ScanProcessResult:
    returncode: int
    output: str
    n_setups: int | None = None
    n_errored: int | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _create_process(args: list[str] | None = None) -> subprocess.Popen:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # Force UTF-8 on the child's stdio. Under the Windows service (and any piped
    # subprocess) Python otherwise defaults stdout to the locale codec (cp1252),
    # which crashes the instant the pipeline prints a non-Latin-1 char such as
    # "→" or an emoji tag. PYTHONUTF8/PYTHONIOENCODING fix the *encode* side
    # in the child; encoding+errors fix the *decode* side here in the parent.
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, SCREENER_SCRIPT]
    if args:
        command.extend(args)
    return subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=flags,
        env=env,
    )


def _run_scan_process_unlocked(args: list[str] | None = None) -> ScanProcessResult:
    process = _create_process(args)
    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        lines.append(line)
        log.info("[scan] %s", line.rstrip())
    process.stdout.close()
    process.wait()
    output = "".join(lines)
    n_setups, n_errored = _parse_scan_result(output)
    return ScanProcessResult(
        returncode=process.returncode,
        output=output,
        n_setups=n_setups,
        n_errored=n_errored,
    )


def _parse_scan_result(output: str) -> tuple[int | None, int]:
    """Parse the child's single ``SCAN_RESULT_JSON:`` line, returning
    ``(n_setups, n_errored)``.

    Both ride the ONE structured payload the child prints for the PRIMARY
    (US-Stocks) universe (``run_screener._print_result_json``), so a multi-universe
    ``--all-universes`` run reports the PRIMARY universe's counts — not the last
    small ETF universe's. This replaces the old ``errored=N`` stdout scrape, which
    read ``reversed(output.splitlines())`` and so returned the LAST universe's
    timing line (ETF errored=0), masking a real US-Stocks silent-drop.

    ``n_setups`` is ``None`` when the payload is missing/unparseable (so the alert
    can tell "no data" from zero). ``n_errored`` defaults to 0 when the key is
    absent (clean scan, or an older child that predates the threaded count) — a
    swallowed-eval-crash count is a tripwire, and "unknown" there means "no known
    crashes", matching the pre-fix zero-on-clean behaviour.
    """
    prefix = "SCAN_RESULT_JSON:"
    for line in reversed(output.splitlines()):
        if line.startswith(prefix):
            try:
                payload = json.loads(line[len(prefix):].strip())
                return int(payload.get("n_setups", 0)), int(payload.get("n_errored", 0))
            except Exception:
                return None, 0
    return None, 0


def _result_status(result: ScanProcessResult) -> str:
    if result.ok:
        return "ok"
    if "StaleMarketDataError" in result.output or "stale market data" in result.output.lower():
        return "stale_data"
    return "failed"


def _tail_error(output: str, limit: int = 1000) -> str | None:
    text = output.strip()
    if not text:
        return None
    for line in reversed(text.splitlines()):
        if "stale market data" in line.lower():
            return line.strip()
    return text[-limit:]


def _last_fetch_health() -> dict | None:
    """The most recent fetch-health record the scan wrote to cache_meta.json."""
    meta_path = os.path.join(ROOT_DIR, "cache_meta.json")
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    health = meta.get("fetch_health") if isinstance(meta, dict) else None
    return health if isinstance(health, dict) else None


def _alert_decision(status: str, n_setups: int | None, fetch_health: dict | None,
                    alert_on_zero: bool, alert_on_degraded: bool,
                    errored_tickers: int | None = None) -> str | None:
    """Return a human-readable alert reason, or None if no alert is warranted.

    Pure (no I/O) so it is unit-testable. A failed/stale scan alerts on its
    status; a scan that swallowed one or more eval-chain crashes alerts as an
    early warning (a regression that throws on a SUBSET of tickers silently drops
    real winners on an otherwise-green build); a successful scan with zero results
    alerts when enabled; a successful scan whose fetch came back unhealthy (low
    return ratio) alerts as an early warning, before the degradation escalates to
    a stale_data failure.

    ``errored_tickers`` defaults to None so existing positional callers keep their
    prior behaviour; None means "no data" (never alerts).
    """
    if status in ("failed", "stale_data"):
        return status
    if (errored_tickers is not None
            and errored_tickers > ERRORED_TICKERS_ALERT_THRESHOLD):
        return (f"{errored_tickers} ticker(s) errored during evaluation "
                f"(swallowed eval crash — possible silent winner drop)")
    if n_setups == 0 and alert_on_zero:
        return "zero scan results"
    if (alert_on_degraded and isinstance(fetch_health, dict)
            and fetch_health.get("healthy") is False):
        return (f"degraded data fetch (mode={fetch_health.get('mode')}, "
                f"return_ratio={fetch_health.get('return_ratio')})")
    return None


def alert_if_needed(trigger: str, status: str, n_setups: int | None,
                    error: str | None = None, errored_tickers: int | None = None) -> None:
    from services.core_settings import load_core_settings

    settings = load_core_settings()
    # Only consult fetch-health for an otherwise-ok scan: a failed/stale run
    # already alerts on its status, and its cache_meta record may be stale.
    fetch_health = _last_fetch_health() if status == "ok" else None
    reason = _alert_decision(
        status,
        n_setups,
        fetch_health,
        bool(getattr(settings, "ALERT_ON_ZERO_RESULTS", True)),
        bool(getattr(settings, "ALERT_ON_DEGRADED_FETCH", True)),
        errored_tickers,
    )
    if reason is None:
        return

    message = f"Chrollo scan alert ({trigger}): {reason}; setups={n_setups}"
    if error:
        message = f"{message}; error={error[:300]}"
    log.warning(message)

    env_name = getattr(settings, "ALERT_WEBHOOK_URL_ENV", "ALERT_WEBHOOK_URL")
    url = os.environ.get(env_name)
    if not url:
        return

    payload = json.dumps({"text": message}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except Exception:
        log.exception("scan alert webhook failed")


def _terminate_child(process: subprocess.Popen | None) -> None:
    """Best-effort terminate→kill of the scan child. Never raises: this runs on
    abort/error paths right before SCAN_LOCK is released, and the lock's whole
    guarantee is "at most one child at a time" — the child must be dead (not
    still evaluating and writing the archive) by the time the lock frees."""
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    except Exception:
        log.exception("failed to terminate scan child process")
    if process.stdout is not None:
        try:
            process.stdout.close()
        except Exception:
            pass


@dataclass
class LiveJob:
    """One manual job, owned by a background thread rather than by an SSE client.

    The child process, the run record and SCAN_LOCK all belong to the thread; an
    SSE response is only a READER of ``events``. That separation is the whole
    point: a client that goes away — one click on the top nav — must not kill the
    12-17 minutes of work the server is already doing (council review
    2026-09-07, finding 4; archive row 271 is a real scan lost this way).
    """
    trigger: str
    kind: str                      # the scan_runs row's kind: 'scan' | 'download'
    job: str                       # the label a client re-attaches by: 'evaluation' | 'download'
    events: list[str] = field(default_factory=list)   # SSE payloads, in order, replayable
    run_id: int | None = None
    done: bool = False
    process: subprocess.Popen | None = None


# Guards _LIVE_JOB and every LiveJob's events/done. Readers wait on it for new
# output instead of polling.
_LIVE_COND = threading.Condition()
_LIVE_JOB: LiveJob | None = None

# A reader re-checks this often even without a notify, so a missed notification
# can never wedge a stream open forever.
_FOLLOW_POLL_SECONDS = 1.0


def _emit(job: LiveJob, event: str) -> None:
    with _LIVE_COND:
        job.events.append(event)
        _LIVE_COND.notify_all()


def _pump_job(job: LiveJob, args: list[str] | None) -> None:
    """Run the child to completion, record the run, release SCAN_LOCK.

    Runs on its own thread and never yields, so no client action can interrupt
    it. It still owns everything the old generator owned — terminate the child on
    a failure, always finish the run row, always release the lock — which is what
    keeps a disconnect from leaving an unsupervised child or a 'running' row.
    """
    from services import scan_status

    lines: list[str] = []
    try:
        job.run_id = scan_status.start_run(job.trigger, kind=job.kind)
        job.process = _create_process(args)
        assert job.process.stdout is not None
        for line in job.process.stdout:
            lines.append(line)
            _emit(job, f"data: {line}\n\n")

        job.process.stdout.close()
        job.process.wait()
        output = "".join(lines)
        n_setups, n_errored = _parse_scan_result(output)
        result = ScanProcessResult(
            returncode=job.process.returncode,
            output=output,
            n_setups=n_setups,
            n_errored=n_errored,
        )
        status = _result_status(result)
        error = _tail_error(output) if status != "ok" else None
        scan_status.finish_run(job.run_id, status=status, n_setups=result.n_setups, error=error)
        alert_if_needed(job.trigger, status, result.n_setups, error, result.n_errored)
        if job.process.returncode != 0:
            _emit(job, f"data: ERROR: scan exited with code {job.process.returncode}\n\n")
    except Exception as exc:
        _terminate_child(job.process)
        if job.run_id is not None:
            scan_status.finish_run(job.run_id, status="failed", error=str(exc))
        alert_if_needed(job.trigger, "failed", None, str(exc))
        _emit(job, f"data: ERROR: {exc}\n\n")
    finally:
        # The route wrappers used to invalidate the screener cache in their own
        # `finally`, which fired when the CLIENT went away rather than when the
        # artifact was rewritten. It belongs to the job, so it lives here.
        if job.kind == "scan":
            _invalidate_screener_cache()
        SCAN_LOCK.release()
        # Released BEFORE [DONE], so a reader that has seen the terminal event
        # can rely on the lock already being free.
        with _LIVE_COND:
            job.events.append("data: [DONE]\n\n")
            job.done = True
            _LIVE_COND.notify_all()


def _invalidate_screener_cache() -> None:
    try:
        from services.screener_data import invalidate_screener_cache

        invalidate_screener_cache()
    except Exception:
        log.exception("failed to invalidate the screener cache after a scan")


def _follow(job: LiveJob) -> Iterator[str]:
    """Stream a live job's events to ONE client, from the beginning.

    Closing this generator — the browser navigating away — does nothing to the
    job. Replaying from index 0 is what makes re-attach work: the client derives
    its progress readout from the lines it has seen, so a fresh reader catches up
    to the current phase by replaying them.
    """
    index = 0
    while True:
        with _LIVE_COND:
            while index >= len(job.events) and not job.done:
                _LIVE_COND.wait(timeout=_FOLLOW_POLL_SECONDS)
            batch = job.events[index:]
            index += len(batch)
            finished = job.done and index >= len(job.events)
        for event in batch:
            yield event
        if finished:
            return


def _stream_process(trigger: str, args: list[str] | None = None,
                    kind: str = "scan", job: str = "evaluation") -> Iterator[str]:
    """Start a manual subprocess job and stream its stdout as server-sent events."""
    global _LIVE_JOB

    if not SCAN_LOCK.acquire(blocking=False):
        yield "data: ERROR: another scan or data job is already running\n\n"
        yield "data: [DONE]\n\n"
        return

    live = LiveJob(trigger=trigger, kind=kind, job=job)
    with _LIVE_COND:
        _LIVE_JOB = live
    threading.Thread(target=_pump_job, args=(live, args),
                     name=f"chrollo-scan-{job}", daemon=True).start()
    yield from _follow(live)


def active_job() -> dict | None:
    """The manual job running right now, or None. This is the verdict a client
    needs in order to re-attach; it never re-derives that from a status row."""
    with _LIVE_COND:
        live = _LIVE_JOB
        if live is None or live.done:
            return None
        return {"job": live.job, "kind": live.kind, "run_id": live.run_id,
                "trigger": live.trigger}


def follow_active_job() -> Iterator[str]:
    """Re-attach a client to the job already running: replay what it has printed
    so far, then follow it live. Serves a single [DONE] when nothing is running."""
    with _LIVE_COND:
        live = _LIVE_JOB
        running = live is not None and not live.done
    if not running:
        yield "data: [DONE]\n\n"
        return
    yield from _follow(live)


def stream_manual_scan() -> Iterator[str]:
    """Run a full manual scan and stream its stdout as server-sent events."""
    yield from _stream_process("manual")


def stream_cached_evaluation() -> Iterator[str]:
    """Evaluate the local market-data cache and stream stdout as SSE."""
    yield from _stream_process("manual_evaluation", ["--cached"], kind="scan")


def stream_data_download() -> Iterator[str]:
    """Refresh market-data cache only and stream stdout as SSE."""
    yield from _stream_process("manual_download", ["--download-only"],
                               kind="download", job="download")


def run_scheduled_scan_and_forward_returns() -> None:
    """Run the scan, then ALWAYS run the forward-return backfill, under one DB lock.

    The backfill matures already-archived rows and does not depend on the scan
    succeeding, so it runs even when the scan fails — a crashing scan must not
    silently starve outcome maturation. The scan status and the backfill report
    independently; the scan's run record still reflects only the scan outcome.
    """
    from core.archive.forward_returns import update_forward_returns
    from services import scan_status

    if not SCAN_LOCK.acquire(blocking=False):
        log.warning("scheduled scan skipped because another scan is already running")
        return

    run_id = scan_status.start_run("scheduled")
    try:
        try:
            # The daily run covers every universe (US-Stocks first); the parsed
            # n_setups reflects the primary US-Stocks run. ETF universes generate
            # their own artifacts and are isolated from each other's failures.
            result = _run_scan_process_unlocked(["--all-universes"])
            status = _result_status(result)
            error = _tail_error(result.output) if status != "ok" else None
            if status != "ok":
                log.error("scheduled scan failed with exit code %s", result.returncode)
            scan_status.finish_run(run_id, status=status, n_setups=result.n_setups, error=error)
            alert_if_needed("scheduled", status, result.n_setups, error, result.n_errored)
        except Exception as exc:
            scan_status.finish_run(run_id, status="failed", error=str(exc))
            alert_if_needed("scheduled", "failed", None, str(exc))
            raise
        finally:
            # Forward-return backfill is independent of the scan: it matures
            # already-archived rows and needs no fresh scan, so run it regardless
            # of scan outcome. Isolated so its own failure neither masks nor is
            # masked by the scan result. Recorded as its OWN scan_runs row
            # (kind='maturation') so a maturation that stalls or throws is visible
            # to the watchdog / health surface instead of vanishing into a swallowed
            # log line (the historical silent-stall root cause).
            mat_run_id = scan_status.start_run("scheduled", kind="maturation")
            try:
                from services.core_settings import load_core_settings

                root_settings = load_core_settings()
                updated = update_forward_returns(
                    min_age_days=getattr(root_settings, "FORWARD_RETURNS_MIN_AGE_DAYS", 5)
                )
                scan_status.finish_run(mat_run_id, status="ok", n_setups=updated)
                log.info("scheduled forward-return update completed: %d setup(s)", updated)
            except Exception as exc:
                scan_status.finish_run(mat_run_id, status="failed", error=str(exc))
                alert_if_needed("scheduled-maturation", "failed", None, str(exc))
                log.exception("scheduled forward-return update failed")
    finally:
        SCAN_LOCK.release()
