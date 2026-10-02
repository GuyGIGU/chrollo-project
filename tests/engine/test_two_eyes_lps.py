"""Stage 6 of the two-eyes reader (task 12a): the LPS and its trigger on the reader's own box — his words first,
then the rule on hand-built bars, then his drawn windows (43 on Fri 02/10/2026) and the junk he named.

His words that these pin:

* the traits (Tue 08/09/2026): "I generally prefer to define it by the traits I want to see and deem high quality
  like Receding Price move over time, Lowering (and low) spread below average, 2 - 5 bars.";
* the window and the trigger (Sat 12/09/2026, Sun 13/09/2026): "The LPS window ends on the last receding day
  before the buy"; the window is the last run of receding days ending today, the day before it is the top; on
  the start: "Lets go with the day after"; the trigger is the last day's high and the buy is the cross of it;
* a cross inside the pullback (Sun 13/09/2026, on MRK): "Bought on 05/08/26 because that's the day I saw the stock
  on, the prior move on 03/08 - 04/08 seemed like a valid pullback to me to place my trade on";
* his four sentences, the only things that refuse an LPS:
  1. sellers rising (Mon 14/09/2026, on AEF): "3 bars with huge increases in both spread and price changes meaning
     the pull back is increasing with sellers";
  2. the slice (same message): "you cut the move off and it's a part of a bigger swing downwards that reaches
     support, we cannot ignore that, that is a fatal flaw of our chart reading fundementals"; and (Tue 08/09/2026)
     "its seems like the correction is getting to deep";
  3. under support (Sun 13/09/2026): "Lets say not below the support area (the area below the support that can be
     considered respected)", and on JAZZ: "I would say the LPS is on the Support rather then Under it since most of
     the move is above it and only small parts of it poke out down";
  4. over resistance (Thu 10/09/2026): "preferably pretty close Since we prefer the LPS be close to the
     consolidation process (the energy gathering stage)" — "Lets go with that ceiling 1.35 I guess....";
* the tail (Mon 14/09/2026, on BMRN): "the blue part can be considered an LPS entry because of the moves final bars
  being pretty shallow and in decline";
* no raw number gates a setup (Sat 12/09/2026): "It's hard to gate using a raw number in case we reject a valid
  setups because of a small neumeric gap".
"""
from __future__ import annotations
from _paths import REPO_ROOT

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from engine_alpha.two_eyes.line import Turn

_ROOT = str(REPO_ROOT)
_DAY0 = dt.date(2026, 1, 5)


def _day(bar: int) -> dt.date:
    return (pd.Timestamp(_DAY0) + pd.tseries.offsets.BDay(bar)).date()


def _valley(bar: int, price: float) -> Turn:
    return Turn(bar=bar, day=_day(bar), kind="valley", price=float(price), knowable_bar=bar + 1,
                knowable_day=_day(bar + 1), size_ranges=1.0)


def _bars(rows) -> tuple:
    """Hand-built days, each ``(high, low)``; every day's range reads two points unless said otherwise."""
    high = np.array([r[0] for r in rows], dtype=float)
    low = np.array([r[1] for r in rows], dtype=float)
    return high, low, np.full(len(rows), 2.0, dtype=float)


#: A box 100 / 94 measured in a two-point daily range (its area is one point), born long before these days.
_BOX = {"R": 100.0, "S": 94.0, "box_unit": 2.0, "born_bar": 0}

#: Six quiet days inside the box, then a rise to a top at 101 (bar 8) and three receding days resting just under
#: resistance: his picture of a pullback. The rise launched from the valley at bar 5.
_QUIET = [(97.0, 95.6), (97.4, 95.9), (97.2, 95.8), (97.6, 96.0), (97.3, 95.9), (96.9, 95.4)]
_RISE = [(98.4, 96.6), (99.8, 98.0), (101.0, 99.2)]
_PULLBACK = [(100.6, 98.9), (100.1, 98.6), (99.7, 98.4)]
_SCENE = _QUIET + _RISE + _PULLBACK
_LAUNCH = [_valley(5, 95.4)]


def _read(rows, turns=_LAUNCH, read_bar=None, **box):
    from engine_alpha.two_eyes import lps

    high, low, ranges = _bars(rows)
    return lps.read(high, low, ranges, turns, **{**_BOX, **box}, read_bar=read_bar)


# --------------------------------------------------------------------------- #
# The window and the trigger                                                  #
# --------------------------------------------------------------------------- #
def test_a_receding_day_makes_a_lower_high_or_a_lower_low_than_the_day_before():
    from engine_alpha.two_eyes import lps

    high = np.array([10.0, 9.5, 9.8, 9.8, 10.2, 10.6, 10.6])
    low = np.array([9.0, 8.8, 9.0, 8.9, 9.1, 8.7, 8.7])
    assert lps.recedes(high, low, 0) is False, "the first day has no day before it"
    assert lps.recedes(high, low, 1) is True, "a lower high"
    assert lps.recedes(high, low, 2) is False, "a higher high and a higher low: the day advances"
    assert lps.recedes(high, low, 3) is True, "an equal high and a lower low"
    assert lps.recedes(high, low, 4) is False
    assert lps.recedes(high, low, 5) is True, "a higher high and a lower low still recedes: it made a lower low"
    assert lps.recedes(high, low, 6) is False, "the same high and the same low recede nothing"


def test_the_window_is_the_last_run_of_receding_days_and_the_day_before_it_is_its_top():
    got = _read(_SCENE)
    assert (got.top_bar, got.start_bar, got.end_bar) == (8, 9, 11)
    assert got.refused == () and got.crossed_bar is None
    # Read a day earlier the run is a day shorter and ends on THAT day: one window per read day.
    earlier = _read(_SCENE[:-1])
    assert (earlier.top_bar, earlier.start_bar, earlier.end_bar) == (8, 9, 10)
    # One receding day is a window: five of his 37 are one receding day under their top.
    one = _read(_SCENE[:-2])
    assert (one.top_bar, one.start_bar, one.end_bar) == (8, 9, 9)


def test_the_trigger_is_the_last_receding_days_high_and_the_low_is_the_pullbacks_lowest_low():
    got = _read(_SCENE)
    assert got.trigger == 99.7
    assert got.low == 98.4
    assert _read(_SCENE[:-1]).trigger == 100.1


