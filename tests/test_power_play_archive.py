"""The Power-Play species archive family (program Task 7): closed-set
enforcement at all three layers (EC-19), one producing path per legal value
(EC-22), paired writes (EC-23), the flag-off leak check through the producer's
own extraction (EC-33), and the model-only registration route (AP-7)."""
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

# The backend dir holds the ORM model (the test_archive_row_assembly bootstrap).
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from engine_alpha.structure.power_play import (
    POWER_PLAY_COLUMN_SQL,
    PP_STATES,
    power_play_archive_values,
    power_play_fields,
)


def _get(fields):
    return lambda key: fields.get(key)


# ── EC-23: the fields builder pairs its facts in every branch ───────────────

def test_never_evaluated_is_the_empty_dict():
    assert power_play_fields(None, None) == {}


def test_state_without_clock_refuses():
    with pytest.raises(ValueError, match="one unit"):
        power_play_fields("admitted_dark", None)


def test_half_pairs_refuse():
    with pytest.raises(ValueError, match="numerator"):
        power_play_fields("admitted_dark", 10, shelf_bars=9)
    with pytest.raises(ValueError, match="land together"):
        power_play_fields("admitted_dark", 10, zone_coverage=1.3)


def test_unknown_state_refuses_naming_the_closed_set():
    with pytest.raises(ValueError, match="refused_clock/"):
        power_play_fields("watched", 10)


# ── EC-22: every legal value is producible end-to-end through the family ────

@pytest.mark.parametrize("state", PP_STATES)
def test_each_state_produces_through_fields_and_extraction(state):
    fields = power_play_fields(
        state, 10, climax_date="2026-07-17", ar_date="2026-07-24",
        pole_gain=1.119, shelf_bars=12, lower_third_bars=0,
        zone_coverage=1.31, zone_collided=1)
    out = power_play_archive_values(_get(fields), prefixed=True)
    assert out["pp_state"] == state
    assert out["pp_clock"] == 10
    assert out["pp_climax_date"] == "2026-07-17"
    assert out["pp_lower_third_bars"] == 0          # a measured zero survives
    assert out["pp_zone_collided"] == 1             # ... and says it collided


# ── EC-19: the write-time refusal at the single stamping point ──────────────

def test_extraction_refuses_an_illegal_state_on_every_writer_shape():
    for prefixed in (True, False):
        row = {("_" if prefixed else "") + "pp_state": "bogus"}
        with pytest.raises(ValueError, match="closed set"):
            power_play_archive_values(_get(row), prefixed=prefixed)


def test_fresh_db_check_constraint_refuses_an_illegal_state():
    from archive_models import Base, SetupArchive

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    def _row(**over):
        base = dict(ticker="MAN", scan_date="2026-08-13", setup_type="LPS",
                    tier="S", score=100.0)
        base.update(over)
        return SetupArchive(**base)

    # EVERY legal tuple value lands through the model CHECK — executable
    # parity between the hand-typed SQL and the PP_STATES tuple (2026-08-17
    # review, Leach): a widened tuple with a forgotten CHECK dies here at
    # add time instead of as a far-away fresh-DB IntegrityError.
    for i, state in enumerate(PP_STATES):
        session.add(_row(ticker=f"T{i}", pp_state=state, pp_clock=10))
    session.commit()
    session.add(_row(ticker="XXX", pp_state="bogus"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.close()


def test_extraction_refuses_half_pairs_on_every_writer_shape():
    # EC-23 enforced at the ONE layer every writer rides (2026-08-17 review,
    # Leach): the lane's fields builder guards the lane, but the seed and
    # manual shapes reach the extraction directly — a contradiction must die
    # there too, never land in the books of record.
    cases = [
        ({"pp_state": "refused_clock"}, "without pp_clock"),
        ({"pp_state": "refused_clock", "pp_clock": 10, "pp_shelf_bars": 9},
         "numerator"),
        ({"pp_state": "refused_clock", "pp_clock": 10,
          "pp_zone_coverage": 1.2}, "land together"),
    ]
    for row, match in cases:
        with pytest.raises(ValueError, match=match):
            power_play_archive_values(_get(row), prefixed=False)


# ── EC-33: the flag-off leak check through the producer's own extraction ────

def test_gated_off_row_extracts_all_none_for_every_family_column():
    for prefixed in (True, False):
        out = power_play_archive_values(_get({}), prefixed=prefixed)
        assert set(out) == set(POWER_PLAY_COLUMN_SQL)
        assert all(v is None for v in out.values())


# ── AP-7: model-only registration; anchor-family from birth ─────────────────

def test_columns_are_model_only_and_join_the_anchor_partition():
    from archive_models import SetupArchive
    from core.archive import writer as archive_writer
    from core.archive.analyze import PHASE_A_ANCHOR_FEATURES

    model_columns = set(SetupArchive.__table__.columns.keys())
    assert set(POWER_PLAY_COLUMN_SQL) <= model_columns
    assert not set(POWER_PLAY_COLUMN_SQL) & set(archive_writer._NEW_COLUMNS)
    assert {"pp_clock", "pp_pole_gain"} <= set(PHASE_A_ANCHOR_FEATURES)
