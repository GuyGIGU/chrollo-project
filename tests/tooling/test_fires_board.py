"""The fires board (Wed 28/10/2026): one switch plus one run measures a reading of his against his live drawings.
What is pinned here is the plumbing, hermetically: the switches are the walk's bools and nothing else, an override
is set for the run and put back, the journal is copied through the backup API with the WAL included and read in
the export's shape, and the board counts what the rows say. The reading itself is the core board's, proved there."""
from __future__ import annotations
from _paths import REPO_ROOT

import os
import sqlite3

import pytest

_ROOT = str(REPO_ROOT)


def test_the_switches_are_the_walks_bools_and_a_switch_is_zero_or_one():
    from engine_alpha import two_eyes_numbers as M
    from tools.calibration import fires_board

    names = fires_board.switch_names()
    assert set(names) == {"ONE_BAR_PAIR", "GAP_BAR_LOW_IS_REACTION", "WIDE_ENDS", "CLIMAX_BAR_OWN_REACTION",
                          "WRAP_TAKES_OVER", "RESPECT_ELECTS", "MINI_ENABLED"}
    assert all(isinstance(getattr(M, name), bool) for name in names)
    assert fires_board.parse_switch("ONE_BAR_PAIR=0") == ("ONE_BAR_PAIR", False)
    assert fires_board.parse_switch("wide_ends=on") == ("WIDE_ENDS", True)
    with pytest.raises(ValueError, match="not a switch"):
        fires_board.parse_switch("BOX_DAYS=0")             # a number, never a switch
    with pytest.raises(ValueError, match="not a switch"):
        fires_board.parse_switch("ONE_BAR_PAIR")
    with pytest.raises(ValueError, match="0 or 1"):
        fires_board.parse_switch("ONE_BAR_PAIR=maybe")


def test_an_override_holds_for_the_run_and_is_put_back_even_when_the_run_breaks():
    from engine_alpha import two_eyes_numbers as M
    from tools.calibration import fires_board

    assert M.ONE_BAR_PAIR is True
    with fires_board.switched({"ONE_BAR_PAIR": False}):
        assert M.ONE_BAR_PAIR is False
    assert M.ONE_BAR_PAIR is True
    with pytest.raises(RuntimeError):
        with fires_board.switched({"ONE_BAR_PAIR": False, "WIDE_ENDS": 0}):
            assert (M.ONE_BAR_PAIR, M.WIDE_ENDS) == (False, False)
            raise RuntimeError("the read broke")
    assert (M.ONE_BAR_PAIR, M.WIDE_ENDS) == (True, True)
    assert fires_board.switch_words({}) == "as built (every switch on)"
    assert fires_board.switch_words({"WIDE_ENDS": False, "ONE_BAR_PAIR": True}) == "ONE_BAR_PAIR=1, WIDE_ENDS=0"


