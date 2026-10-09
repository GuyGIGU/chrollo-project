"""The Momentum Masters volume facts of tools/research/volume_key_points_census.py.

Each fact is pinned on a hand-built base whose answer is worked out in the
comment, so a changed definition shows up as a changed number.
"""
import numpy as np
import pandas as pd

from tools.research.volume_key_points_census import base_volume_read, lps_window, receding_days


def _frame(rows):
    """rows: (high, low, close, volume) per day."""
    return pd.DataFrame(rows, columns=["High", "Low", "Close", "Volume"],
                        index=pd.bdate_range("2026-01-05", periods=len(rows)))


def test_a_receding_day_makes_a_lower_high_or_a_lower_low():
    high = np.array([10, 11, 10.5, 10.6, 10.6])
    low = np.array([9, 9.5, 9.6, 9.4, 9.4])
    # day 1 higher high + higher low: not receding; day 2 lower high; day 3 lower low;
    # day 4 equal high and equal low: not receding
    assert receding_days(high, low).tolist() == [False, False, True, True, False]


def test_the_lps_window_is_the_last_run_of_receding_days():
    high = np.array([10, 11, 10.8, 10.6, 11.2, 11.0, 10.9, 11.5])
    low = np.array([9, 10, 9.8, 9.6, 10.2, 10.0, 9.9, 10.6])
    # receding: 2, 3, 5, 6; day 7 is an up day, so the last receding day is 6 and
    # its run starts at 5 (day 4 made a higher high and a higher low)
    assert lps_window(high, low, start=1, anchor=7) == (5, 6)
    # read on day 3, the run is 2..3
    assert lps_window(high, low, start=1, anchor=3) == (2, 3)
    # clipped to the base
    assert lps_window(high, low, start=6, anchor=7) == (6, 6)
    # no receding day inside the base
    assert lps_window(high, low, start=7, anchor=7) is None


def _base():
    # 50 quiet days at volume 100 (close 10, range 2%), then a 6-day base:
    #   d50 +5% on 300, d51 -0.2% on 200 (heavy volume, but a small decline),
    #   d52 +2% on 300, d53 -3% on 200, d54 -1% on 50, d55 -2.5% on 50 (a full
    #   day's range, but on light volume)
    rows = [(10.1, 9.9, 10.0, 100.0)] * 50
    close = 10.0
    for change, vol in [(0.05, 300), (-0.002, 200), (0.02, 300), (-0.03, 200), (-0.01, 50), (-0.025, 50)]:
        prev, close = close, close * (1 + change)
        rows.append((max(prev, close) * 1.001, min(prev, close) * 0.999, close, float(vol)))
    return _frame(rows)


def test_the_base_facts_on_a_worked_example():
    frame = _base()
    read = base_volume_read(frame, start=50, anchor=55)
    # up days 300, 300 -> 300; down days 200, 200, 50, 50 -> 125
    assert abs(read["up_down_volume"] - 2.4) < 1e-9
    # mean up 3.5% vs mean down (0.2 + 3 + 1 + 2.5) / 4 = 1.675%
    assert abs(read["up_down_size"] - 3.5 / 1.675) < 1e-9
    # vol50 over days 6..55 = (44 x 100 + 300 + 200 + 300 + 200 + 50 + 50) / 50 = 110,
    # heavy = 165. The 20-day ADR is ~2.2%: d53 falls 3% on 200 (heavy); d51 is on
    # 200 but falls only 0.2%, and d55 falls 2.5% but on 50, so neither counts
    assert read["heavy_declines"] == 1
    # the LPS window: d53, d54, d55 recede (d52 was an up day with a higher high)
    assert read["lps_days"] == 3
    assert abs(read["lps_volume"] - (200 + 50 + 50) / 3 / 110) < 1e-9
    assert read["base_days"] == 6


def test_no_day_after_the_read_day_is_used():
    frame = _base()
    later = pd.concat([frame, _frame([(30.0, 5.0, 20.0, 1e9)] * 5)])
    later.index = pd.bdate_range("2026-01-05", periods=len(later))
    assert base_volume_read(later, start=50, anchor=55) == base_volume_read(frame, start=50, anchor=55)


def test_a_base_too_short_to_read_is_none():
    frame = _base()
    assert base_volume_read(frame, start=52, anchor=55) is None   # 4 days
    assert base_volume_read(frame, start=0, anchor=5) is None     # no day before the base
