"""Layer-0 market-structure substrate: HH/HL/LH/LL labelling + BOS/reversal."""
from __future__ import annotations

import pandas as pd

from core.structure.market_structure import (
    classify_window_descent,
    label_market_structure,
    read_market_structure,
)
from core.structure.metrics import (
    measure_resistance_events,
    measure_support_tests,
    read_box_events,
    read_box_staircase,
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


def test_l1_two_bar_up_shuffle_is_not_a_march():
    # BBN/CII/PCQ class: a len-2 window where both H and L tick up is ONE step,
    # net advance ~0 -> a flat base poke, not a markup. The min-steps floor keeps
    # it out of rising_march (it is honest "mixed", not an over-confident march).
    out = classify_window_descent([10.0, 10.2], [9.8, 9.9])
    assert out["rising_march"] is False
    assert out["classification"] == "mixed"


def test_l1_confirmed_higher_low_then_higher_high_ends_the_test():
    # Descent, then a higher-low that the next bar carries above -> turn (BOS-up).
    highs = [10.0, 9.5, 9.2, 9.4, 9.7]
    lows = [9.6, 9.2, 8.9, 9.1, 9.5]
    out = classify_window_descent(highs, lows)
    assert out["confirmed_turn_bar"] == 3
    assert out["classification"] == "turned"


def test_l1_early_up_blip_overrun_by_new_low_is_not_turned():
    # AAON/BTX class: a confirmed up-blip early (bar 2) that the window then
    # OVERRUNS with a new low (bar 4) is not a real ending turn. The raw
    # confirmed_turn_bar still records the blip, but the window stays a dip
    # because its lowest low sits AFTER the turn.
    highs = [10.0, 9.4, 9.6, 9.7, 9.0]
    lows = [9.6, 9.1, 9.3, 9.5, 8.7]
    out = classify_window_descent(highs, lows)
    assert out["confirmed_turn_bar"] == 2          # the blip is still measured
    assert out["window_low_idx"] == 4              # but a new low comes after it
    assert out["classification"] != "turned"
    assert out["classification"] == "clean_dip"


def test_l1_three_bar_all_up_is_not_a_valley_turn():
    # A fully-up 3-bar window has its low at bar 0 — there is no descent into a
    # valley, so it must NOT read as an ending valley-turn. Below the march
    # step-floor it lands in honest 'mixed', never the backwards 'turned'.
    out = classify_window_descent([10.0, 11.0, 12.0], [9.0, 10.0, 11.0])
    assert out["window_low_idx"] == 0
    assert out["classification"] != "turned"
    assert out["classification"] == "mixed"


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


# --- Layer 2: the labeled in-box staircase (read_box_staircase) ----------------

def test_l2_staircase_reads_a_two_sided_zigzag():
    # A clean sawtooth between S=10 and R=12: peaks tag R, valleys tag S -> a
    # genuine two-sided equilibrium zigzag.
    highs = [12.0, 11.0, 12.0, 11.0, 12.0, 11.0, 12.0]
    lows = [11.0, 10.0, 11.0, 10.0, 11.0, 10.0, 11.0]
    df = pd.DataFrame({"High": highs, "Low": lows})
    out = read_box_staircase(df, R=12.0, S=10.0, atr_val=0.5)
    assert out["is_zigzag"] is True
    assert out["n_swings"] >= 3
    assert any(s["kind"] == "peak" and s["rail_event"] == "touch_R" for s in out["swings"])
    assert any(s["kind"] == "valley" and s["rail_event"] == "touch_S" for s in out["swings"])


def test_l2_staircase_flags_rail_breaches():
    # A peak pokes above R (upthrust shape) and a valley pokes below S (spring
    # shape): both must surface as rail breaches for the event layer to read.
    highs = [12.0, 11.0, 12.6, 11.0, 12.0, 11.0, 12.0]
    lows = [11.0, 10.0, 11.0, 9.4, 11.0, 10.0, 11.0]
    df = pd.DataFrame({"High": highs, "Low": lows})
    out = read_box_staircase(df, R=12.0, S=10.0, atr_val=0.5)
    assert any(s["rail_event"] == "breach_R" for s in out["swings"])
    assert any(s["rail_event"] == "breach_S" for s in out["swings"])


def test_l2_staircase_empty_on_degenerate_box():
    df = pd.DataFrame({"High": [12.0, 11.0, 12.0], "Low": [11.0, 10.0, 11.0]})
    out = read_box_staircase(df, R=10.0, S=12.0, atr_val=0.5)   # R <= S
    assert out["n_swings"] == 0
    assert out["is_zigzag"] is False


# --- Layer 2 Brick 2: R-rail event zones (measure_resistance_events) ------------

def test_l2_sos_advance_that_holds():
    # Phase-D advance breaches R=12 then HOLDS above support (no drop to the
    # low-zone 10.6) for >= hold_min_bars -> a confirmed SOS (held, not continued).
    highs = [11.0, 10.6, 12.3, 11.5, 11.6, 11.5]
    lows = [10.5, 10.2, 11.8, 11.2, 11.3, 11.2]
    df = pd.DataFrame({"High": highs, "Low": lows})
    events = measure_resistance_events(df, R=12.0, S=10.0, atr_val=0.5, hold_min_bars=2)
    sos = [e for e in events if e["type"] == "SOS"]
    assert sos
    assert sos[0]["breached"] is True and sos[0]["resolution"] == "held"
    assert sos[0]["strength_box"] is not None and sos[0]["strength_box"] > 0


def test_l2_upthrust_wave_that_fails_back():
    # Phase-D advance breaches R=12 then GIVES IT BACK to the low-zone within
    # hold_min_bars (no hold) -> the run-up is an upthrust, not a string of SOS.
    highs = [11.0, 10.6, 12.3, 10.8, 10.4, 11.1, 10.5]
    lows = [10.5, 10.2, 11.8, 10.4, 10.0, 10.6, 10.2]
    df = pd.DataFrame({"High": highs, "Low": lows})
    events = measure_resistance_events(df, R=12.0, S=10.0, atr_val=0.5, hold_min_bars=2)
    ut = [e for e in events if e["breached"]]
    assert ut and ut[0]["type"] == "upthrust"
    assert ut[0]["resolution"] == "failed"


def test_l2_resistance_events_empty_on_degenerate_box():
    df = pd.DataFrame({"High": [12.0, 12.4, 11.0], "Low": [11.0, 11.8, 10.5]})
    assert measure_resistance_events(df, R=10.0, S=12.0, atr_val=0.5) == []   # R<=S


# --- Layer 2 SOS calibration: near-R bound + real-consolidation hold ------------

def test_l2_held_far_above_R_is_markup_not_sos():
    # A two-sided box that oscillates, then a Phase-D wave breaks FAR above R=12
    # (peak_box_pos ~2.5) and holds tight: that is post-breakout MARKUP, not a
    # creek-jump SOS — the AMRZ over-fire fix (a reach far above R is never SOS).
    highs = [11.8, 10.5, 11.9, 10.6, 15.0, 14.8, 14.9, 14.8, 14.9]
    lows = [11.0, 10.1, 11.0, 10.1, 14.5, 14.6, 14.6, 14.6, 14.6]
    df = pd.DataFrame({"High": highs, "Low": lows})
    events = measure_resistance_events(df, R=12.0, S=10.0, atr_val=0.5, hold_min_bars=2)
    assert not any(e["type"] == "SOS" for e in events)        # never SOS this far above R
    mk = [e for e in events if e["type"] == "markup"]
    assert mk and mk[0]["near_r"] is False and mk[0]["breached"] is True


def test_l2_sos_carries_near_r_and_consolidation_fields():
    # The genuine near-R held SOS exposes the calibration fields used to gate it.
    highs = [11.0, 10.6, 12.3, 11.5, 11.6, 11.5]
    lows = [10.5, 10.2, 11.8, 11.2, 11.3, 11.2]
    df = pd.DataFrame({"High": highs, "Low": lows})
    sos = [e for e in measure_resistance_events(df, R=12.0, S=10.0, atr_val=0.5,
                                                hold_min_bars=2) if e["type"] == "SOS"]
    assert sos
    e = sos[0]
    assert e["near_r"] is True and e["consolidation"] is True
    assert isinstance(e["hold_range_box"], float)


# --- Layer 2 Brick 3: S-rail TEST zones (measure_support_tests) ------------------

def test_l2_support_touch_that_holds_is_a_test():
    highs = [11.5, 10.6, 11.8, 10.7, 11.9, 11.0, 11.8]
    lows = [10.8, 10.1, 11.0, 10.2, 11.0, 10.4, 11.0]
    df = pd.DataFrame({"High": highs, "Low": lows})
    ev = measure_support_tests(df, R=12.0, S=10.0, atr_val=0.5, hold_min_bars=2)
    held = [e for e in ev if e["type"] == "test"]
    assert held
    assert held[0]["resolution"] == "held" and held[0]["valley_box_pos"] <= 0.30


def test_l2_support_touch_that_breaks_down_fails():
    # A valley that touches S then breaks well below it is a failed test, not held.
    highs = [11.5, 10.7, 11.2, 10.4, 10.3, 10.0, 10.1]
    lows = [10.8, 10.2, 10.3, 9.7, 9.5, 9.3, 9.4]
    df = pd.DataFrame({"High": highs, "Low": lows})
    ev = measure_support_tests(df, R=12.0, S=10.0, atr_val=0.5, hold_min_bars=2)
    assert any(e["type"] == "failed" for e in ev)
    assert not any(e["type"] == "test" for e in ev)


# --- Layer 2 unified event view (read_box_events) -------------------------------

def test_l2_read_box_events_assembles_base_relative_and_ordered():
    from types import SimpleNamespace
    highs = [11.0, 10.6, 12.3, 11.5, 11.6, 11.5, 10.4, 11.2]
    lows = [10.5, 10.2, 11.8, 11.2, 11.3, 11.2, 10.1, 10.6]
    n = len(highs)
    df = pd.DataFrame({
        "High": highs, "Low": lows,
        "Close": [(h + lo) / 2 for h, lo in zip(highs, lows)],
        "Volume": [1.0] * n, "Vol_50": [1.0] * n,
    })
    box = SimpleNamespace(start_bar=0, base_len=n, R=12.0, S=10.0,
                          r_anchor_bar=0, s_anchor_bar=1)
    ev = read_box_events(df, box, atr_val=0.5)
    assert ev  # at least the R/S rail events
    # Every zone is box-relative (0 <= bar < base_len) and tagged with rail/type.
    for e in ev:
        assert 0 <= e["zone_start"] < n and 0 <= e["anchor_bar"] < n
        assert e["rail"] in ("R", "S") and "type" in e
    # Deterministically ordered by zone_start.
    starts = [e["zone_start"] for e in ev]
    assert starts == sorted(starts)


def test_l2_read_box_events_empty_on_degenerate_box():
    from types import SimpleNamespace
    df = pd.DataFrame({"High": [12.0, 12.4, 11.0], "Low": [11.0, 11.8, 10.5]})
    box = SimpleNamespace(start_bar=0, base_len=3, R=10.0, S=12.0,
                          r_anchor_bar=0, s_anchor_bar=1)
    assert read_box_events(df, box, atr_val=0.5) == []   # R<=S


def test_l2_read_box_events_offset_origin_translation_and_tiebreak(monkeypatch):
    # The KEY risk: find_spring/find_lps return df-relative bars; the assembler must
    # translate them to box-relative by (- box.start_bar). With box.start_bar=0 the
    # translation is invisible, so use a box that starts at bar 3 and stub the reused
    # detectors at KNOWN df-relative bars to pin the origin shift AND the tie-break.
    from types import SimpleNamespace
    import core.structure.bricks as bricks

    highs = [20.0, 20.0, 20.0] + [11.0, 10.6, 12.3, 11.5, 11.6, 11.5, 10.4, 11.2]
    lows = [19.0, 19.0, 19.0] + [10.5, 10.2, 11.8, 11.2, 11.3, 11.2, 10.1, 10.6]
    n, start = len(highs), 3
    df = pd.DataFrame({
        "High": highs, "Low": lows,
        "Close": [(h + lo) / 2 for h, lo in zip(highs, lows)],
        "Volume": [1.0] * n, "Vol_50": [1.0] * n,
    })
    box = SimpleNamespace(start_bar=start, base_len=n - start, R=12.0, S=10.0,
                          r_anchor_bar=start, s_anchor_bar=start + 1)
    # Both anchor at df-bar start+2 so they collide at box-relative zone_start 2.
    fake_spring = SimpleNamespace(tip_bar=start + 2, recovery_bar=start + 4,
                                  undercut_atr=0.9, recovery_bars=2)
    fake_lps = SimpleNamespace(start_bar=start + 2, end_bar=start + 5,
                               low_bar=start + 3, swing_type="terminal_valley")
    monkeypatch.setattr(bricks, "find_spring", lambda *a, **k: fake_spring)
    monkeypatch.setattr(bricks, "find_lps", lambda *a, **k: fake_lps)

    ev = read_box_events(df, box, atr_val=0.5, v_bar=0)  # v_bar=0 -> lps clears Phase-D gate
    spring = [e for e in ev if e["type"] == "spring"]
    lps = [e for e in ev if e["type"] == "lps"]
    assert spring and lps                                  # reused detector paths emit
    assert spring[0]["zone_start"] == 2 and spring[0]["anchor_bar"] == 2   # start+2 -> 2
    assert lps[0]["zone_start"] == 2 and lps[0]["anchor_bar"] == 3         # low start+3 -> 3
    order = {e["type"]: i for i, e in enumerate(ev)}
    assert order["spring"] < order["lps"]                  # tie-break: priority spring(0) < lps(3)
