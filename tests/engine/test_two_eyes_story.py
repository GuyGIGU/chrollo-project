"""Stage 5 of the two-eyes reader: the story (build task 12b, the events by phase).

His sentence that is this task (Sat 26/09/2026): *"the rest is how we interpret the inner price action in the box
that leads us to the rest of the "events" ... we see how it fares against our box and we can interpret said
drawing to visual patterns we can recognize aka: spring, up thrust, sos, lps, mini consolidation and so on
depending on the chronological "phase" of said setup."* And the sentence that bounds it (Sat 19/09/2026):
*"we just got to nail down our core for detecting consolidations and an LPS. the rest is a nice little bonus."*

So the first law of this file: A WORD NEVER COSTS A FIRE. An event and a state word are facts laid beside the
read; nothing that decides a fire reads them.

Step 2 (this section): a place for an event on the record, and the two closed sets. No chart is read yet.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import inspect

import functools

import numpy as np
import pandas as pd
import pytest

from core.calibration.replay import fixture_frame, load_sealed_fixture
from engine_alpha.two_eyes import line_words as LW
from engine_alpha.two_eyes import lps, record, walk
from engine_alpha.two_eyes import method_numbers as M
from engine_alpha.two_eyes.daily_range import calculate_atr
from engine_alpha.two_eyes.swing_line import turn_line, turn_line_floors
from tools.regression.marks_corpus import load_corpus, setup_key

DAY = dt.date(2026, 3, 2)


def _fired_read(**more) -> record.Read:
    line = record.Line(price=10.0, anchor_day=DAY)
    box = record.Box(resistance=line, support=record.Line(9.0, DAY), opened_day=DAY)
    return record.Read(ticker="T", as_of=DAY, boxes=(box,), state=record.FIRED,
                       lps=record.Lps(start_day=DAY, end_day=DAY, read_against=record.ROLE_PARENT,
                                      trigger_price=10.5), **more)


# --------------------------------------------------------------------------- #
# The record: a place for an event                                            #
# --------------------------------------------------------------------------- #
def test_a_read_carries_its_events_and_every_older_field_is_where_it_was():
    read = record.Read(ticker="T")
    assert read.events == () and read.state_days is None
    names = [f.name for f in dataclasses.fields(record.Read)]
    assert names[:9] == ["ticker", "as_of", "boxes", "lps", "trail", "state", "failed", "refusal", "close"], \
        "a later stage fills the record; it never moves a field the adapter and the archive were built against"
    assert names[9:] == ["events", "state_days"]
    assert (read.boxes, read.lps, read.trail, read.state, read.failed, read.refusal, read.close) == \
        ((), None, (), record.NO_LINES, False, None, None)
    # A list handed in is frozen like the boxes and the trail.
    event = record.Event(kind=record.SPRING, day=DAY, price=8.7)
    assert record.Read(ticker="T", events=[event]).events == (event,)


def test_an_event_is_a_word_of_the_closed_set_dated_by_a_day():
    assert record.EVENT_KINDS == ("spring", "spring test", "upthrust", "SOS", "last supper", "Phase D")
    with pytest.raises(ValueError):
        record.Event(kind="shakeout", day=DAY, price=8.7)       # parked by him (Sun 13/09/2026): not a word here
    # A bar index never leaves the reader: a day is a day.
    with pytest.raises(TypeError):
        record.Event(kind=record.SPRING, day=17, price=8.7)
    with pytest.raises(TypeError):
        record.Event(kind=record.SPRING, day=None, price=8.7)   # an event with no day is no event
    stamped = record.Event(kind=record.SOS, day=pd.Timestamp("2026-03-02 00:00"), price=10.4,
                           first_day=pd.Timestamp("2026-02-26"), last_day=pd.Timestamp("2026-03-02"),
                           known_day=pd.Timestamp("2026-03-04"))
    assert (stamped.day, stamped.first_day, stamped.last_day, stamped.known_day) == \
        (DAY, dt.date(2026, 2, 26), DAY, dt.date(2026, 3, 4))
    assert type(stamped.day) is dt.date
    # Provisional until said otherwise, and frozen.
    assert stamped.committed is False and stamped.size is None and stamped.note == ""
    with pytest.raises(dataclasses.FrozenInstanceError):
        stamped.price = 1.0


# --------------------------------------------------------------------------- #
# THE GUARD OF THE TASK: a word never costs a fire                            #
# --------------------------------------------------------------------------- #
def test_whether_a_read_fired_reads_no_event_and_no_state_word():
    """``Read.fired`` is the box, the LPS's trigger and "the read did not crash" — and nothing else. Whatever
    the story names and whatever word the chart carries, a fire stays a fire and a quiet chart stays quiet."""
    spring = record.Event(kind=record.SPRING, day=DAY, price=8.7, committed=True)
    upthrust = record.Event(kind=record.UPTHRUST, day=DAY, price=11.2)
    fired, quiet = _fired_read(), record.Read(ticker="T", as_of=DAY)
    assert fired.fired and not quiet.fired
    for word in record.STATE_WORDS + (record.READ_FAILED, "a word nobody knows"):
        for events in ((), (spring,), (spring, upthrust)):
            assert dataclasses.replace(fired, state=word, events=events, state_days=3).fired is True, word
            assert dataclasses.replace(quiet, state=word, events=events, state_days=3).fired is False, word


# --------------------------------------------------------------------------- #
# The state words: one closed table, one home for each word                   #
# --------------------------------------------------------------------------- #
def test_the_ten_state_words_are_one_table_and_equal_the_one_the_screen_reads():
    assert record.STATE_WORDS == (
        "fired", "crossed", "lines, no LPS yet", "forming N of 15", "root candidate, unconfirmed",
        "beyond R, undetermined", "under S, undetermined", "broke down", "not scanned", "no lines")
    assert len(set(record.STATE_WORDS)) == 10 and record.READ_FAILED not in record.STATE_WORDS
    # The leaf cannot import the old engine's table and the old file is frozen: held equal from outside.
    from engine_alpha import two_eyes_adapter
    assert tuple(two_eyes_adapter.STATE_WORDS) == record.STATE_WORDS


def test_each_state_word_has_one_home():
    assert walk.LINES_NO_LPS is lps.LINES_NO_LPS is record.LINES_NO_LPS
    assert lps.FIRED is record.FIRED and lps.CROSSED is record.CROSSED
    # Two equal strings can be one object by accident, so the homes are held by the text: the stages that say
    # these words import them, they do not type them again.
    for stage in (walk, lps):
        source = inspect.getsource(stage)
        for name in ("FIRED", "CROSSED", "LINES_NO_LPS", "NO_LINES"):
            assert f"\n{name} = " not in source, f"{stage.__name__} types {name} a second time"
    assert record.NO_LINES == "no lines" and record.NO_LINES in record.STATE_WORDS
    import engine_alpha.two_eyes as two_eyes
    assert two_eyes.STATE_WORDS is record.STATE_WORDS and two_eyes.EVENT_KINDS is record.EVENT_KINDS
    assert two_eyes.Event is record.Event


# --------------------------------------------------------------------------- #
# His rails: the word rules read on the box HE drew (the standard)            #
# --------------------------------------------------------------------------- #
#: The two daily ranges a word has been measured in: the one the rules' numbers were placed in (the range six
#: bars back from his as-of day) and the range of the day his box's second line was anchored on (the box's own).
UNITS = ("placed", "box")


@functools.lru_cache(maxsize=1)
def _standard():
    frames, _ = load_sealed_fixture()
    return {setup_key(s): (s, fixture_frame(frames, setup_key(s), s["ticker"])) for s in load_corpus()}


def _keys(ticker: str) -> list:
    return [k for k in _standard() if k.split(":")[0] == ticker]


@functools.lru_cache(maxsize=None)
def _on_his_rails(key: str, unit_name: str) -> dict:
    """His box, his last LPS window and the line, as the word rules take them, read on his as-of day."""
    s, raw = _standard()[key]
    df = raw.loc[:pd.Timestamp(s["as_of"])].copy()
    df["ATR_10"] = calculate_atr(df, 10)
    at = {day.date(): i for i, day in enumerate(df.index)}
    bar = lambda iso: at[dt.date.fromisoformat(iso)]
    start = bar(s["box"][0])
    second = max(bar(s["anchors"]["R"]), bar(s["anchors"]["S"]))
    unit = float(df["ATR_10"].iloc[-6] if unit_name == "placed" else df["ATR_10"].iloc[second])
    high, low = df["High"].to_numpy(float), df["Low"].to_numpy(float)
    line = turn_line(high, low, turn_line_floors(df, unit))
    R, S = float(s["rails_drawn"]["R"]), float(s["rails_drawn"]["S"])
    read_bar = len(df) - 1
    lps_start = bar((s.get("lps2") or s["lps"])[0])
    fifteenth = start + M.BOX_DAYS - 1
    pc = LW.phase_c(line, high, start, S, unit, R, lps_start, read_bar, fifteenth=fifteenth)
    th = LW.thrusts(line, start, R, unit)
    return {"days": [d.date() for d in df.index], "line": line, "thrusts": th, "phase_c": pc, "R": R, "S": S,
            "unit": unit, "start": start, "read_bar": read_bar, "fifteenth": fifteenth,
            "upthrust": LW.the_upthrust(th, line, R, unit, pc, start, read_bar, fifteenth=fifteenth)}


def _upthrust_day(key: str, unit_name: str):
    his = _on_his_rails(key, unit_name)
    return None if his["upthrust"] is None else his["days"][his["upthrust"]["top_bar"]]


# --------------------------------------------------------------------------- #
# THE upthrust, on his words                                                  #
# --------------------------------------------------------------------------- #
#: The upthrusts he named, each by his own word (he cannot draw one in the app). ALB: "that breach is not an
#: upthrust in fact there is a later on 25/02/2026" (Thu 01/10/2026). UNF: his red "UT" over Thu 11/06/2026
#: (Tue 15/09 and Wed 16/09/2026). VIK: "Purple mark: Up Thrust" (Sat 19/09/2026). FOSL: "it can be a UT."
#: (Sat 19/09/2026).
_HIS_UPTHRUSTS = {"ALB": dt.date(2026, 2, 25), "UNF": dt.date(2026, 6, 11), "VIK": dt.date(2026, 5, 14),
                  "FOSL": dt.date(2026, 1, 27)}
#: Where he said there is none: "I can agree that no UP thrust is also valid" (Thu 17/09/2026).
_NO_UPTHRUST_BY_HIS_WORD = ("EWTX", "JAZZ", "NOK")
#: Named by the rule on his rails and NOT yet seen by him: they go to him as pictures, never as a count of hits.
_UPTHRUSTS_HE_HAS_NOT_SEEN = {"DRTS": dt.date(2026, 2, 25), "MTLS": dt.date(2026, 7, 1), "ST": dt.date(2026, 2, 24)}


@pytest.mark.parametrize("unit", UNITS)
def test_the_upthrust_is_named_where_he_named_it(unit):
    for ticker, day in _HIS_UPTHRUSTS.items():
        (key,) = _keys(ticker)
        assert _upthrust_day(key, unit) == day, f"{ticker} ({unit})"


@pytest.mark.parametrize("unit", UNITS)
def test_a_run_past_resistance_while_the_trend_is_still_ending_is_no_upthrust(unit):
    """ALB, his word of Thu 01/10/2026: the run of Tue 20/01 to Tue 27/01/2026 "is not an upthrust ... that
    movement in 20/1 -> 27/1 and the crash afterwards could be treated as the place where the trend ends". It
    tops on the eighth day of his box. And the breach he crossed out on UNF, Fri 05/06/2026 ("not every small
    false breach of Resistance is one"), the thirteenth day of his box. A push that tops before the box's
    fifteenth day is the trend still ending."""
    for ticker, first, last in (("ALB", dt.date(2026, 1, 20), dt.date(2026, 1, 28)),
                                ("UNF", dt.date(2026, 6, 5), dt.date(2026, 6, 5))):
        (key,) = _keys(ticker)
        his = _on_his_rails(key, unit)
        named = _upthrust_day(key, unit)
        assert named is not None and not (first <= named <= last), (ticker, unit, named)
        # Not by accident of "one per box": with the fifteenth-day clause off, nothing else changes for UNF, and
        # every candidate in that run tops before the fifteenth day.
        early = [t for t in his["thrusts"] if first <= his["days"][t["top_bar"]] <= last]
        assert all(t["top_bar"] < his["fifteenth"] for t in early), (ticker, unit)
    # NET: the push of Fri 07/08/2026, the third day of his box, and the run to Thu 13/08/2026 (the seventh).
    (net,) = _keys("NET")
    assert _upthrust_day(net, unit) is None


@pytest.mark.parametrize("unit", UNITS)
def test_no_upthrust_where_he_agreed_there_is_none_and_no_new_name_appears_unseen(unit):
    named = {key.split(":")[0]: _upthrust_day(key, unit) for key in _standard()
             if _upthrust_day(key, unit) is not None}
    for ticker in _NO_UPTHRUST_BY_HIS_WORD:
        assert ticker not in named, (ticker, unit)
    assert named == {**_HIS_UPTHRUSTS, **_UPTHRUSTS_HE_HAS_NOT_SEEN}, unit


def test_crashing_back_may_take_more_than_one_swing():
    """ALB's upthrust tops Wed 25/02/2026 at 206.00; the next low of the line (Thu 26/02/2026, 181.95) still
    holds over the resistance area, and the price is back inside the range only on a later swing, with no higher
    top in between. His words: it "climbs quickly out of the structure then crashes back into the trading range"."""
    (key,) = _keys("ALB")
    his = _on_his_rails(key, "placed")
    up = his["upthrust"]
    line, area = his["line"], M.LINE_WORD_AREA_ATR * his["unit"]
    k = next(i for i, t in enumerate(line) if t[0] == up["top_bar"] and t[1] == "peak")
    assert line[k + 1][2] >= his["R"] - area, "the next low holds over the resistance area"
    assert up["back_bar"] > line[k + 1][0] and up["back_price"] < his["R"] - area
    assert all(t[2] <= up["top_price"] for t in line[k + 1:] if t[1] == "peak" and t[0] <= up["back_bar"])


@pytest.mark.parametrize("unit", UNITS)
def test_his_no_for_the_spring_on_vik_holds_on_his_rails(unit):
    """VIK (Sat 19/09/2026): "No for the spring" on the dip of Wed 29/04/2026; his upthrust of Thu 14/05/2026
    came after it, so the range was still running."""
    (key,) = _keys("VIK")
    his = _on_his_rails(key, unit)
    assert his["phase_c"] is None or his["days"][his["phase_c"]["tip_bar"]] != dt.date(2026, 4, 29)


def test_a_push_that_goes_on_to_a_higher_top_did_not_crash_back():
    """Hand-built, resistance 14, the area half a range: a push tops at 16.0, pauses at 14.5 (still over the
    resistance area), goes on to 17.0 and only then falls to 11.0. The first top did not crash back: the price
    went higher first. The second did."""
    line = [(0, "valley", 10.0, 1), (5, "peak", 16.0, 6), (6, "valley", 14.5, 7), (8, "peak", 17.0, 9),
            (10, "valley", 11.0, 11)]
    assert LW._crashes_back(line, 1, 14.0, 1.0) is None
    assert LW._crashes_back(line, 3, 14.0, 1.0) == 4
    # And a pause that holds over the area followed by the fall, with no higher top between: more than one swing.
    slower = [(0, "valley", 10.0, 1), (5, "peak", 16.0, 6), (6, "valley", 14.5, 7), (8, "peak", 15.5, 9),
              (10, "valley", 11.0, 11)]
    assert LW._crashes_back(slower, 1, 14.0, 1.0) == 4


def test_a_push_before_the_boxs_fifteenth_day_does_not_cost_the_box_its_spring():
    """Hand-built: support 10, resistance 14, read on bar 30. A dip to 8.5 on bar 3 recovers (a high back over
    the support area, then a higher low at 11.0 on bar 8). Between them the price ran to 16.0 on bar 6, two
    ranges over resistance, and fell back. With the box's fifteenth day on bar 14 that run is the trend still
    ending, not an upthrust, so the range did not "run on" and the dip is the spring. Were it an upthrust (no
    fifteenth day given: the rule as it was copied), the dip would have been Phase B and no spring is named."""
    line = [(0, "peak", 12.0, 0), (3, "valley", 8.5, 4), (6, "peak", 16.0, 7), (8, "valley", 11.0, 9),
            (12, "peak", 13.0, 13)]
    highs = np.full(31, 12.0)
    highs[6] = 16.0
    spring = LW.phase_c(line, highs, 0, 10.0, 1.0, 14.0, None, 30, fifteenth=14)
    assert spring is not None and spring["tip_bar"] == 3
    assert LW.phase_c(line, highs, 0, 10.0, 1.0, 14.0, None, 30) is None
