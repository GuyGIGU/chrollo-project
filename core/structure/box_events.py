"""L2 Wyckoff event reader — the labeled staircase + independent rail-event zones.

Relocated verbatim out of ``core.structure.metrics`` (a pure module peel; no
behavior change). Reads an already-detected equilibrium box and reports the
in-box structure as FACTS — the labeled HH/HL/LH/LL staircase, the independent
R-rail / S-rail event zones (SOS / markup / upthrust / range / rejection / test /
spring / lps), and their chronological assembly into the Wyckoff puzzle. Every
function here is MEASURE-ONLY: it moves no rail, gates nothing, scores nothing;
the Scoring Engine decides what the reads are worth.

For import-compatibility the public symbols are re-exported from
``core.structure.metrics``, so every existing ``from core.structure.metrics
import ...`` site keeps working unchanged.
"""
from __future__ import annotations

import numpy as np

from config import settings
from core.structure.pivots import _build_zigzag, _collapse_swings, _find_pivots


# ---------------------------------------------------------------------------
# L2 staircase — the labeled, chronological HH/HL/LH/LL sequence INSIDE the box
# ---------------------------------------------------------------------------

def _staircase_empty():
    return {"swings": [], "n_swings": 0,
            "counts": {"HH": 0, "HL": 0, "LH": 0, "LL": 0},
            "trend_state": "range", "rail_to_rail": False, "is_zigzag": False}


def _staircase_from_pivots(peaks, valleys, highs, lows, R, S, atr_val, min_amp):
    """Zigzag → amplitude collapse → L0 labels → box annotation over a GIVEN
    order-1 pivot subset: the single staircase machinery behind
    ``read_box_staircase`` (which detects pivots on its own window) and the
    Event Map's windowed views (``core.structure.event_map``, which filter ONE
    whole-frame pivot walk down to a window). Bars in the result index into
    ``highs``/``lows``; the pivot indices must index those same arrays."""
    box = float(R) - float(S)
    if not peaks or not valleys:
        return _staircase_empty()
    zz = _build_zigzag(peaks, valleys, highs, lows)
    if len(zz) < 3:
        return _staircase_empty()
    swings = _collapse_swings(zz, min_amp)
    if len(swings) < 2:
        return _staircase_empty()

    # Lazy import keeps the L0 labeller a leaf dependency (no module-load cycle).
    from core.structure.market_structure import label_market_structure
    labelled = label_market_structure(swings)

    low_zone = settings.TRAVERSAL_LOW_ZONE
    high_zone = settings.TRAVERSAL_HIGH_ZONE
    breach_tol = (settings.BOUNDARY_ATR_BUFFER * float(atr_val)) / box
    out_swings = []
    for pt in labelled["points"]:
        price = float(pt["price"])
        box_pos = (price - float(S)) / box
        if box_pos <= low_zone:
            zone = "low"
        elif box_pos >= high_zone:
            zone = "high"
        else:
            zone = "mid"
        if pt["kind"] == "peak":
            rail_event = ("breach_R" if box_pos > 1.0 + breach_tol
                          else "touch_R" if box_pos >= high_zone else "interior")
        else:
            rail_event = ("breach_S" if box_pos < -breach_tol
                          else "touch_S" if box_pos <= low_zone else "interior")
        out_swings.append({
            "bar": int(pt["bar"]), "kind": pt["kind"], "price": round(price, 4),
            "label": pt["label"], "box_pos": round(box_pos, 4),
            "zone": zone, "rail_event": rail_event,
        })

    counts = {"HH": 0, "HL": 0, "LH": 0, "LL": 0}
    for s in out_swings:
        if s["label"] in counts:
            counts[s["label"]] += 1
    rail_to_rail = (
        any(s["kind"] == "peak" and s["zone"] == "high" for s in out_swings)
        and any(s["kind"] == "valley" and s["zone"] == "low" for s in out_swings)
    )
    return {
        "swings": out_swings,
        "n_swings": len(out_swings),
        "counts": counts,
        "trend_state": labelled["trend_state"],
        "rail_to_rail": bool(rail_to_rail),
        "is_zigzag": bool(rail_to_rail and len(out_swings) >= 3),
    }


