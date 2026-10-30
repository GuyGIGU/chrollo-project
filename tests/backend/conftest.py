"""Backend tests never read the live checkout's cache_meta.json.

``scan_runner._last_not_read`` and ``_last_fetch_health`` read ``ROOT_DIR/cache_meta.json``, the record the
nightly scan leaves in the checkout. A test that fakes the scan child but not that record then reads the real
night's list (Fri 30/10/2026: 16 charts not read since the noon scan) and three tests went red for it. Every
backend test starts with the runner's root in an empty folder; a test that fakes the record points ROOT_DIR
at its own tmp_path, as before, and overrides this.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def _scan_runner_root_in_tmp(tmp_path, monkeypatch):
    from webapp.backend.services import scan_runner

    monkeypatch.setattr(scan_runner, "ROOT_DIR", str(tmp_path))
    twin = sys.modules.get("services.scan_runner")       # the same file imported through webapp/backend
    if twin is not None and twin is not scan_runner:
        monkeypatch.setattr(twin, "ROOT_DIR", str(tmp_path))