def test_a_day_with_a_higher_high_and_a_lower_low_inside_the_run_does_not_end_it():
    rows = _QUIET + _RISE + [(100.6, 98.9), (100.9, 98.6), (99.7, 98.4)]
    got = _read(rows)
    assert (got.top_bar, got.end_bar) == (8, 11), "the outside day made a lower low: the run goes on through it"
    assert got.bought is None, "the last day crossed nothing"


def test_a_last_day_that_crosses_the_trigger_and_makes_a_lower_low_is_a_buy_and_the_pullback_goes_on():
    """Five of his own drawings end on such a day (MATX, NTCT, PBT, ROIV, WTS): his trigger is that day's high. On
    six more it is his buy day (DLX, MTLS, RGR, SKYT, UNF, VIK): the cross was his buy."""
    from engine_alpha.two_eyes import lps

    rows = _QUIET + _RISE + [(100.6, 98.9), (100.9, 98.6)]
    got = _read(rows)
    assert (got.top_bar, got.end_bar, got.trigger) == (8, 10, 100.9)
    assert got.bought == 100.6 and got.crossed_bar is None
    found, steps, state = lps.record(got, [_day(i) for i in range(len(rows))], read_bar=len(rows) - 1)
    assert state == lps.FIRED and found.trigger_price == 100.9
    assert "100.60" in steps[0].saying and "buy" in steps[0].saying
    # The day before was refused: its trigger was never a buy.
    refused = _read(_QUIET + _RISE + [(100.2, 98.4), (99.0, 97.2), (97.9, 95.8), (98.3, 95.7)], S=90.0)
    assert refused.end_bar == 12 and refused.bought is None
    # The day before there was no box yet: there was no fire to buy.
    assert _read(rows, born_bar=10).bought is None and _read(rows, born_bar=9).bought == 100.6
    # The day before did not recede: there was no trigger to cross.
    assert _read(_QUIET + _RISE + [(101.4, 99.0)]).bought is None


def test_a_day_that_advances_ends_the_run_and_the_next_receding_day_opens_a_new_one():
    rows = _SCENE + [(100.3, 98.9), (100.0, 98.7)]
    got = _read(rows)
    assert (got.top_bar, got.start_bar, got.end_bar) == (12, 13, 13)
    assert got.trigger == 100.0


def test_a_cross_of_the_trigger_is_the_buy_and_the_pullback_is_no_longer_overhead():
    rows = _SCENE + [(100.3, 98.9)]                     # its high crosses 99.7, the last receding day's high
    got = _read(rows)
    assert (got.end_bar, got.trigger) == (11, 99.7), "the pullback still ends on its last receding day"
    assert got.crossed_bar == 12
    # A later day: the cross stays where it happened.
    later = _read(rows + [(100.8, 99.5)])
    assert (later.end_bar, later.crossed_bar) == (11, 12)


def test_a_day_that_neither_recedes_nor_crosses_leaves_the_pullback_overhead():
    rows = _SCENE + [(99.7, 98.4)]                      # the same high and the same low
    got = _read(rows)
    assert (got.end_bar, got.trigger, got.crossed_bar) == (11, 99.7, None)


#: His BMRN picture, bar for bar (Tue 09/06 to Thu 18/06/2026): a deep correction off the push over resistance,
#: "the blue part can be considered an LPS entry because of the moves final bars being pretty shallow and in
#: decline". The blue part is Tue 16/06 to Thu 18/06.
_BMRN = [(57.05, 55.11), (57.71, 56.09), (56.89, 56.01),
         (58.11, 56.85),                                    # Tue 09/06: the day before the run
         (58.26, 55.99), (56.59, 55.25), (56.26, 55.48),    # Wed 10/06, Thu 11/06, Fri 12/06
         (56.35, 54.99),                                    # Mon 15/06
         (55.83, 54.61), (56.06, 54.49), (55.62, 54.26)]    # Tue 16/06, Wed 17/06, Thu 18/06


def test_a_run_longer_than_five_bars_is_read_on_its_last_five_from_their_highest_high():
    from engine_alpha.two_eyes import lps, method_numbers as M

    assert M.LPS_MAX_BARS == 5, 'his "2 - 5 bars"'
    high, low, ranges = _bars(_BMRN)
    assert lps.run_top(high, low, 10) == 3, "the run is seven receding days under Tue 09/06"
    got = lps.read(high, low, ranges, [_valley(2, 56.01)], R=57.5, S=53.36, box_unit=1.667, born_bar=0)
    assert (got.top_bar, got.start_bar, got.end_bar) == (7, 8, 10), \
        "the blue part: Tue 16/06 to Thu 18/06, under Mon 15/06's high"
    assert got.trigger == 55.62
    # A run of exactly five bars (the top and four receding days) is read whole.
    five = _read(_QUIET + _RISE + [(100.6, 98.9), (100.4, 98.8), (100.1, 98.6), (99.7, 98.4)])
    assert (five.top_bar, five.start_bar, five.end_bar) == (8, 9, 12)
    # One day longer and the top moves to the highest high of the last five bars, the last day left out.
    six = _read(_QUIET + _RISE + [(100.6, 98.9), (100.4, 98.8), (100.1, 98.6), (99.9, 98.5), (99.7, 98.4)])
    assert (six.top_bar, six.start_bar, six.end_bar) == (9, 10, 13)
    # The last day is never its own pullback's top, though it made the highest high of the five and a lower low.
    six = _read(_QUIET + _RISE + [(100.2, 98.9), (100.1, 98.8), (100.0, 98.6), (99.9, 98.5), (100.5, 98.4)])
    assert (six.top_bar, six.start_bar, six.end_bar) == (9, 10, 13)


# --------------------------------------------------------------------------- #
# The unit                                                                    #
# --------------------------------------------------------------------------- #
def test_the_lps_is_measured_in_the_daily_range_five_trading_days_before_its_last_day():
    from engine_alpha.two_eyes import lps, method_numbers as M

    assert M.LPS_UNIT_DAYS_BACK == 5
    high, low, ranges = _bars(_SCENE)
    ranges = ranges.copy()
    ranges[6] = 1.0                                     # five trading days before the last day (bar 11)
    ranges[7:] = 3.0                                    # the pullback's own days do not move their own yardstick
    got = lps.read(high, low, ranges, _LAUNCH, **_BOX)
    assert got.unit == 1.0
    # Read a day earlier the unit is the day before that one.
    assert lps.read(high[:-1], low[:-1], ranges[:-1], _LAUNCH, **_BOX).unit == 2.0
    # A day with no range is no yardstick: it would compare false with every limit and refuse nothing.
    for missing in (float("nan"), 0.0):
        ranges[6] = missing
        with pytest.raises(ValueError, match="no daily range"):
            lps.read(high, low, ranges, _LAUNCH, **_BOX)


