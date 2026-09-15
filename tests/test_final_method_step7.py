"""Build step 7 of the final method (docs/final_method_2026-09.md points 7, 8 and 6): box gates to grades.

One default-off switch per point, each flag-off byte-identical (the fleet, junk, marks and reader-pin guards
prove that at scale); these tests prove each switch's mechanics on synthetic frames and spies.

Point 7, his Q7: "a box is a box because of its consolidating Zig zag behavior not it's height". The three
percent-of-price width caps (MAX_BOX_WIDTH 18 percent, BAND_MAX_BOX_WIDTH 23 percent, S_MAX_BOX_WIDTH 15
percent) stop refusing a box and stop demoting a tier under BOX_WIDTH_CAPS_GRADED_ENABLED.

Point 8, his Q8: "It's hard to gate using a raw number". The crash floors (the box's lowest low, the read day's
close), the spring's 3.0-range depth cap and the band pool's depth and length caps stop refusing under
DEPTH_CAPS_GRADED_ENABLED.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.scoring.scoring import calculate_structure_tier
from engine_alpha.structure import box_gates, box_primitives

WIDTH = "BOX_WIDTH_CAPS_GRADED_ENABLED"
LO, HI = 100.0, 125.0          # a clean zigzag 26 percent of price wide, wick to wick


def _zigzag_frame(n=80, half=8, lo=LO, hi=HI):
    """A triangle wave between lo and hi: valleys every 2*half days from day 0, peaks between them."""
    t = np.arange(n)
    phase = (t % (2 * half)) / half
    mid = np.where(phase <= 1, lo + (hi - lo) * phase, hi - (hi - lo) * (phase - 1))
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


# ── point 8: no depth number (DEPTH_CAPS_GRADED_ENABLED) ─────────────────────
# His Q8, asked on BODI's drawn Phase C against the 3-range cap: "It's hard to gate using a raw number in case we
# reject a valid setups because of a small neumeric gap".
DEPTH = "DEPTH_CAPS_GRADED_ENABLED"


def test_the_depth_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, DEPTH) is False
    assert DEPTH in ENGINE_SETTINGS_KEYS


def test_the_box_crash_floor_stops_refusing(monkeypatch):
    df = _zigzag_frame(lo=100.0, hi=110.0)
    df.iloc[50, df.columns.get_loc("Low")] = 60.0          # one low 40 percent under S
    R, S = 110.5, 99.5
    assert box_gates._validate_base_quality(df, R, S, 2.0)[2] is None, "flag-off the crash floor refuses"
    monkeypatch.setattr(settings, DEPTH, True)
    assert box_gates._validate_base_quality(df, R, S, 2.0)[2] is not None, "the deepest low is a fact"


def test_the_read_day_crash_floor_stops_dropping_the_chart(monkeypatch):
    from engine_alpha import evaluation

    n = 40
    df = pd.DataFrame({"High": 106.0, "Low": 104.0, "Close": 105.0, "ATR_10": 2.0, "ATR_50": 2.0},
                      index=pd.bdate_range("2026-01-05", periods=n))
    monkeypatch.setattr(evaluation, "read_structure", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(evaluation, "_structure_to_boxes", lambda s, n: {
        "parent": (20, 110.0, 100.0, 0.10, 3, 3, 0, 1, 2, 0, n - 20, False), "inner": None})
    latest = pd.Series({"Close": 60.0})                    # a close 40 percent under S
    assert evaluation._resolve_structure_context(df, latest) is None, "flag-off the chart is dropped"
    monkeypatch.setattr(settings, DEPTH, True)
    ctx = evaluation._resolve_structure_context(df, latest)
    assert ctx is not None and ctx["sup_avg"] == 100.0


def _spring_frame(depth):
    """A 60-day box (S 100, R 110, a daily range of 1.0) with one dip ``depth`` ranges under S on day 40 that
    closes back above S the next day and holds three days."""
    n = 60
    close, low, high = np.full(n, 105.0), np.full(n, 104.0), np.full(n, 106.0)
    low[40], close[40] = 100.0 - depth, 99.0
    low[41], close[41] = 100.5, 101.0
    close[42:45] = 103.0
    return pd.DataFrame({"Open": close, "High": high, "Low": low, "Close": close, "Volume": 1e6},
                        index=pd.bdate_range("2026-01-05", periods=n))


def test_a_spring_deeper_than_three_ranges_is_read_under_the_switch(monkeypatch):
    from engine_alpha.structure.phase_features import _phase_c_candidate

    kw = dict(box_start=0, base_len=60, R=110.0, S=100.0, atr_val=1.0)
    deep, shallow = _spring_frame(4.0), _spring_frame(2.5)
    assert _phase_c_candidate(shallow, shallow, **kw)["bin_c_type"] == "SPRING", "inside the 3-range cap"
    assert _phase_c_candidate(deep, deep, **kw)["bin_c_present"] is False, "flag-off 4 ranges is past the cap"
    monkeypatch.setattr(settings, DEPTH, True)
    got = _phase_c_candidate(deep, deep, **kw)
    assert got["bin_c_type"] == "SPRING" and got["bin_c_undercut_atr"] == pytest.approx(4.0)


def test_the_band_pool_no_longer_caps_an_event_by_length(monkeypatch):
    from engine_alpha.structure.rail_qualification import _qualify_band

    n = 80
    close, low, high = np.full(n, 105.0), np.full(n, 104.0), np.full(n, 106.0)
    close[30:55], low[30:55] = 98.0, 97.0                  # 25 trading days under the support area
    args = (close, low, high, 100.0, 110.0, 0.5)
    assert _qualify_band(*args) is None, "flag-off a 25-day event is a markdown leg"
    monkeypatch.setattr(settings, DEPTH, True)
    read = _qualify_band(*args)
    assert read is not None and (read["excursions"][0]["start"], read["excursions"][0]["end"]) == (30, 55)


def test_the_band_pool_no_longer_caps_an_event_by_depth(monkeypatch):
    from engine_alpha.structure import rail_qualification

    seen = []
    monkeypatch.setattr(rail_qualification, "_qualify_band", lambda *a, **k: seen.append(k["max_depth"]) or None)
    df = _zigzag_frame(lo=100.0, hi=110.0)
    rail_qualification.qualify_pair_events(df, 99.5, 110.5, 2.0)
    monkeypatch.setattr(settings, DEPTH, True)
    rail_qualification.qualify_pair_events(df, 99.5, 110.5, 2.0)
    assert seen == [settings.BAND_EVENT_MAX_DEPTH_ATR * 2.0, None]
