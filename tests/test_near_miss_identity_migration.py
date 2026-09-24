"""The near-miss episode identity is the ANCHOR DATES, not the rail prices
(council review 2026-09-07 finding 5).

``uq_near_miss_framing_identity`` used to carry both rails as FLOATs rounded to
4dp — a quantum a thousand times finer than the float32 panel they are read from,
and a value that MOVES under a corporate action. Measured on the live archive on
2026-09-07: 4 duplicate groups, all APH, one of them the float-noise pair (77.68
vs 77.6801) and every one of them an exact 2x rail pair from APH's split — one
drawn structure re-minted as a fresh episode with ``first_seen`` and the whole
forward clock reset. Zero legitimately distinct framings shared a pair of anchor
dates in 1,483 rows, which is what the enumeration guarantees: the rail and its
anchor bar come out of ``box_primitives._oriented_pairs`` as one zigzag pivot, so
the anchors determine the rails within a panel and survive a re-scaling of it.

These pin the new key, the rebuild that installs it, and the writer that upserts
against it. The legacy schema is generated from the model's own DDL with the old
6-column UNIQUE substituted back in AND the four explicit indexes replayed, so
the fixture cannot drift from the real pre-migration shape — verified column for
column and index for index against the operator's archive (read-only) on
2026-09-07. The indexes are load-bearing: without them the rebuild's
rename-collision path is unexercised, and that path is the difference between a
boot and no boot (council review 2026-09-07, fix review F1).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex, CreateTable

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
from database import make_sqlite_engine  # noqa: E402
from app.startup import migrate_near_miss_framing_identity  # noqa: E402

_NEW_UNIQUE = ('CONSTRAINT uq_near_miss_framing_identity UNIQUE (ticker, '
               'universe_type, r_anchor_date, s_anchor_date)')
_OLD_UNIQUE = ('CONSTRAINT uq_near_miss_framing_identity UNIQUE (ticker, '
               'universe_type, r_level, s_level, r_anchor_date, s_anchor_date)')


def _legacy_ddl() -> str:
    """The model's CREATE TABLE with the PRE-migration 6-column UNIQUE."""
    ddl = str(CreateTable(archive_models.NearMissArchive.__table__)
              .compile(dialect=sqlite_dialect.dialect()))
    flat = " ".join(ddl.split())
    assert _NEW_UNIQUE in flat, (
        "the model no longer declares the date-anchored identity — the rail "
        "prices must never go back into uq_near_miss_framing_identity"
    )
    return flat.replace(_NEW_UNIQUE, _OLD_UNIQUE)


# The four explicit indexes the LIVE table carries, read off the operator's
# archive read-only on 2026-09-07. SQLAlchemy emits ``Index`` objects as
# SEPARATE ``CREATE INDEX`` statements, so a fixture built from ``CreateTable``
# alone has NO indexes — and the migration's rename-collision path (SQLite keeps
# an index's NAME when its table is renamed, so all four follow the old table and
# then collide with the new one's) goes entirely unexercised. Pinned by name so a
# future edit cannot quietly hollow the fixture back out.
_LIVE_INDEXES = {"ix_near_miss_archive_first_seen", "ix_near_miss_archive_id",
                 "ix_near_miss_archive_ticker", "ix_near_miss_identity"}


def _legacy_index_ddl() -> list[str]:
    """The CREATE INDEX statements the live pre-migration table carries."""
    indexes = archive_models.NearMissArchive.__table__.indexes
    assert {ix.name for ix in indexes} == _LIVE_INDEXES, (
        "the fixture no longer builds the live table's index set — the "
        "migration's rename-collision path would go unexercised"
    )
    return [str(CreateIndex(ix).compile(dialect=sqlite_dialect.dialect()))
            for ix in indexes]


