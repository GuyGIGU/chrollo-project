"""Broker-free scan runner shared by manual SSE and scheduled jobs."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
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

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _create_process() -> subprocess.Popen:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    return subprocess.Popen(
        [sys.executable, SCREENER_SCRIPT],
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=flags,
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
    return ScanProcessResult(returncode=process.returncode, output="".join(lines))


def stream_manual_scan() -> Iterator[str]:
    """Run a manual scan and stream its stdout as server-sent events."""
    if not SCAN_LOCK.acquire(blocking=False):
        yield "data: ERROR: another scan is already running\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        process = _create_process()
        assert process.stdout is not None
        for line in process.stdout:
            yield f"data: {line}\n\n"

        process.stdout.close()
        process.wait()
        if process.returncode != 0:
            yield f"data: ERROR: scan exited with code {process.returncode}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as exc:
        yield f"data: ERROR: {exc}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        SCAN_LOCK.release()


def run_scheduled_scan_and_forward_returns() -> None:
    """Run scan then forward-return backfill sequentially under one DB-write lock."""
    from core.archive.forward_returns import update_forward_returns

    if not SCAN_LOCK.acquire(blocking=False):
        log.warning("scheduled scan skipped because another scan is already running")
        return

    try:
        result = _run_scan_process_unlocked()
        if not result.ok:
            log.error("scheduled scan failed with exit code %s", result.returncode)
            return

        from services.core_settings import load_core_settings

        root_settings = load_core_settings()
        updated = update_forward_returns(
            min_age_days=getattr(root_settings, "FORWARD_RETURNS_MIN_AGE_DAYS", 5)
        )
        log.info("scheduled forward-return update completed: %d setup(s)", updated)
    finally:
        SCAN_LOCK.release()
