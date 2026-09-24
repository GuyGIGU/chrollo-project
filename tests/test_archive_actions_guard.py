"""/analysis and /update-returns join the same-app guarded posture (council
2026-08-22, Ramirez F4): both were reachable as CORS "simple requests" — a GET
and a body-less POST need no preflight — so a drive-by page could spawn 120s
analysis subprocesses and hold SCAN_LOCK across the 18:00 scheduled scan's
non-blocking acquire. Mirrors the watchlist/candles guard-declaration pins."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from domains.archive import actions as archive_actions  # noqa: E402
from domains.calibration.router import require_same_app  # noqa: E402


def _guard_declared(path: str) -> bool:
    for route in archive_actions.router.routes:
        if route.path == path:
            return require_same_app in [d.call for d in route.dependant.dependencies]
    raise AssertionError(f"route {path} not registered")


def test_analysis_declares_the_cross_app_guard():
    assert _guard_declared("/analysis")


def test_update_returns_declares_the_cross_app_guard():
    assert _guard_declared("/update-returns")
