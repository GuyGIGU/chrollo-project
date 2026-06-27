"""Layer-0 market-structure substrate: HH/HL/LH/LL labelling + BOS/reversal."""
from __future__ import annotations

import pandas as pd

from core.structure.market_structure import (
    classify_window_descent,
    label_market_structure,
    read_market_structure,
)


def _labels(out):
    return [p["label"] for p in out["points"]]


def test_clean_uptrend_labels_hh_hl_and_marks_bos():
    # valley/peak both stair-stepping up: HL valleys, HH peaks, trend = up.
    zz = [
        (0, "valley", 10.0), (1, "peak", 12.0), (2, "valley", 11.0),
        (3, "peak", 14.0), (4, "valley", 13.0), (5, "peak", 16.0),
    ]
    out = label_market_structure(zz)
    assert out["trend_state"] == "up"
    assert _labels(out) == ["first", "first", "HL", "HH", "HL", "HH"]
    # First HH lifts range->up (a mechanical reversal); the next HH continues (BOS).
    assert [e["type"] for e in out["events"]] == ["reversal", "BOS"]
    assert all(e["direction"] == 1 for e in out["events"])
    assert out["last_event"]["type"] == "BOS" and out["last_event"]["bar"] == 5


def test_downtrend_then_reversal_flips_up():
    # LH/LL downtrend, then a HH takes out the prior swing high -> flips up.
    zz = [
        (0, "peak", 20.0), (1, "valley", 15.0), (2, "peak", 18.0),
        (3, "valley", 12.0), (4, "peak", 22.0), (5, "valley", 17.0),
    ]
    out = label_market_structure(zz)
    assert _labels(out) == ["first", "first", "LH", "LL", "HH", "HL"]
    # LL out of range flips the mechanical trend down; the HH then flips it up.
    assert out["events"][0] == {"bar": 3, "type": "reversal", "direction": -1, "broke": 15.0}
    assert out["last_event"] == {"bar": 4, "type": "reversal", "direction": 1, "broke": 18.0}
    assert out["trend_state"] == "up"


def test_double_top_holds_without_a_break():
    # An equal high matches but does not take out the prior swing high.
    zz = [(0, "valley", 10.0), (1, "peak", 15.0), (2, "valley", 12.0), (3, "peak", 15.0)]
    out = label_market_structure(zz)
    assert _labels(out) == ["first", "first", "HL", "HH"]
    assert out["events"] == []            # no structural break
    assert out["trend_state"] == "range"


def test_short_or_empty_zigzag_is_empty():
    for zz in ([], [(0, "peak", 10.0)]):
        out = label_market_structure(zz)
        assert out["n_points"] == 0
        assert out["trend_state"] == "range"
        assert out["events"] == [] and out["last_event"] is None


def test_read_market_structure_reads_an_uptrend_frame():
    highs = [11, 13, 12, 15, 14, 17, 16, 19, 18, 21, 20, 23]
    lows = [10, 12, 11, 14, 13, 16, 15, 18, 17, 20, 19, 22]
    df = pd.DataFrame({"High": highs, "Low": lows})
    out = read_market_structure(df)
    assert out["trend_state"] == "up"
    assert "HH" in _labels(out) and "HL" in _labels(out)
    # Bar indices are df-positional and land on real pivots (interior bars).
    assert all(0 < p["bar"] < len(df) - 1 for p in out["points"])


# --- Layer 1: the LPS/Test window bottom read (classify_window_descent) --------

def test_l1_clean_descent_is_clean_dip():
    # Every bar a lower-high and lower-low: a pure reaction into support.
    highs = [10.0, 9.6, 9.2, 8.8, 8.5]
    lows = [9.6, 9.2, 8.8, 8.4, 8.1]
    out = classify_window_descent(highs, lows)
    assert out["classification"] == "clean_dip"
    assert out["noise_pokes"] == []
    assert out["confirmed_turn_bar"] is None
    assert out["down_steps"] == 4 and out["up_steps"] == 0


def test_l1_lone_high_poke_is_forgiven_noise():
    # AEF Jun 3->10: a descent with one wide bar (Jun 9) whose high pokes up but
    # whose LOW makes a new low and whose next high falls back -> noise, not a turn.
    highs = [9.77, 9.53, 9.15, 8.95, 9.23, 9.01]
    lows = [9.56, 9.24, 8.64, 8.73, 8.53, 8.68]
    out = classify_window_descent(highs, lows)
    assert 4 in out["noise_pokes"]                 # the Jun 9 poke is forgiven
    assert out["confirmed_turn_bar"] is None       # the formation is not broken
    assert out["classification"] == "clean_dip"


def test_l1_all_up_window_is_a_rising_march():
    # OHI Jun 22->26: every bar higher-high AND higher-low -> markup, not a test.
    highs = [45.29, 46.56, 47.71, 47.75, 48.42]
    lows = [44.30, 45.33, 46.50, 46.94, 47.74]
    out = classify_window_descent(highs, lows)
    assert out["rising_march"] is True
    assert out["classification"] == "rising_march"
    assert out["up_steps"] == 4


def test_l1_confirmed_higher_low_then_higher_high_ends_the_test():
    # Descent, then a higher-low that the next bar carries above -> turn (BOS-up).
    highs = [10.0, 9.5, 9.2, 9.4, 9.7]
    lows = [9.6, 9.2, 8.9, 9.1, 9.5]
    out = classify_window_descent(highs, lows)
    assert out["confirmed_turn_bar"] == 3
    assert out["classification"] == "turned"


def test_l1_flat_tail_reads_as_flat_end():
    highs = [10.0, 9.5, 9.2, 9.22, 9.21, 9.23]
    lows = [9.6, 9.2, 9.0, 8.99, 9.0, 9.01]
    out = classify_window_descent(highs, lows, base_spread=0.3)
    assert out["end_shape"] == "flat"


def test_l1_big_dip_only_when_deep_and_not_tight():
    # Deep window with wide bars (spread 1.0 > base 0.5), depth 7 ATR.
    highs = [20.0, 18.0, 16.0, 14.0]
    lows = [19.0, 17.0, 15.0, 13.0]
    out = classify_window_descent(highs, lows, base_spread=0.5, atr=1.0,
                                  big_dip_depth_atr=3.0)
    assert out["tighter_than_base"] is False
    assert out["big_dip"] is True
    # A measure-only call (no threshold) never asserts a big_dip verdict.
    out2 = classify_window_descent(highs, lows, base_spread=0.5, atr=1.0)
    assert out2["big_dip"] is None


def test_l1_insufficient_window():
    out = classify_window_descent([10.0], [9.0])
    assert out["classification"] == "insufficient"
