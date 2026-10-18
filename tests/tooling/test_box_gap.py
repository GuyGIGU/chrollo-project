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
    assert fix["events"] == [], "the events table is younger than the fixes: none placed yet"
    assert box_gap.load_fixes(str(tmp_path / "missing.db")) == []
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE box_fix_events (id INTEGER PRIMARY KEY, fix_id INTEGER, kind TEXT, first_day TEXT, "
                "last_day TEXT, price REAL, band_high REAL, band_low REAL, label TEXT)")
    con.execute("INSERT INTO box_fix_events VALUES (1, 1, 'lps', '2026-01-13', '2026-01-16', 9.5, NULL, NULL, NULL)")
    con.execute("INSERT INTO box_fix_events VALUES (2, 1, 'spring', '2025-12-29', '2025-12-29', 9.1, NULL, NULL, NULL)")
    con.execute("INSERT INTO box_fix_events VALUES (3, 99, 'span', '2026-01-02', '2026-01-05', NULL, NULL, NULL, 'orphan')")
    con.commit()
    con.close()
    (fix,) = box_gap.load_fixes(str(path))
    assert [e["kind"] for e in fix["events"]] == ["spring", "lps"], "his events ride with their fix, oldest first"
    assert box_gap.fix_setup(fix)["events"] == fix["events"]


@pytest.mark.slow
def test_one_sealed_drawing_runs_through_the_board():
    frames, _ = load_sealed_fixture()
    setup = next(s for s in load_corpus() if s["ticker"] == "VIK")
    row = walk_board.score_setup(setup, fixture_frame(frames, setup_key(setup), "VIK"))
    row["population"], row["setup"] = "sealed", setup
    assert box_gap.cause(row) == "his box", "VIK is HIS on the walk board"
    board = box_gap.format_board([row], [])
    assert "agree 1 · differ 0" in board and "HIS 1 · CLOSE 0" in board


def _read(events=(), lps=None, minis=()):
    """A reader's record as event_agreement reads it: events with a kind, a day and a price; the LPS's two days;
    the mini boxes."""
    ev = [SimpleNamespace(kind=k, day=dt.date.fromisoformat(d), price=p) for k, d, p in events]
    the_lps = SimpleNamespace(start_day=dt.date.fromisoformat(lps[0]), end_day=dt.date.fromisoformat(lps[1])) if lps else None
    boxes = [SimpleNamespace(role="mini", resistance=SimpleNamespace(price=r), support=SimpleNamespace(price=s_),
                             opened_day=dt.date.fromisoformat(o), end_day=None) for r, s_, o in minis]
    return SimpleNamespace(events=ev, lps=the_lps, boxes=boxes)


def _fix_row(his_events, read):
    """His AAPL on its October days, the bars made up flat so the words, not the prices, are under test."""
    days = [dt.date(2026, 10, d) for d in (1, 2, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16)]
    import pandas as pd
    prepared = pd.DataFrame({"Open": 340.0, "High": 345.0, "Low": 335.0, "Close": 341.0}, index=pd.to_datetime(days))
    return {"key": "AAPL:fix 2026-10-16", "days": days, "unit": 6.0, "read": read, "prepared": prepared,
            "population": "fix", "verdict": "HIS", "his_pair": None, "box": None, "why": None,
            "setup": {"events": his_events}}


