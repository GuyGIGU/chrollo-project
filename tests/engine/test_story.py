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
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from core.calibration.replay import fixture_frame, load_sealed_fixture
from engine_alpha import story as LW
from engine_alpha import reader
from engine_alpha import grade, lps, record, state, story
from engine_alpha.box import walk
from engine_alpha import numbers as M
from engine_alpha.chart import calculate_atr
from engine_alpha.line import turn_line, turn_line_floors
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
    assert names[9:] == ["events", "state_days", "grade"], "the grade (stage 7, task 14) is the last field"
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
def test_the_spring_event_is_dated_on_its_own_dip_and_the_recovery_bars_own_low_is_no_test():
    """His GFR (Thu 16/10/2026), on the reader's own words for it: the spring of Fri 02/10/2026 was marked over
    Fri 02/10 to Tue 06/10, "the bars going up, aka the recover after the swing, not the spring itself", and a
    "spring test" was named on Tue 06/10, the low of the bar that recovered — "one of them is already engulfed
    in the other". The event's days are the dip's, first bar under the support area to the tip; a valley on
    the reaching bar's own day is no test."""
    turn = lambda bar, kind, price, known: SimpleNamespace(bar=bar, kind=kind, price=price, knowable_bar=known)
    lows = np.array([10.5, 10.2, 9.8, 9.4, 9.2, 8.0, 9.0, 9.7, 9.6, 10.3, 10.1, 10.8, 10.4, 11.0] + [10.6] * 26)
    highs = lows + 0.6
    days = tuple(dt.date(2026, 9, 1) + dt.timedelta(days=i) for i in range(len(lows)))
    # The bar of 08 reaches the area with its high and carries its own low 9.6 (bar 8 is wide: peak, then valley).
    turns = [turn(0, "peak", 11.1, 1), turn(5, "valley", 8.0, 6), turn(8, "peak", 10.9, 9), turn(8, "valley", 9.6, 9),
             turn(13, "peak", 11.6, 14), turn(20, "valley", 10.6, 21), turn(39, "peak", 11.2, None)]
    events = {e.kind: e for e in story.read(turns, highs, lows, days, start_bar=0, R=14.0, S=10.0, unit=1.0,
                                             read_bar=39)}
    spring = events[record.SPRING]
    assert (spring.day, spring.first_day, spring.last_day) == (days[5], days[3], days[5])
    assert spring.known_day == days[9] and spring.committed
    assert record.SPRING_TEST not in events, "the reaching bar's own low is the recovery, not a test"


def test_his_aapl_the_spring_test_is_the_valley_after_the_recovery_not_the_one_the_sos_rises_from():
    """His AAPL (Fri 17/10/2026), the bars converted into swings on the lens: *"everything is correct expect the
    Test after the spring, as you can see it happened earlier and what you marked as the Test is already a part
    of the SOS."* The reader told: the spring's tip Thu 01/10 at 325.81; the spring's test Mon 12/10 at 337.60
    (the valley THE SOS's swing starts from); THE SOS tops Tue 13/10 at 348.15. His test is the valley of Tue
    06/10 at 330.62, the first after the spring's recovery (Mon 05/10), over the spring's low and 0.55 daily
    ranges under support. The rest of the story stands as he passed it."""
    from tests.engine.test_story_words import AAPL_BOX, AAPL_HIGHS, AAPL_LINE, AAPL_LOWS
    turn = lambda bar, kind, price, known: SimpleNamespace(bar=bar, kind=kind, price=price, knowable_bar=known)
    days = tuple(dt.date.fromisoformat(d) for d in (
        "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23",
        "2026-09-24", "2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02",
        "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13",
        "2026-10-14", "2026-10-15", "2026-10-16"))
    turns = [turn(*t) for t in AAPL_LINE]
    pullback = SimpleNamespace(stood=True, start_bar=21, end_bar=23, crossed_bar=None)
    b = AAPL_BOX
    events = story.read(turns, AAPL_HIGHS, AAPL_LOWS, days, start_bar=b["start"], R=b["R"], S=b["S"],
                        unit=b["unit"], read_bar=b["read_bar"], pullback=pullback)
    told = {e.kind: e for e in events}
    assert len(told) == len(events) == 4, [e.kind for e in events]
    assert (told[record.SPRING].day, told[record.SPRING].first_day, told[record.SPRING].price) == \
        (dt.date(2026, 10, 1), dt.date(2026, 9, 29), 325.81)
    assert (told[record.SPRING_TEST].day, told[record.SPRING_TEST].price) == (dt.date(2026, 10, 6), 330.62), \
        "his test: the valley after the recovery, not the one THE SOS rises from"
    assert told[record.SPRING_TEST].committed and told[record.SPRING_TEST].known_day == dt.date(2026, 10, 7)
    assert (told[record.SOS].first_day, told[record.SOS].day, told[record.SOS].price) == \
        (dt.date(2026, 10, 12), dt.date(2026, 10, 13), 348.15)
    assert (told[record.PHASE_D].day, told[record.PHASE_D].note) == (dt.date(2026, 10, 12), "round trip")


def test_the_ten_state_words_are_one_table_and_equal_the_one_the_screen_reads():
    assert record.STATE_WORDS == (
        "fired", "crossed", "lines, no LPS yet", "forming N of 15", "root candidate, unconfirmed",
        "beyond R, undetermined", "under S, undetermined", "broke down", "not scanned", "no lines")
    assert len(set(record.STATE_WORDS)) == 10 and record.READ_FAILED not in record.STATE_WORDS
    # The leaf cannot import the old engine's table and the old file is frozen: held equal from outside.
    from engine_alpha import result
    assert tuple(result.STATE_WORDS) == record.STATE_WORDS


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
    import engine_alpha.reader as reader
    assert reader.STATE_WORDS is record.STATE_WORDS and reader.EVENT_KINDS is record.EVENT_KINDS
    assert reader.Event is record.Event


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
_UPTHRUSTS_HE_HAS_NOT_SEEN = {"DRTS": dt.date(2026, 2, 25), "MTLS": dt.date(2026, 7, 1), "ST": dt.date(2026, 2, 24),
                              "CLOV": dt.date(2026, 8, 6)}