# --------------------------------------------------------------------------- #
# His four sentences, each named                                              #
# --------------------------------------------------------------------------- #
#: His AEF picture, bar for bar (Mon 01/06 to Tue 09/06/2026), against the box the reader shows there.
_AEF = [(9.46, 9.31), (9.74, 9.50), (9.89, 9.72), (9.93, 9.60), (9.97, 9.85),
        (10.10, 9.86),                                      # Mon 01/06
        (10.14, 10.02),                                     # Tue 02/06: the top
        (10.00, 9.78), (9.75, 9.46), (9.36, 8.84),          # Wed 03/06, Thu 04/06, Fri 05/06
        (9.16, 8.94), (9.45, 8.73)]                         # Mon 08/06, Tue 09/06
#: Each of those days' own range, as the reader's frame carries it.
_AEF_RANGES = [0.27, 0.28, 0.27, 0.28, 0.26, 0.26, 0.25, 0.25, 0.26, 0.31, 0.30, 0.34]
_AEF_BOX = {"R": 9.04, "S": 8.66, "box_unit": 0.304, "born_bar": 0}


def _aef(read_bar: int):
    from engine_alpha.two_eyes import lps

    high = np.array([r[0] for r in _AEF])
    low = np.array([r[1] for r in _AEF])
    ranges = np.array(_AEF_RANGES)
    return lps.read(high[:read_bar + 1], low[:read_bar + 1], ranges[:read_bar + 1], [_valley(5, 9.86)], **_AEF_BOX)


def test_sentence_one_three_bars_each_wider_and_each_falling_further_is_sellers_rising():
    from engine_alpha.two_eyes import lps

    thursday = _aef(8)                                  # Tue 02/06, Wed 03/06, Thu 04/06: his three bars
    assert thursday.sellers_rising is True and lps.SELLERS_RISING in thursday.refused
    assert _aef(9).sellers_rising is True, "Fri 05/06: wider again, and falling further again"
    # Falling further each day and the last fall a big one, but the last day is not wider than the day before.
    rows = _QUIET + _RISE + [(100.4, 99.6), (99.9, 98.9), (98.7, 97.8)]
    assert _read(rows).sellers_rising is False, "the last day's range (0.9) is not wider than the day before's (1.0)"
    # Each wider and the last fall a big one, but the second day fell less than the first.
    rows = _QUIET + _RISE + [(99.8, 98.9), (99.6, 98.5), (98.4, 97.0)]
    assert _read(rows).sellers_rising is False, "the second day fell 0.3 after the first fell 0.75"
    # Each wider, each falling further, but the last fall smaller than the day before's whole range.
    rows = _QUIET + [(98.4, 96.6), (99.8, 98.0), (101.0, 100.2)] + [(100.7, 99.4), (100.2, 98.7)]
    got = _read(rows)
    assert got.sellers_rising is False, "the last fall (0.6) is not bigger than the day before's range (1.3)"
    # The same bars with the last day falling more than the day before's whole range.
    rows = _QUIET + [(98.4, 96.6), (99.8, 98.0), (101.0, 100.2)] + [(100.7, 99.4), (99.3, 97.9)]
    assert _read(rows).sellers_rising is True
    # Two bars are not three: one receding day under its top never reads sellers rising, though the three bars
    # that end on it are each wider and each "falling further" (the first two are the rise into the top).
    got = _read(_QUIET[:-1] + [(97.0, 96.0), (99.0, 98.2), (100.0, 99.0)] + [(98.6, 97.4)], turns=[_valley(5, 96.0)])
    assert (got.top_bar, got.end_bar) == (7, 8) and got.sellers_rising is False


def test_sentence_two_a_pullback_deeper_than_his_deepest_is_a_slice_of_a_bigger_swing_down():
    from engine_alpha.two_eyes import lps, method_numbers as M

    assert M.LPS_DEPTH_MAX_RANGES == 2.5
    # From the top at 101 down to 96.2: 2.4 daily ranges, a pullback.
    shallow = _read(_QUIET + _RISE + [(100.2, 98.4), (99.0, 97.2), (98.1, 96.2)], S=90.0)
    assert shallow.depth == pytest.approx(2.4) and lps.SLICE not in shallow.refused
    # Down to 95.8: 2.6 daily ranges from its top.
    deep = _read(_QUIET + _RISE + [(100.2, 98.4), (99.0, 97.2), (97.9, 95.8)], S=90.0)
    assert deep.depth == pytest.approx(2.6) and deep.refused == (lps.SLICE,)
    # The depth is from the top of the swing on the line, not from the window's own top: a bounce too small to
    # turn the line does not hide the fall before it.
    rows = _QUIET + _RISE + [(100.0, 97.6), (98.6, 96.9), (98.9, 97.0), (98.5, 95.8)]
    got = _read(rows, S=90.0)
    assert (got.top_bar, got.swing_top_bar) == (11, 8), "the window opens under the bounce; the swing under 101"
    assert got.depth == pytest.approx(2.6) and lps.SLICE in got.refused
    # The swing opens at the line's last valley before the run: an older, higher high behind that valley is
    # another swing's.
    older = _read([(103.0, 101.0)] + _QUIET[1:] + _RISE + [(100.2, 98.4), (99.0, 97.2), (98.1, 96.2)], S=90.0)
    assert older.swing_top_bar == 8 and older.depth == pytest.approx(2.4) and older.refused == ()
    # A valley the line committed INSIDE the run opens no new swing either: the pullback is the whole run, and
    # its depth is from the top it fell from.
    rows = _QUIET + _RISE + [(100.2, 98.4), (100.6, 97.2), (98.1, 96.2)]
    inside = _read(rows, turns=[_valley(5, 95.4), _valley(9, 98.4)], S=90.0)
    assert (inside.top_bar, inside.swing_top_bar) == (8, 8) and inside.depth == pytest.approx(2.4)
    # His AEF picture: Mon 08/06 and Tue 09/06 are the tail of the fall from 10.14.
    for bar in (10, 11):
        assert _aef(bar).refused == (lps.SLICE,), f"bar {bar}"
        assert _aef(bar).swing_top_bar == 6


