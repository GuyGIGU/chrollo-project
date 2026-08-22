"""Council 2026-06-30 P2 follow-up — the episode-grouping cache version is
scoped per universe_type. The signature was whole-table, so a commodities/ETF
insert (the daily multi-universe scan) busted the cached us_equities grouping
even though no equities row changed — forcing a full re-group on the next
/episodes + /missed-winners request. These pin the scoping end to end: the
signature ignores other universes' rows, the cached equities grouping survives
an ETF insert, and an equities insert still invalidates it.

Real throwaway SQLite database, never the live DB.
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import database  # noqa: E402
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE  # noqa: E402
from services import archive_queries  # noqa: E402
from services.episode_cache import VersionedCache  # noqa: E402


@pytest.fixture()
def db():
    engine = database.make_sqlite_engine(":memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine, autoflush=False)()
    yield sess
    sess.close()
    engine.dispose()


def _add_row(db, ticker, universe_type, scan_date="2026-06-25"):
    db.add(archive_models.SetupArchive(
        ticker=ticker, scan_date=scan_date, setup_type="LPS", tier="B", score=1.0,
        s_level=90.0, trigger_price=100.0, source="screener",
        universe_type=universe_type,
    ))
    db.commit()


def test_scoped_version_ignores_other_universes(db):
    _add_row(db, "AAA", DEFAULT_UNIVERSE_TYPE)
    before = archive_queries._archive_version(db, DEFAULT_UNIVERSE_TYPE)

    _add_row(db, "SPY", "us_sectors")
    # The equities-scoped signature must not move on a sectors insert…
    assert archive_queries._archive_version(db, DEFAULT_UNIVERSE_TYPE) == before
    # …while the unscoped (all-universes) signature must.
    assert archive_queries._archive_version(db) != before

    _add_row(db, "BBB", DEFAULT_UNIVERSE_TYPE)
    assert archive_queries._archive_version(db, DEFAULT_UNIVERSE_TYPE) != before


def test_cached_equities_grouping_survives_etf_insert(db, monkeypatch):
    monkeypatch.setattr(archive_queries, "_EPISODE_CACHE", VersionedCache())
    builds = {"n": 0}
    real_build = archive_queries._build_grouping

    def spy(db_, filters):
        builds["n"] += 1
        return real_build(db_, filters)

    monkeypatch.setattr(archive_queries, "_build_grouping", spy)

    _add_row(db, "AAA", DEFAULT_UNIVERSE_TYPE)
    archive_queries._grouped_episodes(db, {})
    assert builds["n"] == 1
    archive_queries._grouped_episodes(db, {})
    assert builds["n"] == 1  # warm cache, nothing changed

    # An ETF insert leaves the cached equities grouping intact (the defect:
    # the whole-table signature rebuilt here).
    _add_row(db, "SPY", "us_sectors")
    eps = archive_queries._grouped_episodes(db, {})
    assert builds["n"] == 1
    assert [e.ticker for e in eps] == ["AAA"]

    # An equities insert still invalidates — and the ETF row stays excluded.
    _add_row(db, "BBB", DEFAULT_UNIVERSE_TYPE)
    eps = archive_queries._grouped_episodes(db, {})
    assert builds["n"] == 2
    assert sorted(e.ticker for e in eps) == ["AAA", "BBB"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