#: Named in the placed unit only (his drawings of Fri 30/10/2026): on VTMX he drew a last supper over those days
#: (Mon 24/08 to Fri 28/08/2026), not an upthrust. Pictures for his eye.
_UPTHRUSTS_HE_HAS_NOT_SEEN_PLACED_ONLY = {"DSGX": dt.date(2026, 8, 31), "VTMX": dt.date(2026, 8, 21)}


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
    placed_only = _UPTHRUSTS_HE_HAS_NOT_SEEN_PLACED_ONLY if unit == "placed" else {}
    assert named == {**_HIS_UPTHRUSTS, **_UPTHRUSTS_HE_HAS_NOT_SEEN, **placed_only}, unit


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


# --------------------------------------------------------------------------- #
# The story, wired: the reader's OWN read on his last receding day            #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def his_last_receding_day() -> dict:
    """Each of his 40 setups read by the reader itself, through its one door, on the last day of his last LPS
    window: the day the fire is judged on."""
    out = {}
    for key, (s, raw) in _standard().items():
        day = (s.get("lps2") or s["lps"])[1]
        out[key] = reader.read(s["ticker"], raw.loc[:pd.Timestamp(day)])
    assert len(out) == 52
    return out


def test_the_story_is_one_step_after_the_lps_and_its_events_are_dated_by_days(his_last_receding_day):
    told = 0
    for key, read in his_last_receding_day.items():
        assert read.failed is False, key
        stages = [s.stage for s in read.trail]
        if read.parent is None:
            assert read.events == () and story.STAGE not in stages, key
            continue
        # the story's one step follows the LPS's; only the grade's (stage 7, task 14) comes after it
        assert stages.count(story.STAGE) == 1 and stages[-3:] == ["LPS", story.STAGE, grade.STAGE], (key, stages)
        assert "could not be read" not in read.trail[-2].saying, (key, read.trail[-2].saying)
        for event in read.events:
            assert isinstance(event, record.Event) and type(event.day) is dt.date, (key, event)
            assert read.parent.opened_day <= event.day <= read.as_of, (key, event)
            for other in (event.first_day, event.last_day, event.known_day):
                assert other is None or (type(other) is dt.date and other <= read.as_of), (key, event)
            assert (event.known_day is not None) == event.committed, (key, event)
        assert list(read.events) == sorted(read.events, key=lambda e: (e.day, e.kind)), key
        told += bool(read.events)
    assert told >= 30, "the story names a word on most of his boxes; under that the wiring is not reading them"


def test_a_story_that_falls_over_costs_no_fire(monkeypatch):
    """THE GUARD, on a real fire: SYRE on his last receding day. Make a word rule raise: the read still fires at
    the same trigger, it is not a failed read, the events are empty and the trail says the story could not be
    read. A bug in a word is a missing word, never a missing setup."""
    s, raw = _standard()["SYRE:2026-02-19"]
    cut = raw.loc[:pd.Timestamp((s.get("lps2") or s["lps"])[1])]
    whole = reader.read("SYRE", cut)
    assert whole.fired and whole.events, "the control: SYRE fires and the story names words on it"

    def broken(*args, **kwargs):
        raise StopIteration("a word rule fell over")

    monkeypatch.setattr(LW, "phase_d", broken)
    read = reader.read("SYRE", cut)
    assert read.fired and read.failed is False and read.state == record.FIRED
    assert read.lps == whole.lps and read.boxes == whole.boxes and read.close == whole.close
    assert read.events == ()
    assert read.trail[:-2] == whole.trail[:-2], "everything before the story is told as before"
    assert read.trail[-2].stage == story.STAGE and "could not be read" in read.trail[-2].saying
    assert "StopIteration" in read.trail[-2].saying
    assert read.trail[-1].stage == grade.STAGE, "the grade (stage 7) still reads, on no story"


def test_keeping_the_listing_changes_no_event(his_last_receding_day):
    for key in ("SYRE:2026-02-19", "VIK:2026-06-11", "ALB:2026-04-13"):
        s, raw = _standard()[key]
        cut = raw.loc[:pd.Timestamp((s.get("lps2") or s["lps"])[1])]
        listed = reader.read(s["ticker"], cut, keep_listing=True)
        assert listed.events == his_last_receding_day[key].events, key
        assert listed.trail[-1] == his_last_receding_day[key].trail[-1], key


# --------------------------------------------------------------------------- #
# The unit of the words: the box's own range, the numbers held to his marks   #
# --------------------------------------------------------------------------- #
#: Left out of the SOS ground: DSGN by his word ("Ignore the DSGN SOS markings", Tue 15/09/2026) and BODI by ours
#: (he set the chart's BOX aside on Thu 01/10/2026; its drawn events stand, and no push of the line tops on his).
_SET_ASIDE = ("DSGN", "BODI")


def _drawn_in_the_boxs_range(kind: str) -> list:
    """Each of his drawn spans of ``kind`` measured on the bars alone, in the range of the day his box's second
    line was anchored: for an SOS the ground from the lowest low to the highest high of his span; for a last
    supper the drop from its highest high to the lowest low after it in his span, and the days between."""
    out = []
    for key, (s, raw) in _standard().items():
        if kind not in s:
            continue
        his = _on_his_rails(key, "box")
        df = raw.loc[:pd.Timestamp(s["as_of"])]
        high, low = df["High"].to_numpy(float), df["Low"].to_numpy(float)
        at = {d: i for i, d in enumerate(his["days"])}
        for first, last in s[kind]:
            a, b = at[dt.date.fromisoformat(first)], at[dt.date.fromisoformat(last)]
            top = a + int(np.argmax(high[a:b + 1]))
            if kind == "sos":
                launch = a + int(np.argmin(low[a:top + 1]))
                out.append(((high[top] - low[launch]) / his["unit"], 0, key.split(":")[0]))
            else:
                bottom = top + int(np.argmin(low[top:b + 1]))
                out.append(((high[top] - low[bottom]) / his["unit"], bottom - top, key.split(":")[0]))
    return sorted(out)


