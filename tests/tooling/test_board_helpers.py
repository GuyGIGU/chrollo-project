"""The boards' shared measurements against his drawings (moved from the yardstick, retired 31/10/2026).

Pinned on hand-built cases whose right answer is worked out from HIS rules, never copied from what a board
happens to print. The headline is deliberately strict: "did the engine fire somewhere in a window around his
setup" is not the question. The question is whether the engine's OWN two lines carry a fire on his last receding
day, at his trigger.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tools.calibration import board_helpers


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _setup(**over) -> dict:
    """One drawn setup, in the corpus's own shape."""
    base = {
        "ticker": "TEST",
        "rails_drawn": {"R": 100.0, "S": 90.0},
        "lps": ["2026-03-02", "2026-03-06"],
        "trigger": "2026-03-09",
        "trigger_price": 101.5,
        "box": ["2026-01-05", "2026-03-06"],
        "anchors": {"R": "2026-01-06", "S": "2026-01-05"},
        "first_rail": "support",
    }
    base.update(over)
    return base


def _read(day: str, **over) -> dict:
    """One engine read of one chart on one day."""
    # `lps_end` is the day the ENGINE's own run of receding days ended. His
    # `trigger` is the day he would BUY — the next session. They are one day
    # apart on every one of his drawings, so they are never compared directly.
    base = {"day": _d(day), "fired": True, "R": 100.0, "S": 90.0,
            "box_start": _d("2026-01-05"), "lps_end": _d("2026-03-06"),
            "trigger_price": 101.5, "stage": None, "seconds": 0.01}
    base.update(over)
    return base


def test_his_last_receding_day_is_the_end_of_his_last_shelf():
    assert board_helpers.his_last_lps_day(_setup()) == _d("2026-03-06")
    two = _setup(lps2=["2026-03-10", "2026-03-13"])
    assert board_helpers.his_last_lps_day(two) == _d("2026-03-13")
    assert board_helpers.his_last_lps_day(_setup(lps=None)) is None


def test_the_strict_headline_needs_his_day_and_his_trigger():
    setup = _setup()
    # Fired on his day, at his trigger: a hit.
    assert board_helpers.strict_hit(setup, [_read("2026-03-06")]) is True
    # Same day, a cent off his trigger: not his buy.
    assert board_helpers.strict_hit(
        setup, [_read("2026-03-06", trigger_price=101.52)]) is False
    # Same day, the engine's run ended a day earlier: not his buy either.
    assert board_helpers.strict_hit(
        setup, [_read("2026-03-06", lps_end=_d("2026-03-05"))]) is False
    # Read on his day, no fire.
    assert board_helpers.strict_hit(setup, [_read("2026-03-06", fired=False)]) is False
    # Fired a day late or early: the chance column's business, never the headline.
    assert board_helpers.strict_hit(setup, [_read("2026-03-09")]) is False
    assert board_helpers.strict_hit(setup, [_read("2026-03-04")]) is False


def test_the_chance_column_shifts_his_day_and_his_trigger_with_it():
    setup = _setup()
    highs = {_d("2026-03-09"): 102.0, _d("2026-03-06"): 101.5, _d("2026-03-04"): 99.0}
    # The engine ended its run on 03-09 and priced the buy at THAT day's high:
    # a chance hit within three days, not within one.
    late = [_read("2026-03-09", lps_end=_d("2026-03-09"), trigger_price=102.0)]
    assert board_helpers.chance_hit(setup, late, highs, shift=3) is True
    assert board_helpers.chance_hit(setup, late, highs, shift=1) is False, \
        "03-09 is three trading days from 03-06 on the calendar"
    # The same day, but priced off his real trigger: asks nothing new.
    assert board_helpers.chance_hit(
        setup, [_read("2026-03-09", lps_end=_d("2026-03-09"), trigger_price=101.5)], highs, shift=3) is False
    # Fired near his day but the run did not end there.
    assert board_helpers.chance_hit(
        setup, [_read("2026-03-04", lps_end=_d("2026-03-03"), trigger_price=99.0)], highs, shift=3) is False


