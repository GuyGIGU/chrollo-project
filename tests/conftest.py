"""Shared pytest fixtures.

The one frame builder a test still names (``_flat_frame``), exposed as a factory
fixture: the fixture returns the builder function. The old engine's other
builders and the ``old_reader`` fixture left with that engine (Sat 31/10/2026).

It also redirects the backend database away from the operator's live archive
for the whole session — see the module-scope block below.
"""

import os
import shutil
import sys
import tempfile

import pandas as pd
import pytest

# ── the live archive is OFF LIMITS to the suite ────────────────────────────
# `import main` runs initialize_database() at import scope, and three test
# modules import main in a subprocess with cwd=webapp/backend. Left alone that
# migrates webapp/backend/trading_journal.db (12,507 archived setups) and its
# orphaned-run reconcile rewrites any in-flight scan row to status='failed' —
# observed in the operator's archive. Point the whole session at a throwaway
# file instead. This runs at conftest IMPORT time, before pytest collects any
# test module, so a module-scope `import database` already sees it; children
# inherit it through os.environ. tests/integration/test_db_isolation.py is the guard.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="chrollo-test-db-")
os.environ["CHROLLO_DB_PATH"] = os.path.join(_TEST_DB_DIR, "trading_journal.db")

# ...and the STRUCTURAL half. The line above only protects call sites that READ
# the override; this refuses the live path at the sqlite driver itself, so it
# covers all ten front doors at once — including any new one somebody adds. It
# refuses rather than redirects: a test that reaches the archive is a defect to
# surface, not to paper over. Proven against a decoy path in
# tests/integration/test_db_isolation.py, never against the real one (register row 18).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_archive_guard import install as _install_live_archive_guard  # noqa: E402
from core.archive.db_path import DEFAULT_DB_PATH as _LIVE_DB_PATH  # noqa: E402

_install_live_archive_guard(_LIVE_DB_PATH)


@pytest.fixture(scope="session", autouse=True)
def _discard_the_throwaway_database():
    yield
    # Return the pooled SQLite handles first: on Windows an open handle keeps
    # the file undeletable and the directory would survive every run.
    db = sys.modules.get("database")
    if db is not None:
        db.engine.dispose()
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_sec_requests(monkeypatch):
    """No test asks the SEC: the live config names a contact (the operator's, 2026-10-12),
    which would turn every fundamentals test into a network call. A test of the SEC fill
    passes its own contact and fakes the fetch."""
    from config import settings

    monkeypatch.setattr(settings, "SEC_CONTACT", "")


@pytest.fixture
def _flat_frame():
    """High == Low == Close, so a swing's amplitude is the raw close move (no
    band inflation) — needed to exercise genuinely sub-threshold reversals."""
    def _build(closes):
        return pd.DataFrame({"High": list(closes), "Low": list(closes), "Close": list(closes)})
    return _build
