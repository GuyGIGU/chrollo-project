"""Guarded background jobs for archive maintenance actions."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from services.scan_runner import SCAN_LOCK

log = logging.getLogger("chrollo.archive_jobs")

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_JOBS: Dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


class ArchiveJobBusy(RuntimeError):
    """Raised when a guarded archive job cannot safely start."""


def start_forward_returns_job() -> dict:
    return start_job("forward_returns", _run_forward_returns)


def get_job_status(kind: str) -> dict:
    with _JOBS_LOCK:
        job = _JOBS.get(kind)
        if job is None:
            return {"kind": kind, "status": "idle"}
        return dict(job)


def start_job(kind: str, runner: Callable[[], subprocess.CompletedProcess]) -> dict:
    with _JOBS_LOCK:
        existing = _JOBS.get(kind)
        if existing and existing.get("status") == "running":
            return {**existing, "already_running": True}

        job = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "status": "running",
            "started_at": _now_iso(),
            "finished_at": None,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": None,
            "already_running": False,
        }
        _JOBS[kind] = job

    thread = threading.Thread(
        target=_run_job,
        args=(kind, job["id"], runner),
        daemon=True,
        name=f"archive-{kind}",
    )
    thread.start()
    return dict(job)


def _run_job(kind: str, job_id: str, runner: Callable[[], subprocess.CompletedProcess]) -> None:
    status = "failed"
    returncode = None
    stdout = ""
    stderr = ""
    error = None
    try:
        result = runner()
        returncode = result.returncode
        stdout = _tail(result.stdout, 2000)
        stderr = _tail(result.stderr, 1000)
        status = "succeeded" if result.returncode == 0 else "failed"
    except ArchiveJobBusy as exc:
        status = "blocked"
        error = str(exc)
    except subprocess.TimeoutExpired as exc:
        status = "failed"
        error = "archive job timed out"
        stdout = _tail(exc.stdout, 2000)
        stderr = _tail(exc.stderr, 1000)
    except Exception as exc:
        log.exception("archive job failed: %s", kind)
        status = "failed"
        error = str(exc)

    with _JOBS_LOCK:
        job = _JOBS.get(kind)
        if not job or job.get("id") != job_id:
            return
        job.update({
            "status": status,
            "finished_at": _now_iso(),
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "error": error,
            "already_running": False,
        })


def _run_forward_returns() -> subprocess.CompletedProcess:
    if not SCAN_LOCK.acquire(blocking=False):
        raise ArchiveJobBusy("A scan or archive update is already running")
    try:
        script = os.path.join(_ROOT_DIR, "core", "archive", "forward_returns.py")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, script],
            cwd=_ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            creationflags=flags,
            env=env,
        )
    finally:
        SCAN_LOCK.release()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail(value: Any, limit: int) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)[-limit:]
