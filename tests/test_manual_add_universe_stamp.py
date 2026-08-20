"""Manual-add route stamps the widened identity key (conventions.md EC-4).

Defect (2026-08-06 inventory sweep): POST /add-setup never stamped
``universe_type`` — the mapper auto-filled it as None, the ORM then OMITS a
None-valued column that declares a server_default, and on the ALTER-migrated
live DB (ADD COLUMN carries no SQLite-level DEFAULT) the omission lands NULL:
rows silently invisible to every default-scoped read. A fresh create_all DB
(this fixture) masks that — its DDL-level DEFAULT fires on the omission — so
the stamp is pinned on the assembled constructor kwargs (what the live INSERT
is built from), not just the persisted fresh-DB row. The route's existence
check was also still the 2-col (ticker, scan_date) identity instead of the
widened 3-col key seed.py already uses.

Real route handler against a real throwaway SQLite database — never a mocked
session, never the live DB, never a booted app (hard-safety line). Downloads,
the eval, and market context are monkeypatched at their source modules (the
route imports them at call time).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import database  # noqa: E402
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE  # noqa: E402
from routers.archive_actions import add_setup_manually  # noqa: E402
from routers.archive_schemas import ManualSetupIn  # noqa: E402

SCAN_DATE = "2026-06-25"


@pytest.fixture()
def db():
    engine = database.make_sqlite_engine(":memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine, autoflush=False)()
    yield sess
    sess.close()
    engine.dispose()


def _flat_ohlcv(end, periods=250):
    """A flat single-ticker OHLCV frame ending AT the scan date, so the route's
    forward slice is empty and no forward-return computation runs."""
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=periods)
    return pd.DataFrame(
        {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0,
         "Volume": 1_000_000.0},
        index=idx,
    )


def _eval_result():
    """The required-via-[] keys of the route's overrides block; .get keys may
    be absent (they map to NULL)."""
    return {
        "setup_type": "LPS", "tier": "A", "score": 55.0,
        "current_price": 100.0, "r_level": 110.0, "s_level": 90.0,
        "trigger_price": 111.0, "base_length": 40, "box_width": 0.2,
        "touches": 6, "r_touches": 3, "s_touches": 3, "atr_ratio": 0.5,
        "lps_length": 5, "breach_days": 0, "vol_contraction": 0.8,
        "tightness_ratio": 0.5,
    }


def _call_add(db, monkeypatch, ticker="AAA", scan_date=SCAN_DATE):
    """Drive the real route handler; returns (persisted row, the constructor
    kwargs the route assembled — i.e. exactly what a live INSERT is built from)."""
    import core.archive.seed as seed_mod
    import core.pipeline.downloads as downloads
    import engine_alpha.freeze.manifest as manifest_mod
    import routers.archive_actions as actions_mod

    monkeypatch.setattr(downloads, "_batched_download",
                        lambda tickers, params, label: _flat_ohlcv(scan_date))
    monkeypatch.setattr(seed_mod, "_evaluate_at_date", lambda _df: _eval_result())
    monkeypatch.setattr(manifest_mod, "manifest_hash", lambda: "test-manifest")
    monkeypatch.setattr(archive_models, "get_market_context", lambda _d: {})
    monkeypatch.setattr(archive_models, "get_sector_etf", lambda _t: None)

    assembled = {}
    real_mapper = actions_mod.archive_row_from_result

    def spy(result, *, overrides):
        kwargs = real_mapper(result, overrides=overrides)
        assembled.update(kwargs)
        return kwargs

    monkeypatch.setattr(actions_mod, "archive_row_from_result", spy)

    row = add_setup_manually(ManualSetupIn(ticker=ticker, scan_date=scan_date), db)
    return row, assembled


def test_manual_row_lands_with_universe_tag_and_is_default_scope_visible(db, monkeypatch):
    row, assembled = _call_add(db, monkeypatch)

    # The stamp itself, at the assembled-kwargs level: the route's overrides
    # carry the constant (EC-1). None here means the ORM omits the column and
    # the ALTER-migrated live DB (no DDL-level default) lands NULL — the fresh
    # fixture DB's DEFAULT would mask that, so the row check alone is not enough.
    assert assembled["universe_type"] == DEFAULT_UNIVERSE_TYPE
    assert row.universe_type == DEFAULT_UNIVERSE_TYPE
    assert row.source == "manual"

    # And the row is visible to the default-scoped read surface (the shared
    # filter layer under /setups, /episodes, analyze) — a NULL-universe row
    # falls out of exactly this query.
    from services.archive_queries import _apply_setup_filters

    scoped = _apply_setup_filters(db.query(archive_models.SetupArchive)).all()
    assert [(r.ticker, r.scan_date) for r in scoped] == [("AAA", SCAN_DATE)]


def test_existence_check_uses_the_3col_identity(db, monkeypatch):
    # A same ticker/scan_date row in ANOTHER universe is a different identity —
    # under the old 2-col check it would have 409'd this manual equities add.
    db.add(archive_models.SetupArchive(
        ticker="AAA", scan_date=SCAN_DATE, setup_type="LPS", tier="B", score=1.0,
        s_level=90.0, trigger_price=0.0, source="screener", universe_type="us_sectors",
    ))
    db.commit()

    row, _ = _call_add(db, monkeypatch)
    assert row.universe_type == DEFAULT_UNIVERSE_TYPE

    # The equities identity itself still dedups: a repeat manual add is a 409.
    with pytest.raises(HTTPException) as exc:
        _call_add(db, monkeypatch)
    assert exc.value.status_code == 409

    # Contrast: the sectors row stays outside the default equities scope.
    from services.archive_queries import _apply_setup_filters

    scoped = _apply_setup_filters(db.query(archive_models.SetupArchive)).all()
    assert [(r.ticker, r.universe_type) for r in scoped] == [("AAA", DEFAULT_UNIVERSE_TYPE)]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
