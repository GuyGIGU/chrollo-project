"""The archive, made safe for a second reader.

Task 6 of the two-eyes-reader build, and it is two separate promises.

**A lost night is the one unrecoverable failure.** Today the whole scan is
assembled row by row into ONE session and committed once at the end, with no
guard around a row. A single malformed value — a price that is not a number, a
date that is not a date — raises out of the writer and nothing at all is
committed. The setups were found, the night is over, and the record of it is
gone; there is no re-running yesterday's close. A bad row must cost that row,
and the night must SAY it lost one, because a silently shorter archive is how
a reader regression hides for a month.

**And a second reader needs somewhere to put what it sees.** The old engine
stores one box as a price pair and bar offsets; the new one reads a parent and
a mini, each line anchored on a DAY. Bar offsets cannot be redrawn once the
two-year window slides past them, and there is nowhere at all to put the
second box. Both land dark here, before a single new-reader row exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
for _p in (str(ROOT), str(BACKEND_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --------------------------------------------------------------------------- #
# Driving the real writer, with the network cut off                           #
# --------------------------------------------------------------------------- #
def _row(ticker: str, **over) -> dict:
    """One plausible fire row, in the live result dict's own vocabulary."""
    row = {
        "Ticker": ticker, "Setup": "box", "Tier": "B", "Score": 50.0,
        "Current Price": 10.0, "_R": 11.0, "_S": 9.0, "_trigger_price": 11.2,
        "Base Len": 40, "Box Width": 2.0, "Touches": 4, "_r_touches": 2,
        "_s_touches": 2, "ATR Ratio": 1.5, "LPS Length": 5, "Breach Days": 0,
        "_vol_contraction": 0.5, "_tightness_ratio": 0.4,
        "_base_date_start": "2026-01-05", "_base_date_end": "2026-03-06",
        "_base_close_start": 10.0, "_base_close_end": 10.5,
    }
    row.update(over)
    return row


@pytest.fixture()
def writer_on_a_scratch_db(tmp_path, monkeypatch):
    """The real `archive_scan_results`, against a throwaway file DB, with every
    network call stubbed. The live archive is never opened — `database` is the
    ONE door and this replaces it for the duration."""
    from sqlalchemy import create_engine

    import archive_models
    import database
    from core.archive import writer as writer_mod

    db = tmp_path / "scratch_archive.db"
    engine = create_engine(f"sqlite:///{db}")
    archive_models.SetupArchive.metadata.create_all(bind=engine)

    monkeypatch.setattr(database, "make_sqlite_engine", lambda *a, **k: engine)
    monkeypatch.setattr(archive_models, "resolve_sector_etf", lambda t: (True, ""))
    monkeypatch.setattr(archive_models, "get_market_context", lambda d: {})
    monkeypatch.setattr(archive_models, "get_sector_trend", lambda *a, **k: None)
    monkeypatch.setattr(writer_mod, "load_sector_etf_cache", lambda *a, **k: {})
    monkeypatch.setattr(writer_mod, "save_sector_etf_cache", lambda *a, **k: None)

    def rows_in_the_archive():
        from sqlalchemy.orm import sessionmaker
        session = sessionmaker(bind=engine)()
        try:
            return session.query(archive_models.SetupArchive).all()
        finally:
            session.close()

    return writer_mod, rows_in_the_archive


def test_one_bad_row_costs_that_row_and_not_the_night(writer_on_a_scratch_db):
    """The failure this task exists to end.

    Six good setups and one whose price is not a number. Today the bad one
    raises out of the loop before the single commit, so SIX good rows are lost
    with it and the night's record simply does not exist. There is no
    re-running a close.
    """
    writer_mod, rows_in_the_archive = writer_on_a_scratch_db

    good = [_row(f"AAA{i}") for i in range(6)]
    bad = _row("ROTTEN", **{"Current Price": "not a number"})
    frame = pd.DataFrame(good[:3] + [bad] + good[3:])

    refused: dict = {}
    written = writer_mod.archive_scan_results(
        frame, scan_date_str="2026-03-06", enable=True, refused=refused)

    stored = {r.ticker for r in rows_in_the_archive()}
    assert stored == {f"AAA{i}" for i in range(6)}, (
        "the six good setups are the night's record and must survive a "
        f"seventh bad one; stored {sorted(stored)}")
    assert written == 6
    assert refused["count"] == 1
    assert "ROTTEN" in refused["tickers"]


def test_the_night_says_how_many_rows_it_refused(writer_on_a_scratch_db):
    """A shorter archive that says nothing is worse than a crash: a reader
    regression that spoils one row in fifty would take a month to notice."""
    writer_mod, _ = writer_on_a_scratch_db

    frame = pd.DataFrame([_row("AAA"), _row("BBB")])
    refused: dict = {}
    writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06",
                                    enable=True, refused=refused)
    assert refused == {"count": 0, "tickers": []}, (
        "a clean night still reports, so zero is a measurement and not a "
        "missing key")


def test_a_refused_row_rides_the_scan_result_line_and_alerts_above_zero():
    """The count has to leave the process. It rides SCAN_RESULT_JSON, exactly
    as the errored-ticker count already does, and trips the alert at ONE — a
    lost row is not a threshold to tune."""
    import json

    from webapp.backend.services.scan_runner import _alert_decision, _parse_scan_result

    line = ('SCAN_RESULT_JSON:'
            + json.dumps({"n_setups": 7, "n_archived": 6, "n_errored": 0,
                          "n_refused": 1}))
    parsed = _parse_scan_result(line)
    assert parsed.n_refused == 1, "the refused count never left the scan"

    assert _alert_decision("ok", 6, None, True, True, 0, refused_rows=1), \
        "one refused row must alert"
    assert _alert_decision("ok", 6, None, True, True, 0, refused_rows=0) is None


def test_a_result_line_from_before_the_count_existed_reads_as_zero_refused():
    """A child that predates the count prints no `n_refused` key. That reads
    as zero — "no known refusals" — exactly as a missing errored count does,
    so an old line never raises a phantom alert and never breaks the parse."""
    import json

    from webapp.backend.services.scan_runner import _parse_scan_result

    older = 'SCAN_RESULT_JSON:' + json.dumps(
        {"n_setups": 5, "n_archived": 5, "n_errored": 0})
    counts = _parse_scan_result(older)
    assert counts.n_setups == 5
    assert counts.n_refused == 0