def _explicit_indexes(con) -> set:
    """Index names on ``near_miss_archive`` (autoindexes have NULL sql)."""
    return {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='near_miss_archive' AND sql IS NOT NULL").fetchall()}


_REQUIRED = {
    "fired_first_night": 0, "pool": "strict", "kill_stage": "occupancy",
    "failing_leg": "occupancy", "lane_ruleset": "2026-07-26.A",
    "engine_config_version": "abc123", "judged_n": 28,
    "window_start_date": "2026-08-03", "window_end_date": "2026-08-28",
    "nm_width": 0.17, "nm_respect_share": 1, "nm_respect_run": 9,
    "nm_crash": 0.25, "nm_r_touches": 2, "nm_s_touches": 1,
    "nm_r_touch_thirds": 0, "nm_s_touch_thirds": 0, "nm_lower_dwell": -1,
    "nm_upper_dwell": 3, "nm_mid_dwell": 4, "nm_coverage": 1,
    "nm_traversal_count": 0, "nm_traversal_density": 0.02,
    "would_be_trigger": 100.0, "scan_close": 99.0,
}


def _row(**over) -> dict:
    row = dict(_REQUIRED)
    row.update(universe_type="us_equities", nights_seen=1, fired_any_night=0)
    row.update(over)
    return row


def _legacy_db(path: str, rows: list[dict], ddl: str | None = None) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute(ddl or _legacy_ddl())
        for stmt in _legacy_index_ddl():
            con.execute(stmt)
        for row in rows:
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            con.execute(f"INSERT INTO near_miss_archive ({cols}) VALUES ({marks})",
                        tuple(row.values()))
        con.commit()
    finally:
        con.close()


# ── idempotence ───────────────────────────────────────────────────────────────
def test_migration_is_noop_on_missing_table(tmp_path):
    eng = make_sqlite_engine(str(tmp_path / "empty.db"))
    assert migrate_near_miss_framing_identity(eng) is False
    eng.dispose()


def test_migration_is_noop_on_a_fresh_model_db(tmp_path):
    eng = make_sqlite_engine(str(tmp_path / "fresh.db"))
    archive_models.NearMissArchive.__table__.create(bind=eng)
    assert migrate_near_miss_framing_identity(eng) is False
    eng.dispose()


# ── the rebuild ───────────────────────────────────────────────────────────────
def test_migration_folds_the_live_aph_duplicates_into_one_episode_each(tmp_path):
    """The live 2026-09-07 state, replicated: APH's split re-minted its framings,
    one of them twice over on 4dp float noise. Each group must collapse onto its
    EARLIEST-first_seen row — the first-refusal record, whose rails, would-be
    trigger and scan close are all on one price scale — with only the three
    recurrence counters folded across the group."""
    db = str(tmp_path / "legacy.db")
    _legacy_db(db, [
        # APH group A — three rows, one framing. Pre-split, then the split's
        # re-mint, then the same rails again off a 4dp float wobble.
        _row(id=1, ticker="APH", r_level=176.33, s_level=155.36,
             r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
             first_seen="2026-08-27", last_seen="2026-08-28", nights_seen=2),
        _row(id=2, ticker="APH", r_level=88.165, s_level=77.6801,
             r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
             first_seen="2026-09-02", last_seen="2026-09-03", nights_seen=2,
             fired_any_night=1),
        _row(id=3, ticker="APH", r_level=88.165, s_level=77.68,
             r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
             first_seen="2026-09-04", last_seen="2026-09-04", nights_seen=1),
        # APH group B — the plain 2x split pair.
        _row(id=4, ticker="APH", r_level=178.52, s_level=153.15,
             r_anchor_date="2026-06-30", s_anchor_date="2026-07-08",
             first_seen="2026-08-12", last_seen="2026-08-12", nights_seen=1),
        _row(id=5, ticker="APH", r_level=89.26, s_level=76.575,
             r_anchor_date="2026-06-30", s_anchor_date="2026-07-08",
             first_seen="2026-09-02", last_seen="2026-09-02", nights_seen=1),
        # A genuinely distinct framing — must survive untouched.
        _row(id=6, ticker="MSFT", r_level=420.0, s_level=390.0,
             r_anchor_date="2026-07-01", s_anchor_date="2026-07-14",
             first_seen="2026-08-01", last_seen="2026-08-20", nights_seen=7,
             fired_any_night=1),
        # A tie on first_seen — the lowest id wins, so the fold is deterministic.
        _row(id=20, ticker="TIE", r_level=10.0, s_level=9.0,
             r_anchor_date="2026-07-02", s_anchor_date="2026-07-09",
             first_seen="2026-08-05", last_seen="2026-08-05"),
        _row(id=21, ticker="TIE", r_level=20.0, s_level=18.0,
             r_anchor_date="2026-07-02", s_anchor_date="2026-07-09",
             first_seen="2026-08-05", last_seen="2026-08-06"),
    ])

    assert migrate_near_miss_framing_identity(make_sqlite_engine(db)) is True
    assert migrate_near_miss_framing_identity(make_sqlite_engine(db)) is False
    assert Path(db + ".prenearmissidentity.bak").exists()

    con = sqlite3.connect(db)
    try:
        assert con.execute("SELECT COUNT(*) FROM near_miss_archive").fetchone()[0] == 4

        # The date-anchored identity is the live UNIQUE key now.
        uniques = []
        for idx in con.execute("PRAGMA index_list(near_miss_archive)").fetchall():
            if idx[2]:
                uniques.append({r[2] for r in con.execute(
                    f"PRAGMA index_info('{idx[1]}')").fetchall()})
        assert {"ticker", "universe_type", "r_anchor_date", "s_anchor_date"} in uniques

        a = con.execute(
            "SELECT id, r_level, s_level, first_seen, last_seen, nights_seen, "
            "fired_any_night, fired_first_night FROM near_miss_archive "
            "WHERE ticker='APH' AND r_anchor_date='2026-08-06'").fetchone()
        # The earliest-first_seen row survives WHOLE — its own rails, its own
        # first refusal, its own forward clock.
        assert a[0] == 1
        assert (a[1], a[2]) == (176.33, 155.36)
        assert a[3] == "2026-08-27"
        # …and only the three recurrence counters are folded across the group.
        assert a[4] == "2026-09-04"      # max last_seen
        assert a[5] == 5                 # 2 + 2 + 1 nights of the SAME framing
        assert a[6] == 1                 # any night fired

        b = con.execute(
            "SELECT id, first_seen, nights_seen FROM near_miss_archive "
            "WHERE ticker='APH' AND r_anchor_date='2026-06-30'").fetchone()
        assert (b[0], b[1], b[2]) == (4, "2026-08-12", 2)

        # The distinct framing is byte-for-byte what it was.
        m = con.execute(
            "SELECT id, r_level, first_seen, last_seen, nights_seen "
            "FROM near_miss_archive WHERE ticker='MSFT'").fetchone()
        assert m == (6, 420.0, "2026-08-01", "2026-08-20", 7)

        # The tie broke on the lowest id.
        t = con.execute("SELECT id, r_level, last_seen, nights_seen "
                        "FROM near_miss_archive WHERE ticker='TIE'").fetchone()
        assert t == (20, 10.0, "2026-08-06", 2)
    finally:
        con.close()


def test_the_rebuild_drops_the_renamed_tables_indexes_before_replaying_them(tmp_path):
    """The single most dangerous line in this migration, on the real shape.

    SQLite keeps an index's NAME when its table is renamed, so the live table's
    four explicit indexes follow it to ``near_miss_archive_old`` and the new
    table's own ``CREATE INDEX`` then hits 'index ... already exists'. Because
    the failure re-raises out of ``migrate_near_miss_framing_identity`` ->
    ``initialize_database()`` -> ``main.py`` import scope, a regression here is
    not a bad row — it is a backend that does not boot at all, on a 44 MB
    archive. So the DROP loop is proven, and the indexes are proven back."""
    db = str(tmp_path / "indexed.db")
    _legacy_db(db, [
        _row(id=1, ticker="APH", r_level=176.33, s_level=155.36,
             r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
             first_seen="2026-08-27", last_seen="2026-08-28", nights_seen=2),
        _row(id=2, ticker="APH", r_level=88.165, s_level=77.68,
             r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
             first_seen="2026-09-04", last_seen="2026-09-04", nights_seen=1),
    ])

    con = sqlite3.connect(db)
    try:  # the fixture really is the live shape, not a bare CreateTable
        assert _explicit_indexes(con) == _LIVE_INDEXES
    finally:
        con.close()

    assert migrate_near_miss_framing_identity(make_sqlite_engine(db)) is True

    con = sqlite3.connect(db)
    try:
        # Every index is back, on the REBUILT table, and the old one is gone —
        # the drop was a rename artifact, never a loss of the live table's plan.
        assert _explicit_indexes(con) == _LIVE_INDEXES
        assert {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'").fetchall()} == {"near_miss_archive"}
        assert con.execute(
            "SELECT COUNT(*) FROM near_miss_archive").fetchone()[0] == 1
    finally:
        con.close()


def test_migration_fails_closed_on_a_missing_not_null_model_column(tmp_path):
    """A rebuild into a NOT NULL column the source cannot fill must refuse, not
    half-write the operator's archive."""
    db = str(tmp_path / "shortcolumns.db")
    _legacy_db(db, [], ddl=_legacy_ddl().replace("scan_close FLOAT NOT NULL, ", ""))

    with pytest.raises(RuntimeError, match="missing model column"):
        migrate_near_miss_framing_identity(make_sqlite_engine(db))
    # Nothing was touched: the original table is still there, still legacy.
    con = sqlite3.connect(db)
    try:
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert names == {"near_miss_archive"}
    finally:
        con.close()


def test_migration_rebuilds_a_table_missing_a_NULLABLE_model_column(tmp_path):
    """The other half of failing closed: refusing must be reserved for what the
    rebuild genuinely cannot fill.

    Every column this table has gained since birth is nullable outcome
    substrate, and the ADD-only pass that would supply one runs AFTER this
    migration — so a blanket 'any model/DB column gap refuses' turns the next
    such release into a dead backend for anyone booting a DB restored from an
    older backup, which this file's own comments say happens. A missing NULLABLE
    column is copied as NULL, which is exactly what the model permits."""
    db = str(tmp_path / "nullablegap.db")
    _legacy_db(db, [
        _row(id=1, ticker="APH", r_level=176.33, s_level=155.36,
             r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
             first_seen="2026-08-27", last_seen="2026-08-28", nights_seen=2),
        _row(id=2, ticker="APH", r_level=88.165, s_level=77.68,
             r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
             first_seen="2026-09-04", last_seen="2026-09-04", nights_seen=1),
    ], ddl=_legacy_ddl().replace("abnormal_ret_to_date FLOAT, ", ""))

    assert migrate_near_miss_framing_identity(make_sqlite_engine(db)) is True

    con = sqlite3.connect(db)
    try:
        row = con.execute(
            "SELECT id, first_seen, nights_seen, abnormal_ret_to_date "
            "FROM near_miss_archive").fetchall()
        assert row == [(1, "2026-08-27", 3, None)]
    finally:
        con.close()


# ── the constraint bites, and the writer upserts against it ───────────────────
def test_a_rail_that_moves_cannot_mint_a_second_episode(tmp_path, monkeypatch):
    """The whole point, end to end through the writer: the same framing observed
    again with a differently-rounded (or split-rescaled) rail is a RECURRENCE —
    counters bump, the record stands — not a new row."""
    from sqlalchemy.orm import sessionmaker

    import database
    from core.archive import near_miss_writer as nmw

    eng = make_sqlite_engine(str(tmp_path / "lane.db"))
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=eng))

    margins = {"width": 0.17, "respect_share": 1, "respect_run": 9,
               "crash": 0.25, "r_touches": 2, "s_touches": 1,
               "r_touch_thirds": 0, "s_touch_thirds": 0, "lower_dwell": -1,
               "upper_dwell": 3, "mid_dwell": 4, "coverage": 1,
               "traversal_count": 0, "traversal_density": 0.02}

    def _lane_row(scan_date, r_level, s_level):
        return {"ticker": "APH", "scan_date": scan_date,
                "r_level": r_level, "s_level": s_level,
                "r_anchor_date": "2026-08-06", "s_anchor_date": "2026-08-03",
                "window_start_date": "2026-08-03", "window_end_date": scan_date,
                "pool": "strict", "kill_stage": "occupancy",
                "failing_leg": "occupancy", "judged_n": 28, "fired_night": 0,
                "episode_profile": "S+ R^", "margins": dict(margins),
                "would_be_trigger": r_level, "scan_close": s_level + 1.0,
                "lane_ruleset": "2026-07-26.A"}

    first = nmw.archive_near_miss_rows(
        [_lane_row("2026-09-02", 88.165, 77.6801)],
        universe_type="us_equities", enable=True)
    assert first["inserted"] == 1

    # Same framing, rail re-read one ten-thousandth lower.
    again = nmw.archive_near_miss_rows(
        [_lane_row("2026-09-04", 88.165, 77.68)],
        universe_type="us_equities", enable=True)
    assert again["inserted"] == 0
    assert again["recurred"] == 1

    # Same framing after a 2-for-1 split — the rails halve, the box does not move.
    split = nmw.archive_near_miss_rows(
        [_lane_row("2026-09-08", 44.0825, 38.84)],
        universe_type="us_equities", enable=True)
    assert split["inserted"] == 0
    assert split["recurred"] == 1

    session = sessionmaker(bind=eng)()
    try:
        rows = session.query(archive_models.NearMissArchive).all()
        assert len(rows) == 1, "a moving price minted a second episode"
        assert rows[0].first_seen == "2026-09-02"     # the clock never restarted
        assert rows[0].last_seen == "2026-09-08"
        assert rows[0].nights_seen == 3
        assert rows[0].s_level == 77.6801             # first-refusal evidence stands
    finally:
        session.close()
    eng.dispose()


def test_the_database_itself_refuses_a_second_row_on_one_framing(tmp_path):
    """Belt to the writer's braces: the constraint is an assertion, so the DB
    rejects the duplicate even if some future writer forgets to probe."""
    from sqlalchemy.orm import sessionmaker

    eng = make_sqlite_engine(str(tmp_path / "constraint.db"))
    archive_models.NearMissArchive.__table__.create(bind=eng)
    session = sessionmaker(bind=eng)()
    common = dict(_REQUIRED, universe_type="us_equities", ticker="APH",
                  r_anchor_date="2026-08-06", s_anchor_date="2026-08-03",
                  first_seen="2026-09-02", last_seen="2026-09-02",
                  nights_seen=1, fired_any_night=0)
    try:
        session.add(archive_models.NearMissArchive(
            r_level=88.165, s_level=77.6801, **common))
        session.commit()
        session.add(archive_models.NearMissArchive(
            r_level=88.165, s_level=77.68, **common))
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        eng.dispose()
