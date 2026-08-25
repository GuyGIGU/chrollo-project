"""Worked-band rail pool + deep-excursion events (Event Map Task 11) — guards.

The MECHANISM ships dark and structurally safe; the band-derivation rule is
still operator-calibration territory (see the flag ledger). These guards pin
the safety properties that must hold regardless of calibration:

1. flag-off, the band pool is never even CONSULTED (EC-8 inert);
2. flag-on, it is a LAST RESORT — a window with strict candidates never
   consults it, so an ordinary election can never move;
3. excursion qualification is strict: a span that never reclaims, is undercut
   after reclaim, or is still outside at the window edge disqualifies the read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
import engine_alpha.structure.box_primitives as bp
import engine_alpha.structure.rail_qualification as rq
from engine_alpha.structure.rail_qualification import (
    _merge_spans,
    _qualify_band,
    _spans,
    qualify_pair_events,
)


def _frame(closes, lo_off=0.4, hi_off=0.4):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "High": closes + hi_off,
        "Low": closes - lo_off,
        "Close": closes,
    })


def _boxy_closes(n=40, lo=100.0, hi=110.0):
    """A worked two-rail range: closes alternate through the band."""
    out = []
    for i in range(n):
        cyc = i % 8
        out.append(lo + (hi - lo) * (cyc / 4 if cyc <= 4 else (8 - cyc) / 4))
    return out


def test_band_pool_flag_off_is_inert(monkeypatch):
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", False)
    monkeypatch.setattr(bp, "_band_rail_candidates",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError(
                            "band pool consulted while the flag is off")))
    df = _frame(_boxy_closes())
    bp.collect_zigzag_candidates(df, atr_val=1.0,
                                 enforce_traversal=True)


def test_band_pool_is_last_resort_flag_on(monkeypatch):
    # A clean two-rail range yields strict zigzag candidates; the band pool
    # must never be consulted for it even flag-on.
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", True)
    monkeypatch.setattr(bp, "_band_rail_candidates",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError(
                            "band pool consulted although strict candidates exist")))
    df = _frame(_boxy_closes())
    got = bp.collect_zigzag_candidates(df, atr_val=1.0,
                                       enforce_traversal=True)
    assert got, "fixture must yield strict candidates for the guard to bite"


def test_qualify_band_reclaim_and_hold():
    # A below-band span that reclaims and holds qualifies and is excised.
    closes = np.array([105, 106, 104, 103, 96, 94, 95, 104, 105, 106,
                       104, 105, 103, 104, 105, 106, 104, 105, 103, 104,
                       105, 106, 104, 105, 103, 104, 105, 106, 104, 105],
                      dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    read = _qualify_band(closes, lows, highs, 102.0, 107.0, buf=1.0)
    assert read is not None
    assert [(e["kind"], e["start"], e["end"]) for e in read["excursions"]] == [("below", 4, 7)]
    assert not read["judged"][4:7].any() and read["judged"][7:].all()


def test_qualify_band_rejects_undercut_after_reclaim():
    # The shakeout low is undercut later: HOLD fails, the read dies.
    closes = np.array([105, 106, 104, 103, 96, 94, 95, 104, 105, 106,
                       104, 105, 103, 104, 105, 93, 104, 105, 103, 104,
                       105, 106, 104, 105, 103, 104, 105, 106, 104, 105],
                      dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    assert _qualify_band(closes, lows, highs, 102.0, 107.0, buf=1.0) is None


def test_qualify_band_rejects_unresolved_edge_excursion():
    # Still below the band at the window's right edge: unresolved, no read.
    closes = np.array([105, 106, 104, 103, 105, 104, 105, 104, 105, 106,
                       104, 105, 103, 104, 105, 106, 104, 105, 103, 104,
                       105, 106, 104, 105, 103, 104, 96, 94, 93, 92],
                      dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    assert _qualify_band(closes, lows, highs, 102.0, 107.0, buf=1.0) is None


def test_qualify_band_above_excursion_must_fail_back_and_hold():
    # An above-band poke that fails back qualifies; exceeding it later kills.
    base = _boxy_closes(32, 100, 106)
    poke = list(base)
    poke[10], poke[11] = 112.0, 113.0
    closes = np.array(poke, dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    read = _qualify_band(closes, lows, highs, 100.0, 106.0, buf=1.0)
    assert read is not None
    assert [e["kind"] for e in read["excursions"]] == ["above"]

    worse = list(poke)
    # Exceeds the poke high BEYOND the episode-merge gap: a separate, higher
    # break — the first poke's fail-back is violated and the read dies.
    worse[25] = 114.0
    closes = np.array(worse, dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    assert _qualify_band(closes, lows, highs, 100.0, 106.0, buf=1.0) is None


def test_qualify_band_above_departure_is_not_a_poke():
    # DBD negative-corpus regression (2026-07-16 flip): a multi-week stay above
    # R is a DEPARTURE — the range is not in force — never an event. Above the
    # rail the band pool grants no more patience than the respect gate's own
    # forgiveness horizon (MAX_CONSECUTIVE_OUTSIDE_DAYS); at the horizon it
    # still qualifies, one bar past it the pair dies.
    horizon = settings.MAX_CONSECUTIVE_OUTSIDE_DAYS

    def _with_above_run(run):
        vals = list(_boxy_closes(40, 100, 106))
        for i in range(10, 10 + run):
            vals[i] = 112.0
        closes = np.array(vals, dtype=float)
        return closes, closes - 0.5, closes + 0.5

    closes, lows, highs = _with_above_run(horizon)
    read = _qualify_band(closes, lows, highs, 100.0, 106.0, buf=1.0)
    assert read is not None and [e["kind"] for e in read["excursions"]] == ["above"]

    closes, lows, highs = _with_above_run(horizon + 1)
    assert _qualify_band(closes, lows, highs, 100.0, 106.0, buf=1.0) is None


# ── sequence-aware HOLD chain + depth cap (plan task 9; expected values
# transcribed from the operator's marks, not from the code) ────────────────

def _two_step_closes(second_low=92.0):
    """BODI's progressive two-step shape at synthetic scale: a first spring
    (extreme ~95.5), a long reclaim, then a SECOND deeper spring (extreme
    second_low - 0.5), reclaim, hold. The real chart measured 0.86 ATR then
    3.34 ATR at the operator's rails (probe 2026-07-16)."""
    return ([105.0, 106, 104, 105, 103, 104, 105, 106]        # worked range
            + [100.5, 100.5, 100.0]                           # spring 1 (shallow)
            + [104.0, 105, 103, 104, 105, 106, 104, 105, 103, 104, 105, 106]
            + [second_low, second_low]                        # spring 2 (deeper)
            + [104.0, 105, 103, 104, 105, 106, 104, 105, 103, 104, 105, 106])


