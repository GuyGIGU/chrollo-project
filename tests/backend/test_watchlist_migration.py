"""Finviz plan Task 5 — the watchlist event-ledger rebuild is idempotent and
lossless, and the rebuilt schema's constraints actually assert.

The old grain (ticker PRIMARY KEY, created_at) rebuilds into the dated event
ledger: surrogate id, UNIQUE(ticker, save_date), a partial unique index holding
the ACTIVE set to one row per ticker, the full-pin CHECK (all four pin columns
or none) and the snapshot CHECK (valid JSON, <=256KB). Legacy rows must survive
as ACTIVE watches — save_date from created_at's date part, the NULL-created_at
row landing on the migration day — origin 'legacy', pins/snapshot NULL (never
fabricated). Hermetic: throwaway sqlite files, never the live DB."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from database import make_sqlite_engine  # noqa: E402
from app.startup import migrate_watchlist_ledger, migrate_watchlist_weeks  # noqa: E402


def _create_legacy_watchlist(db: str) -> None:
    """The pre-ledger shape exactly as the live DB carried it (ticker PK +
    created_at + the named ticker index whose name the rebuild must vacate)."""
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE watchlist (ticker VARCHAR NOT NULL, created_at DATETIME, "
        "PRIMARY KEY (ticker))"
    )
    con.execute("CREATE INDEX ix_watchlist_ticker ON watchlist (ticker)")
    con.executemany(
        "INSERT INTO watchlist (ticker, created_at) VALUES (?, ?)",
        [
            ("MPLX", "2026-06-29 11:34:20.018928"),
            ("CVLG", "2026-07-01 23:29:15.837310"),
            ("GHST", None),  # the NULL-created_at legacy row the plan names
        ],
    )
    con.commit()
    con.close()


def test_migration_is_noop_on_current_schema(tmp_path):
    db = str(tmp_path / "current.db")
    eng = make_sqlite_engine(db)
    models.Watchlist.__table__.create(bind=eng)
    assert migrate_watchlist_ledger(eng) is False
    eng.dispose()


def test_migration_is_noop_on_missing_table(tmp_path):
    db = str(tmp_path / "empty.db")
    eng = make_sqlite_engine(db)
    assert migrate_watchlist_ledger(eng) is False
    eng.dispose()


def test_migration_rebuilds_legacy_rows_as_active_history(tmp_path):
    db = str(tmp_path / "legacy.db")
    _create_legacy_watchlist(db)

    assert migrate_watchlist_ledger(make_sqlite_engine(db)) is True   # rebuilt
    assert migrate_watchlist_ledger(make_sqlite_engine(db)) is False  # idempotent

    con = sqlite3.connect(db)
    try:
        rows = {
            r[0]: r for r in con.execute(
                "SELECT ticker, save_date, saved_at, unstarred_at, origin, "
                "pin_scan_date, pin_universe_type, pin_setup_type, "
                "pin_engine_config_version, snapshot_json FROM watchlist"
            ).fetchall()
        }
        assert len(rows) == 3  # row count exact

        # Dated from created_at's date part; saved_at copied verbatim.
        assert rows["MPLX"][1] == "2026-06-29"
        assert rows["MPLX"][2] == "2026-06-29 11:34:20.018928"
        assert rows["CVLG"][1] == "2026-07-01"
        # NULL created_at lands on the migration day with a real audit stamp.
        assert rows["GHST"][1] == datetime.now(timezone.utc).date().isoformat()
        assert rows["GHST"][2] is not None

        for row in rows.values():
            assert row[3] is None       # unstarred_at NULL -> survives ACTIVE
            assert row[4] == "legacy"   # origin
            assert row[5:] == (None, None, None, None, None)  # never fabricate

        # The ledger identity: UNIQUE(ticker, save_date) + the partial unique
        # index holding the active set to one row per ticker per week.
        # index_list rows: (seq, name, unique, origin, partial)
        indexes = con.execute("PRAGMA index_list(watchlist)").fetchall()
        unique_col_sets = []
        for idx in indexes:
            if idx[2]:
                cols = {r[2] for r in con.execute(f"PRAGMA index_info('{idx[1]}')")}
                unique_col_sets.append(cols)
        assert {"ticker", "save_date"} in unique_col_sets
        assert {"ticker", "week_start"} in unique_col_sets
        assert any(
            idx[1] == "ux_watchlist_active_ticker_week" and idx[2] == 1 and idx[4] == 1
            for idx in indexes
        )
    finally:
        con.close()


# --- The rebuilt schema's constraints are live assertions, not decoration ----


@pytest.fixture()
def ledger_db(tmp_path):
    """A fresh event-ledger watchlist built from the current model."""
    db = str(tmp_path / "ledger.db")
    eng = make_sqlite_engine(db)
    models.Watchlist.__table__.create(bind=eng)
    eng.dispose()
    con = sqlite3.connect(db)
    yield con
    con.close()


def _insert(con, **overrides):
    row = {
        "ticker": "TEST",
        "save_date": "2026-08-11",
        "saved_at": "2026-08-11 21:00:00.000000",
        "unstarred_at": None,
        "origin": "user",
        "pin_scan_date": None,
        "pin_universe_type": None,
        "pin_setup_type": None,
        "pin_engine_config_version": None,
        "snapshot_json": None,
    }
    row.update(overrides)
    cols = ", ".join(row)
    params = ", ".join(f":{k}" for k in row)
    con.execute(f"INSERT INTO watchlist ({cols}) VALUES ({params})", row)


def test_at_most_one_active_row_per_ticker_per_week(ledger_db):
    _insert(ledger_db, save_date="2026-08-10", week_start="2026-08-10")
    with pytest.raises(sqlite3.IntegrityError):
        _insert(ledger_db, save_date="2026-08-11", week_start="2026-08-10")  # second ACTIVE row
    # Next week's list holds the same name while last week's keeps it.
    _insert(ledger_db, save_date="2026-08-15", week_start="2026-08-17")
    # Un-starred history does not block a new active save.
    ledger_db.execute("UPDATE watchlist SET unstarred_at = '2026-08-11 09:00:00.000000' "
                      "WHERE save_date = '2026-08-10'")
    _insert(ledger_db, save_date="2026-08-11", week_start="2026-08-10")


def test_side_and_ready_vocabularies_are_enforced(ledger_db):
    with pytest.raises(sqlite3.IntegrityError):
        _insert(ledger_db, side="X")
    with pytest.raises(sqlite3.IntegrityError):
        _insert(ledger_db, ready=3)
    _insert(ledger_db, side="S", ready=2)


# --- The weekly list: an existing ledger gains its weeks ----------------------

# The ledger as the live DB carries it before the weekly list (Fri 23/10/2026).
_PRE_WEEKS_LEDGER = (
    "CREATE TABLE watchlist (id INTEGER PRIMARY KEY, ticker VARCHAR NOT NULL, "
    "save_date VARCHAR NOT NULL, saved_at DATETIME NOT NULL, unstarred_at DATETIME, "
    "origin VARCHAR NOT NULL, pin_scan_date VARCHAR, pin_universe_type VARCHAR, "
    "pin_setup_type VARCHAR, pin_engine_config_version VARCHAR, snapshot_json TEXT, "
    "CONSTRAINT uq_watchlist_save_event UNIQUE (ticker, save_date))",
    "CREATE UNIQUE INDEX ux_watchlist_active_ticker ON watchlist (ticker) "
    "WHERE unstarred_at IS NULL",
)


def test_weeks_migration_gives_every_save_its_week_once(tmp_path):
    db = str(tmp_path / "weeks.db")
    con = sqlite3.connect(db)
    for statement in _PRE_WEEKS_LEDGER:
        con.execute(statement)
    pin = ("us_equities", "LPS", "abc")
    con.executemany(
        "INSERT INTO watchlist (ticker, save_date, saved_at, origin, pin_scan_date, "
        "pin_universe_type, pin_setup_type, pin_engine_config_version) "
        "VALUES (?, ?, '2026-10-20 21:00:00', 'user', ?, ?, ?, ?)",
        [("TUE", "2026-10-20", "2026-10-20", *pin),     # Tuesday's scan: this week
         ("FRI", "2026-10-24", "2026-10-23", *pin),     # Friday's scan: next week
         ("OLD", "2026-10-25", None, None, None, None)])  # unpinned Sunday save: next week
    con.commit()
    con.close()

    assert migrate_watchlist_weeks(make_sqlite_engine(db)) == 3
    assert migrate_watchlist_weeks(make_sqlite_engine(db)) == 0  # idempotent

    con = sqlite3.connect(db)
    try:
        rows = {r[0]: r[1:] for r in con.execute(
            "SELECT ticker, week_start, basis_scan_date, side, ready, ready_at FROM watchlist")}
        assert rows == {"TUE": ("2026-10-19", "2026-10-20", "L", 0, None),
                        "FRI": ("2026-10-26", "2026-10-23", "L", 0, None),
                        "OLD": ("2026-10-26", None, "L", 0, None)}
        names = {idx[1] for idx in con.execute("PRAGMA index_list(watchlist)")}
        assert "ux_watchlist_active_ticker" not in names
        assert "ux_watchlist_active_ticker_week" in names
        # The same name may now be active in two weeks, never twice in one.
        con.execute("INSERT INTO watchlist (ticker, save_date, saved_at, origin, week_start) "
                    "VALUES ('TUE', '2026-10-24', '2026-10-24 10:00:00', 'user', '2026-10-26')")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO watchlist (ticker, save_date, saved_at, origin, week_start) "
                        "VALUES ('TUE', '2026-10-25', '2026-10-25 10:00:00', 'user', '2026-10-26')")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE watchlist SET side = 'X' WHERE ticker = 'FRI'")
    finally:
        con.close()


def test_half_pin_cannot_exist(ledger_db):
    with pytest.raises(sqlite3.IntegrityError):
        _insert(ledger_db, pin_scan_date="2026-08-11")  # 1 of 4 pin columns
    _insert(
        ledger_db,
        pin_scan_date="2026-08-11",
        pin_universe_type="us_equities",
        pin_setup_type="LPS",
        pin_engine_config_version="abc123",
    )  # the full quadruple is legal


def test_snapshot_must_be_valid_bounded_json(ledger_db):
    with pytest.raises(sqlite3.IntegrityError):
        _insert(ledger_db, snapshot_json="not json{")
    with pytest.raises(sqlite3.IntegrityError):
        _insert(ledger_db, snapshot_json='{"pad": "' + "x" * 262145 + '"}')
    _insert(ledger_db, snapshot_json='{"snapshot_version": 1}')


def test_origin_vocabulary_is_enforced(ledger_db):
    """EC-19: the closed origin set is a CHECK, not a comment."""
    with pytest.raises(sqlite3.IntegrityError):
        _insert(ledger_db, origin="imported")
    _insert(ledger_db, origin="legacy")
    _insert(ledger_db, ticker="OTHR", origin="user")