# --------------------------------------------------------------------------- #
# The second reader's column family                                           #
# --------------------------------------------------------------------------- #
def test_the_new_family_is_one_producer_and_every_column_is_nullable():
    """EC-30: a column family rides EVERY writer through ONE producer."""
    import archive_models
    from engine_alpha.two_eyes_archive import (TWO_EYES_COLUMN_SQL,
                                               two_eyes_archive_values)

    columns = {c.name: c for c in archive_models.SetupArchive.__table__.columns}
    for name in TWO_EYES_COLUMN_SQL:
        assert name in columns, f"{name} is not on the model"
        assert columns[name].nullable, (
            f"{name} must be nullable — every row the old reader ever wrote, "
            "and every row it writes tomorrow, has nothing to put there")
    assert set(two_eyes_archive_values(lambda k: None, prefixed=True)) \
        == set(TWO_EYES_COLUMN_SQL)


def test_the_family_carries_both_boxes_with_their_anchor_days():
    """Bar offsets cannot be redrawn once the two-year window slides past
    them; a DAY can. Two boxes of the same shape, because his mini and its
    parent are one setup."""
    from engine_alpha.two_eyes_archive import TWO_EYES_COLUMN_SQL

    for box in ("parent", "mini"):
        for part in ("r_price", "r_anchor_date", "s_price", "s_anchor_date",
                     "opened_date", "end_date", "daily_range"):
            name = f"two_eyes_{box}_{part}"
            assert name in TWO_EYES_COLUMN_SQL, f"{name} is missing"
    assert "two_eyes_lps_read_against" in TWO_EYES_COLUMN_SQL
    assert "two_eyes_has_mini" in TWO_EYES_COLUMN_SQL


def test_nothing_measured_is_stored_empty_and_never_as_a_number():
    """The whole family is NULL under the old reader — and NULL, not 0.0 and
    not "". A zero price is a made-up price, and a made-up number in an
    archive column is indistinguishable from a measured one forever after."""
    from engine_alpha.two_eyes_archive import two_eyes_archive_values

    empty = two_eyes_archive_values(lambda key: None, prefixed=True)
    assert set(empty.values()) == {None}, \
        f"the old reader's row invents values: { {k: v for k, v in empty.items() if v is not None} }"


def test_the_lps_box_word_is_a_closed_set_that_refuses_an_invented_word():
    """EC-22: every value in a closed-set label column has a committed
    producing test, and a word off the set never reaches the column."""
    from engine_alpha.two_eyes_archive import (TWO_EYES_LPS_BOXES,
                                               two_eyes_archive_values)

    assert TWO_EYES_LPS_BOXES == ("parent", "mini", "earlier")
    for word in TWO_EYES_LPS_BOXES:
        out = two_eyes_archive_values(
            {"_two_eyes_lps_read_against": word}.get, prefixed=True)
        assert out["two_eyes_lps_read_against"] == word

    with pytest.raises(ValueError):
        two_eyes_archive_values(
            {"_two_eyes_lps_read_against": "somewhere else"}.get, prefixed=True)


def test_the_mini_flag_has_three_states_not_two():
    """Yes, no, and "the reader that wrote this row never looked" — which is
    every row in the archive today. A two-state flag would quietly claim all
    of them had no mini."""
    from engine_alpha.two_eyes_archive import two_eyes_archive_values

    def flag(value):
        return two_eyes_archive_values(
            {"_two_eyes_has_mini": value}.get, prefixed=True)["two_eyes_has_mini"]

    assert flag(True) == 1
    assert flag(False) == 0
    assert flag(None) is None


# --------------------------------------------------------------------------- #
# End to end: the reader's record, through the adapter, into the real writer  #
# --------------------------------------------------------------------------- #
def _fired_read(*, with_mini: bool, lps_box: str = "parent", parent_end=None):
    """A fire as the new reader will hand it over. The stages that FIND these
    boxes do not exist yet; the adapter and the writer that CARRY them do, and
    that crossing is what this proves."""
    import datetime as dt

    from engine_alpha.two_eyes import record

    d = dt.date
    boxes = [record.Box(resistance=record.Line(100.0, d(2026, 1, 5)),
                        support=record.Line(90.0, d(2026, 1, 7)),
                        opened_day=d(2026, 1, 5), end_day=parent_end,
                        daily_range=2.0, role=record.ROLE_PARENT)]
    if with_mini:
        boxes.append(record.Box(resistance=record.Line(98.0, d(2026, 2, 10)),
                                support=record.Line(94.0, d(2026, 2, 12)),
                                opened_day=d(2026, 2, 10), end_day=None,
                                daily_range=1.5, role=record.ROLE_MINI))
    lps = record.Lps(d(2026, 3, 2), d(2026, 3, 6), lps_box, trigger_price=98.4)
    return record.Read(ticker="TWOEYES", as_of=d(2026, 3, 6), boxes=tuple(boxes),
                       lps=lps, state="fired")


def _archive_one(writer_on_a_scratch_db, read):
    from engine_alpha.two_eyes_adapter import to_result

    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    refused: dict = {}
    writer_mod.archive_scan_results(pd.DataFrame([to_result(read)]),
                                    scan_date_str="2026-03-06", enable=True,
                                    refused=refused)
    assert refused["count"] == 0, (
        f"the writer refused the new reader's OWN row: {refused['tickers']} — "
        "every two-eyes fire would be lost")
    (stored,) = rows_in_the_archive()
    return stored


def test_a_real_fire_fills_both_boxes_through_the_real_writer(writer_on_a_scratch_db):
    """The family must be FILLED by the reader that owns it, not just shaped.

    Every guard above fed the producer hand-made keys, and all of them passed
    while a real fire filled 2 of the 16 columns: the adapter spoke one set of
    names and the family read another. Only the whole crossing can catch that.
    """
    stored = _archive_one(writer_on_a_scratch_db, _fired_read(
        with_mini=True, lps_box="mini", parent_end=__import__("datetime").date(2026, 3, 4)))

    assert (stored.two_eyes_parent_r_price, stored.two_eyes_parent_r_anchor_date) \
        == (100.0, "2026-01-05")
    assert (stored.two_eyes_parent_s_price, stored.two_eyes_parent_s_anchor_date) \
        == (90.0, "2026-01-07")
    assert stored.two_eyes_parent_opened_date == "2026-01-05"
    assert stored.two_eyes_parent_end_date == "2026-03-04"
    assert stored.two_eyes_parent_daily_range == 2.0

    assert (stored.two_eyes_mini_r_price, stored.two_eyes_mini_r_anchor_date) \
        == (98.0, "2026-02-10")
    assert (stored.two_eyes_mini_s_price, stored.two_eyes_mini_s_anchor_date) \
        == (94.0, "2026-02-12")
    assert stored.two_eyes_mini_opened_date == "2026-02-10"
    assert stored.two_eyes_mini_end_date is None, "a live box has no end day"
    assert stored.two_eyes_mini_daily_range == 1.5

    assert stored.two_eyes_lps_read_against == "mini"
    assert stored.two_eyes_has_mini == 1


