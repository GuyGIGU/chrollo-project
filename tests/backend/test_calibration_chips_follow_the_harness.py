"""The workbench chips grade a mark exactly as the harness CLI does.

The ledger's Engine chips exist to agree with
``python -m tools.calibration.calibration_harness``, so they must call the same
grading code on the same frozen frame. The router tests inject a fake grader;
these run the real engine end to end on synthetic frozen frames and compare each
chip with the harness's own grade of the same mark. A chip whose import or call
breaks degrades to an 'error' chip instead of raising (EC-6), so only an
end-to-end comparison like this one sees it.

Two marks cover both chip paths: SYNA is read (a box the engine surfaces and
fires on, at other rails), SYNB is not (no read, and the fired walk misses).
"""
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from _paths import BACKEND_DIR, REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from models import CalibrationMark  # noqa: E402
import domains.calibration.agreement as agreement_chip  # noqa: E402
import domains.calibration.fired as fired_chip  # noqa: E402
from domains.calibration.router import calibration_engine_read  # noqa: E402
from engine_alpha.election_identity import DEFAULT_RAIL_TOL_BOX_FRAC  # noqa: E402
from tools.calibration import agreement  # noqa: E402
from tools.calibration import calibration_harness as harness  # noqa: E402

AS_OF = "2026-04-06"


def _synthetic_frame(seed):
    """A seeded two-year uptrend into an 80-session sideways base, cut at AS_OF."""
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2024-01-02", "2026-04-15", freq="B")
    box_start = len(idx) - 80
    level, closes = 20.0, []
    for i in range(len(idx)):
        if i < box_start:
            level *= 1.0035
            closes.append(level * (1 + rng.uniform(-0.01, 0.01)))
        else:
            k = i - box_start
            closes.append(level * (1 + 0.0004 * k + 0.03 * np.sin(k / 5.0 + 1.0)
                                   + rng.uniform(-0.008, 0.008)))
    closes = np.array(closes)
    high = closes * (1 + rng.uniform(0.004, 0.015, len(idx)))
    low = closes * (1 - rng.uniform(0.004, 0.015, len(idx)))
    frame = pd.DataFrame({"Open": (high + low) / 2, "High": high, "Low": low,
                          "Close": closes, "Volume": rng.uniform(8e5, 1.2e6, len(idx))},
                         index=idx)
    return frame.loc[:AS_OF], idx[box_start]


@pytest.fixture()
def marks(tmp_path, monkeypatch):
    """SYNA and SYNB frozen in a tmp store (both frame_store instances) and
    saved as box marks drawn around each base; the chip caches start cold."""
    import frame_store
    import webapp.backend.frame_store as wb_frame_store
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(wb_frame_store, "FRAMES_DIR", str(tmp_path))
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    now = datetime(2026, 4, 6, tzinfo=timezone.utc)
    for ticker, seed in (("SYNA", 3), ("SYNB", 1)):
        frozen, box_start = _synthetic_frame(seed)
        digest, _ = frame_store.freeze_frame(ticker, AS_OF, frozen)
        box = frozen.loc[box_start:]
        session.add(CalibrationMark(
            ticker=ticker, as_of_date=AS_OF, label="", verdict="box",
            resistance=round(float(box["High"].max()), 2),
            support=round(float(box["Low"].min()), 2),
            box_start_date=box_start.strftime("%Y-%m-%d"), box_end_date=AS_OF,
            data_regime="as_traded", engine_config_version="cfg",
            anchor_close=float(frozen["Close"].iloc[-1]), frame_digest=digest,
            revision=1, created_at=now, updated_at=now))
    session.commit()
    agreement_chip.reset_agreement_cache()
    fired_chip.reset_fired_cache()
    yield {m.ticker: m for m in session.query(CalibrationMark).all()}
    session.close()
    engine.dispose()


def _harness_grade(mark):
    return harness.grade_one(harness._mark_dict(mark), [{}])[0]


def _harness_fired(mark):
    return harness.fired_one(harness._mark_dict(mark), [{}])[0]


def test_the_fixture_reads_both_ways(marks):
    # Guard the guard: if the engine stops reading these frames this way, the
    # parity checks below compare two empty answers. Re-pick the seeds then.
    assert _harness_grade(marks["SYNA"])["outcome"] in ("match", "disagree")
    assert _harness_fired(marks["SYNA"])["fired"] is True
    assert _harness_grade(marks["SYNB"])["outcome"] == "engine_no_read"
    assert _harness_fired(marks["SYNB"])["fired"] is False


def test_the_election_chip_is_the_harness_grade(marks):
    chips = agreement_chip.agreement_for_marks(list(marks.values()))
    for mark in marks.values():
        expected = agreement_chip._chip_from_fragment(_harness_grade(mark))
        assert chips[mark.id] == {**expected, "revision": 1, "stale": True}, mark.ticker


def test_the_fired_chip_is_the_harness_fired_walk(marks):
    out = fired_chip.fired_for_marks(list(marks.values()), background=False)
    assert out["computing"] is False
    for mark in marks.values():
        md = harness._mark_dict(mark)
        expected = fired_chip._chip_from_fired(md, _harness_fired(mark))
        assert out["marks"][mark.id] == {**expected, "revision": 1, "stale": True}, mark.ticker
    assert out["marks"][marks["SYNB"].id]["stage"], "the missed chip lost its reject stage"


def test_the_overlay_reads_the_session_the_harness_grades(marks):
    for mark in marks.values():
        graded = _harness_grade(mark)
        overlay = calibration_engine_read(ticker=mark.ticker, as_of=AS_OF,
                                          frame_digest=mark.frame_digest)
        assert overlay["elected"] is (graded["outcome"] in ("match", "disagree")), mark.ticker
        assert overlay["eval_session"] == graded["eval_session"], mark.ticker
        assert overlay["snapped"] == graded["snapped"], mark.ticker


def test_the_chip_caches_key_on_the_policy_the_harness_stamps():
    # A chip is cached under these signatures; the harness stamps the same
    # values into every report, so a policy change rotates both together.
    assert agreement_chip._tol_sig() == (
        f"rail{DEFAULT_RAIL_TOL_BOX_FRAC}:span{agreement.DEFAULT_SPAN_OVERLAP_MIN}"
        f":snap{harness.SNAP_BACK_SESSIONS}")
    assert fired_chip._fired_sig() == (
        f"v{harness.HARNESS_POLICY_VERSION}:win{harness.FIRED_WINDOW_SESSIONS}"
        f":rail{DEFAULT_RAIL_TOL_BOX_FRAC}")