def test_a_push_covers_no_more_ground_than_his_smallest_drawn_sos():
    """His sentence: "It's hard to gate using a raw number in case we reject a valid setups because of a small
    neumeric gap" (Sat 12/09/2026). In the box's own range his smallest drawn SOS covers 1.33 ranges (SGHT, Mon
    21/09 to Tue 22/09/2026); the floor sits a fifth of a range on his side of it."""
    grounds = [g for g in _drawn_in_the_boxs_range("sos") if g[2] not in _SET_ASIDE]
    assert len(grounds) == 37      # his 52 drawings (Fri 30/10/2026); the smallest is still SGHT
    smallest = grounds[0]
    assert smallest[2] == "SGHT" and smallest[0] == pytest.approx(1.33, abs=0.01)
    assert M.LINE_WORD_SOS_MIN_GROUND_ATR <= smallest[0] - 0.195


def test_a_last_supper_digs_no_deeper_and_lasts_no_longer_than_his_own():
    suppers = _drawn_in_the_boxs_range("last_supper")
    assert len(suppers) == 10      # his 52 drawings (Fri 30/10/2026); the shallowest is still SILC
    shallowest = suppers[0]
    assert shallowest[2] == "SILC" and shallowest[0] == pytest.approx(1.52, abs=0.01)
    assert M.LINE_WORD_SUPPER_DIG_ATR <= shallowest[0] - 0.2
    # "a noticeable deep correction" (Sat 03/10/2026): a last supper is NAMED only when it digs as deep as his
    # shallowest, less the margin the floors keep — 1.32. The push-ending floor above stays where his PBT push needs it.
    assert M.LINE_WORD_SUPPER_NAMED_DIG_ATR == pytest.approx(shallowest[0] - 0.2, abs=0.01)
    assert M.LINE_WORD_SUPPER_NAMED_DIG_ATR > M.LINE_WORD_SUPPER_DIG_ATR
    assert max(days for _, days, _ in suppers) == 4 == M.LINE_WORD_SUPPER_MAX_DAYS, "his longest: MATX and VTMX, four days"


def test_the_upthrust_floor_sits_between_the_breach_he_crossed_out_and_the_smallest_he_named():
    """In the box's own range the breach he crossed out on UNF (Fri 05/06/2026) climbs 1.21 ranges over his
    resistance and the smallest upthrust he named (VIK, Thu 14/05/2026) 1.31. The floor is strictly between; the
    band is under a tenth of a range wide, a knife edge on both sides that the record says out loud."""
    def climb(ticker, day):
        (key,) = _keys(ticker)
        his = _on_his_rails(key, "box")
        top = next(t[2] for t in his["line"] if t[1] == "peak" and his["days"][t[0]] == day)
        return (top - his["R"]) / his["unit"]

    crossed_out, smallest = climb("UNF", dt.date(2026, 6, 5)), climb("VIK", dt.date(2026, 5, 14))
    assert crossed_out == pytest.approx(1.21, abs=0.01) and smallest == pytest.approx(1.31, abs=0.01)
    assert crossed_out < M.LINE_WORD_UPTHRUST_MIN_POKE_ATR < smallest


def test_the_story_reads_every_word_in_the_boxs_own_range(his_last_receding_day):
    """One unit per box: the size the story records for a word is measured in the range the box's own rail areas
    are measured in (``Box.daily_range``), frozen at the box's birth, never the read day's."""
    seen = 0
    for key, read in his_last_receding_day.items():
        if read.parent is None:
            continue
        unit = read.parent.daily_range
        for event in read.events:
            if event.kind == record.SPRING:
                assert event.size == pytest.approx((read.parent.support.price - event.price) / unit, abs=0.002), key
                seen += 1
            if event.kind == record.UPTHRUST:
                assert event.size == pytest.approx((event.price - read.parent.resistance.price) / unit, abs=0.002), key
                seen += 1
    assert seen >= 20


# --------------------------------------------------------------------------- #
# The reader's own story, held to his drawn events on his last receding day   #
# --------------------------------------------------------------------------- #
def _named(read, kind) -> list:
    return [e for e in read.events if e.kind == kind]


def _his_words(key: str, read) -> dict:
    """Per drawn word of his on this setup: ``(kind, his day, hit)``. His day is the day his drawing points at:
    the last day of his SOS span (the last SOS drawn before his last LPS window ends), the lowest low of a spring
    or spring-test span, the highest high of a last-supper span. A hit is the reader's word within ONE trading
    day of it."""
    s, raw = _standard()[key]
    last = (s.get("lps2") or s["lps"])[1]
    df = raw.loc[:pd.Timestamp(last)]
    days = [d.date() for d in df.index]
    at = {d: i for i, d in enumerate(days)}
    bar = lambda iso: at[dt.date.fromisoformat(iso)]
    high, low = df["High"].to_numpy(float), df["Low"].to_numpy(float)
    near = lambda events, target: any(e.day in at and abs(at[e.day] - target) <= 1 for e in events)
    out = []
    spans = [x for x in s.get("sos", []) if dt.date.fromisoformat(x[1]) <= dt.date.fromisoformat(last)]
    if spans:
        target = bar(spans[-1][1])
        out.append(("sos", days[target], near(_named(read, record.SOS), target)))
    for kind, word in (("phase_c", record.SPRING), ("spring_test", record.SPRING_TEST)):
        for first, end in s.get(kind, []):
            a, b = bar(first), bar(end)
            target = a + int(np.argmin(low[a:b + 1]))
            out.append((kind, days[target], near(_named(read, word), target)))
    for first, end in s.get("last_supper", []):
        a, b = bar(first), min(bar(end) if dt.date.fromisoformat(end) in at else len(days) - 1, len(days) - 1)
        target = a + int(np.argmax(high[a:b + 1]))
        out.append(("last_supper", days[target], near(_named(read, record.LAST_SUPPER), target)))
    return out


