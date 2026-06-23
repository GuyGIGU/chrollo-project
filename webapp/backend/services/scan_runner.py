"""Broker-free scan runner shared by manual SSE and scheduled jobs."""
from __future__ import annotations

import logging
import os
import json
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Iterator

from services.notify import post_webhook

log = logging.getLogger("chrollo.scan")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCREENER_SCRIPT = os.path.join(ROOT_DIR, "run_screener.py")
SCAN_LOCK = threading.Lock()

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


@dataclass
class ScanProcessResult:
    returncode: int
    output: str
    n_setups: int | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _create_process() -> subprocess.Popen:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # Force UTF-8 on the child's stdio. Under the Windows service (and any piped
    # subprocess) Python otherwise defaults stdout to the locale codec (cp1252),
    # which crashes the instant the pipeline prints a non-Latin-1 char such as
    # "→" or an emoji tag. PYTHONUTF8/PYTHONIOENCODING fix the *encode* side
    # in the child; encoding+errors fix the *decode* side here in the parent.
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.Popen(
        [sys.executable, SCREENER_SCRIPT],
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


def _run_scan_process_unlocked() -> ScanProcessResult:
    process = _create_process()
    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        lines.append(line)
        log.info("[scan] %s", line.rstrip())
    process.stdout.close()
    process.wait()
    output = "".join(lines)
    return ScanProcessResult(
        returncode=process.returncode,
        output=output,
        n_setups=_parse_n_setups(output),
    )


def _parse_n_setups(output: str) -> int | None:
    prefix = "SCAN_RESULT_JSON:"
    for line in reversed(output.splitlines()):
        if line.startswith(prefix):
            try:
                payload = json.loads(line[len(prefix):].strip())
                return int(payload.get("n_setups", 0))
            except Exception:
                return None
    return None


def _result_status(result: ScanProcessResult) -> str:
    if result.ok:
        return "ok"
    if "StaleMarketDataError" in result.output or "stale market data" in result.output.lower():
        return "stale_data"
    return "failed"


def _tail_error(output: str, limit: int = 4000) -> str | None:
    text = output.strip()
    if not text:
        return None
    for line in reversed(text.splitlines()):
        if "stale market data" in line.lower():
            return line.strip()
    traceback_idx = text.rfind("Traceback (most recent call last):")
    if traceback_idx >= 0:
        return text[traceback_idx:][-limit:]
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
                    alert_on_zero: bool, alert_on_degraded: bool) -> str | None:
    """Return a human-readable alert reason, or None if no alert is warranted.

    Pure (no I/O) so it is unit-testable. A failed/stale scan alerts on its
    status; a successful scan with zero results alerts when enabled; a successful
    scan whose fetch came back unhealthy (low return ratio) alerts as an early
    warning, before the degradation escalates to a stale_data failure.
    """
    if status in ("failed", "stale_data"):
        return status
    if n_setups == 0 and alert_on_zero:
        return "zero scan results"
    if (alert_on_degraded and isinstance(fetch_health, dict)
            and fetch_health.get("healthy") is False):
        return (f"degraded data fetch (mode={fetch_health.get('mode')}, "
                f"return_ratio={fetch_health.get('return_ratio')})")
    return None


def alert_if_needed(trigger: str, status: str, n_setups: int | None, error: str | None = None) -> None:
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
    )
    if reason is None:
        return

    message = f"Chrollo scan alert ({trigger}): {reason}; setups={n_setups}"
    if error:
        message = f"{message}; error={error[:300]}"
    log.warning(message)

    post_webhook(message)


def stream_manual_scan() -> Iterator[str]:
    """Run a manual scan and stream its stdout as server-sent events."""
    from services import scan_status

    if not SCAN_LOCK.acquire(blocking=False):
        yield "data: ERROR: another scan is already running\n\n"
        yield "data: [DONE]\n\n"
        return

    run_id = scan_status.start_run("manual")
    process = None
    finished = False
    lines: list[str] = []
    try:
        process = _create_process()
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)
            yield f"data: {line}\n\n"

        process.stdout.close()
        process.wait()
        output = "".join(lines)
        result = ScanProcessResult(
            returncode=process.returncode,
            output=output,
            n_setups=_parse_n_setups(output),
        )
        status = _result_status(result)
        error = _tail_error(output) if status != "ok" else None
        scan_status.finish_run(run_id, status=status, n_setups=result.n_setups, error=error)
        finished = True
        alert_if_needed("manual", status, result.n_setups, error)
        if process.returncode != 0:
            yield f"data: ERROR: scan exited with code {process.returncode}\n\n"
        yield "data: [DONE]\n\n"
    except GeneratorExit:
        if not finished:
            _terminate_process(process)
            error = "manual scan stream disconnected"
            scan_status.finish_run(run_id, status="failed", error=error)
            log.warning(error)
        raise
    except Exception as exc:
        _terminate_process(process)
        scan_status.finish_run(run_id, status="failed", error=str(exc))
        alert_if_needed("manual", "failed", None, str(exc))
        yield f"data: ERROR: {exc}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        SCAN_LOCK.release()


def _terminate_process(process) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


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
            result = _run_scan_process_unlocked()
            status = _result_status(result)
            error = _tail_error(result.output) if status != "ok" else None
            if status != "ok":
                log.error("scheduled scan failed with exit code %s", result.returncode)
            scan_status.finish_run(run_id, status=status, n_setups=result.n_setups, error=error)
            alert_if_needed("scheduled", status, result.n_setups, error)
        except Exception as exc:
            scan_status.finish_run(run_id, status="failed", error=str(exc))
            alert_if_needed("scheduled", "failed", None, str(exc))
            raise
        finally:
            # Forward-return backfill is independent of the scan: it matures
            # already-archived rows and needs no fresh scan, so run it regardless
            # of scan outcome. Isolated so its own failure neither masks nor is
            # masked by the scan result.
            try:
                from services.core_settings import load_core_settings

                root_settings = load_core_settings()
                updated = update_forward_returns(
                    min_age_days=getattr(root_settings, "FORWARD_RETURNS_MIN_AGE_DAYS", 5)
                )
                log.info("scheduled forward-return update completed: %d setup(s)", updated)
            except Exception:
                log.exception("scheduled forward-return update failed")
    finally:
        SCAN_LOCK.release()
