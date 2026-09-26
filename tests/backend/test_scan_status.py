"""scan_runs status helpers run on the boot-migrated schema only (council
2026-08-22, Ramirez F7): the per-call PRAGMA sniff and the no-kind SQL twins
are deleted — app/startup.py creates scan_runs WITH the kind column and
carries the idempotent ALTER, so these tests pin the helpers against exactly
that boot schema (built from startup's own CREATE statement)."""
from __future__ import annotations

import sys

import pytest
from sqlalchemy import create_engine, text

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import services.scan_status as scan_status_mod  # noqa: E402
from app.startup import _MIGRATIONS  # noqa: E402


@pytest.fixture()
def status_engine(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'status.db'}")
    create_scan_runs = next(
        s for s in _MIGRATIONS if "CREATE TABLE IF NOT EXISTS scan_runs" in s
    )
    with eng.begin() as conn:
        conn.execute(text(create_scan_runs))
    monkeypatch.setattr(scan_status_mod, "engine", eng)
    return eng


def test_start_finish_latest_round_trip_with_kind(status_engine):
    run_id = scan_status_mod.start_run("manual", kind="maturation")
    scan_status_mod.finish_run(run_id, "ok", n_setups=3)

    latest = scan_status_mod.latest_run(kind="maturation")
    assert latest["id"] == run_id
    assert latest["kind"] == "maturation"
    assert latest["status"] == "ok"
    assert latest["n_setups"] == 3
    # The kind filter still filters: no scan-kind run exists yet.
    assert scan_status_mod.latest_run(kind="scan") is None


def test_recent_runs_filters_by_kind_and_none_means_all(status_engine):
    scan_status_mod.start_run("scheduled")  # default kind='scan'
    scan_status_mod.start_run("os", kind="maturation")

    assert [r["kind"] for r in scan_status_mod.recent_runs(kind="scan")] == ["scan"]
    assert len(scan_status_mod.recent_runs(kind=None)) == 2
    assert scan_status_mod.latest_run(kind=None)["kind"] == "maturation"


def test_explicit_null_kind_row_still_reads_as_scan(status_engine):
    # The COALESCE belt survives the simplification: a row with kind
    # explicitly NULL (never produced by these helpers) reads as 'scan'.
    with status_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO scan_runs (started_at, status, trigger, kind) "
            "VALUES ('2026-08-22T00:00:00+00:00', 'ok', 'manual', NULL)"
        ))

    latest = scan_status_mod.latest_run(kind="scan")
    assert latest is not None
    assert latest["kind"] == "scan"


# ── the wire: one resolver for both routes (EC-39) ────────────────────────────
def test_latest_and_history_agree_on_reason_and_solution(status_engine, monkeypatch):
    """The single-item route and its list sibling resolve every row through the
    SAME function, so the topbar pill and the diagnostics registry cannot tell
    the operator two different stories about one run."""
    import domains.screener.router as screener_router

    run_id = scan_status_mod.start_run("scheduled")
    scan_status_mod.finish_run(run_id, "aborted", error="client disconnected mid-stream")
    monkeypatch.setattr(screener_router.scan_diagnosis, "current_missed_slot_notice",
                        lambda: None)

    latest = screener_router.get_latest_scan_status()
    history = screener_router.get_scan_status_history(limit=5, kind="scan")["runs"][0]

    assert latest["id"] == history["id"] == run_id
    assert latest["reason"] == history["reason"]
    assert latest["solution"] == history["solution"]
    assert latest["reason"]


def test_history_widens_to_the_other_jobs_only_when_asked(status_engine, monkeypatch):
    """`kind=all` is what surfaces the outcome-backfill and download failures no
    surface had ever shown; the Archive header's Scan History button opens it.
    Pinning the route back to scans alone must not pass silently."""
    import domains.screener.router as screener_router

    monkeypatch.setattr(screener_router.scan_diagnosis, "current_missed_slot_notice",
                        lambda: None)
    scan_id = scan_status_mod.start_run("scheduled")
    scan_status_mod.finish_run(scan_id, "failed", error="boom")
    mat_id = scan_status_mod.start_run("os_task", kind="maturation")
    scan_status_mod.finish_run(mat_id, "failed", error="boom")

    everything = screener_router.get_scan_status_history(limit=5, kind="all")["runs"]
    scans_only = screener_router.get_scan_status_history(limit=5, kind="scan")["runs"]

    assert {r["id"] for r in everything} == {scan_id, mat_id}
    assert {r["id"] for r in scans_only} == {scan_id}
    # And the backfill row is described as a backfill, not as "the scan".
    backfill = next(r for r in everything if r["id"] == mat_id)
    assert "the outcome backfill" in backfill["reason"].lower()
    assert "Evaluate" not in backfill["solution"]


def test_the_never_row_still_carries_the_resolved_fields(status_engine):
    """A fresh install must not serve a row shaped differently from every other
    row — the 'never' fallback goes through the same enrichment."""
    import domains.screener.router as screener_router

    payload = screener_router.get_latest_scan_status()

    assert payload["status"] == "never"
    for key in ("reason", "solution", "kind", "failure_kind"):
        assert key in payload


def test_failure_kind_travels_on_both_read_paths(status_engine):
    with status_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO scan_runs (started_at, status, trigger, kind, failure_kind) "
            "VALUES ('2026-09-04T22:00:01+00:00', 'failed', 'scheduled', 'scan', "
            "'interrupted_shutdown')"
        ))

    assert scan_status_mod.latest_run()["failure_kind"] == "interrupted_shutdown"
    assert scan_status_mod.recent_runs()[0]["failure_kind"] == "interrupted_shutdown"
