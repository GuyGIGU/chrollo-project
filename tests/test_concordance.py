"""Epoch honesty + the verdict channel (TA-grade build task 14).

Pins the concordance reader's two ruled flags (orphans surfaced, version
mismatches flagged), the grade channel's closed vocabulary at the router
(EC-19 write-time legs + producing tests per EC-22), and the migration
registration that lets read_verdicts gain model-only columns.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))


def _mem_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    import archive_models  # noqa: F401 — register on Base before create_all
    import models          # noqa: F401

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _fire(ticker, scan_date, ecv, **cols):
    from archive_models import SetupArchive

    base = dict(ticker=ticker, scan_date=scan_date, setup_type="LPS",
                tier="B", score=90.0, current_price=10.0, r_level=11.0,
                s_level=9.5, trigger_price=11.1, base_length=30,
                box_width=0.1, touches=4, atr_ratio=0.5, lps_length=3,
                breach_days=0, vol_contraction=0.4, tightness_ratio=0.4,
                engine_config_version=ecv, source="screener")
    base.update(cols)
    return SetupArchive(**base)


def _verdict(ticker, scan_date, ecv, **kw):
    from models import ReadVerdict

    base = dict(ticker=ticker, scan_date=scan_date,
                universe_type="us_equities", verdict="agree",
                engine_config_version=ecv)
    base.update(kw)
    return ReadVerdict(**base)


def test_concordance_surfaces_orphans_and_flags_version_mismatch():
    from services.concordance import read_verdict_concordance

    session = _mem_session()
    session.add_all([
        _fire("MATCH", "2026-08-07", "hashA", ta_grade=61.2),
        _fire("STALE", "2026-08-07", "hashB"),
        _verdict("MATCH", "2026-08-07", "hashA",
                 grade_verdict="too_high", note="graded rich"),
        # The operator judged hashA's narrative; a re-scan replaced it.
        _verdict("STALE", "2026-08-07", "hashA", verdict="disagree"),
        # A verdict on a never-archived scan — accepted evidence (ruled).
        _verdict("ORPHN", "2026-08-06", "hashA"),
    ])
    session.commit()
    report = read_verdict_concordance(session)
    assert report["n"] == 3
    assert report["orphans"] == 1
    assert report["version_mismatches"] == 1
    by_ticker = {r["ticker"]: r for r in report["rows"]}
    match = by_ticker["MATCH"]
    assert match["version_match"] is True and match["orphan"] is False
    assert match["grade_verdict"] == "too_high"
    assert match["ta_grade"] == pytest.approx(61.2)
    stale = by_ticker["STALE"]
    assert stale["version_match"] is False    # the narrative was replaced
    orphan = by_ticker["ORPHN"]
    assert orphan["orphan"] is True and orphan["archived"] is False
    assert orphan["version_match"] is None    # nothing to compare against


def test_grade_verdict_closed_vocabulary_at_the_router():
    """EC-19/22 for the grade channel: every legal value lands end-to-end
    through the real route handler; an illegal one is a 422 refusal; None
    clears. The route runs as a plain function (never a booted server)."""
    from fastapi import HTTPException
    from routers.archive_reviews import set_read_verdict
    from routers.archive_schemas import ReadVerdictIn
    from models import ReadVerdict

    session = _mem_session()
    for legal in ("agree", "too_high", "too_low"):
        out = set_read_verdict(ReadVerdictIn(
            ticker="AAA", scan_date="2026-08-07", verdict="agree",
            grade_verdict=legal), db=session)
        assert out["grade_verdict"] == legal
        row = session.query(ReadVerdict).filter_by(ticker="AAA").one()
        assert row.grade_verdict == legal
    with pytest.raises(HTTPException) as err:
        set_read_verdict(ReadVerdictIn(
            ticker="AAA", scan_date="2026-08-07", verdict="agree",
            grade_verdict="way_too_high"), db=session)
    assert err.value.status_code == 422
    # None = the grade was not judged; it clears any prior grade verdict
    # while the READ verdict stands (the two channels are separable).
    out = set_read_verdict(ReadVerdictIn(
        ticker="AAA", scan_date="2026-08-07", verdict="agree",
        grade_verdict=None), db=session)
    assert out["grade_verdict"] is None
    row = session.query(ReadVerdict).filter_by(ticker="AAA").one()
    assert row.grade_verdict is None and row.verdict == "agree"


def test_grade_verdict_round_trips_and_the_clear_coupling_refuses():
    """2026-08-08 review, finding 6: the channel must ROUND-TRIP — the
    identity GET serves the stored grade_verdict (it used to omit it, so the
    only read path could never show what the write path stored), a
    grade-verdict-with-null-read payload is a 422 (not an accept-and-drop),
    and the clear branch returns the same keys as its two siblings."""
    from fastapi import HTTPException
    from routers.archive_reviews import get_read_verdict, set_read_verdict
    from routers.archive_schemas import ReadVerdictIn
    from models import ReadVerdict

    session = _mem_session()
    set_read_verdict(ReadVerdictIn(
        ticker="BBB", scan_date="2026-08-07", verdict="disagree",
        grade_verdict="too_low", note="graded thin"), db=session)
    served = get_read_verdict(ticker="BBB", scan_date="2026-08-07",
                              universe_type=None, db=session)
    assert served == {"verdict": "disagree", "grade_verdict": "too_low",
                      "note": "graded thin"}
    # Grade-without-read is unrepresentable — refused, and the stored row
    # is untouched (no silent discard reporting success).
    with pytest.raises(HTTPException) as err:
        set_read_verdict(ReadVerdictIn(
            ticker="BBB", scan_date="2026-08-07", verdict=None,
            grade_verdict="too_high"), db=session)
    assert err.value.status_code == 422
    row = session.query(ReadVerdict).filter_by(ticker="BBB").one()
    assert row.verdict == "disagree" and row.grade_verdict == "too_low"
    # The clear branch's shape matches its siblings (grade_verdict present).
    out = set_read_verdict(ReadVerdictIn(
        ticker="BBB", scan_date="2026-08-07", verdict=None), db=session)
    assert out["verdict"] is None and out["grade_verdict"] is None
    empty = get_read_verdict(ticker="BBB", scan_date="2026-08-07",
                             universe_type=None, db=session)
    assert empty == {"verdict": None, "grade_verdict": None, "note": None}


def test_read_verdicts_is_registered_with_the_auto_migrator():
    """The table joined _MIGRATED_ARCHIVE_MODELS when it gained its first
    model-only column — otherwise grade_verdict would silently never reach
    the live DB (the mechanism's own registration rule)."""
    from services.startup import _MIGRATED_ARCHIVE_MODELS

    assert "read_verdicts" in {name for name, _fn in _MIGRATED_ARCHIVE_MODELS}
