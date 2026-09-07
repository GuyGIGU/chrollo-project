"""Near-miss cohort store integrity (near-miss lane Task 9) — Leach/Beck.

The store trio for every closed-set label (EC-19: fresh-DB CHECK +
stamping-point refusal + this archive-layer test), the R-EPISODE upsert
semantics (recurrence bumps counters, NEVER the record), the cap/dedup
counters (no silent bounds), the enable pass-through, and the generalized
model-diff migrator covering the new table at birth. Hermetic: throwaway
sqlite files, never the live DB.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import database  # noqa: E402
from config import settings  # noqa: E402
from core.archive import near_miss_writer as nmw  # noqa: E402
from services import startup  # noqa: E402

pytestmark = pytest.mark.regression

_MARGINS = {"width": 0.17, "respect_share": 1, "respect_run": 9,
            "crash": 0.25, "r_touches": 2, "s_touches": 1,
            "r_touch_thirds": 0, "s_touch_thirds": 0,
            "lower_dwell": -1, "upper_dwell": 3, "mid_dwell": 4,
            "coverage": 1, "traversal_count": 0, "traversal_density": 0.02}


def _row(ticker="EGBN", scan_date="2026-01-15", fired=0, r=25.0, s=22.5,
         r_anchor="2025-12-01", s_anchor="2025-12-08"):
    # The framing identity is the ANCHOR DATES (council review 2026-09-07
    # finding 5), so a SECOND framing on one ticker is expressed by moving the
    # anchors — moving only the rails names the same box.
    return {"ticker": ticker, "scan_date": scan_date, "r_level": r,
            "s_level": s, "r_anchor_date": r_anchor,
            "s_anchor_date": s_anchor, "window_start_date": "2025-12-01",
            "window_end_date": scan_date, "pool": "strict",
            "kill_stage": "occupancy", "failing_leg": "occupancy",
            "judged_n": 28, "fired_night": fired,
            "episode_profile": "S+ S+ R^", "margins": dict(_MARGINS),
            "would_be_trigger": r, "scan_close": 24.2,
            "lane_ruleset": "2026-07-26.A"}


@pytest.fixture()
def lane_db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'lane.db'}")
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=eng))
    return eng


def test_fresh_db_checks_close_the_label_sets(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    archive_models.NearMissArchive.__table__.create(bind=eng)
    db = sessionmaker(bind=eng)()

    def _model(ticker, leg, pool):
        return archive_models.NearMissArchive(
            ticker=ticker, universe_type="us_equities", r_level=10.0,
            s_level=9.0, r_anchor_date="2026-01-02",
            s_anchor_date="2026-01-06", first_seen="2026-02-02",
            last_seen="2026-02-02", nights_seen=1, fired_first_night=0,
            fired_any_night=0, pool=pool, kill_stage=leg, failing_leg=leg,
            lane_ruleset="2026-07-26.A", engine_config_version="x",
            judged_n=20, window_start_date="2026-01-02",
            window_end_date="2026-02-02", nm_width=0.1, nm_respect_share=1,
            nm_respect_run=1, nm_crash=0.1, nm_r_touches=1, nm_s_touches=1,
            nm_r_touch_thirds=1, nm_s_touch_thirds=1, nm_lower_dwell=1,
            nm_upper_dwell=1, nm_mid_dwell=1, nm_coverage=1,
            nm_traversal_count=1, nm_traversal_density=0.1,
            would_be_trigger=10.0, scan_close=9.5)

    db.add(_model("OK1", "occupancy", "strict"))
    db.commit()
    db.add(_model("BAD1", "typo_leg", "strict"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(_model("BAD2", "occupancy", "story"))   # story is policy, never a pool here
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_stamping_points_refuse_unknown_labels():
    assert nmw._failing_leg_label("respect_share") == "respect_share"
    assert nmw._pool_label("band") == "band"
    for bad in (None, "typo", "", "Occupancy", "story"):
        with pytest.raises(ValueError, match="closed set"):
            nmw._failing_leg_label(bad)
    with pytest.raises(ValueError, match="closed set"):
        nmw._pool_label("story")


def test_writer_episode_upsert_and_counters(lane_db):
    first = nmw.archive_near_miss_rows(
        [_row(), _row(ticker="ZZT", fired=1)],
        universe_type="us_equities", enable=True)
    assert first["inserted"] == 2 and first["recurred"] == 0

    # Re-observation the next night, now fired: counters move, record doesn't.
    second = nmw.archive_near_miss_rows(
        [_row(scan_date="2026-01-16", fired=1)],
        universe_type="us_equities", enable=True)
    assert second["inserted"] == 0 and second["recurred"] == 1

    db = database.SessionLocal()
    row = db.query(archive_models.NearMissArchive).filter_by(ticker="EGBN").one()
    assert row.first_seen == "2026-01-15"          # the forward-clock anchor
    assert row.last_seen == "2026-01-16" and row.nights_seen == 2
    assert row.fired_first_night == 0 and row.fired_any_night == 1
    assert row.nm_lower_dwell == -1                # first refusal's evidence, untouched
    assert row.lane_ruleset == "2026-07-26.A"
    assert row.engine_config_version
    db.close()


def test_writer_caps_and_dedup_are_counted(lane_db, monkeypatch):
    monkeypatch.setattr(settings, "NEAR_MISS_WRITER_TICKER_CAP", 1)
    monkeypatch.setattr(settings, "NEAR_MISS_WRITER_GLOBAL_CAP", 2)
    # The writer sorts on (ticker, anchors, rails) BEFORE dedup/caps (review
    # 2026-07-26 finding 15), so WHICH rows the caps drop is a function of the
    # rows alone — the deliberately shuffled input below must land exactly
    # the same drop set as any other arrival order.
    rows = [_row(),                                           # EGBN — sorts past the global 2
            _row(ticker="BBB", r=12.0, s=11.0),
            _row(ticker="AAA", r=13.0, s=12.0,                # AAA's 2nd framing
                 r_anchor="2025-12-15", s_anchor="2025-12-22"),
            _row(ticker="AAA", r=11.0, s=10.0),
            _row(ticker="AAA", r=11.0, s=10.0)]               # exact duplicate
    counters = nmw.archive_near_miss_rows(rows, universe_type="us_equities",
                                          enable=True)
    assert counters["dedup_dropped"] == 1
    assert counters["ticker_cap_dropped"] == 1                # AAA's 2nd framing
    assert counters["global_cap_dropped"] == 1                # EGBN, deterministically
    assert counters["inserted"] == 2
    db = database.SessionLocal()
    kept = sorted(r.ticker for r in db.query(archive_models.NearMissArchive).all())
    db.close()
    assert kept == ["AAA", "BBB"]                             # the reproducible cut


def test_two_rails_on_one_framing_dedup_in_memory_before_the_flush(lane_db):
    """One night, ONE framing, two rails — APH's split re-read, or plain 4dp
    float noise. The IN-MEMORY key must drop the second row, not the constraint.

    ``session.autoflush`` is off, so the existence probe cannot see the first
    row's pending add: if the in-memory key still carried the rails, both rows
    would be added, the UNIQUE would bite on ``commit()``, and the whole night's
    near-miss batch would degrade to ``flush_error`` with ``inserted = 0`` —
    precisely the EC-4 failure this identity change exists to close, on the half
    of it the probe test does not reach. The exact-duplicate case above dedups
    under either key and so proves nothing here."""
    counters = nmw.archive_near_miss_rows(
        [_row(ticker="APH", r=88.165, s=77.6801),
         _row(ticker="APH", r=176.33, s=155.36)],
        universe_type="us_equities", enable=True)
    assert counters["dedup_dropped"] == 1
    assert counters["inserted"] == 1
    assert counters["flush_error"] == 0

    db = database.SessionLocal()
    rows = db.query(archive_models.NearMissArchive).all()
    db.close()
    assert len(rows) == 1
    # The pre-dedup sort is on (ticker, anchors, rails), so WHICH of a colliding
    # pair survives is a function of the rows alone.
    assert rows[0].r_level == 88.165


def test_real_deferred_rows_round_trip_through_the_writer(lane_db, monkeypatch):
    """The producer→writer contract proven on REAL deferred_rows output, not
    hand-typed fixture twins (review 2026-07-26 finding 10): a renamed margin
    key or row field now KeyErrors HERE, not on the first live flush."""
    import pandas as pd
    import pytest as _pytest

    from engine_alpha.evaluation import evaluate_ticker_with_near_miss
    from tools.marks_corpus import _FROZEN_BREADTH
    from tools.marks_corpus import _load_fixture as _load_marks_fixture
    from tools.replay import fixture_frame

    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp("2026-01-15")]
    _result, rows, _stats = evaluate_ticker_with_near_miss(
        e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert rows, "the flagship frame produced no ruled rows"

    counters = nmw.archive_near_miss_rows(rows, universe_type="us_equities",
                                          enable=True)
    assert counters["inserted"] == len(rows) and counters["flush_error"] == 0

    db = database.SessionLocal()
    for row in rows:
        stored = db.query(archive_models.NearMissArchive).filter_by(
            ticker=row["ticker"], r_level=row["r_level"],
            s_level=row["s_level"], r_anchor_date=row["r_anchor_date"],
            s_anchor_date=row["s_anchor_date"]).one()
        for leg, margin in row["margins"].items():
            if leg == "window":
                continue          # nullable: floor unconsulted at this seam
            assert getattr(stored, f"nm_{leg}") == _pytest.approx(margin), leg
        assert stored.pool == row["pool"]
        assert stored.failing_leg == row["failing_leg"]
        assert stored.first_seen == row["scan_date"]
    db.close()


def test_writer_enable_passthrough_writes_nothing(lane_db):
    counters = nmw.archive_near_miss_rows([_row()], universe_type="us_equities",
                                          enable=False)
    assert counters["inserted"] == 0
    insp = inspect(database.engine)
    assert "near_miss_archive" not in insp.get_table_names()


_WOULD_BE_DROPS = (
    "ALTER TABLE near_miss_archive DROP COLUMN would_be_score",
    "ALTER TABLE near_miss_archive DROP COLUMN would_be_tier",
)

# The runner's idempotency predicate (see startup._apply_migrations) — the
# same contract test_startup_migrations pins for the ADD side.
_SKIP_MARKERS = ("duplicate column", "already exists", "no such column")


def test_would_be_pair_is_retired_model_and_migration():
    """would_be_score/would_be_tier were declared, rendered, and unwritable —
    no writer ever existed, and a refused framing has no election context to
    score (council review 2026-08-22). The model must not re-grow the pair,
    and the one-off DROP must be registered so a DB restored from a pre-drop
    backup converges instead of resurrecting the columns permanently."""
    cols = {c.name for c in archive_models.NearMissArchive.__table__.columns}
    assert "would_be_score" not in cols and "would_be_tier" not in cols
    for stmt in _WOULD_BE_DROPS:
        assert stmt in startup._MIGRATIONS, f"missing migration: {stmt}"


def test_would_be_drop_converges_a_predrop_db_and_rerun_is_idempotent(tmp_path):
    """A pre-drop DB (columns present) converges on one application; a re-run
    on the already-clean DB raises exactly a skip-marker error — the runner's
    already-applied contract, so a boot on a migrated DB is a no-op."""
    db = tmp_path / "predrop.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE near_miss_archive "
                "(id INTEGER PRIMARY KEY, ticker VARCHAR, "
                "would_be_score FLOAT, would_be_tier VARCHAR)")
    con.commit()

    for stmt in _WOULD_BE_DROPS:
        con.execute(stmt)
    con.commit()
    cols = {r[1] for r in con.execute("PRAGMA table_info(near_miss_archive)")}
    assert "would_be_score" not in cols and "would_be_tier" not in cols

    for stmt in _WOULD_BE_DROPS:
        with pytest.raises(sqlite3.OperationalError) as exc:
            con.execute(stmt)
        assert any(m in str(exc.value).lower() for m in _SKIP_MARKERS), str(exc.value)
    con.close()


def test_model_diff_migrator_covers_the_new_table_at_birth(tmp_path):
    assert any(t == "near_miss_archive"
               for t, _m in startup._MIGRATED_ARCHIVE_MODELS)
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE near_miss_archive "
                "(id INTEGER PRIMARY KEY, ticker VARCHAR)")
    con.commit()
    con.close()
    eng = create_engine(f"sqlite:///{db}")
    statements = startup.model_add_column_migrations(eng)
    added = {s.split(" ADD COLUMN ")[1].split(" ")[0]
             for s in statements if "near_miss_archive" in s}
    model_cols = {c.name for c in
                  archive_models.NearMissArchive.__table__.columns
                  if not c.primary_key}
    assert added == model_cols - {"ticker"}, (
        "the generalized migrator must surface every model-only column")
