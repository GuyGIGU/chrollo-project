"""The workbench's Engine chip grades a mark exactly as the harness does.

The ledger's Engine chip exists to agree with
``python -m tools.calibration.calibration_harness --fired``, so it must call the
same fired walk (``domains.calibration.grading.fired_one``, the production
grading the harness imports) on the same frozen frame. The router tests inject a
fake grader; this runs the real reader end to end on two of his sealed frames and
compares each chip with the fired walk's own fragment. A chip whose import or
call breaks degrades to an 'error' chip instead of raising (EC-6), so only an
end-to-end comparison like this one sees it.

Two marks cover both chip paths: JAZZ to Tue 24/02/2026 fires on his day; VTMX to
Fri 02/10/2026 fires on no day of its fair window, so the missed chip carries the
reader's own words for his day.
"""
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from _paths import BACKEND_DIR, REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from models import CalibrationMark  # noqa: E402
import domains.calibration.fired as fired_chip  # noqa: E402
from domains.calibration import grading  # noqa: E402
from core.calibration.agreement import DEFAULT_RAIL_TOL_BOX_FRAC  # noqa: E402

# (ticker, as_of, his resistance, his support, his box start)
FIRES = ("JAZZ", "2026-02-24", 171.51, 164.44, "2025-12-04")
MISSES = ("VTMX", "2026-10-02", 13.05, 11.89, "2026-07-27")


@pytest.fixture()
def marks(tmp_path, monkeypatch):
    """Both sealed frames frozen in a tmp store (both frame_store instances) and
    saved as box marks; the chip cache starts cold."""
    import frame_store
    import webapp.backend.frame_store as wb_frame_store
    from core.calibration.replay import load_sealed_fixture

    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(wb_frame_store, "FRAMES_DIR", str(tmp_path))
    frames, _ = load_sealed_fixture()
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    now = datetime(2026, 10, 31, tzinfo=timezone.utc)
    for ticker, as_of, resistance, support, box_start in (FIRES, MISSES):
        frozen = frames[f"{ticker}:{as_of}"]
        digest, _ = frame_store.freeze_frame(ticker, as_of, frozen)
        session.add(CalibrationMark(
            ticker=ticker, as_of_date=as_of, label="", verdict="box",
            resistance=resistance, support=support,
            box_start_date=box_start, box_end_date=as_of,
            data_regime="as_traded", engine_config_version="cfg",
            anchor_close=float(frozen["Close"].loc[:as_of].iloc[-1]), frame_digest=digest,
            revision=1, created_at=now, updated_at=now))
    session.commit()
    fired_chip.reset_fired_cache()
    yield {m.ticker: m for m in session.query(CalibrationMark).all()}
    session.close()
    engine.dispose()


def _walk(mark):
    return grading.fired_one(grading._mark_dict(mark), [{}])[0]


def test_the_fixture_reads_both_ways(marks):
    # Guard the guard: if the reader stops reading these frames this way, the
    # parity check below compares two answers of one kind. Re-pick the frames then.
    assert _walk(marks["JAZZ"])["fired"] is True
    assert _walk(marks["VTMX"])["fired"] is False


def test_the_fired_chip_is_the_fired_walk(marks):
    out = fired_chip.fired_for_marks(list(marks.values()), background=False)
    assert out["computing"] is False
    for mark in marks.values():
        md = grading._mark_dict(mark)
        expected = fired_chip._chip_from_fired(md, _walk(mark))
        assert out["marks"][mark.id] == {**expected, "revision": 1, "stale": True}, mark.ticker
    fired = out["marks"][marks["JAZZ"].id]
    assert fired["state"] == "ok" and fired["kind"] == "fired" and fired["fire_date"] <= FIRES[1]
    missed = out["marks"][marks["VTMX"].id]
    assert missed["state"] == "miss" and missed["kind"] == "missed" and missed["stage"]
    assert missed["detail"].startswith("the new reader"), "the missed chip lost the reader's own words"


def test_the_chip_cache_keys_on_the_policy_the_harness_stamps():
    # A chip is cached under this signature; the harness stamps the same values
    # into every report, so a policy change rotates both together.
    assert fired_chip._fired_sig() == (
        f"v{grading.HARNESS_POLICY_VERSION}:win{grading.FIRED_WINDOW_SESSIONS}"
        f":rail{DEFAULT_RAIL_TOL_BOX_FRAC}")