def test_sentence_three_mostly_under_the_support_area_refuses_and_a_poke_under_it_does_not():
    from engine_alpha.two_eyes import lps, method_numbers as M

    assert M.LPS_UNDER_SUPPORT_SHARE == 0.5
    rows = [(96.0, 94.6)] * 6 + [(95.2, 94.0), (95.6, 94.2), (95.9, 94.4)]
    # On support: the lows poke under the area (93.0) and most of each bar is above it — his JAZZ.
    on_support = _read(rows + [(95.4, 93.4), (95.0, 92.8), (94.8, 92.6)], turns=[_valley(6, 94.0)])
    assert on_support.under_support == pytest.approx(0.6 / 6.4) and on_support.refused == ()
    # Under it: most of the pullback's travel lies under the area.
    under = _read(rows + [(94.0, 92.4), (93.0, 91.6), (92.6, 91.2)], turns=[_valley(6, 94.0)])
    assert under.under_support == pytest.approx(3.4 / 4.4) and under.refused == (lps.UNDER_SUPPORT,)


def test_sentence_four_more_than_his_ceiling_over_resistance_refuses_and_his_farthest_does_not():
    from engine_alpha.two_eyes import lps, method_numbers as M

    assert M.LPS_CEILING_RANGES == 1.35
    base = _QUIET + [(99.0, 97.0), (102.0, 99.5), (104.6, 102.4)]
    near = _read(base + [(104.2, 103.0), (103.9, 102.6)])          # its low 1.30 ranges over resistance: his ST
    assert near.over_resistance == pytest.approx(1.30) and near.refused == ()
    far = _read(base + [(104.2, 103.0), (103.9, 102.8)])           # 1.40 over
    assert far.over_resistance == pytest.approx(1.40) and far.refused == (lps.OVER_RESISTANCE,)
    # Inside the box the distance is negative and nothing is refused.
    assert _read(_SCENE).over_resistance == pytest.approx(-0.8)
    # The distance is counted in the LPS's own unit, never in the range the box was born in: a box born in a
    # one-point range does not make the same pullback twice as far.
    narrow = _read(base + [(104.2, 103.0), (103.9, 102.6)], box_unit=1.0)
    assert narrow.over_resistance == pytest.approx(1.30) and narrow.refused == ()


def test_every_sentence_that_refuses_is_named_in_his_order():
    from engine_alpha.two_eyes import lps

    assert lps.SENTENCES == (lps.SELLERS_RISING, lps.SLICE, lps.UNDER_SUPPORT, lps.OVER_RESISTANCE)
    thursday = _aef(8)                                  # Thu 04/06: sellers rising AND 1.5 ranges over resistance
    assert thursday.refused == (lps.SELLERS_RISING, lps.OVER_RESISTANCE)
    assert _aef(9).refused == (lps.SELLERS_RISING, lps.SLICE)      # Fri 05/06: back in the box, 5 ranges down
    assert _aef(7).refused == (lps.OVER_RESISTANCE,)    # Wed 03/06: the first falling day, far over the box


def test_his_aef_picture_fires_no_lps_on_any_day():
    from engine_alpha.two_eyes import lps

    for bar in range(6, len(_AEF)):
        got = _aef(bar)
        assert got is None or got.refused or got.crossed_bar is not None or got.end_bar < bar, \
            f"bar {bar}: {got}"


# --------------------------------------------------------------------------- #
# The record: the LPS, the trail, the state word                              #
# --------------------------------------------------------------------------- #
def _record(rows, **box):
    from engine_alpha.two_eyes import lps

    return lps.record(_read(rows, **box), [_day(i) for i in range(len(rows))], read_bar=len(rows) - 1)


def test_a_pullback_none_of_his_sentences_refuses_is_the_lps_and_the_read_fires():
    from engine_alpha.two_eyes import lps, record

    found, steps, state = _record(_SCENE)
    assert state == lps.FIRED == "fired"
    assert (found.start_day, found.end_day, found.trigger_price) == (_day(9), _day(11), 99.7)
    assert found.read_against == record.ROLE_PARENT
    assert [s.stage for s in steps] == ["LPS"]
    assert "99.70" in steps[0].saying and f"{_day(11):%a %d/%m/%Y}" in steps[0].saying


def test_a_refused_pullback_is_no_lps_and_the_trail_names_the_sentence():
    from engine_alpha.two_eyes import lps

    found, steps, state = _record(_QUIET + _RISE + [(100.2, 98.4), (99.0, 97.2), (97.9, 95.8)], S=90.0)
    assert found is None and state == lps.LINES_NO_LPS == "lines, no LPS yet"
    assert [s.stage for s in steps] == ["LPS"] and lps.SLICE in steps[0].saying


def test_on_the_buy_day_the_read_says_crossed_and_nothing_fires():
    from engine_alpha.two_eyes import lps

    found, steps, state = _record(_SCENE + [(100.3, 98.9)])
    assert found is None and state == lps.CROSSED == "crossed"
    assert "99.70" in steps[0].saying and f"{_day(12):%a %d/%m/%Y}" in steps[0].saying
    # The day after the buy: the pullback is behind, nothing is overhead, nothing fires.
    found, steps, state = _record(_SCENE + [(100.3, 98.9), (100.8, 99.5)])
    assert found is None and state == lps.LINES_NO_LPS


def test_a_refused_pullback_that_is_crossed_is_no_buy():
    from engine_alpha.two_eyes import lps

    rows = _QUIET + _RISE + [(100.2, 98.4), (99.0, 97.2), (97.9, 95.8), (98.4, 96.0)]
    found, steps, state = _record(rows, S=90.0)
    assert found is None and state == lps.LINES_NO_LPS


def test_a_pullback_that_ended_before_the_box_was_a_box_is_not_its_lps():
    from engine_alpha.two_eyes import lps

    # The box is born on the buy day itself: the day before there was no box, so there was no fire to buy.
    found, steps, state = _record(_SCENE + [(100.3, 98.9)], born_bar=12)
    assert found is None and state == lps.LINES_NO_LPS
    # Born on the pullback's last day: the fire is legal that day.
    found, steps, state = _record(_SCENE, born_bar=11)
    assert found is not None and state == lps.FIRED


def test_no_box_no_lps():
    from engine_alpha.two_eyes import lps

    assert lps.record(None, [_day(i) for i in range(3)], read_bar=2) == (None, (), None)


# --------------------------------------------------------------------------- #
# What the core's blind check found (Sun 27/09/2026): a verdict that changed   #
# after the fact, and two rules of the long run no test was watching          #
# --------------------------------------------------------------------------- #
def _valley_known(bar: int, price: float, known: int) -> Turn:
    return Turn(bar=bar, day=_day(bar), kind="valley", price=float(price), knowable_bar=known,
                knowable_day=_day(known), size_ranges=1.0)