def test_qualify_band_progressive_two_step_chain_qualifies():
    # The BODI ruling: successively deeper springs that each reclaim and hold
    # are ONE progressive Phase-C step-down, not a breakdown. The old
    # per-event HOLD refused this (spring 2 undercuts spring 1's extreme).
    closes = np.array(_two_step_closes(), dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    read = _qualify_band(closes, lows, highs, 102.0, 107.0, buf=1.0,
                         max_depth=12.0)
    assert read is not None
    below = [e for e in read["excursions"] if e["kind"] == "below"]
    assert len(below) == 2
    assert below[0]["extreme"] == 99.5 and below[1]["extreme"] == 91.5
    assert not read["judged"][8:11].any() and not read["judged"][23:25].any()


def test_qualify_band_chain_final_event_still_answers_unconditionally():
    # The forgiveness never reaches past the last event: a low under the
    # final extreme AFTER the chain is a breakdown, exactly as before.
    closes = _two_step_closes()
    closes[-3] = 90.0            # undercuts spring 2's 91.5 with no reclaim event
    arr = np.array(closes, dtype=float)
    lows, highs = arr - 0.5, arr + 0.5
    assert _qualify_band(arr, lows, highs, 102.0, 107.0, buf=1.0,
                         max_depth=12.0) is None


def test_qualify_band_interevent_bars_must_respect_the_standing_floor():
    # A non-event bar between the two springs digs under spring 1's extreme:
    # not a qualified event, no forgiveness — the pair dies.
    closes = _two_step_closes()
    arr = np.array(closes, dtype=float)
    lows, highs = arr - 0.5, arr + 0.5
    lows[15] = 99.0              # a non-event LOW wicks under spring 1's 99.5
    assert _qualify_band(arr, lows, highs, 102.0, 107.0, buf=1.0,
                         max_depth=12.0) is None


def test_qualify_band_depth_cap_refuses_the_egbn_overreach():
    # The EGBN flip-pause ruling: an excision digging 7.68-9.98 ATR below the
    # rail is a breakdown electing a stale box, never a terminal shakeout.
    # At atr=1: S - extreme = 102 - 91.5 = 10.5 ATR > cap -> refused; the
    # same shape passes at BODI scale (3.34 ATR < 5.0).
    closes = np.array(_two_step_closes(), dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    assert _qualify_band(closes, lows, highs, 102.0, 107.0, buf=1.0,
                         max_depth=settings.BAND_EVENT_MAX_DEPTH_ATR * 1.0) is None
    shallow = np.array(_two_step_closes(second_low=99.0), dtype=float)
    lows, highs = shallow - 0.5, shallow + 0.5
    read = _qualify_band(shallow, lows, highs, 102.0, 107.0, buf=1.0,
                         max_depth=settings.BAND_EVENT_MAX_DEPTH_ATR * 1.0)
    assert read is not None


def test_qualify_band_duration_cap_refuses_a_markdown_leg():
    # EGBN's stale April framing rode a 40-bar "event" — a two-month run
    # below the rail is a markdown leg, never a shakeout episode (BODI's
    # real episodes measured 12 and 18 bars). Pinned at the knob boundary.
    n_long = settings.BAND_EVENT_MAX_BARS + 1
    closes = np.array([105.0, 106, 104, 105, 103, 104, 105, 106]
                      + [96.0] * n_long
                      + [104.0, 105, 103, 104, 105, 106] * 4, dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    assert _qualify_band(closes, lows, highs, 102.0, 107.0, buf=1.0,
                         max_depth=12.0) is None
    ok = np.array([105.0, 106, 104, 105, 103, 104, 105, 106]
                  + [96.0] * settings.BAND_EVENT_MAX_BARS
                  + [104.0, 105, 103, 104, 105, 106] * 4, dtype=float)
    lows, highs = ok - 0.5, ok + 0.5
    assert _qualify_band(ok, lows, highs, 102.0, 107.0, buf=1.0,
                         max_depth=12.0) is not None


def test_qualify_pair_events_refuses_non_finite_or_zero_atr():
    # NaN masks silently report "no excursions" — the quarantine refuses
    # loudly instead, falling back to strict-path behavior.
    df = _frame(_two_step_closes())
    assert qualify_pair_events(df, 102.0, 107.0, float("nan")) is None
    assert qualify_pair_events(df, 102.0, 107.0, 0.0) is None
    assert qualify_pair_events(df, 102.0, 107.0, None) is None


def test_spans_finds_contiguous_runs():
    mask = np.array([False, True, True, False, True, False])
    assert _spans(mask) == [(1, 3), (4, 5)]


def test_merge_spans_joins_spring_then_test_episodes():
    # A deep episode is ONE event from first penetration to final reclaim:
    # spans separated by at most the merge gap join; farther ones stay apart.
    assert _merge_spans([(4, 7), (9, 12)], gap=3) == [(4, 12)]
    assert _merge_spans([(4, 7), (20, 22)], gap=3) == [(4, 7), (20, 22)]
    # The multi-dip case that motivated the merge: without it, the first dip's
    # HOLD is violated by the deeper second dip and the whole pair is refused.
    closes = np.array([105.0] * 8 + [96.0, 95.0] + [101.5, 101.0]
                      + [93.0, 92.0] + [104.0, 105.0] * 12)
    lows, highs = closes - 0.5, closes + 0.5
    read = _qualify_band(closes, lows, highs, 102.0, 107.0, buf=1.0)
    assert read is not None
    assert [(e["kind"], e["start"], e["end"]) for e in read["excursions"]] == [("below", 8, 14)]


def test_qualify_pair_events_requires_a_deep_multibar_event():
    # Ordinary springy pokes are the respect buffer's business: a pair with no
    # DEEP below-rail event is refused, so the class width allowance can never
    # leak to a merely-wide box. (Windows sized 60 to clear the matured-cause
    # floor — the refusals here must be about the EVENT, not maturity.)
    df = _frame(_boxy_closes(60))          # clean range, no excursion at all
    assert qualify_pair_events(df, 100.0, 110.0, 1.0) is None

    # One-bar poke below: too short for an event, refused.
    closes = _boxy_closes(60)
    closes[12] = 96.0
    assert qualify_pair_events(_frame(closes), 100.0, 110.0, 1.0) is None

    # A multi-bar DEEP episode (beyond S - 2*buf, within the terminal-shakeout
    # depth cap) that reclaims and holds: read. (The original 6.5-ATR-deep
    # fixture now correctly refuses under BAND_EVENT_MAX_DEPTH_ATR — that
    # magnitude is the EGBN breakdown class, pinned in its own test.)
    closes = _boxy_closes(60)
    closes[12], closes[13], closes[14] = 96.5, 96.0, 96.5
    read = qualify_pair_events(_frame(closes), 100.0, 110.0, 1.0)
    assert read is not None
    assert [e["kind"] for e in read["excursions"]] == ["below"]
    assert int(read["judged"].sum()) == 60 - 3


def test_qualify_pair_events_demands_a_matured_cause():
    # SPCB negative-corpus regression (2026-07-16 flip): a young high-flag's
    # churn scraped every gate on 30 judged bars. A terminal shakeout ends a
    # MATURED cause: judged bars must reach 2 x MIN_BASE_DAYS; one bar short
    # refuses the pair.
    floor = 2 * settings.MIN_BASE_DAYS

    def _with_event(n):
        closes = _boxy_closes(n)
        closes[12], closes[13], closes[14] = 96.5, 96.0, 96.5
        return _frame(closes)

    assert qualify_pair_events(_with_event(floor + 3), 100.0, 110.0, 1.0) is not None
    assert qualify_pair_events(_with_event(floor + 2), 100.0, 110.0, 1.0) is None


# ── Phase-C feed: TERMINAL_SHAKEOUT (flag-dark, Task 11 tail) ────────────


def _shakeout_frame():
    """A worked 90/100 range whose one excursion is a violent, later-reclaimed
    collapse: depth 7.4 (3.7 ATR at ATR=2) — beyond BOTH breakdown caps of the
    calibrated spring detector (3.0 ATR / 0.65 box), yet a clean qualified
    deep event (4 bars below the band, reclaim, hold). 60 bars (56 judged) so
    the matured-cause floor (2 x MIN_BASE_DAYS) is cleared; the collapse
    coordinates (bars 30-33, trough @31) are unchanged."""
    closes = []
    for i in range(30):                    # bars 0-29: closes oscillate 91..99
        cyc = i % 6
        closes.append(91 + 8 * (cyc / 3 if cyc <= 3 else (6 - cyc) / 3))
    closes += [87.0, 83.0, 84.5, 87.5]     # bars 30-33: the collapse (< S-buf=89)
    closes += [91.0, 92.0, 93.5, 94.0, 95.0, 95.5]  # bars 34-39: reclaim + hold
    for i in range(20):                    # bars 40-59: hold — oscillate 91..99
        cyc = i % 6
        closes.append(91 + 8 * (cyc / 3 if cyc <= 3 else (6 - cyc) / 3))
    df = _frame(closes)                    # lows = closes - 0.4 → trough 82.6 @31
    df["Volume"] = 1_000_000 + np.arange(len(closes)) * 1_000.0
    return df


def test_phase_c_feed_flag_off_never_consults_the_band_read(monkeypatch):
    import engine_alpha.structure.phase_features as bf
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", False)
    monkeypatch.setattr(bf, "_terminal_shakeout",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError(
                            "terminal-shakeout feed consulted while the flag is off")))
    df = _shakeout_frame()
    r = bf._phase_c_candidate(df, df, box_start=0, base_len=len(df),
                              R=100.0, S=90.0, atr_val=2.0)
    assert r["bin_c_present"] is False and r["bin_c_type"] is None


def test_phase_c_feed_types_the_terminal_shakeout(monkeypatch):
    # Hand-reasoned coordinates (EC-8 value pinning, no ranges): the collapse
    # troughs at bar 31 (low 82.6 → undercut 7.4 = 3.7 ATR), first close back
    # inside the band at bar 34.
    import engine_alpha.structure.phase_features as bf
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", True)
    df = _shakeout_frame()
    r = bf._phase_c_candidate(df, df, box_start=0, base_len=len(df),
                              R=100.0, S=90.0, atr_val=2.0)
    assert r["bin_c_present"] is True
    assert r["bin_c_type"] == "TERMINAL_SHAKEOUT"
    assert (r["bin_c_event_bar"], r["bin_c_recovery_bar"],
            r["bin_c_recovery_bars"]) == (31, 34, 3)
    assert r["bin_c_undercut_atr"] == 3.7
    assert r["bin_c_time_loc"] == round(31 / 59, 4)


def test_phase_c_feed_never_retypes_a_calibrated_spring(monkeypatch):
    # An in-caps spring is the ordinary detector's find; the fallback must be
    # unreachable — a calibrated SPRING can never come back re-typed.
    import engine_alpha.structure.phase_features as bf
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", True)
    monkeypatch.setattr(bf, "_terminal_shakeout",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError(
                            "fallback consulted although a calibrated spring exists")))
    closes = []
    for i in range(30):
        cyc = i % 6
        closes.append(91 + 8 * (cyc / 3 if cyc <= 3 else (6 - cyc) / 3))
    closes += [88.5, 88.8]                 # bars 30-31: in-caps undercut (low 88.1)
    closes += [92.0, 93.0, 94.0, 95.0, 95.5, 96.0]  # reclaim + hold
    df = _frame(closes)
    df["Volume"] = 1_000_000 + np.arange(len(closes)) * 1_000.0
    r = bf._phase_c_candidate(df, df, box_start=0, base_len=len(df),
                              R=100.0, S=90.0, atr_val=2.0)
    assert r["bin_c_present"] is True and r["bin_c_type"] == "SPRING"
    assert r["bin_c_event_bar"] == 30


# ---------------------------------------------------------------------------
# cluster_rails (Rail Program Task 6): the representative resting extreme.
# Measure-only statistic — these pin its promised routes so the dark-build
# consumer can never inherit a silently different definition.
# ---------------------------------------------------------------------------

def test_cluster_rails_quarantines_the_outlier_wick():
    # Ten bars resting near 100/90 plus ONE wick to 106: the plain extreme
    # anchor reads R=106; the cluster rail must ignore the unsupported wick
    # and sit at the resting cluster's top.
    highs = np.array([100.0, 99.8, 100.2, 99.9, 100.1, 106.0,
                      99.7, 100.0, 99.9, 100.1])
    lows = highs - 10.0
    R, S = rq.cluster_rails(highs, lows, atr_val=1.0)
    assert R == 100.2                      # top of the cluster, not the wick
    assert S == 89.7                       # mirrored: bottom of the low cluster
    # the low side has no outlier, so it equals the plain extreme
    assert S == float(np.min(lows))


def test_cluster_rails_needs_enough_resting_bars():
    # TWO bars sharing a wick level are still not "resting" at the default
    # EQ_MIN_TOUCHES_PER_RAIL=3: twin wicks stay quarantined.
    assert settings.EQ_MIN_TOUCHES_PER_RAIL == 3
    highs = np.array([100.0, 100.1, 99.9, 100.0, 106.0, 106.0])
    lows = highs - 10.0
    R, _S = rq.cluster_rails(highs, lows, atr_val=1.0)
    assert R == 100.1
    # ...but with min_rest=2 the twin wicks qualify (the knob is explicit)
    R2, _ = rq.cluster_rails(highs, lows, atr_val=1.0, min_rest=2)
    assert R2 == 106.0


def test_cluster_rails_pinned_routes():
    highs = np.array([100.0, 100.1, 99.9, 100.0])
    lows = highs - 10.0
    # non-finite / non-positive ATR -> no cluster rail, loudly None
    assert rq.cluster_rails(highs, lows, atr_val=np.nan) == (None, None)
    assert rq.cluster_rails(highs, lows, atr_val=0.0) == (None, None)
    assert rq.cluster_rails(highs, lows, atr_val=None) == (None, None)
    # NaN extremes are excluded: never a candidate level, never support
    h_nan = np.array([100.0, np.nan, 100.1, 99.9, np.nan, 100.0])
    R, S = rq.cluster_rails(h_nan, h_nan - 10.0, atr_val=1.0)
    assert R == 100.1 and S == 89.9
    # fewer finite extremes than min_rest -> None (never a fabricated level)
    tiny = np.array([100.0, np.nan])
    assert rq.cluster_rails(tiny, tiny - 10.0, atr_val=1.0) == (None, None)


def test_cluster_rails_is_suffix_consistent():
    # The pure form is the parity oracle for the dark build's suffix
    # precompute: recomputing on any suffix must equal slicing the inputs.
    rng = np.random.default_rng(7)
    highs = 100.0 + rng.normal(0.0, 0.6, size=40)
    highs[5] = 108.0                       # one outlier wick
    lows = highs - 8.0
    for start in (0, 3, 11, 25):
        R_full, S_full = rq.cluster_rails(highs[start:], lows[start:], atr_val=1.0)
        R_again, S_again = rq.cluster_rails(np.array(highs[start:]),
                                            np.array(lows[start:]), atr_val=1.0)
        assert R_full == R_again and S_full == S_again