def test_a_fire_without_a_mini_says_no_rather_than_nothing(writer_on_a_scratch_db):
    """The new reader LOOKED, so its answer is 0, never NULL — NULL is kept
    for the rows written by a reader that never looked."""
    stored = _archive_one(writer_on_a_scratch_db, _fired_read(with_mini=False))
    assert stored.two_eyes_has_mini == 0
    assert stored.two_eyes_mini_r_price is None
    assert stored.two_eyes_parent_r_price == 100.0


def test_the_stored_lines_stay_the_parents_when_a_mini_is_live(writer_on_a_scratch_db):
    """Still one row, one trigger — and the columns every existing reader of
    the archive knows as THE box stay the parent's. The mini rides only in
    its own columns."""
    stored = _archive_one(writer_on_a_scratch_db,
                          _fired_read(with_mini=True, lps_box="mini"))
    assert (stored.r_level, stored.s_level) == (100.0, 90.0)
    assert stored.trigger_price == 98.4


@pytest.mark.parametrize("lps_box", ["parent", "mini", "earlier"])
def test_every_lps_box_word_is_produced_end_to_end(writer_on_a_scratch_db, lps_box):
    """EC-22: each legal value of a closed-set column is PRODUCED by the real
    path, not merely accepted by the producer when handed it."""
    stored = _archive_one(writer_on_a_scratch_db,
                          _fired_read(with_mini=(lps_box == "mini"), lps_box=lps_box))
    assert stored.two_eyes_lps_read_against == lps_box


# --------------------------------------------------------------------------- #
# The blind check's findings (verify-6): each a guard, each watched failing   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [
    {"_lps_zone_type": ["a", "list"]},          # a list in a text column
    {"_r_touch_vol_z": "n/a"},                  # a word in a number column
    {"Score": float("nan")},                    # empty in a NOT NULL column
    {"_elected_pool": "invented"},              # a word off a CHECK
], ids=["list-in-text", "word-in-number", "nan-in-not-null", "off-check"])
def test_a_row_the_database_refuses_costs_that_row_alone(writer_on_a_scratch_db, bad):
    """The first guard caught only rows that failed to ASSEMBLE. These all
    assemble cleanly and are refused by the database when the row is written
    — and that used to happen at the one commit at the end of the night,
    which took every good row down with it. The only test then used a price,
    one of the few values the writer casts itself, so it passed while the
    promise was false for nearly every column."""
    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    frame = pd.DataFrame([_row("AAA0"), _row("ROTTEN", **bad), _row("AAA1")])
    refused: dict = {}
    written = writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06",
                                              enable=True, refused=refused)
    assert {r.ticker for r in rows_in_the_archive()} == {"AAA0", "AAA1"}
    assert written == 2
    assert refused == {"count": 1, "tickers": ["ROTTEN"]}


def test_a_bad_update_does_not_undo_the_nights_other_updates(writer_on_a_scratch_db):
    """Re-archiving a date updates rows in place. One bad update used to roll
    back every other update and every new row with it."""
    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    writer_mod.archive_scan_results(pd.DataFrame([_row("AAA0"), _row("AAA1")]),
                                    scan_date_str="2026-03-06", enable=True)
    again = pd.DataFrame([_row("AAA0", Score=77.0),
                          _row("AAA1", _lps_zone_type=["bad"]),
                          _row("NEW1", Score=66.0)])
    refused: dict = {}
    writer_mod.archive_scan_results(again, scan_date_str="2026-03-06",
                                    enable=True, refused=refused)
    scores = {r.ticker: r.score for r in rows_in_the_archive()}
    assert scores == {"AAA0": 77.0, "AAA1": 50.0, "NEW1": 66.0}
    assert refused["tickers"] == ["AAA1"]


def test_a_night_where_every_row_is_refused_fails_instead_of_passing_green(
        writer_on_a_scratch_db):
    """One bad row is a row. EVERY row refused is the writer or the reader
    broken, and recorded as a green run it would skip the boot catch-up that
    re-runs a lost close and show on the screen as served."""
    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    frame = pd.DataFrame([_row(f"T{i}", **{"Current Price": "n/a"}) for i in range(3)])
    with pytest.raises(writer_mod.ArchiveRefusedEveryRow):
        writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06", enable=True)
    assert rows_in_the_archive() == []


def test_an_odd_base_date_voids_one_rows_sector_read_not_the_night(
        writer_on_a_scratch_db, monkeypatch):
    """The sector window is gathered BEFORE the per-row guard. One row's
    missing base date (NaN, which is truthy) or a timestamp there made min()
    compare mixed types and ended the night before a single row was written.
    The fixture maps no ticker to a sector, so this path needs its own."""
    import yfinance

    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    monkeypatch.setattr(writer_mod, "load_sector_etf_cache",
                        lambda *a, **k: {"AAA0": "XLK", "NODATE": "XLK", "STAMP": "XLK"})
    monkeypatch.setattr(yfinance, "download", lambda *a, **k: pd.DataFrame())
    nodate = _row("NODATE")
    del nodate["_base_date_start"]
    frame = pd.DataFrame([_row("AAA0"), nodate,
                          _row("STAMP", _base_date_start=pd.Timestamp("2026-01-05"))])
    refused: dict = {}
    written = writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06",
                                              enable=True, refused=refused)
    assert written == 3 and refused["count"] == 0
    assert {r.ticker for r in rows_in_the_archive()} == {"AAA0", "NODATE", "STAMP"}


