"""Build step 3 of the final method (Sun 13/09/2026): LPS refusals to grades,
DARK, behind ONE flag. Flag off the path is byte-identical (the fleet, junk,
marks and reader-pin guards prove that at scale); these tests prove the flag's
mechanics on fakes, so a branch that silently stopped biting would go red here.

His points (docs/final_method_2026-09.md): 18 the support side read on whole
bars (his Q18 "not below the support area" and his JAZZ answer: a poke never
refuses, a window mostly under the area does, one mostly under S is typed
UNDERCUT_S; the tight-box widening leaves the ceiling once the ceiling is read
in ranges); 19
the three post-window checks go, and the depth cap in profile units with them;
20 volume never refuses and never elects.
"""
from __future__ import annotations

import numpy as np
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure.lps import _zone_tolerance, detect_lps, detect_lps_candidates

FLAG = "LPS_REFUSALS_TO_GRADES_ENABLED"
# Box 100..110 on a stock whose daily range is 2: the zone area is 1.0 (no
# tight-box widening at a 10 percent box), the support floor 99, the profile
# unit 8 (spread cap 10, depth 3.2..36 in price), the span cap 8.5.
KW = dict(sup_avg=100, res_avg=110, atr_val=2, base_range_threshold=8, base_len=20, swing_complete_idx=-1)


@pytest.fixture
def _three_day(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)


def test_the_step3_flag_is_dark_and_rides_the_manifest():
    assert getattr(settings, FLAG) is False
    assert FLAG in ENGINE_SETTINGS_KEYS


def test_a_poke_under_the_support_area_never_refuses_and_the_zone_is_typed_by_the_bars(monkeypatch, _three_day, _lps_behavior_frame):
    # His JAZZ answer: on support "since most of the move is above it and only small parts of it poke out down".
    # The last day's low pokes a full range under the support floor; most of the window's travel sits above S.
    df = _lps_behavior_frame(highs=[104, 102, 100.5], lows=[101, 99.5, 97], closes=[102, 100.5, 100])
    off, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert off is None and rejects["low outside the support zones"] == 1
    monkeypatch.setattr(settings, FLAG, True)
    on = detect_lps(df, df.iloc[-1], **KW)
    assert on is not None and on["low"] == 97, "the low is the wick low, a fact, never a refusal"
    assert on["zone_type"] == "INSIDE" and on["setup_type"] == "LPS", "most of the move above S: ON support"
    closing_under = _lps_behavior_frame(highs=[104, 102, 100.5], lows=[101, 99.5, 97], closes=[102, 100.5, 98])
    c = detect_lps(closing_under, closing_under.iloc[-1], **KW)
    assert c is not None and c["zone_type"] == "INSIDE", "a close under S changes nothing: the bars decide"


def test_a_window_whose_move_sits_mostly_under_s_is_an_lps_on_a_spring_candidate(monkeypatch, _three_day, _lps_behavior_frame):
    # 5.5 of the window's 7.2 of travel sits under S = 100, while every close prints above S.
    df = _lps_behavior_frame(highs=[101, 100.4, 100.3], lows=[99.0, 98.0, 97.5], closes=[100.5, 100.2, 100.1])
    monkeypatch.setattr(settings, FLAG, True)
    c = detect_lps(df, df.iloc[-1], **KW)
    assert c is not None and c["zone_type"] == "UNDERCUT_S" and c["setup_type"] == "REBOUND", \
        "closes above S do not make it ON support; most of the move is under it"


def test_a_window_below_the_support_area_is_refused_as_he_ruled(monkeypatch, _three_day, _lps_behavior_frame):
    """His Q18: "not below the support area". Every bar of this window sits under S - 0.5 ranges (99)."""
    df = _lps_behavior_frame(highs=[98.8, 97.8, 97.2], lows=[96.6, 95.8, 95.4], closes=[97.0, 96.2, 95.8])
    monkeypatch.setattr(settings, FLAG, True)
    res, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert res is None and rejects["low outside the support zones"] == 1


