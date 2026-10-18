"""His "fix the box" (Fri 17/10/2026): a correction of the reader's box drawn on the lens round-trips through the
calibration domain, beside the pair the reader showed, and never touches a calibration mark. Real handlers against
a throwaway in-memory SQLite, as tests/backend/test_calibration_router.py does; the same-app write guard's wiring is
pinned by route inspection."""
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

import models  # noqa: E402
from models import BoxFix, CalibrationMark  # noqa: E402
from domains.calibration import box_fixes  # noqa: E402
from domains.calibration.router import (  # noqa: E402
    BoxFixIn, BoxFixOut, delete_box_fix, list_box_fixes, require_same_app, router, save_box_fix)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


def _aapl(**over):
    """His AAPL (Fri 17/10/2026): the climax 345.34 of Tue 22/09, the reaction low 334.30 of Thu 24/09, drawn over
    a reader that showed the same pair; the fix proves the round trip, not a disagreement."""
    fields = dict(ticker="aapl ", scan_day="2026-10-16", resistance=345.34, r_day="2026-09-22", support=334.30,
                  s_day="2026-09-24", reader_resistance=345.34, reader_r_day="2026-09-22", reader_support=334.30,
                  reader_s_day="2026-09-24", reader_opened_day="2026-09-22", ruleset="two-eyes-0.9.2-test",
                  note="  the box is right ")
    fields.update(over)
    return BoxFixIn(**fields)


def test_a_fix_round_trips_beside_the_readers_pair_and_a_second_save_is_his_latest_word(db):
    saved = BoxFixOut.model_validate(save_box_fix(_aapl(), db))
    assert (saved.ticker, saved.scan_day, saved.revision, saved.note) == ("AAPL", "2026-10-16", 1, "the box is right")
    assert (saved.resistance, saved.r_day, saved.support, saved.s_day) == (345.34, "2026-09-22", 334.30, "2026-09-24")
    assert (saved.reader_resistance, saved.reader_support, saved.reader_opened_day) == (345.34, 334.30, "2026-09-22")
    listed = list_box_fixes(ticker="aapl", db=db)
    assert [f.id for f in listed] == [saved.id]
    again = save_box_fix(_aapl(support=333.05, s_day="2026-09-21", note=None), db)
    assert (again.id, again.revision, again.support, again.s_day, again.note) == (saved.id, 2, 333.05, "2026-09-21", None)
    assert db.query(BoxFix).count() == 1, "one fix per chart and day"
    assert db.query(CalibrationMark).count() == 0, "a fix is never a mark"
    assert delete_box_fix(saved.id, db) == {"status": "deleted", "id": saved.id}
    assert list_box_fixes(ticker=None, db=db) == []
    with pytest.raises(HTTPException) as gone:
        delete_box_fix(saved.id, db)
    assert gone.value.status_code == 404


def test_a_fix_that_is_no_box_is_refused_with_plain_words(db):
    for over, words in ((dict(support=350.0), "resistance must sit over support"),
                        (dict(r_day="2026-10-19"), "r_day must be at or before the scan day"),
                        (dict(scan_day="16/10/2026"), "scan_day must be an ISO day"),
                        (dict(ticker="  "), "a fix needs a ticker"),
                        (dict(reader_opened_day="yesterday"), "reader_opened_day must be an ISO day or absent")):
        with pytest.raises(HTTPException) as refused:
            save_box_fix(_aapl(**over), db)
        assert refused.value.status_code == 422 and words in refused.value.detail["problems"], over
    assert db.query(BoxFix).count() == 0


def test_a_fix_without_a_reader_box_is_saved_with_the_readers_fields_empty(db):
    saved = save_box_fix(_aapl(reader_resistance=None, reader_r_day=None, reader_support=None, reader_s_day=None,
                               reader_opened_day=None), db)
    assert saved.reader_resistance is None and saved.reader_opened_day is None


def test_the_fix_writes_are_guarded_by_the_same_app_header():
    guarded = {r.path for r in router.routes if "box-fixes" in r.path
               and any(d.dependency is require_same_app for d in r.dependencies)}
    assert guarded == {"/calibration/box-fixes", "/calibration/box-fixes/{fix_id}", "/calibration/box-fixes/{fix_id}/events"}
    reads = [r for r in router.routes if r.path == "/calibration/box-fixes" and "GET" in r.methods]
    assert reads and not any(d.dependency is require_same_app for d in reads[0].dependencies)


def test_the_judgment_is_pure_and_normalizes_the_identity():
    data = box_fixes.normalize({"ticker": " ngl", "note": "", "scan_day": "2026-01-16", "resistance": 10.29,
                                "r_day": "2025-12-11", "support": 9.38, "s_day": "2025-12-15"})
    assert (data["ticker"], data["note"], data["ruleset"]) == ("NGL", None, "")
    assert box_fixes.problems(data) == []
    assert box_fixes.problems({**data, "support": 0.0, "resistance": 1.0}) == ["support must be a price over zero"]
