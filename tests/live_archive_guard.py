"""Refuse, at the sqlite driver, any attempt to open the operator's live archive.

``tests/conftest.py`` points ``CHROLLO_DB_PATH`` at a throwaway file, but that is
a PATH-specific defence: it only protects the sites that read the override. This
is the STRUCTURAL one — it sits under every one of them at once, so a module that
rebuilds the live path from its own anchor is refused rather than silently
served (register row 11).

**It refuses, it does not redirect.** A test that reaches the live archive is a
defect to be surfaced, not papered over; a silent redirect would let the caller
keep the bug and pass.

Keyed on ``_forbidden_path``, a module attribute rather than a constant baked
into the closure, so ``tests/integration/test_db_isolation.py`` can prove the mechanism
against a DECOY path. That matters: a proof that handed sqlite the real archive
path would open the archive on every run where the guard was broken — which is
precisely the failure it exists to prevent (council review 2026-09-07, finding B).
"""
from __future__ import annotations

import os
import sqlite3
import sqlite3.dbapi2

#: The single path the guard refuses. ``None`` disables it entirely.
_forbidden_path: str | None = None

_real_connect = sqlite3.dbapi2.connect
_installed = False


def _same_path(a, b: str) -> bool:
    """True when ``a`` names the same file as ``b``. Never raises: a caller may
    pass a URI, an int fd, or a Path, and a guard that explodes on an exotic
    argument would break connections it was never meant to judge."""
    try:
        candidate = os.fspath(a)
    except TypeError:
        return False
    if not isinstance(candidate, str) or not candidate:
        return False
    # A `file:...?mode=ro` URI names the same file; strip the scheme and query
    # so read-only access to the live archive is refused too.
    if candidate.startswith("file:"):
        candidate = candidate[len("file:"):].split("?", 1)[0]
    try:
        return os.path.normcase(os.path.abspath(candidate)) == os.path.normcase(
            os.path.abspath(b))
    except (ValueError, OSError):
        return False


def _guarded_connect(database=None, *args, **kwargs):
    target = database if database is not None else kwargs.get("database")
    forbidden = _forbidden_path
    if forbidden and _same_path(target, forbidden):
        raise AssertionError(
            f"a test opened the LIVE archive at {target!r}. Nothing in the suite "
            "may touch the operator's database. Route this call through "
            "core.archive.db_path.archive_db_path(), which honours "
            "CHROLLO_DB_PATH (tests/conftest.py points it at a throwaway file)."
        )
    if database is None:
        return _real_connect(*args, **kwargs)
    return _real_connect(database, *args, **kwargs)


def install(forbidden_path: str) -> None:
    """Patch the sqlite driver for the whole session. Idempotent."""
    global _forbidden_path, _installed
    _forbidden_path = forbidden_path
    if _installed:
        return
    # sqlite3.connect IS sqlite3.dbapi2.connect — both names must be rebound or
    # a caller reaching the module by the other name walks straight past.
    sqlite3.dbapi2.connect = _guarded_connect
    sqlite3.connect = _guarded_connect
    _installed = True
