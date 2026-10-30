"""The core's board (task 12a): what it says about a drawing and a junk chart, pinned on four of his drawings and
on AEF, so the numbers he is shown at the core sitting are the reader's and not the board's own invention."""
from __future__ import annotations
from _paths import REPO_ROOT

import datetime as dt
import os

import pytest

_ROOT = str(REPO_ROOT)


@pytest.fixture(scope="module")
def rows() -> dict:
    from tools.calibration import core_board
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    wanted = ("SYRE:2026-02-19", "JAZZ:2026-02-24", "YPF:2026-05-18", "SILC:2026-04-13", "DLX:2026-04-13")
    setups = {setup_key(s): s for s in load_corpus() if setup_key(s) in wanted}
    assert sorted(setups) == sorted(wanted)
    return {key: core_board.score_setup(s, fixture_frame(frames, key, s["ticker"])) for key, s in setups.items()}


def test_the_box_is_his_close_or_other_against_his_two_lines():
    from engine_alpha.two_eyes import Box, Line
    from tools.calibration import core_board

    day = dt.date(2026, 3, 2)

    def box(r, s):
        return Box(resistance=Line(r, day), support=Line(s, day), opened_day=day)

    rails = {"R": 100.0, "S": 90.0}
    assert core_board.verdict(box(100.0, 90.0), rails, 2.0) == "HIS"
    assert core_board.verdict(box(100.9, 89.2), rails, 2.0) == "CLOSE", "both within half a two-point range"
    assert core_board.verdict(box(101.1, 90.0), rails, 2.0) == "OTHER", "resistance more than half a range off"
    assert core_board.verdict(None, rails, 2.0) == "NONE"


def test_a_drawing_is_scored_on_his_last_receding_day_and_the_silence_is_named(rows):
    from engine_alpha.two_eyes import lps
    from tools.calibration import core_board

    syre = rows["SYRE:2026-02-19"]
    assert (syre["box"], syre["strict"], syre["why"]) == ("HIS", True, None)
    assert syre["on_last"]["day"] == dt.date(2026, 2, 17) and syre["on_buy"]["read"].state == lps.CROSSED
    jazz = rows["JAZZ:2026-02-24"]
    assert jazz["box"] == "HIS" and not jazz["strict"] and jazz["why"] == f"{core_board.DOOR} (sma50)"
    assert jazz["on_last"]["read"].fired, "the read fires: the door is what refuses the day"
    ypf = rows["YPF:2026-05-18"]
    assert not ypf["strict"] and ypf["why"] == core_board.ADVANCES + ": the buy day"
    # SILC: on the box of tasks 10 and 11 his window was refused by sentence four (the reader's box sat far under
    # his); on the box of the rule he settled it is his to the cent — the bars resting on his support are respect
    # (his word on the pictures, Thu 01/10/2026) — and the read fires on his day.
    silc = rows["SILC:2026-04-13"]
    assert (silc["box"], silc["strict"], silc["why"]) == ("HIS", True, None)
    assert silc["on_last"]["pullback"].refused == ()
    # His buy day made a lower low as well: the pullback goes on, and the board says so.
    assert rows["DLX:2026-04-13"]["strict"] and rows["DLX:2026-04-13"]["on_buy"]["read"].state == lps.FIRED
    # How each is drawn: the LPS with its trigger, the LPS the door keeps out, the buy day, the refused pullback.
    looks = {key: core_board.pullback_look(row["on_last"])[1] for key, row in rows.items()}
    assert looks == {"SYRE:2026-02-19": "trigger", "DLX:2026-04-13": "trigger",
                     "JAZZ:2026-02-24": "not scanned; trigger", "YPF:2026-05-18": "crossed",
                     "SILC:2026-04-13": "trigger"}
    assert core_board.pullback_look(syre["on_buy"])[1] == "crossed"


def test_the_board_counts_what_the_rows_say_and_puts_the_misses_first(rows):
    from tools.calibration import core_board

    got = list(rows.values())
    board = core_board.format_board(got)
    assert "FIRES ON HIS DAY AT HIS TRIGGER: 3 of 5" in board
    assert "THE BOX: HIS 4 · CLOSE 1 · OTHER 0 · NONE 0" in board
    assert "crossed, nothing on the board 2" in board and "the pullback goes on 1 (DLX:2026-04-13)" in board
    assert [r["strict"] for r in core_board.misses_first(got)] == [False, False, True, True, True]


