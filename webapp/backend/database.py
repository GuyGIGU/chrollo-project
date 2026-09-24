import os
import sys

# The repo root, so ``core`` is importable however this module was reached.
# main.py does the same three lines before its own first import; this module is
# also imported directly (by tests, and by tools that add only the backend dir),
# so it cannot assume someone else ran that bootstrap first.
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT_DIR not in sys.path:
    sys.path.append(_ROOT_DIR)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from core.archive.db_path import DEFAULT_DB_PATH, archive_db_path

# The path and the CHROLLO_DB_PATH override both live in core/archive/db_path.py
# — ONE home for ten front doors (register row 18, EC-3). ``DEFAULT_DB_PATH`` is
# re-exported here because that is the name the isolation guards and the rest of
# the backend already import.
#
# Why the override exists: `import main` runs the whole migration battery at
# import scope (main.py's initialize_database()), and three test modules import
# main in a subprocess with cwd=webapp/backend. Without an override a plain
# `pytest` run migrates the operator's live archive and — through
# _reconcile_orphaned_runs — stamps an in-flight scan 'failed'. tests/conftest.py
# sets it to a throwaway file for the whole session (guarded by
# tests/integration/test_db_isolation.py). Nothing in the service sets it, so production
# keeps the anchored path.
_DB_PATH = archive_db_path()
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"


def make_sqlite_engine(db_path: str):
    """Build a SQLAlchemy engine for a SQLite file configured for safe
    concurrent access from multiple processes (the webapp backend + the
    screener pipeline both write to the same DB).

    - ``timeout=30`` (sqlite3 connect arg) sets a 30s busy wait on the
      Python side before raising OperationalError.
    - ``PRAGMA journal_mode=WAL`` enables Write-Ahead Logging so readers
      do not block writers and vice-versa. This setting is sticky on the
      database file once applied.
    - ``PRAGMA busy_timeout=30000`` is the SQLite-level equivalent and
      applies to every statement on the connection (the connect-arg
      timeout only covers the initial connect).
    - ``PRAGMA synchronous=NORMAL`` is the recommended pairing with WAL —
      durable across crashes, faster than FULL, no observed corruption.
    """
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(eng, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        # busy_timeout MUST come first: with it set, every subsequent
        # statement on this connection waits up to 30s for contention to
        # clear instead of failing immediately with "database is locked".
        # This alone resolves the autoflush-during-query failure that hit
        # archive_writer.py when uvicorn held a short read lock.
        cur.execute("PRAGMA busy_timeout=30000")
        # journal_mode=WAL is best-effort: switching journals needs an
        # exclusive lock that may not be obtainable while another process
        # has the DB open (uvicorn, dashboard, etc). If the upgrade fails
        # we keep going on rollback-journal mode — busy_timeout alone is
        # enough to prevent the original error. The next clean restart
        # will switch the file to WAL persistently.
        try:
            cur.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return eng


engine = make_sqlite_engine(_DB_PATH)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_trade_or_404(db, trade_id: int):
    """Fetch a ``TradeLog`` by id or raise 404. Shared by the trade and journal
    routers, which both gate their per-trade operations on this lookup.

    ``models``/``fastapi`` are imported lazily so this DB-layer module stays free
    of an import cycle with ``models`` (which imports ``Base`` from here).
    """
    from fastapi import HTTPException

    import models

    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade
