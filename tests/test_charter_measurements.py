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
from engine_alpha.structure.events.market_structure import classify_window_descent
from engine_alpha.structure.metrics.base import (
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


# ── measure_trend_bases — the ONE bounded box-walk (task 8) ──────────────────
# The walk's CONTRACT (ordering, dedup, cap, ratio units, absence rules) is
# pinned with scripted brick sequences — the detector geometry is the
# injected expensive component here (its own correctness lives in the bricks
# suites), so every expectation below stays hand-computable. The absence
# cases run the REAL labelling on pure synthetics; the EC-17 cascade runs
# the REAL walk end-to-end on the shadow fixture.

import pandas as pd

from engine_alpha.structure.events import market_structure as ms_mod


def _frame(closes):
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1000.0] * len(closes),
    })


class _FakeRoot:
    def __init__(self, climax_bar):
        self.climax_bar = climax_bar


class _FakeBox:
    def __init__(self, R, S, start_bar):
        self.R, self.S, self.start_bar = R, S, start_bar


def _scripted_bricks(monkeypatch, roots, boxes_by_climax):
    """Script the walk's brick calls: find_root_swing pops chronological
    roots >= search_from; validate_equilibrium returns the box scripted for
    that climax (or None)."""
    import engine_alpha.structure.narrative.bricks as bricks_mod

    def fake_find_root(sub, search_from, atr):
        for r in roots:
            if r >= search_from:
                return _FakeRoot(r)
        return None

    def fake_validate(sub, root, atr):
        return boxes_by_climax.get(root.climax_bar)

    monkeypatch.setattr(bricks_mod, "find_root_swing", fake_find_root)
    monkeypatch.setattr(bricks_mod, "validate_equilibrium", fake_validate)


def _covering_up_segment(monkeypatch, seg_start=0, seg_end=None):
    monkeypatch.setattr(ms_mod, "read_market_structure",
                        lambda df, **kw: {"points": [{"stub": 1}]})
    monkeypatch.setattr(ms_mod, "segment_trends", lambda pts: [{
        "direction": 1, "start_bar": seg_start, "end_bar": seg_end,
        "terminal_bar": 999, "terminal_price": 0.0}])


def test_trend_bases_counts_and_ratio_hand_computed(monkeypatch):
    # Two predecessors: widths (11-10)/10 = 0.10 then (10.5-10)/10 = 0.05.
    # Elected width 0.03 -> count = 3, ratio = 0.03/0.05 = 0.6 (hand).
    _covering_up_segment(monkeypatch)
    _scripted_bricks(monkeypatch, roots=[5, 25],
                     boxes_by_climax={5: _FakeBox(11.0, 10.0, 8),
                                      25: _FakeBox(10.5, 10.0, 30)})
    out = ms_mod.measure_trend_bases(_frame([10.0] * 120), 1.0,
                                     elected_start_bar=100,
                                     elected_width=0.03)
    assert out["trend_base_count"] == 3
    assert out["inter_base_width_ratio"] == pytest.approx(0.6)


def test_trend_bases_dedup_rule_skips_non_chronological_starts(monkeypatch):
    # The second box starts AT/BEFORE the first admitted start -> skipped by
    # the stated dedup rule; count = 2, ratio vs the ONE admitted width.
    _covering_up_segment(monkeypatch)
    _scripted_bricks(monkeypatch, roots=[5, 25],
                     boxes_by_climax={5: _FakeBox(11.0, 10.0, 8),
                                      25: _FakeBox(10.4, 10.0, 8)})
    out = ms_mod.measure_trend_bases(_frame([10.0] * 120), 1.0,
                                     elected_start_bar=100,
                                     elected_width=0.05)
    assert out["trend_base_count"] == 2
    assert out["inter_base_width_ratio"] == pytest.approx(0.05 / 0.10)


