"""Small persistence helpers for scan run status."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from database import engine

STALE_RUNNING_MINUTES = 120


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_run(trigger: str) -> int:
    mark_stale_running()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO scan_runs (started_at, status, trigger)
                VALUES (:started_at, :status, :trigger)
                """
            ),
            {
                "started_at": _now_iso(),
                "status": "running",
                "trigger": trigger,
            },
        )
        return int(result.lastrowid)


def finish_run(run_id: int, status: str, n_setups: int | None = None, error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE scan_runs
                SET finished_at = :finished_at,
                    status = :status,
                    n_setups = :n_setups,
                    error = :error
                WHERE id = :id
                """
            ),
            {
                "id": run_id,
                "finished_at": _now_iso(),
                "status": status,
                "n_setups": n_setups,
                "error": error,
            },
        )


def mark_stale_running(max_age_minutes: int = STALE_RUNNING_MINUTES) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE scan_runs
                SET finished_at = :finished_at,
                    status = :status,
                    error = :error
                WHERE status = 'running'
                  AND started_at < :cutoff
                """
            ),
            {
                "finished_at": _now_iso(),
                "status": "failed",
                "error": "scan status expired before completion",
                "cutoff": cutoff.isoformat(),
            },
        )


def latest_run() -> dict | None:
    mark_stale_running()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, started_at, finished_at, status, n_setups, error, trigger
                FROM scan_runs
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        return dict(row) if row else None


def recent_runs(limit: int = 20) -> list[dict]:
    """Most recent scan runs, newest first (for the in-app scan-history view)."""
    mark_stale_running()
    limit = max(1, min(int(limit), 100))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, started_at, finished_at, status, n_setups, error, trigger
                FROM scan_runs
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]