def read_box_staircase(base_df, R, S, atr_val, *, noise_frac=None):
    """The labeled, chronological HH/HL/LH/LL staircase INSIDE an equilibrium box.

    The sibling measures read the in-box swing sequence as STATISTICS
    (``measure_contractions`` depths, ``measure_support_slope`` slope,
    ``measure_traversal`` density). This composes the SAME calibrated
    significant-swing skeleton (``_collapse_swings`` — the one ``measure_traversal``
    uses, so the staircase swings ARE the worked-equilibrium swings) with the L0
    swing labelling (``label_market_structure``) and annotates each swing with its
    box-position and rail event: ONE chronological sequence the Wyckoff events
    (upthrust / shakeout / spring / test / LPS) can later be read off, each
    relative to the rail it sits at and the swing before it. Measure-only — it
    moves no rail, gates nothing, scores nothing.

    Each swing dict: ``{bar, kind, price, label, box_pos, zone, rail_event}``:
      * ``label``      HH / HL / LH / LL / first (L0 ``label_market_structure``).
      * ``box_pos``    ``(price - S) / (R - S)``; 0 = S rail, 1 = R rail; <0 or >1
                       is a breach beyond the rail.
      * ``zone``       low (``<= TRAVERSAL_LOW_ZONE``) / high
                       (``>= TRAVERSAL_HIGH_ZONE``) / mid.
      * ``rail_event`` peak: ``breach_R`` (above R + ATR buffer) / ``touch_R``
                       (in the high zone) / ``interior``; valley symmetrically
                       ``breach_S`` / ``touch_S`` / ``interior``.

    Returns dict (safe defaults on a degenerate window):
        swings        list[dict] chronological (bar = ``base_df``-relative)
        n_swings      significant swings after amplitude filtering
        counts        {HH, HL, LH, LL}
        trend_state   L0 running trend at the last swing
        rail_to_rail  a genuine two-sided zigzag: a peak reaches the high zone AND
                      a valley reaches the low zone
        is_zigzag     ``rail_to_rail`` AND ``n_swings >= 3``
    """
    empty = {"swings": [], "n_swings": 0,
             "counts": {"HH": 0, "HL": 0, "LH": 0, "LL": 0},
             "trend_state": "range", "rail_to_rail": False, "is_zigzag": False}
    if base_df is None or len(base_df) == 0:
        return empty
    box = float(R) - float(S)
    if box <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return empty

    highs = base_df["High"].values.astype(float)
    lows = base_df["Low"].values.astype(float)
    if len(highs) < 3:
        return empty

    # The SAME sensitive (order-1) zigzag + amplitude collapse measure_traversal
    # uses, so the labeled staircase rides on the worked-equilibrium swings rather
    # than a fresh skeleton.
    peaks, valleys = _find_pivots(highs, lows, 1)
    if not peaks or not valleys:
        return empty
    zz = _build_zigzag(peaks, valleys, highs, lows)
    if len(zz) < 3:
        return empty
    min_amp = (noise_frac if noise_frac is not None
               else settings.TRAVERSAL_NOISE_FRAC) * box
    swings = _collapse_swings(zz, min_amp)
    if len(swings) < 2:
        return empty

    # Lazy import keeps the L0 labeller a leaf dependency (no module-load cycle).
    from core.structure.market_structure import label_market_structure
    labelled = label_market_structure(swings)

    low_zone = settings.TRAVERSAL_LOW_ZONE
    high_zone = settings.TRAVERSAL_HIGH_ZONE
    breach_tol = (settings.BOUNDARY_ATR_BUFFER * float(atr_val)) / box
    out_swings = []
    for pt in labelled["points"]:
        price = float(pt["price"])
        box_pos = (price - float(S)) / box
        if box_pos <= low_zone:
            zone = "low"
        elif box_pos >= high_zone:
            zone = "high"
        else:
            zone = "mid"
        if pt["kind"] == "peak":
            rail_event = ("breach_R" if box_pos > 1.0 + breach_tol
                          else "touch_R" if box_pos >= high_zone else "interior")
        else:
            rail_event = ("breach_S" if box_pos < -breach_tol
                          else "touch_S" if box_pos <= low_zone else "interior")
        out_swings.append({
            "bar": int(pt["bar"]), "kind": pt["kind"], "price": round(price, 4),
            "label": pt["label"], "box_pos": round(box_pos, 4),
            "zone": zone, "rail_event": rail_event,
        })

    counts = {"HH": 0, "HL": 0, "LH": 0, "LL": 0}
    for s in out_swings:
        if s["label"] in counts:
            counts[s["label"]] += 1
    rail_to_rail = (
        any(s["kind"] == "peak" and s["zone"] == "high" for s in out_swings)
        and any(s["kind"] == "valley" and s["zone"] == "low" for s in out_swings)
    )
    return {
        "swings": out_swings,
        "n_swings": len(out_swings),
        "counts": counts,
        "trend_state": labelled["trend_state"],
        "rail_to_rail": bool(rail_to_rail),
        "is_zigzag": bool(rail_to_rail and len(out_swings) >= 3),
    }


# ---------------------------------------------------------------------------
# L2 Brick 2 — R-rail event ZONES: SOS (strength that holds) vs upthrust (fail)
# ---------------------------------------------------------------------------

# The printed-bars horizon that confirms a hold (R-rail waves and S-rail tests
# share it). Named so the Event Map's role stamps derive knowability from the
# SAME horizon the measurers actually used — never a re-declared literal.
_EVENT_HOLD_MIN_BARS = 6


