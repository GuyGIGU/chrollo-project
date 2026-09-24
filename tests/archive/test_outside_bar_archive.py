"""The outside-bar vocabulary's archive family (engine-eyes Task 1).

EC-19 (closed-set columns get the universe_type treatment): the model CHECK
on ``eq_terminal_run_form`` refuses an illegal label on a fresh database,
and NULL / every legal value lands. EC-22 (every legal value has a producing
path): each value of ``TERMINAL_RUN_FORMS`` is minted by the REAL producer
(``measure_gate_margins`` on a hand frame), driven through the seed mapper's
real re-keying, and the live writer's hand mapping is pinned at source level
(the seed/live agreement itself is the column-parity AST guard's job).

Hermetic: in-memory SQLite via the ORM's own metadata — no live DB, no scan.
"""
import os
import sys

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp", "backend"))

from archive_models import Base, SetupArchive  # noqa: E402
# The ONE declarations (EC-33) — imported, never re-typed.
from engine_alpha.structure.box_gates import TERMINAL_RUN_FORMS  # noqa: E402
from engine_alpha.structure.metrics import (  # noqa: E402
    OUTSIDE_BAR_MEASURES,
    measure_gate_margins,
)

ARCHIVE_COLUMNS = tuple(f"eq_{key}" for key in OUTSIDE_BAR_MEASURES) + ("eq_traversals_per_20d",)

# Hand frames (R 110 / S 100 / ATR 1) whose right edge mints each label.
_IN = {"High": 106.0, "Low": 104.0, "Close": 105.0}
_PRODUCERS = {
    "inside": [_IN, _IN, _IN],
    "rest_above_r": [_IN, {"High": 111.5, "Low": 110.2, "Close": 111.2}],
    "hold_below_s": [_IN, {"High": 99.0, "Low": 98.0, "Close": 98.5}],
    "poke_close_back": [_IN, {"High": 111.5, "Low": 104.0, "Close": 110.0}],
    "straddle_close_out": [_IN, {"High": 111.5, "Low": 109.0, "Close": 111.2}],
}


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _row(**overrides):
    values = dict(ticker="TEST", scan_date="2026-09-05", setup_type="LPS",
                  score=1.0, tier="B", source="screener")
    values.update(overrides)
    return SetupArchive(**values)


def test_the_real_producer_mints_every_terminal_form():
    assert set(_PRODUCERS) == set(TERMINAL_RUN_FORMS)
    for label, rows in _PRODUCERS.items():
        gm = measure_gate_margins(pd.DataFrame(rows), 110.0, 100.0, 1.0)
        assert gm["terminal_run_form"] == label


def test_every_terminal_form_and_null_land_on_a_fresh_db():
    session = _session()
    for i, value in enumerate((*TERMINAL_RUN_FORMS, None)):
        session.add(_row(ticker=f"T{i}", eq_terminal_run_form=value,
                         eq_terminal_run_bars=(0 if value in ("inside", None) else 1)))
    session.commit()
    got = {r.eq_terminal_run_form for r in session.query(SetupArchive).all()}
    assert got == {*TERMINAL_RUN_FORMS, None}


def test_an_illegal_terminal_form_cannot_land_on_a_fresh_db():
    session = _session()
    # the resolution words are a DIFFERENT closed set — never a form label
    session.add(_row(eq_terminal_run_form="right_edge"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_the_family_flows_from_a_result_dict_to_archived_columns():
    """Behavioral leg: a fired result's underscore keys are driven through
    the seed mapper's real re-keying and read back from a committed row."""
    from core.archive.result_adapter import seed_row_from_result

    gm = measure_gate_margins(pd.DataFrame(_PRODUCERS["rest_above_r"]),
                              110.0, 100.0, 1.0)
    result = {f"_eq_{key}": gm[key] for key in OUTSIDE_BAR_MEASURES}
    result["_eq_traversals_per_20d"] = 0.5
    mapped = seed_row_from_result(result)
    session = _session()
    session.add(_row(**{col: mapped[col] for col in ARCHIVE_COLUMNS}))
    session.commit()
    back = session.query(SetupArchive).one()
    assert back.eq_terminal_run_form == "rest_above_r"
    assert back.eq_terminal_run_bars == 1
    assert back.eq_rest_above_r_frac == pytest.approx(0.5)
    assert back.eq_hold_below_s_frac == 0.0
    assert back.eq_traversals_per_20d == pytest.approx(0.5)


def test_the_live_writer_source_carries_the_hand_mapping():
    import inspect
    import re
    from core.archive import writer

    src = re.sub(r"\s+", "", inspect.getsource(writer))
    for column in ARCHIVE_COLUMNS:
        assert f'{column}=row.get("_{column}")' in src, column


def test_the_columns_are_model_only_registrations():
    """AP-7: the eq_* hand lists must NOT grow for a new family — the boot
    pass and the writer's second pass derive the ALTERs from the table."""
    from core.archive import writer

    assert not set(ARCHIVE_COLUMNS) & set(writer._NEW_COLUMNS)
    assert set(ARCHIVE_COLUMNS) <= set(SetupArchive.__table__.columns.keys())
