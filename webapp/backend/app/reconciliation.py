"""Record interrupted scan runs before background services start."""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text
import archive_models
import models

_log = logging.getLogger("chrollo.migrate")

from services.scan_diagnosis import PENDING_KIND, RECONCILE_MARKER

def _reconcile_orphaned_runs(bind) -> None:
    """Mark any scan_runs row left status='running' as failed on boot.

    start_run() inserts status='running' and finish_run() only runs if the process
    survives; a hard kill (SIGKILL / OOM / power loss / container stop) between them
    orphans the row forever. Nothing else ever rewrites it, so latest_run() would
    keep returning 'running' — mislabeling a crash and, worse, pinning
    _scan_is_running() True, which silently suppresses the live-price fallback until
    a new run completes. Reconciling at boot is safe: the scheduler has not started
    and no scan/maturation is in flight yet, so every 'running' row here is genuinely
    orphaned. Idempotent and best-effort — a missing table or transient error must
    never block backend boot.

    This RECORDS A FACT and claims no cause. The row is tagged with the pending
    failure kind; services/scan_diagnosis.resolve_pending works out WHY later,
    from the backend's lifespan startup, when the Windows Event Log service is
    actually up. Measured 2026-09-05: this reconcile can run seconds INTO a
    shutdown (NSSM restarts uvicorn as Windows stops the service), one second
    after the Event Log service has already stopped — so no evidence read and no
    boot-time comparison belongs on this path. ``finished_at`` is stamped as the
    moment the orphan was DETECTED, which is what makes the later diagnosis
    possible; it is not a completion time.
    """
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with bind.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE scan_runs SET status = 'failed', "
                    "finished_at = COALESCE(finished_at, :now), "
                    "error = COALESCE(error, :marker), "
                    "failure_kind = COALESCE(failure_kind, :pending) "
                    "WHERE status = 'running'"
                ),
                {"now": now_iso, "marker": RECONCILE_MARKER, "pending": PENDING_KIND},
            )
            n = result.rowcount
        if n:
            _log.warning(
                "reconciled %d orphaned 'running' scan_runs row(s) at boot "
                "(cause pending: %s)", n, PENDING_KIND,
            )
    except Exception as exc:  # pragma: no cover - defensive; boot must not fail
        _log.warning("orphaned scan_runs reconcile skipped (%s)", exc.__class__.__name__)