def _deepest_valley_bar(swings) -> int:
    """The structural V: the deepest staircase valley, box_pos ties broken by bar
    (earliest) for determinism. ``box_pos`` is the rounded value ``read_box_staircase``
    emits — the SINGLE basis the SOS stage-gate and the LPS Phase-D gate both share,
    so they cannot desync. Returns 0 when there are no valleys."""
    valleys = [s for s in swings if s["kind"] == "valley"]
    return (min(valleys, key=lambda s: (s["box_pos"], s["bar"]))["bar"]
            if valleys else 0)


def measure_resistance_events(base_df, R, S, atr_val, *, v_bar=None,
                              hold_min_bars=_EVENT_HOLD_MIN_BARS, swings=None):
    """Independent R-rail event ZONES anchored on the BOX-RELATIVE staircase.

    Anchoring on an ATR band (``R - k*ATR``) over-fires in tight boxes — 0.5 ATR
    is a big slice of a short box, so "reached R" lands mid-box. Instead this
    rides the L0/L2 staircase (``read_box_staircase``): every PEAK that turns in
    the R high-zone (``box_pos >= TRAVERSAL_HIGH_ZONE``) is an R-rail interaction.
    For each, measure the rally STRENGTH into it (from the prior valley), whether
    it BREACHED R, the LINGER (contiguous bars whose High held the high-zone), and
    — from the NEXT staircase valley (or a later higher-high) — whether it HELD or
    FAILED back into the range. AREA-based (linger-tolerant) and INDEPENDENT:
    nothing is gated on another event (an LPS is found separately by
    ``detect_lps`` and is NEVER a precondition).

      * ``SOS``        a Phase-D creek-jump that HELD: the wave-top sits NEAR R
                       (``peak_box_pos <= SOS_NEAR_R_MAX_BOX``) AND the printed
                       post-top hold window is a genuine mini-consolidation (a tight
                       band, ``<= SOS_HOLD_MAX_RANGE_BOX`` of the box) — CONFIRMED BY
                       A HOLD, not by continuation. One SOS per wave.
      * ``markup``     a Phase-D advance that held FAR above R (``peak_box_pos >
                       SOS_NEAR_R_MAX_BOX``) — post-breakout markup, not a creek-jump
                       test of the rail (this is what over-fired SOS in active boxes).
      * ``upthrust``   a Phase-D advance that FAILED — it gave back to the support
                       low-zone before establishing a hold; the WHOLE run-up wave
                       is the upthrust (a false break; short side). One per wave.
      * ``range``      a held advance that is NOT a confirmed SOS — either left of
                       the V (Phase B cause-building) or held at R without a genuine
                       mini-consolidation. NOT a Sign of Strength.
      * ``rejection``  reached R, no clean breach, then gave back — ordinary range
                       oscillation at the ceiling, not a named event.
      * ``in_progress`` still climbing at the right edge — not enough bars after
                       the wave top to confirm a hold and no failure yet.

    An SOS is confirmed by a HOLD (a mini-consolidation/LPS), NOT by continuation:
    a vertical run of higher-highs that ENDS IN A FAILED BREACH is ONE upthrust
    wave, not a string of SOS (operator, 2026-06-28) — the outcome reclassifies
    the whole wave. So consecutive higher-high R-reaches (no drop to support
    between them) are grouped into a WAVE and typed by its TERMINAL outcome: it
    gave back to the low-zone within ``hold_min_bars`` -> FAILED (upthrust); it
    held above support >= ``hold_min_bars`` -> HELD (SOS); a hold, once
    established, is shakeout-tolerant. SOS/range split is by the ``v_bar`` (the V:
    the structural low; defaults to the deepest staircase valley, or pass the
    spring tip). Upthrusts stay stage-agnostic. Measure-only — gates/scores
    nothing. Returns one event per wave, in chronological order.
    """
    box = float(R) - float(S)
    if box <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return []
    if swings is None:   # caller (read_box_events) may pass a precomputed staircase
        swings = read_box_staircase(base_df, R, S, atr_val)["swings"]
    if not swings:
        return []

    highs = base_df["High"].values.astype(float)
    lows = base_df["Low"].values.astype(float)
    n = len(highs)
    high_zone_price = float(S) + settings.TRAVERSAL_HIGH_ZONE * box
    low_zone_price = float(S) + settings.TRAVERSAL_LOW_ZONE * box
    breach_buf = settings.BOUNDARY_ATR_BUFFER * float(atr_val)

    # The "V": the structural low that opens the right side / Phase D. SOS is
    # noted only to the right of it; default = the deepest staircase valley.
    if v_bar is None:
        v_bar = _deepest_valley_bar(swings)

    def _linger(peak_bar):
        lo = peak_bar
        while lo > 0 and highs[lo - 1] >= high_zone_price:
            lo -= 1
        hi = peak_bar
        while hi + 1 < n and highs[hi + 1] >= high_zone_price:
            hi += 1
        return lo, hi

    # R-reach peaks (peaks turning in the high zone) — the wave material.
    reach = [(i, s) for i, s in enumerate(swings)
             if s["kind"] == "peak" and s["zone"] == "high"]

    events = []
    m = 0
    while m < len(reach):
        start_i, start_p = reach[m]
        top_i, top_p = reach[m]
        m2 = m
        # Extend the wave while the next R-reach is a higher-high reached with NO
        # drop to the support low-zone in between — a continuous advance (no hold
        # between pushes). A vertical run is therefore ONE wave.
        while m2 + 1 < len(reach):
            _ni, nxt = reach[m2 + 1]
            if float(nxt["price"]) <= float(top_p["price"]):
                break
            seg = lows[int(top_p["bar"]) + 1: int(nxt["bar"]) + 1]
            if len(seg) and float(seg.min()) <= low_zone_price:
                break
            m2 += 1
            top_i, top_p = reach[m2]

        top_bar = int(top_p["bar"])
        peak_box_pos = float(top_p["box_pos"])
        breached = float(top_p["price"]) > R + breach_buf

        # Terminal outcome after the wave top. A drop to the support low-zone
        # BEFORE a hold of >= hold_min_bars = the advance gave the gains back =
        # FAILED (the whole run-up is the upthrust). No such drop with enough
        # PRINTED bars after = the wave resolved up; too few bars after = still
        # developing at the right edge (never confirm a hold off a partially
        # printed window — no right-edge lookahead).
        after_lows = lows[top_bar + 1:]
        drop_at = next((d for d, lo in enumerate(after_lows)
                        if lo <= low_zone_price), None)
        bars_after = n - top_bar - 1
        if drop_at is not None and drop_at < hold_min_bars:
            resolution = "failed"
        elif drop_at is None and bars_after < hold_min_bars:
            resolution = "in_progress"
        else:
            resolution = "held"

        # An SOS is confirmed ONLY by a genuine mini-consolidation, not by merely
        # "didn't collapse" (the old over-firing cause — a shallow drift counted as
        # a hold). Measure the fully-printed hold window (the bars right after the
        # top, capped at hold_min_bars and at n) and require it CONTAINED: a tight
        # band <= SOS_HOLD_MAX_RANGE_BOX of the box. A late shakeout AFTER this
        # window doesn't un-confirm it (shakeout-tolerant).
        hold_end = min(top_bar + 1 + hold_min_bars, n)
        hold_hi = highs[top_bar + 1:hold_end]
        hold_lo = lows[top_bar + 1:hold_end]
        hold_range_box = (float(hold_hi.max() - hold_lo.min()) / box
                          if len(hold_hi) else None)
        consolidation = (hold_range_box is not None
                         and hold_range_box <= settings.SOS_HOLD_MAX_RANGE_BOX)
        # A creek-jump TESTS the rail: the wave-top sits NEAR R (box-relative). A
        # reach far above R (peak_box_pos > SOS_NEAR_R_MAX_BOX) is post-breakout
        # MARKUP, not an SOS — this is what over-fired in active/extended boxes.
        near_r = peak_box_pos <= settings.SOS_NEAR_R_MAX_BOX

        in_phase_d = top_bar > v_bar
        if resolution == "in_progress":
            etype = "in_progress"
        elif resolution == "held":
            if not in_phase_d:
                etype = "range"          # Phase B (left of the V): cause-building, never an SOS
            elif not near_r:
                etype = "markup"         # held far above R: post-breakout markup, not a creek-jump
            elif not consolidation:
                etype = "range"          # held at R but no genuine mini-consolidation: unconfirmed
            else:
                etype = "SOS"            # Phase D + near R + a real consolidation hold
        elif breached:
            etype = "upthrust"
        else:
            etype = "rejection"

        launch = (swings[start_i - 1]
                  if start_i > 0 and swings[start_i - 1]["kind"] == "valley" else None)
        strength_box = ((float(top_p["price"]) - float(launch["price"])) / box
                        if launch else None)
        lo_b, hi_b = _linger(top_bar)
        zone_start = int(launch["bar"]) if launch else lo_b

        events.append({
            "type": etype,
            "phase": "D" if in_phase_d else "B",
            "peak_bar": top_bar,
            "zone_start": int(zone_start),
            "zone_end": int(hi_b),
            "peak_price": round(float(top_p["price"]), 4),
            "peak_box_pos": round(peak_box_pos, 4),
            "breached": bool(breached),
            "near_r": bool(near_r),
            "consolidation": bool(consolidation),
            "hold_range_box": (round(hold_range_box, 4)
                               if hold_range_box is not None else None),
            "linger_bars": int(hi_b - lo_b + 1),
            "strength_box": (round(strength_box, 4) if strength_box is not None else None),
            "resolution": resolution,
            "wave_bars": int(top_bar - int(start_p["bar"]) + 1),
        })
        m = m2 + 1

    return events


