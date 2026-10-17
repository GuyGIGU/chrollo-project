"""The box gap tool (his "fix the box", Fri 17/10/2026): the cause words, a fix read as a drawing, the fixes read
read-only from a database that may not have the table yet, and one sealed drawing through the whole board."""
from __future__ import annotations

import datetime as dt
import sqlite3
from types import SimpleNamespace

import pytest

from engine_alpha.two_eyes import walk
from tools.calibration import box_gap, walk_board
from tools.regression.marks_corpus import load_corpus, setup_key
from core.calibration.replay import fixture_frame, load_sealed_fixture


def _row(verdict="OTHER", his_pair=None, box=None, why=None):
    return {"verdict": verdict, "his_pair": his_pair, "box": box, "why": why, "days": [dt.date(2026, 1, 1)]}


def test_every_drawing_has_one_cause_in_words():
    assert box_gap.cause(_row("HIS")) == "his box"
    assert box_gap.cause(_row("CLOSE")).startswith("close")
    assert box_gap.cause(_row()) == "his pair is not a pair the rule lists"
    unfit = SimpleNamespace(unfit="not a daily range tall", birth_bar=None, r_back=None, s_back=None)
    assert box_gap.cause(_row(his_pair=unfit)) == "his pair can never be a box: not a daily range tall"
    young = SimpleNamespace(unfit=None, birth_bar=None, r_back=3, s_back=None)
    assert box_gap.cause(_row(his_pair=young)) == "his pair is no box by his day: the bars not back at support"
    short = SimpleNamespace(unfit=None, birth_bar=None, r_back=3, s_back=4)
    assert box_gap.cause(_row(his_pair=short)) == "his pair is no box by his day: under fifteen days"
    born = SimpleNamespace(unfit=None, birth_bar=9, r_back=3, s_back=4)
    assert box_gap.cause(_row("NONE", his_pair=born)) == "no box shown"
    shown = SimpleNamespace(birth_bar=7)
    assert box_gap.cause(_row(his_pair=born, box=shown, why=walk.FIRST_BOX)) == \
        "his pair is a box, another was a box first"
    assert box_gap.cause(_row(his_pair=born, box=shown, why=walk.LIVE_TREND)) == \
        f"his pair is a box, another is shown by a hand-over: {walk.LIVE_TREND}"


def test_a_fix_is_read_as_a_drawing_on_the_chart_he_fixed():
    fix = {"ticker": "AAPL", "scan_day": "2026-10-16", "resistance": 345.34, "r_day": "2026-09-22",
           "support": 334.30, "s_day": "2026-09-24", "reader_resistance": 345.34, "reader_support": 334.30,
           "revision": 2}
    setup = box_gap.fix_setup(fix)
    assert setup_key(setup) == "AAPL:fix 2026-10-16"
    assert (setup["as_of"], setup["anchors"], setup["box"]) == \
        ("2026-10-16", {"R": "2026-09-22", "S": "2026-09-24"}, ["2026-09-22", "2026-10-16"])
    assert setup["rails_drawn"] == {"R": 345.34, "S": 334.30} and setup["trigger"] is None
    assert setup["lps"] == ["2026-10-16", "2026-10-16"], "no LPS window: his day is the chart's last day"


def test_the_fixes_are_read_read_only_and_a_database_without_the_table_is_empty(tmp_path):
    path = tmp_path / "journal.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE other (id INTEGER)")
    con.commit()
    con.close()
    assert box_gap.load_fixes(str(path)) == []
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE box_fixes (id INTEGER PRIMARY KEY, ticker TEXT, scan_day TEXT, resistance REAL, "
                "r_day TEXT, support REAL, s_day TEXT, reader_resistance REAL, reader_r_day TEXT, "
                "reader_support REAL, reader_s_day TEXT, reader_opened_day TEXT, ruleset TEXT, note TEXT, "
                "revision INTEGER)")
    con.execute("INSERT INTO box_fixes VALUES (1, 'NGL', '2026-01-16', 10.29, '2025-12-11', 9.38, '2025-12-15', "
                "NULL, NULL, NULL, NULL, NULL, '', NULL, 1)")
    con.commit()
    con.close()
    (fix,) = box_gap.load_fixes(str(path))
    assert (fix["ticker"], fix["scan_day"], fix["resistance"], fix["s_day"]) == ("NGL", "2026-01-16", 10.29, "2025-12-15")
    assert box_gap.load_fixes(str(tmp_path / "missing.db")) == []


@pytest.mark.slow
def test_one_sealed_drawing_runs_through_the_board():
    frames, _ = load_sealed_fixture()
    setup = next(s for s in load_corpus() if s["ticker"] == "VIK")
    row = walk_board.score_setup(setup, fixture_frame(frames, setup_key(setup), "VIK"))
    row["population"], row["setup"] = "sealed", setup
    assert box_gap.cause(row) == "his box", "VIK is HIS on the walk board"
    board = box_gap.format_board([row], [])
    assert "agree 1 · differ 0" in board and "HIS 1 · CLOSE 0" in board