#: A swing up to 104 (bar 8), a fall to 97.6 (bar 11), a bounce too small to turn the line, and a one-day pullback
#: that ends on bar 14. Bar 15 equals its high, which crosses nothing; bar 16 crosses it, and that rally is what
#: turns the line at the low of bar 11: a valley known on bar 16, two days after the pullback ended.
_DEEP = _QUIET + [(98.4, 96.6), (101.0, 98.0), (104.0, 100.5), (102.5, 100.0), (101.0, 98.6), (99.6, 97.6),
                  (100.0, 97.8), (100.2, 98.0), (99.9, 97.9), (99.9, 98.0), (101.0, 98.2)]


def test_a_pullback_is_judged_on_what_was_known_the_evening_it_ended():
    """A pullback refused the evening it ended put no trigger on the board, so no later day can have crossed
    one: its verdict is the verdict of that evening, whatever the line learns afterwards."""
    from engine_alpha.two_eyes import lps

    that_evening = _read(_DEEP[:15])
    assert (that_evening.top_bar, that_evening.end_bar, that_evening.swing_top_bar) == (13, 14, 8)
    assert that_evening.depth == pytest.approx(3.2) and that_evening.refused == (lps.SLICE,)
    later = _read(_DEEP, turns=_LAUNCH + [_valley_known(11, 97.6, known=16)])
    assert (later.end_bar, later.crossed_bar) == (14, 16)
    assert (later.swing_top_bar, later.refused) == (8, (lps.SLICE,)), "the verdict changed after the fact"
    found, steps, state = lps.record(later, [_day(i) for i in range(len(_DEEP))], read_bar=16)
    assert found is None and state == lps.LINES_NO_LPS and lps.SLICE in steps[0].saying
    # A turn the line had already made by that evening is read, as it always was.
    known = _read(_DEEP, turns=_LAUNCH + [_valley_known(11, 97.6, known=14)])
    assert (known.swing_top_bar, known.refused, known.crossed_bar) == (13, (), 16)
    # The trigger of the day before, when the pullback's own last day crossed it, is judged on what was known
    # the evening before too: a slice that evening, it was never a buy.
    rows = _DEEP[:13] + [(99.8, 97.7), (100.1, 97.5)]
    assert _read(rows[:14]).refused == (lps.SLICE,)
    went_on = _read(rows, turns=_LAUNCH + [_valley_known(11, 97.6, known=14)])
    assert went_on.end_bar == 14 and went_on.bought is None, "the pullback of bar 13 was refused that evening"


#: A run of six receding days under a top at 104 (bar 8): longer than five bars, so it is read on its last five,
#: from their highest high (bar 10). Bar 12 is an outside day, a higher high and a lower low.
_LONG_RUN = _QUIET + [(98.4, 96.6), (101.0, 98.0), (104.0, 100.5), (103.0, 100.8), (102.0, 100.0), (101.0, 99.0),
                      (101.4, 98.6), (100.6, 98.4), (100.0, 98.2)]


def test_the_swings_top_is_looked_for_from_the_runs_own_top_not_from_the_trimmed_windows():
    from engine_alpha.two_eyes import lps

    high, low, _ = _bars(_LONG_RUN)
    # The line turned inside the run, under the run's top and on the trimmed window's.
    got = _read(_LONG_RUN, turns=_LAUNCH + [_valley(10, 100.0)])
    assert (lps.run_top(high, low, 14), got.top_bar, got.end_bar) == (8, 10, 14)
    assert got.swing_top_bar == 8 and got.depth == pytest.approx(2.9)
    assert got.refused == (lps.SLICE,), "the long decline is the one sentence two exists for"


#: A run of six receding days whose last four make higher highs and lower lows, so the highest high of its last
#: five bars is the day before the last; its last three bars widen and fall further.
_WIDENING = _QUIET + [(98.4, 96.6), (101.0, 98.0), (104.0, 102.0), (103.0, 101.5), (101.0, 100.4), (101.2, 100.2),
                      (101.6, 100.0), (101.8, 99.0), (99.0, 94.8)]


def test_sentence_one_is_read_on_the_run_and_not_on_the_trimmed_window():
    from engine_alpha.two_eyes import lps

    high, low, _ = _bars(_WIDENING)
    got = _read(_WIDENING)
    assert (lps.run_top(high, low, 14), got.top_bar, got.end_bar) == (8, 13, 14)
    assert got.sellers_rising is True, "one receding day under the trimmed window's top, six under the run's"
    assert got.refused == (lps.SELLERS_RISING, lps.SLICE)


# --------------------------------------------------------------------------- #
# His drawn windows                                                           #
# --------------------------------------------------------------------------- #
def _date(value) -> dt.date:
    return dt.date.fromisoformat(str(value)[:10])


