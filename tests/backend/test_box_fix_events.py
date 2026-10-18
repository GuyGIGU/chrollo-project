"""His events on a fixed box (Sat 18/10/2026: *"lets widen it by letting me put events (spring, upthrust, sos,
lps/former lps, span, mini consolidation.) and add an indicator that this box was edited/fixed"*): the events
round-trip beside the fix through the calibration domain, a second list is his latest word, the fix's summary
sentence is resolved by the backend (EC-28), and the judgment is pure. Real handlers against a throwaway
in-memory SQLite, as tests/backend/test_box_fixes.py does."""
import datetime as dt
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

import models  # noqa: E402
from models import BoxFix, BoxFixEvent, CalibrationMarkEvent  # noqa: E402
from domains.calibration import box_fixes  # noqa: E402
from domains.calibration.router import (  # noqa: E402
    BoxFixEventIn, BoxFixIn, delete_box_fix, list_box_fixes, require_same_app, router, save_box_fix,
    save_box_fix_events)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", lambda con, _: con.execute("PRAGMA foreign_keys=ON"))
    models.Base.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


def _aapl_fix(**over):
    """His AAPL (Fri 17/10/2026): the climax 345.34 of Tue 22/09, the reaction low 334.30 of Thu 24/09."""
    fields = dict(ticker="AAPL", scan_day="2026-10-16", resistance=345.34, r_day="2026-09-22", support=334.30,
                  s_day="2026-09-24", reader_resistance=345.34, reader_r_day="2026-09-22", reader_support=334.30,
                  reader_s_day="2026-09-24", reader_opened_day="2026-09-22", ruleset="two-eyes-0.9.2-test")
    fields.update(over)
    return BoxFixIn(**fields)


def _aapl_events():
    """His AAPL swings: the spring's tip Thu 01/10 at 325.81, THE SOS from Mon 12/10 to Tue 13/10 topping at 348.15,
    the LPS the two days after, and a span he names himself."""
    return [BoxFixEventIn(kind="spring", first_day="2026-10-01", price=325.81),
            BoxFixEventIn(kind="SOS ", first_day="2026-10-13", last_day="2026-10-12", price=348.15),
            BoxFixEventIn(kind="lps", first_day="2026-10-14", last_day="2026-10-16", price=340.46),
            BoxFixEventIn(kind="span", first_day="2026-09-25", last_day="2026-09-30", label="  the dull middle ")]


def test_events_round_trip_beside_the_fix_and_the_summary_is_resolved_by_the_backend(db):
    fix = save_box_fix(_aapl_fix(), db)
    assert fix.events == [] and fix.summary.startswith("fixed ") and fix.summary.endswith(": the box as the reader drew it")
    saved = save_box_fix_events(fix.id, _aapl_events(), db)
    kinds = [(e.kind, e.first_day, e.last_day, e.price, e.label) for e in saved.events]
    assert kinds == [("span", "2026-09-25", "2026-09-30", None, "the dull middle"),
                     ("spring", "2026-10-01", "2026-10-01", 325.81, None),
                     ("sos", "2026-10-12", "2026-10-13", 348.15, None),
                     ("lps", "2026-10-14", "2026-10-16", 340.46, None)], "normalized: kinds lower, days ordered, one-day event closed"
    today = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y")
    assert saved.summary == f'fixed {today}: 4 events: span "the dull middle", spring, SOS, LPS'
    assert saved.revision == 1, "events never bump the fix's revision: his lines did not move"
    (listed,) = list_box_fixes(ticker="aapl", db=db)
    assert len(listed.events) == 4 and listed.summary == saved.summary
    # A second list is his latest word on that chart: it replaces, never adds.
    again = save_box_fix_events(fix.id, [BoxFixEventIn(kind="former_lps", first_day="2026-09-28", last_day="2026-09-29")], db)
    assert [e.kind for e in again.events] == ["former_lps"]
    assert again.summary == f"fixed {today}: 1 event: former LPS"
    assert db.query(BoxFixEvent).count() == 1
    assert db.query(CalibrationMarkEvent).count() == 0, "a fix's event is never a calibration mark's event"
    # The fix gone, its events go with it.
    delete_box_fix(fix.id, db)
    assert db.query(BoxFixEvent).count() == 0


def test_moved_rails_and_events_both_name_themselves_in_the_summary(db):
    fix = save_box_fix(_aapl_fix(support=333.05, s_day="2026-09-21"), db)
    assert fix.summary.endswith(": rails")
    with_events = save_box_fix_events(fix.id, [BoxFixEventIn(kind="mini", first_day="2026-10-05", last_day="2026-10-09",
                                                             band_high=339.0, band_low=342.5)], db)
    assert with_events.summary.endswith(": rails + 1 event: mini")
    assert (with_events.events[0].band_high, with_events.events[0].band_low) == (342.5, 339.0), "the band is ordered"


def test_events_that_are_no_events_are_refused_with_plain_words(db):
    fix = save_box_fix(_aapl_fix(), db)
    for events, words in (([BoxFixEventIn(kind="creek", first_day="2026-10-01")], "event 1: 'creek' is not one of"),
                          ([BoxFixEventIn(kind="lps", first_day="2026-10-14", last_day="2026-10-19")],
                           "event 1: last_day must be at or before the scan day"),
                          ([BoxFixEventIn(kind="spring", first_day="01/10/2026")], "event 1: first_day must be an ISO day"),
                          ([BoxFixEventIn(kind="mini", first_day="2026-10-05", last_day="2026-10-09", band_high=340.0)],
                           "event 1: a mini needs its two lines, the higher over the lower"),
                          ([BoxFixEventIn(kind="spring", first_day="2026-10-01", price=0.0)],
                           "event 1: price must be a price over zero")):
        with pytest.raises(HTTPException) as refused:
            save_box_fix_events(fix.id, events, db)
        assert refused.value.status_code == 422, events
        assert any(p.startswith(words) for p in refused.value.detail["problems"]), (words, refused.value.detail)
    assert db.query(BoxFixEvent).count() == 0
    with pytest.raises(HTTPException) as gone:
        save_box_fix_events(fix.id + 99, [], db)
    assert gone.value.status_code == 404


def test_the_event_write_is_guarded_by_the_same_app_header():
    guarded = {r.path for r in router.routes if "box-fixes" in r.path
               and any(d.dependency is require_same_app for d in r.dependencies)}
    assert "/calibration/box-fixes/{fix_id}/events" in guarded


def test_the_judgment_is_pure():
    events = box_fixes.normalize_events([{"kind": " Spring", "first_day": "2026-10-01", "last_day": None, "label": ""}])
    assert events == [{"kind": "spring", "first_day": "2026-10-01", "last_day": "2026-10-01", "price": None,
                       "band_high": None, "band_low": None, "label": None}]
    assert box_fixes.event_problems(events, "2026-10-16") == []
    assert box_fixes.event_problems(events, "2026-09-30") == ["event 1: last_day must be at or before the scan day"]
    fix = {"resistance": 10.0, "support": 9.0, "reader_resistance": 10.0, "reader_support": 9.0,
           "updated_at": dt.datetime(2026, 10, 18, 20, 5)}
    assert box_fixes.summary(fix, []) == "fixed 18/10/2026: the box as the reader drew it"
    assert box_fixes.summary({**fix, "reader_support": None}, []) == "fixed 18/10/2026: rails"
    assert box_fixes.summary({**fix, "updated_at": "2026-10-18T20:05:00"}, events) == "fixed 18/10/2026: 1 event: spring"
    assert box_fixes.EVENT_KINDS == ("spring", "upthrust", "sos", "lps", "former_lps", "span", "mini")