def test_the_board_and_the_one_door_agree_on_every_one_of_his_drawings():
    """The board reads the reader and asks the universe door's own function itself, so it can draw the lines of
    a chart the door refuses. What it counts as a fire is what the one door returns, chart for chart, and the
    leg it names is the leg the door names."""
    import pandas as pd

    from engine_alpha import reader
    from tools.calibration import core_board
    from tools.regression.marks_corpus import load_corpus
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    drawings = load_corpus()
    got = core_board.run_board(drawings, frames)
    assert len(got) == len(drawings) >= 37    # the population follows his drawings (his ruling, Tue 08/09/2026)
    for row in got:
        watch, on_last = {}, row["on_last"]
        result = reader.evaluate_ticker(row["ticker"], row["raw"].loc[:pd.Timestamp(row["last"])], watch=watch)
        assert isinstance(result, dict) == on_last["fired"], row["key"]
        assert (watch["state"] == "not scanned") == (on_last["door"] is not None), row["key"]
        assert on_last["door"] is None or watch["why"] == on_last["door"], row["key"]
        assert not on_last["fired"] or result["_trigger_price"] == on_last["read"].lps.trigger_price, row["key"]
        # And the box the LPS was read against (task 13): the band the board draws is the band that fired.
        assert not on_last["fired"] or result["_two_eyes_lps_read_against"] == on_last["lps_box"], row["key"]


def test_a_junk_chart_is_read_on_every_day_of_its_window_and_aef_fires_on_its_first_day_only(tmp_path):
    """AEF: the pullback he refused runs from Wed 03/06/2026. Since the wrap rule of Thu 29/10/2026 the one-bar box
    of April (9.04 / 8.66) gives way to the pair inside it, so 9.98 / 9.57 is shown and the pullback's first day
    fires at 10.00 (as on the rule of Thu 01/10/2026); from the second day on it is refused each day by his own
    sentence (tests/engine/test_two_eyes_lps.py)."""
    import datetime as dt

    from engine_alpha.two_eyes import lps
    from tools.calibration import core_board
    from tools.regression import negative_corpus

    frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c["ticker"] == "AEF")
    row = core_board.junk_row(case, frames["AEF"])
    assert len(row["reads"]) == 10 and [f["day"] for f in row["fires"]] == [dt.date(2026, 6, 3)]
    said = [core_board.why_silent(r) or "" for r in row["reads"]]
    assert any(lps.SLICE in why for why in said) and any(lps.UNDER_SUPPORT in why for why in said)
    assert any(lps.SELLERS_RISING in why for why in said)      # the first day fires now, so no "over resistance"
    # How a refused pullback is drawn: grey, "no LPS".
    refused = next(r for r in row["reads"] if r["day"] == dt.date(2026, 6, 4))
    assert core_board.pullback_look(refused)[1] == "no LPS"
    board = core_board.format_junk([row])
    assert "charts that fire on any day of their window: 1 of 1" in board and "silent: AEF" not in board


def test_the_pages_draw_bars_and_never_candles_and_one_is_written_per_chart(rows, tmp_path):
    import inspect

    from tools.calibration import core_board
    from tools.regression import negative_corpus

    source = inspect.getsource(core_board)
    assert "candlestick" not in source.lower() and "_draw_bars" in source
    frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c["ticker"] == "AEF")
    his = [rows["SYRE:2026-02-19"], rows["SILC:2026-04-13"]]
    his_pages, junk_pages = core_board.render_pages(his, [core_board.junk_row(case, frames["AEF"])], str(tmp_path))
    assert [row["key"] for row, _ in his_pages] == ["SILC:2026-04-13", "SYRE:2026-02-19"], "misses first"
    assert len(junk_pages) == 1
    for _, path in his_pages + junk_pages:
        assert os.path.getsize(path) > 20_000, path
    sheet = core_board.write_contact_sheet(his_pages, junk_pages, str(tmp_path))
    text = open(sheet, encoding="utf-8").read()
    assert "Your 2 drawings" in text and "The 1 junk charts" in text and "his_SYRE_2026-02-19.png" in text


def test_the_board_prints_the_story_against_his_drawn_events(rows):
    """Build task 12b: the board scores the reader's own story on his last receding day against the events he
    drew, by reading the events off the record (it types no rule of its own), and tallies the state words."""
    from tools.calibration import core_board

    got = list(rows.values())
    hits = core_board.story_hits(rows["SYRE:2026-02-19"]["setup"], rows["SYRE:2026-02-19"]["raw"],
                                 rows["SYRE:2026-02-19"]["on_last"]["read"])
    assert [(kind, hit) for kind, _, hit in hits] == [("sos", True), ("phase_c", True)]
    # A read with no events lands nothing: the hits come off Read.events and nowhere else.
    import dataclasses
    bare = dataclasses.replace(rows["SYRE:2026-02-19"]["on_last"]["read"], events=())
    assert not any(hit for _, _, hit in core_board.story_hits(rows["SYRE:2026-02-19"]["setup"],
                                                              rows["SYRE:2026-02-19"]["raw"], bare))
    board = core_board.format_story(got)
    # The fixture holds a handful of his drawings; the line of each word is the count of its hits among them.
    every = [h for r in got for h in core_board.story_hits(r["setup"], r["raw"], r["on_last"]["read"])]
    for kind, name in (("sos", "THE SOS"), ("phase_c", "the spring"), ("last_supper", "the last supper")):
        mine = [hit for k, _, hit in every if k == kind]
        assert f"{name}: {sum(mine)} of {len(mine)}" in board, (name, board)
    assert sum(1 for k, _, _ in every if k == "sos") >= 3
    assert "could not be read on: 0 of" in board
    assert "state words, his drawings: " in board