def test_the_named_charts_read_his_words_on_his_days(his_last_receding_day):
    """Each date is his own drawing or his own word, read by the reader on its own box and its own line."""
    day = lambda read, kind: [e.day for e in _named(read, kind)]
    syre = his_last_receding_day["SYRE:2026-02-19"]
    assert day(syre, record.SPRING) == [dt.date(2026, 1, 5)]
    assert day(syre, record.PHASE_D) == [dt.date(2026, 1, 26)], '"Phase D opens roughly after the 26/01/26"'
    assert day(syre, record.SOS) == [dt.date(2026, 2, 13)]
    pbt = his_last_receding_day["PBT:2026-05-11"]
    assert day(pbt, record.PHASE_D) == [dt.date(2026, 4, 23)], '"on PBT I would say it starts on 23/04/26"'
    assert day(pbt, record.SOS) == [dt.date(2026, 5, 4)], "his push tops Tue 05/05/2026: within a day"
    nktr = his_last_receding_day["NKTR:2026-04-10"]
    assert day(nktr, record.SPRING) == [dt.date(2026, 3, 30)] and day(nktr, record.SOS) == [dt.date(2026, 4, 1)]
    mrk = his_last_receding_day["MRK:2026-08-10"]
    assert day(mrk, record.SOS) == [dt.date(2026, 7, 28)] and dt.date(2026, 7, 28) in day(mrk, record.LAST_SUPPER)
    # THE upthrust, on the reader's own box: UNF as he named it.
    (unf,) = _keys("UNF")
    assert day(his_last_receding_day[unf], record.UPTHRUST) == [dt.date(2026, 6, 11)]


#: His drawn words the reader's own story does NOT land on his last receding day, each with its cause. A miss is
#: charged to the box (the reader's box is not his), to the word (the rule), or to his own setting aside.
_SOS_MISSES = {
    "ALB": "the box: the reader's box is 182.80 / 156.04 for his 179.10 / 160.02",
    # BODI's miss went with his redraw of Sat 10/10/2026, which carries no event. His drawings of Fri 30/10/2026:
    "ANET": "the box: on his drawing of Fri 02/10/2026 the reader's SOS tops Fri 25/09/2026 for his Tue 22/09/2026 "
            "(on his drawing of Fri 25/09/2026 it lands); its box is 214.89 / 187.03 for his 198.92 / 187.03",
    "TWLO": "the box: the reader's box is the June bar, 238.48 / 222.62, and its SOS Mon 10/08/2026; his box opens "
            "Fri 28/08/2026 and his SOS is Tue 15/09/2026",
    "DSGN": 'his word: "Ignore the DSGN SOS markings"',
    "MATX": "the box (the reader shows the shelf on his resistance) AND the word: on his own lines the rule "
            "names Tue 09/06/2026 for his Fri 12/06/2026, his half-range area keeping the earlier top",
    "MDT": "the word: in the box's range the pauses of Mon 29/06 and Thu 02/07/2026 each end a push",
    "VIK": "the word: on his fire day the middle of the box has not passed his upthrust of Thu 14/05/2026",
}
_SPRING_MISSES = {
    "ORMP": "the box: 3.67 / 3.32 for his 3.71 / 3.35, and an earlier dip takes the word",
    "ST": "the word: his rail area (half a range) in the box's range leaves the top of Wed 11/03/2026 outside it",
}
_LAST_SUPPER_MISSES = {
    "MATX": "the box",
    # His drawings of Fri 30/10/2026:
    "CBLL": "the word: the reader's one last supper tops Wed 21/10/2026; he shaded Fri 16/10 to Mon 19/10/2026",
    "VTMX": "the box: on 35.02 / 32.01 the reader names no last supper; the spike of Fri 21/08/2026 (36.05) is an "
            "upthrust in the placed unit",
}


def test_the_reader_lands_his_drawn_words_and_every_miss_is_named(his_last_receding_day):
    """The ratchet, on the reader's OWN read: THE SOS on 30 of his 37, the spring on 10 of his 12, the last supper
    on 7 of his 10 (his 52, Fri 30/10/2026). A word landed today may not be lost tomorrow; a miss that starts
    landing is taken off the list on purpose. The spring test is listed, never scored (4 drawn)."""
    missed = {"sos": [], "phase_c": [], "last_supper": [], "spring_test": []}
    count = {"sos": 0, "phase_c": 0, "last_supper": 0, "spring_test": 0}
    for key, read in his_last_receding_day.items():
        for kind, _, hit in _his_words(key, read):
            count[kind] += 1
            if not hit:
                missed[kind].append(key.split(":")[0])
    assert count == {"sos": 37, "phase_c": 12, "last_supper": 10, "spring_test": 4}     # his 52 (Fri 30/10/2026)
    assert sorted(missed["sos"]) == sorted(_SOS_MISSES)
    assert sorted(missed["phase_c"]) == sorted(_SPRING_MISSES)
    assert sorted(missed["last_supper"]) == sorted(_LAST_SUPPER_MISSES)
    assert len(missed["spring_test"]) <= 4


#: His seven landed last suppers, the day the reader's ONE last supper tops on his last receding day: his top to the
#: day on five; on SILC THE SOS's top of the same correction one trading day before his (one low, two tops, named
#: from the higher), on VIK the line's peak one day before his bar's high.
_HIS_LAST_SUPPERS_NAMED = {"EWTX": "2026-03-17", "MRK": "2026-07-28", "NGL": "2026-03-25", "NTCT": "2026-02-20",
                           "SILC": "2026-03-25", "VIK": "2026-05-28", "WTS": "2026-05-28"}


def test_a_box_carries_one_last_supper_and_on_his_charts_it_is_his(his_last_receding_day):
    """HIS, Sat 03/10/2026: "you mark LS to every pull back above resistance in phase D which is in correct, a last
    supper is a noticeable deep correction that happens *usually only once either pre or post break out." On his
    last receding day no chart of his 52 carries two; where he drew one and the reader lands it, the one named is
    his, or THE SOS's top of the same correction one trading day before his (SILC). As built the reader named 60 on
    26 of his 40 (six on DSGN and VLO); once, 26 on the same 26; once and as deep as his shallowest less the margin
    (1.32 ranges), 23 — 16 where he drew none, the pictures for his eye. On his 52 (Fri 30/10/2026): 29, on 29
    charts, 22 where he drew none."""
    per_chart = {key: _named(read, record.LAST_SUPPER) for key, read in his_last_receding_day.items()}
    assert max(len(v) for v in per_chart.values()) == 1, sorted(k for k, v in per_chart.items() if len(v) > 1)
    assert sum(len(v) for v in per_chart.values()) == 29
    assert min(e.size for v in per_chart.values() for e in v) >= M.LINE_WORD_SUPPER_NAMED_DIG_ATR
    named = {key.split(":")[0]: str(v[0].day) for key, v in per_chart.items()
             if v and key.split(":")[0] in _HIS_LAST_SUPPERS_NAMED}
    assert named == _HIS_LAST_SUPPERS_NAMED