def _journal(path: str) -> sqlite3.Connection:
    """A journal with the two tables the board reads, in WAL mode, two marks: one with an LPS and a trigger, one
    with nothing drawn on it. Left OPEN so the second mark's rows sit in the -wal."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=wal")
    con.execute("""CREATE TABLE calibration_marks (id INTEGER PRIMARY KEY, ticker TEXT, as_of_date TEXT,
        resistance REAL, support REAL, box_start_date TEXT, box_end_date TEXT, r_anchor_date TEXT,
        s_anchor_date TEXT, first_rail TEXT, trigger_date TEXT, trigger_price REAL, frame_digest TEXT)""")
    con.execute("""CREATE TABLE calibration_mark_events (id INTEGER PRIMARY KEY, mark_id INTEGER,
        event_type TEXT, start_date TEXT, end_date TEXT, band_high REAL, band_low REAL)""")
    con.execute("INSERT INTO calibration_marks VALUES (1, 'SYRE', '2026-02-19', 30.5, 26.1, '2025-12-01', "
                "'2026-02-17', '2025-12-01', '2025-12-10', 'resistance', '2026-02-18', 30.2, '" + "a" * 64 + "')")
    con.execute("INSERT INTO calibration_mark_events VALUES (1, 1, 'lps', '2026-02-12', '2026-02-17', NULL, NULL)")
    con.execute("INSERT INTO calibration_mark_events VALUES (2, 1, 'sos', '2026-01-20', '2026-01-22', NULL, NULL)")
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    # The second mark is written AFTER the checkpoint and the connection stays open: it lives in the -wal only.
    con.execute("INSERT INTO calibration_marks VALUES (2, 'CLDT', '2026-10-09', 4.1, 3.6, '2026-08-01', "
                "'2026-10-07', '2026-08-01', '2026-08-12', 'resistance', NULL, NULL, '" + "b" * 64 + "')")
    con.commit()
    return con


def test_the_journal_is_copied_through_the_backup_api_with_the_wal_and_read_in_the_exports_shape(tmp_path):
    from tools.calibration import fires_board

    src = str(tmp_path / "trading_journal.db")
    live = _journal(src)
    try:
        assert os.path.getsize(src + "-wal") > 0, "the second mark is in the -wal"
        before = open(src, "rb").read()
        copy = fires_board.copy_journal(src, str(tmp_path / "copy.db"))
        assert open(src, "rb").read() == before, "the live file was not touched"
        rows = sqlite3.connect(copy).execute("SELECT ticker FROM calibration_marks ORDER BY id").fetchall()
        assert rows == [("SYRE",), ("CLDT",)], "a file copy would have dropped CLDT with the -wal"
        setups, skipped = fires_board.live_setups(copy)
    finally:
        live.close()
    assert skipped == [("CLDT:2026-10-09", fires_board.NO_LPS)]
    (syre,) = setups
    assert syre["ticker"] == "SYRE" and syre["as_of"] == "2026-02-19" and syre["lps"] == ["2026-02-12", "2026-02-17"]
    assert syre["rails_drawn"] == {"R": 30.5, "S": 26.1} and syre["anchors"] == {"R": "2025-12-01", "S": "2025-12-10"}
    assert (syre["trigger"], syre["trigger_price"], syre["sos"]) == ("2026-02-18", 30.2, [["2026-01-20", "2026-01-22"]])
    with pytest.raises(FileNotFoundError):
        fires_board.copy_journal(str(tmp_path / "nowhere.db"), str(tmp_path / "x.db"))


def test_the_board_counts_what_the_rows_say_and_names_the_misses_and_the_skipped():
    from tools.calibration import fires_board

    def row(key, box, fired, strict, off=0.0, why=None):
        return {"key": key, "box": box, "fired": fired, "strict": strict, "trigger": None if not fired else 10.0,
                "his_trigger": 10.0, "off": None if not fired else off, "why": why}

    rows = [row("A:2026-01-01", "HIS", True, True), row("B:2026-01-01", "CLOSE", True, True),
            row("C:2026-01-01", "OTHER", True, False, off=0.9),
            row("D:2026-01-01", "HIS", False, False, why="the universe door (sma50)")]
    text = fires_board.format_board(rows, [("CLDT:2026-10-09", fires_board.NO_TRIGGER)], {"ONE_BAR_PAIR": False})
    assert "switches: ONE_BAR_PAIR=0" in text
    assert "HIS 1 fired / 1 not · CLOSE 1 fired / 0 not · OTHER 1 fired / 0 not" in text
    assert "FIRES ON HIS DAY AT HIS TRIGGER (to the cent): 2 of 4" in text
    assert "within half a daily range of his: 2 of 4" in text
    assert "D:2026-01-01" in text and "the universe door (sma50)" in text
    assert "C:2026-01-01" in text and "(+0.90 ranges)" in text and "fired, not on his day at his trigger" in text
    assert "skipped: CLDT:2026-10-09 (no trigger drawn)" in text
    assert "A:2026-01-01" not in text.split("the misses:")[1]
