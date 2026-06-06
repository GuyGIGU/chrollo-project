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
               (bc_anchor_bar -> phase_b_start_bar)
    Phase B  — the working base / cause-building region. In the chart
               validation overlay it is read as the whole base from
               phase_b_start_bar through the setup end, with Phase D as an
               overlapping right-side subregion rather than a hard cutoff.
    Phase D  — the right-most region where the LPS is evaluated.
               Anchored on the LPS (always the foundation). When the detector
               selected an inner sub-box (a mini-consolidation), Phase D is that
               inner box; otherwise it's the LPS shelf.
    Phase C  — optional spring marker: only when the LPS undercut support
               (zone_type == "UNDERCUT_S" / a REBOUND).

The LPS zone (``lps_zone_low``/``lps_zone_high`` + ``lps_zone_start_date``/
``lps_zone_end_date``) is the bounding box of the exact LPS candidate bars —
Chrollo's convention highlights those specific bars, so the zone wraps them
tightly in both price and time rather than stretching a level across Phase D.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


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
                           phase_d_start_bar: Optional[int] = None) -> Optional[int]:
    """Phase-D right-most-region start bar, df-positional. Pure.

    Single source of truth for the Phase-D boundary, shared between the scoping
    overlay (``scope_consolidation``) and the bin-feature measurer
    (``core.structure.bin_features``) so the drawn band and the measured Phase-D
    bin can never drift apart:

      - phase_d_start_bar -> the inner base anchors Phase D (the parent+inner
                             model's proxy for the B->D split when there is no
                             Phase C), pulled earlier if the LPS starts before it
                             (the LPS always sits inside Phase D).
      - inner sub-box  -> legacy path where the mini-consolidation replaced the
                          active box: use that box start.
      - otherwise      -> the final third of the base (the right-most side),
                          pulled earlier if the LPS itself starts before it (the
                          LPS always sits inside Phase D). A fraction, not the
                          2-7 bar LPS window, so it reads as a region. The exact
                          fraction is the first knob the fidelity grader will
                          calibrate. ``None`` when there is no LPS window.

    The result is clamped on-frame and never allowed to invert the body start
    ``b``: when the base is too young to separate body from Phase D it
    collapses to ``b`` rather than crossing it.
    """
    if phase_d_start_bar is not None:
        d = phase_d_start_bar
        if has_lps_window:
            # The LPS always sits inside Phase D. The inner base anchors Phase D,
            # but if the detected LPS starts before it (e.g. it fell back to the
            # parent box), pull Phase D back to the LPS so it stays contained.
            # No-op in the usual case where the LPS is rooted in the inner.
            d = min(d, lps_start)
    elif is_inner_box:
        d = box_start
    elif has_lps_window:
        final_third = box_start + (2 * base_len) // 3
        d = max(box_start, min(final_third, lps_start))
    else:
        d = None
    if d is not None:
        d = max(0, min(d, last))
        if b is not None and d < b:
            d = b
    return d


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
        lps_offset, lps_length: locate the LPS window: it ends at
            ``len(df) - lps_offset`` (exclusive) and spans ``lps_length`` bars.
        lps_zone_type: "INSIDE" / "OVERSHOOT_R" / "UNDERCUT_S". A spring
            (UNDERCUT_S) emits a Phase C marker.
        atr_val: ATR snapshot used for the support-band thickness.

    Returns a JSON-safe dict (un-prefixed keys; the pipeline prefixes them):
        phase_a_start_date, phase_b_start_date, phase_d_start_date,
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
        "phase_b_start_date": None,
        "phase_d_start_date": None,
        "phase_c_event_date": None,
        "lps_zone_low": None,
        "lps_zone_high": None,
        "lps_zone_start_date": None,
        "lps_zone_end_date": None,
        "has_mini_consolidation": bool(is_inner_box or phase_d_start_bar is not None),
        "scope_confidence": 0.0,
        "phase_a_start_bar": None,
        "phase_b_start_bar": None,
        "phase_d_start_bar": None,
    }
    if n == 0 or base_len <= 0:
        return empty

    last = n - 1

    # ── Phase A / Phase B anchors (df-positional) ───────────────────────────
    a = bc_anchor_bar if (bc_anchor_bar is not None and 0 <= bc_anchor_bar < n) else None
    b = phase_b_start_bar if (phase_b_start_bar is not None and 0 <= phase_b_start_bar < n) else None
    # Degenerate ordering (climax after body start) → drop the lead-in pair
    # rather than draw an inverted band.
    if a is not None and b is not None and a > b:
        a = None
        b = None

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
    # Boundary rule lives in _resolve_phase_d_start (shared with
    # core.structure.bin_features so the drawn band and the measured Phase-D
    # bin use one rule): inner sub-box -> its start; else the final third of the
    # base, pulled earlier if the LPS begins before it; clamped on-frame and
    # never allowed to cross the body start b.
    d = _resolve_phase_d_start(
        box_start=box_start, base_len=base_len, last=last,
        is_inner_box=is_inner_box, has_lps_window=has_lps_window,
        lps_start=lps_start, b=b, phase_d_start_bar=phase_d_start_bar,
    )

    # ── Phase C spring marker (UNDERCUT_S only) — the undercut low (V tip) ───
    c = lps_low_bar if (lps_zone_type == "UNDERCUT_S" and lps_low_bar is not None) else None

    # ── LPS zone: the bounding box of the exact LPS candidate bars ──────────
    # Chrollo's convention highlights the specific bars that form the LPS, so
    # the zone wraps those bars tightly in BOTH axes: price spans their true
    # [min low, max high], and the start/end dates bound them in time. A flat
    # one-bar window still needs drawable height, so atr_val is a visibility
    # floor only (never the band's meaning).
    lps_zone_low = None
    lps_zone_high = None
    lps_zone_start_date = None
    lps_zone_end_date = None
    if lps_low is not None and lps_high is not None:
        lps_zone_low = round(lps_low, 4)
        hi = lps_high
        if hi <= lps_low:
            band = float(atr_val) if (atr_val is not None and atr_val > 0) else lps_low * 0.005
            hi = lps_low + band
        lps_zone_high = round(hi, 4)
        lps_zone_start_date = _date_at(df, lps_start)
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
        "phase_b_start_date": _date_at(df, b),
        "phase_d_start_date": _date_at(df, d),
        "phase_c_event_date": _date_at(df, c),
        "lps_zone_low": lps_zone_low,
        "lps_zone_high": lps_zone_high,
        "lps_zone_start_date": lps_zone_start_date,
        "lps_zone_end_date": lps_zone_end_date,
        "has_mini_consolidation": bool(is_inner_box or phase_d_start_bar is not None),
        "scope_confidence": round(confidence, 3),
        "phase_a_start_bar": a,
        "phase_b_start_bar": b,
        "phase_d_start_bar": d,
    }