@pytest.mark.xfail(strict=True, reason=(
    'KNOWN MISS, his own words against the moving middle. VIK (Sat 19/09/2026): "No for the spring" on the dip of '
    "Wed 29/04/2026, and his upthrust is Thu 14/05/2026. The upthrust belongs in Phase B, read as at or before the "
    "middle of the box, and the middle is measured to the read day: on his last receding day (Mon 08/06/2026) his "
    "push sits on bar 17 of the box and the middle is 16.5, so no upthrust is named, the dip keeps the spring's "
    "word and his upthrust's top is read as THE SOS. From his buy day on the middle has passed it and the read is "
    "his. Dropping the Phase B clause is Tested-DEAD (it calls his SOS pushes upthrusts). Shown to him as a picture."))
def test_vik_reads_his_upthrust_and_no_spring_on_his_fire_day(his_last_receding_day):
    vik = his_last_receding_day["VIK:2026-06-11"]
    assert [e.day for e in _named(vik, record.UPTHRUST)] == [dt.date(2026, 5, 14)]
    assert dt.date(2026, 4, 29) not in [e.day for e in _named(vik, record.SPRING)]


def test_a_word_standing_on_the_forming_turn_is_provisional():
    """The story reads the whole line, the turn still forming at the right edge included: that turn is what makes
    a word provisional. Hand-built: a spring (tip bar 5) recovered by bar 9 (a higher low over the support area,
    so no test yet), and the read day's own low, bar 12 at 9.7, a valley the line has not committed, back under
    support and over the spring's low: the spring's test, named, provisional, with no day it became known. The
    spring is committed. (Until his AAPL, Fri 17/10/2026, the specimen was NGL on Fri 16/01/2026: its valley of
    Thu 15/01 sat after THE SOS's swing, so it is the SOS's own now and no test; his NGL marks carry no test.)"""
    turn = lambda bar, kind, price, known: SimpleNamespace(bar=bar, kind=kind, price=price, knowable_bar=known)
    lows = np.array([10.5, 10.2, 9.8, 9.4, 9.2, 8.0, 9.0, 9.7, 10.3, 10.6, 11.0, 11.0, 9.7])
    highs = lows + 0.6
    highs[0] = 12.5                  # the peak the spring fell from: the recovery clears nothing, so no push, no SOS
    days = tuple(dt.date(2026, 9, 1) + dt.timedelta(days=i) for i in range(len(lows)))
    turns = [turn(0, "peak", 12.5, 1), turn(5, "valley", 8.0, 6), turn(8, "peak", 10.9, 9), turn(9, "valley", 10.6, 10),
             turn(11, "peak", 11.6, 12), turn(12, "valley", 9.7, None)]
    events = story.read(turns, highs, lows, days, start_bar=0, R=14.0, S=10.0, unit=1.0, read_bar=12)
    assert [(e.kind, e.day, e.committed, e.known_day) for e in events] == [
        (record.SPRING, days[5], True, days[10]), (record.SPRING_TEST, days[12], False, None)]
    assert ", provisional" in story.record(events)[0].saying
    assert all(e.known_day is not None for e in events if e.committed)


def test_the_story_leans_only_on_a_pullback_that_stood():
    """Three words lean on the LPS (THE SOS tops at or before its low, a last supper is sought before its window,
    Phase D may open on its first day). They lean on a pullback that STOOD on its last day: one that his sentences
    refused, or that ended before the box was a box, is no LPS and gives the words nothing."""
    low = np.array([10.0, 9.0, 8.0, 7.5, 7.8, 9.0])
    stood = SimpleNamespace(stood=True, start_bar=2, end_bar=4)
    assert story._lps_days(stood, low) == (2, 3)
    assert story._lps_days(SimpleNamespace(stood=False, start_bar=2, end_bar=4), low) == (None, None)
    assert story._lps_days(None, low) == (None, None)


def test_on_the_readers_own_later_alb_box_his_upthrust_is_named_too(his_last_receding_day):
    """His ALB sentence (Thu 01/10/2026): "even a later pair could work if that movement in 20/1 -> 27/1 and the
    crash afterwards could be treated as the place where the trend ends", and "there is a later [upthrust] on
    25/02/2026". The reader's ALB box (182.80 / 156.04) is such a later pair: it opens on Thu 05/02/2026 and took
    its place from a box anchored inside the rise that topped on Tue 27/01/2026. The fourteen days of "the trend
    still ending" are counted from that top, the END OF THE TREND, so his upthrust of Wed 25/02/2026 is named on
    the reader's box too. Counted from the box's own first line it would be the fourteenth day, one day short:
    the blind check of Sat 03/10/2026 found the reader refusing his own named upthrust by that one day."""
    alb = his_last_receding_day["ALB:2026-04-13"]
    assert (alb.parent.resistance.price, alb.parent.support.price) == pytest.approx((182.80, 156.04), abs=0.005)
    assert alb.parent.opened_day == dt.date(2026, 2, 5)
    assert [e.day for e in _named(alb, record.UPTHRUST)] == [dt.date(2026, 2, 25)]


