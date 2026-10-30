"""The stage read: the stock's life cycle on its weekly chart, and the week its advance began (Fri 16/10/2026).

Each rule of ``engine_alpha/stage_read.py`` has a chart here whose answer can be worked out by hand: weekly closes
in whole dollars (so every 40-week average is exact), each week five flat trading days, the high a dollar over the
close and the low a dollar under. The stage read is measure-only; these pin what it says, not what it is worth.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine_alpha import two_eyes_numbers as M
from engine_alpha.stage_read import STAGE_FACTS, advance_start, completed_weeks, read_stage, stages


def _daily(closes, end="2026-10-09"):
    """Five trading days a week ending on the Friday ``end``, each week flat at its weekly close."""
    days = pd.bdate_range(end=end, periods=5 * len(closes))
    close = np.repeat(np.asarray(closes, float), 5)
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close,
                         "Volume": 1e6}, index=days)


def _weeks(closes, end="2026-10-09"):
    close = np.asarray(closes, float)
    return pd.DataFrame({"High": close + 1, "Low": close - 1, "Close": close},
                        index=pd.date_range(end=end, periods=len(close), freq="W-FRI"))


#: 60 flat weeks at $100 with one week at $90 (week 55: a decline week, under an average that falls), then thirty
#: weeks up $2 a week from $101 to $159. The 52-week low is that week's $89, so an advance week must close at $115.70
#: or more: the first is week 68 ($117, over a rising average). The last close under an average that is not rising
#: is week 55's, so the advance began week 56, and on week 89 it is 34 weeks old.
_BASE = [100] * 55 + [90] + [100] * 4
_ADVANCE = _BASE + list(range(101, 161, 2))


def test_the_charts_below_hold_the_numbers_their_comments_say():
    assert len(_ADVANCE) == 90 and _ADVANCE[55] == 90 and _ADVANCE[68] == 117 and _ADVANCE[-1] == 159


# --------------------------------------------------------------------------- #
# The weekly bars
# --------------------------------------------------------------------------- #
def test_a_week_is_the_highest_high_the_lowest_low_and_the_last_close_of_its_days():
    days = pd.bdate_range("2026-10-05", "2026-10-09")
    daily = pd.DataFrame({"High": [11, 14, 12, 13, 12], "Low": [9, 10, 8, 10, 11],
                          "Close": [10, 13, 9, 12, 11.5]}, index=days)
    week = completed_weeks(daily)
    assert list(week.index) == [pd.Timestamp("2026-10-09")]
    assert week.iloc[0].tolist() == [14, 8, 11.5]


def test_the_forming_week_is_left_out_until_its_last_session():
    """Read on Wednesday the week is still forming: the read stands on last Friday's week."""
    daily = _daily([100, 101, 102])
    wednesday = daily.loc[:"2026-10-07"]
    assert completed_weeks(wednesday).index[-1] == pd.Timestamp("2026-10-02")
    assert completed_weeks(daily).index[-1] == pd.Timestamp("2026-10-09")


def test_a_week_whose_friday_is_a_holiday_is_complete_on_its_thursday():
    """Good Friday 2026 is Fri 03/04: the week ends on Thu 02/04, and a read that evening counts it."""
    daily = _daily([100, 101], end="2026-04-03").loc[:"2026-04-02"]
    assert completed_weeks(daily).index[-1] == pd.Timestamp("2026-04-03")
    assert len(completed_weeks(daily)) == 2


# --------------------------------------------------------------------------- #
# The four stages
# --------------------------------------------------------------------------- #
def test_stage_2_is_an_advance_confirmed_30_percent_off_the_low_while_the_average_rises():
    stage = stages(_weeks(_ADVANCE))
    assert stage[55] == 4, "week 55 closes under an average that falls"
    assert stage[56:68] == [1] * 12, "after the decline, no advance week yet: $115 is short of 30% over $89"
    assert stage[68:] == [2] * 22


def test_a_rise_short_of_30_percent_off_the_low_is_still_stage_1():
    """Up to $113 over a rising average, under the 30% the book asks before it calls stage 2."""
    chart = _BASE + list(range(101, 115, 2)) + [113] * 10
    assert stages(_weeks(chart))[-1] == 1
    assert read_stage(_daily(chart)) == {"cycle_stage": 1, "advance_start": None, "advance_weeks": None}


def test_stage_3_once_the_average_stops_rising_after_an_advance():
    """Up $5 a week to $200, then 80 weeks swinging $196 / $204: once the 40 weeks are all swings the average is
    $200 flat, never rising and never falling, so the advance is not followed by a decline: stage 3."""
    chart = _BASE + list(range(105, 205, 5)) + [196, 204] * 40
    stage = stages(_weeks(chart))
    assert stage[-1] == 3
    assert set(stage[-30:]) == {3}
    assert read_stage(_daily(chart))["cycle_stage"] == 3


def test_stage_4_on_a_close_under_a_falling_average():
    chart = [100] * 60 + list(range(98, 58, -2))
    assert stages(_weeks(chart))[-1] == 4
    assert read_stage(_daily(chart)) == {"cycle_stage": 4, "advance_start": None, "advance_weeks": None}


def test_a_rally_over_a_still_falling_average_after_a_decline_is_the_turn_stage_1_not_4():
    """Down to $60, then up to $90: the 40-week average ($86.125) still falls ($87.875 four weeks earlier), the price
    is over it. A falling knife's rally is not a decline week; after the decline it is stage 1."""
    chart = [100] * 60 + list(range(98, 58, -2)) + list(range(65, 95, 5))
    weeks = _weeks(chart)
    average = weeks["Close"].rolling(40).mean()
    assert average.iloc[-1] == 86.125 and average.iloc[-5] == 87.875
    assert stages(weeks)[-1] == 1


