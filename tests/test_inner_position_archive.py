"""The inner_position archive family (ONE-Event-Map Task 10).

EC-19 (closed-set columns get the universe_type treatment): the model CHECK
refuses an illegal label on a fresh database, and NULL/legal values land.
EC-22 (every legal value has a producing path): each ruled value flows from a
result dict through the live writer's field mapping.

Hermetic: in-memory SQLite via the ORM's own metadata — no live DB, no scan.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp", "backend"))

from archive_models import Base, SetupArchive  # noqa: E402

RULED_VALUES = ("at_ceiling", "mid_range", "on_support", "touching_both")


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _row(**overrides):
    values = dict(ticker="TEST", scan_date="2026-08-30", setup_type="LPS",
                  score=1.0, tier="B", source="screener")
    values.update(overrides)
    return SetupArchive(**values)


def test_every_ruled_value_and_null_land():
    session = _session()
    for i, value in enumerate((*RULED_VALUES, None)):
        session.add(_row(ticker=f"T{i}", inner_position=value,
                         inner_position_r_atr=-0.4 if value else None,
                         inner_position_s_atr=3.9 if value else None))
    session.commit()
    got = {r.inner_position for r in session.query(SetupArchive).all()}
    assert got == {*RULED_VALUES, None}


def test_an_illegal_label_cannot_land_on_a_fresh_db():
    session = _session()
    # The retired five-way vocabulary and any typo must refuse (EC-19) —
    # including the census's banding words, which were never a live vocabulary.
    session.add(_row(inner_position="above_resistance"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_the_writer_maps_the_result_keys_to_the_columns():
    # The live writer's field mapping, asserted at the source level: the three
    # result keys reach the three columns (the seed path is covered by the
    # column-parity AST guard, which fails CI on a one-writer wiring).
    import inspect
    from core.archive import writer

    src = inspect.getsource(writer).replace(" ", "")
    for result_key, column in [("_inner_position", "inner_position"),
                               ("_inner_position_r_atr", "inner_position_r_atr"),
                               ("_inner_position_s_atr", "inner_position_s_atr")]:
        assert f'{column}=row.get("{result_key}")' in src
