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
import core.structure.box_primitives as bp
from core.structure.band_rails import _qualify_band, _spans, derive_band_candidates


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
    worse[20] = 114.0                       # exceeds the poke high later
    closes = np.array(worse, dtype=float)
    lows, highs = closes - 0.5, closes + 0.5
    assert _qualify_band(closes, lows, highs, 100.0, 106.0, buf=1.0) is None


def test_spans_finds_contiguous_runs():
    mask = np.array([False, True, True, False, True, False])
    assert _spans(mask) == [(1, 3), (4, 5)]


def test_derive_band_candidates_empty_on_short_window():
    df = _frame(_boxy_closes(5))
    assert derive_band_candidates(df, 1.0) == []
