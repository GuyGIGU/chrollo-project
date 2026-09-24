"""Build step 12 of the final method, part two (docs/final_method_2026-09.md point 21): the grade ledger.

His answer 10 ("Volume: no hard gates, no points") and his Wed 12/08/2026 ruling (a setup is more complete with a
clear Phase C); the ledger docs/grade_ledger_2026-09.md gives every one of today's 171 points a fate. Under ONE
default-off switch, GRADE_LEDGER_ENABLED: the tightness term reads the box's height in daily ranges, the committed
turns at each rail on the line replace touch bars, the LPS term reads the window's mean bar spread in ranges, the
dead-space dock's pardon is keyed to a named leg on the map, seven terms go to zero weight and stay archived, and
tier S keeps its ceiling in ranges. Flag-off byte-identical.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha import evaluation
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.scoring import taxonomy
from engine_alpha.scoring.scoring import calculate_structure_tier, score_setup

SWITCH = "GRADE_LEDGER_ENABLED"
NAMES = ("GRADE_LEDGER_CAPS", "BOX_HEIGHT_FULL_RANGES", "BOX_HEIGHT_ZERO_RANGES", "TURNS_POINT_RATE",
         "LPS_SPREAD_FULL_RANGES", "LPS_SPREAD_ZERO_RANGES", "TIER_S_MAX_HEIGHT_RANGES")
ZEROED = ("SCORE_BASE_AGE", "SCORE_VOL_CONTRACTION", "SCORE_ATR_SQUEEZE", "SCORE_CONTRACTION",
          "SCORE_ASCENDING_SUPPORT", "SCORE_ADR", "SCORE_52W_HIGH_PROXIMITY")


@pytest.fixture
def switch_on(monkeypatch):
    monkeypatch.setattr(settings, SWITCH, True)


def _score(**over):
    """A full-credit base flag-off: tight, worked, old, dry, squeezed, near its high, on a lively mover."""
    kw = dict(box_width=0.05, r_touches=4, s_touches=4, atr_ratio=0.5, tightness_ratio=0.3, vol_contraction=0.6,
              base_len=120, yearly_return=0.5, excess_return=0.3, dist_52w_high_pct=-0.02, breadth_pct=0.7,
              contraction_quality=1.0, support_quality=1.0, adr_quality=1.0, adr_value=3.0,
              traversal_density=0.5, max_swing_frac=1.0, dwell_asymmetry=0.0, has_spring=False)
    kw.update(over)
    return score_setup(**kw)


def test_the_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, SWITCH) is False
    assert {SWITCH, *NAMES} <= set(ENGINE_SETTINGS_KEYS)
    assert set(settings.GRADE_LEDGER_CAPS) == set(ZEROED)
    assert all(v == 0 for v in settings.GRADE_LEDGER_CAPS.values())
    assert (settings.BOX_HEIGHT_FULL_RANGES, settings.BOX_HEIGHT_ZERO_RANGES) == (1.0, 4.0)
    assert (settings.LPS_SPREAD_FULL_RANGES, settings.LPS_SPREAD_ZERO_RANGES) == (0.6, 1.6)
    assert settings.TURNS_POINT_RATE == 1.5 and settings.TIER_S_MAX_HEIGHT_RANGES == 2.5


# ── one cap resolver ─────────────────────────────────────────────────────────

def test_cap_of_reads_the_setting_flag_off_and_the_ledger_flag_on(monkeypatch):
    assert taxonomy.cap_of("SCORE_BASE_AGE") == float(settings.SCORE_BASE_AGE) == 22.0
    assert taxonomy.cap_of("SCORE_BOX_TIGHTNESS") == 22.0
    monkeypatch.setattr(settings, SWITCH, True)
    assert taxonomy.cap_of("SCORE_BASE_AGE") == 0.0
    assert taxonomy.cap_of("SCORE_BOX_TIGHTNESS") == 22.0, "a cap the ledger does not name stays as set"
    assert taxonomy.REGISTRY[6].key == "base_age" and taxonomy.REGISTRY[6].cap() == 0.0


def test_the_divisor_moves_with_the_ledger(monkeypatch):
    assert taxonomy.structural_cap_sum() == pytest.approx(171.0), "today's 171 points"
    monkeypatch.setattr(settings, SWITCH, True)
    assert taxonomy.structural_cap_sum() == pytest.approx(171.0 - (22 + 20 + 8 + 12 + 8 + 8 + 8))


# ── the scorer ───────────────────────────────────────────────────────────────

def test_flag_off_the_ledger_reads_are_ignored():
    plain = _score()
    with_reads = _score(height_ranges=3.9, turns=(1, 1), window_spread_ranges=1.5, largest_limb_named=True)
    assert with_reads == plain
    assert plain["total"] > 100


def test_the_zeroed_terms_read_zero_under_the_ledger(switch_on):
    on = _score()
    for key in ("base_age", "vol_contraction", "atr_squeeze", "contraction", "ascending_support", "adr",
                "high_proximity"):
        assert on[key] == 0.0, key
    assert on["total"] == pytest.approx(on["box_tightness"] + on["touch_density"] + on["traversal_quality"]
                                        + on["lps_tightness"] + on["setup_quality"] + on["breadth_bonus"],
                                        abs=0.06), "the five graded terms plus the regime label's points"


def test_the_zeroed_terms_earn_points_flag_off():
    off = _score()
    for key in ("base_age", "vol_contraction", "atr_squeeze", "contraction", "ascending_support", "adr",
                "high_proximity"):
        assert off[key] > 0, key


def test_height_in_ranges_is_the_tightness_term(switch_on):
    assert _score(height_ranges=1.0)["box_tightness"] == 22.0
    assert _score(height_ranges=0.5)["box_tightness"] == 22.0, "tighter than full is full"
    assert _score(height_ranges=2.5)["box_tightness"] == 11.0
    assert _score(height_ranges=4.0)["box_tightness"] == 0.0
    assert _score(height_ranges=5.0)["box_tightness"] == 0.0


def test_without_a_height_read_the_adr_term_stands(monkeypatch):
    off = _score()["box_tightness"]
    monkeypatch.setattr(settings, SWITCH, True)
    assert _score(height_ranges=None)["box_tightness"] == off
    assert _score(height_ranges=4.0)["box_tightness"] != off


def test_turns_at_the_rails_replace_touch_bars(switch_on):
    assert _score(r_touches=0, s_touches=0, turns=(4, 6))["touch_density"] == 25.0, "15 base + the bonus"
    assert _score(r_touches=0, s_touches=0, turns=(2, 2))["touch_density"] == 6.0, "4 turns x 1.5, no bonus"
    assert _score(r_touches=0, s_touches=0, turns=(1, 5))["touch_density"] == 19.0, "9 + the total bonus"
    assert _score(r_touches=9, s_touches=9, turns=None)["touch_density"] == 25.0, "no turns read: the bars"
    assert _score(r_touches=9, s_touches=9, turns=(1, 1))["touch_density"] == 3.0, \
        "with turns read, the bars reach neither the base points nor the bonus"


def test_the_window_spread_is_the_lps_term(switch_on):
    assert _score(window_spread_ranges=0.6)["lps_tightness"] == 20.0
    assert _score(window_spread_ranges=0.4)["lps_tightness"] == 20.0
    assert _score(window_spread_ranges=1.1)["lps_tightness"] == 10.0
    assert _score(window_spread_ranges=1.6)["lps_tightness"] == 0.0
    assert _score(tightness_ratio=0.3, window_spread_ranges=None)["lps_tightness"] == 20.0, "no read: today's"


def test_a_named_leg_is_never_docked_and_an_unnamed_lunge_is(switch_on):
    assert _score(max_swing_frac=2.0, largest_limb_named=True)["traversal_quality"] == 10.0
    assert _score(max_swing_frac=2.0, largest_limb_named=False)["traversal_quality"] == 2.0
    assert _score(max_swing_frac=2.0, largest_limb_named=None)["traversal_quality"] == 2.0, "nothing named"
    assert _score(max_swing_frac=2.0, has_spring=True, largest_limb_named=False)["traversal_quality"] == 2.0, \
        "spring or no spring"
    assert _score(max_swing_frac=2.0, box_width=0.02, largest_limb_named=False)["traversal_quality"] == 2.0, \
        "tight box or not"


def test_flag_off_the_spring_and_the_tight_box_still_pardon():
    assert _score(box_width=0.10, max_swing_frac=2.0)["traversal_quality"] == 2.0
    assert _score(box_width=0.10, max_swing_frac=2.0, has_spring=True)["traversal_quality"] == 10.0
    assert _score(box_width=0.02, max_swing_frac=2.0)["traversal_quality"] == 10.0


def test_tier_s_keeps_its_ceiling_in_ranges(monkeypatch):
    top = float(settings.TIER_S_STRUCT)
    assert calculate_structure_tier(top, box_width=0.30, height_ranges=2.5) == "A", "flag-off: the percent cap"
    monkeypatch.setattr(settings, SWITCH, True)
    top = float(settings.GRADE_LEDGER_TIER_CUTS[0])
    assert calculate_structure_tier(top, box_width=0.30, height_ranges=2.5) == "S", "the percent cap is gone"
    assert calculate_structure_tier(top, box_width=0.05, height_ranges=2.51) == "A", "the ceiling in ranges"
    assert calculate_structure_tier(top, box_width=0.30, height_ranges=None) == "S", "no height read, no ceiling"
    assert calculate_structure_tier(top - 1, box_width=0.05, height_ranges=1.0) == "A", "the grade decides"


def test_the_letters_cuts_move_one_tier_up_under_the_ledger(monkeypatch):
    assert settings.GRADE_LEDGER_TIER_CUTS == (72, 62, 52, 42)
    assert [calculate_structure_tier(g) for g in (62.0, 61.9, 51.9, 41.9, 31.9)] == list("SABCD"), "today's cuts"
    monkeypatch.setattr(settings, SWITCH, True)
    assert [calculate_structure_tier(g) for g in (72.0, 71.9, 61.9, 51.9, 41.9)] == list("SABCD")
    assert calculate_structure_tier(62.0) == "A", "today's S cut is an A on the re-based scale"


# ── the reads on the line ────────────────────────────────────────────────────

def _frame(spec, n=60, band=0.25):
    """OHLC bars through the spec's turns (linear legs, then flat), highs and lows a quarter either side."""
    bars = [b for b, _, _ in spec]
    prices = [float(p) for _, _, p in spec]
    close = np.interp(np.arange(n), bars, prices)
    idx = pd.bdate_range("2025-06-02", periods=n)
    return pd.DataFrame({"Open": close, "High": close + band, "Low": close - band, "Close": close,
                         "Volume": 1e6}, index=idx)