# ---------------------------------------------------------------------------
# L2 Brick 3 — S-rail TEST zones: a touch of S that HOLDS (stage-agnostic)
# ---------------------------------------------------------------------------

def measure_support_tests(base_df, R, S, atr_val, *,
                          hold_min_bars=_EVENT_HOLD_MIN_BARS, swings=None):
    """Independent S-rail TEST zones: a touch of S that HOLDS. Stage-agnostic.

    The S-rail sibling of ``measure_resistance_events`` — but deliberately NOT a
    mirror of the R-rail wave machinery (a test needs no wave grouping and no
    Phase-D split). A ``test`` is a staircase VALLEY that reaches the support
    low-zone WITHOUT a deep breach (the breach-and-reclaim case is a SPRING,
    detected separately by ``find_spring``) and then HOLDS: price makes no
    sustained breakdown below the valley within the printed hold window. AREA-based
    (the excursion + recovery), one zone per qualifying valley, in chronological
    order. ``failed`` = broke below the valley (not a hold); ``in_progress`` = too
    few printed bars after the valley to confirm (no right-edge lookahead).
    Measure-only — gates/scores nothing.
    """
    box = float(R) - float(S)
    if box <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return []
    if swings is None:   # caller (read_box_events) may pass a precomputed staircase
        swings = read_box_staircase(base_df, R, S, atr_val)["swings"]
    if not swings:
        return []

    highs = base_df["High"].values.astype(float)
    lows = base_df["Low"].values.astype(float)
    n = len(lows)
    breach_buf = settings.BOUNDARY_ATR_BUFFER * float(atr_val)

    events = []
    for s in swings:
        if s["kind"] != "valley" or s["zone"] != "low":
            continue
        # A clean test touches S; a deep breach is spring territory (handled by
        # find_spring) — skip it here so the two never double-emit.
        if s["rail_event"] == "breach_S":
            continue
        valley_bar = int(s["bar"])
        valley_low = float(s["price"])
        # HOLD: within the printed window after the valley, price must not make a
        # sustained breakdown below the valley low (a held test). Too few printed
        # bars after -> in_progress (no right-edge lookahead).
        bars_after = n - valley_bar - 1
        hold_end = min(valley_bar + 1 + hold_min_bars, n)
        after_lows = lows[valley_bar + 1:hold_end]
        broke_down = (len(after_lows) > 0
                      and float(after_lows.min()) < valley_low - breach_buf)
        if broke_down:
            resolution = "failed"
        elif bars_after < hold_min_bars:
            resolution = "in_progress"
        else:
            resolution = "held"
        rec_hi = highs[valley_bar:hold_end]
        recovery_box = (float(rec_hi.max() - valley_low) / box
                        if len(rec_hi) > 0 else None)
        events.append({
            "type": "test" if resolution == "held" else resolution,
            "valley_bar": valley_bar,
            "zone_start": valley_bar,
            "zone_end": int(hold_end - 1),
            "valley_price": round(valley_low, 4),
            "valley_box_pos": round(float(s["box_pos"]), 4),
            "recovery_box": (round(recovery_box, 4)
                             if recovery_box is not None else None),
            "resolution": resolution,
        })
    return events


