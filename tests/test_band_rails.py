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
from engine_alpha.structure.band_rails import (
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
    bp.collect_zigzag_candidates(df, base_length=len(df), atr_val=1.0,
                                 enforce_traversal=True)


def test_band_pool_is_last_resort_flag_on(monkeypatch):
    # A clean two-rail range yields strict zigzag candidates; the band pool
    # must never be consulted for it even flag-on.
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", True)
    monkeypatch.setattr(bp, "_band_rail_candidates",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError(
                            "band pool consulted although strict candidates exist")))
    df = _frame(_boxy_closes())
    got = bp.collect_zigzag_candidates(df, base_length=len(df), atr_val=1.0,
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
    # leak to a merely-wide box.
    df = _frame(_boxy_closes(40))          # clean range, no excursion at all
    assert qualify_pair_events(df, 100.0, 110.0, 1.0) is None

    # One-bar poke below: too short for an event, refused.
    closes = _boxy_closes(40)
    closes[12] = 96.0
    assert qualify_pair_events(_frame(closes), 100.0, 110.0, 1.0) is None

    # A multi-bar DEEP episode (beyond S - 2*buf) that reclaims and holds: read.
    closes = _boxy_closes(40)
    closes[12], closes[13], closes[14] = 96.0, 94.0, 95.0
    read = qualify_pair_events(_frame(closes), 100.0, 110.0, 1.0)
    assert read is not None
    assert [e["kind"] for e in read["excursions"]] == ["below"]
    assert int(read["judged"].sum()) == 40 - 3


# ── Phase-C feed: TERMINAL_SHAKEOUT (flag-dark, Task 11 tail) ────────────


def _shakeout_frame():
    """A worked 90/100 range whose one excursion is a violent, later-reclaimed
    collapse: depth 7.4 (3.7 ATR at ATR=2) — beyond BOTH breakdown caps of the
    calibrated spring detector (3.0 ATR / 0.65 box), yet a clean qualified
    deep event (4 bars below the band, reclaim, hold)."""
    closes = []
    for i in range(30):                    # bars 0-29: closes oscillate 91..99
        cyc = i % 6
        closes.append(91 + 8 * (cyc / 3 if cyc <= 3 else (6 - cyc) / 3))
    closes += [87.0, 83.0, 84.5, 87.5]     # bars 30-33: the collapse (< S-buf=89)
    closes += [91.0, 92.0, 93.5, 94.0, 95.0, 95.5]  # bars 34-39: reclaim + hold
    df = _frame(closes)                    # lows = closes - 0.4 → trough 82.6 @31
    df["Volume"] = 1_000_000 + np.arange(len(closes)) * 1_000.0
    return df


def test_phase_c_feed_flag_off_never_consults_the_band_read(monkeypatch):
    import engine_alpha.structure.bin_features as bf
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
    import engine_alpha.structure.bin_features as bf
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", True)
    df = _shakeout_frame()
    r = bf._phase_c_candidate(df, df, box_start=0, base_len=len(df),
                              R=100.0, S=90.0, atr_val=2.0)
    assert r["bin_c_present"] is True
    assert r["bin_c_type"] == "TERMINAL_SHAKEOUT"
    assert (r["bin_c_event_bar"], r["bin_c_recovery_bar"],
            r["bin_c_recovery_bars"]) == (31, 34, 3)
    assert r["bin_c_undercut_atr"] == 3.7
    assert r["bin_c_time_loc"] == round(31 / 39, 4)


def test_phase_c_feed_never_retypes_a_calibrated_spring(monkeypatch):
    # An in-caps spring is the ordinary detector's find; the fallback must be
    # unreachable — a calibrated SPRING can never come back re-typed.
    import engine_alpha.structure.bin_features as bf
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