ZIGZAG = [(0, "peak", 110), (5, "valley", 100), (10, "peak", 110), (15, "valley", 100), (20, "peak", 110),
          (25, "valley", 100), (30, "peak", 114), (35, "valley", 106), (40, "peak", 110), (45, "valley", 105),
          (50, "peak", 106)]


def _ctx(df, lps=(45, 51), unit=None):
    structure = SimpleNamespace(box=SimpleNamespace(start_bar=0), unit=unit,
                                lps=SimpleNamespace(start_bar=lps[0], end_bar=lps[1]) if lps else None)
    return {"structure": structure, "atr_for_zone": 1.0, "res_avg": 110.0, "sup_avg": 100.0}


def test_the_ledger_reads_height_turns_window_and_the_largest_limb():
    df = _frame(ZIGZAG)
    out = evaluation._ledger_reads(df, _ctx(df), None)
    assert out["height_ranges"] == pytest.approx(10.0)
    assert out["turns"] == (4, 3), "peaks within half a range of 110 and valleys within half a range of 100"
    assert out["window_spread_ranges"] == pytest.approx(0.5), "the window's bars are half a range tall"
    assert out["max_swing_frac"] == pytest.approx(1.45), "the lunge to 114 off the 100 floor, wick to wick"
    assert out["largest_limb_named"] is None, "no words read: nothing is named"