def test_a_pullback_under_a_still_rising_average_stays_stage_2():
    """Week 90 drops to $120, under the average ($122.75), which still rises: a pullback inside the advance."""
    chart = _ADVANCE + [120]
    weeks = _weeks(chart)
    average = weeks["Close"].rolling(40).mean()
    assert weeks["Close"].iloc[-1] < average.iloc[-1] and average.iloc[-1] > average.iloc[-2]
    assert stages(weeks)[-1] == 2
    read = read_stage(_daily(chart))
    assert read["advance_start"] == completed_weeks(_daily(chart)).index[56].date().isoformat()
    assert read["advance_weeks"] == 35, "a close under a rising average does not restart the advance"


def test_a_shakeout_week_under_an_average_still_up_on_the_month_stays_stage_2_and_restarts_the_count():
    """Week 90 drops to $95: the average ticks down on the week ($122.125 from $122.25) but stands over its value four
    weeks earlier ($117.975), so it still rises and the advance stands. The count rule reads the week over week: a
    close under an average that is not rising, so the count restarts next week and no advance week is said yet."""
    chart = _ADVANCE + [95]
    weeks = _weeks(chart)
    average = weeks["Close"].rolling(40).mean()
    assert (average.iloc[-1], average.iloc[-2], average.iloc[-5]) == (122.125, 122.25, 117.975)
    assert stages(weeks)[-1] == 2
    assert advance_start(weeks, len(weeks) - 1) == len(weeks)
    assert read_stage(_daily(chart)) == {"cycle_stage": 2, "advance_start": None, "advance_weeks": None}


def test_the_30_percent_is_over_the_52_week_low_not_an_older_one():
    """A year-old base at $60, then $100 for a year with one week at $90 under a falling average (a decline week),
    then up to $112: 30% over the 52-week low ($89) is $115.70, so no advance week yet: stage 1. Measured from the
    $59 low of two years ago it would be."""
    chart = [60] * 50 + list(range(62, 102, 2)) + [100] * 50 + [90] + [100] * 4 + list(range(102, 114, 2))
    assert stages(_weeks(chart))[-1] == 1


def test_a_stage_reads_no_later_week():
    """The stage of every week is the stage a read standing on that week gives: nothing after it moves it."""
    chart = _BASE + list(range(105, 205, 5)) + [196, 204] * 25 + list(range(190, 120, -5))
    weeks = _weeks(chart)
    whole = stages(weeks)
    assert [stages(weeks.iloc[:i + 1])[-1] for i in range(len(weeks))] == whole
    assert set(whole) == {None, 1, 2, 3, 4}, "the chart walks through every stage"


def test_fewer_weeks_than_the_average_and_its_month_need_is_not_read():
    """The 40-week average and its value four weeks earlier: 44 completed weeks, or no stage."""
    assert read_stage(_daily(list(range(100, 143))))["cycle_stage"] is None
    assert read_stage(_daily(list(range(100, 144))))["cycle_stage"] == 2


# --------------------------------------------------------------------------- #
# The advance
# --------------------------------------------------------------------------- #
def test_the_advance_begins_the_week_after_the_last_close_under_an_average_that_is_not_rising():
    read = read_stage(_daily(_ADVANCE))
    weeks = completed_weeks(_daily(_ADVANCE))
    assert read == {"cycle_stage": 2, "advance_start": weeks.index[56].date().isoformat(), "advance_weeks": 34}
    assert read["advance_start"] == "2026-02-20"


def test_a_close_under_a_rising_average_is_no_restart_of_the_advance(monkeypatch):
    """The count rule asks for an average that is NOT rising: with a 3-week average, week 3 ($90 under $96.67, the average
    down from $100) restarts the count; week 7 ($114 under $114.67, the average up from $110) does not."""
    monkeypatch.setattr(M, "STAGE_MA_WEEKS", 3)
    weeks = _weeks([100, 100, 100, 90, 100, 110, 120, 114, 130])
    assert advance_start(weeks, len(weeks) - 1) == 4


def test_the_advance_is_said_in_stage_2_only():
    for chart in (_BASE + list(range(105, 205, 5)) + [196, 204] * 40,      # stage 3
                  [100] * 60 + list(range(98, 58, -2)),                    # stage 4
                  _BASE + list(range(101, 115, 2)) + [113] * 10):          # stage 1
        read = read_stage(_daily(chart))
        assert read["cycle_stage"] != 2
        assert read["advance_start"] is None and read["advance_weeks"] is None


def test_an_advance_older_than_the_frame_has_no_start_said():
    """Five years up, never a close under the average: the advance began before the frame, so no week is named."""
    chart = list(range(100, 360))
    read = read_stage(_daily(chart))
    assert read == {"cycle_stage": 2, "advance_start": None, "advance_weeks": None}


# --------------------------------------------------------------------------- #
# A stock fact never costs a fire
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("frame", [
    pd.DataFrame(),
    pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.bdate_range("2026-01-05", periods=2)),
    pd.DataFrame({"High": ["a"], "Low": ["b"], "Close": ["c"]}, index=pd.bdate_range("2026-01-05", periods=1)),
])
def test_a_frame_the_read_cannot_use_gives_empty_facts_never_a_raise(frame):
    assert read_stage(frame) == {key: None for key in STAGE_FACTS}
