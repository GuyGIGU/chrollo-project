"""The sentence-token family through a REAL database (council review
2026-09-01, finding 10c).

Every other guard on this family is static analysis — splat names read out of
the writers' source (``test_archive_row_assembly``), model-column subsets
(``test_archive_column_parity``), producer shape (``test_event_vocabulary``).
None of them ever bound a value to SQLite. This is the leg that stands between
the operator and a failed archive write on flip night: the REAL producer chain
(``unify_events`` -> ``serialize_sentence`` -> ``sentence_archive_values``)
mints the cells, the row lands through the writers' own splat into a throwaway
in-memory database, and the cells are read back out and compared — the house
pattern the power-play and near-miss families already use.

The three-state law gets its SQL proof here too: the measured-empty zero and
the not-measured NULL must be distinguishable BY QUERY, which is the only
place that law is ever actually cashed.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT

# The backend dir holds the ORM model + the shared row mapper (the
# test_archive_row_assembly bootstrap).
_PROJECT_ROOT = str(REPO_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from engine_alpha.structure.events.event_vocabulary import (  # noqa: E402
    SENTENCE_COLUMN_SQL,
    sentence_archive_values,
    serialize_sentence,
    unify_events,
)

# Hand-written reader outputs (shapes from the readers' documented contracts,
# values literal) — the same fixtures the vocabulary tests use.
PUZZLE = [
    {"type": "test", "rail": "S", "zone_start": 2, "zone_end": 5,
     "anchor_bar": 3, "valley_bar": 3, "resolution": "held"},
    {"type": "rejection", "rail": "R", "zone_start": 8, "zone_end": 11,
     "anchor_bar": 9, "peak_bar": 9, "resolution": "held"},
]
LABELS = {"labels": [
    {"role": "test", "knowable_bar": 11, "in_progress": False,
     "election_dependent": False},
    {"role": "rejection", "knowable_bar": 15, "in_progress": False,
     "election_dependent": False},
], "n_labels": 2}
EPISODES = {"episodes": [
    {"rail": "S", "outcome": "completed", "start_bar": 1, "end_bar": 6,
     "posture": False, "knowable_bar": 9, "in_progress": False},
    {"rail": "R", "outcome": "failed", "start_bar": 19, "end_bar": 24,
     "posture": True, "knowable_bar": 26, "in_progress": False},
], "n_episodes": 2, "nan_bars": 0, "n_bars": 30}


def _measured_cells() -> dict:
    """The REAL producer chain, on the live caller's declared ruler (bar 0 =
    the box start, offset zero) — never hand-typed cell literals."""
    dates = pd.bdate_range("2026-01-05", periods=30)
    unified = unify_events(
        box_events=PUZZLE, role_labels=LABELS, episode_read=EPISODES,
        puzzle_operands={"R": 25.0, "S": 22.5, "atr": 0.6,
                         "box_start_in_window": 0},
        episode_operands={"R": 25.0, "S": 22.5, "atr": 0.6})
    return serialize_sentence(unified, dates)


def _db():
    """A throwaway in-memory archive — never the live DB."""
    from archive_models import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _add(session, ticker: str, cells: dict, *, prefixed: bool):
    """Land one row the way the REAL writers land it: the family's own
    extraction splatted into the model (EC-30 — the producer rides every
    writer; a raw model pass would skip the scrub and the coercions)."""
    from archive_models import SetupArchive

    result = {(("_" + k) if prefixed else k): v for k, v in cells.items()}
    row = SetupArchive(
        ticker=ticker, scan_date="2026-02-17", setup_type="LPS", tier="S",
        score=100.0,
        **sentence_archive_values(result.get, prefixed=prefixed))
    session.add(row)
    return row


# ── the measured state, minted and read back ────────────────────────────────

def test_measured_sentence_round_trips_through_a_real_database():
    cells = _measured_cells()
    minted = json.loads(cells["sentence_tokens"])
    assert len(minted) == 4 and cells["sentence_n_tokens"] == 4

    engine, session = _db()
    _add(session, "EGBN", cells, prefixed=True)
    session.commit()

    from archive_models import SetupArchive
    stored = session.query(SetupArchive).filter_by(ticker="EGBN").one()
    assert stored.sentence_tokens == cells["sentence_tokens"]
    assert json.loads(stored.sentence_tokens) == minted
    assert stored.sentence_n_tokens == 4
    assert stored.sentence_nan_bars == 0
    # The tape cell must survive as TEXT, not as a bound Python object: a
    # producer that ever returned the list itself would raise here, which is
    # the exact class that shipped a flag-on crash on the manual route once.
    assert isinstance(stored.sentence_tokens, str)
    for record in json.loads(stored.sentence_tokens):
        assert record["span"] is None or all(
            len(d) == 10 for d in record["span"])   # dates, never bar indexes
    session.close()
    engine.dispose()


def test_both_writer_shapes_store_identical_cells():
    # EC-30: the live writer reads ``_``-prefixed keys, the seed and manual
    # writers read the stripped ones — the SAME extraction, so the persisted
    # row must not depend on which writer wrote it.
    cells = _measured_cells()
    engine, session = _db()
    _add(session, "LIVE", cells, prefixed=True)
    _add(session, "SEED", cells, prefixed=False)
    session.commit()

    from archive_models import SetupArchive
    live = session.query(SetupArchive).filter_by(ticker="LIVE").one()
    seed = session.query(SetupArchive).filter_by(ticker="SEED").one()
    for col in SENTENCE_COLUMN_SQL:
        assert getattr(live, col) == getattr(seed, col), col
    session.close()
    engine.dispose()


def test_the_seed_row_mapper_carries_the_family_to_the_database():
    # The seed and manual routes assemble through the shared model-driven
    # mapper; drive it end-to-end so a family that falls out of the overrides
    # splat lands NULL here instead of on flip night.
    from archive_models import SetupArchive
    from domains.archive.queries import archive_row_from_result

    cells = _measured_cells()
    result = dict(cells)
    values = archive_row_from_result(result, overrides={
        "ticker": "PKE", "scan_date": "2026-02-17", "setup_type": "LPS",
        "tier": "S", "score": 100.0,
        **sentence_archive_values(result.get, prefixed=False)})

    engine, session = _db()
    session.add(SetupArchive(**values))
    session.commit()
    stored = session.query(SetupArchive).filter_by(ticker="PKE").one()
    assert stored.sentence_tokens == cells["sentence_tokens"]
    assert stored.sentence_n_tokens == cells["sentence_n_tokens"]
    assert stored.sentence_nan_bars == cells["sentence_nan_bars"]
    session.close()
    engine.dispose()


# ── the NULL state, and the three-state law cashed in SQL ───────────────────

def test_the_family_null_state_lands_as_three_sql_nulls():
    # Flag dark (or a refused read): the producer sees no keys at all and the
    # WHOLE family NULLs together — never empty strings, never zeros.
    engine, session = _db()
    _add(session, "DARK", {}, prefixed=True)
    session.commit()

    row = session.execute(text(
        "SELECT sentence_tokens, sentence_n_tokens, sentence_nan_bars "
        "FROM setup_archive WHERE ticker='DARK'")).one()
    assert list(row) == [None, None, None]
    session.close()
    engine.dispose()


def test_measured_empty_is_queryably_distinct_from_not_measured():
    """The three-state law's only real cash-out: a reader that RAN and found
    nothing (explicit zero beside its readability companion) must be separable
    by query from a family that was never measured (NULL)."""
    from archive_models import SetupArchive

    empty = serialize_sentence(
        unify_events(episode_read={"episodes": [], "n_episodes": 0,
                                   "nan_bars": 0, "n_bars": 30}),
        pd.bdate_range("2026-01-05", periods=30))
    assert empty == {"sentence_tokens": "[]", "sentence_n_tokens": 0,
                     "sentence_nan_bars": 0}

    engine, session = _db()
    _add(session, "EMPTY", empty, prefixed=True)
    _add(session, "DARK", {}, prefixed=True)
    session.commit()

    measured = session.query(SetupArchive).filter(
        SetupArchive.sentence_n_tokens.isnot(None)).all()
    not_measured = session.query(SetupArchive).filter(
        SetupArchive.sentence_n_tokens.is_(None)).all()
    assert [r.ticker for r in measured] == ["EMPTY"]
    assert [r.ticker for r in not_measured] == ["DARK"]
    # ... and the measured-empty row says zero, not NULL, on every cell.
    stored = measured[0]
    assert stored.sentence_n_tokens == 0 and stored.sentence_nan_bars == 0
    assert stored.sentence_tokens == "[]"
    session.close()
    engine.dispose()


def test_a_nan_companion_scrubs_to_null_before_it_reaches_sqlite():
    # EC-2 at the pandas boundary: bool(nan) is True, so an unscrubbed cell
    # would land the literal float('nan') in an INTEGER column and poison
    # every three-state query that follows.
    from archive_models import SetupArchive

    engine, session = _db()
    _add(session, "NANC", {"sentence_tokens": "[]", "sentence_n_tokens": 0,
                           "sentence_nan_bars": float("nan")}, prefixed=True)
    session.commit()
    stored = session.query(SetupArchive).filter_by(ticker="NANC").one()
    assert stored.sentence_nan_bars is None
    assert stored.sentence_n_tokens == 0     # its sibling stays measured
    session.close()
    engine.dispose()


def test_every_declared_family_column_is_a_nullable_table_column():
    # The declaration and the schema cannot drift: a declared cell with no
    # model column would write nowhere, and a NOT NULL one would make the
    # family's own NULL state unstorable.
    from archive_models import SetupArchive

    columns = SetupArchive.__table__.columns
    for col, sql_type in SENTENCE_COLUMN_SQL.items():
        assert col in columns, col
        assert columns[col].nullable, col
        assert str(columns[col].type).upper().startswith(
            "INTEGER" if sql_type == "INTEGER" else "VARCHAR"), col