def test_the_frozen_unit_is_the_ledgers_unit_when_the_box_has_one():
    df = _frame(ZIGZAG)
    frozen = evaluation._ledger_reads(df, _ctx(df, unit=2.0), None)
    assert frozen["height_ranges"] == pytest.approx(5.0)
    assert frozen["window_spread_ranges"] == pytest.approx(0.25), "the window's spread is in the frozen unit too"
    assert evaluation._ledger_reads(df, _ctx(df, lps=None), None)["window_spread_ranges"] is None


def test_the_largest_limb_is_named_when_a_named_leg_covers_it():
    df = _frame(ZIGZAG)
    ctx = _ctx(df)
    sos = {"the_sos": {"launch_bar": 25, "top_bar": 30}}
    assert evaluation._ledger_reads(df, ctx, sos)["largest_limb_named"] is True
    elsewhere = {"the_sos": {"launch_bar": 5, "top_bar": 10}}
    assert evaluation._ledger_reads(df, ctx, elsewhere)["largest_limb_named"] is False
    assert evaluation._ledger_reads(df, ctx, {})["largest_limb_named"] is False


def test_named_legs_read_the_four_kinds_of_word():
    words = {"phase_c": {"start_bar": 3, "tip_bar": 5, "reach_bar": 7},
             "the_upthrust": {"swing_bar": 25, "top_bar": 30, "back_bar": 33},
             "the_sos": {"launch_bar": 35, "top_bar": 40},
             "last_suppers": [{"top_bar": 40, "low_bar": 45}, {"top_bar": 50, "low_bar": None}]}
    assert evaluation._named_legs(words) == [(3, 7), (25, 33), (35, 40), (40, 45)]
    assert evaluation._named_legs({"phase_c": {"start_bar": 3, "tip_bar": 5, "reach_bar": None}}) == [(3, 5)]
    assert evaluation._named_legs({}) == []


