"""CSV Activity-Statement import guards (quality-doctrine WP-B, P0).

Pins the two ingest-time normalizations that keep CSV rows compatible with
live fills:

- statement times (naive US/Eastern) are stored as naive UTC, the same clock
  live fills use — mixed clocks skewed the FIFO round-trip walk by 4-5 hours;
- a CSV row covering a fill already ingested from the live feed is skipped
  (``matched_live``) instead of inserted twice — live execIds and synthetic
  ``csv:`` ids never collide, so the exec_id dedupe alone can't catch this.
"""
import sys
from datetime import datetime

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import database
import models
from domains.trading import csv_import

ACCOUNT = "U1234567"

_HEADER = (
    "Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,"
    "Quantity,T. Price,Comm/Fee,Realized P/L,Code"
)


def _statement(*trade_rows):
    lines = [f"Account Information,Data,Account,{ACCOUNT}", _HEADER]
    lines.extend(trade_rows)
    return "\n".join(lines) + "\n"


def _trade_row(symbol, date_time, qty, price, commission="-1.00", realized="0"):
    return (
        f'Trades,Data,Order,Stocks,USD,{symbol},"{date_time}",'
        f"{qty},{price},{commission},{realized},O"
    )


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine(f"sqlite:///{tmp_path / 'journal.db'}")
    database.Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng)
    monkeypatch.setattr(csv_import, "SessionLocal", Session)
    db = Session()
    yield db
    db.close()
    eng.dispose()


def _live_fill(db, exec_id, symbol, side, qty, price, time_utc):
    db.add(models.Execution(
        exec_id=exec_id,
        account=ACCOUNT,
        symbol=symbol,
        sec_type="STK",
        side=side,
        quantity=qty,
        price=price,
        commission=1.0,
        time=time_utc,
    ))
    db.commit()


def test_statement_times_are_stored_as_utc(db_session):
    # 2026-03-02 is EST (UTC-5); 2026-07-01 is EDT (UTC-4).
    csv_import.import_activity_statement(_statement(
        _trade_row("AAPL", "2026-03-02, 13:14:04", 100, 50.0),
        _trade_row("MSFT", "2026-07-01, 10:00:00", 10, 400.0),
    ))

    rows = {r.symbol: r for r in db_session.query(models.Execution).all()}
    assert rows["AAPL"].time == datetime(2026, 3, 2, 18, 14, 4)
    assert rows["MSFT"].time == datetime(2026, 7, 1, 14, 0, 0)


def test_live_fill_overlap_is_skipped_not_double_counted(db_session):
    # A fill already ingested live (real IBKR execId, naive-UTC time).
    _live_fill(db_session, "0001f4e8.686f2b48.01.01", "AAPL", "BUY",
               100.0, 50.0, datetime(2026, 3, 2, 18, 14, 3))

    summary = csv_import.import_activity_statement(_statement(
        _trade_row("AAPL", "2026-03-02, 13:14:04", 100, 50.0),
    ))

    assert summary["imported"] == 0
    assert summary["matched_live"] == 1
    assert "1 matched live fills" in summary["message"]
    # Still exactly one execution — no phantom second fill.
    assert db_session.query(models.Execution).count() == 1


def test_partial_fills_aggregate_to_the_statement_order_row(db_session):
    # One order, two live partial fills; the statement row carries the total
    # qty and the fill VWAP: (60*50.10 + 40*49.90) / 100 = 50.02.
    _live_fill(db_session, "0001f4e8.686f2b48.01.02", "AAPL", "BUY",
               60.0, 50.10, datetime(2026, 3, 2, 18, 14, 3))
    _live_fill(db_session, "0001f4e8.686f2b48.01.03", "AAPL", "BUY",
               40.0, 49.90, datetime(2026, 3, 2, 18, 14, 20))

    summary = csv_import.import_activity_statement(_statement(
        _trade_row("AAPL", "2026-03-02, 13:14:04", 100, 50.02),
    ))

    assert summary["imported"] == 0
    assert summary["matched_live"] == 1
    assert db_session.query(models.Execution).count() == 2


def test_distinct_order_outside_window_still_imports(db_session):
    # Same facts but hours apart — a genuine separate order, not a duplicate.
    _live_fill(db_session, "0001f4e8.686f2b48.01.04", "AAPL", "BUY",
               100.0, 50.0, datetime(2026, 3, 2, 15, 0, 0))

    summary = csv_import.import_activity_statement(_statement(
        _trade_row("AAPL", "2026-03-02, 13:14:04", 100, 50.0),
    ))

    assert summary["imported"] == 1
    assert summary["matched_live"] == 0
    assert db_session.query(models.Execution).count() == 2


def test_reupload_is_idempotent_and_heals_legacy_eastern_times(db_session):
    statement = _statement(_trade_row("AAPL", "2026-03-02, 13:14:04", 100, 50.0))

    first = csv_import.import_activity_statement(statement)
    assert first["imported"] == 1

    # The synthetic id hashes the statement-local (Eastern) time — the exact
    # signature pre-normalization imports used — so legacy rows keep deduping.
    row = db_session.query(models.Execution).one()
    assert row.exec_id == csv_import._synthesize_exec_id(
        ACCOUNT, "AAPL", "2026-03-02T13:14:04", "BUY", 100.0, 50.0,
    )

    # Simulate a legacy pre-normalization row: stored time still naive Eastern.
    row.time = datetime(2026, 3, 2, 13, 14, 4)
    db_session.commit()

    second = csv_import.import_activity_statement(statement)
    assert second["imported"] == 0
    assert second["skipped"] == 1

    db_session.expire_all()
    healed = db_session.query(models.Execution).one()
    assert healed.time == datetime(2026, 3, 2, 18, 14, 4)  # back to UTC
