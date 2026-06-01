"""Small persistence helpers for scan run status."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from database import engine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_run(trigger: str) -> int:
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


def latest_run() -> dict | None:
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
