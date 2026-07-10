"""Deep-excursion (terminal-shakeout) event qualification for the pair
election (Event Map Task 11).

The zigzag pair election anchors rails at the CHRONOLOGICAL swing extremes —
the operator's own rule ("I anchor Resistance and Support from the swings in
chronological order and see if the structure holds", wick to wick, end to
end). That is right for most boxes — but a base whose range carries one
violent, later-reclaimed excursion (BODI: the Feb collapse the operator rules
a PHASE C terminal-shakeout spring, "not a box break") can never elect: the
event span leaves a weeks-long run below the rail (respect-reject), and the
pair's wick-measured width runs past the ordinary MAX_BOX_WIDTH gate.

This module supplies the event half of the corrected read, pure and
measure-first:

* **excursion spans** — contiguous runs whose closes leave the ATR-buffered
  rails of a chronological pair. Each below-rail span must satisfy the spring
  invariants at terminal-shakeout scale: penetration -> RECLAIM (closes return
  inside) -> HOLD (its extreme is never undercut afterwards). Above-rail spans
  must fail back inside and never be exceeded afterwards. A non-qualifying
  span disqualifies the pair — a breakdown/breakout, exactly as today.
* the **judged window** — a boolean mask excluding qualified spans. The caller
  runs the UNCHANGED respect/occupancy/traversal gates full-strength over the
  masked bars; the excursion bars answer to the stricter reclaim/fail-back
  rules above instead. Nothing is excused and no gate is weakened.

The one calibrated concession this class carries: a pair holding at least one
qualified DEEP below-rail event may measure up to ``BAND_MAX_BOX_WIDTH``
(wick-to-wick, the operator's basis) instead of ``MAX_BOX_WIDTH`` — the
allowance exists ONLY when the event does, so it can never act as a general
width loosening.

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


def _merge_spans(spans: list[tuple[int, int]], gap: int) -> list[tuple[int, int]]:
    """Merge same-side spans separated by at most ``gap`` inside-bars: a deep
    episode is ONE event from first penetration to final reclaim (spring then
    test — a brief return inside shorter than the respect gate's own
    outside-run cap does not end it)."""
    if not spans:
        return spans
    merged = [spans[0]]
    for start, end in spans[1:]:
        if start - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _qualify_band(closes, lows, highs, S_val, R_val, buf) -> Optional[dict]:
    """One pair's excursion qualification. None = a span failed (breakdown /
    breakout / unresolved at the edge), disqualifying the pair entirely."""
    below = closes < (S_val - buf)
    above = closes > (R_val + buf)
    n = len(closes)
    excursions = []
    for kind, mask in (("below", below), ("above", above)):
        for start, end in _merge_spans(_spans(mask),
                                       settings.MAX_CONSECUTIVE_OUTSIDE_DAYS):
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
    # The pair must still frame a real, worked window after excision.
    if int(judged.sum()) < settings.MIN_BASE_DAYS:
        return None
    return {"R": float(R_val), "S": float(S_val),
            "judged": judged, "excursions": excursions}


def qualify_pair_events(eq_df, S_val: float, R_val: float,
                        atr_val: float) -> Optional[dict]:
    """Qualify one CHRONOLOGICAL pair's window: type its excursions or refuse.

    Returns ``None`` unless every band-leaving span qualifies AND at least one
    qualified below-rail event is DEEP — a multi-bar span whose extreme digs
    beyond the buffered rail by more than the buffer again (an ordinary spring
    poke is the respect gate's business, not an event; without this floor the
    class width allowance would leak to every mildly-springy wide box).
    """
    if eq_df is None or len(eq_df) < settings.MIN_BASE_DAYS:
        return None
    closes = eq_df["Close"].values.astype(float)
    lows = eq_df["Low"].values.astype(float)
    highs = eq_df["High"].values.astype(float)
    buf = _band_buffer(atr_val)
    read = _qualify_band(closes, lows, highs, S_val, R_val, buf)
    if read is None:
        return None
    deep = [e for e in read["excursions"]
            if e["kind"] == "below"
            and (e["end"] - e["start"]) >= settings.BAND_EVENT_MIN_BARS
            and e["extreme"] < S_val - 2.0 * buf]
    if not deep:
        return None
    return read
