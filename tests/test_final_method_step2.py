"""Build step 2 of the final method (Sun 13/09/2026): the ruled stack behind
flags, DARK. Every flag defaults OFF and the flag-off path is byte-identical
(the fleet, junk, marks and reader-pin guards prove that at scale); these tests
prove each flag's mechanics on fakes, so a flag that silently stopped biting
would go red here.

Rulings (docs/decisions.md): R1 whole-bar respect, R8/R12 the LPS in daily
ranges with the 1.35-range ceiling, R9/R9b the LPS defined by graded traits
with the story-position floors, R11 the hand-over in ranges, R13 the dwell
exam graded, R17 the spring bounds lifted, R18 + the sixteenth sitting the one
window per read day ending on the last receding day, and the narrow buy-day
clause (the "still live" test reads the high).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure import box_gates
from engine_alpha.structure.lps import detect_lps, detect_lps_candidates
from engine_alpha.structure.phase_features import _phase_c_candidate

STEP2_FLAGS = (
    "RESPECT_WHOLE_BAR_ENABLED", "DWELL_GRADED_ENABLED", "BOX_HANDOVER_RANGES_ENABLED",
    "SPRING_BOUNDS_LIFTED_ENABLED", "LPS_RANGES_YARDSTICK_ENABLED", "LPS_GRADED_TRAITS_ENABLED",
    "LPS_WINDOW_RECEDING_ENABLED", "LPS_BUY_DAY_READS_HIGH_ENABLED",
)
KW = dict(sup_avg=100, res_avg=110, atr_val=2, base_range_threshold=8, base_len=20, swing_complete_idx=-1)
WIDE = dict(KW, atr_val=4)   # a stock whose daily range is 4: the ruled caps scale with it


def test_every_step2_flag_is_dark_and_rides_the_manifest():
    for flag in STEP2_FLAGS:
        assert getattr(settings, flag) is False, f"{flag} must default OFF (dark) until the operator flips it"
        assert flag in ENGINE_SETTINGS_KEYS, f"{flag} must rotate engine_config_version from birth"


# ── R18 + one window per read day ───────────────────────────────────────────
def test_receding_window_is_one_per_read_day_ending_on_the_last_receding_day(monkeypatch, _lps_behavior_frame):
    df = _lps_behavior_frame(highs=[112, 111, 110, 109, 108], lows=[107, 106, 105, 104, 103])
    off, _ = detect_lps_candidates(df, df.iloc[-1], diagnose=True, **KW)
    assert len(off) > 1, "flag off, the 2..7 length enumeration yields several windows"

    monkeypatch.setattr(settings, "LPS_WINDOW_RECEDING_ENABLED", True)
    on, rejects = detect_lps_candidates(df, df.iloc[-1], diagnose=True, **KW)
    assert len(on) == 1, "one window per read day"
    (c,) = on
    assert (c["start_index"], c["end_index"], c["length"]) == (0, 5, 5), "the run of four receding days plus its top"
    assert c["trigger_price"] == 108 and c["low"] == 103, "the trigger is the last receding day's high"
    assert rejects["does not end on the last receding day"] > 0, "every earlier read day is refused"


def test_receding_window_ends_before_a_non_receding_day_and_the_buy_day_clause_reads_the_high(monkeypatch, _lps_behavior_frame):
    # Day 4 makes a higher high AND a higher low: not receding, so the window
    # ends on day 3 (trigger 109). Day 4's high 111 crossed that trigger while
    # its close 106 sits back under it.
    df = _lps_behavior_frame(highs=[112, 111, 110, 109, 111], lows=[107, 106, 105, 104, 106])
    monkeypatch.setattr(settings, "LPS_WINDOW_RECEDING_ENABLED", True)
    elected = detect_lps(df, df.iloc[-1], **KW)
    assert elected is not None and elected["end_index"] == 4 and elected["trigger_price"] == 109
    assert elected["start_index"] == 0, "the top is the day before the run"

    monkeypatch.setattr(settings, "LPS_BUY_DAY_READS_HIGH_ENABLED", True)
    bought, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert bought is None, "the setup was bought on the cross; nothing shows"
    assert rejects["bought: a later high crossed the trigger"] > 0


def test_buy_day_clause_alone_refuses_a_crossed_trigger_the_close_test_would_keep(monkeypatch, _lps_behavior_frame):
    # Day 4's high 113 crosses every earlier window's trigger while its close
    # 106 sits back under them all; no window ends on day 4 (its low is not
    # the window low). Today the close test keeps a crossed window live.
    df = _lps_behavior_frame(highs=[112, 111, 110, 109, 113], lows=[107, 106, 105, 104, 106])
    assert detect_lps(df, df.iloc[-1], **KW) is not None, "flag off, the close under the trigger keeps it live"
    monkeypatch.setattr(settings, "LPS_BUY_DAY_READS_HIGH_ENABLED", True)
    assert detect_lps(df, df.iloc[-1], **KW) is None


def test_buy_day_clause_elects_the_live_window_beside_a_crossed_one(monkeypatch, _lps_behavior_frame):
    # Two pullbacks: the later one (days 3-5, trigger 104) was crossed by day
    # 6's high 106; the earlier one (days 0-3, trigger 108) never was. Today
    # the elector takes the later window; under the clause the crossed window
    # is out and the live one is elected, not nothing.
    df = _lps_behavior_frame(highs=[112, 110, 109, 108, 105, 104, 106], lows=[107, 105, 104, 103, 100, 99, 101])
    off = detect_lps(df, df.iloc[-1], **KW)
    assert off is not None and off["end_index"] == 6 and off["trigger_price"] == 104
    monkeypatch.setattr(settings, "LPS_BUY_DAY_READS_HIGH_ENABLED", True)
    on = detect_lps(df, df.iloc[-1], **KW)
    assert on is not None and on["end_index"] == 4 and on["trigger_price"] == 108


def test_receding_window_may_not_end_on_a_breakout_day(monkeypatch, _lps_behavior_frame):
    # Day 4 recedes by its lower low but closes 0.5 over the prior high (0.25
    # ranges over the 0.10-range allowance).
    df = _lps_behavior_frame(highs=[112, 111, 110, 109, 110], lows=[107, 106, 105, 104, 103.5],
                             closes=[107, 106, 105, 104, 109.5])
    monkeypatch.setattr(settings, "LPS_WINDOW_RECEDING_ENABLED", True)
    cands, rejects = detect_lps_candidates(df, df.iloc[-1], diagnose=True, **KW)
    assert not [c for c in cands if c["end_index"] == 5]
    assert rejects["ends on a breakout day"] == 1


# ── R9 / R9b + R15: graded traits, the story position stays a refusal ───────
def test_graded_traits_turn_the_spread_cap_into_a_grade(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 4)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 4)
    kw = dict(KW, base_range_threshold=4)          # profile unit 4 -> spread cap 5
    df = _lps_behavior_frame(highs=[110, 109, 108, 107], lows=[106, 104, 102, 101])
    off, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **kw)
    assert off is None and rejects["bar spread too wide"] == 1
    monkeypatch.setattr(settings, "LPS_GRADED_TRAITS_ENABLED", True)
    on = detect_lps(df, df.iloc[-1], **kw)
    assert on is not None and on["tightness_ratio"] == pytest.approx(1.5), "the spread is a fact, not a refusal"


def test_graded_traits_let_the_last_day_sit_above_the_window_low(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(highs=[109, 107, 106], lows=[104, 102, 103], closes=[105, 103, 104])
    off, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert off is None and rejects["does not rest on its low"] == 1
    monkeypatch.setattr(settings, "LPS_GRADED_TRAITS_ENABLED", True)
    on = detect_lps(df, df.iloc[-1], **KW)
    assert on is not None and on["low"] == 102 and on["lps_low_bar"] == 1, "the LPS low is the window low"


def test_graded_traits_keep_the_story_position_as_a_refusal(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_GRADED_TRAITS_ENABLED", True)
    # the last high back at the first high (0.8 over it, 0.4 ranges): no correction
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 4)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 4)
    df = _lps_behavior_frame(highs=[110, 111.5, 108, 110.8], lows=[106, 105, 104, 105])
    cands, rejects = detect_lps_candidates(df, df.iloc[-1], diagnose=True, **KW)
    assert not cands
    assert rejects["its last high is back at its first high, not a correction"] == 1
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 7)
    # a dig under 0.70 ranges: no real pullback
    df = _lps_behavior_frame(highs=[110, 109.8, 109.6], lows=[109.2, 109, 108.8])
    res, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert res is None and rejects["no real pullback (dig under the correction floor)"] > 0
    # the low before the high: not a correction
    df = _lps_behavior_frame(highs=[108, 110, 109, 108.5], lows=[103, 105, 104.5, 104])
    _res, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert rejects["not a correction: the low comes before the high"] > 0


# ── R8 / R12: the LPS in daily ranges ───────────────────────────────────────
def test_ranges_yardstick_lifts_the_zone_ceiling_to_the_ruled_ranges(monkeypatch, _lps_behavior_frame):
    # the window low sits 1.0 range above R: outside today's 0.5-range zone,
    # inside the ruled 1.35-range ceiling
    df = _lps_behavior_frame(highs=[114, 113, 112.5], lows=[113, 112.5, 112], closes=[113.5, 113, 112.2])
    off, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **KW)
    assert off is None and rejects["low outside the support zones"] > 0
    monkeypatch.setattr(settings, "LPS_RANGES_YARDSTICK_ENABLED", True)
    monkeypatch.setattr(settings, "LPS_GRADED_TRAITS_ENABLED", True)
    on = detect_lps(df, df.iloc[-1], **KW)
    assert on is not None and on["zone_type"] == "OVERSHOOT_R" and on["low"] == 112


def test_ranges_yardstick_reads_the_window_height_in_ranges(monkeypatch, _lps_behavior_frame):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    # a 2-bar window 9 tall on a stock with a 4-point daily range: over 0.85
    # box heights (refused today; not a clean downswing at length 2), under
    # 2.5 ranges = 10 (accepted under the yardstick), over 2.0 ranges = 8
    df = _lps_behavior_frame(highs=[110, 106], lows=[105, 101])
    off, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **WIDE)
    assert off is None and rejects["window spans the box"] == 1
    monkeypatch.setattr(settings, "LPS_RANGES_YARDSTICK_ENABLED", True)
    monkeypatch.setattr(settings, "LPS_GRADED_TRAITS_ENABLED", True)
    on = detect_lps(df, df.iloc[-1], **WIDE)
    assert on is not None
    monkeypatch.setattr(settings, "LPS_WINDOW_SPAN_ATR_MAX", 2.0)
    res, rejects = detect_lps(df, df.iloc[-1], diagnose=True, **WIDE)
    assert res is None and rejects["window spans the box"] == 1


# ── R1: a bar is outside only when the whole bar sits beyond the area ───────
def test_whole_bar_respect_counts_a_poke_as_respect(monkeypatch):
    highs = np.array([111.5, 105.0, 113.0]); lows = np.array([108.0, 103.0, 112.0])   # buffer 1 -> ceiling 111
    off = box_gates._respect_stats(highs, lows, 110.0, 100.0, 2.0)
    assert off[3] == 2, "today a wick over the area counts as outside (bars 0 and 2)"
    monkeypatch.setattr(settings, "RESPECT_WHOLE_BAR_ENABLED", True)
    on = box_gates._respect_stats(highs, lows, 110.0, 100.0, 2.0)
    assert on[3] == 1, "the poke is respect; only the whole bar above the area is outside"


# ── R13: the dwell legs are graded ──────────────────────────────────────────
def test_dwell_graded_never_refuses_on_the_close_dwell_legs(monkeypatch):
    eq = {"r_touches": 5, "s_touches": 5, "r_touch_thirds": 3, "s_touch_thirds": 3,
          "lower_dwell": 0.0, "upper_dwell": 0.5, "mid_dwell": 0.2, "coverage": 1.0}
    monkeypatch.setattr(box_gates, "_measure_close_residence", lambda *a, **k: dict(eq))
    eq_df = pd.DataFrame({"High": [109.0] * 30, "Low": [101.0] * 30, "Close": [105.0] * 30})
    assert box_gates._validate_base_quality(eq_df, 110.0, 100.0, 2.0)[3] is False
    monkeypatch.setattr(settings, "DWELL_GRADED_ENABLED", True)
    assert box_gates._validate_base_quality(eq_df, 110.0, 100.0, 2.0)[3] is True


# ── R17: the spring bounds lifted ───────────────────────────────────────────
def test_spring_bounds_lifted_admit_an_early_deep_spring(monkeypatch):
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", False)   # no shakeout fallback in this test
    n, box_start, base_len, S, R, atr = 60, 10, 50, 100.0, 110.0, 3.0
    highs = np.full(n, 106.0); lows = np.full(n, 104.0); closes = np.full(n, 105.0)
    # a spring at bar 18 (first half of the base), 7 deep: 2.33 ranges (under the
    # 3.0-range cap), 0.70 box heights (over the 0.65 box cap); reclaimed at 19
    lows[16:19] = [99.5, 97.0, 93.0]; closes[16:19] = 99.0
    df = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
    kw = dict(box_start=box_start, base_len=base_len, R=R, S=S, atr_val=atr)
    off = _phase_c_candidate(df, df.iloc[box_start:], **kw)
    assert off["bin_c_present"] is False, "today: the late-half rule and the box cap both refuse it"
    monkeypatch.setattr(settings, "SPRING_BOUNDS_LIFTED_ENABLED", True)
    on = _phase_c_candidate(df, df.iloc[box_start:], **kw)
    assert on["bin_c_present"] is True and on["bin_c_event_bar"] == 18