def test_the_days_of_the_trend_still_ending_are_counted_from_the_end_of_the_trend():
    """Hand-built: resistance 14, support 10, the box opens on bar 20; a push tops on bar 30 two ranges over
    resistance and crashes back. Counted from the box's first line (its fifteenth day is bar 34) that push is
    the trend still ending and no upthrust. When the box took its place from one anchored inside a trend that
    topped on bar 10, the trend ended there (its fifteenth day is bar 24) and the push is THE upthrust."""
    turn = lambda bar, kind, price, known: SimpleNamespace(bar=bar, kind=kind, price=price, knowable_bar=known)
    turns = [turn(20, "peak", 13.8, 21), turn(24, "valley", 10.2, 25), turn(30, "peak", 16.0, 31),
             turn(33, "valley", 11.0, 34), turn(40, "peak", 13.0, 41), turn(44, "valley", 11.5, 45)]
    high, low = np.full(50, 13.0), np.full(50, 11.0)
    days = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(50)]
    box = dict(start_bar=20, R=14.0, S=10.0, unit=1.0, read_bar=49)
    kinds = lambda events: [e.kind for e in events]
    assert record.UPTHRUST not in kinds(story.read(turns, high, low, days, **box))
    late = story.read(turns, high, low, days, trend_end_bar=10, **box)
    assert [(e.kind, e.day) for e in late if e.kind == record.UPTHRUST] == [(record.UPTHRUST, days[30])]
    # A trend end AFTER the box's first line never pushes the count later: a push topping on bar 36, past the
    # box's own fifteenth day, is THE upthrust whatever later trend end the read may name.
    later = [turn(20, "peak", 13.8, 21), turn(24, "valley", 10.2, 25), turn(36, "peak", 16.0, 37),
             turn(39, "valley", 11.0, 40), turn(46, "peak", 13.0, 47), turn(50, "valley", 11.5, 51)]
    high, low = np.full(60, 13.0), np.full(60, 11.0)
    days = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(60)]
    box = dict(start_bar=20, R=14.0, S=10.0, unit=1.0, read_bar=59)
    for trend_end in (None, 10, 28):
        named = story.read(later, high, low, days, trend_end_bar=trend_end, **box)
        assert [e.day for e in named if e.kind == record.UPTHRUST] == [days[36]], trend_end


def test_a_phase_d_opened_by_an_unsettled_sos_is_provisional():
    """Hand-built: resistance 14, support 10, the box from bar 0, read on bar 30. A push from 11.0 (bar 16) is at
    15.0 on bar 20 and that top has not committed on the line yet; the LPS stood on bars 21 and 22. THE SOS is
    named, provisional; it opens Phase D (its last swing starts on bar 16, after the middle), and that opening
    is provisional too: it is as settled as what opened it."""
    turn = lambda bar, kind, price, known: SimpleNamespace(bar=bar, kind=kind, price=price, knowable_bar=known)
    turns = [turn(10, "peak", 13.0, 11), turn(16, "valley", 11.0, 17), turn(20, "peak", 15.0, None)]
    high, low = np.full(31, 13.0), np.full(31, 12.0)
    low[22] = 11.8
    days = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(31)]
    lps_days = SimpleNamespace(stood=True, start_bar=21, end_bar=22, crossed_bar=None)
    events = {e.kind: e for e in story.read(turns, high, low, days, start_bar=0, R=14.0, S=10.0, unit=1.0,
                                           read_bar=30, pullback=lps_days)}
    assert events[record.SOS].committed is False and events[record.SOS].day == days[20]
    opening = events[record.PHASE_D]
    assert (opening.note, opening.day, opening.committed, opening.known_day) == ("SOS", days[16], False, None)


def test_phase_d_is_as_settled_as_what_opened_it(his_last_receding_day):
    """The right side's opening is committed when what opened it is: a low of the line that has committed, THE
    SOS once THE SOS itself is settled, the LPS once the pullback has been bought. On his last receding day the
    LPS is still only that day's reading, so a Phase D that the LPS opened is provisional; on his buy day it is
    committed."""
    by_opener = {}
    for key, read in his_last_receding_day.items():
        for d in _named(read, record.PHASE_D):
            by_opener.setdefault(d.note, []).append((key, read, d))
    assert set(by_opener) <= {"round trip", "staircase", "SOS", "LPS"} and len(by_opener.get("SOS", [])) >= 5
    for key, read, d in by_opener.get("SOS", []):
        (sos,) = _named(read, record.SOS)
        assert d.committed == sos.committed, key
    for key, read, d in by_opener.get("LPS", []):
        assert d.committed is False and d.known_day is None, key
    key, read, d = by_opener["LPS"][0]
    s, raw = _standard()[key]
    bought = reader.read(s["ticker"], raw.loc[:pd.Timestamp(s["trigger"])])
    after = [e for e in _named(bought, record.PHASE_D) if e.note == "LPS"]
    assert bought.state == record.CROSSED and after and after[0].committed and after[0].known_day == bought.as_of


# --------------------------------------------------------------------------- #
# The state word: one of the ten, decided after the LPS                       #
# --------------------------------------------------------------------------- #
def _box(R=14.0, S=10.0, unit=1.0, birth_bar=0):
    return SimpleNamespace(R=R, S=S, area=0.5 * unit, birth_bar=birth_bar)


def _found(winner=None, pairs=()):
    return SimpleNamespace(winner=winner, pairs=dict(enumerate(pairs)))


def _bars(*rows):
    high, low = zip(*rows)
    return np.array(high, dtype=float), np.array(low, dtype=float)


def test_the_right_edge_is_read_only_when_nothing_fired():
    """Row 1 before row 5, his ANRO: "its an LPS above Resistance that fires". Bars that sit wholly over the
    resistance area change no fire and no buy day: ``fired`` and ``crossed`` are final."""
    high, low = _bars((13.0, 12.0), (15.6, 14.8), (15.9, 14.9))
    for word in (record.FIRED, record.CROSSED):
        assert state.decide(_found(_box()), word, high, low, 2) == (word, None)
    assert state.decide(_found(_box()), record.LINES_NO_LPS, high, low, 2) == (record.BEYOND_R, 2)


def test_bars_wholly_past_a_lines_area_are_undetermined_and_the_run_is_counted():
    """Resistance 14, support 10, the area half a range. "The bars after wards determine the meaning" (Sun
    30/08/2026): a day whose LOW is over 14.5 is wholly beyond resistance, a day whose HIGH is under 9.5 wholly
    under support; a day that still reaches the area is at the box."""
    high, low = _bars((13.0, 12.0), (15.0, 14.4), (15.6, 14.6), (15.9, 14.9), (16.2, 15.1))
    assert state.decide(_found(_box()), record.LINES_NO_LPS, high, low, 4) == (record.BEYOND_R, 3)
    assert state.decide(_found(_box()), record.LINES_NO_LPS, high, low, 1) == (record.LINES_NO_LPS, None), \
        "a low at 14.4 still reaches the resistance area"
    high, low = _bars((11.0, 10.2), (9.4, 8.8), (9.2, 8.5))
    assert state.decide(_found(_box()), record.LINES_NO_LPS, high, low, 2) == (record.UNDER_S, 2)
    high, low = _bars((11.0, 10.2), (9.4, 8.8), (9.6, 8.5))
    assert state.decide(_found(_box()), record.LINES_NO_LPS, high, low, 2) == (record.LINES_NO_LPS, None)
    # The run is counted on the days the box has been a box, no further back.
    high, low = _bars((15.5, 14.8), (15.6, 14.6), (15.9, 14.9))
    assert state.decide(_found(_box(birth_bar=1)), record.LINES_NO_LPS, high, low, 2) == (record.BEYOND_R, 2)


