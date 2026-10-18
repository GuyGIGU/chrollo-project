"""The volume facts of tools/research/lps_volume_new_reader.py.

Each fact is pinned on a hand-built volume series whose answer is worked out in the
comment, so a changed definition shows up as a changed number.
"""
import numpy as np

from tools.research.lps_volume_new_reader import _vs_average, quietest_stretch


def test_a_stretch_is_read_against_the_50_day_average_ending_on_its_last_day():
    volume = np.array([100.0] * 58 + [50.0, 50.0])
    # days 58..59 average 50; the 50 days ending on day 59: 48 x 100 + 2 x 50 = 4,900 -> 98
    assert abs(_vs_average(volume, 58, 59) - 50 / 98) < 1e-12
    # a 50-day average of nothing is no ratio
    assert _vs_average(np.zeros(60), 58, 59) is None


def test_the_quietest_stretch_of_2_to_5_days_in_the_last_week():
    volume = np.array([100.0] * 53 + [20.0, 20.0] + [100.0] * 5)
    # the fire day is 59; stretches end on days 53..59. The quietest is days 53..54 at 20,
    # against the 50 days ending on day 54: 48 x 100 + 2 x 20 = 4,840 -> 96.8
    assert abs(quietest_stretch(volume, 59) - 20 / 96.8) < 1e-12


def test_a_quiet_stretch_older_than_the_last_week_is_not_counted():
    volume = np.array([100.0] * 45 + [20.0, 20.0] + [100.0] * 13)
    # days 45..46 are quiet, but a stretch ending on day 53 or later starts on day 49 at
    # the earliest: every stretch reads 100 against a 50-day average of 96.8
    assert abs(quietest_stretch(volume, 59) - 100 / 96.8) < 1e-12
