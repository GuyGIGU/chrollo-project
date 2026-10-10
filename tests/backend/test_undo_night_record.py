"""The undo night through the service: its run row says "not archived".

Go-live plan task 8. ``run_screener.py --no-archive`` prints ``"archived": false``
on its one result line; the service passes the flag through from the Evaluate
route, reads the key back, and writes it into the run's own row — so the night's
record carries it, not only the log. Hermetic: the child process and the run
store are faked.
"""
from __future__ import annotations

import sys

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.services import scan_runner


@pytest.fixture(autouse=True)
def _no_live_job_leaks():
    scan_runner._LIVE_JOB = None
    yield
    scan_runner._LIVE_JOB = None
    assert not scan_runner.SCAN_LOCK.locked(), "a test left SCAN_LOCK held"


def test_the_result_line_says_whether_the_night_was_archived():
    off = scan_runner._parse_scan_result(
        'SCAN_RESULT_JSON:{"n_setups": 4, "n_archived": 0, "archived": false}\n')
    on = scan_runner._parse_scan_result('SCAN_RESULT_JSON:{"n_setups": 4, "n_archived": 4}\n')
    assert off.archived is False
    assert on.archived is True          # today's line, no key: archived as always
    assert scan_runner._parse_scan_result("no line at all").archived is True


def _fake_child(monkeypatch, output: str) -> dict:
    import services.scan_status as scan_status_mod

    calls: dict = {}

    class FakeStdout:
        def __iter__(self):
            return iter([output])

        def close(self):
            pass

    class FakeProcess:
        stdout = FakeStdout()
        returncode = 0

        def wait(self):
            pass

    def fake_create_process(args=None):
        calls["args"] = args
        return FakeProcess()

    monkeypatch.setattr(scan_runner, "_create_process", fake_create_process)
    monkeypatch.setattr(scan_status_mod, "start_run", lambda trigger, kind="scan": 42)
    monkeypatch.setattr(scan_status_mod, "finish_run",
                        lambda run_id, status, n_setups=None, error=None:
                            calls.__setitem__("finish", (run_id, status, n_setups, error)))
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)
    return calls


def test_the_undo_evaluation_runs_every_universe_unarchived_and_its_row_says_so(monkeypatch):
    calls = _fake_child(
        monkeypatch, 'SCAN_RESULT_JSON:{"n_setups": 5, "n_archived": 0, "archived": false}\n')

    events = list(scan_runner.stream_cached_evaluation(archive=False))

    assert calls["args"] == ["--cached", "--all-universes", "--no-archive"]
    run_id, status, n_setups, error = calls["finish"]
    assert (run_id, status, n_setups) == (42, "ok", 5)
    assert error is not None and "not archived" in error.lower()
    assert any("[DONE]" in e for e in events)


def test_a_normal_evaluation_row_is_unchanged(monkeypatch):
    calls = _fake_child(monkeypatch, 'SCAN_RESULT_JSON:{"n_setups": 5, "n_archived": 5}\n')

    list(scan_runner.stream_cached_evaluation())

    assert calls["args"] == ["--cached"]
    assert calls["finish"] == (42, "ok", 5, None)


def test_the_evaluate_route_passes_the_undo_flag_through(monkeypatch):
    from domains.screener import router as screener_router

    seen = []
    monkeypatch.setattr(screener_router.scan_runner, "stream_cached_evaluation",
                        lambda archive=True: seen.append(archive) or iter(()))

    screener_router.run_cached_evaluation_stream(no_archive=True)
    screener_router.run_cached_evaluation_stream()

    assert seen == [False, True]