# ---------------------------------------------------------------------------
# L2 — unified independent event view (the pieces E2 assembles into the puzzle)
# ---------------------------------------------------------------------------

# Sentinel distinguishing "not provided -> detect the piece" (the measure-only
# default) from an injected brick, INCLUDING an injected ``None`` (= the engine
# elected no such piece; never re-detect and fabricate one). Compared with ``is``
# only — never ``==`` (which would touch a dataclass ``__eq__``).
_DETECT = object()


def _box_events_with_meta(df, box, atr_val, *, v_bar=None,
                          spring=_DETECT, lps=_DETECT):
    """The independent L2 event ZONES inside ``box`` + the shared assembly meta.

    The single chokepoint behind BOTH ``read_box_events`` (which discards the
    meta) and ``assemble_box_narrative`` (which consumes it). Each event is
    detected on its OWN geometry and is NEVER gated on another; the bullish
    chronology (spring -> SOS -> LPS) is a future quality grade, not a definition
    here. Composed by REUSING the calibrated detectors:
      * SOS / markup / upthrust / range / rejection / in_progress  (R-rail waves)
        via ``measure_resistance_events``
      * test  (S-rail touch-that-holds)  via ``measure_support_tests``
      * spring  (breach-S-that-reclaims) — the calibrated Phase-C brick
      * LPS  (Phase-D support test) — gated PURELY on bar position (right of the
        V), NEVER on an SOS existing.

    The spring / LPS bricks come from ONE of two sources, selected per-arg by the
    ``spring``/``lps`` kwargs: the default ``_DETECT`` re-runs ``find_spring`` /
    ``find_lps`` here (the measure-only ``read_box_events`` path — byte-identical
    to before), while a caller that already elected them (E3 scoring passes
    ``structure.spring``/``structure.lps``) injects them so the read describes the
    bricks that ACTUALLY fired — including a tighter inner-box LPS. An injected
    ``None`` means "the engine elected no such piece" and is honored (no re-detect).

    ``find_spring``/``find_lps`` index into the FULL ``df``; their bars are
    translated to box-relative (``- box.start_bar``) so every zone shares ONE
    origin — the box / base (0 = box.start_bar), which is also the render's frame.
    An injected inner-box LPS still carries ABSOLUTE df bars and ``inner ⊆ parent``
    guarantees ``start_bar >= box.start_bar``, so the same ``- start`` translation
    applies with no rebasing.

    Builds the staircase ONCE and resolves the V ONCE: returns
    ``(events, v_bar, base_n, has_valley)`` where ``v_bar`` is the SAME resolved
    structural-low int threaded into the SOS stage-gate and the LPS Phase-D gate
    (single-sourced so phase segmentation cannot desync from the gates), ``base_n``
    is the rendered base-frame length, and ``has_valley`` says whether a real V
    exists (>=1 valley swing) so callers don't read a defaulted ``v_bar==0`` as a
    real structural low. Measure-only — gates/scores nothing.
    """
    # Leaf import keeps bricks a downstream dependency (no module-load cycle).
    from core.structure.bricks import find_lps, find_spring

    if (df is None or box is None or atr_val is None or atr_val <= 0
            or not np.isfinite(atr_val)):
        return [], 0, 0, False
    start = int(box.start_bar)
    if start < 0 or start >= len(df) or int(box.base_len) <= 0:
        return [], 0, 0, False
    R, S = float(box.R), float(box.S)
    if R - S <= 0:
        return [], 0, 0, False
    base_df = df.iloc[start:]
    base_n = len(base_df)

    def _clip(b):  # bound translated brick bars into the rendered base frame
        return max(0, min(int(b), base_n - 1))

    # Build the staircase ONCE and share it: the V, the R-rail waves and the S-rail
    # tests all read the SAME swings (the heaviest L2 primitive runs once, not 3x).
    swings = read_box_staircase(base_df, R, S, atr_val)["swings"]
    has_valley = any(s["kind"] == "valley" for s in swings)
    if v_bar is None:
        v_bar = _deepest_valley_bar(swings)

    events = []
    for e in measure_resistance_events(base_df, R, S, atr_val, v_bar=v_bar,
                                       swings=swings):
        events.append({**e, "rail": "R", "anchor_bar": int(e["peak_bar"])})
    for e in measure_support_tests(base_df, R, S, atr_val, swings=swings):
        events.append({**e, "rail": "S", "anchor_bar": int(e["valley_bar"])})

    sp = find_spring(df, box, atr_val) if spring is _DETECT else spring
    if sp is not None:
        tip = int(sp.tip_bar) - start
        rec = int(sp.recovery_bar) - start
        if tip >= 0:   # the brick guarantees in-box bars; clip is a belt-and-braces bound
            tip, rec = _clip(tip), _clip(rec)
            events.append({
                "type": "spring", "rail": "S", "phase": "C",
                "zone_start": tip, "zone_end": max(tip, rec), "anchor_bar": tip,
                "undercut_atr": round(float(sp.undercut_atr), 4),
                "recovery_bars": int(sp.recovery_bars),
            })

    lp = find_lps(df, box, atr_val) if lps is _DETECT else lps
    if lp is not None:
        if lps is not _DETECT:
            # Injected = read_structure's ELECTED brick (may be the inner-box LPS);
            # its bars are absolute df indices and inner ⊆ parent, so start_bar is
            # never left of the box start. Pin the geometry invariant loudly.
            assert int(lp.start_bar) >= start, "elected LPS left of box start (inner⊄parent)"
        lstart = int(lp.start_bar) - start
        lend = int(lp.end_bar) - start
        llow = int(lp.low_bar) - start
        # Phase-D gate: PURELY bar position (right of the V) — never SOS presence.
        if lstart >= 0 and lstart > v_bar:
            lstart, lend, llow = _clip(lstart), _clip(lend), _clip(llow)
            events.append({
                "type": "lps", "rail": "S", "phase": "D",
                "zone_start": lstart, "zone_end": max(lstart, lend),
                "anchor_bar": llow, "swing_type": lp.swing_type,
            })

    _PRIORITY = {"spring": 0, "test": 1, "SOS": 2, "lps": 3, "upthrust": 4,
                 "markup": 5, "range": 6, "rejection": 7, "failed": 8,
                 "in_progress": 9}
    events.sort(key=lambda e: (int(e["zone_start"]),
                               _PRIORITY.get(e["type"], 99),
                               e.get("rail", ""), int(e.get("anchor_bar", 0))))
    return events, int(v_bar), int(base_n), bool(has_valley)


