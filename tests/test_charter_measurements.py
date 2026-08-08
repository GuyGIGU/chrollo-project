"""Hand-computed batteries for the wave-1 charter measurements (build task 7).

These archived RAW columns have NO downstream consumer until the operator's
A/B — these batteries are the only correctness check they get, so every
expected value below is computed BY HAND on purpose-built synthetic series
(Beck P1: never pasted from the implementation's own output). Boundary
variants are the point: the ABSENT rules are the measurement's contract.

Task 8's bounded box-walk battery joins this file.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.structure.market_structure import classify_window_descent
from engine_alpha.structure.metrics import (
    measure_lps_contraction,
    measure_story_richness,
)


def _tests(*ranges):
    return [{"window_range_pct_box": r} for r in ranges]


# ── lps_shrink_frac — the successive-test shrink read ────────────────────────

def test_shrink_frac_full_when_every_test_tightens():
    # 3 tests, 2 steps, both non-rising -> 2/2 = 1.0 (hand).
    out = measure_lps_contraction(_tests(0.5, 0.4, 0.3), None, None, 1.0)
    assert out["lps_shrink_frac"] == pytest.approx(1.0)


def test_shrink_frac_zero_when_every_test_widens():
    # 0.3 -> 0.4 (> 0.3*1.05) and 0.4 -> 0.5 (> 0.42): both RISE -> 0/2 = 0.0.
    # An honest zero — evidence, not absence (the staircase widened).
    out = measure_lps_contraction(_tests(0.3, 0.4, 0.5), None, None, 1.0)
    assert out["lps_shrink_frac"] == pytest.approx(0.0)


def test_shrink_frac_half_on_a_mixed_staircase():
    # 0.5 -> 0.3 (non-rising) then 0.3 -> 0.5 (rising) -> 1/2 = 0.5 (hand).
    out = measure_lps_contraction(_tests(0.5, 0.3, 0.5), None, None, 1.0)
    assert out["lps_shrink_frac"] == pytest.approx(0.5)


def test_shrink_frac_tolerates_a_tiny_uptick():
    # 0.50 -> 0.51 (<= 0.525 = 0.50*1.05) and 0.51 -> 0.52 (<= 0.5355):
    # both inside the 5% tolerance -> non-rising -> 1.0 (hand).
    out = measure_lps_contraction(_tests(0.50, 0.51, 0.52), None, None, 1.0)
    assert out["lps_shrink_frac"] == pytest.approx(1.0)


def test_shrink_frac_absent_below_the_minimum_step_floor():
    # Two tests = ONE step: quantizes to 0-or-1 -> ABSENT, never a value.
    assert measure_lps_contraction(
        _tests(0.5, 0.3), None, None, 1.0)["lps_shrink_frac"] is None
    # Empty and missing staircases are absent, never zero and never one.
    assert measure_lps_contraction(
        _tests(), None, None, 1.0)["lps_shrink_frac"] is None
    assert measure_lps_contraction(
        None, None, None, 1.0)["lps_shrink_frac"] is None


def test_shrink_frac_filters_unusable_tests_before_the_floor():
    # A NaN range drops that test: 3 listed but only 2 usable -> ABSENT.
    out = measure_lps_contraction(
        _tests(0.5, float("nan"), 0.4), None, None, 1.0)
    assert out["lps_shrink_frac"] is None


# ── lps_window_classification — the elected window's descent read ────────────

def test_window_classification_absent_on_an_insufficient_window():
    out = measure_lps_contraction(_tests(0.5, 0.4, 0.3), [10.0], [9.0], 1.0)
    assert out["lps_window_classification"] is None
    out = measure_lps_contraction(_tests(0.5, 0.4, 0.3), None, None, 1.0)
    assert out["lps_window_classification"] is None


def test_window_classification_delegates_to_the_one_dark_reader():
    # A clearly descending 5-bar test window. The fold DELEGATES to
    # classify_window_descent (EC-18: one implementation of the judgment) —
    # assert equality with the reader's own output and closed-set membership,
    # never a re-specified twin of its rules.
    highs = [11.0, 10.8, 10.6, 10.4, 10.2]
    lows = [10.4, 10.2, 10.0, 9.8, 9.6]
    out = measure_lps_contraction(_tests(0.5, 0.4, 0.3), highs, lows, 0.5)
    direct = classify_window_descent(highs, lows, atr=0.5)
    assert out["lps_window_classification"] == direct["classification"]
    assert out["lps_window_classification"] in {
        "rising_march", "turned", "clean_dip", "mixed"}


# ── story_richness_rate — richness vs youth, bounded ─────────────────────────

def test_richness_saturates_at_the_full_anchor():
    # events = 4+3+2+2 = 11 over max(60, 20) bars = 0.1833/bar; /0.15 = 1.22
    # -> saturates to 1.0 (hand).
    assert measure_story_richness(4, 3, 2, 2, 60) == pytest.approx(1.0)


def test_richness_partial_value_hand_computed():
    # events = 1 over max(100, 20) = 0.01/bar; /0.15 = 0.0667 (hand).
    assert measure_story_richness(1, 0, 0, 0, 100) == pytest.approx(1.0 / 15.0)


def test_richness_denominator_floor_stops_short_base_luck():
    # events = 1, base_len 5: FLOORED den = 20 -> 0.05/0.15 = 1/3 (hand).
    # Without the floor it would read 0.2/0.15 -> saturated 1.0.
    assert measure_story_richness(1, 0, 0, 0, 5) == pytest.approx(1.0 / 3.0)


def test_richness_absent_only_when_every_ingredient_is_absent():
    assert measure_story_richness(None, None, None, None, 60) is None
    # One present ingredient makes it measured — zeros are evidence.
    assert measure_story_richness(0, None, None, None, 60) == 0.0
    # Non-finite ingredients are absent among present ones.
    assert measure_story_richness(
        float("nan"), 3, None, None, 60) == pytest.approx(
        (3 / 60.0) / settings.STORY_RICHNESS_FULL)


def test_richness_is_always_bounded():
    # A pathologically dense tape cannot blow past 1.0 (McKinney: unbounded
    # rate measures archive outliers that dominate any later calibration).
    assert measure_story_richness(4, 99, 99, 99, 21) == 1.0
