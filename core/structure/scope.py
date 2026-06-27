"""
Consolidation scoping layer — "which part of the base is which".

This is the descriptive Phase-D scoping layer (see docs/strategy_v2.md, "The
Phase D Model"). It does NOT detect anything new and it does NOT score: it
consumes values the detector + LPS finder already produced and re-expresses
them as the right-most launch region the human eye reads first.

It answers a single question per setup: *given where the box, the swing, and
the LPS already are, where does the right-most region (Phase D) begin, and what
sits inside it?* The output is bands + a support-zone price band, archived raw
and drawn on the chart overlay. It is a HINT, never a gate — nothing here can drop
a ticker or change a score.

Regions (all best-effort; any boundary that can't be placed confidently is
returned as ``None`` so the chart degrades gracefully — young bases legitimately
have fewer regions, and we never force four tidy quadrants):

    Phase A  — lead-in: climax / trend exhaustion into the equilibrium body
               (bc_anchor_bar -> phase_a_end_bar, usually the AR)
    Phase B  — the working base / cause-building region. In the chart
               validation overlay it is read as the whole base from
               phase_b_start_bar through the setup end, with Phase D as an
               overlapping right-side subregion rather than a hard cutoff.
    Phase D  — the right-most region where the LPS is evaluated. It begins at
               the earliest credible right-side evidence after the Phase-C /
               search floor: support-test cluster, inner mini-consolidation,
               or V-tip. The LPS remains the mandatory gate and fallback.
    Phase C  — optional measured spring. A spring recovery floors the Phase-D
               search; it is not itself the Phase-D boundary source.

The LPS zone (``lps_zone_low``/``lps_zone_high`` + ``lps_zone_start_date``/
``lps_zone_end_date``) is the bounding box of the exact LPS candidate bars —
Chrollo's convention highlights those specific bars, so the zone wraps them
tightly in both price and time rather than stretching a level across Phase D.
"""
from __future__ import annotations

import json
from typing import Optional

import pandas as pd

from core.structure.phase_d import drawn_lps_zone_start, resolve_phase_d_boundary


def _date_at(df: "pd.DataFrame", idx: Optional[int]) -> Optional[str]:
    """``df.index[idx]`` as a ``YYYY-MM-DD`` string, or None if out of range.

    Mirrors the ``str(...index...)[:10]`` idiom used elsewhere in the pipeline
    (e.g. ``_base_date_start``). Defensive: a non-datetime index or an
    out-of-range / None idx returns None rather than raising — a single bad
    value must never poison the per-ticker result.
    """
    if idx is None:
        return None
    n = len(df)
    if idx < 0 or idx >= n:
        return None
    try:
        return str(df.index[idx])[:10]
    except (IndexError, TypeError, ValueError):
        return None


def _resolve_phase_d_start(*, box_start: int, base_len: int, last: int,
                           is_inner_box: bool, has_lps_window: bool,
                           lps_start: int, b: Optional[int],
                           phase_d_start_bar: Optional[int] = None,
                           support_test_start_bar: Optional[int] = None,
                           sos_reclaim_start_bar: Optional[int] = None,
                           rising_support_start_bar: Optional[int] = None,
                           phase_c_recovery_bar: Optional[int] = None,
                           v_tip_bar: Optional[int] = None) -> Optional[int]:
    """Phase-D right-most-region start bar, df-positional. Pure.

    Compatibility wrapper around ``core.structure.phase_d`` so existing tests and
    callers can ask for the bar only while bins/scope/narrative share one rule.

    The result is clamped on-frame and never allowed to invert the body start
    ``b``: when the base is too young to separate body from Phase D it
    collapses to ``b`` rather than crossing it.
    """
    inner_start = box_start if (is_inner_box and phase_d_start_bar is None) else phase_d_start_bar
    return resolve_phase_d_boundary(
        last=last,
        has_lps_window=has_lps_window,
        lps_start=lps_start,
        b=b,
        phase_c_recovery_bar=phase_c_recovery_bar,
        phase_d_start_bar=inner_start,
        v_tip_bar=v_tip_bar,
        support_test_start_bar=support_test_start_bar,
        sos_reclaim_start_bar=sos_reclaim_start_bar,
        rising_support_start_bar=rising_support_start_bar,
    ).start_bar


