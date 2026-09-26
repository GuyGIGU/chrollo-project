"""What axis the band pool's two ADJACENCY gates are judged on, and why.

Council review 2026-09-07, finding 6, plus the review of its first fix.
``_band_rail_candidates`` excises the qualified excursion spans and hands
``_build_candidate`` the COMPACTED arrays. Two of the gates that then run are
adjacency statistics, not set statistics:

* the touch THIRDS spread — "touches spread across the window, not clustered";
* the respect RUN cap — "N consecutive trading days outside the buffered
  rails" (the DEPARTURE defence: the range is not in force).

**The thirds are cut on the ORIGINAL span.** On the compacted array bars weeks
apart become neighbours and the boundaries stop falling on the window's own
calendar thirds, so touches confined to the real first third can read as two.
An excised bar there is simply no touch, which is true, so the mask rides into
``_rail_touch_thirds`` and the excised positions are empty.

**The run stays on the COMPACTED array — deliberately.** An excised bar was
outside a rail, so it can be read three ways, and all three were measured on
the fixture below (17 real outside days against a cap of 10):

* fill the excised positions "inside" — reads **7** and ADMITS the framing.
  This is the permissive error the finding was raised to prevent. Shipped in
  ceb0a27, removed the same day.
* count the original window bar by bar so the event's days charge the cap —
  reads **17** and refuses; but a qualified event may legally run 20 bars
  against a cap of 10, so it deletes the class outright (BODI's own framing
  goes from a run of 2 to 19 and stops firing).
* the KEPT read: the gate counts the outside days it owns and runs straight
  across event time — the excursion neither breaks the run (price did not come
  back inside, it went further out) nor charges its own days to a cap half
  their legal length. Reads **13** and refuses.

These guards pin all three numbers, pin that every SET statistic (respect
share, touch counts, dwell, coverage) is untouched, and pin that every non-band
caller stays exactly where it was.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings                                           # noqa: E402
import engine_alpha.structure.box.box_primitives as bp                # noqa: E402
from engine_alpha.structure.box.box_gates import _respect_stats       # noqa: E402
from engine_alpha.structure.metrics.base import _rail_touch_thirds    # noqa: E402

R_VAL, S_VAL, ATR = 110.0, 100.0, 1.0


# --- the adjacency statistics, measured directly ----------------------------

def _wick_below(n, outside_bars):
    """A window inside the rails, except ``outside_bars`` whose LOW pierces
    S - buffer (bar-basis: the respect gate's own geometry)."""
    highs = np.full(n, 105.0)
    lows = np.full(n, 104.0)
    lows[list(outside_bars)] = 99.0        # < S - 0.5*ATR
    return highs, lows


def _max_run(mask):
    """Longest True run — the run cap's own arithmetic, spelled out here so a
    test can measure a mask the gate is no longer asked to produce."""
    d = np.diff(np.concatenate(([False], mask, [False])).astype(int))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return int((ends - starts).max()) if len(starts) else 0


def _outside_mask(lows):
    """The respect gate's own below-S classification, spelled out so a test can
    measure a mask the gate is not asked to produce."""
    return lows < S_VAL - settings.BOUNDARY_ATR_BUFFER * ATR


def test_an_excursion_neither_breaks_a_departure_run_nor_charges_its_own_days():
    """The run cap's reading, and the two that were measured and rejected.

    Seventeen consecutive days below the rail, five of them lifted out as a
    qualified excursion. The gate must not read that as a series of short
    pokes, and must not read it as seventeen either — the excursion's own days
    answer to the event rules, which permit twice this cap.
    """
    n = 100
    highs, lows = _wick_below(n, list(range(10, 27)))
    judged = np.ones(n, dtype=bool)
    judged[16:21] = False                        # the excursion, excised

    gate = _respect_stats(highs[judged], lows[judged], R_VAL, S_VAL, ATR)
    severed = np.zeros(n, dtype=bool)            # fill the holes "inside"
    severed[judged] = _outside_mask(lows[judged])
    charged = _outside_mask(lows)                # charge the event's own days

    assert gate[5] == 12, (
        "the twelve outside days the gate owns are ONE departure — price never "
        "came back inside between them, it went further out")
    assert not gate[0], "a twelve-day departure is over the cap: refuse"
    assert _max_run(severed) == 6, (
        "the counterfeit-inside read: it forgives the excursion into a return "
        "and admits the framing — the permissive error, kept out here")
    assert _max_run(charged) == 17               # the class-deleting read


def test_a_qualified_event_longer_than_the_cap_never_refuses_on_its_own():
    """Why the event's days are not charged to this cap: a qualified excursion
    may legally run ``BAND_EVENT_MAX_BARS`` — twice the departure cap — so
    counting them deletes the deep-event class instead of defending it (BODI's
    own framing, 76 bars with 30 excised, reads a run of 2 here and 19 there).
    """
    cap = settings.MAX_CONSECUTIVE_OUTSIDE_DAYS
    event = settings.BAND_EVENT_MAX_BARS
    assert event > cap, "the premise of this guard moved — re-measure BODI"

    n = 100
    highs, lows = _wick_below(n, list(range(30, 30 + event)))
    judged = np.ones(n, dtype=bool)
    judged[30:30 + event] = False                # the whole event, excised

    gate = _respect_stats(highs[judged], lows[judged], R_VAL, S_VAL, ATR)
    assert gate[5] == 0 and gate[0], (
        "an excised qualified event is the EVENT's business — charging its "
        "days to the departure cap refuses every framing the pool exists for")
    assert _max_run(_outside_mask(lows)) > cap   # what charging them would read


def test_the_run_is_the_departure_verdict_not_a_cosmetic_number():
    """Two short pokes with genuinely inside days between them stay two pokes;
    the same bars welded into one run would refuse the framing."""
    cap = settings.MAX_CONSECUTIVE_OUTSIDE_DAYS      # 10
    n = 100
    highs, lows = _wick_below(n, list(range(10, 16)) + list(range(21, 27)))

    gate = _respect_stats(highs, lows, R_VAL, S_VAL, ATR)
    assert gate[5] == 6 <= cap and gate[0], (
        "five inside days separate them — that is two pokes, not a departure")
    assert gate[3] == 12                             # the SET count is the sum


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

    plain = _rail_touch_thirds(highs, lows, R_VAL, S_VAL, ATR)
    masked = _rail_touch_thirds(highs, lows, R_VAL, S_VAL, ATR, judged_mask=full)
    assert plain[2:] == masked[2:]
    assert np.array_equal(plain[0], masked[0])
    assert np.array_equal(plain[1], masked[1])


# --- the live band pool: the mask must actually be THREADED ------------------

_CYCLE = [100.2, 102.0, 104.0, 106.0, 108.0, 109.8, 108.0, 106.0, 104.0, 102.0]


def _band_frame(departure=True):
    """A worked 100/110 range carrying ONE qualified deep below-rail event.

    Closes never leave the buffered band except across the event, so the
    excursion qualifier excises exactly bars 37-40 either way.

    ``departure=True`` flanks the event with wick-only outside runs (bars
    30-36 and 41-46: lows pierce S - buffer, closes stay inside — outside days
    for the bar-basis respect gate, judged bars for the excursion reader).
    Bars 30 THROUGH 46 are then SEVENTEEN consecutive trading days below the
    rail: the range is not in force and the cap of 10 must refuse the framing.
    The gate owns 13 of those days and reads 13 — refused. Scattering the
    judged verdicts back with the excised positions filled "inside" reads 7 and
    ADMITS it, which is the read this fixture exists to keep out.

    ``departure=False`` is the same range with the flanks quiet — the only
    outside days are the four event bars, so the respect gate passes and the
    cascade reaches the occupancy leg.
    """
    n = 80
    closes = np.array([_CYCLE[i % 10] for i in range(n)], dtype=float)
    highs = closes + 0.3
    lows = closes - 0.3
    if departure:
        for i in list(range(30, 37)) + list(range(41, 47)):
            lows[i] = 99.2                    # wick outside, close inside
    for i in range(37, 41):                   # the qualified deep event
        closes[i] = 98.0
        highs[i] = 98.3
        lows[i] = 97.0
    return pd.DataFrame({"High": highs, "Low": lows, "Close": closes,
                         "Open": closes})


_ZIGZAG = [(0, "valley", S_VAL), (5, "peak", R_VAL)]


def _run_band_pool(df, trace=None):
    return bp._band_rail_candidates(
        df, df["High"].to_numpy(dtype=float), df["Low"].to_numpy(dtype=float),
        _ZIGZAG, ATR, trace=trace)


def test_the_fixture_really_excises_one_deep_event():
    """Guard the guard: if the qualifier stops excising, the pool tests below
    would pass for the wrong reason."""
    from engine_alpha.structure.box.rail_qualification import qualify_pair_events
    for departure in (True, False):
        read = qualify_pair_events(_band_frame(departure), S_VAL, R_VAL, ATR)
        assert read is not None
        assert [(e["start"], e["end"]) for e in read["excursions"]] == [(37, 41)]
        assert int(read["judged"].sum()) == 76


def test_band_pool_refuses_a_framing_whose_departure_exceeds_the_cap():
    """Bars 30-46 are one unbroken seventeen-day stay below the rail. The gate
    owns 13 of them and refuses. Only the counterfeit-inside read — which
    forgives the excursion into a return and reads 7 — lets this through."""
    df = _band_frame()
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    from engine_alpha.structure.box.rail_qualification import qualify_pair_events
    mask = qualify_pair_events(df, S_VAL, R_VAL, ATR)["judged"]

    measured = _respect_stats(highs[mask], lows[mask], R_VAL, S_VAL, ATR)
    assert measured[5] == 13 > settings.MAX_CONSECUTIVE_OUTSIDE_DAYS
    severed = np.zeros(len(mask), dtype=bool)
    severed[mask] = _outside_mask(lows[mask])
    assert _max_run(severed) == 7 <= settings.MAX_CONSECUTIVE_OUTSIDE_DAYS

    trace = []
    assert _run_band_pool(df, trace=trace) == [], (
        "a seventeen-day stay below support elected a band box — the run cap "
        "forgave the excursion sitting in the middle of it")
    assert any(r["stage"] == "respect" and r["verdict"] == "rejected"
               for r in trace), "the framing died somewhere other than respect"


def test_band_pool_threads_the_excision_mask_into_the_touch_thirds():
    """The thirds leg is only honest if the mask actually REACHES it. Run on
    the quiet frame, whose respect leg passes, so the occupancy gate is
    reached at all."""
    seen = []
    import engine_alpha.structure.box.box_gates as bg
    real_thirds = bg._rail_touch_thirds

    def spy_thirds(*a, **kw):
        seen.append(kw.get("judged_mask"))
        return real_thirds(*a, **kw)

    bg._rail_touch_thirds = spy_thirds
    try:
        _run_band_pool(_band_frame(departure=False))
    finally:
        bg._rail_touch_thirds = real_thirds

    assert seen, "the occupancy gate was never reached"
    for mask in seen:
        assert mask is not None, "the touch thirds judged a compacted axis"
        assert len(mask) == 80 and int(mask.sum()) == 76


def _thirds_drift_frame():
    """A 100/110 range whose three R touches all sit in the window's real FIRST
    third (bars 2/12/24 of 80), carrying a 20-bar qualified deep event at bars
    30-49. Compaction to 60 bars slides the thirds boundaries under those same
    touches and spreads them across two — the anti-clustering leg's whole
    failure mode, in one frame."""
    n = 80
    closes = np.full(n, 105.0)
    highs = closes + 0.3
    lows = closes - 0.3
    highs[[2, 12, 24]] = R_VAL
    lows[[4, 14, 26]] = S_VAL
    for i in range(30, 50):                   # the qualified deep event
        closes[i] = 97.0
        highs[i] = 97.3
        lows[i] = 96.5
    return pd.DataFrame({"High": highs, "Low": lows, "Close": closes,
                         "Open": closes})


# --- the measure-only mirror must mirror the gate it mirrors ----------------

def test_margin_mirror_reads_the_same_legs_as_the_band_gate():
    """``gate_margins`` exists to reproduce the gate's verdict on the same
    window: the same run number, and the same thirds the mask produced."""
    from engine_alpha.structure.box.gate_margins import complete_leg_vector
    from engine_alpha.structure.box.rail_qualification import qualify_pair_events
    from engine_alpha.structure.metrics.base import _rail_touch_thirds as thirds

    df = _band_frame()
    mask = qualify_pair_events(df, S_VAL, R_VAL, ATR)["judged"]
    window = df[mask]
    gate_run = _respect_stats(window["High"].to_numpy(dtype=float),
                              window["Low"].to_numpy(dtype=float),
                              R_VAL, S_VAL, ATR)[5]
    mirrored = complete_leg_vector(window, R_VAL, S_VAL, ATR,
                                   width_max=settings.BAND_MAX_BOX_WIDTH,
                                   judged_mask=mask)
    assert mirrored["respect_run"]["measured"] == gate_run == 13
    assert not mirrored["respect_run"]["passed"]

    # the thirds leg, on the frame where the mask actually changes the answer
    drift = _thirds_drift_frame()
    dmask = qualify_pair_events(drift, S_VAL, R_VAL, ATR)["judged"]
    dwindow = drift[dmask]
    gate_thirds = thirds(dwindow["High"].to_numpy(dtype=float),
                         dwindow["Low"].to_numpy(dtype=float),
                         R_VAL, S_VAL, ATR, judged_mask=dmask)[2]
    assert gate_thirds == 1
    on_mask = complete_leg_vector(dwindow, R_VAL, S_VAL, ATR,
                                  width_max=settings.BAND_MAX_BOX_WIDTH,
                                  judged_mask=dmask)
    assert on_mask["r_touch_thirds"]["measured"] == gate_thirds
    drifting = complete_leg_vector(dwindow, R_VAL, S_VAL, ATR,
                                   width_max=settings.BAND_MAX_BOX_WIDTH)
    assert drifting["r_touch_thirds"]["measured"] == 2, (
        "without the mask the mirror reports a thirds leg the gate never "
        "measured — the drift this module raises on")


def test_the_near_miss_completion_threads_the_mask_for_band_refusals():
    import engine_alpha.structure.box.near_miss as nm

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
        "the deferred completion rebuilt the masked window but cut its touch "
        "thirds on the compacted axis")
