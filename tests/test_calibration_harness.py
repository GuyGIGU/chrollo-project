"""Agreement-harness bite proofs (Task 9) — a scorer nobody has seen fail
proves nothing. Forced-never-match must report zero agreement, forced-always
must report full; a malformed row aborts the batch NAMING the offender; and a
full grading pass leaves the marks byte-identical (the path of least
resistance to better numbers must never be 'correct' the ground truth)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from models import CalibrationMark  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import webapp.backend.frame_store as frame_store  # noqa: E402
from tools import agreement, replay  # noqa: E402
from tools.calibration_harness import (  # noqa: E402
    _refuse_sealed_output,
    grade_one,
    load_marks,
    marks_fingerprint,
    parse_variant,
)


def _loader(frame):
    """A fake frame_store.load_frame honoring its digest-resolved signature."""
    return lambda ticker, as_of, digest=None: frame


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


def _frozen_frame():
    idx = pd.date_range("2026-01-05", "2026-04-15", freq="B")
    closes = [11.0] * len(idx)
    return pd.DataFrame({"Open": closes, "High": [c + 1 for c in closes],
                         "Low": [c - 1 for c in closes], "Close": closes,
                         "Volume": [1e6] * len(idx)}, index=idx)


_FROZEN = _frozen_frame()
_DIGEST = frame_store.ohlcv_digest(_FROZEN)


def _add_mark(session, **overrides):
    now = datetime(2026, 4, 15, tzinfo=timezone.utc)
    fields = dict(ticker="BODI", as_of_date="2026-04-15", label="",
                  verdict="box", resistance=12.0, support=10.0,
                  box_start_date="2026-01-05", box_end_date="2026-04-15",
                  data_regime="as_traded", engine_config_version="test",
                  anchor_close=11.0, frame_digest=_DIGEST,
                  created_at=now, updated_at=now)
    fields.update(overrides)
    session.add(CalibrationMark(**fields))
    session.commit()


def _election_returning(structure, seen_snaps=None):
    """A fake snapped election: every variant sees ``structure`` on the
    as-of session, never snapped. ``seen_snaps`` records the snap_back the
    harness asked for (the per-verdict policy pin)."""
    def _run(frozen, as_of, variants, snap_back=5):
        if seen_snaps is not None:
            seen_snaps.append(snap_back)
        df = frozen.loc[:pd.Timestamp(as_of)]
        return (df, 1.0, [structure for _ in variants]), df.index[-1], 0
    return _run


class _Read:
    """Engine-read stand-in shaped like a Structure (R/S/box.start_bar)."""
    def __init__(self, R, S, start_bar):
        self.R, self.S = R, S
        self.box = type("B", (), {"start_bar": start_bar})()


def test_bite_forced_never_match(session):
    _add_mark(session)
    _add_mark(session, as_of_date="2026-04-14", verdict="no_structure",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)
    marks = load_marks(session)
    rows = [grade_one(m, [{}], frame_loader=_loader(_FROZEN),
                      election=_election_returning(None))[0] for m in marks]
    t = agreement.tally(rows)
    assert t["counts"]["match"] == 0
    assert t["counts"]["engine_no_read"] == 1      # the box mark: no read
    assert t["counts"]["negative_upheld"] == 1     # the negative: upheld


def test_bite_forced_always_match(session):
    _add_mark(session)
    marks = load_marks(session)
    exact = _Read(R=12.0, S=10.0, start_bar=0)  # bar 0 = 2026-01-05 = drawn start
    rows = [grade_one(m, [{}], frame_loader=_loader(_FROZEN),
                      election=_election_returning(exact))[0] for m in marks]
    assert agreement.tally(rows)["match_over_scored"] == 1.0


def test_negatives_grade_at_the_asserted_session_only(session):
    # The snap-back walk is a BOX policy; hunting prior sessions to convict a
    # negative would bias upheld_over_negatives (Council finding 6).
    _add_mark(session, as_of_date="2026-04-14", verdict="no_structure",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)
    _add_mark(session)  # the box mark, as-of 04-15
    seen = []
    for m in load_marks(session):  # ordered by as_of: negative first
        grade_one(m, [{}], frame_loader=_loader(_FROZEN),
                  election=_election_returning(None, seen_snaps=seen))
    assert seen == [0, replay.SNAP_BACK_SESSIONS]


def test_unresolved_digest_grades_basis_mismatch(session, tmp_path, monkeypatch):
    # Through the REAL digest-resolved loader: a mark whose digest matches no
    # frozen rendering is named, never replayed on other bars.
    import frame_store as bare_frame_store
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(bare_frame_store, "FRAMES_DIR", str(tmp_path))
    frame_store.freeze_frame("BODI", "2026-04-15", _FROZEN)
    _add_mark(session, frame_digest="0" * 64)
    row = grade_one(load_marks(session)[0], [{}],
                    election=_election_returning(None))[0]
    assert row["outcome"] == "basis_mismatch"
    assert "no frozen frame matches" in row["detail"]
    # And the matching digest resolves fine through the same real loader.
    session.query(CalibrationMark).first().frame_digest = _DIGEST
    session.commit()
    row = grade_one(load_marks(session)[0], [{}],
                    election=_election_returning(None))[0]
    assert row["outcome"] == "engine_no_read"


def test_malformed_row_aborts_naming_the_offender(session):
    # Valid to the DDL but invalid to the shared judgment: span past as-of.
    _add_mark(session, box_end_date="2026-05-01", label="stale")
    with pytest.raises(ValueError) as err:
        load_marks(session)
    assert "BODI" in str(err.value) and "'stale'" in str(err.value)
    assert "after as_of_date" in str(err.value)


def test_full_grading_pass_is_read_only(session):
    # The pin covers EVERY mark column and the events rows (the fingerprint
    # canonicalizes the whole mark dict, order-free): the path of least
    # resistance to better numbers must never be to "correct" ground truth.
    _add_mark(session)
    _add_mark(session, as_of_date="2026-04-14", verdict="no_structure",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)
    before = marks_fingerprint(load_marks(session))
    for m in load_marks(session):
        grade_one(m, [{}, {"BAND_RAILS_ENABLED": True}],
                  frame_loader=_loader(_FROZEN),
                  election=_election_returning(None))
    session.expire_all()
    assert marks_fingerprint(load_marks(session)) == before


def test_json_output_refuses_the_sealed_corpus(tmp_path):
    import os
    sealed = os.path.join(str(ROOT), "docs", "marks", "report.json")
    with pytest.raises(ValueError) as err:
        _refuse_sealed_output(sealed)
    assert "sealed corpus" in str(err.value)
    _refuse_sealed_output(str(tmp_path / "report.json"))  # elsewhere: fine


def test_fingerprint_is_order_free_and_content_bound(session):
    _add_mark(session)
    _add_mark(session, ticker="KLAC", as_of_date="2025-09-11",
              box_start_date="2025-07-18", box_end_date="2025-09-11",
              resistance=95.0, support=87.74)
    a = marks_fingerprint(load_marks(session))
    b = marks_fingerprint(list(reversed(load_marks(session))))
    assert a == b
    session.query(CalibrationMark).filter_by(ticker="KLAC").first().resistance = 95.5
    session.commit()
    assert marks_fingerprint(load_marks(session)) != a


def test_parse_variant():
    assert parse_variant("BAND_RAILS_ENABLED=true") == {"BAND_RAILS_ENABLED": True}
    assert parse_variant("X=2.5") == {"X": 2.5}
    with pytest.raises(ValueError):
        parse_variant("JUSTAFLAG")
