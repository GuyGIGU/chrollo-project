"""Worked-band rail candidates + deep-excursion qualification (Event Map Task 11).

The zigzag pair election anchors rails at pivot EXTREMES (bars-not-candles).
That is right for most boxes — but a base whose range carries one violent,
later-reclaimed excursion (BODI: the Feb collapse the operator rules a PHASE C
terminal-shakeout spring, "not a box break") can never elect: every candidate S
either absorbs the excursion lows (width-reject) or leaves a weeks-long run
below the rail (respect-reject). The operator's ruling on the mark: the box is
ONE structure measured at the WORKED BAND (~17.5%), with the collapse a typed
event inside it.

This module derives that read, measure-first and pure:

* the **worked band** — the bounded-width price band where closes actually
  dwell (max close-dwell share, edges snapped to real close extremes inside
  it). "Where price dwells and turns", from the same frame the election reads.
* **excursion spans** — contiguous runs whose closes leave the ATR-buffered
  band. Each below-band span must satisfy the spring invariants at
  terminal-shakeout scale: penetration -> RECLAIM (closes return to the band)
  -> HOLD (its extreme is never undercut afterwards). Above-band spans must
  fail back inside and never be exceeded afterwards. A non-qualifying span
  disqualifies the whole read — a breakdown/breakout, exactly as today.
* the **judged window** — a boolean mask excluding qualified spans. The caller
  runs the UNCHANGED respect/occupancy/traversal gates full-strength over the
  masked bars; the excursion bars answer to the stricter reclaim/fail-back
  rules above instead. Nothing is excused and no gate is weakened.

Consumed by ``collect_zigzag_candidates`` as a LAST-RESORT candidate pool
behind ``BAND_RAILS_ENABLED`` (dark): consulted only when the strict AND
rescued pools are both empty, so an ordinary box's election can never move.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from config import settings


def _band_buffer(atr_val: float) -> float:
    # The SAME buffer the respect gate uses for its zones; wick pokes (and
    # close pokes) within it never open an excursion span.
    return settings.BOUNDARY_ATR_BUFFER * float(atr_val)


def _turn_levels(prices: np.ndarray, pivot_idx: list[int], tol: float,
                 side: str) -> list[tuple[int, float]]:
    """Cluster pivot-close prices into turn levels: each pivot's price is a
    candidate level scored by how many pivots turn within ``tol`` of it.
    Every kept cluster contributes its center AND its inner edge (the highest
    member for an S cluster, the lowest for an R cluster) — the operator's
    band is measured at the worked INNER edge, not the cluster extreme.
    Returns (count, level) pairs, strongest cluster first, deduped by tol."""
    if not pivot_idx:
        return []
    vals = prices[pivot_idx]
    scored = []
    for v in vals:
        count = int((np.abs(vals - v) <= tol).sum())
        scored.append((count, float(v)))
    scored.sort(key=lambda t: (-t[0], t[1]))
    kept: list[tuple[int, float]] = []
    for count, v in scored:
        if any(abs(v - kv) <= tol for _c, kv in kept):
            continue
        kept.append((count, v))
    kept = kept[:_MAX_LEVELS]
    out = list(kept)
    for count, v in kept:
        members = vals[np.abs(vals - v) <= tol]
        inner = float(members.max()) if side == "S" else float(members.min())
        if abs(inner - v) > 1e-9:
            out.append((count, inner))
    return out


def _turn_bands(closes: np.ndarray) -> list[tuple[float, float]]:
    """Candidate [S, R] bands from where CLOSES actually turn: order-1 pivots
    of the close series, clustered into turn levels; every (valley-cluster,
    peak-cluster) pair of valid box width holding at least ``BAND_MIN_DWELL``
    of the window's closes is a candidate, strongest turn clusters first. The
    band snaps to real close prices; dwell is a floor, never the selector —
    the election's unchanged gates + quality pick among survivors."""
    from core.structure.pivots import _find_pivots

    n = len(closes)
    if n < 3:
        return []
    peaks, valleys = _find_pivots(closes, closes, 1)
    if not peaks or not valleys:
        return []
    spread = float(np.nanmax(closes) - np.nanmin(closes))
    tol = settings.BAND_TURN_TOL_FRAC * spread
    r_levels = _turn_levels(closes, peaks, tol, "R")
    s_levels = _turn_levels(closes, valleys, tol, "S")
    out = []
    for s_count, s in s_levels:
        for r_count, r in r_levels:
            if r <= s:
                continue
            width = (r - s) / s
            if width > settings.MAX_BOX_WIDTH:
                continue
            share = ((closes >= s) & (closes <= r)).sum() / n
            if share < settings.BAND_MIN_DWELL:
                continue
            out.append((s_count + r_count, share, float(s), float(r)))
    out.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [(s, r) for _t, _sh, s, r in out[:_MAX_BANDS]]


_MAX_LEVELS = 6
_MAX_BANDS = 8


def _spans(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous True runs as [start, end) pairs."""
    out = []
    i, n = 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def _qualify_band(closes, lows, highs, S_val, R_val, buf) -> Optional[dict]:
    """One band's excursion qualification. None = a span failed (breakdown /
    breakout / unresolved at the edge), disqualifying this band entirely."""
    below = closes < (S_val - buf)
    above = closes > (R_val + buf)
    n = len(closes)
    excursions = []
    for kind, mask in (("below", below), ("above", above)):
        for start, end in _spans(mask):
            if end >= n:
                return None            # still outside at the window edge: unresolved
            if kind == "below":
                extreme = float(lows[start:end].min())
                # HOLD: the shakeout low is never undercut after the reclaim.
                if float(lows[end:].min()) < extreme:
                    return None
            else:
                extreme = float(highs[start:end].max())
                # FAIL-BACK: the poke high is never exceeded after the return.
                if float(highs[end:].max()) > extreme:
                    return None
            excursions.append({"kind": kind, "start": int(start), "end": int(end),
                               "extreme": extreme, "reclaim_bar": int(end)})

    judged = np.ones(n, dtype=bool)
    for e in excursions:
        judged[e["start"]:e["end"]] = False
    # The band must still be a real, worked window after excision.
    if int(judged.sum()) < settings.MIN_BASE_DAYS:
        return None
    return {"R": R_val, "S": S_val, "judged": judged, "excursions": excursions}


def derive_band_candidates(eq_df, atr_val: float) -> list[dict]:
    """Every qualified worked-band read for one candidate window, densest
    first. Pure, measure-only. Each read::

        {"R": float, "S": float, "judged": bool-mask,
         "excursions": [{"kind": "below"|"above", "start": int, "end": int,
                         "extreme": float, "reclaim_bar": int}, ...]}

    Bars inside qualified spans are excluded from ``judged``; everything else
    is judged by the caller's UNCHANGED gates, and the caller's standard
    quality selection picks among the survivors."""
    if eq_df is None or len(eq_df) < settings.MIN_BASE_DAYS:
        return []
    closes = eq_df["Close"].values.astype(float)
    lows = eq_df["Low"].values.astype(float)
    highs = eq_df["High"].values.astype(float)
    buf = _band_buffer(atr_val)
    reads = []
    for S_val, R_val in _turn_bands(closes):
        read = _qualify_band(closes, lows, highs, S_val, R_val, buf)
        if read is not None:
            reads.append(read)
    return reads
