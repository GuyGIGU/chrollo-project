"""Build step 7 of the final method (docs/final_method_2026-09.md points 7, 8 and 6): box gates to grades.

One default-off switch per point, each flag-off byte-identical (the fleet, junk, marks and reader-pin guards
prove that at scale); these tests prove each switch's mechanics on synthetic frames and spies.

Point 7, his Q7: "a box is a box because of its consolidating Zig zag behavior not it's height". The three
percent-of-price width caps (MAX_BOX_WIDTH 18 percent, BAND_MAX_BOX_WIDTH 23 percent, S_MAX_BOX_WIDTH 15
percent) stop refusing a box and stop demoting a tier under BOX_WIDTH_CAPS_GRADED_ENABLED.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.scoring.scoring import calculate_structure_tier
from engine_alpha.structure import box_gates, box_primitives

WIDTH = "BOX_WIDTH_CAPS_GRADED_ENABLED"
LO, HI = 100.0, 125.0          # a clean zigzag 26 percent of price wide, wick to wick


def _zigzag_frame(n=80, half=8):
    """A triangle wave between LO and HI: valleys every 2*half days from day 0, peaks between them."""
    t = np.arange(n)
    phase = (t % (2 * half)) / half
    mid = np.where(phase <= 1, LO + (HI - LO) * phase, HI - (HI - LO) * (phase - 1))
    idx = pd.bdate_range("2025-06-02", periods=n)
    return pd.DataFrame({"Open": mid, "High": mid + 0.5, "Low": mid - 0.5, "Close": mid,
                         "Volume": 1e6}, index=idx)


# One oriented pair on that frame: R = the day-8 peak's high, S = the day-0 valley's low.
PAIR = [(0, "valley", LO - 0.5), (8, "peak", HI + 0.5)]
R_WIDE, S_WIDE = HI + 0.5, LO - 0.5


@pytest.fixture
def width_on(monkeypatch):
    monkeypatch.setattr(settings, WIDTH, True)


def test_the_width_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, WIDTH) is False
    assert WIDTH in ENGINE_SETTINGS_KEYS


def test_the_pair_is_wider_than_every_percent_cap():
    width = (R_WIDE - S_WIDE) / S_WIDE
    assert width > max(settings.MAX_BOX_WIDTH, settings.BAND_MAX_BOX_WIDTH, settings.S_MAX_BOX_WIDTH)


def test_the_one_width_judgment_refuses_only_with_the_switch_off(monkeypatch):
    assert box_gates._width_refuses(0.19, 0.18) is True
    assert box_gates._width_refuses(0.18, 0.18) is False, "at the cap is inside it"
    monkeypatch.setattr(settings, WIDTH, True)
    assert box_gates._width_refuses(0.19, 0.18) is False


def test_the_occupancy_judge_measures_a_wide_box_under_the_switch(monkeypatch):
    df = _zigzag_frame()
    for cap in (None, settings.BAND_MAX_BOX_WIDTH):
        assert box_gates._validate_base_quality(df, R_WIDE, S_WIDE, 2.0, max_width=cap)[2] is None, \
            "flag-off the width refuses before anything is measured"
    monkeypatch.setattr(settings, WIDTH, True)
    for cap in (None, settings.BAND_MAX_BOX_WIDTH):
        r_t, s_t, eq, _ = box_gates._validate_base_quality(df, R_WIDE, S_WIDE, 2.0, max_width=cap)
        assert eq is not None and r_t >= 3 and s_t >= 3, "the box is judged on its zigzag, not its height"


def test_the_strict_pool_no_longer_refuses_a_pair_on_width(monkeypatch):
    df = _zigzag_frame()
    trace = []
    box_primitives.collect_zigzag_candidates(df, 2.0, trace=trace)
    assert any(rec["stage"] == "width" for rec in trace), "flag-off the strict pool refuses on width"
    monkeypatch.setattr(settings, WIDTH, True)
    trace = []
    got = box_primitives.collect_zigzag_candidates(df, 2.0, trace=trace)
    assert trace and not any(rec["stage"] == "width" for rec in trace)
    assert any(c.box_width > settings.MAX_BOX_WIDTH for c in got), "the wide pair is a candidate"


def test_the_band_pool_reaches_its_event_read_on_a_wide_pair(monkeypatch):
    from engine_alpha.structure import rail_qualification

    seen = []
    monkeypatch.setattr(rail_qualification, "qualify_pair_events", lambda *a, **k: seen.append(a) or None)
    df = _zigzag_frame()
    box_primitives._band_rail_candidates(df, df["High"].values, df["Low"].values, PAIR, 2.0)
    assert seen == [], "flag-off the 23 percent band cap skips the pair"
    monkeypatch.setattr(settings, WIDTH, True)
    box_primitives._band_rail_candidates(df, df["High"].values, df["Low"].values, PAIR, 2.0)
    assert len(seen) == 1


def test_the_story_pool_reaches_its_posture_read_on_a_wide_pair(monkeypatch):
    from engine_alpha.structure import event_map

    seen = []
    monkeypatch.setattr(event_map, "frame_terminal_posture", lambda *a, **k: seen.append(a) or False)
    monkeypatch.setattr(event_map, "frame_r_engaged", lambda *a, **k: False)
    df = _zigzag_frame()
    box_primitives._story_pool_candidates(df, df["High"].values, df["Low"].values, PAIR, 2.0, 0)
    assert seen == [], "flag-off the 18 percent cap skips the pair"
    monkeypatch.setattr(settings, WIDTH, True)
    box_primitives._story_pool_candidates(df, df["High"].values, df["Low"].values, PAIR, 2.0, 0)
    assert len(seen) == 1


def test_a_wide_box_keeps_tier_s_under_the_switch(monkeypatch):
    top = settings.TIER_S_STRUCT
    assert calculate_structure_tier(top, box_width=settings.S_MAX_BOX_WIDTH) == "S"
    assert calculate_structure_tier(top, box_width=settings.S_MAX_BOX_WIDTH + 0.01) == "A", "flag-off: demoted"
    monkeypatch.setattr(settings, WIDTH, True)
    assert calculate_structure_tier(top, box_width=settings.S_MAX_BOX_WIDTH + 0.01) == "S"
    assert calculate_structure_tier(top - 1, box_width=0.30) == "A", "the grade still decides the letter"