def read_box_events(df, box, atr_val, *, v_bar=None):
    """The independent Wyckoff event ZONES inside ``box``, all box-relative.

    The flat, deterministically-ordered list of measure-only L2 event zones —
    spring / test / SOS / markup / upthrust / range / rejection / lps /
    in_progress — each detected on its OWN geometry and NEVER gated on another;
    the bullish chronology is a future quality grade (see ``assemble_box_narrative``),
    not a definition here. Thin public wrapper over ``_box_events_with_meta`` (which
    carries the shared V / base_n the assembler also reads). Returns a flat list of
    zone dicts, each carrying ``type``/``zone_start``/``zone_end``/``anchor_bar``,
    ordered by ``(zone_start, type-priority, rail)``. Measure-only — gates/scores
    nothing.
    """
    return _box_events_with_meta(df, box, atr_val, v_bar=v_bar)[0]


# ---------------------------------------------------------------------------
# L2 — E2: chronological assembly of the independent pieces into the PUZZLE
# ---------------------------------------------------------------------------

def assemble_box_narrative(df, box, atr_val, *, v_bar=None,
                           spring=_DETECT, lps=_DETECT):
    """Assemble the independent L2 event ZONES (``read_box_events``) into the
    Wyckoff puzzle + an explainable trace. MEASURE-ONLY — the assembled read E3
    will later score; this gates/scores nothing and encodes no veto.

    Consumes ONLY the pieces ``_box_events_with_meta`` returns (one staircase
    build, one V): the whole spine is selected by FILTERING the passthrough
    ``events`` by ``type``, so the V, the LPS Phase-D gate, and the chronology can
    never desync from E1. The ``spring``/``lps`` kwargs are forwarded verbatim to
    ``_box_events_with_meta``: the default ``_DETECT`` re-detects (measure-only,
    byte-identical), while E3 scoring injects the engine's already-elected
    ``structure.spring``/``structure.lps`` so the assembled read describes the
    bricks that ACTUALLY fired — including a tighter inner-box LPS — rather than a
    fresh parent-box re-detection.

    The chronology spring -> SOS -> LPS is a DESCRIPTIVE quality signal when
    present and bar-ordered; it is NEVER a gate, and a missing piece is reported,
    never fabricated. The returned dict's only reads are descriptive grades — a
    raw 0..4 ``completeness`` tally, a 3-valued ``chronology`` enum, and
    ``upthrust_terminal`` (a read of the detected outcome) — none shaped as a
    pass/fail another layer could consume as a filter. Every leaf is a native
    Python int/str/bool/None/float (JSON-friendly, byte-stable).

    spine bars (the canonical chronology comparator, frozen): spring -> anchor_bar
    (tip), SOS -> anchor_bar (= peak_bar), LPS -> anchor_bar (low_bar).
    ``chronology == "intact"`` iff all three present AND
    ``spring.anchor_bar < sos.anchor_bar < lps.anchor_bar`` (strict).
    ``upthrust_terminal`` (the TITN read) iff an upthrust exists, NO SOS exists
    anywhere, and nothing after the last upthrust resolves it up or is still
    developing (no markup / in_progress / genuine Phase-D ``range`` R-wave at or
    after it) — so it is mutually exclusive with a spine SOS and never overrides
    E1's right-edge no-lookahead.
    Phases are O(1) derivations off the shared V (only when a real V exists):
    ``B = [0, v_bar]``; ``C = spring zone`` (a marked sub-zone that may overlap B);
    ``D = [v_bar+1, base_n-1]`` iff any Phase-D event (SOS / markup / lps) exists.
    """
    events, v_bar, base_n, has_valley = _box_events_with_meta(
        df, box, atr_val, v_bar=v_bar, spring=spring, lps=lps)

    spine = {"spring": None, "sos": None, "lps": None}
    if not events and not has_valley:
        # Degenerate / structureless box -> a well-formed empty narrative. The
        # trace is intentionally EMPTY here (nothing was read), distinct from the
        # summary-only trace the main path emits for a valid box that has a V but
        # no named pieces -- do not unify the two paths.
        return {
            "events": events, "v_bar": int(v_bar), "base_n": int(base_n),
            "spine": spine, "tests": 0, "upthrust_terminal": False,
            "completeness": 0, "chronology": "absent",
            "phases": {"B": None, "C": None, "D": None},
            "lps_pre_v_dropped": False, "trace": [],
        }

    # ONE linear pass over the (already chronologically-sorted) pieces — adds zero
    # detector calls; spine is references into events[] (do not mutate).
    spring = lps_event = None
    sos_events = []
    upthrusts = []
    tests = 0
    has_phase_d_event = False
    for e in events:
        t = e["type"]
        if t == "spring":
            spring = e
        elif t == "lps":
            lps_event = e
            has_phase_d_event = True
        elif t == "test":
            tests += 1
        elif t == "SOS":
            sos_events.append(e)
            has_phase_d_event = True
        elif t == "upthrust":
            upthrusts.append(e)
        elif t == "markup":
            has_phase_d_event = True

    # First chronological SOS = the creek-jump that opens markup; later held
    # reaches stay in events[] but are not the spine SOS. Full key is defensive —
    # SOS waves are non-overlapping so anchor_bar is already unique.
    sos = (min(sos_events, key=lambda e: (int(e["anchor_bar"]),
                                          int(e["zone_start"]),
                                          float(e["peak_price"])))
           if sos_events else None)
    spine["spring"], spine["sos"], spine["lps"] = spring, sos, lps_event

    # An injected (engine-elected) LPS that the Phase-D bar-position gate dropped
    # (a rare late-V parent where the elected LPS anchors at/left of the parent V)
    # would silently understate completeness — surface it rather than hide it. The
    # gate itself stays (it is the Phase-D placement guard); this only makes the
    # drop auditable. ``lps`` here is the injection PARAM (a brick or None when the
    # engine elected/rejected one, else the _DETECT sentinel); ``lps_event`` is the
    # zone that survived the gate. Only meaningful for an injected LPS.
    lps_pre_v_dropped = (lps is not _DETECT and lps is not None
                         and lps_event is None and has_valley)

    # upthrust_terminal: the run-up IS the terminal event (TITN) — an upthrust with
    # zero SOS anywhere (mutually exclusive with a spine SOS) and nothing after the
    # last upthrust that resolves up. A held R-wave after the last upthrust clears
    # the terminal read: markup / in_progress (unchanged), plus a genuine Phase-D
    # "range" (held near R). The Phase-D guard (anchor > v_bar) on the "range" term
    # keeps a Phase-B cause-building range (left of the V, which shares the label)
    # from wrongly clearing a terminal upthrust.
    upthrust_terminal = False
    if upthrusts and sos is None:
        last_up = max(int(e["anchor_bar"]) for e in upthrusts)
        resolved_after = any(
            e.get("rail") == "R" and int(e["anchor_bar"]) >= last_up
            and (e["type"] in ("markup", "in_progress")
                 or (e["type"] == "range" and int(e["anchor_bar"]) > v_bar))
            for e in events)
        upthrust_terminal = not resolved_after

    # Descriptive grades — NEVER gates. completeness counts distinct canonical
    # pieces present (held tests only, each class at most 1); the test slot reuses
    # the SAME held-test filter as ``tests`` so the two cannot drift.
    completeness = ((spring is not None) + (sos is not None)
                    + (lps_event is not None) + (tests > 0))

    if (spring is not None and sos is not None and lps_event is not None
            and spring["anchor_bar"] < sos["anchor_bar"] < lps_event["anchor_bar"]):
        chronology = "intact"
    elif spring is not None or sos is not None or lps_event is not None:
        chronology = "partial"
    else:
        chronology = "absent"

    # Phases — only when a real V exists. B/C/D are pure derivations off the shared
    # v_bar/base_n; the V bar belongs to B (matching in_phase_d = top_bar > v_bar),
    # so B.end + 1 == D.start with no overlap. C (the spring zone) may overlap B —
    # a marked sub-zone, not a partition member.
    phases = {"B": None, "C": None, "D": None}
    if has_valley:
        phases["B"] = [0, int(v_bar)]
        if spring is not None:
            phases["C"] = [int(spring["zone_start"]), int(spring["zone_end"])]
        if has_phase_d_event and int(v_bar) + 1 <= int(base_n) - 1:
            phases["D"] = [int(v_bar) + 1, int(base_n) - 1]

    # Trace — a pure render of the spine/phases (no recomputation, no second code
    # path). Interpolates only ints / already-rounded values so it is byte-stable.
    steps = []
    if spring is not None:
        steps.append((int(spring["anchor_bar"]),
                      f"C[bar {int(spring['anchor_bar'])}]: spring - breach S, "
                      f"reclaimed in {int(spring['recovery_bars'])} bars "
                      f"(undercut {spring['undercut_atr']} ATR)"))
    if sos is not None:
        steps.append((int(sos["anchor_bar"]),
                      f"D[bar {int(sos['anchor_bar'])}]: SOS - creek-jump held "
                      f"near R (hold {sos['hold_range_box']} box)"))
    if lps_event is not None:
        steps.append((int(lps_event["anchor_bar"]),
                      f"D[bar {int(lps_event['anchor_bar'])}]: LPS - support test held "
                      f"({lps_event['swing_type']})"))
    steps.sort(key=lambda s: s[0])
    trace = [line for _, line in steps]
    if tests:
        trace.append(f"test x{tests}: support touch(es) that held")
    if upthrust_terminal:
        trace.append("terminal upthrust - run-up topped above R and failed back "
                     "(no SOS)")
    if lps_pre_v_dropped:
        trace.append("note: engine-elected LPS anchors at/left of the V "
                     "(Phase-D gate dropped it) - completeness excludes the LPS")
    trace.append(f"-> chronology {chronology}, completeness {completeness}/4")

    return {
        "events": events,
        "v_bar": int(v_bar),
        "base_n": int(base_n),
        "spine": spine,
        "tests": int(tests),
        "upthrust_terminal": bool(upthrust_terminal),
        "completeness": int(completeness),
        "chronology": chronology,
        "phases": phases,
        "lps_pre_v_dropped": bool(lps_pre_v_dropped),
        "trace": trace,
    }