def test_his_events_are_read_against_the_readers_words_and_the_former_lps_names_the_earlier_entry():
    his = [{"kind": "spring", "first_day": "2026-10-01", "last_day": "2026-10-01", "price": 325.81},
           {"kind": "sos", "first_day": "2026-10-12", "last_day": "2026-10-13", "price": 348.15},
           {"kind": "upthrust", "first_day": "2026-10-08", "last_day": "2026-10-08", "price": 349.0},
           {"kind": "lps", "first_day": "2026-10-14", "last_day": "2026-10-16", "price": 340.46},
           {"kind": "former_lps", "first_day": "2026-10-06", "last_day": "2026-10-07", "price": 330.6},
           {"kind": "mini", "first_day": "2026-10-13", "last_day": "2026-10-16", "band_high": 348.0, "band_low": 340.5},
           {"kind": "span", "first_day": "2026-10-02", "last_day": "2026-10-05", "label": "the dull middle"}]
    read = _read(events=(("spring", "2026-10-01", 325.81), ("SOS", "2026-10-13", 348.15)), lps=("2026-10-15", "2026-10-16"),
                 minis=((348.1, 340.4, "2026-10-13"),))
    lines = box_gap.event_agreement(_fix_row(his, read))
    by = {line["kind"]: line for line in lines}
    assert by["spring"]["verdict"] == "agree" and by["spring"]["words"] == "the reader's spring on 01/10 too"
    assert by["sos"]["verdict"] == "agree", "the reader's SOS top falls inside his launch-to-top span"
    assert by["upthrust"]["verdict"] == "differ" and by["upthrust"]["words"] == "the reader names no upthrust on this box"
    assert by["lps"]["verdict"] == "agree" and "shares a day" in by["lps"]["words"]
    assert by["former_lps"]["verdict"] == "noted" and by["former_lps"]["earlier_by"] == 6
    assert by["former_lps"]["words"].startswith("the entry was earlier: the reader's LPS begins 6 trading days after your former LPS ended (15/10)")
    assert by["mini"]["verdict"] == "agree", "both lines within half a range"
    assert by["span"]["verdict"] == "noted" and by["span"]["words"] == 'your word: "the dull middle"'
    # The reader elsewhere: a spring on another day, the LPS on his former LPS, a mini with other lines.
    other = _read(events=(("spring", "2026-10-07", 331.0),), lps=("2026-10-06", "2026-10-07"), minis=((352.0, 345.0, "2026-10-13"),))
    by = {line["kind"]: line for line in box_gap.event_agreement(_fix_row(his, other))}
    assert by["spring"]["verdict"] == "differ" and by["spring"]["words"] == "the reader's spring is on 07/10 at 331.00"
    assert by["sos"]["words"] == "the reader names no SOS on this box"
    assert by["lps"]["verdict"] == "differ" and by["lps"]["words"] == "the reader's LPS is 06/10 to 07/10"
    assert by["former_lps"]["words"] == "the reader's LPS sits on your former LPS: it reads the earlier entry as tonight's"
    assert by["mini"]["verdict"] == "differ" and by["mini"]["words"] == "the reader's mini is 352.00 / 345.00 from 13/10"
    assert box_gap.event_agreement({**_fix_row([], other)}) == [], "no events placed: nothing to say"


def test_the_events_block_counts_per_kind_and_prints_the_bars_under_a_disagreement():
    his = [{"kind": "spring", "first_day": "2026-10-01", "last_day": "2026-10-01", "price": 325.81},
           {"kind": "lps", "first_day": "2026-10-14", "last_day": "2026-10-16", "price": 340.46},
           {"kind": "former_lps", "first_day": "2026-10-06", "last_day": "2026-10-07", "price": 330.6}]
    row = _fix_row(his, _read(events=(("spring", "2026-10-07", 331.0),), lps=("2026-10-15", "2026-10-16")))
    block = box_gap.format_events([row, {"key": "X", "refused": "no bars"}])
    assert "HIS EVENTS on 1 fixes: spring 0/1 · LPS 1/1  (agree/placed)" in block
    assert "former LPS placed 1: the entry was earlier on 1 (the reader's LPS 6-6 trading days after it)" in block
    assert "DIFFER  spring 01/10 at 325.81 · the reader's spring is on 07/10 at 331.00" in block
    assert "Thu 01/10  O 340.00  H 345.00  L 335.00  C 341.00" in block, "the bars under the disagreement"
    assert "Fri 02/10  O 340.00" in block, "one bar of padding after his day"
    assert "agree   LPS 14/10-16/10 at 340.46" in block
    assert box_gap.format_events([_fix_row([], None)]) == "", "no events on any fix: no block"
    assert "Wed 14/10" not in block.split("agree   LPS")[1], "no bars under an agreement"