def test_a_setup_with_no_buy_can_never_be_a_strict_hit():
    setup = _setup(trigger=None, trigger_price=None)
    reads = [_read("2026-03-06")]
    assert board_helpers.strict_hit(setup, reads) is False
    assert board_helpers.chance_hit(setup, reads, {}, shift=3) is False


def test_lines_are_close_when_both_sit_inside_half_a_daily_range():
    atr = 2.0      # half a range = 1.0
    assert board_helpers.rails_close(100.0, 90.0, 100.9, 90.9, atr) is True
    assert board_helpers.rails_close(100.0, 90.0, 101.1, 90.0, atr) is False, \
        "one line outside the area is enough"
    assert board_helpers.rails_close(100.0, 90.0, 100.0, 88.9, atr) is False, \
        "support counts as much as resistance"
    assert board_helpers.rails_close(100.0, 90.0, None, None, atr) is False
    with pytest.raises(ValueError):
        board_helpers.rails_close(100.0, 90.0, 100.0, 90.0, 0.0)


def test_a_refused_frame_is_not_reported_as_wrong_lines():
    setup = _setup()
    refused = {"day": _d("2026-03-06"), "error": "no frame", "fired": False}
    assert board_helpers.first_difference(setup, refused, 2.0) == "no frame"
    crashed = {"day": _d("2026-03-06"), "error": "ZeroDivisionError", "fired": False}
    assert board_helpers.first_difference(setup, crashed, 2.0) == "the read crashed"


def test_the_first_difference_is_reported_in_the_order_he_reads():
    setup = _setup()
    atr = 2.0
    assert board_helpers.first_difference(setup, _read("2026-03-06"), atr) is None
    # Wrong lines come first, whatever else is wrong.
    both = _read("2026-03-06", R=105.0, fired=False)
    assert board_helpers.first_difference(setup, both, atr) == "lines"
    assert board_helpers.first_difference(
        setup, _read("2026-03-06", box_start=_d("2026-01-12")), atr) == "opening day"
    assert board_helpers.first_difference(
        setup, _read("2026-03-06", fired=False), atr) == "no fire"
    assert board_helpers.first_difference(
        setup, _read("2026-03-06", trigger_price=101.9), atr) == "trigger"
    assert board_helpers.first_difference(setup, None, atr) == "no read"


def test_his_buy_is_the_day_after_his_last_receding_day_priced_off_it():
    """The law the strict headline rests on, measured on every one of his marks.

    His BUY day is the very next trading day after his last run of receding
    days, and his trigger price is exactly the HIGH of that last receding day
    — every one, no exceptions (37 of 37 on Tue 29/09/2026). This is why his `trigger` field and the
    engine's LPS end are never compared to each other: they are one session
    apart by construction, and comparing them scores every setup a miss.

    If this ever stops holding, the strict headline is measuring something he
    did not draw, and this test is the only thing that would say so.
    """
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    checked = 0
    for setup in setups:
        if setup.get("trigger") is None:
            continue
        raw = fixture_frame(frames, setup_key(setup), setup["ticker"])
        sessions = [d.date() for d in raw.index]
        last_receding = board_helpers.his_last_lps_day(setup)
        buy = _d(setup["trigger"])
        if buy not in sessions:
            # A mark drawn on its last receding day (the scan day) is frozen on a
            # frame that ends there; his buy is the next session, past the frame
            # (CBLL and CLOV, drawn Fri 30/10/2026).
            assert last_receding == sessions[-1] < buy, (
                f"{setup_key(setup)}: his buy is not the session after his last "
                "receding day")
        else:
            assert sessions.index(buy) - sessions.index(last_receding) == 1, (
                f"{setup_key(setup)}: his buy is not the session after his last "
                "receding day")
        high = float(raw.iloc[sessions.index(last_receding)]["High"])
        assert abs(high - float(setup["trigger_price"])) < 0.005, (
            f"{setup_key(setup)}: his trigger price is not that day's high")
        checked += 1
    with_a_buy = sum(1 for s in setups if s.get("trigger") is not None)
    assert checked == with_a_buy >= 37, f"checked {checked} drawings of {with_a_buy} with a buy"