def test_the_writer_stores_empty_for_what_the_reader_did_not_measure(
        writer_on_a_scratch_db):
    """A nullable core column the reader left out used to be stored as 0 — a
    number nobody measured — and a None there made the row fail. Empty now,
    in both cases. A row that carries every number is stored exactly as
    before."""
    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    blank = _row("BLANK", Touches=None, _r_touches=None)
    del blank["Breach Days"], blank["_vol_contraction"]
    writer_mod.archive_scan_results(pd.DataFrame([_row("FULL"), blank]),
                                    scan_date_str="2026-03-06", enable=True)
    stored = {r.ticker: r for r in rows_in_the_archive()}
    b = stored["BLANK"]
    assert (b.touches, b.r_touches, b.breach_days, b.vol_contraction) == (None,) * 4
    f = stored["FULL"]
    assert (f.touches, f.r_touches, f.breach_days, f.vol_contraction) == (4, 2, 0, 0.5)
    assert (f.current_price, f.r_level, f.s_level, f.trigger_price) == (10.0, 11.0, 9.0, 11.2)

    # A night of ONLY blanks. Mixed with a full row above, pandas hands the
    # writer NaN; alone, the column holds a bare None — the shape a night of
    # nothing but new-reader rows arrives in. A first version of this test
    # only ever reached the NaN path, and a mutation on the None path walked
    # straight past it.
    alone = _row("ALONE", Touches=None, _r_touches=None)
    writer_mod.archive_scan_results(pd.DataFrame([alone]),
                                    scan_date_str="2026-03-09", enable=True)
    a = next(r for r in rows_in_the_archive() if r.ticker == "ALONE")
    assert (a.touches, a.r_touches) == (None, None)


def test_a_new_reader_fire_stores_the_real_close_and_no_invented_counts(
        writer_on_a_scratch_db):
    """End to end: the setup's price is the read day's close (the resistance
    line stood in once — and the forward-returns backfill scales every
    trigger by this price), and what the reader does not count yet is empty."""
    import dataclasses

    read = dataclasses.replace(_fired_read(with_mini=False), close=95.37)
    stored = _archive_one(writer_on_a_scratch_db, read)
    assert stored.current_price == 95.37
    assert (stored.touches, stored.r_touches, stored.s_touches, stored.breach_days,
            stored.vol_contraction, stored.tightness_ratio) == (None,) * 6
    # One meaning per column. A first version put the box's height in daily
    # ranges into the ATR-squeeze column, its width in price points into a
    # column that holds a fraction, and calendar days into bar counts — all
    # stored as if measured, and all read by the same reports as the old
    # reader's numbers.
    assert stored.box_width == pytest.approx((100.0 - 90.0) / 90.0), \
        "the column's own definition: height over support"
    assert stored.atr_ratio is None, "this reader does not measure the squeeze"
    assert (stored.base_length, stored.lps_length) == (None, None), \
        "bar counts, which stage 5 has not ruled how to count yet"


def test_a_fresh_database_refuses_an_off_set_word_even_past_the_producer(tmp_path):
    """EC-19: the producer refuses a bad word, and on a fresh database the
    table does too, like every sibling closed-set column — a raw insert that
    bypasses the producer must not land."""
    import datetime as dt

    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    import archive_models

    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    base = dict(ticker="X", scan_date=dt.date(2026, 3, 6),
                setup_type="box", tier="B", score=1.0)
    for bad in ({"two_eyes_lps_read_against": "somewhere else"},
                {"two_eyes_has_mini": 7}):
        session = sessionmaker(bind=engine)()
        session.add(archive_models.SetupArchive(**base, **bad))
        with pytest.raises(IntegrityError):
            session.commit()
        session.close()


@pytest.mark.parametrize("value", [2, -1, 0.7, "yes"])
def test_the_mini_flag_refuses_anything_but_yes_or_no(value):
    """int() stored a 2 as a 2 and truncated 0.7 to 0 — "no mini" — a
    different fact made up out of a bad number."""
    from engine_alpha.two_eyes_archive import two_eyes_archive_values

    with pytest.raises(ValueError):
        two_eyes_archive_values({"_two_eyes_has_mini": value}.get, prefixed=True)


def test_a_day_column_holds_a_day():
    """A timestamp is cut to its day, not stored with a clock time the market
    never traded at; a string that is not a day is refused."""
    from engine_alpha.two_eyes_archive import two_eyes_archive_values

    out = two_eyes_archive_values(
        {"_two_eyes_parent_opened_date": pd.Timestamp("2026-01-05 09:30")}.get,
        prefixed=True)
    assert out["two_eyes_parent_opened_date"] == "2026-01-05"
    with pytest.raises(ValueError):
        two_eyes_archive_values({"_two_eyes_parent_opened_date": "garbage"}.get,
                                prefixed=True)


# --------------------------------------------------------------------------- #
# The count's way out of the process, link by link                            #
# --------------------------------------------------------------------------- #
def test_the_result_line_the_child_prints_carries_the_count(capsys):
    """Not a hand-written line: the one run_screener actually prints."""
    import run_screener
    from webapp.backend.services.scan_runner import _parse_scan_result

    run_screener._print_result_json(7, 6, 0, None, 3)
    assert _parse_scan_result(capsys.readouterr().out).n_refused == 3


def test_the_nightly_all_universes_line_sums_refusals_over_every_universe(
        monkeypatch, capsys):
    """The scheduled scan runs every universe and each archives into the same
    table. The other counts stay the primary's on purpose; a row refused in an
    ETF universe is still a lost row, and a lost night cannot be re-run."""
    from types import SimpleNamespace

    import run_screener
    from webapp.backend.services.scan_runner import _parse_scan_result

    def result(n_refused):
        return SimpleNamespace(n_setups=3, n_archived=3, n_errored=0,
                               fundamentals_counts=None, n_refused=n_refused)

    monkeypatch.setattr(run_screener, "run_all_universe_scans", lambda mode: {
        run_screener.DEFAULT_UNIVERSE_KEY: result(0),
        "us_sectors": result(2), "commodities_etf": result(1), "crashed": None})
    monkeypatch.setattr(sys, "argv", ["run_screener.py", "--all-universes"])
    run_screener.main()
    counts = _parse_scan_result(capsys.readouterr().out)
    assert counts.n_refused == 3
    assert counts.n_setups == 3, "the others stay the primary's"


def test_the_alert_itself_hears_the_refused_count(monkeypatch, caplog):
    """alert_if_needed, not just the pure decision behind it."""
    import logging
    from types import SimpleNamespace

    import app.core_settings as core_settings_mod
    from webapp.backend.services import scan_runner

    monkeypatch.setattr(scan_runner, "_last_fetch_health", lambda: None)
    monkeypatch.setattr(core_settings_mod, "load_core_settings", lambda: SimpleNamespace())
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    with caplog.at_level(logging.WARNING):
        scan_runner.alert_if_needed("scheduled", "ok", 6, None, 0, 2)
    assert any("2 row(s) refused" in r.getMessage() for r in caplog.records)


def test_a_refused_row_adds_to_the_alert_and_never_silences_it():
    """One malformed row on a night that also lost forty tickers to eval
    crashes must not be the only thing the alert says."""
    from webapp.backend.services.scan_runner import _alert_decision

    both = _alert_decision("ok", 6, None, True, True, 40, refused_rows=1)
    assert "40 ticker(s) errored" in both and "1 row(s) refused" in both
    alone = _alert_decision("ok", 6, None, True, True, 40, refused_rows=0)
    assert alone.startswith("40 ticker(s) errored") and "refused" not in alone