def test_a_low_inside_the_area_with_closes_above_s_is_retyped_from_the_wick_to_the_bars(monkeypatch, _three_day, _lps_behavior_frame):
    df = _lps_behavior_frame(highs=[104, 102, 100.5], lows=[101, 99.8, 99.2], closes=[102, 100.5, 100])
    off = detect_lps(df, df.iloc[-1], **KW)
    assert off is not None and off["zone_type"] == "UNDERCUT_S", "today the lowest wick types the zone"
    monkeypatch.setattr(settings, FLAG, True)
    on = detect_lps(df, df.iloc[-1], **KW)
    assert on is not None and on["zone_type"] == "INSIDE" and on["low"] == 99.2


def test_the_tight_box_widening_leaves_the_ceiling_once_the_ceiling_is_in_ranges(monkeypatch, _three_day, _lps_behavior_frame):
    # An 8 percent box on a stock whose range is 2: the widening makes the area 4.0 (half the box), so today's
    # ceiling is 112 and the ruled 1.35-range ceiling would be 110.7. A shelf resting at 111.5 sits between them.
    kw = dict(KW, res_avg=108)
    assert _zone_tolerance(100.0, 108.0, 2.0) == 4.0
    df = _lps_behavior_frame(highs=[115, 113.5, 112.5], lows=[113, 112, 111.5], closes=[114, 112.5, 112])
    assert detect_lps(df, df.iloc[-1], **kw) is not None, "today the widening admits it"
    monkeypatch.setattr(settings, FLAG, True)
    assert detect_lps(df, df.iloc[-1], **kw) is not None, "step 3 alone keeps today's ceiling (MRK's tight box)"
    monkeypatch.setattr(settings, "LPS_RANGES_YARDSTICK_ENABLED", True)
    _, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **kw)
    assert rejects["low outside the support zones"] == 1, "with the ceiling in ranges it is exactly 1.35 ranges"
    monkeypatch.setattr(settings, FLAG, False)
    assert detect_lps(df, df.iloc[-1], **kw) is not None, "the yardstick alone keeps the widened ceiling (step 2 as measured)"


@pytest.mark.parametrize("post_day, slug", [
    (dict(high=99, low=90, close=90.5), "support hold broken"),
    (dict(high=99, low=93, close=95), "low broken after the LPS"),
    (dict(high=112, low=97, close=100), "spread widens after the LPS"),
])
def test_the_three_post_window_checks_go(monkeypatch, _three_day, _lps_behavior_frame, post_day, slug):
    df = _lps_behavior_frame(highs=[104, 102, 100, post_day["high"]], lows=[101, 99.8, 99.2, post_day["low"]],
                             closes=[102, 100.5, 100, post_day["close"]])
    off, rejects = detect_lps_candidates(df, df.iloc[-1], diagnose=True, **KW)
    assert not [c for c in off if (c["start_index"], c["end_index"]) == (0, 3)] and rejects[slug] == 1
    monkeypatch.setattr(settings, FLAG, True)
    on, rejects = detect_lps_candidates(df, df.iloc[-1], diagnose=True, **KW)
    assert [c for c in on if (c["start_index"], c["end_index"]) == (0, 3)], "the window before the post day is read"
    assert rejects[slug] == 0


def test_the_depth_cap_in_profile_units_goes(monkeypatch, _three_day, _lps_behavior_frame):
    kw = dict(KW, base_range_threshold=1)       # profile unit 1.5: the cap is 6.75 in price
    df = _lps_behavior_frame(highs=[106.5, 103.5, 100.5], lows=[105, 102, 99.2])
    off, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **kw)
    assert off is None and rejects["pullback depth out of range (4.87)"] == 1
    monkeypatch.setattr(settings, FLAG, True)
    on = detect_lps(df, df.iloc[-1], **kw)
    assert on is not None and on["pullback_profile"] == pytest.approx(7.3 / 1.5), "the dig is a fact"