@pytest.fixture(scope="module")
def his_windows() -> list:
    """Each of his drawn windows, read on its own last day: the bars, the reader's line, HIS two lines in the
    unit the reader measures a pair in (the range of its second anchor's day), and the reader's own read."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import frame as frame_module, line as line_module, lps
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    out = []
    for setup in load_corpus():
        raw = fixture_frame(frames, setup_key(setup), setup["ticker"])
        spans = [s for s in (setup.get("lps"), setup.get("lps2")) if s]
        for n, span in enumerate(spans):
            last = n == len(spans) - 1
            cut = raw.loc[:pd.Timestamp(span[1])]
            prepared = frame_module.prepare(cut)
            line = line_module.build(prepared)
            days = [d.date() for d in prepared.index]
            high = prepared["High"].to_numpy(dtype=float)
            low = prepared["Low"].to_numpy(dtype=float)
            ranges = prepared[frame_module.DAILY_RANGE].to_numpy(dtype=float)
            second = max(days.index(_date(setup["anchors"]["R"])), days.index(_date(setup["anchors"]["S"])))
            rails = setup["rails_drawn"]
            on_his_lines = lps.read(high, low, ranges, line.committed, R=float(rails["R"]), S=float(rails["S"]),
                                    box_unit=float(ranges[second]), born_bar=0)
            out.append({"key": setup_key(setup) + ("" if last else " (first)"), "setup": setup, "last": last,
                        "span": (_date(span[0]), _date(span[1])), "days": days, "high": high, "low": low,
                        "on_his_lines": on_his_lines, "raw": raw,
                        "read": two_eyes.read(setup["ticker"], cut)})
    assert len(out) == 43      # 40 drawings, three of them with two windows (ALB, PBT, SYRE)
    return out


#: The one drawn window whose last day does not recede: Fri 15/05/2026 made a higher high and a higher low than
#: Thu 14/05, so by his own MRK answer it crossed Thursday's high — the reader's pullback ends on Thursday.
_LAST_DAY_ADVANCES = ("YPF:2026-05-18",)


def test_on_his_last_receding_day_the_pullback_ends_that_day_at_his_trigger(his_windows):
    seen = []
    for row in his_windows:
        got, (_, his_end) = row["on_his_lines"], row["span"]
        if row["key"] in _LAST_DAY_ADVANCES:
            assert row["days"][got.end_bar] < his_end and got.crossed_bar == len(row["days"]) - 1, row["key"]
            seen.append(row["key"])
            continue
        assert row["days"][got.end_bar] == his_end and got.crossed_bar is None, row["key"]
        assert got.trigger == pytest.approx(float(row["high"][-1])), row["key"]
        if row["last"]:
            assert got.trigger == pytest.approx(float(row["setup"]["trigger_price"]), abs=0.005), row["key"]
    assert tuple(seen) == _LAST_DAY_ADVANCES


def test_none_of_his_windows_is_refused_by_any_of_his_four_sentences_on_his_own_lines(his_windows):
    refused = {row["key"]: row["on_his_lines"].refused for row in his_windows if row["on_his_lines"].refused}
    assert refused == {}


def test_the_window_opens_where_he_shades_it_on_most_of_his_windows(his_windows):
    """His shading starts on the top day (30 of 37 when he ruled it) or the day after ("Lets go with the day
    after"); the seven that differ carry a bounce day inside his drawing, which by his MRK answer is a buy. WAT,
    drawn by him on Thu 01/10/2026, is one more: he shades Fri 18/09 to Wed 23/09/2026, and Tue 22/09 made a higher
    high inside it."""
    his = [row for row in his_windows if row["key"] not in _LAST_DAY_ADVANCES]
    same = [row["key"] for row in his
            if row["span"][0] in (row["days"][row["on_his_lines"].top_bar], row["days"][row["on_his_lines"].start_bar])]
    other = sorted(set(row["key"] for row in his) - set(same))
    assert other == ["FOSL:2026-02-18", "MRK:2026-08-10", "MS:2026-06-04", "MSGS:2026-05-22", "ORMP:2026-04-13",
                     "SILC:2026-04-13", "WAT:2026-09-24"], other
    # JAZZ, the run he trimmed: six receding days, read on the last five bars, open where he opens it.
    jazz = next(row for row in his if row["key"] == "JAZZ:2026-02-24")
    assert jazz["days"][jazz["on_his_lines"].start_bar] == dt.date(2026, 2, 6) == jazz["span"][0]


def test_the_numbers_are_re_derived_from_his_marks_in_the_unit_the_reader_uses(his_windows):
    """Each number sits where his own windows put it, measured in the reader's LPS unit on his own lines. When he
    redraws, this is the test that says a number no longer covers his marks."""
    from engine_alpha.two_eyes import method_numbers as M

    got = [row["on_his_lines"] for row in his_windows if row["key"] not in _LAST_DAY_ADVANCES]
    over = {row["key"]: round(row["on_his_lines"].over_resistance, 2) for row in his_windows
            if row["key"] not in _LAST_DAY_ADVANCES and row["on_his_lines"].over_resistance > 0}
    # The ruling's six (Thu 10/09/2026): WTS 0.12, VLO 0.27, NGL 0.29, VIK 0.33, UNF 0.45, ST 1.30 — to the cent in
    # this unit. SILC's low sits on his resistance. MTLS joined them when he drew it (Sun 27/09/2026).
    assert over == {"MTLS:2026-09-04": 0.63, "NGL:2026-04-20": 0.29, "SILC:2026-04-13": 0.01, "ST:2026-04-17": 1.30,
                    "UNF:2026-07-10": 0.45, "VIK:2026-06-11": 0.33, "VLO:2026-07-08": 0.27, "WTS:2026-06-12": 0.12}
    assert max(over.values()) < M.LPS_CEILING_RANGES < max(over.values()) + 0.1
    # His deepest pullback, top to low (R8's research, Tue 08/09/2026: min 0.80, median 1.23, max 2.43).
    deepest = max(p.depth for p in got)
    assert deepest == pytest.approx(2.43, abs=0.005)
    assert deepest < M.LPS_DEPTH_MAX_RANGES < deepest + 0.1
    # Most of the move above the support area: his worst is JAZZ's poke.
    assert max(p.under_support for p in got) < 0.05 < M.LPS_UNDER_SUPPORT_SHARE
    # "2 - 5 bars": every window he drew, the top day and the receding days.
    drawn = [len([d for d in row["days"] if row["span"][0] <= d <= row["span"][1]]) for row in his_windows]
    assert (min(drawn), max(drawn)) == (2, M.LPS_MAX_BARS)
    assert max(p.end_bar - p.top_bar + 1 for p in got) <= M.LPS_MAX_BARS


#: Where the reader's OWN box refuses his window. On the box of tasks 10 and 11 sentence four refused three (MS,
#: ROIV, SILC: its resistance sat 1.4 to 3.3 ranges under his LPS). On the box of the rule he settled (Thu
#: 01/10/2026) none of his windows is refused.
_REFUSED_ON_THE_READERS_BOX = {}


def test_the_reader_fires_on_his_last_receding_day_at_his_trigger_on_its_own_box(his_windows):
    from engine_alpha.two_eyes import lps

    fired, silent = [], {}
    for row in his_windows:
        read = row["read"]
        assert read.failed is False, row["key"]
        if read.fired:
            assert read.state == lps.FIRED and read.lps.end_day == row["span"][1], row["key"]
            assert read.lps.trigger_price == pytest.approx(float(row["high"][-1])), row["key"]
            assert read.lps.start_day <= read.lps.end_day
            fired.append(row["key"])
        else:
            assert read.lps is None
            silent[row["key"]] = next(s.saying for s in read.trail if s.stage == "LPS")
    assert sorted(silent) == sorted(list(_REFUSED_ON_THE_READERS_BOX) + list(_LAST_DAY_ADVANCES))
    for key in _REFUSED_ON_THE_READERS_BOX:
        assert lps.OVER_RESISTANCE in silent[key], silent[key]
    assert len(fired) == 42       # of his 43 windows: all but YPF, whose last day advances


#: His buy days that made a lower low as well as crossing his trigger: the cross was his buy, and the pullback
#: goes on with that day's high as its trigger.
_BUY_DAY_RECEDES = ("DLX:2026-04-13", "MTLS:2026-09-04", "RGR:2026-03-19", "SKYT:2026-04-13", "UNF:2026-07-10",
                    "VIK:2026-06-11", "WAT:2026-09-24")


def test_on_his_buy_day_the_read_says_crossed_and_shows_no_fire(his_windows):
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import lps

    crossed, goes_on = [], []
    for row in his_windows:
        if not row["last"] or not row["read"].fired:
            continue
        buy = _date(row["setup"]["trigger"])
        read = two_eyes.read(row["setup"]["ticker"], row["raw"].loc[:pd.Timestamp(buy)])
        assert read.as_of == buy and read.failed is False, row["key"]
        said = next(s.saying for s in read.trail if s.stage == "LPS")
        assert f"{row['setup']['trigger_price']:.2f}" in said, f"{row['key']}: {said}"
        if row["key"] in _BUY_DAY_RECEDES:
            assert read.state == lps.FIRED and read.lps.end_day == buy and "buy" in said, f"{row['key']}: {said}"
            goes_on.append(row["key"])
            continue
        assert read.state == lps.CROSSED and read.fired is False and read.lps is None, f"{row['key']}: {read.state}"
        crossed.append(row["key"])
    assert tuple(goes_on) == _BUY_DAY_RECEDES and len(crossed) == 32


# --------------------------------------------------------------------------- #
# The junk he named                                                           #
# --------------------------------------------------------------------------- #
def _junk_days(key: str) -> list:
    from core.calibration.replay import fired_window_sessions
    from tools.regression import negative_corpus

    frames, _ = negative_corpus._load_fixture()
    raw = frames[key]
    sessions, _ = fired_window_sessions(raw, raw.index[-1], [])
    return [(ts.date(), raw.loc[:ts]) for ts in sessions]


def test_aef_the_pullback_he_refused_fires_on_no_day_and_each_refusal_names_his_sentence():
    """His AEF words (Mon 14/09/2026): "3 bars with huge increases in both spread and price changes meaning the
    pull back is increasing with sellers, not to mention you cut the move off and it's a part of a bigger swing
    downwards that reaches support". That pullback runs from Wed 03/06/2026; from its second day on it is refused,
    each day by his own sentence. On its FIRST day it is one receding day inside the reader's box (9.98 / 9.57,
    the rule he settled on Thu 01/10/2026), none of his sentences is true of it yet, and the read fires at 10.00;
    the next day falls and nothing crosses it. On the box of tasks 10 and 11 that day was refused by sentence
    four, and AEF fired on no day."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import lps

    said, fires = {}, []
    for day, cut in _junk_days("AEF"):
        read = two_eyes.read("AEF", cut)
        assert read.failed is False
        if read.fired:
            fires.append((day, read.lps.trigger_price))
        said[day] = next((s.saying for s in read.trail if s.stage == "LPS"), "")
    assert fires == [(dt.date(2026, 6, 3), pytest.approx(10.00))]
    assert "one receding day under the top of Tue 02/06/2026" in said[dt.date(2026, 6, 3)]
    assert lps.SELLERS_RISING in said[dt.date(2026, 6, 4)] and lps.SELLERS_RISING in said[dt.date(2026, 6, 5)]
    assert lps.SLICE in said[dt.date(2026, 6, 8)] and lps.SLICE in said[dt.date(2026, 6, 9)]
    assert all("no LPS" in words for day, words in said.items() if day > dt.date(2026, 6, 3))


