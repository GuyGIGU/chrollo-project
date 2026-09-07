"""Broker-free scan runner shared by manual SSE and scheduled jobs."""
from __future__ import annotations

import logging
import os
import json
import subprocess
import sys
import threading
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
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


@contextmanager
def scan_lock() -> Iterator[bool]:
    """THE one-child-at-a-time gate, in ONE shape (EC-3).

    Yields whether the lock was taken; releases it on every exit path,
    including one taken by an exception raised *between* the acquire and the
    first line of work. That gap is not hypothetical: the scheduled job used
    to write its run record on the bare line after ``acquire()``, outside the
    ``try`` whose ``finally`` released — and ``scan_status.start_run`` does a
    SQLite INSERT, which raises on a busy database, the exact condition the
    30-second busy timeout exists to survive. One raise there orphaned the
    lock for the life of the process, and every later scan, scheduled or
    manual, logged "skipped because another scan is already running" and did
    nothing until someone restarted the service (council 2026-09-07, F1).
    Acquiring through this context manager is what makes that unwritable.
    """
    acquired = SCAN_LOCK.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            SCAN_LOCK.release()


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


def _stream_process(trigger: str, args: list[str] | None = None,
                    kind: str = "scan") -> Iterator[str]:
    """Run a manual subprocess job and stream its stdout as server-sent events."""
    with scan_lock() as acquired:
        if not acquired:
            yield "data: ERROR: another scan or data job is already running\n\n"
            yield "data: [DONE]\n\n"
            return

        yield from _stream_locked_process(trigger, args, kind)


def _stream_locked_process(trigger: str, args: list[str] | None,
                           kind: str) -> Iterator[str]:
    """The streamed job itself. Runs only with SCAN_LOCK held; the caller owns
    the release, so nothing in here can orphan it."""
    from services import scan_status

    run_id = None
    run_recorded = False
    process = None
    lines: list[str] = []
    try:
        run_id = scan_status.start_run(trigger, kind=kind)
        process = _create_process(args)
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)
            yield f"data: {line}\n\n"

        process.stdout.close()
        process.wait()
        output = "".join(lines)
        n_setups, n_errored = _parse_scan_result(output)
        result = ScanProcessResult(
            returncode=process.returncode,
            output=output,
            n_setups=n_setups,
            n_errored=n_errored,
        )
        status = _result_status(result)
        error = _tail_error(output) if status != "ok" else None
        scan_status.finish_run(run_id, status=status, n_setups=result.n_setups, error=error)
        run_recorded = True
        alert_if_needed(trigger, status, result.n_setups, error, result.n_errored)
        if process.returncode != 0:
            yield f"data: ERROR: scan exited with code {process.returncode}\n\n"
        yield "data: [DONE]\n\n"
    except GeneratorExit:
        # The browser disconnected mid-stream: Starlette closes this generator,
        # which raises GeneratorExit at the current yield. It is a BaseException,
        # so the `except Exception` below never sees it — without this handler
        # the child kept running unsupervised past the lock release and the
        # scan_runs row stayed 'running' forever. No yields allowed here.
        # run_recorded guards a disconnect at the trailing yields: a run whose
        # outcome is already written must not be relabeled 'aborted'.
        log.warning("scan stream aborted by client disconnect (%s); terminating child", trigger)
        _terminate_child(process)
        if run_id is not None and not run_recorded:
            scan_status.finish_run(run_id, status="aborted",
                                   error="client disconnected mid-stream; child terminated")
        raise
    except Exception as exc:
        _terminate_child(process)
        if run_id is not None and not run_recorded:
            scan_status.finish_run(run_id, status="failed", error=str(exc))
        alert_if_needed(trigger, "failed", None, str(exc))
        yield f"data: ERROR: {exc}\n\n"
        yield "data: [DONE]\n\n"


def stream_manual_scan() -> Iterator[str]:
    """Run a full manual scan and stream its stdout as server-sent events."""
    yield from _stream_process("manual")


def stream_cached_evaluation() -> Iterator[str]:
    """Evaluate the local market-data cache and stream stdout as SSE."""
    yield from _stream_process("manual_evaluation", ["--cached"], kind="scan")


def stream_data_download() -> Iterator[str]:
    """Refresh market-data cache only and stream stdout as SSE."""
    yield from _stream_process("manual_download", ["--download-only"], kind="download")


def run_scheduled_scan_and_forward_returns() -> None:
    """Run the scan, then ALWAYS run the forward-return backfill, under one DB lock.

    The backfill matures already-archived rows and does not depend on the scan
    succeeding, so it runs even when the scan fails — a crashing scan must not
    silently starve outcome maturation. The scan status and the backfill report
    independently; the scan's run record still reflects only the scan outcome.
    """
    from core.archive.forward_returns import update_forward_returns
    from services import scan_status

    with scan_lock() as acquired:
        if not acquired:
            log.warning("scheduled scan skipped because another scan is already running")
            return

        run_id = scan_status.start_run("scheduled")
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