def test_trend_bases_count_saturates_but_the_ratio_stays_honest(monkeypatch):
    # Five walkable predecessors (widths (i+1)*0.01), cap 4: the COUNT
    # saturates at the cap, but the walk keeps paying to the segment's right
    # edge so the ratio compares against the TRUE most recent predecessor
    # (width 0.05) — the old cap break truncated the enumeration exactly
    # where the most recent predecessor lives, so saturated rows (the
    # strongest names) archived a ratio against the wrong base (2026-08-08
    # review, finding 8; the old pinned expectation was 0.01/0.03 — the
    # third-oldest base, not the most recent).
    _covering_up_segment(monkeypatch)
    roots = [5, 15, 25, 35, 45]
    boxes = {r: _FakeBox(10.0 + (i + 1) * 0.1, 10.0, r + 2)
             for i, r in enumerate(roots)}
    _scripted_bricks(monkeypatch, roots, boxes)
    out = ms_mod.measure_trend_bases(_frame([10.0] * 120), 1.0,
                                     elected_start_bar=100,
                                     elected_width=0.01)
    assert out["trend_base_count"] == settings.TREND_BASE_COUNT_CAP
    assert out["inter_base_width_ratio"] == pytest.approx(0.01 / 0.05)


def test_trend_bases_budget_truncated_walk_emits_no_ratio(monkeypatch):
    # More walkable roots than TREND_BASE_WALK_MAX_ROOTS: the enumeration
    # never reaches the segment's right edge, so the most recent predecessor
    # is UNKNOWN — the count still saturates, the ratio is ABSENT, never a
    # value measured against whatever base the truncation happened to stop at.
    _covering_up_segment(monkeypatch)
    budget = int(settings.TREND_BASE_WALK_MAX_ROOTS)
    roots = [5 + 3 * i for i in range(budget + 3)]
    boxes = {r: _FakeBox(11.0, 10.0, r + 1) for r in roots}
    _scripted_bricks(monkeypatch, roots, boxes)
    out = ms_mod.measure_trend_bases(_frame([10.0] * 300), 1.0,
                                     elected_start_bar=250,
                                     elected_width=0.05)
    assert out["trend_base_count"] == settings.TREND_BASE_COUNT_CAP
    assert out["inter_base_width_ratio"] is None


def test_trend_bases_no_predecessor_ratio_is_null_never_one(monkeypatch):
    _covering_up_segment(monkeypatch)
    _scripted_bricks(monkeypatch, roots=[], boxes_by_climax={})
    out = ms_mod.measure_trend_bases(_frame([10.0] * 120), 1.0,
                                     elected_start_bar=100,
                                     elected_width=0.05)
    assert out["trend_base_count"] == 1        # the elected base, never zero
    assert out["inter_base_width_ratio"] is None


def test_trend_bases_no_covering_up_segment_counts_one_measured(monkeypatch):
    # Only a DOWN segment covers the elected start (anchor polarity): no walk
    # runs, the count is the elected base alone — measured 1, never absent,
    # never a root sought inside the opposite-direction trend.
    monkeypatch.setattr(ms_mod, "read_market_structure",
                        lambda df, **kw: {"points": [{"stub": 1}]})
    monkeypatch.setattr(ms_mod, "segment_trends", lambda pts: [{
        "direction": -1, "start_bar": 0, "end_bar": None,
        "terminal_bar": 10, "terminal_price": 0.0}])
    out = ms_mod.measure_trend_bases(_frame([10.0] * 120), 1.0,
                                     elected_start_bar=100,
                                     elected_width=0.05)
    assert out["trend_base_count"] == 1
    assert out["inter_base_width_ratio"] is None


def test_trend_bases_absent_when_the_labelling_refuses():
    # A 2-bar frame yields no swing points: the WHOLE measurement is absent
    # (a fabricated count never archives). Same for a missing frame.
    out = ms_mod.measure_trend_bases(_frame([10.0, 10.1]), 1.0,
                                     elected_start_bar=1, elected_width=0.05)
    assert out["trend_base_count"] is None
    assert out["inter_base_width_ratio"] is None
    empty = ms_mod.measure_trend_bases(None, 1.0, 5, 0.05)
    assert empty["trend_base_count"] is None
