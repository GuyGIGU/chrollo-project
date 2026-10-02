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

import pandas as pd
import pytest

from engine_alpha.two_eyes import lps, record, walk

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
