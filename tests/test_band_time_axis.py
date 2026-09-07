"""Band-rail boxes are judged on the REAL time axis, not the compacted one.

Council review 2026-09-07, finding 6. ``_band_rail_candidates`` excises the
qualified excursion spans and hands ``_build_candidate`` the COMPACTED arrays.
Two of the gates that then run are adjacency statistics, not set statistics:

* the respect RUN cap — "N consecutive trading days outside the buffered
  rails" (the DEPARTURE defence: the range is not in force);
* the touch THIRDS spread — "touches spread across the window, not clustered".

On a compacted axis both read a number that does not correspond to real
trading days: bars either side of an excised excursion are array-neighbours
but weeks apart on the chart. These guards pin the corrected read, and pin
that every SET statistic (respect share, touch counts, dwell, coverage) and
every non-band caller stays exactly where it was.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings                                       # noqa: E402
import engine_alpha.structure.box_primitives as bp                # noqa: E402
from engine_alpha.structure.box_gates import _respect_stats       # noqa: E402
from engine_alpha.structure.metrics import _rail_touch_thirds     # noqa: E402

R_VAL, S_VAL, ATR = 110.0, 100.0, 1.0


# --- the adjacency statistics, measured directly ----------------------------

def _wick_below(n, outside_bars):
    """A window inside the rails, except ``outside_bars`` whose LOW pierces
    S - buffer (bar-basis: the respect gate's own geometry)."""
    highs = np.full(n, 105.0)
    lows = np.full(n, 104.0)
    lows[list(outside_bars)] = 99.0        # < S - 0.5*ATR
    return highs, lows


def test_respect_run_counts_real_trading_days_not_array_neighbours():
    # Two 6-bar outside runs with a 5-bar excursion excised between them.
    n = 100
    run_a, gap, run_b = range(10, 16), range(16, 21), range(21, 27)
    highs, lows = _wick_below(n, list(run_a) + list(run_b))
    judged = np.ones(n, dtype=bool)
    judged[list(gap)] = False

    compacted = _respect_stats(highs[judged], lows[judged], R_VAL, S_VAL, ATR)
    on_axis = _respect_stats(highs[judged], lows[judged], R_VAL, S_VAL, ATR,
                             judged_mask=judged)

    assert compacted[5] == 12, "the compacted axis welds the two runs together"
    assert on_axis[5] == 6, (
        "the excursion between them is five real trading days — the run cap "
        "must see two runs of six, not one of twelve")
    # the SET statistics are untouched by the axis
    assert compacted[3] == on_axis[3] == 12          # total outside bars
    assert compacted[4] == on_axis[4]                # respect share


def test_respect_run_verdict_flips_where_the_cap_is_the_only_difference():
    """The number is not cosmetic: it decides the DEPARTURE verdict."""
    n = 100
    cap = settings.MAX_CONSECUTIVE_OUTSIDE_DAYS      # 10
    run_a = range(10, 10 + 6)
    gap = range(16, 21)
    run_b = range(21, 21 + 6)
    highs, lows = _wick_below(n, list(run_a) + list(run_b))
    judged = np.ones(n, dtype=bool)
    judged[list(gap)] = False

    compacted = _respect_stats(highs[judged], lows[judged], R_VAL, S_VAL, ATR)
    on_axis = _respect_stats(highs[judged], lows[judged], R_VAL, S_VAL, ATR,
                             judged_mask=judged)
    assert compacted[5] > cap and on_axis[5] <= cap
    assert compacted[0] is False or not compacted[0]
    assert on_axis[0], "a framing refused only by the compacted run must pass"


def test_touch_thirds_are_cut_on_the_original_window():
    """Excising the window's middle shifts the compacted thirds boundaries, so
    touches confined to the real FIRST third can read as two thirds."""
    n = 30
    highs = np.full(n, 105.0)
    lows = np.full(n, 104.0)
    highs[[2, 5, 8]] = R_VAL          # every R touch inside the real 1st third
    judged = np.ones(n, dtype=bool)
    judged[10:28] = False             # excise most of the rest

    _r, _s, compacted_thirds, _st = _rail_touch_thirds(
        highs[judged], lows[judged], R_VAL, S_VAL, ATR)
    _r2, _s2, axis_thirds, _st2 = _rail_touch_thirds(
        highs[judged], lows[judged], R_VAL, S_VAL, ATR, judged_mask=judged)

    assert compacted_thirds == 3, "the compacted axis spreads a clustered read"
    assert axis_thirds == 1, (
        "all three touches sit in the window's real first third — the "
        "anti-clustering leg must say one third")
    # and the verdict follows the number: the compacted read PASSES the
    # anti-clustering floor on a framing whose touches never left one third.
    assert compacted_thirds >= settings.EQ_MIN_TOUCH_THIRDS
    assert axis_thirds < settings.EQ_MIN_TOUCH_THIRDS


def test_touch_counts_are_set_statistics_and_do_not_move():
    n = 30
    highs = np.full(n, 105.0)
    lows = np.full(n, 104.0)
    highs[[2, 5, 8]] = R_VAL
    lows[[3, 6, 9]] = S_VAL
    judged = np.ones(n, dtype=bool)
    judged[10:28] = False

    a = _rail_touch_thirds(highs[judged], lows[judged], R_VAL, S_VAL, ATR)
    b = _rail_touch_thirds(highs[judged], lows[judged], R_VAL, S_VAL, ATR,
                           judged_mask=judged)
    assert int(a[0].sum()) == int(b[0].sum()) == 3
    assert int(a[1].sum()) == int(b[1].sum()) == 3


def test_contiguous_window_reads_identically_with_or_without_the_axis():
    """Every non-band caller passes no mask; an all-True mask is the same
    window. Neither may move from the pre-2026-09-07 read."""
    n = 36
    highs, lows = _wick_below(n, [4, 5, 6, 20, 21])
    highs[[2, 12, 30]] = R_VAL
    lows[[3, 13, 31]] = S_VAL
    full = np.ones(n, dtype=bool)

    assert _respect_stats(highs, lows, R_VAL, S_VAL, ATR) == \
        _respect_stats(highs, lows, R_VAL, S_VAL, ATR, judged_mask=full)
    plain = _rail_touch_thirds(highs, lows, R_VAL, S_VAL, ATR)
    masked = _rail_touch_thirds(highs, lows, R_VAL, S_VAL, ATR, judged_mask=full)
    assert plain[2:] == masked[2:]
    assert np.array_equal(plain[0], masked[0])
    assert np.array_equal(plain[1], masked[1])


# --- the live band pool: the mask must actually be THREADED ------------------

_CYCLE = [100.2, 102.0, 104.0, 106.0, 108.0, 109.8, 108.0, 106.0, 104.0, 102.0]


def _band_frame():
    """A worked 100/110 range carrying ONE qualified deep below-rail event,
    flanked by two wick-only outside runs.

    Closes never leave the buffered band except across the event, so the
    excursion qualifier excises exactly bars 37-40. The flanking runs pierce
    S - buffer with their LOWS only — outside days for the bar-basis respect
    gate, judged bars for the excursion reader. 7 + 6 = 13 outside bars, which
    the share leg allows over 76 judged bars; welded by compaction they are a
    13-day run against a cap of 10, and on the real axis two runs of 7 and 6.
    """
    n = 80
    closes = np.array([_CYCLE[i % 10] for i in range(n)], dtype=float)
    highs = closes + 0.3
    lows = closes - 0.3
    for i in list(range(30, 37)) + list(range(41, 47)):
        lows[i] = 99.2                        # wick outside, close inside
    for i in range(37, 41):                   # the qualified deep event
        closes[i] = 98.0
        highs[i] = 98.3
        lows[i] = 97.0
    return pd.DataFrame({"High": highs, "Low": lows, "Close": closes,
                         "Open": closes})


_ZIGZAG = [(0, "valley", S_VAL), (5, "peak", R_VAL)]


def _run_band_pool(df):
    return bp._band_rail_candidates(
        df, df["High"].to_numpy(dtype=float), df["Low"].to_numpy(dtype=float),
        _ZIGZAG, ATR)


def test_the_fixture_really_excises_one_deep_event():
    """Guard the guard: if the qualifier stops excising, the pool test below
    would pass for the wrong reason."""
    from engine_alpha.structure.rail_qualification import qualify_pair_events
    read = qualify_pair_events(_band_frame(), S_VAL, R_VAL, ATR)
    assert read is not None
    assert [(e["start"], e["end"]) for e in read["excursions"]] == [(37, 41)]
    assert int(read["judged"].sum()) == 76


def test_band_pool_admits_a_framing_whose_outside_runs_only_touch_after_excision():
    pool = _run_band_pool(_band_frame())
    assert len(pool) == 1, (
        "the two wick runs are 7 and 6 real trading days with a four-day "
        "excursion between them; only the compacted axis reads a 13-day "
        "departure and refuses the framing")
    assert pool[0].pool == "band"
    assert pool[0].judged_len == 76


def test_band_pool_threads_the_excision_mask_into_both_adjacency_gates():
    """The axis is only honest if it reaches BOTH gates — a fix that threads
    the respect run and forgets the touch thirds is half a fix."""
    seen = {"respect": [], "thirds": []}
    real_respect = bp._respect_stats
    import engine_alpha.structure.box_gates as bg
    real_thirds = bg._rail_touch_thirds

    def spy_respect(*a, **kw):
        seen["respect"].append(kw.get("judged_mask"))
        return real_respect(*a, **kw)

    def spy_thirds(*a, **kw):
        seen["thirds"].append(kw.get("judged_mask"))
        return real_thirds(*a, **kw)

    bp._respect_stats = spy_respect
    bg._rail_touch_thirds = spy_thirds
    try:
        _run_band_pool(_band_frame())
    finally:
        bp._respect_stats = real_respect
        bg._rail_touch_thirds = real_thirds

    assert seen["respect"], "the respect gate was never consulted"
    assert seen["thirds"], (
        "the occupancy gate was never reached — the respect leg refused the "
        "framing first, which is what a compacted run cap does here")
    for leg in ("respect", "thirds"):
        for mask in seen[leg]:
            assert mask is not None, f"the {leg} gate judged a compacted axis"
            assert len(mask) == 80 and int(mask.sum()) == 76


# --- the measure-only mirror must mirror the corrected gate -----------------

def test_margin_mirror_reads_the_same_run_as_the_band_gate():
    """``gate_margins`` exists to reproduce the gate's verdict on the same
    window; without the axis it would report a leg the gate never measured."""
    from engine_alpha.structure.gate_margins import complete_leg_vector
    from engine_alpha.structure.rail_qualification import qualify_pair_events

    df = _band_frame()
    read = qualify_pair_events(df, S_VAL, R_VAL, ATR)
    mask = read["judged"]
    window = df[mask]
    gate_run = _respect_stats(window["High"].to_numpy(dtype=float),
                              window["Low"].to_numpy(dtype=float),
                              R_VAL, S_VAL, ATR, judged_mask=mask)[5]

    mirrored = complete_leg_vector(window, R_VAL, S_VAL, ATR,
                                   width_max=settings.BAND_MAX_BOX_WIDTH,
                                   judged_mask=mask)
    assert mirrored["respect_run"]["measured"] == gate_run == 7

    drifting = complete_leg_vector(window, R_VAL, S_VAL, ATR,
                                   width_max=settings.BAND_MAX_BOX_WIDTH)
    assert drifting["respect_run"]["measured"] != gate_run, (
        "without the axis the mirror reports a different leg than the gate "
        "judged — the drift this module raises on")


def test_the_near_miss_completion_threads_the_axis_for_band_refusals():
    import engine_alpha.structure.near_miss as nm

    df = _band_frame()
    rec = nm.NearMissRecorder()
    rec.begin_consultation(0, frame=df, atr=ATR)
    rec.refusal("occupancy", "band", 5, 0, 0, R_VAL, S_VAL, 76)

    seen = []
    real = nm.complete_leg_vector

    def spy(*a, **kw):
        seen.append(kw.get("judged_mask"))
        return real(*a, **kw)

    nm.complete_leg_vector = spy
    try:
        nm.deferred_rows(rec, fired=False, scan_close=105.0)
    finally:
        nm.complete_leg_vector = real

    assert len(seen) == 1, f"the band refusal was not completed ({seen})"
    assert seen[0] is not None and int(seen[0].sum()) == 76, (
        "the deferred completion rebuilt the masked window but judged its "
        "adjacency legs on the compacted axis")