def test_the_board_counts_the_names_that_move_night_to_night():
    """A count in a document is reproduced by a tool: the committed words whose name moved from one night to the
    next while the box shown stayed the same. VIK alone, from three days before his last receding day to his
    as-of day: his upthrust's top is THE SOS at first and THE upthrust once the middle of the box has passed it,
    so THE SOS's name is counted as moved and the day carries another word."""
    from core.calibration.replay import load_sealed_fixture
    from tools.calibration import core_board
    from tools.regression.marks_corpus import load_corpus

    frames, _ = load_sealed_fixture()
    vik = [s for s in load_corpus() if s["ticker"] == "VIK"]
    moves = core_board.name_moves(vik, frames, back=3)
    assert moves["nights"] >= 6 and moves["same_box"] == moves["pairs"] == moves["nights"] - 1
    assert moves["renamed"].get("SOS", 0) + moves["gone"].get("SOS", 0) >= 1
    board = core_board.format_name_moves(moves)
    total = sum(moves["gone"].values()) + sum(moves["renamed"].values())
    assert f"committed names moved {total} times in {moves['same_box']} pairs of nights" in board


def test_the_board_draws_the_mini_and_names_the_box_the_lps_was_read_against(tmp_path, monkeypatch):
    """DSGN (task 13): the mini thinner beside the parent and his band dotted red over its own days; the words
    name the mini and which box the LPS was read against and how; the pullback drawn is the one measured against
    the mini; the board's mini lines sit outside the strict headline."""
    from engine_alpha import two_eyes_numbers as M

    monkeypatch.setattr(M, "MINI_ENABLED", True)     # the stage is sunset (Fri 30/10/2026) and pinned here behind its switch
    from engine_alpha import two_eyes
    from tools.calibration import core_board
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    setup = next(s for s in load_corpus() if s["ticker"] == "DSGN")
    row = core_board.score_setup(setup, fixture_frame(frames, setup_key(setup), "DSGN"))
    on_last = row["on_last"]
    assert on_last["read"].mini is not None and on_last["lps_box"] == two_eyes.ROLE_MINI
    assert on_last["pullback"].born_bar == on_last["mini_pair"].birth_bar
    words = core_board._words(on_last["read"], on_last["door"])
    assert "The mini: R 10.74" in words and "read against the mini, in" in words
    pages, _ = core_board.render_pages([row], [], str(tmp_path))
    assert len(pages) == 1 and os.path.getsize(pages[0][1]) > 20_000
    board = core_board.format_board([row])
    assert "FIRES ON HIS DAY AT HIS TRIGGER: 1 of 1" in board
    assert "THE MINI (never counted above): a second box inside the parent on 1 of 1: DSGN:2026-03-31 10.74 / 9.82" in board
    assert "your drawn mini on DSGN:2026-03-31: the reader's mini 10.74 / 9.82 is within half a range of your band 10.97 / 9.90" in board
    assert "the LPS read against the mini on 1 (in 1)" in board and "the mini could not be read: 0" in board


def test_the_letter_is_counted_night_after_night_on_his_drawings():
    """The grade keys off THE SOS, a word that moves between nights; how often the letter moves with it is
    measured, never assumed (council review 2026-10-09, finding 6)."""
    from core.calibration.replay import load_sealed_fixture
    from tools.calibration import core_board
    from tools.regression.marks_corpus import load_corpus, setup_key

    frames, _ = load_sealed_fixture()
    setups = [s for s in load_corpus() if setup_key(s) in ("MTLS:2026-09-04", "ALB:2026-04-13")]
    moves = core_board.grade_moves(setups, frames, back=3)
    assert moves["nights"] >= 8 and 0 < moves["pairs"] < moves["nights"]
    assert 0 <= moves["moves_with_the_sos"] <= moves["moves"] <= moves["pairs"]
    assert set(moves["charts"]) <= {"MTLS:2026-09-04", "ALB:2026-04-13"}