def test_a_young_pair_the_bars_came_back_to_is_forming_and_the_number_rides_beside_the_word():
    """No box is shown. A pair of lines the bars have already come back to, on its twelfth day: ``forming N of
    15`` with the letter N (the word is one of the closed ten) and 12 beside it. A pair the bars have not come
    back to is no lines yet; so is a pair that can never be a box."""
    young = SimpleNamespace(unfit=None, birth_bar=None, r_back=5, s_back=7, fifteenth=24, opening_bar=10, second_bar=11)
    high, low = _bars(*[(12.0, 11.0)] * 30)
    assert state.decide(_found(None, [young]), record.NO_LINES, high, low, 21) == (record.FORMING, 12)
    assert record.FORMING == "forming N of 15"
    no_answer = SimpleNamespace(unfit=None, birth_bar=None, r_back=5, s_back=None, fifteenth=24, opening_bar=10, second_bar=11)
    unfit = SimpleNamespace(unfit="under one daily range tall", birth_bar=None, r_back=5, s_back=7, fifteenth=24,
                            opening_bar=10, second_bar=11)
    assert state.decide(_found(None, [no_answer, unfit]), record.NO_LINES, high, low, 21) == (record.NO_LINES, None)
    assert state.decide(_found(None, []), record.NO_LINES, high, low, 21) == (record.NO_LINES, None)
    # Fifteen days is the whole of "forming": a pair past its fifteenth day that is still no box is not forming.
    late = SimpleNamespace(unfit=None, birth_bar=None, r_back=5, s_back=7, fifteenth=20, opening_bar=6, second_bar=7)
    assert state.decide(_found(None, [late]), record.NO_LINES, high, low, 21) == (record.NO_LINES, None)
    # The oldest of two young pairs gives the count.
    older = SimpleNamespace(unfit=None, birth_bar=None, r_back=5, s_back=7, fifteenth=22, opening_bar=8, second_bar=9)
    assert state.decide(_found(None, [young, older]), record.NO_LINES, high, low, 21) == (record.FORMING, 14)


def test_every_read_of_his_40_carries_one_of_the_ten_words(his_last_receding_day):
    tally = {}
    for key, read in his_last_receding_day.items():
        assert read.state in record.STATE_WORDS, (key, read.state)
        assert (read.state_days is not None) == (read.state in (record.FORMING, record.BEYOND_R, record.UNDER_S)), key
        tally[read.state] = tally.get(read.state, 0) + 1
    # On his last receding day the bare read fires on 48 of his 52; YPF's and EXPD's last days advance (they
    # crossed); DDI's rest of Fri 07/08/2026 is refused as more than 1.35 ranges over the box's top, and VTMX's of
    # Wed 02/09/2026 as a slice of a bigger swing down (his drawings of Fri 30/10/2026).
    assert tally == {record.FIRED: 48, record.CROSSED: 2, record.BEYOND_R: 1, record.LINES_NO_LPS: 1}, tally


def test_a_state_word_that_cannot_be_decided_costs_no_fire(monkeypatch):
    """The state word has its own guard, like the story: make the decision raise on a real fire (SYRE, his last
    receding day) and the read still fires, still says ``fired``, and the trail says the word could not be
    decided."""
    s, raw = _standard()["SYRE:2026-02-19"]
    cut = raw.loc[:pd.Timestamp((s.get("lps2") or s["lps"])[1])]
    whole = reader.read("SYRE", cut)

    def broken(*args, **kwargs):
        raise KeyError("forming 12 of 15")

    monkeypatch.setattr(state, "decide", broken)
    read = reader.read("SYRE", cut)
    assert read.fired and read.failed is False and read.state == record.FIRED and read.state_days is None
    assert read.lps == whole.lps and read.events == whole.events
    assert [s.stage for s in read.trail][-1] == state.STAGE and "could not be decided" in read.trail[-1].saying
    assert read.trail[:-1] == whole.trail


def test_alb_the_day_its_box_is_born_the_bars_sit_wholly_over_resistance():
    """ALB on Tue 13/01/2026: the box (150.72 / 143.84) became a box that day and the day's bar (high 177.67, low
    172.75) sits wholly over its resistance area: no LPS, and the word for the open right edge."""
    s, raw = _standard()["ALB:2026-04-13"]
    read = reader.read("ALB", raw.loc[:pd.Timestamp("2026-01-13")])
    assert read.parent is not None and read.lps is None and not read.fired
    assert (read.state, read.state_days) == (record.BEYOND_R, 1)


#: The junk charts whose last days trade wholly past the box shown, with no new box born where they trade (the
#: build log's note of task 12a): the word for the open right edge, and how many days it has run.
_JUNK_RIGHT_EDGE = {"BBVA": (record.BEYOND_R, 6), "BMRN": (record.BEYOND_R, 7), "KWR": (record.BEYOND_R, 6)}


def test_the_junk_charts_that_ran_on_past_their_box_say_so():
    from tools.regression import negative_corpus

    frames, meta = negative_corpus._load_fixture()
    said = {}
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        read = reader.read(case["ticker"], frames[key])
        assert read.state in record.STATE_WORDS, (key, read.state)
        said[key] = (read.state, read.state_days)
    undetermined = {k: v for k, v in said.items() if v[0] in (record.BEYOND_R, record.UNDER_S)}
    assert undetermined == _JUNK_RIGHT_EDGE, said


# --------------------------------------------------------------------------- #
# "After the middle is a must": the four comparisons, each on its own line    #
# --------------------------------------------------------------------------- #
# His ruling (Mon 14/09/2026): Phase D opens only after the middle of the box: "Yes its a must". The middle is
# measured from the box's first day to the read day. Resistance 14, support 10, the area half a range, the box
# from bar 0: a turn ON the middle is not after it.
_P, _V = "peak", "valley"