def test_the_largest_limb_on_the_line():
    line = [(0, "peak", 110.0, 1), (5, "valley", 100.0, 6), (10, "peak", 114.0, 11), (15, "valley", 108.0, None)]
    assert evaluation._largest_limb(line, 0, 110.0, 100.0) == (pytest.approx(1.4), 5, 10)
    assert evaluation._largest_limb(line, 6, 110.0, 100.0) is None, "one committed turn after the start"
    assert evaluation._largest_limb(line, 0, 110.0, 100.0)[1:] == (5, 10), "the forming turn is not a limb"


# ── the chain ────────────────────────────────────────────────────────────────

def test_the_chain_carries_the_reads_only_under_the_ledger(monkeypatch):
    """The real cascade (EC-17) on the committed shadow fixture: flag-off byte-identical scores; flag-on the
    scorer reads the ledger (the total moves on at least one fire) and every grade stays on its scale."""
    from core.pipeline.screener import _evaluate_ticker
    from engine_alpha.evaluation import EVAL_ERROR
    from tools.shadow_diff import _load_fixture

    frames, scalars = _load_fixture()
    breadth = scalars.get("breadth_pct")
    spy, breadth = float(scalars.get("spy_6m_return", 0.0)), (float(breadth) if breadth is not None else None)
    moved = moved_box = checked = 0
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        off = _evaluate_ticker(ticker, df, spy, breadth)
        if off is None or off is EVAL_ERROR:
            continue
        again = _evaluate_ticker(ticker, df, spy, breadth)
        assert again == off, ticker
        assert "_height_ranges" not in off, "flag-off the row carries no ledger read"
        monkeypatch.setattr(settings, SWITCH, True)
        on = _evaluate_ticker(ticker, df, spy, breadth)
        monkeypatch.setattr(settings, SWITCH, False)
        assert on is not None and on is not EVAL_ERROR, ticker
        assert 0.0 <= float(on["_ta_grade"]) <= 100.0 and on["Tier"] in "SABCD", ticker
        for key in ("base_age", "vol_contraction", "atr_squeeze", "adr"):
            assert float(on["_sub_scores"][key]) == 0.0, (ticker, key)
        assert float(off["_sub_scores"]["base_age"]) > 0.0, ticker
        checked += 1
        moved += float(on["Score"]) != float(off["Score"])
        moved_box += float(on["_sub_scores"]["box_tightness"]) != float(off["_sub_scores"]["box_tightness"])
    assert checked >= 5 and moved >= 1, (checked, moved)
    assert moved_box >= 1, "the height read never reached the scorer"


def test_the_chain_hands_the_height_to_the_ladder_and_the_reads_to_the_row(monkeypatch):
    """Under the switch compose_ta_grade receives the ledger's height read (the S ceiling in ranges rides it)
    and the row carries the five reads; the real cascade on the first firing fixture ticker."""
    from core.pipeline.screener import _evaluate_ticker
    from engine_alpha.evaluation import EVAL_ERROR
    from tools.shadow_diff import _load_fixture

    seen = []
    real = evaluation.compose_ta_grade

    def spy(*args, **kwargs):
        seen.append(kwargs.get("height_ranges"))
        return real(*args, **kwargs)

    monkeypatch.setattr(evaluation, "compose_ta_grade", spy)
    monkeypatch.setattr(settings, SWITCH, True)
    frames, scalars = _load_fixture()
    breadth = scalars.get("breadth_pct")
    spy_ret, breadth = float(scalars.get("spy_6m_return", 0.0)), (float(breadth) if breadth is not None else None)
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        on = _evaluate_ticker(ticker, df, spy_ret, breadth)
        if on is None or on is EVAL_ERROR:
            continue
        assert seen and seen[-1] is not None and seen[-1] == pytest.approx(on["_height_ranges"]), ticker
        assert on["_height_ranges"] > 0 and on["_turns_at_r"] >= 0 and on["_turns_at_s"] >= 0, ticker
        assert on["_window_spread_ranges"] > 0 and on["_largest_limb_named"] in (True, False, None), ticker
        break
    else:
        pytest.fail("no fire on the fixture")


def test_compose_ta_grade_carries_the_height_to_the_ladder(monkeypatch):
    from engine_alpha.scoring.scoring import compose_ta_grade

    full = {t.key: t.cap() for t in taxonomy.always_emitted_terms()}
    monkeypatch.setattr(settings, SWITCH, True)
    assert compose_ta_grade(full, box_width=0.05, height_ranges=1.0)["structure_tier"] == "S"
    assert compose_ta_grade(full, box_width=0.05, height_ranges=3.0)["structure_tier"] == "A"
