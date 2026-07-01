"""Layer-0 market-structure substrate: HH/HL/LH/LL labelling + BOS/reversal."""
from __future__ import annotations

import pandas as pd

from core.structure.market_structure import (
    classify_window_descent,
    label_market_structure,
    read_market_structure,
)
from core.structure.metrics import (
    _box_events_with_meta,
    _deepest_valley_bar,
    assemble_box_narrative,
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


# --- Layer 2 — E2: chronological assembly (assemble_box_narrative) ---------------

def _ohlc(highs, lows):
    n = len(highs)
    return pd.DataFrame({
        "High": highs, "Low": lows,
        "Close": [(h + lo) / 2 for h, lo in zip(highs, lows)],
        "Volume": [1.0] * n, "Vol_50": [1.0] * n,
    })


def _box(start, n, R=12.0, S=10.0):
    from types import SimpleNamespace
    return SimpleNamespace(start_bar=start, base_len=n - start, R=R, S=S,
                           r_anchor_bar=start, s_anchor_bar=start + 1)


# A clean bullish staircase: oscillation -> Phase-D wave breaches R=12 NEAR R and
# HOLDS tight for >= the default hold_min_bars(6) -> a confirmed SOS at bar 4.
_CLEAN_BULL_H = [11.0, 10.6, 11.3, 10.7, 12.6, 12.3, 12.4, 12.2, 12.5, 12.3, 12.4]
_CLEAN_BULL_L = [10.5, 10.1, 10.8, 10.2, 11.5, 11.6, 11.7, 11.6, 11.8, 11.7, 11.6]
# A terminal upthrust: breach R at bar 4, collapse to the support low-zone (fails),
# then STAY low -> one upthrust, zero SOS (the TITN read).
_TERMINAL_UT_H = [11.0, 10.6, 11.3, 10.7, 12.6, 11.0, 10.5, 10.4, 10.5, 10.4, 10.5]
_TERMINAL_UT_L = [10.5, 10.1, 10.8, 10.2, 11.8, 10.5, 10.1, 10.0, 10.1, 10.0, 10.1]


def test_e2_read_box_events_unchanged_and_v_single_sourced():
    # The helper extraction must be output-preserving AND single-source the V: the
    # v_bar the assembler reads for phases == the V the detectors gated events on.
    df = _ohlc(_CLEAN_BULL_H, _CLEAN_BULL_L)
    box = _box(0, len(_CLEAN_BULL_H))
    events_pub = read_box_events(df, box, atr_val=0.5)
    events_meta, v_bar, base_n, has_valley = _box_events_with_meta(df, box, atr_val=0.5)
    assert events_pub == events_meta                        # public contract unchanged
    base = df.iloc[box.start_bar:]
    swings = read_box_staircase(base, box.R, box.S, 0.5)["swings"]
    assert v_bar == _deepest_valley_bar(swings)             # same V the gates used
    assert base_n == len(base) and has_valley is True


def test_e2_clean_bullish_chronology_is_intact(monkeypatch):
    import core.structure.bricks as bricks
    from types import SimpleNamespace
    df = _ohlc(_CLEAN_BULL_H, _CLEAN_BULL_L)
    box = _box(0, len(_CLEAN_BULL_H))
    # spring tip at the V (bar 1); LPS low at bar 9 (right of the V) -> Phase-D.
    monkeypatch.setattr(bricks, "find_spring", lambda *a, **k: SimpleNamespace(
        tip_bar=1, recovery_bar=3, undercut_atr=0.9, recovery_bars=2))
    monkeypatch.setattr(bricks, "find_lps", lambda *a, **k: SimpleNamespace(
        start_bar=8, end_bar=10, low_bar=9, swing_type="terminal_valley"))
    nar = assemble_box_narrative(df, box, atr_val=0.5)
    s = nar["spine"]
    assert s["spring"] and s["sos"] and s["lps"]
    assert s["spring"]["anchor_bar"] < s["sos"]["anchor_bar"] < s["lps"]["anchor_bar"]
    assert nar["chronology"] == "intact" and nar["completeness"] == 4
    assert nar["upthrust_terminal"] is False
    assert nar["phases"]["B"] == [0, nar["v_bar"]]
    assert nar["phases"]["C"] == [s["spring"]["zone_start"], s["spring"]["zone_end"]]
    assert nar["phases"]["D"][0] == nar["v_bar"] + 1        # B.end + 1 == D.start
    # trace is a pure render of the spine: one line per piece + summary.
    assert any("spring" in ln for ln in nar["trace"])
    assert any("SOS" in ln for ln in nar["trace"])
    assert nar["trace"][-1] == "-> chronology intact, completeness 4/4"


def test_e2_titn_upthrust_terminal_zero_sos(monkeypatch):
    # The headline anchor: a run-up that tops in one upthrust reads zero SOS +
    # upthrust_terminal, WITHOUT suppressing the independent spring/test/lps.
    import core.structure.bricks as bricks
    from types import SimpleNamespace
    df = _ohlc(_TERMINAL_UT_H, _TERMINAL_UT_L)
    box = _box(0, len(_TERMINAL_UT_H))
    monkeypatch.setattr(bricks, "find_spring", lambda *a, **k: SimpleNamespace(
        tip_bar=1, recovery_bar=3, undercut_atr=1.1, recovery_bars=2))
    monkeypatch.setattr(bricks, "find_lps", lambda *a, **k: SimpleNamespace(
        start_bar=8, end_bar=10, low_bar=8, swing_type="terminal_valley"))
    nar = assemble_box_narrative(df, box, atr_val=0.5)
    assert nar["spine"]["sos"] is None                      # zero SOS in the spine
    assert nar["upthrust_terminal"] is True
    assert nar["spine"]["spring"] is not None               # independence preserved
    assert nar["spine"]["lps"] is not None
    assert nar["chronology"] == "partial"
    # cross-field invariant: a spine SOS and a terminal upthrust are exclusive.
    assert not (nar["spine"]["sos"] is not None and nar["upthrust_terminal"])
    assert any("terminal upthrust" in ln for ln in nar["trace"])


def test_e2_first_sos_is_the_spine_sos(monkeypatch):
    # Two confirmed SOS waves: the spine SOS is the FIRST by bar (the creek-jump);
    # the later held reach stays visible in events[]. Feed synthetic pieces so the
    # selection logic is pinned independent of staircase geometry.
    import core.structure.metrics as metrics
    early = {"type": "SOS", "rail": "R", "anchor_bar": 4, "zone_start": 2,
             "peak_price": 12.4, "peak_box_pos": 1.2, "hold_range_box": 0.4}
    late = {"type": "SOS", "rail": "R", "anchor_bar": 11, "zone_start": 9,
            "peak_price": 12.9, "peak_box_pos": 1.45, "hold_range_box": 0.5}
    monkeypatch.setattr(metrics, "_box_events_with_meta",
                        lambda *a, **k: ([late, early], 1, 16, True))
    nar = metrics.assemble_box_narrative(None, None, 0.5)
    assert nar["spine"]["sos"]["anchor_bar"] == 4           # first by bar, not by quality
    assert sum(1 for e in nar["events"] if e["type"] == "SOS") == 2  # both still visible


def test_e2_completeness_counts_held_tests_only(monkeypatch):
    # The completeness test-slot + the tests count both use the SAME held filter:
    # failed / in_progress S-touches never inflate the tally.
    import core.structure.metrics as metrics
    events = [
        {"type": "test", "rail": "S", "anchor_bar": 2, "zone_start": 2},
        {"type": "test", "rail": "S", "anchor_bar": 5, "zone_start": 5},
        {"type": "failed", "rail": "S", "anchor_bar": 8, "zone_start": 8},
    ]
    monkeypatch.setattr(metrics, "_box_events_with_meta",
                        lambda *a, **k: (events, 1, 12, True))
    nar = metrics.assemble_box_narrative(None, None, 0.5)
    assert nar["tests"] == 2                                # held only (failed excluded)
    assert nar["completeness"] == 1                         # the one test class, capped at 1
    assert nar["chronology"] == "absent"


def test_e2_phases_none_when_no_real_v(monkeypatch):
    # A valid box with zero valley swings has no real V (v_bar defaults to 0) ->
    # phases must be None, not [0,0], even when a Phase-D event exists.
    import core.structure.metrics as metrics
    events = [{"type": "SOS", "rail": "R", "anchor_bar": 4, "zone_start": 2,
               "peak_price": 12.4, "peak_box_pos": 1.2, "hold_range_box": 0.4}]
    monkeypatch.setattr(metrics, "_box_events_with_meta",
                        lambda *a, **k: (events, 0, 8, False))
    nar = metrics.assemble_box_narrative(None, None, 0.5)
    assert nar["phases"] == {"B": None, "C": None, "D": None}


def test_e2_no_veto_shaped_field(monkeypatch):
    # Story-2 negative: the narrative encodes NO pass/fail another layer could read
    # as a gate. Only descriptive grades + upthrust_terminal (a read of the outcome).
    import core.structure.bricks as bricks
    from types import SimpleNamespace
    df = _ohlc(_CLEAN_BULL_H, _CLEAN_BULL_L)
    box = _box(0, len(_CLEAN_BULL_H))
    monkeypatch.setattr(bricks, "find_spring", lambda *a, **k: SimpleNamespace(
        tip_bar=1, recovery_bar=3, undercut_atr=0.9, recovery_bars=2))
    monkeypatch.setattr(bricks, "find_lps", lambda *a, **k: SimpleNamespace(
        start_bar=8, end_bar=10, low_bar=9, swing_type="terminal_valley"))
    nar = assemble_box_narrative(df, box, atr_val=0.5)
    veto_names = {"pass", "fail", "ok", "valid", "invalid", "reject", "veto",
                  "gate", "eligible", "qualifies", "is_complete", "passes"}
    assert not (set(nar) & veto_names)
    # the only bare bools in the top-level dict are the explicitly-descriptive
    # reads (the outcome read + the elected-LPS gate-drop diagnostic) — neither is
    # a pass/fail another layer could consume as a gate.
    bool_keys = [k for k, v in nar.items() if isinstance(v, bool)]
    assert set(bool_keys) == {"upthrust_terminal", "lps_pre_v_dropped"}
    assert isinstance(nar["completeness"], int) and 0 <= nar["completeness"] <= 4


def test_e2_degenerate_box_is_well_formed_empty():
    df = _ohlc([12.0, 12.4, 11.0], [11.0, 11.8, 10.5])
    box = _box(0, 3, R=10.0, S=12.0)                        # R <= S
    nar = assemble_box_narrative(df, box, atr_val=0.5)
    assert nar["events"] == [] and nar["trace"] == []
    assert nar["spine"] == {"spring": None, "sos": None, "lps": None}
    assert nar["completeness"] == 0 and nar["chronology"] == "absent"
    assert nar["upthrust_terminal"] is False
    assert nar["phases"] == {"B": None, "C": None, "D": None}
    assert type(nar["v_bar"]) is int and type(nar["base_n"]) is int


def test_e2_deterministic_and_json_native(monkeypatch):
    # Built twice -> byte-identical when serialized; every leaf a native python
    # type (no numpy scalar leaking through).
    import json
    import core.structure.bricks as bricks
    from types import SimpleNamespace
    df = _ohlc(_CLEAN_BULL_H, _CLEAN_BULL_L)
    box = _box(0, len(_CLEAN_BULL_H))
    monkeypatch.setattr(bricks, "find_spring", lambda *a, **k: SimpleNamespace(
        tip_bar=1, recovery_bar=3, undercut_atr=0.9, recovery_bars=2))
    monkeypatch.setattr(bricks, "find_lps", lambda *a, **k: SimpleNamespace(
        start_bar=8, end_bar=10, low_bar=9, swing_type="terminal_valley"))
    a = assemble_box_narrative(df, box, atr_val=0.5)
    b = assemble_box_narrative(df, box, atr_val=0.5)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert type(a["v_bar"]) is int and type(a["completeness"]) is int

    def _leaves(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from _leaves(v)
        elif isinstance(o, list):
            for v in o:
                yield from _leaves(v)
        else:
            yield o
    # every leaf is a native python type — no numpy scalar leaked through.
    assert all(isinstance(x, (int, float, str, bool, type(None)))
               for x in _leaves(a))
    assert all(type(x).__module__ == "builtins" for x in _leaves(a))


def test_e2_assembler_internals_not_imported_by_pipeline():
    # E3 wired the public assemble_box_narrative into the pipeline (behind the
    # PUZZLE_SCORE_ENABLED flag) as a scoring input — so that name now legitimately
    # appears in core/pipeline. The INTERNAL helper must stay contained: nothing in
    # core/pipeline may reach past the public assembler into _box_events_with_meta.
    import glob
    import os
    pipe = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "core", "pipeline")
    for path in glob.glob(os.path.join(pipe, "*.py")):
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        assert "_box_events_with_meta" not in src


def test_e2_upthrust_terminal_un_terminaled_by_later_r_wave(monkeypatch):
    # The no-lookahead contract: an R-rail markup OR in_progress at/after the last
    # upthrust un-terminals it (the run-up resolved up / is still developing); an
    # S-rail in_progress does NOT (it says nothing about the R-rail run-up).
    import core.structure.metrics as metrics

    def _ut():
        return {"type": "upthrust", "rail": "R", "anchor_bar": 4, "zone_start": 2}
    cases = [
        ([_ut(), {"type": "markup", "rail": "R", "anchor_bar": 7, "zone_start": 5}], False),
        ([_ut(), {"type": "in_progress", "rail": "R", "anchor_bar": 9, "zone_start": 7}], False),
        ([_ut(), {"type": "in_progress", "rail": "S", "anchor_bar": 9, "zone_start": 9}], True),
    ]
    for events, expected in cases:
        monkeypatch.setattr(metrics, "_box_events_with_meta",
                            lambda *a, _e=events, **k: (_e, 1, 12, True))
        nar = metrics.assemble_box_narrative(None, None, 0.5)
        assert nar["upthrust_terminal"] is expected
        assert nar["spine"]["sos"] is None          # terminal is exclusive with a spine SOS


def test_e2_chronology_strict_order_boundary(monkeypatch):
    # intact requires STRICT spring.anchor < sos.anchor < lps.anchor; a tie or an
    # out-of-order trio reads partial (never intact), though completeness is 3.
    import core.structure.metrics as metrics

    def _spring(b):
        return {"type": "spring", "rail": "S", "anchor_bar": b, "zone_start": b,
                "zone_end": b + 1, "recovery_bars": 1, "undercut_atr": 0.9}

    def _sos(b):
        return {"type": "SOS", "rail": "R", "anchor_bar": b, "zone_start": b - 1,
                "peak_price": 12.4, "hold_range_box": 0.4}

    def _lps(b):
        return {"type": "lps", "rail": "S", "anchor_bar": b, "zone_start": b - 1,
                "zone_end": b + 1, "swing_type": "terminal_valley"}

    tie = [_spring(5), _sos(5), _lps(9)]        # spring tip == sos peak -> not strict
    ooo = [_spring(2), _sos(8), _lps(4)]        # lps low before sos peak -> out of order
    for events in (tie, ooo):
        monkeypatch.setattr(metrics, "_box_events_with_meta",
                            lambda *a, _e=events, **k: (_e, 1, 12, True))
        nar = metrics.assemble_box_narrative(None, None, 0.5)
        assert nar["chronology"] == "partial" and nar["completeness"] == 3


def test_e2_partial_from_single_piece_and_phase_d_at_right_edge(monkeypatch):
    import core.structure.metrics as metrics
    # Exactly one canonical piece -> chronology partial (some present, not all).
    spring_only = [{"type": "spring", "rail": "S", "anchor_bar": 3, "zone_start": 3,
                    "zone_end": 4, "recovery_bars": 1, "undercut_atr": 0.8}]
    monkeypatch.setattr(metrics, "_box_events_with_meta",
                        lambda *a, **k: (spring_only, 1, 12, True))
    nar = metrics.assemble_box_narrative(None, None, 0.5)
    assert nar["chronology"] == "partial" and nar["completeness"] == 1
    # V at the last base bar -> Phase-D span suppressed (no inverted [v+1, v] span).
    events = [{"type": "lps", "rail": "S", "anchor_bar": 7, "zone_start": 7,
               "zone_end": 7, "swing_type": "terminal_valley"}]
    monkeypatch.setattr(metrics, "_box_events_with_meta",
                        lambda *a, **k: (events, 7, 8, True))   # v_bar == base_n - 1
    nar2 = metrics.assemble_box_narrative(None, None, 0.5)
    assert nar2["phases"]["D"] is None and nar2["phases"]["B"] == [0, 7]


def test_e2_sentinel_three_state_injection(monkeypatch):
    # The elected-brick fix, pinned at the source: the spring/lps kwargs have THREE
    # states. Default _DETECT re-detects (the measure-only path, unchanged); an
    # injected brick is used VERBATIM (describes the LPS that actually fired, not a
    # re-detection); an injected None means "the engine elected no such piece" and
    # is honored (never fabricate one).
    import core.structure.bricks as bricks
    import core.structure.metrics as metrics
    from types import SimpleNamespace
    df = _ohlc(_CLEAN_BULL_H, _CLEAN_BULL_L)
    box = _box(0, len(_CLEAN_BULL_H))
    detected = SimpleNamespace(start_bar=8, end_bar=10, low_bar=9,
                               swing_type="terminal_valley")
    monkeypatch.setattr(bricks, "find_spring", lambda *a, **k: SimpleNamespace(
        tip_bar=1, recovery_bar=3, undercut_atr=0.9, recovery_bars=2))
    monkeypatch.setattr(bricks, "find_lps", lambda *a, **k: detected)

    def _lps(events):
        return [e for e in events if e["type"] == "lps"]

    # (1) default -> detect: the (monkeypatched) find_lps result is used.
    ev_detect = metrics.read_box_events(df, box, 0.5)
    assert len(_lps(ev_detect)) == 1 and _lps(ev_detect)[0]["anchor_bar"] == 9

    # (2) injected brick -> used verbatim (a DIFFERENT low_bar); find_lps ignored.
    injected = SimpleNamespace(start_bar=7, end_bar=9, low_bar=8,
                               swing_type="terminal_valley")
    ev_inject = metrics._box_events_with_meta(df, box, 0.5, lps=injected)[0]
    assert len(_lps(ev_inject)) == 1 and _lps(ev_inject)[0]["anchor_bar"] == 8

    # (3) injected None -> honored: NO lps event despite find_lps returning one.
    ev_none = metrics._box_events_with_meta(df, box, 0.5, lps=None)[0]
    assert _lps(ev_none) == []


def test_e2_upthrust_terminal_phase_d_range_clears_phase_b_range_does_not(monkeypatch):
    # F3: a held Phase-D "range" (anchor > v_bar) after the last upthrust clears the
    # terminal read (price recovered near R); a Phase-B "range" (left of the V, which
    # shares the type label) must NOT clear it. markup/in_progress keep no phase guard.
    import core.structure.metrics as metrics

    def _ut(b=4):
        return {"type": "upthrust", "rail": "R", "anchor_bar": b, "zone_start": b - 1}
    v_bar = 8
    cases = [
        ([_ut(), {"type": "range", "rail": "R", "anchor_bar": 9, "zone_start": 8}], False),   # Phase-D range -> clears
        ([_ut(), {"type": "range", "rail": "R", "anchor_bar": 6, "zone_start": 5}], True),    # Phase-B range -> does NOT clear
        ([_ut(), {"type": "markup", "rail": "R", "anchor_bar": 6, "zone_start": 5}], False),  # markup: no phase guard, still clears
    ]
    for events, expected in cases:
        monkeypatch.setattr(metrics, "_box_events_with_meta",
                            lambda *a, _e=events, **k: (_e, v_bar, 12, True))
        nar = metrics.assemble_box_narrative(None, None, 0.5)
        assert nar["upthrust_terminal"] is expected


def test_e2_injected_lps_gate_drop_is_observable(monkeypatch):
    # The elected LPS is never SILENTLY dropped: when an engine-elected LPS is
    # injected but the Phase-D gate emits no lps event (the rare late-V case),
    # lps_pre_v_dropped is True + a trace note fires. The default (detect) path,
    # which has no "elected" brick, never flags it.
    import core.structure.metrics as metrics
    from types import SimpleNamespace
    # Events with an SOS but NO lps event -> stands in for the gate having dropped it.
    events = [{"type": "SOS", "rail": "R", "anchor_bar": 6, "zone_start": 5,
               "peak_price": 12.4, "hold_range_box": 0.4}]
    monkeypatch.setattr(metrics, "_box_events_with_meta",
                        lambda *a, **k: (events, 8, 12, True))
    brick = SimpleNamespace(start_bar=2, end_bar=4, low_bar=3,
                            swing_type="terminal_valley")
    nar = metrics.assemble_box_narrative(None, None, 0.5, lps=brick)
    assert nar["lps_pre_v_dropped"] is True and nar["spine"]["lps"] is None
    assert any("Phase-D gate dropped" in ln for ln in nar["trace"])
    # Control: injected None (engine elected no LPS) is NOT a drop; nor is detect.
    nar_none = metrics.assemble_box_narrative(None, None, 0.5, lps=None)
    assert nar_none["lps_pre_v_dropped"] is False
    nar_detect = metrics.assemble_box_narrative(None, None, 0.5)
    assert nar_detect["lps_pre_v_dropped"] is False
