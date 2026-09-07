"""The suite may never open the operator's live archive.

``webapp/backend/main.py`` calls ``initialize_database()`` at IMPORT scope, so
the sanctioned "import main to check the routes registered" verification runs
the whole migration battery — ``create_all``, the ALTER list, three rebuild
migrations, and ``_reconcile_orphaned_runs``, which rewrites any ``scan_runs``
row still marked 'running' to 'failed'. Three test modules import main
(``test_service_boot``, ``test_request_logging``, ``test_engine_alpha_runtime``),
so before ``CHROLLO_DB_PATH`` existed a plain ``pytest`` run migrated
``webapp/backend/trading_journal.db`` and could stamp an in-flight scan failed —
that exact string is in the operator's archive.

These are behavioural guards, not assertions about a constant: one asks the
bound engine which FILE it actually opens, the other refuses the live path at
the sqlite driver and imports main the way the service does. Both go red if the
live database becomes reachable from a test session again.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
LIVE_DB = BACKEND_DIR / "trading_journal.db"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))


def _same_file_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def test_the_bound_engine_opens_a_file_that_is_not_the_live_archive():
    """Ask SQLite itself, through the engine the whole backend imports.

    ``PRAGMA database_list`` reports the file the connection is actually
    attached to, so this survives any amount of path plumbing between the env
    var and the engine — including someone rebuilding the engine from a stale
    constant.
    """
    import database

    with database.engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA database_list").fetchall()
    opened = [r[2] for r in rows if r[1] == "main" and r[2]]
    assert opened, "the engine attached no file - cannot prove isolation"
    assert not _same_file_path(opened[0], str(LIVE_DB)), (
        f"the test session's engine is bound to the LIVE archive ({opened[0]}); "
        "tests/conftest.py must point CHROLLO_DB_PATH at a throwaway file"
    )


def test_importing_main_from_the_service_cwd_never_opens_the_live_archive():
    """Import main exactly the way the service (and three test modules) do,
    with the live path refused at the sqlite driver.

    The child raises BEFORE any connection is made, so even a failing run
    cannot write to the archive — the guard is safe to fail.
    """
    code = (
        "import os, sqlite3, sqlite3.dbapi2\n"
        f"LIVE = {str(LIVE_DB)!r}\n"
        "_real = sqlite3.dbapi2.connect\n"
        "def _refuse(database, *a, **k):\n"
        "    try:\n"
        "        p = os.path.abspath(os.fspath(database))\n"
        "    except TypeError:\n"
        "        p = str(database)\n"
        "    if os.path.normcase(p) == os.path.normcase(os.path.abspath(LIVE)):\n"
        "        raise AssertionError('the live archive was opened: ' + p)\n"
        "    return _real(database, *a, **k)\n"
        # sqlite3.connect and sqlite3.dbapi2.connect are the same function under
        # two names; SQLAlchemy's pysqlite dialect calls it through the module
        # object, so both bindings have to be replaced.
        "sqlite3.dbapi2.connect = _refuse\n"
        "sqlite3.connect = _refuse\n"
        "import main  # noqa: F401 - import scope runs initialize_database()\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        "importing main from a test session opened the operator's live archive "
        f"(exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )


def test_the_override_is_what_redirects_the_path():
    """The default stays ``__file__``-anchored — the override is the only lever.

    Without this, a future change could satisfy the two guards above by moving
    the DEFAULT (e.g. to a cwd-relative name), which would silently relocate the
    operator's production archive instead of isolating the tests.
    """
    import database

    assert _same_file_path(database.DEFAULT_DB_PATH, str(LIVE_DB))
    assert os.environ.get("CHROLLO_DB_PATH"), (
        "conftest must set CHROLLO_DB_PATH for the whole session"
    )