def test_the_right_side_opens_only_after_the_middle_of_the_box():
    """The round trip: after the dip to 8.5 the price reaches the resistance area (13.8) and the next low holds
    the support area on bar 10. Read on bar 19 the middle is 9.5 and the right side opens on bar 10; read on bar
    20 the middle IS bar 10 and nothing has opened."""
    trip = [(0, _P, 13.0, 0), (2, _V, 8.5, 3), (6, _P, 13.8, 7), (10, _V, 10.2, 11), (12, _P, 12.0, 13)]
    assert LW._right_side_opens(trip, 1, 0, 14.0, 10.0, 1.0, None, 19) == 10
    assert LW._right_side_opens(trip, 1, 0, 14.0, 10.0, 1.0, None, 20) is None
    # The staircase near resistance: two lows over the box's middle price, the second higher (12.2 then 12.6 on
    # bar 12), a top in the resistance area between them. A lower low after the dip rules the round trip out.
    stairs = [(0, _P, 13.0, 0), (2, _V, 8.5, 3), (3, _P, 9.4, 4), (4, _V, 8.0, 5), (6, _P, 13.0, 7),
              (8, _V, 12.2, 9), (10, _P, 13.8, 11), (12, _V, 12.6, 13), (14, _P, 13.2, 15)]
    assert LW._right_side_opens(stairs, 1, 0, 14.0, 10.0, 1.0, None, 23) == 12
    assert LW._right_side_opens(stairs, 1, 0, 14.0, 10.0, 1.0, None, 24) is None


def test_an_upthrust_on_the_middle_day_is_still_phase_b():
    """The spring's "the range ran on": an upthrust at or before the middle of the box means the dip before it
    was Phase B. A top ON the middle (bar 6, the middle 6.0) still counts; half a day past it, it is a push of
    the right side and the dip keeps its word."""
    line = [(0, _P, 13.0, 0), (2, _V, 8.5, 3), (6, _P, 16.0, 7), (8, _V, 11.0, 9)]
    assert LW._range_ran_on(line, 1, 14.0, 10.0, 1.0, None, 6.0) is True
    assert LW._range_ran_on(line, 1, 14.0, 10.0, 1.0, None, 5.5) is False


def test_phase_d_takes_the_first_staircase_after_the_middle():
    """Two staircases near resistance, their second lows on bar 10 and on bar 16. Read on bar 19 (the middle 9.5)
    Phase D opens on bar 10; read on bar 20 the middle IS bar 10, so that one opens nothing and Phase D opens on
    bar 16."""
    line = [(0, _P, 13.0, 0), (2, _V, 12.2, 3), (5, _P, 13.8, 6), (10, _V, 12.6, 11), (13, _P, 13.9, 14),
            (16, _V, 12.9, 17), (18, _P, 13.5, 19)]
    assert LW.phase_d(line, 0, 14.0, 10.0, 1.0, None, None, None, 19)["open_bar"] == 10
    assert LW.phase_d(line, 0, 14.0, 10.0, 1.0, None, None, None, 20)["open_bar"] == 16


# --------------------------------------------------------------------------- #
# Committed or provisional, night after night                                 #
# --------------------------------------------------------------------------- #
def test_on_his_buy_day_the_words_of_the_fire_day_are_still_told(his_last_receding_day):
    """The buy day says ``crossed`` and shows no LPS, but the story still leans on the pullback that was bought:
    THE SOS and the spring named on the fire day are named on the buy day too, on the same days. (Without it the
    three words that lean on the LPS would vanish the day he buys.) One chart moves, by the rules' own reasons and
    toward his drawing: ORMP, where on his buy day the spring is read on Mon 09/03/2026, the day he drew it."""
    kept = checked = 0
    moved = {}
    for key, (s, raw) in _standard().items():
        fire = his_last_receding_day[key]
        if not s.get("trigger") or not fire.fired:
            continue
        buy = reader.read(s["ticker"], raw.loc[:pd.Timestamp(s["trigger"])])
        if buy.state != record.CROSSED or buy.parent != fire.parent:
            continue
        checked += 1
        then = {(e.kind, e.day) for e in fire.events if e.kind in (record.SOS, record.SPRING) and e.committed}
        now = {(e.kind, e.day) for e in buy.events}
        if then <= now:
            kept += 1
        else:
            moved[key] = {e.kind: e.day for e in buy.events if e.kind in (record.SOS, record.SPRING)}
    assert (checked, kept) == (37, 36), (checked, kept, sorted(moved))     # his 52 (Fri 30/10/2026)
    assert moved == {"ORMP:2026-04-13": {record.SPRING: dt.date(2026, 3, 9), record.SOS: dt.date(2026, 3, 17)}}


def test_vik_night_by_night_the_middle_moves_his_upthrust_into_place():
    """VIK, the reader's own read (its box is his to the cent), from his last receding day to his as-of day. The
    middle of the box is measured to the read day, so it moves a half day a night: on Mon 08/06/2026 his push of
    Thu 14/05/2026 sits past the middle and is read as THE SOS, with the dip of Wed 29/04/2026 as the spring; once
    the middle has passed it, it is THE upthrust and that dip is no spring: his own reading. A name moves; the
    days and the prices of the swings never do."""
    s, raw = _standard()["VIK:2026-06-11"]
    told = {}
    for night in raw.loc[pd.Timestamp("2026-06-08"):pd.Timestamp(s["as_of"])].index:
        read = reader.read("VIK", raw.loc[:night])
        told[night.date()] = {e.kind: (e.day, round(e.price, 2)) for e in read.events
                              if e.kind in (record.SPRING, record.UPTHRUST, record.SOS)}
    first, last = told[dt.date(2026, 6, 8)], told[max(told)]
    assert first.get(record.SOS, (None,))[0] == dt.date(2026, 5, 14) and record.UPTHRUST not in first
    assert first.get(record.SPRING, (None,))[0] == dt.date(2026, 4, 29)
    assert last.get(record.UPTHRUST, (None,))[0] == dt.date(2026, 5, 14), last
    assert last.get(record.SPRING, (None,))[0] != dt.date(2026, 4, 29), "his: No for the spring"
    # The swing is the same swing under either name: the same top, to the cent.
    assert first[record.SOS][1] == last[record.UPTHRUST][1] == 92.0