# --------------------------------------------------------------------------- #
# The second blind check's findings (verify-6b)                               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [
    {"_inner_source": pd.Timestamp("2026-01-05")},
    {"_lps_anchor_date": pd.Timestamp("2026-01-05")},
    {"_inner_source": pd.Timedelta(days=1)},
    {"_adr_pct": complex(1, 2)},
], ids=["timestamp", "timestamp-in-a-date-column", "duration", "complex"])
def test_one_rows_odd_type_does_not_poison_the_column_for_the_others(
        writer_on_a_scratch_db, bad):
    """pandas types a column across the whole frame. One row's timestamp in a
    column the other rows leave empty makes the column dates, and every OTHER
    row reads back NaT — which the database cannot bind. The per-row guard
    then refused every good row with the bad one, and the night was lost
    through the side door."""
    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    frame = pd.DataFrame([_row("AAA0"), _row("ROTTEN", **bad), _row("AAA1")])
    refused: dict = {}
    written = writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06",
                                              enable=True, refused=refused)
    assert {r.ticker for r in rows_in_the_archive()} == {"AAA0", "AAA1"}
    assert written == 2 and refused["tickers"] == ["ROTTEN"]


def test_a_fault_of_the_database_fails_the_night_instead_of_dropping_rows(
        writer_on_a_scratch_db, monkeypatch):
    """A lock held past the busy timeout, a full disk, an I/O error: none of
    them is a row's fault. Counted as bad rows, a lock that cleared halfway
    would leave a green night silently short — the catch-up skips a green
    night. It fails the night whole instead, as it always did, and the rows
    written before it are rolled back with it."""
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    real_flush, calls = Session.flush, []

    def flush_until_locked(self, *a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise OperationalError("INSERT", {}, Exception("database is locked"))
        return real_flush(self, *a, **k)

    monkeypatch.setattr(Session, "flush", flush_until_locked)
    frame = pd.DataFrame([_row("AAA0"), _row("AAA1"), _row("AAA2")])
    with pytest.raises(OperationalError):
        writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06", enable=True)
    monkeypatch.setattr(Session, "flush", real_flush)
    assert rows_in_the_archive() == [], "the night is one transaction"


def test_a_scan_killed_mid_archive_leaves_no_partial_night(tmp_path):
    """The night is ONE transaction. Committed row by row, a scan stopped or
    powered off halfway left a partial night made of the best-graded rows
    only (the results are sorted), with nothing to say it was partial. This
    runs the real writer in a child that dies on the fourth row."""
    import subprocess
    import textwrap

    db = tmp_path / "killed.db"
    child = textwrap.dedent(f"""
        import os, sys
        sys.path[:0] = [{str(ROOT)!r}, {str(BACKEND_DIR)!r}]
        os.environ["CHROLLO_DB_PATH"] = {str(tmp_path / "unused.db")!r}
        import pandas as pd
        from sqlalchemy import create_engine
        import archive_models, database
        from core.archive import writer as w
        engine = create_engine("sqlite:///" + {str(db)!r})
        archive_models.SetupArchive.metadata.create_all(bind=engine)
        database.make_sqlite_engine = lambda *a, **k: engine
        archive_models.resolve_sector_etf = lambda t: (True, "")
        archive_models.get_market_context = lambda d: {{}}
        archive_models.get_sector_trend = lambda *a, **k: None
        w.load_sector_etf_cache = lambda *a, **k: {{}}
        w.save_sector_etf_cache = lambda *a, **k: None
        real_empty = w._empty
        def dies_on_the_fourth(value):
            if value == "G3":
                os._exit(9)
            return real_empty(value)
        w._empty = dies_on_the_fourth
        rows = [dict(Ticker=f"G{{i}}", Setup="box", Tier="B", Score=100.0 - i)
                for i in range(6)]
        w.archive_scan_results(pd.DataFrame(rows), scan_date_str="2026-03-06",
                               enable=True)
    """)
    done = subprocess.run([sys.executable, "-c", child], capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 9, f"the child did not die where planned: {done.stderr[-800:]}"

    import sqlite3
    with sqlite3.connect(db) as conn:
        stored = conn.execute("SELECT ticker FROM setup_archive").fetchall()
    assert stored == [], f"a killed scan left a partial night: {stored}"


def test_a_refused_rerun_keeps_the_earlier_row_and_says_so(writer_on_a_scratch_db, caplog):
    """A date is often archived twice (a manual scan, then the evening slot).
    When the second write is refused, the first run's row is still there — so
    "not in the record" would be false. The log says which it is."""
    import logging

    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    writer_mod.archive_scan_results(pd.DataFrame([_row("AAA"), _row("BBB")]),
                                    scan_date_str="2026-03-06", enable=True)
    again = pd.DataFrame([_row("AAA", Score=80.0, _lps_zone_type=["bad"]),
                          _row("BBB", Score=70.0)])
    with caplog.at_level(logging.ERROR, logger="chrollo.archive"):
        writer_mod.archive_scan_results(again, scan_date_str="2026-03-06", enable=True)
    scores = {r.ticker: r.score for r in rows_in_the_archive()}
    assert scores == {"AAA": 50.0, "BBB": 70.0}
    assert any("earlier run's row for this date is kept" in r.getMessage()
               for r in caplog.records)


def test_a_base_date_that_is_not_a_day_voids_only_its_own_sector_read(
        writer_on_a_scratch_db, monkeypatch):
    """The window is the earliest start to the latest end over the night. A
    string that is not a day sorted to the end of it and moved the whole
    window, so every row's RS-vs-sector read came back empty."""
    import yfinance

    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    monkeypatch.setattr(writer_mod, "load_sector_etf_cache",
                        lambda *a, **k: {"AAA0": "XLK", "ODD": "XLK"})

    def closes(etf, start, end, **k):
        days = pd.bdate_range(start, end)
        return pd.DataFrame({"Close": [100.0 + i for i in range(len(days))]}, index=days)

    monkeypatch.setattr(yfinance, "download", closes)
    frame = pd.DataFrame([_row("AAA0"), _row("ODD", _base_date_end="not a day")])
    writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06", enable=True)
    stored = {r.ticker: r for r in rows_in_the_archive()}
    assert stored["AAA0"].rs_vs_sector_pct is not None, "the good row's read survives"
    assert stored["ODD"].rs_vs_sector_pct is None


def test_a_read_built_from_a_date_index_still_archives_as_days(writer_on_a_scratch_db):
    """A date index hands out timestamps. Written down as-is they carry a
    clock time, and the archive — which stores days — refused the whole
    fire. The record cuts them to days on the way in."""
    import datetime as dt

    from engine_alpha.two_eyes import record

    ts = pd.Timestamp
    box = record.Box(resistance=record.Line(100.0, ts("2026-01-05")),
                     support=record.Line(90.0, ts("2026-01-07")),
                     opened_day=ts("2026-01-05"), end_day=ts("2026-03-04"),
                     daily_range=2.0)
    read = record.Read(ticker="STAMPED", as_of=ts("2026-03-06"), boxes=(box,),
                       lps=record.Lps(ts("2026-03-02"), ts("2026-03-06"), "parent",
                                      trigger_price=98.4),
                       state="fired", close=95.0)
    assert read.as_of == dt.date(2026, 3, 6) and type(read.as_of) is dt.date
    stored = _archive_one(writer_on_a_scratch_db, read)
    assert stored.two_eyes_parent_r_anchor_date == "2026-01-05"
    assert stored.two_eyes_parent_end_date == "2026-03-04"


def test_the_archives_lps_words_are_the_records_own_tuple_and_its_check():
    """One vocabulary (EC-33): the archive takes the record's tuple rather
    than a copy typed out again, and the table's fresh-database CHECK names
    exactly the same words."""
    import re

    import archive_models
    from engine_alpha.two_eyes import record
    from engine_alpha.two_eyes_archive import TWO_EYES_LPS_BOXES

    assert TWO_EYES_LPS_BOXES is record.ROLES
    check = next(c for c in archive_models.SetupArchive.__table__.constraints
                 if c.name == "ck_setup_archive_two_eyes_lps_read_against")
    assert tuple(re.findall(r"'([^']+)'", str(check.sqltext))) == record.ROLES


def test_the_scan_prints_a_new_reader_row_before_it_archives_it(capsys):
    """The terminal table is printed BEFORE the archive runs, with no guard.
    A value the new reader leaves empty made it raise, and the first night
    the reader fired would have lost its archive at the print."""
    from engine_alpha.two_eyes_adapter import to_result
    from core.pipeline.screening.terminal import print_results

    print_results(pd.DataFrame([to_result(_fired_read(with_mini=False))]))
    assert "TWOEYES" in capsys.readouterr().out


# -- the count, on the links a mutation walked past --------------------------
def test_an_etf_universe_that_refused_every_row_still_counts_on_the_night(monkeypatch):
    """An ETF universe's failure is isolated by design, and when the failure
    IS the archive refusing every row, it used to become a bare None that the
    night's sum read as nothing refused — the quietest shape, since an ETF
    universe usually fires one or two setups."""
    from types import SimpleNamespace

    from core.archive.writer import ArchiveRefusedEveryRow
    from core.pipeline.screening import scan_job

    primary, etf = SimpleNamespace(key="us_stocks"), SimpleNamespace(key="us_sectors")
    monkeypatch.setattr(scan_job, "all_universes", lambda: [primary, etf])

    def scan(mode, universe):
        if universe is etf:
            raise ArchiveRefusedEveryRow("every row refused", ["XLK", "XLF"])
        return scan_job.ScanExportResult(n_setups=5, n_archived=5)

    monkeypatch.setattr(scan_job, "run_scan_and_export", scan)
    results = scan_job.run_all_universe_scans()
    assert results["us_sectors"].n_refused == 2


def test_a_stale_primary_night_still_carries_the_other_universes_refusals(
        monkeypatch, capsys):
    """The primary's stale error is re-raised AFTER the ETF universes have
    archived. Their refusals used to leave with the exception, and the alert
    named only the staleness."""
    from types import SimpleNamespace

    import run_screener
    from core.pipeline.screening import scan_job
    from webapp.backend.services.scan_runner import _alert_decision, _parse_scan_result

    primary, etf = SimpleNamespace(key="us_stocks"), SimpleNamespace(key="us_sectors")
    monkeypatch.setattr(scan_job, "all_universes", lambda: [primary, etf])

    def scan(mode, universe):
        if universe is primary:
            raise scan_job.StaleMarketDataError("stale", n_setups=5)
        return scan_job.ScanExportResult(n_setups=2, n_archived=0, n_refused=2)

    monkeypatch.setattr(scan_job, "run_scan_and_export", scan)
    monkeypatch.setattr(run_screener, "run_all_universe_scans", scan_job.run_all_universe_scans)
    monkeypatch.setattr(sys, "argv", ["run_screener.py", "--all-universes"])
    with pytest.raises(scan_job.StaleMarketDataError):
        run_screener.main()
    counts = _parse_scan_result(capsys.readouterr().out)
    assert counts.n_refused == 2
    reason = _alert_decision("stale_data", counts.n_setups, None, True, True,
                             counts.n_errored, refused_rows=counts.n_refused)
    assert reason.startswith("stale_data") and "2 row(s) refused" in reason


def test_the_manual_scans_own_line_carries_the_count(monkeypatch, capsys):
    """The single-universe line — the one a manual scan and the cached
    evaluation print — not only the nightly all-universes one."""
    from types import SimpleNamespace

    import run_screener
    from webapp.backend.services.scan_runner import _parse_scan_result

    monkeypatch.setattr(run_screener, "run_scan_and_export", lambda **k: SimpleNamespace(
        n_setups=3, n_archived=1, n_errored=0, fundamentals_counts=None, n_refused=2))
    monkeypatch.setattr(sys, "argv", ["run_screener.py"])
    run_screener.main()
    assert _parse_scan_result(capsys.readouterr().out).n_refused == 2


def test_the_nightly_runner_reads_the_count_off_the_childs_own_line(monkeypatch):
    """The scheduled scan's runner, unstubbed: a fake child prints the line
    and the runner's own result must carry the count it printed."""
    from types import SimpleNamespace

    from webapp.backend.services import scan_runner

    lines = ["scanning\n",
             'SCAN_RESULT_JSON:{"n_setups": 3, "n_archived": 1, "n_errored": 0, '
             '"n_refused": 2}\n']

    class Stdout:
        def __iter__(self):
            return iter(lines)

        def close(self):
            pass

    child = SimpleNamespace(stdout=Stdout(), returncode=0, wait=lambda: 0)
    monkeypatch.setattr(scan_runner, "_create_process", lambda args=None: child)
    assert scan_runner._run_scan_process_unlocked(["--all-universes"]).n_refused == 2


# --------------------------------------------------------------------------- #
# The root causes a diagnosis found behind the second round (diagnose-6)      #
# --------------------------------------------------------------------------- #
def test_a_complex_value_in_a_column_the_others_fill_costs_only_its_row(
        writer_on_a_scratch_db):
    """The other coupling pandas makes. One complex value in a column the
    other rows FILL turns the whole column complex, every good row arrives as
    x+0j, and the database refuses them all. The earlier poisoning test only
    had the other rows leave the column EMPTY — the shape the first fix
    handled — because the fixture's rows are sparse and a real row is not."""
    writer_mod, rows_in_the_archive = writer_on_a_scratch_db
    frame = pd.DataFrame([_row("AAA0", _adr_pct=2.5),
                          _row("ROTTEN", _adr_pct=complex(1, 2)),
                          _row("AAA1", _adr_pct=3.25)])
    refused: dict = {}
    written = writer_mod.archive_scan_results(frame, scan_date_str="2026-03-06",
                                              enable=True, refused=refused)
    stored = {r.ticker: r.adr_pct for r in rows_in_the_archive()}
    assert stored == {"AAA0": 2.5, "AAA1": 3.25}, "the good values, exactly"
    assert written == 2 and refused["tickers"] == ["ROTTEN"]


def test_a_manual_scan_whose_archive_refused_everything_still_names_the_count(
        monkeypatch, capsys):
    """Only the stale failure used to carry the count out. Every other
    failure — including the archive refusing every row, the very case that
    fails the night on purpose — printed no line at all."""
    import run_screener
    from core.archive.writer import ArchiveRefusedEveryRow
    from webapp.backend.services.scan_runner import _alert_decision, _parse_scan_result

    def refuses_everything(**k):
        raise ArchiveRefusedEveryRow("every row refused", ["AAA", "BBB"])

    monkeypatch.setattr(run_screener, "run_scan_and_export", refuses_everything)
    monkeypatch.setattr(sys, "argv", ["run_screener.py"])
    with pytest.raises(ArchiveRefusedEveryRow):
        run_screener.main()
    counts = _parse_scan_result(capsys.readouterr().out)
    assert counts.n_refused == 2
    assert "2 row(s) refused" in _alert_decision(
        "failed", counts.n_setups, None, True, True, 0, refused_rows=counts.n_refused)


def test_a_primary_that_fails_for_any_reason_carries_every_universes_refusals(
        monkeypatch, capsys):
    from types import SimpleNamespace

    import run_screener
    from core.archive.writer import ArchiveRefusedEveryRow
    from core.pipeline.screening import scan_job
    from webapp.backend.services.scan_runner import _parse_scan_result

    primary, etf = SimpleNamespace(key="us_stocks"), SimpleNamespace(key="us_sectors")
    monkeypatch.setattr(scan_job, "all_universes", lambda: [primary, etf])

    def scan(mode, universe):
        if universe is primary:
            raise ArchiveRefusedEveryRow("every row refused", ["AAA"])
        return scan_job.ScanExportResult(n_setups=2, n_archived=0, n_refused=2)

    monkeypatch.setattr(scan_job, "run_scan_and_export", scan)
    monkeypatch.setattr(run_screener, "run_all_universe_scans", scan_job.run_all_universe_scans)
    monkeypatch.setattr(sys, "argv", ["run_screener.py", "--all-universes"])
    with pytest.raises(ArchiveRefusedEveryRow):
        run_screener.main()
    assert _parse_scan_result(capsys.readouterr().out).n_refused == 3, \
        "the primary's own refusal plus the ETF universe's two"


def test_a_failure_with_no_refusals_prints_no_line_exactly_as_before(monkeypatch, capsys):
    import run_screener

    def crashes(**k):
        raise RuntimeError("the chain broke")

    monkeypatch.setattr(run_screener, "run_scan_and_export", crashes)
    monkeypatch.setattr(sys, "argv", ["run_screener.py"])
    with pytest.raises(RuntimeError):
        run_screener.main()
    assert "SCAN_RESULT_JSON" not in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# The third blind check's findings (verify-6c)                                #
# --------------------------------------------------------------------------- #
def test_the_night_takes_the_write_lock_before_it_reads(tmp_path, monkeypatch):
    """BEGIN IMMEDIATE, not a deferred BEGIN. The loop reads (the upsert's
    existence check) before it writes; a deferred read transaction cannot be
    upgraded to a write if another process committed in between, and SQLite
    refuses that at once — the busy timeout does not help — failing the whole
    night. Taken up front, the lock makes the other writer wait instead."""
    import sqlite3

    from sqlalchemy import create_engine, event

    import archive_models
    import database
    from core.archive import writer as writer_mod

    db = tmp_path / "wal.db"
    engine = create_engine(f"sqlite:///{db}")

    @event.listens_for(engine, "connect")
    def _wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    archive_models.SetupArchive.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "make_sqlite_engine", lambda *a, **k: engine)
    monkeypatch.setattr(archive_models, "resolve_sector_etf", lambda t: (True, ""))
    monkeypatch.setattr(archive_models, "get_market_context", lambda d: {})
    monkeypatch.setattr(archive_models, "get_sector_trend", lambda *a, **k: None)
    monkeypatch.setattr(writer_mod, "load_sector_etf_cache", lambda *a, **k: {})
    monkeypatch.setattr(writer_mod, "save_sector_etf_cache", lambda *a, **k: None)

    other_writer = {}
    real_family = writer_mod.two_eyes_archive_values

    def someone_else_writes_mid_row(get, *, prefixed):
        # Runs after the first row's existence check and before its flush —
        # exactly the moment a deferred transaction is still only a reader.
        if not other_writer:
            side = sqlite3.connect(db, timeout=0.2, isolation_level=None)
            try:
                side.execute("BEGIN IMMEDIATE")
                side.execute("INSERT INTO setup_archive (ticker, scan_date, setup_type, "
                             "tier, score, universe_type) VALUES "
                             "('SIDE', '2026-03-05', 'LPS', 'B', 1.0, 'us_equities')")
                side.execute("COMMIT")
                other_writer["result"] = "wrote"
            except sqlite3.OperationalError:
                other_writer["result"] = "waited"
            finally:
                side.close()
        return real_family(get, prefixed=prefixed)

    monkeypatch.setattr(writer_mod, "two_eyes_archive_values", someone_else_writes_mid_row)
    written = writer_mod.archive_scan_results(
        pd.DataFrame([_row("AAA0"), _row("AAA1")]), scan_date_str="2026-03-06", enable=True)
    assert other_writer["result"] == "waited", "the night did not hold the write lock"
    assert written == 2


def test_a_new_reader_fire_is_archived_as_an_lps_setup(writer_on_a_scratch_db):
    """setup_type holds the SETUP TYPE (LPS / REBOUND) on every old-reader
    row. The new reader first wrote its screen word there ('fired'), a second
    vocabulary in one column."""
    stored = _archive_one(writer_on_a_scratch_db, _fired_read(with_mini=False))
    assert stored.setup_type == "LPS"


def test_the_seed_and_manual_writers_fill_the_family_from_their_own_row_shape():
    """Both take their row from the seed's re-keying — leading underscores
    stripped — and call the producer with prefixed=False. Only the live writer
    had a test that the family ends up FULL; for these two, only that the
    producer is called. This is the crossing itself, plus the one argument
    that makes it work at each call site."""
    import ast
    import inspect

    from core.archive import seed
    from core.archive.result_adapter import seed_row_from_result
    from engine_alpha.two_eyes_adapter import to_result
    from engine_alpha.two_eyes_archive import TWO_EYES_COLUMN_SQL, two_eyes_archive_values
    from domains.archive import actions as archive_actions

    # The bars through the LPS's last day: the family's LPS volume is measured on
    # them (his word Mon 12/10/2026), so without them that column would be empty.
    days = pd.bdate_range(end="2026-03-06", periods=260)
    bars = pd.DataFrame({"Open": 95.0, "High": 99.0, "Low": 93.0, "Close": 97.0,
                         "Volume": 1000.0}, index=days)
    row = seed_row_from_result(to_result(_fired_read(with_mini=True, lps_box="mini"), frame=bars))
    family = two_eyes_archive_values(row.get, prefixed=False)
    empty = {c for c, v in family.items() if v is None}
    assert empty == {"two_eyes_parent_end_date", "two_eyes_mini_end_date", "two_eyes_clarity_json"}, \
        f"only live end days and clarity unmeasured by this legacy-shaped read may be empty: {sorted(empty)}"
    assert family["two_eyes_has_mini"] == 1 and set(family) == set(TWO_EYES_COLUMN_SQL)

    for fn in (seed.seed_archive, archive_actions.add_setup_manually):
        calls = [n for n in ast.walk(ast.parse(inspect.getsource(fn)))
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "two_eyes_archive_values"]
        assert calls, f"{fn.__name__} no longer calls the family producer"
        for call in calls:
            prefixed = {k.arg: k.value for k in call.keywords}["prefixed"]
            assert isinstance(prefixed, ast.Constant) and prefixed.value is False, \
                f"{fn.__name__} reads a re-keyed row and must pass prefixed=False"


def test_an_unknown_setup_count_stays_unknown_on_a_failed_nights_line(monkeypatch, capsys):
    """A failure's line carries the refused rows, but the setup count is not
    known there: it is printed empty, parsed as None, and never shown as a
    zero nobody counted — nor does an empty count drop the refused one."""
    import run_screener
    from webapp.backend.services.scan_runner import _parse_scan_result

    def fails_after_refusing(**k):
        exc = RuntimeError("the lane broke after the archive")
        exc.n_refused = 1
        raise exc

    monkeypatch.setattr(run_screener, "run_scan_and_export", fails_after_refusing)
    monkeypatch.setattr(sys, "argv", ["run_screener.py"])
    with pytest.raises(RuntimeError):
        run_screener.main()
    counts = _parse_scan_result(capsys.readouterr().out)
    assert counts.n_setups is None
    assert counts.n_refused == 1


def test_an_etf_universe_that_fails_after_refusing_rows_still_counts(monkeypatch):
    """Not only the all-refused failure: an ETF universe whose archive refused
    some rows and then failed in the lane used to vanish into a None."""
    from types import SimpleNamespace

    from core.pipeline.screening import scan_job

    primary, etf = SimpleNamespace(key="us_stocks"), SimpleNamespace(key="us_sectors")
    monkeypatch.setattr(scan_job, "all_universes", lambda: [primary, etf])

    def scan(mode, universe):
        if universe is etf:
            exc = RuntimeError("the lane broke after the archive")
            exc.n_refused = 2
            raise exc
        return scan_job.ScanExportResult(n_setups=5, n_archived=5)

    monkeypatch.setattr(scan_job, "run_scan_and_export", scan)
    assert scan_job.run_all_universe_scans()["us_sectors"].n_refused == 2


def test_his_dsgn_fills_both_boxes_through_the_real_writer(writer_on_a_scratch_db, monkeypatch):
    """Build task 13: the stage that FINDS the mini exists. His DSGN drawing, read on his last receding day
    (Mon 30/03/2026) by the new reader itself, crosses the adapter into the real writer as one row with both
    pairs — his parent 10.31 / 9.00 and the size-eligible mini 10.745 / 9.82 with its own anchor days — one trigger, the LPS
    read against the mini, the flag 1."""
    from engine_alpha import two_eyes_numbers as M

    monkeypatch.setattr(M, "MINI_ENABLED", True)     # the stage is sunset (Fri 30/10/2026) and pinned here behind its switch
    from engine_alpha import two_eyes
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.regression.marks_corpus import load_corpus, setup_key

    setup = next(s for s in load_corpus() if s["ticker"] == "DSGN")
    frames, _ = load_sealed_fixture()
    raw = fixture_frame(frames, setup_key(setup), "DSGN")
    read = two_eyes.read("DSGN", raw.loc[:pd.Timestamp("2026-03-30")])
    assert read.fired and read.mini is not None
    stored = _archive_one(writer_on_a_scratch_db, read)
    assert (round(stored.two_eyes_parent_r_price, 2), stored.two_eyes_parent_r_anchor_date) == (10.31, "2025-12-05")
    assert (round(stored.two_eyes_parent_s_price, 2), stored.two_eyes_parent_s_anchor_date) == (9.0, "2025-12-10")
    assert (round(stored.two_eyes_mini_r_price, 2), stored.two_eyes_mini_r_anchor_date) == (10.74, "2026-02-03")
    assert (round(stored.two_eyes_mini_s_price, 2), stored.two_eyes_mini_s_anchor_date) == (9.82, "2026-01-30")
    assert stored.two_eyes_mini_opened_date == "2026-01-30" and stored.two_eyes_mini_end_date is None
    assert stored.two_eyes_lps_read_against == "mini" and stored.two_eyes_has_mini == 1
    assert round(stored.trigger_price, 2) == 10.70 if hasattr(stored, "trigger_price") else True
