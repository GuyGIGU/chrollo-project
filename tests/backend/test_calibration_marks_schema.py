"""Calibration-marks schema guards (Calibration at Scale, Task 1).

The marks table is operator-owned ground truth: the constraints ARE the
assertions (a constraint nobody has seen bite proves nothing), so each one is
driven to rejection here on a throwaway in-memory engine — never the live DB.
"""
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402  (resolves via BACKEND_DIR, like test_backend_services)
from models import CalibrationMark, CalibrationMarkEvent  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()
    engine.dispose()


def _mark(**overrides):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    fields = dict(
        ticker="BODI",
        as_of_date="2026-04-15",
        label="",
        verdict="box",
        resistance=12.40,
        support=10.15,
        box_start_date="2025-12-12",
        box_end_date="2026-04-16",
        data_regime="as_traded",
        engine_config_version="test-config",
        anchor_close=11.02,
        created_at=now,
        updated_at=now,
    )
    fields.update(overrides)
    return CalibrationMark(**fields)


def test_mini_consolidation_band_constraints_bite(session):
    """The mini-consolidation is a small BOX: the DDL refuses one with no band,
    a half band, and an inverted band — the same rails-order discipline the
    parent mark's own R/S carry."""
    def _save(**event_fields):
        mark = _mark(ticker="MINI", as_of_date=f"2026-04-{event_fields.pop('day')}")
        mark.events.append(CalibrationMarkEvent(
            event_type="mini_consolidation", start_date="2026-04-01",
            end_date="2026-04-10", source="operator", **event_fields))
        session.add(mark)
        session.commit()

    for day, fields in (("11", {}),                                   # no band
                        ("12", {"band_high": 12.40}),                 # half a band
                        ("13", {"band_high": 10.15, "band_low": 12.40})):  # inverted
        with pytest.raises(IntegrityError):
            _save(day=day, **fields)
        session.rollback()

    _save(day="14", band_high=12.40, band_low=10.15)
    saved = session.query(CalibrationMarkEvent).one()
    assert (saved.band_high, saved.band_low) == (12.40, 10.15)


def test_a_span_event_saves_with_no_band(session):
    """SOS and the other span types carry no band — the columns stay NULL."""
    mark = _mark(ticker="SOSX")
    mark.events.append(CalibrationMarkEvent(
        event_type="sos", start_date="2026-03-02", end_date="2026-03-13"))
    session.add(mark)
    session.commit()
    saved = session.query(CalibrationMarkEvent).one()
    assert (saved.band_high, saved.band_low) == (None, None)


def test_full_positive_mark_round_trips(session):
    mark = _mark()
    mark.events.append(CalibrationMarkEvent(
        event_type="phase_c", start_date="2026-02-10", end_date="2026-03-20",
        tip_date="2026-03-02", tip_price=6.77, source="extraction",
    ))
    session.add(mark)
    session.commit()
    got = session.query(CalibrationMark).one()
    assert (got.ticker, got.verdict, got.revision) == ("BODI", "box", 1)
    assert got.resistance == 12.40 and got.support == 10.15
    assert [e.event_type for e in got.events] == ["phase_c"]


def test_negative_mark_needs_no_geometry(session):
    session.add(_mark(verdict="no_structure", resistance=None, support=None,
                      box_start_date=None, box_end_date=None,
                      note="chop, no worked equilibrium"))
    session.commit()
    assert session.query(CalibrationMark).one().verdict == "no_structure"


def test_duplicate_identity_rejected(session):
    session.add(_mark())
    session.commit()
    session.add(_mark())
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    # A different label is a different structure on the same chart: allowed.
    session.add(_mark(label="upper shelf"))
    session.commit()


def test_unknown_verdict_rejected(session):
    session.add(_mark(verdict="maybe"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_box_without_rails_rejected(session):
    session.add(_mark(resistance=None))
    with pytest.raises(IntegrityError):
        session.commit()


def test_inverted_rails_rejected(session):
    session.add(_mark(resistance=10.15, support=12.40))
    with pytest.raises(IntegrityError):
        session.commit()


def test_inverted_span_rejected(session):
    session.add(_mark(box_start_date="2026-04-16", box_end_date="2025-12-12"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_event_constraints_bite(session):
    mark = _mark()
    mark.events.append(CalibrationMarkEvent(
        event_type="breakout", start_date="2026-02-10", end_date="2026-03-20"))
    session.add(mark)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    mark = _mark()
    mark.events.append(CalibrationMarkEvent(
        event_type="lps", start_date="2026-04-15", end_date="2026-04-09"))
    session.add(mark)
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_a_mark_removes_its_events(session):
    mark = _mark()
    mark.events.append(CalibrationMarkEvent(
        event_type="spring_test", start_date="2026-03-04", end_date="2026-03-06"))
    session.add(mark)
    session.commit()
    session.delete(mark)  # hard delete — no soft-delete flags in this table
    session.commit()
    assert session.query(CalibrationMarkEvent).count() == 0


# ── Trigger CHECKs (fresh-DB defence-in-depth; live DB enforces via validity) ──


def test_trigger_round_trips_on_a_box(session):
    session.add(_mark(trigger_date="2026-04-16", trigger_price=12.55))
    session.commit()
    got = session.query(CalibrationMark).one()
    assert (got.trigger_date, got.trigger_price) == ("2026-04-16", 12.55)


def test_a_box_without_a_trigger_stores_null(session):
    session.add(_mark())
    session.commit()
    got = session.query(CalibrationMark).one()
    assert got.trigger_date is None and got.trigger_price is None


def test_trigger_date_and_price_must_be_paired(session):
    session.add(_mark(trigger_date="2026-04-16"))  # price missing
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.add(_mark(trigger_price=12.55))  # date missing
    with pytest.raises(IntegrityError):
        session.commit()


def test_trigger_only_allowed_on_a_box(session):
    session.add(_mark(verdict="engine_wrong", trigger_date="2026-04-16",
                      trigger_price=12.55))
    with pytest.raises(IntegrityError):
        session.commit()


def test_trigger_may_precede_as_of_at_the_ddl_level(session):
    # Relaxed 2026-07-22: the as_of-floor CHECK is gone — the buy may precede the
    # snapshot. "After the last LPS bar" is enforced in marks_validity (it needs
    # the event rows a row-local CHECK can't see), so the DB accepts this row.
    session.add(_mark(trigger_date="2026-04-10", trigger_price=12.55))  # < as_of
    session.commit()
    assert session.query(CalibrationMark).one().trigger_date == "2026-04-10"


def test_trigger_price_must_be_positive(session):
    session.add(_mark(trigger_date="2026-04-16", trigger_price=0.0))
    with pytest.raises(IntegrityError):
        session.commit()
