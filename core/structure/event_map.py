"""Event Map — the mechanical swing layer (whole-frame, measure-only).

Widens the ONE calibrated swing skeleton (the L2 staircase's order-1 pivots +
amplitude collapse) from the elected box's window to the WHOLE evaluation frame,
so the engine can read the pre-box trend and the box story on one substrate. It
stands up no second skeleton: ONE bar-level pivot walk runs per frame, and each
windowed view — the pre-box segment, the in-box staircase — is that walk's
pivots filtered to its window and fed through the SAME staircase machinery
(``box_events._staircase_from_pivots``).

The in-box view is byte-identical to ``read_box_staircase`` by construction:
an order-1 pivot at frame bar ``a`` with ``start < a < n-1`` satisfies exactly
the comparisons the windowed walk applies at base bar ``a - start`` (asserted by
tests and the Task-4 capture battery). The widening is therefore additive —
pre-box swings appear, including a pivot at the box-start bar itself (which the
windowed walk's order margin masked); nothing inside the box moves.

The two views are stitched, not re-collapsed: alternation and collapse state
reset at the box-start seam (the price of keeping the in-box slice identical to
the elected staircase), and each view's HH/HL/LH/LL labels start fresh at its
own first swing. Consumers reading across the seam treat it as a boundary
(causality contract §4: interval/seam conventions are stated, never implicit).

Causality (specs/event-map-causality-contract.md — binding):
  * every swing carries ``describes_bar`` (its pivot bar) and ``knowable_bar`` —
    the first bar at whose close the swing was irreversibly committed: the bar
    that pivot-confirms the first opposite extreme whose counter-move off this
    swing reaches the collapse threshold ``min_amp``. Before that, a
    same-direction exceedance would have absorbed the swing (the collapse's
    forward merge), so commitment is refused (conservatively, on an equal
    extreme too) and the swing is ``in_progress``.
  * ``in_progress`` (``knowable_bar`` None) covers the right-edge swing whose
    committing reversal has not printed AND a window-edge extreme superseded
    outside its window. In-progress never satisfies a downstream predicate.
  * stamps are frame-causal, not window-causal: a pre-box swing may be committed
    by in-box bars — that is real chronology, not lookahead.
  * the frame's first swing is ``edge_uncertain`` — whether a more extreme swing
    preceded it depends on bars left of the live two-year trim (contract §3).

NaN policy (contract §5): highs/lows are coerced to float once at entry;
non-finite bars are counted in ``nan_bars`` and can never pivot (every pivot
comparison against NaN is False — the walk fails closed, and the count makes the
silence visible).

Measure-only: moves no rail, gates nothing, scores nothing. Nothing on the live
scan path calls this yet — fire-path staging with its flag protocol is plan
Task 6 (PLAN-event-tape.md).
"""
from __future__ import annotations

import numpy as np

from config import settings
from core.structure.box_events import _staircase_empty, _staircase_from_pivots
from core.structure.pivots import _find_pivots


def _empty_map() -> dict:
    return {
        "swings": [], "n_swings": 0,
        "pre_box": {"n_swings": 0, "trend_state": "range"},
        "box": {"n_swings": 0, "trend_state": "range",
                "counts": {"HH": 0, "HL": 0, "LH": 0, "LL": 0},
                "rail_to_rail": False, "is_zigzag": False},
        "start_bar": 0, "n_bars": 0, "nan_bars": 0,
    }


def _stamp_causality(swings, highs, lows, min_amp):
    """Dual bar stamps (contract §1–§2), in place.

    A swing is committed at the bar that pivot-confirms the first opposite
    extreme lying ``min_amp`` beyond it: for a peak, the first valley-form bar
    ``v`` (``lows[v] <= lows[v-1]`` and ``lows[v] < lows[v+1]``) with
    ``lows[v] <= peak - min_amp`` — knowable at ``v + 1``, the bar that confirms
    the pivot. A same-direction extreme at/above the swing's price before that
    point means the collapse would have absorbed it: commitment is refused and
    the swing stays ``in_progress``. Comparisons run on the raw arrays the walk
    itself read — no re-derived floats (contract §4).
    """
    n = len(highs)
    for s in swings:
        bar = int(s["bar"])
        s["describes_bar"] = bar
        know = None
        if s["kind"] == "peak":
            top = highs[bar]
            for v in range(bar + 1, n - 1):
                if highs[v] >= top:
                    break                      # extreme migrated before committing
                if (lows[v] <= top - min_amp
                        and lows[v] <= lows[v - 1] and lows[v] < lows[v + 1]):
                    know = v + 1
                    break
        else:
            bot = lows[bar]
            for v in range(bar + 1, n - 1):
                if lows[v] <= bot:
                    break                      # extreme migrated before committing
                if (highs[v] >= bot + min_amp
                        and highs[v] >= highs[v - 1] and highs[v] > highs[v + 1]):
                    know = v + 1
                    break
        s["knowable_bar"] = know
        s["in_progress"] = know is None
    if swings:
        swings[0]["edge_uncertain"] = True


