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
    silc = rows["SILC:2026-04-13"]
    assert silc["box"] == "OTHER" and silc["why"] == lps.OVER_RESISTANCE
    assert silc["on_last"]["pullback"].refused == (lps.OVER_RESISTANCE,)
    # His buy day made a lower low as well: the pullback goes on, and the board says so.
    assert rows["DLX:2026-04-13"]["strict"] and rows["DLX:2026-04-13"]["on_buy"]["read"].state == lps.FIRED
    # How each is drawn: the LPS with its trigger, the LPS the door keeps out, the buy day, the refused pullback.
    looks = {key: core_board.pullback_look(row["on_last"])[1] for key, row in rows.items()}
    assert looks == {"SYRE:2026-02-19": "trigger", "DLX:2026-04-13": "trigger",
                     "JAZZ:2026-02-24": "not scanned; trigger", "YPF:2026-05-18": "crossed",
                     "SILC:2026-04-13": "no LPS"}
    assert core_board.pullback_look(syre["on_buy"])[1] == "crossed"


def test_the_board_counts_what_the_rows_say_and_puts_the_misses_first(rows):
    from tools.calibration import core_board

    got = list(rows.values())
    board = core_board.format_board(got)
    assert "FIRES ON HIS DAY AT HIS TRIGGER: 2 of 5" in board
    assert "THE BOX: HIS 2 · CLOSE 1 · OTHER 2 · NONE 0" in board
    assert "crossed, nothing on the board 1" in board and "the pullback goes on 1 (DLX:2026-04-13)" in board
    assert [r["strict"] for r in core_board.misses_first(got)] == [False, False, False, True, True]


def test_the_board_and_the_one_door_agree_on_every_one_of_his_35():
    """The board reads the reader and asks the universe door's own function itself, so it can draw the lines of
    a chart the door refuses. What it counts as a fire is what the one door returns, chart for chart, and the
    leg it names is the leg the door names."""
    import pandas as pd

    from engine_alpha import reader
    from tools.calibration import core_board
    from tools.regression.marks_corpus import load_corpus
    from core.calibration.replay import flag_capture, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    got = core_board.run_board(load_corpus(), frames)
    assert len(got) == 35
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        for row in got:
            watch, on_last = {}, row["on_last"]
            result = reader.evaluate_ticker(row["ticker"], row["raw"].loc[:pd.Timestamp(row["last"])], watch=watch)
            assert isinstance(result, dict) == on_last["fired"], row["key"]
            assert (watch["state"] == "not scanned") == (on_last["door"] is not None), row["key"]
            assert on_last["door"] is None or watch["why"] == on_last["door"], row["key"]
            assert not on_last["fired"] or result["_trigger_price"] == on_last["read"].lps.trigger_price, row["key"]


def test_a_junk_chart_is_read_on_every_day_of_its_window_and_aef_fires_on_none(tmp_path):
    from engine_alpha.two_eyes import lps
    from tools.calibration import core_board
    from tools.regression import negative_corpus

    frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c["ticker"] == "AEF")
    row = core_board.junk_row(case, frames["AEF"])
    assert len(row["reads"]) == 10 and row["fires"] == []
    said = {core_board.why_silent(r) for r in row["reads"]}
    assert lps.SLICE in said and lps.OVER_RESISTANCE in said
    assert any(lps.SELLERS_RISING in (why or "") for why in said)
    board = core_board.format_junk([row])
    assert "charts that fire on any day of their window: 0 of 1" in board and "silent: AEF" in board


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
