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


def _row(ticker="EGBN", scan_date="2026-01-15", fired=0, r=25.0, s=22.5):
    return {"ticker": ticker, "scan_date": scan_date, "r_level": r,
            "s_level": s, "r_anchor_date": "2025-12-01",
            "s_anchor_date": "2025-12-08", "window_start_date": "2025-12-01",
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
    assert row.would_be_score is None and row.would_be_tier is None
    assert row.lane_ruleset == "2026-07-26.A"
    assert row.engine_config_version
    db.close()


def test_writer_caps_and_dedup_are_counted(lane_db, monkeypatch):
    monkeypatch.setattr(settings, "NEAR_MISS_WRITER_TICKER_CAP", 1)
    monkeypatch.setattr(settings, "NEAR_MISS_WRITER_GLOBAL_CAP", 2)
    rows = [_row(), _row(),                                   # exact duplicate
            _row(r=26.0, s=23.0),                             # same ticker, 2nd framing
            _row(ticker="AAA", r=11.0, s=10.0),
            _row(ticker="BBB", r=12.0, s=11.0)]
    counters = nmw.archive_near_miss_rows(rows, universe_type="us_equities",
                                          enable=True)
    assert counters["dedup_dropped"] == 1
    assert counters["ticker_cap_dropped"] == 1                # EGBN's 2nd framing
    assert counters["global_cap_dropped"] == 1                # BBB over the global 2
    assert counters["inserted"] == 2


def test_writer_enable_passthrough_writes_nothing(lane_db):
    counters = nmw.archive_near_miss_rows([_row()], universe_type="us_equities",
                                          enable=False)
    assert counters["inserted"] == 0
    insp = inspect(database.engine)
    assert "near_miss_archive" not in insp.get_table_names()


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
