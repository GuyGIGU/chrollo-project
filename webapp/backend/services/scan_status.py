"""Small persistence helpers for scan run status.

The ``kind`` column is guaranteed by the boot migrations (services/startup.py
creates scan_runs WITH it and carries an idempotent ALTER) — no per-call schema
sniffing here. The COALESCE keeps any explicit-NULL row reading as 'scan'.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from database import engine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_run(trigger: str, kind: str = "scan") -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO scan_runs (started_at, status, trigger, kind)
                VALUES (:started_at, :status, :trigger, :kind)
                """
            ),
            {"started_at": _now_iso(), "status": "running", "trigger": trigger, "kind": kind},
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


def latest_run(kind: str | None = "scan") -> dict | None:
    with engine.connect() as conn:
        where = "WHERE COALESCE(kind, 'scan') = :kind" if kind else ""
        params = {"kind": kind} if kind else {}
        row = conn.execute(
            text(
                f"""
                SELECT id, started_at, finished_at, status, n_setups, error, trigger,
                       COALESCE(kind, 'scan') AS kind, failure_kind
                FROM scan_runs
                {where}
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            params,
        ).mappings().first()
        return dict(row) if row else None


def recent_runs(limit: int = 20, kind: str | None = "scan") -> list[dict]:
    """Most recent scan runs, newest first (for the in-app scan-history view)."""
    limit = max(1, min(int(limit), 100))
    with engine.connect() as conn:
        where = "WHERE COALESCE(kind, 'scan') = :kind" if kind else ""
        params = {"limit": limit}
        if kind:
            params["kind"] = kind
        rows = conn.execute(
            text(
                f"""
                SELECT id, started_at, finished_at, status, n_setups, error, trigger,
                       COALESCE(kind, 'scan') AS kind, failure_kind
                FROM scan_runs
                {where}
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(r) for r in rows]


def never_run(kind: str = "scan") -> dict:
    """The shape a fresh install serves when no run has ever been recorded.

    Lives here rather than being hand-typed in the route so the 'never' row goes
    through exactly the same enrichment as a real row and can never be missing a
    field every other row carries.
    """
    return {
        "id": None,
        "started_at": None,
        "finished_at": None,
        "status": "never",
        "n_setups": None,
        "error": None,
        "trigger": None,
        "kind": kind,
        "failure_kind": None,
    }
