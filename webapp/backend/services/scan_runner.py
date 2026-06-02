"""Broker-free scan runner shared by manual SSE and scheduled jobs."""
from __future__ import annotations

import logging
import os
import json
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass
from typing import Iterator

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


def _tail_error(output: str, limit: int = 1000) -> str | None:
    text = output.strip()
    if not text:
        return None
    return text[-limit:]


def alert_if_needed(trigger: str, status: str, n_setups: int | None, error: str | None = None) -> None:
    from services.core_settings import load_core_settings

    settings = load_core_settings()
    zero_result = n_setups == 0 and bool(getattr(settings, "ALERT_ON_ZERO_RESULTS", True))
    should_alert = status in {"failed", "stale_data"} or zero_result
    if not should_alert:
        return

    reason = "zero scan results" if zero_result and status == "ok" else status
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


def stream_manual_scan() -> Iterator[str]:
    """Run a manual scan and stream its stdout as server-sent events."""
    from services import scan_status

    if not SCAN_LOCK.acquire(blocking=False):
        yield "data: ERROR: another scan is already running\n\n"
        yield "data: [DONE]\n\n"
        return

    run_id = scan_status.start_run("manual")
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
        alert_if_needed("manual", status, result.n_setups, error)
        if process.returncode != 0:
            yield f"data: ERROR: scan exited with code {process.returncode}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as exc:
        scan_status.finish_run(run_id, status="failed", error=str(exc))
        alert_if_needed("manual", "failed", None, str(exc))
        yield f"data: ERROR: {exc}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        SCAN_LOCK.release()


def run_scheduled_scan_and_forward_returns() -> None:
    """Run scan then forward-return backfill sequentially under one DB-write lock."""
    from core.archive.forward_returns import update_forward_returns
    from services import scan_status

    if not SCAN_LOCK.acquire(blocking=False):
        log.warning("scheduled scan skipped because another scan is already running")
        return

    run_id = scan_status.start_run("scheduled")
    try:
        result = _run_scan_process_unlocked()
        status = _result_status(result)
        if status != "ok":
            error = _tail_error(result.output)
            scan_status.finish_run(run_id, status=status, n_setups=result.n_setups, error=error)
            alert_if_needed("scheduled", status, result.n_setups, error)
            log.error("scheduled scan failed with exit code %s", result.returncode)
            return

        from services.core_settings import load_core_settings

        root_settings = load_core_settings()
        updated = update_forward_returns(
            min_age_days=getattr(root_settings, "FORWARD_RETURNS_MIN_AGE_DAYS", 5)
        )
        log.info("scheduled forward-return update completed: %d setup(s)", updated)
        scan_status.finish_run(run_id, status="ok", n_setups=result.n_setups)
        alert_if_needed("scheduled", "ok", result.n_setups)
    except Exception as exc:
        scan_status.finish_run(run_id, status="failed", error=str(exc))
        alert_if_needed("scheduled", "failed", None, str(exc))
        raise
    finally:
        SCAN_LOCK.release()