@pytest.fixture(scope="module")
def junk_fire_days() -> dict:
    """Every junk chart read through the door on every day of its fired window: the days it fires."""
    from engine_alpha import reader
    from core.calibration.replay import fired_window_sessions, flag_capture
    from tools.regression import negative_corpus

    frames, meta = negative_corpus._load_fixture()
    out = {}
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        for case in meta["cases"]:
            key = case.get("key", case["ticker"])
            raw = frames[key]
            sessions, _ = fired_window_sessions(raw, raw.index[-1], [])
            out[key] = [ts.date() for ts in sessions
                        if isinstance(reader.evaluate_ticker(case["ticker"], raw.loc[:ts]), dict)]
    assert len(out) == 16
    return out


#: The junk charts none of his four sentences and nothing in the box's rules keeps silent today. His words on them
#: are about the box ("Extreme Width, Spread, Messy non tight structure"; on OHI "lps is fine though"), which his
#: method grades (task 14) and never gates.
_JUNK_THAT_FIRES = ("ABEV", "AEF", "BBVA", "BBVA@2026-06-05", "BMRN", "COLM", "DGII", "ENIC", "FLG", "FRPH", "KWR",
                    "OHI", "RLGT", "SPCB")


def test_the_junk_charts_that_fire_and_the_two_that_stay_silent(junk_fire_days):
    firing = sorted(key for key, days in junk_fire_days.items() if days)
    assert firing == sorted(_JUNK_THAT_FIRES)
    # DBD by his third sentence and the door, GOOD by the door. On the box of the rule he settled AEF fires on one
    # day (the test above); DBD, which fired before the rebuild, is silent. BBVA joined on Fri 02/10/2026: once a
    # dip that comes back gives a box its place back, its box is the one over the dip (23.74 / 22.89) and three
    # days of its window fire. He had set the junk charts aside the evening before ("idc about bodi, nor about
    # other junk charts lets focus on Working intended examples").
    assert sorted(set(junk_fire_days) - set(firing)) == ["DBD", "GOOD"]
    assert junk_fire_days["AEF"] == [dt.date(2026, 6, 3)]
    assert junk_fire_days["BBVA"] == [dt.date(2026, 6, 18), dt.date(2026, 6, 24), dt.date(2026, 6, 26)]


@pytest.mark.xfail(strict=True, reason=(
    "THE STOP RULE'S JUNK CLAUSE, not met at task 12a and not met on the rule of the pair he settled (Thu "
    "01/10/2026): today's engine fires on 8 of the 16 junk charts, the new reader on 14 (13 before a dip that "
    "comes back gave a box its place back, 12 before the rebuild). He set the junk charts aside on Thu 01/10/2026. "
    "The bar was fixed on Sun 20/09/2026 and is not moved here; his ruling at the core sitting, or the grade "
    "(task 14), owes it. The day this passes, this mark comes off deliberately."))