def test_volume_never_refuses(monkeypatch, _three_day, _lps_behavior_frame):
    loud = _lps_behavior_frame(highs=[104, 102, 100.5], lows=[101, 99.8, 99.2], closes=[102, 100.5, 100])
    loud["Volume"] = 950                        # 95 percent of the 50-day average: no dry-up
    off, rejects = detect_lps(loud, loud.iloc[-1], diagnose=True, **KW)
    assert off is None and rejects["volume not drying up"] == 1
    broken = loud.copy()
    broken["Vol_50"] = np.nan
    off, rejects = detect_lps(broken, broken.iloc[-1], diagnose=True, **KW)
    assert off is None and rejects["volume baseline invalid"] == 1

    monkeypatch.setattr(settings, FLAG, True)
    on = detect_lps(loud, loud.iloc[-1], **KW)
    assert on is not None and on["vol_contraction"] == pytest.approx(0.05), "the ratio stays a fact on the card"
    on = detect_lps(broken, broken.iloc[-1], **KW)
    assert on is not None and on["vol_contraction"] == 0.0


def test_volume_never_elects(monkeypatch, _three_day, _lps_behavior_frame):
    monkeypatch.setattr(settings, FLAG, True)
    loud = _lps_behavior_frame(highs=[104, 102, 100.5], lows=[101, 99.8, 99.2], closes=[102, 100.5, 100])
    quiet = loud.copy()
    loud["Volume"], quiet["Volume"] = 950, 100
    (a,), _ = detect_lps_candidates(loud, loud.iloc[-1], diagnose=True, **KW)
    (b,), _ = detect_lps_candidates(quiet, quiet.iloc[-1], diagnose=True, **KW)
    assert a["vol_contraction"] != b["vol_contraction"]
    assert a["_quality"] == b["_quality"] > 0, "the election weight is volume-free"


# ── point 19, his answer on AEF (Mon 14/09/2026): the pullback increasing with sellers is fatal ─────────────────
# Four bars: the day before the window, then the three-day window. Box 100..110, daily range 2 (KW above).

FATAL = "LPS_SELLERS_RISING_FATAL_ENABLED"
_PRIOR = (104.5, 103.5)


def _four(lows_highs):
    highs = [_PRIOR[0]] + [h for h, _ in lows_highs]
    lows = [_PRIOR[1]] + [lo for _, lo in lows_highs]
    return highs, lows


def test_the_sellers_rising_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, FATAL) is False and FATAL in ENGINE_SETTINGS_KEYS


def test_three_days_each_wider_and_each_falling_further_is_no_lps(monkeypatch, _three_day, _lps_behavior_frame):
    """AEF Tue 02/06 to Thu 04/06/2026 in miniature: spreads 1.0, 1.5, 2.0; falls -0.5, 1.05, 1.95; the last fall
    bigger than the whole 1.5 range of the day before."""
    df = _lps_behavior_frame(*_four([(105.0, 104.0), (104.2, 102.7), (102.5, 100.5)]))
    assert detect_lps(df, df.iloc[-1], **KW) is not None, "flag-off today's read takes it"
    monkeypatch.setattr(settings, FATAL, True)
    res, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert res is None and rejects["the pullback grows with sellers"] == 1


@pytest.mark.parametrize("bars, why", [
    ([(105.0, 104.0), (104.4, 102.9), (103.6, 101.6)], "grows, but the last fall (1.05) is under the day before's 1.5"),
    ([(105.0, 103.0), (104.2, 102.7), (102.5, 101.3)], "a big last fall, but the spreads shrink"),
    ([(106.0, 104.0), (105.0, 103.4), (104.2, 102.7)], "his BMRN shape: final bars shallow and in decline"),
    ([(105.0, 104.0), (103.6, 102.2), (102.3, 100.5)], "wider and a big last fall, but the fall before was bigger"),
])
def test_only_both_halves_together_refuse(monkeypatch, _three_day, _lps_behavior_frame, bars, why):
    df = _lps_behavior_frame(*_four(bars))
    assert detect_lps(df, df.iloc[-1], **KW) is not None, why
    monkeypatch.setattr(settings, FATAL, True)
    assert detect_lps(df, df.iloc[-1], **KW) is not None, why


def test_the_measure_only_staircase_keeps_the_window(monkeypatch, _three_day, _lps_behavior_frame):
    df = _lps_behavior_frame(*_four([(105.0, 104.0), (104.2, 102.7), (102.5, 100.5)]))
    monkeypatch.setattr(settings, FATAL, True)
    cands, _ = detect_lps_candidates(df, df.iloc[-1], staircase=True, **KW)
    assert cands, "the support-test staircase reads every window; the refusal is the election's"
