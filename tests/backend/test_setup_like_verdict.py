"""The LIKE verdict on a setup (operator 2026-09-02).

`setup_reviews` carries ONE row per setup and a closed two-value verdict, so the
operator's two marks are mutually exclusive by construction:

  "liked"  — the screener card's heart: the kind of setup he wants more of
  "passed" — the archive's saw-&-skipped, which feeds the missed-winners report

That pairing is the whole point and the reason these tests are worth their
weight: a like is only INFORMATIVE against a negative class. Likes alone cannot
tell "he saw it and shrugged" from "he never looked at it", so the two verdicts
must stay separable — a like must never be counted as a pass (it would poison
missed-winners with charts he actually wanted) and a pass must never be counted
as a like (it would poison the preference study with charts he rejected).

The tests below pin exactly that separation, plus the replace-don't-stack
behaviour the unique constraint implies when he changes his mind about a chart.
"""
from __future__ import annotations

import sys

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from domains.archive import reviews as archive_reviews  # noqa: E402
from domains.archive.schemas import ReviewToggleIn  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

SCAN_DATE = "2026-08-20"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    models.SetupReview.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _like(db, ticker="NP", scan_date=SCAN_DATE):
    return archive_reviews.toggle_like(ReviewToggleIn(ticker=ticker, scan_date=scan_date), db=db)


def _pass(db, ticker="NP", scan_date=SCAN_DATE):
    return archive_reviews.toggle_review(ReviewToggleIn(ticker=ticker, scan_date=scan_date), db=db)


def _rows(db):
    return db.query(models.SetupReview).all()


def test_like_writes_its_own_verdict_and_toggles_off(db):
    assert _like(db)["liked"] is True
    rows = _rows(db)
    assert len(rows) == 1
    assert (rows[0].ticker, rows[0].scan_date, rows[0].verdict) == ("NP", SCAN_DATE, "liked")
    assert rows[0].created_at is not None

    # Clicking the verdict it already carries clears the row entirely — an
    # unliked setup is UNMARKED, never silently demoted to "passed".
    assert _like(db)["liked"] is False
    assert _rows(db) == []


def test_a_like_is_never_counted_as_a_pass(db):
    """The separation that protects the missed-winners report.

    If a like leaked into the passed set, every chart he actually WANTED would
    read as 'reviewed and skipped' — the report's whole job is telling those two
    apart, and it would be wrong in the most misleading direction.
    """
    _like(db)
    assert archive_reviews.list_liked_reviews(db=db) == {"tickers": ["NP"]}
    assert archive_reviews.list_passed_reviews(db=db) == {"tickers": []}


def test_a_pass_is_never_counted_as_a_like(db):
    """The mirror, protecting the preference study: a chart he rejected must
    not arrive in the corpus of charts he wants more of."""
    _pass(db)
    assert archive_reviews.list_passed_reviews(db=db) == {"tickers": ["NP"]}
    assert archive_reviews.list_liked_reviews(db=db) == {"tickers": []}


def test_changing_his_mind_REPLACES_the_verdict_rather_than_stacking(db):
    """One row per setup (the unique constraint), so the latest verdict wins.

    Stacking would be the quiet failure: the same chart would appear in BOTH
    the liked corpus and the skipped corpus, and every downstream count would
    double-count it.
    """
    _like(db)
    result = _pass(db)
    assert result["passed"] is True
    assert result["verdict"] == "passed"
    rows = _rows(db)
    assert len(rows) == 1 and rows[0].verdict == "passed"
    assert archive_reviews.list_liked_reviews(db=db) == {"tickers": []}

    # ...and back again.
    assert _like(db)["liked"] is True
    rows = _rows(db)
    assert len(rows) == 1 and rows[0].verdict == "liked"
    assert archive_reviews.list_passed_reviews(db=db) == {"tickers": []}


def test_verdicts_are_per_setup_not_per_ticker(db):
    """Keyed on (ticker, scan_date): the same name can be liked in one episode
    and skipped in another, which is the normal case over months of scans."""
    _like(db, scan_date="2026-08-20")
    _pass(db, scan_date="2026-05-04")
    assert len(_rows(db)) == 2
    assert archive_reviews.list_liked_reviews(db=db) == {"tickers": ["NP"]}
    assert archive_reviews.list_passed_reviews(db=db) == {"tickers": ["NP"]}


def test_the_verdict_set_stays_closed(db):
    """The helper is the ONE writer, and it refuses anything outside the set —
    a third verdict must be a deliberate change here, not a typo at a call site.
    """
    assert archive_reviews.SETUP_VERDICTS == ("passed", "liked")
    with pytest.raises(AssertionError):
        archive_reviews._toggle_verdict(db, "NP", SCAN_DATE, "loved")


def test_a_blank_ticker_is_refused(db):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        _like(db, ticker="   ")
    assert excinfo.value.status_code == 400
