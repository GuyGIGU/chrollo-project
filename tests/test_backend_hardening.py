import asyncio
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.routers import archive_browse, portfolio, trades
from webapp.backend.services import archive_jobs
from webapp.backend.services.db_write import commit_or_http


def test_trade_list_declares_bounded_pagination():
    route = next(route for route in trades.router.routes if route.path == "/trades/" and "GET" in route.methods)
    params = {param.name: param for param in route.dependant.query_params}

    assert _constraint(params["skip"], "ge") == 0
    assert _constraint(params["limit"], "ge") == 1
    assert _constraint(params["limit"], "le") == 1000


def test_archive_sort_fields_are_whitelisted():
    with pytest.raises(HTTPException) as exc:
        archive_browse.list_episodes(sort_by="__dict__")

    assert exc.value.status_code == 400
    assert "Unsupported sort field" in exc.value.detail


def test_portfolio_csv_reader_stops_when_size_cap_is_crossed(monkeypatch):
    monkeypatch.setattr(portfolio, "_MAX_CSV_BYTES", 5)
    monkeypatch.setattr(portfolio, "_CSV_CHUNK_BYTES", 3)

    class FakeUpload:
        def __init__(self):
            self._chunks = [b"abc", b"def"]

        async def read(self, _size):
            return self._chunks.pop(0) if self._chunks else b""

    with pytest.raises(HTTPException) as exc:
        asyncio.run(portfolio._read_limited_upload(FakeUpload()))

    assert exc.value.status_code == 413


def test_commit_or_http_rolls_back_integrity_errors():
    class DB:
        rolled_back = False

        def commit(self):
            raise IntegrityError("insert", {}, Exception("duplicate"))

        def rollback(self):
            self.rolled_back = True

    db = DB()

    with pytest.raises(HTTPException) as exc:
        commit_or_http(db, conflict_detail="duplicate")

    assert exc.value.status_code == 409
    assert exc.value.detail == "duplicate"
    assert db.rolled_back is True


def test_archive_job_suppresses_duplicate_running_jobs():
    kind = "test_forward_returns_guard"
    started = threading.Event()
    release = threading.Event()

    def runner():
        started.set()
        release.wait(timeout=2)
        return subprocess.CompletedProcess(["test"], 0, "done", "")

    with archive_jobs._JOBS_LOCK:
        archive_jobs._JOBS.pop(kind, None)


def _constraint(param, name):
    for item in param.field_info.metadata:
        if hasattr(item, name):
            return getattr(item, name)
    return None

    first = archive_jobs.start_job(kind, runner)
    assert started.wait(timeout=1)

    second = archive_jobs.start_job(kind, runner)
    release.set()

    assert first["status"] == "running"
    assert second["already_running"] is True
    assert second["id"] == first["id"]

    deadline = time.time() + 2
    status = archive_jobs.get_job_status(kind)
    while status["status"] == "running" and time.time() < deadline:
        time.sleep(0.01)
        status = archive_jobs.get_job_status(kind)

    assert status["status"] == "succeeded"
    assert status["returncode"] == 0

    with archive_jobs._JOBS_LOCK:
        archive_jobs._JOBS.pop(kind, None)