def test_no_more_junk_charts_fire_than_under_todays_engine(junk_fire_days):
    assert sum(1 for days in junk_fire_days.values() if days) <= 8


def test_on_the_junk_chart_spcb_a_pullback_refused_the_evening_it_ended_is_never_worded_crossed():
    """The blind check's night (Sun 27/09/2026). SPCB's pullback of Mon 27/11/2023 was refused that evening and
    the next as a slice of the fall from 12.60. On Wed 29/11/2023 the rally to 8.00 crossed its high and, the
    same day, turned the line at the low of Mon 20/11: judged again on that, the pullback was no slice and the
    read said "crossed", the word for a buy, of a pullback that had never been on the board."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import lps
    from tools.regression import negative_corpus

    frames, _ = negative_corpus._load_fixture()
    said = {}
    for night in ("2023-11-27", "2023-11-28", "2023-11-29"):
        read = two_eyes.read("SPCB", frames["SPCB"].loc[:pd.Timestamp(night)])
        said[night] = (read.state, next(s.saying for s in read.trail if s.stage == "LPS"))
    assert [state for state, _ in said.values()] == [lps.LINES_NO_LPS] * 3, said
    assert all(lps.SLICE in words and "Mon 27/11/2023" in words for _, words in said.values()), said


def test_the_day_a_box_is_born_the_pullback_that_ended_before_it_is_not_its_lps():
    """ALB on Tue 13/01/2026: the box became a box that day, and the last receding days ended on Thu 08/01."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import lps

    setup, raw = _his("ALB:2026-04-13")
    read = two_eyes.read("ALB", raw.loc[:pd.Timestamp("2026-01-13")])
    said = next(s.saying for s in read.trail if s.stage == "LPS")
    # No LPS; and since build task 12b the state word reads the open right edge: that day's bar sits wholly
    # over the new box's resistance area (tests/engine/test_two_eyes_story.py pins the word and the count).
    assert read.parent is not None and read.state == "beyond R, undetermined" and read.lps is None
    assert "from Wed 07/01/2026 to Thu 08/01/2026" in said
    assert "before the box became a box on Tue 13/01/2026" in said


def test_bmrn_is_read_on_the_final_shallow_declining_days():
    from engine_alpha import two_eyes

    day, cut = _junk_days("BMRN")[0]
    assert day == dt.date(2026, 6, 18)
    read = two_eyes.read("BMRN", cut)
    assert read.fired and (read.lps.start_day, read.lps.end_day) == (dt.date(2026, 6, 16), dt.date(2026, 6, 18)), \
        "his blue part: Tue 16/06 to Thu 18/06/2026"
    assert read.lps.trigger_price == pytest.approx(55.62)


# --------------------------------------------------------------------------- #
# The door and the row                                                        #
# --------------------------------------------------------------------------- #
def _his(key: str):
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    setup = next(s for s in load_corpus() if setup_key(s) == key)
    return setup, fixture_frame(frames, key, setup["ticker"])


def test_a_fire_crosses_the_door_as_a_whole_row_with_the_box_the_lps_and_the_trigger():
    from engine_alpha import reader, two_eyes_adapter
    from core.calibration.replay import flag_capture

    setup, raw = _his("SYRE:2026-02-19")
    watch, stamp = {}, {}
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        row = reader.evaluate_ticker("SYRE", raw.loc[:pd.Timestamp("2026-02-17")], watch=watch, stamp=stamp)
    assert stamp == {"reader": reader.READER_NEW}
    assert isinstance(row, dict) and not [k for k in two_eyes_adapter.REQUIRED_KEYS if k not in row]
    assert (round(row["_R"], 2), round(row["_S"], 2)) == (35.31, 32.26)
    assert row["_trigger_price"] == pytest.approx(37.22) and row["_lps_zone_end_date"] == "2026-02-17"
    assert row["_two_eyes_lps_read_against"] == "parent"
    assert watch["state"] == "fired" and watch["read"].fired


#: His last receding days the universe door refuses, with the leg that refuses each: the door is his ("The 50-day
#: filter stays", "The 200-day filter stays"), and it refuses the same four days to today's engine.
_THE_DOOR_REFUSES = {"JAZZ:2026-02-24": "sma50", "MDT:2026-07-24": "sma200", "NGL:2026-01-20": "sma50",
                     "SKYT:2026-04-13": "sma50"}


def test_through_the_door_the_reader_fires_on_his_day_at_his_trigger_or_is_named(his_windows):
    """The yardstick's headline for the new reader, pinned chart by chart: every one of his drawings either fires on his
    last receding day at his trigger, or is named here with the reason it does not."""
    from engine_alpha import reader
    from core.calibration.replay import flag_capture

    fired, not_scanned, silent = [], {}, []
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        for row in his_windows:
            if not row["last"]:
                continue
            watch = {}
            cut = row["raw"].loc[:pd.Timestamp(row["span"][1])]
            result = reader.evaluate_ticker(row["setup"]["ticker"], cut, watch=watch)
            if watch["state"] == "not scanned":
                assert result is None
                not_scanned[row["key"]] = watch["why"]
            elif isinstance(result, dict):
                assert result["_lps_zone_end_date"] == row["span"][1].isoformat(), row["key"]
                assert result["_trigger_price"] == pytest.approx(float(row["setup"]["trigger_price"]), abs=0.005)
                fired.append(row["key"])
            else:
                assert result is None
                silent.append(row["key"])
    assert not_scanned == _THE_DOOR_REFUSES
    assert sorted(silent) == sorted(list(_REFUSED_ON_THE_READERS_BOX) + list(_LAST_DAY_ADVANCES))
    assert len(fired) == 35 and len(fired) + len(silent) + len(not_scanned) == 40


def test_the_universe_door_stands_before_the_read_and_a_refused_chart_is_not_scanned():
    from engine_alpha import reader, two_eyes
    from core.calibration.replay import flag_capture

    setup, raw = _his("JAZZ:2026-02-24")
    cut = raw.loc[:pd.Timestamp("2026-02-11")]
    assert two_eyes.read("JAZZ", cut).fired, "the read itself fires: the door is what refuses the day"
    watch = {}
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        assert reader.evaluate_ticker("JAZZ", cut, watch=watch) is None
    assert watch["state"] == "not scanned" and watch["why"] == "sma50"
    # The entry that raises refuses the same way: not scanned is an answer, never a crash.
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        assert reader.run_eval_chain("JAZZ", cut) is None
