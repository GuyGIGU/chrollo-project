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
live database becomes reachable from a test session again, and both are safe to
FAIL — neither opens the archive on its way to the assertion.

Scope. The first three guards are PATH-specific: they pin
``webapp/backend/database.py`` and the ``CHROLLO_DB_PATH`` override. That was
once the whole defence, and it left the archive with ten front doors and one
lock — nine other modules rebuilt the live path from their own ``__file__``
anchor and ignored the override (register row 11). Both halves have since
landed and are pinned below:

* the EC-3 fold — every door resolves through ``core.archive.db_path``, asserted
  on BEHAVIOUR (each module's bound path IS the session override) rather than on
  a grep for the literal, which would pass the day someone respells it;
* the STRUCTURAL guard — ``tests/live_archive_guard`` refuses the live path at
  the sqlite driver, under all ten doors at once and any new one. It is proven
  against a DECOY path, never the real one: a proof that handed sqlite the live
  path would open the archive on exactly the runs where the guard is broken.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _paths import REPO_ROOT as ROOT
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

    The engine's own URL is checked FIRST, without connecting: ``database.py``'s
    connect listener runs ``PRAGMA journal_mode=WAL`` (a header write) on every
    new connection, so connecting under a broken override would modify the
    archive before this assertion could fire. Reading ``engine.url`` costs no
    connection, so this guard — like the one below — is safe to fail.
    """
    import database

    bound = database.engine.url.database
    assert bound, "the engine has no file in its URL - cannot prove isolation"
    assert not _same_file_path(bound, str(LIVE_DB)), (
        f"the test session's engine is bound to the LIVE archive ({bound}); "
        "tests/conftest.py must point CHROLLO_DB_PATH at a throwaway file"
    )

    with database.engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA database_list").fetchall()
    opened = [r[2] for r in rows if r[1] == "main" and r[2]]
    assert opened, "the engine attached no file - cannot prove isolation"
    assert not _same_file_path(opened[0], str(LIVE_DB)), (
        f"the engine's URL says {bound} but SQLite attached the LIVE archive "
        f"({opened[0]})"
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


# ─────────────────────────────────────────────────────────────────────────────
# The STRUCTURAL guard (register row 11). The three tests above are
# PATH-specific: they pin webapp/backend/database.py, the one door that reads
# CHROLLO_DB_PATH. These pin the refuser that sits under ALL of them.
# ─────────────────────────────────────────────────────────────────────────────
def test_every_archive_door_now_resolves_through_the_one_home():
    """The EC-3 fold: ten modules used to rebuild the live path from their own
    ``__file__`` anchor and ignore the override. Now they ask one function.

    Asserted on BEHAVIOUR, not on the source text — a grep for the literal would
    pass the day somebody rebuilds the path by another spelling.
    """
    import importlib

    from core.archive import db_path

    doors = [
        ("core.archive.analyze", "_DB_PATH"),
        ("core.archive.seed_recall", "_DB_PATH"),
        ("core.backtest.loader", "DEFAULT_DB_PATH"),
        ("database", "_DB_PATH"),
    ]
    override = os.environ["CHROLLO_DB_PATH"]
    for mod_name, attr in doors:
        mod = importlib.import_module(mod_name)
        bound = getattr(mod, attr)
        assert _same_file_path(bound, override), (
            f"{mod_name}.{attr} resolved to {bound!r}, not the session override "
            f"{override!r} — it is rebuilding the path instead of asking "
            "core.archive.db_path.archive_db_path()"
        )
        assert not _same_file_path(bound, str(LIVE_DB))
    # And the shared home agrees about where production lives.
    assert _same_file_path(db_path.DEFAULT_DB_PATH, str(LIVE_DB))


def test_the_five_writer_side_doors_ask_the_shared_home_at_call_time():
    """``writer``/``purge``/``seed``/``forward_returns``/``near_miss_outcomes``
    resolve inside their functions, so the override must be read at CALL time —
    a constant captured at import would miss a variable set afterwards."""
    import core.archive.db_path as db_path

    before = db_path.archive_db_path()
    os.environ["CHROLLO_DB_PATH"] = os.path.join(str(tmp_dir := Path(before).parent),
                                                 "moved.db")
    try:
        assert db_path.archive_db_path().endswith("moved.db"), (
            "archive_db_path() captured the environment at import time"
        )
    finally:
        os.environ["CHROLLO_DB_PATH"] = before
    assert db_path.archive_db_path() == before
    assert tmp_dir  # the throwaway dir, not the backend's


def test_the_refuser_blocks_a_forbidden_path_without_naming_the_live_one(tmp_path):
    """Prove the mechanism against a DECOY.

    A proof that handed sqlite the real archive path would OPEN the archive on
    exactly the runs where the guard is broken — the failure it exists to
    prevent (council review 2026-09-07, finding B). So the guard is keyed on a
    module attribute, and this swaps in a decoy instead.
    """
    import sqlite3

    import live_archive_guard as guard

    decoy = str(tmp_path / "decoy.db")
    real_forbidden = guard._forbidden_path
    guard._forbidden_path = decoy
    try:
        with pytest.raises(AssertionError, match="LIVE archive"):
            sqlite3.connect(decoy)
        # The read-only URI form names the same file and must also be refused.
        with pytest.raises(AssertionError, match="LIVE archive"):
            sqlite3.connect(f"file:{decoy}?mode=ro", uri=True)
        # Anything else still connects normally — the guard is a scalpel.
        other = str(tmp_path / "fine.db")
        sqlite3.connect(other).close()
        assert os.path.exists(other)
        # It never created the decoy: refusal happens BEFORE the real connect.
        assert not os.path.exists(decoy)
    finally:
        guard._forbidden_path = real_forbidden
    assert guard._forbidden_path == real_forbidden


def test_the_refuser_is_installed_and_keyed_on_the_live_archive():
    """The decoy test proves the mechanism; this proves it is actually armed,
    on the right path, for the whole session."""
    import sqlite3

    import live_archive_guard as guard

    assert guard._installed, "conftest never installed the live-archive refuser"
    assert _same_file_path(guard._forbidden_path, str(LIVE_DB))
    # Both names must be rebound — they are the same function object, and a
    # caller reaching sqlite3.dbapi2.connect would otherwise walk straight past.
    assert sqlite3.connect is guard._guarded_connect
    assert sqlite3.dbapi2.connect is guard._guarded_connect