def read_swing_map(df, box, atr_val, *, noise_frac=None) -> dict:
    """The whole-frame mechanical swing map around an elected equilibrium box.

    One order-1 pivot walk over the full frame, sliced into two windowed views
    through the shared staircase machinery:

      * ``region == "box"`` — the in-box staircase, byte-identical to
        ``read_box_staircase(df.iloc[box.start_bar:], R, S, atr_val)`` (bars
        re-based to df-absolute; the tape adds only ``region`` + the causality
        stamps).
      * ``region == "pre_box"`` — the same machinery over the pivots left of the
        box start (bar ``start`` itself included: its right context exists in
        the full frame), df-absolute, annotated against the SAME elected rails
        so the trend's position relative to the box is readable.

    Returns (safe empty shape on a degenerate frame/box):
        swings     chronological, df-absolute; each ``{bar, kind, price, label,
                   box_pos, zone, rail_event, region, describes_bar,
                   knowable_bar, in_progress}`` (+ ``edge_uncertain`` on the
                   frame's first swing)
        n_swings   total swings across both regions
        pre_box    {n_swings, trend_state} of the pre-box view
        box        {n_swings, trend_state, counts, rail_to_rail, is_zigzag} —
                   the staircase's own summary, verbatim
        start_bar / n_bars / nan_bars

    Measure-only; no live-path caller (fire-path staging is plan Task 6).
    """
    if df is None or len(df) == 0 or box is None:
        return _empty_map()
    R, S = float(box.R), float(box.S)
    height = R - S
    if height <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return _empty_map()
    start = int(box.start_bar)
    n = len(df)
    if start < 0 or start >= n:
        return _empty_map()

    # Coerce ONCE at entry (contract §5); count unreadable bars loudly.
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    nan_bars = int((~(np.isfinite(highs) & np.isfinite(lows))).sum())

    min_amp = (noise_frac if noise_frac is not None
               else settings.TRAVERSAL_NOISE_FRAC) * height

    # THE one bar-level swing walk for the whole frame.
    peaks, valleys = _find_pivots(highs, lows, 1) if n >= 3 else ([], [])

    # In-box view: full-frame pivots right of the box start, re-based and run
    # through the same machinery the box staircase uses.
    box_view = _staircase_from_pivots(
        [p - start for p in peaks if p >= start + 1],
        [v - start for v in valleys if v >= start + 1],
        highs[start:], lows[start:], R, S, atr_val, min_amp,
    ) if len(highs) - start >= 3 else _staircase_empty()

    # Pre-box view: pivots at/left of the box start, same machinery, absolute bars.
    pre_view = _staircase_from_pivots(
        [p for p in peaks if p <= start],
        [v for v in valleys if v <= start],
        highs, lows, R, S, atr_val, min_amp,
    )

    swings = [{**s, "region": "pre_box"} for s in pre_view["swings"]]
    swings += [{**s, "bar": int(s["bar"]) + start, "region": "box"}
               for s in box_view["swings"]]
    _stamp_causality(swings, highs, lows, min_amp)

    return {
        "swings": swings,
        "n_swings": len(swings),
        "pre_box": {"n_swings": pre_view["n_swings"],
                    "trend_state": pre_view["trend_state"]},
        "box": {"n_swings": box_view["n_swings"],
                "trend_state": box_view["trend_state"],
                "counts": box_view["counts"],
                "rail_to_rail": box_view["rail_to_rail"],
                "is_zigzag": box_view["is_zigzag"]},
        "start_bar": start,
        "n_bars": n,
        "nan_bars": nan_bars,
    }
