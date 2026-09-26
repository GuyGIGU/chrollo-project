"""The trend-terminal FLOOR — ``market_structure.trend_terminal_floor``.

Migrated verbatim 2026-09-08 from ``tests/test_trend_terminal_gate.py`` when the
operator ruled ``TREND_TERMINAL_BOX_GATE_ENABLED`` DELETED. The GATE retired; the
floor did NOT. It is unconditionally live feeding Phase A's climax polarity
(``bricks._cause_is_up``, the 2026-08-19 re-key off ``root.kind``), so these
guards had to migrate rather than retire with the flag — the flag ledger's own
instruction, and the reason this file exists rather than a deletion.

One test did NOT migrate: ``test_the_real_election_never_opens_before_its_root``
asserted the gate's offset arithmetic through ``validate_equilibrium(...,
terminal_floor=...)``, a parameter that no longer exists.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine_alpha.structure.events.market_structure import trend_terminal_floor


def _ohlc_from_closes(closes, *, band=1.0, volume=1000.0):
    return pd.DataFrame({
        "Open": list(closes),
        "High": [c + band for c in closes],
        "Low": [c - band for c in closes],
        "Close": list(closes),
        "Volume": [volume] * len(closes),
    })


def _worked_frame():
    """A one-way leg crashing into a genuinely worked 100/110 range.

    The same construction test_bricks uses for the pair cascade: the election
    returns a box at df bar 6, and a SECOND valid framing exists at df bar 10 —
    which is what lets the back-extension pin below say something real.
    """
    crash = [120, 118, 140, 120, 110, 104]
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    return _ohlc_from_closes(crash + worked)


def _seg(*, start_bar, end_bar, terminal_bar, terminal_price=100.0, direction=1):
    return {
        "start_bar": start_bar, "end_bar": end_bar,
        "terminal_bar": terminal_bar, "terminal_price": terminal_price,
        "direction": direction,
    }


def test_floor_of_an_empty_or_missing_frame_is_empty():
    for df in (None, pd.DataFrame({"High": [], "Low": [], "Close": []})):
        floor = trend_terminal_floor(df)
        assert len(floor.bar) == 0
        assert len(floor.price) == 0 and len(floor.direction) == 0


def test_no_confirmed_segment_leaves_every_bar_uncovered():
    df = _worked_frame()
    floor = trend_terminal_floor(df, segments=[])

    assert np.array_equal(floor.bar, np.full(len(df), -1))


def test_a_still_running_segment_never_vetoes():
    # A trend with no CHoCH has not proven it topped; its "terminal" is only the
    # highest high so far. Vetoing on it cost a pinned Guided-List hit (VIK).
    # The worked frame's OWN segmentation is exactly this case, so assert both
    # the injected form and the real read.
    df = _worked_frame()
    running = trend_terminal_floor(df, segments=[
        _seg(start_bar=0, end_bar=None, terminal_bar=len(df) - 1)])

    assert np.array_equal(running.bar, np.full(len(df), -1))
    assert np.array_equal(trend_terminal_floor(df).bar, np.full(len(df), -1))


def test_the_cause_trend_owns_the_shared_handover_bar():
    # Segments overlap by one leg: an uptrend runs to its CHoCH, which IS the
    # next downtrend's start. First write wins, so the EARLIER (cause) trend owns
    # bar 30 — letting the later one win vetoes a base at the very top where it
    # belongs (measured 2026-07-27: 6 pinned Guided-List hits broke).
    df = _ohlc_from_closes([100.0] * 60)
    floor = trend_terminal_floor(df, segments=[
        _seg(start_bar=0, end_bar=30, terminal_bar=25, direction=1),
        _seg(start_bar=30, end_bar=50, terminal_bar=45, direction=-1),
    ])

    assert floor.bar[29] == 25
    assert floor.bar[30] == 25               # handover bar: the CAUSE trend's
    assert floor.bar[31] == 45
    assert floor.direction[30] == 1
    assert floor.bar[51] == -1               # past both segments: uncovered


def test_degenerate_and_out_of_frame_windows_are_skipped():
    df = _ohlc_from_closes([100.0] * 40)
    floor = trend_terminal_floor(df, segments=[
        _seg(start_bar=20, end_bar=10, terminal_bar=15),        # inverted
        _seg(start_bar=100, end_bar=200, terminal_bar=150),     # past the frame
        _seg(start_bar=-5, end_bar=5, terminal_bar=3),          # clipped at 0
    ])

    assert np.array_equal(floor.bar[:6], np.full(6, 3))
    assert np.array_equal(floor.bar[6:], np.full(34, -1))


def test_the_floor_reports_the_segments_terminal_verbatim():
    # Half (a) of the box-blind defect (decisions.md 2026-08-14): where the
    # operator's trend end is not in the pivot set, `segment_trends` hands over a
    # terminal drawn from a later in-base upthrust instead. The floor does NOT
    # re-read price to sanity-check it — it copies the reported bar — so the
    # gate is only ever as good as the pivot set it is handed. Pinned so the
    # limitation is visible in the suite rather than only in the ledger.
    df = _ohlc_from_closes([100.0] * 60)
    df.loc[10, "High"] = 500.0               # the obvious extreme, NOT the terminal
    floor = trend_terminal_floor(df, segments=[
        _seg(start_bar=0, end_bar=40, terminal_bar=35, terminal_price=101.0)])

    assert floor.bar[0] == 35
    assert float(floor.price[0]) == 101.0
