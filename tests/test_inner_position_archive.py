"""The inner_position archive family (ONE-Event-Map Task 10).

EC-19 (closed-set columns get the universe_type treatment): the model CHECK
refuses an illegal label on a fresh database, and NULL/legal values land.
EC-22 (every legal value has a producing path): each ruled value lands through
the ORM, the seed mapper is driven behaviorally, and the live writer's hand
mapping is pinned at source level (whitespace-normalized; the seed/live
agreement itself is the column-parity AST guard's job).

Hermetic: in-memory SQLite via the ORM's own metadata — no live DB, no scan.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp", "backend"))

from archive_models import Base, SetupArchive  # noqa: E402
# The ONE declaration of the ruled closed set (EC-33) — imported, never
# re-typed, so a vocabulary ruling re-scores this battery automatically.
from engine_alpha.structure.box.inner_box import RULED_POSITION_VALUES as RULED_VALUES  # noqa: E402


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


def test_the_family_flows_from_a_result_dict_to_archived_columns():
    """The behavioral leg (council review 2026-08-30, Beck): a result dict
    carrying the three underscore keys is driven through the seed mapper's
    real re-keying and the columns are read back from a committed row — the
    mapping EXECUTES, not merely appears in source. The live writer's hand
    mapping is tied to this path by the column-parity AST guard."""
    from core.archive.result_adapter import seed_row_from_result

    result = {"_inner_position": "touching_both",
              "_inner_position_r_atr": -0.22,
              "_inner_position_s_atr": 0.40}
    mapped = seed_row_from_result(result)
    assert mapped["inner_position"] in RULED_VALUES

    session = _session()
    session.add(_row(inner_position=mapped["inner_position"],
                     inner_position_r_atr=mapped["inner_position_r_atr"],
                     inner_position_s_atr=mapped["inner_position_s_atr"]))
    session.commit()
    back = session.query(SetupArchive).one()
    assert back.inner_position == "touching_both"
    assert back.inner_position_r_atr == pytest.approx(-0.22)
    assert back.inner_position_s_atr == pytest.approx(0.40)


def test_the_live_writer_source_carries_the_hand_mapping():
    # Source-level pin on the live writer's hand-written values dict, made
    # whitespace-robust (ALL whitespace stripped, so an innocent reflow never
    # false-alarms). Behavior lives in the test above; seed/live agreement is
    # the column-parity AST guard's job.
    import inspect
    import re
    from core.archive import writer

    src = re.sub(r"\s+", "", inspect.getsource(writer))
    for result_key, column in [("_inner_position", "inner_position"),
                               ("_inner_position_r_atr", "inner_position_r_atr"),
                               ("_inner_position_s_atr", "inner_position_s_atr")]:
        assert f'{column}=row.get("{result_key}")' in src