def scope_consolidation(
    df: "pd.DataFrame",
    *,
    bc_anchor_bar: int,
    phase_b_start_bar: int,
    base_len: int,
    is_inner_box: bool,
    lps_offset: int,
    lps_length: int,
    lps_zone_type: str,
    atr_val: float,
    phase_d_start_bar: Optional[int] = None,
    support_test_start_bar: Optional[int] = None,
    sos_reclaim_start_bar: Optional[int] = None,
    rising_support_start_bar: Optional[int] = None,
    phase_a_end_bar: Optional[int] = None,
    phase_c_recovery_bar: Optional[int] = None,
    v_tip_bar: Optional[int] = None,
    lps_zone_draw_min_descent: float = 0.0,
) -> dict:
    """Scope the right-most region of an already-detected base. Pure measurement.

    All bar indices are df-positional (same frame the candles are drawn from),
    so the emitted dates line up with the chart's OHLC series regardless of how
    the chart windows them.

    Args:
        df: the per-ticker OHLC frame (DatetimeIndex), as seen by the detector.
        bc_anchor_bar: df-positional BC/SC climax bar (Phase A start).
        phase_b_start_bar: df-positional equilibrium-body start (AR low / bounce
            high for an outer box; inner search start for an inner box).
        base_len: working box length in bars (=> box start = len(df) - base_len).
        is_inner_box: True when the hierarchical detector picked an inner
            sub-box (a Phase D mini-consolidation).
        phase_d_start_bar: optional explicit Phase-D start. Used when the parent
            remains the base of record and an inner Phase D range is drawn inside
            it.
        support_test_start_bar: optional df-positional start of a measured
            right-side support-test cluster. Used only as a better descriptive
            Phase-D hint when no inner range exists.
        sos_reclaim_start_bar/rising_support_start_bar: optional df-positional
            starts of first-class right-side evidence derived from LPS/Test
            candidates.
        phase_c_recovery_bar: optional df-positional recovery bar of a true
            measured Phase-C spring. When present, this floors the Phase-D
            evidence search; the boundary still comes from right-side evidence
            or the LPS fallback.
        v_tip_bar: optional df-positional final recovered low in the late base.
            Used as the Phase B->D divider when no inner range exists.
        lps_offset, lps_length: locate the LPS window: it ends at
            ``len(df) - lps_offset`` (exclusive) and spans ``lps_length`` bars.
        lps_zone_type: "INSIDE" / "OVERSHOOT_R" / "UNDERCUT_S". A spring
            (UNDERCUT_S) emits a Phase C marker.
        atr_val: ATR snapshot used for the support-band thickness.

    Returns a JSON-safe dict (un-prefixed keys; the pipeline prefixes them):
        phase_a_start_date, phase_b_start_date, phase_d_start_date,
        phase_a_end_date    -> "YYYY-MM-DD" | None
        phase_c_event_date  -> "YYYY-MM-DD" | None
        lps_zone_low, lps_zone_high                 -> float | None
        lps_zone_start_date, lps_zone_end_date      -> "YYYY-MM-DD" | None
            (time bounds of the exact LPS candidate bars; the zone is their
            bounding box, not a level stretched across Phase D)
        has_mini_consolidation                      -> bool
        scope_confidence                            -> float in [0, 1]
        phase_a_start_bar, phase_b_start_bar, phase_d_start_bar -> int | None
            (raw df-positional anchors, for archive / fidelity grading)
    """
    n = len(df)
    empty = {
        "phase_a_start_date": None,
        "phase_a_end_date": None,
        "phase_b_start_date": None,
        "phase_d_start_date": None,
        "phase_c_event_date": None,
        "lps_zone_low": None,
        "lps_zone_high": None,
        "lps_zone_start_date": None,
        "lps_zone_end_date": None,
        "has_mini_consolidation": bool(is_inner_box or phase_d_start_bar is not None),
        "scope_confidence": 0.0,
        "phase_d_evidence_json": None,
        "phase_a_start_bar": None,
        "phase_a_end_bar": None,
        "phase_b_start_bar": None,
        "phase_d_start_bar": None,
    }
    if n == 0 or base_len <= 0:
        return empty

    last = n - 1

    # ── Phase A / Phase B anchors (df-positional) ───────────────────────────
    a = bc_anchor_bar if (bc_anchor_bar is not None and 0 <= bc_anchor_bar < n) else None
    a_end = phase_a_end_bar if (
        phase_a_end_bar is not None and 0 <= phase_a_end_bar < n
    ) else None
    b = phase_b_start_bar if (phase_b_start_bar is not None and 0 <= phase_b_start_bar < n) else None
    if a_end is None and a is not None and b is not None:
        a_end = b
    # Degenerate ordering (climax after body start) → drop the lead-in pair
    # rather than draw an inverted band.
    if a is not None and b is not None and a > b:
        a = None
        a_end = None
        b = None
    if a is not None and a_end is not None and a_end < a:
        a = None
        a_end = None

    # ── LPS window (df-positional, clamped) + its low bar ───────────────────
    lps_end = n - max(0, int(lps_offset))          # exclusive
    lps_start = max(0, lps_end - max(1, int(lps_length)))
    lps_end = min(lps_end, n)
    has_lps_window = lps_end > lps_start
    lps_low = None
    lps_high = None
    lps_low_bar = None       # df-positional bar of the LPS low (the V's tip)
    if has_lps_window:
        try:
            low_seg = df["Low"].iloc[lps_start:lps_end]
            high_seg = df["High"].iloc[lps_start:lps_end]
            lps_low = float(low_seg.min())
            lps_high = float(high_seg.max())
            lps_low_bar = lps_start + int(low_seg.values.argmin())
        except (KeyError, ValueError, TypeError):
            lps_low = None
            lps_high = None
            lps_low_bar = None

    box_start = n - base_len

    # ── Phase D anchor — the right-most region ─────────────────────────────
    # Boundary rule lives in core.structure.phase_d: use the best right-side
    # evidence available, with the LPS window as the mandatory fallback.
    inner_start = box_start if (is_inner_box and phase_d_start_bar is None) else phase_d_start_bar
    phase_d = resolve_phase_d_boundary(
        last=last,
        has_lps_window=has_lps_window,
        lps_start=lps_start,
        b=b,
        phase_c_recovery_bar=phase_c_recovery_bar,
        phase_d_start_bar=inner_start,
        v_tip_bar=v_tip_bar,
        support_test_start_bar=support_test_start_bar,
        sos_reclaim_start_bar=sos_reclaim_start_bar,
        rising_support_start_bar=rising_support_start_bar,
    )
    d = phase_d.start_bar

    # ── Phase C spring marker (UNDERCUT_S only) — the undercut low (V tip) ───
    c = lps_low_bar if (lps_zone_type == "UNDERCUT_S" and lps_low_bar is not None) else None

    # ── LPS zone: the bounding box of the drawn LPS candidate bars ──────────
    # Chrollo's convention highlights the specific bars that form the LPS, so
    # the zone wraps those bars tightly in BOTH axes: price spans their true
    # [min low, max high], and the start/end dates bound them in time. A flat
    # one-bar window still needs drawable height, so atr_val is a visibility
    # floor only (never the band's meaning).
    #
    # DISPLAY TRIM (recall-safe): when ``lps_zone_draw_min_descent`` is set, a
    # rising shelf's drawn start is advanced to its longest down/sideways suffix
    # so the gold box shows the reaction, not the climb into it. This narrows
    # ONLY the drawn box — the structural window (lps_start/lps_end, lps_low_bar
    # V-tip, Phase-D resolution above, and every gate/score) is unchanged.
    lps_zone_low = None
    lps_zone_high = None
    lps_zone_start_date = None
    lps_zone_end_date = None
    if lps_low is not None and lps_high is not None:
        zone_start = lps_start
        zone_low = lps_low
        zone_high = lps_high
        try:
            low_vals = df["Low"].iloc[lps_start:lps_end].to_numpy()
            trim = drawn_lps_zone_start(low_vals, min_descent_frac=lps_zone_draw_min_descent)
            if trim > 0:
                zone_start = lps_start + trim
                zone_low = float(low_vals[trim:].min())
                zone_high = float(df["High"].iloc[zone_start:lps_end].max())
        except (KeyError, ValueError, TypeError):
            pass
        lps_zone_low = round(zone_low, 4)
        hi = zone_high
        if hi <= zone_low:
            band = float(atr_val) if (atr_val is not None and atr_val > 0) else zone_low * 0.005
            hi = zone_low + band
        lps_zone_high = round(hi, 4)
        lps_zone_start_date = _date_at(df, zone_start)
        lps_zone_end_date = _date_at(df, lps_end - 1)

    # ── Confidence: weight Phase D heaviest (it's the region that matters) ──
    confidence = 0.0
    if a is not None:
        confidence += 0.25
    if b is not None:
        confidence += 0.25
    if d is not None:
        confidence += 0.50

    return {
        "phase_a_start_date": _date_at(df, a),
        "phase_a_end_date": _date_at(df, a_end),
        "phase_b_start_date": _date_at(df, b),
        "phase_d_start_date": _date_at(df, d),
        "phase_c_event_date": _date_at(df, c),
        "lps_zone_low": lps_zone_low,
        "lps_zone_high": lps_zone_high,
        "lps_zone_start_date": lps_zone_start_date,
        "lps_zone_end_date": lps_zone_end_date,
        "has_mini_consolidation": bool(is_inner_box or phase_d_start_bar is not None),
        "scope_confidence": round(confidence, 3),
        "phase_d_evidence_json": (
            json.dumps(phase_d.evidence, sort_keys=True)
            if phase_d.evidence else None
        ),
        "phase_a_start_bar": a,
        "phase_a_end_bar": a_end,
        "phase_b_start_bar": b,
        "phase_d_start_bar": d,
    }
