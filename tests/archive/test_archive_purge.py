"""Safety guards for the only module that DELETES archive rows.

``core.archive.purge`` shipped untested — the sole engine/core module with no
coverage, and the one that removes the unbiased edge-measurement record. Two
things here are easy to break silently and expensive to notice:

* **The SQL NULL trap.** ``~col.in_([...])`` is FALSE for NULL in SQL, not
  TRUE — so stray rows with a NULL source would quietly survive the purge they
  are the whole point of. The module matches them explicitly; that is pinned.
* **The protected set.** ``source='screener'`` rows carry forward returns that
  are still accruing; deleting them resets the measurement clock to zero. They
  must survive unless ``--include-live`` is passed, and seed/manual must
  survive even then.

Every test runs against an in-memory database injected at
``database.make_sqlite_engine`` — the module's own path is hardcoded to the
LIVE archive, so it is never opened here.
"""
import sys

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.archive import purge as purge_module  # noqa: E402

# ticker, source — one row per source the purge must reason about
_ROWS = [
    ("SEED", "seed"),
    ("MANU", "manual"),
    ("LIVE", "screener"),
    ("STRAY", "test"),
    ("NULLY", None),
]


@pytest.fixture
def archive(monkeypatch):
    """An in-memory setup_archive holding one row per source class."""
    import archive_models
    import database
    from sqlalchemy.orm import sessionmaker

    engine = database.make_sqlite_engine(":memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    for ticker, source in _ROWS:
        session.add(archive_models.SetupArchive(
            ticker=ticker, scan_date="2026-08-01", setup_type="LPS", tier="A",
            score=1.0, s_level=90.0, trigger_price=0.0, source=source,
            universe_type="us_equities"))
    session.commit()
    session.close()

    # source is Column(String, default="screener"), so the ORM turns a None
    # into "screener" on insert — a genuine NULL has to be forced. The live
    # archive holds zero NULL rows today (10,152 screener / 45 seed / 1 manual,
    # measured 2026-08-25) precisely because of that default, which makes the
    # module's NULL branch defensive rather than hot. Defensive code that is
    # never exercised is exactly the kind that rots unnoticed.
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE setup_archive SET source = NULL WHERE ticker = 'NULLY'"))

    monkeypatch.setattr(database, "make_sqlite_engine", lambda _p: engine)

    def surviving():
        s = sessionmaker(bind=engine, autoflush=False)()
        try:
            return {t for (t,) in s.query(archive_models.SetupArchive.ticker)}
        finally:
            s.close()

    return surviving


def test_a_dry_run_deletes_nothing(archive):
    """The default invocation is a REPORT. It must never touch a row."""
    result = purge_module.purge()
    assert result == {"would_delete": 2}, "stray + NULL are the deletable pair"
    assert archive() == {"SEED", "MANU", "LIVE", "STRAY", "NULLY"}


def test_a_dry_run_with_include_live_still_deletes_nothing(archive):
    """--include-live widens the SCOPE, it does not imply --apply."""
    result = purge_module.purge(include_live=True)
    assert result == {"would_delete": 3}, "screener joins the deletable set"
    assert archive() == {"SEED", "MANU", "LIVE", "STRAY", "NULLY"}


def test_the_default_purge_protects_seed_manual_and_live(archive):
    result = purge_module.purge(apply=True)
    assert result == {"deleted": 2}
    assert archive() == {"SEED", "MANU", "LIVE"}, (
        "source='screener' is the unbiased edge record — deleting it without "
        "--include-live resets the measurement clock to zero"
    )


def test_a_null_source_row_is_purged_not_silently_spared(archive):
    """The SQL NULL trap: ``~col.in_([...])`` is FALSE for NULL, so a bare
    negated IN would leave every stray NULL row behind — exactly the rows the
    purge exists to remove."""
    purge_module.purge(apply=True)
    assert "NULLY" not in archive(), (
        "a NULL source survived: the explicit is_(None) match has been lost, "
        "and the purge now silently spares the rows it is meant to delete"
    )


def test_include_live_deletes_screener_but_still_spares_seed_and_manual(archive):
    result = purge_module.purge(apply=True, include_live=True)
    assert result == {"deleted": 3}
    assert archive() == {"SEED", "MANU"}, (
        "seed and manual are protected at every setting — no flag deletes them"
    )
