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
behind ``BAND_RAILS_ENABLED`` (LIVE since 2026-07-16; last-resort semantics
unchanged): consulted only when the strict AND rescued pools are both empty,
so an ordinary box's election can never move. ``qualify_pair_events`` has two
further consumers: ``phase_features._terminal_shakeout`` (the flag-dark
terminal-shakeout Phase-C fallback) and the near-miss lane's deferred
completion (``near_miss.py``).
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


def _qualify_band(closes, lows, highs, S_val, R_val, buf,
                  max_depth: Optional[float] = None) -> Optional[dict]:
    """One pair's excursion qualification. None = a span failed (breakdown /
    breakout / unresolved at the edge), disqualifying the pair entirely.

    Below-rail events form a **sequence-aware HOLD chain** (the operator's
    BODI ruling: successively deeper springs that each reclaim and hold are
    one progressive Phase-C step-down, not a breakdown): an earlier event's
    extreme may be undercut ONLY by a later qualified below-rail event — the
    working floor steps to the most recent event's extreme — non-event bars
    must respect that standing floor, and the FINAL event answers the
    original never-undercut rule against all remaining tape. A pure
    relaxation: every window the old per-event rule accepted still
    qualifies. Gap-merging runs BEFORE the chain is considered —
    forgiveness relates distinct merged events, never bars inside one
    episode. The above-rail FAIL-BACK rule is untouched.

    ``max_depth`` (price units; the caller derives it from
    ``BAND_EVENT_MAX_DEPTH_ATR``) caps how far below the RAIL a qualified
    event may dig — deeper is a genuine breakdown, never a terminal shakeout
    (the EGBN over-reach ruling: a 7.68-ATR excision electing a stale box is
    the failure this cap exists to kill). ``None`` skips the cap (unit-test
    seam only; the production caller always supplies it).
    """
    below = closes < (S_val - buf)
    above = closes > (R_val + buf)
    n = len(closes)
    excursions = []

    below_spans = _merge_spans(_spans(below), settings.MAX_CONSECUTIVE_OUTSIDE_DAYS)
    for i, (start, end) in enumerate(below_spans):
        if end >= n:
            return None            # still outside at the window edge: unresolved
        if (end - start) > settings.BAND_EVENT_MAX_BARS and not settings.DEPTH_CAPS_GRADED_ENABLED:
            return None            # months below the rail is a markdown leg, not an episode (point 8, step 7: no day count)
        extreme = float(lows[start:end].min())
        if max_depth is not None and (S_val - extreme) > max_depth:
            return None            # beyond terminal-shakeout scale: a breakdown
        # HOLD with event-forgiveness: after this event's reclaim the working
        # floor is THIS event's extreme, and it must hold until the next
        # qualified event's own dig (which is forgiven — the floor then steps
        # to that event). The last event answers for all remaining tape: the
        # original unconditional never-undercut rule. This is a pure
        # relaxation — every single-event window is judged exactly as before.
        next_start = below_spans[i + 1][0] if i + 1 < len(below_spans) else n
        if end < next_start and float(lows[end:next_start].min()) < extreme:
            return None
        excursions.append({"kind": "below", "start": int(start), "end": int(end),
                           "extreme": extreme, "reclaim_bar": int(end)})

    for start, end in _merge_spans(_spans(above),
                                   settings.MAX_CONSECUTIVE_OUTSIDE_DAYS):
        if end >= n:
            return None            # still outside at the window edge: unresolved
        # A poke is SHORT: above the rail the band pool grants no more patience
        # than the respect gate's own forgiveness horizon — a multi-week stay
        # above R is a departure (the range is not in force), not an event.
        # (DBD negative-corpus regression at the 2026-07-16 flip: a 15-bar,
        # 4.1-ATR rally above R rode the uncapped above loop into a tier-S
        # dead-space election.)
        if (end - start) > settings.MAX_CONSECUTIVE_OUTSIDE_DAYS:
            return None
        extreme = float(highs[start:end].max())
        # FAIL-BACK: the poke high is never exceeded after the return.
        if float(highs[end:].max()) > extreme:
            return None
        excursions.append({"kind": "above", "start": int(start), "end": int(end),
                           "extreme": extreme, "reclaim_bar": int(end)})

    judged = np.ones(n, dtype=bool)
    for e in excursions:
        judged[e["start"]:e["end"]] = False
    # The pair must still frame a real, worked window after excision.
    if int(judged.sum()) < settings.MIN_BASE_DAYS:
        return None
    return {"R": float(R_val), "S": float(S_val),
            "judged": judged, "excursions": excursions}


def cluster_rails(highs, lows, atr_val, *, min_rest: Optional[int] = None,
                  tol_atr: Optional[float] = None):
    """The representative RESTING extremes of a window — cluster-anchored rail
    levels (Rail Program Task 6; measure-only, no live caller yet).

    Rails sit at bar High/Low — the operator's rule. The question a
    wick-inflated window poses (NKTR) is WHICH bars' extremes define the rail:
    the level several bars genuinely rest at, or the one outlier wick. This
    statistic answers with a pure counting rule over the window's own bars:

      R = the HIGHEST high supported by >= ``min_rest`` bars whose highs rest
          within ``tol_atr`` * ATR of it (the bar itself counts);
      S = the LOWEST low with the mirrored support.

    Never mean/std — the outlier inflates those; a count simply skips it.
    Defaults are the touch machinery's own constants
    (``EQ_MIN_TOUCHES_PER_RAIL`` / ``TOUCH_TOLERANCE_ATR``): the cluster rail
    is the outermost level the touch gate itself would call worked — no new
    calibration knob is introduced by the statistic.

    Pinned routes: NaN extremes are excluded (never a candidate level, never
    support); a non-finite or non-positive ATR returns ``(None, None)``; bars
    sharing one extreme value propose one identical level, so the tie-break is
    the value itself (fixed by construction). Suffix-precomputable: support is
    pairwise ``|x_i - x_j| <= tol`` counting, so every suffix window of an eq
    window derives from one vectorized pass. (The rail-placement program this
    statistic served closed 2026-07-25 with every lever ruled NO — the pure
    form is retained as the measured reference; validation record at
    docs/archive/tools/cluster_rail_validation.py.)

    Returns ``(R, S)``; either side is ``None`` when no level has enough
    support.
    """
    if atr_val is None or not np.isfinite(atr_val) or atr_val <= 0:
        return None, None
    k = settings.EQ_MIN_TOUCHES_PER_RAIL if min_rest is None else int(min_rest)
    tol = ((settings.TOUCH_TOLERANCE_ATR if tol_atr is None else float(tol_atr))
           * float(atr_val))

    def _outermost(values, take_max: bool):
        v = np.asarray(values, dtype=float)
        v = v[np.isfinite(v)]
        if len(v) < k:
            return None
        support = (np.abs(v[:, None] - v[None, :]) <= tol).sum(axis=1)
        qualified = v[support >= k]
        if len(qualified) == 0:
            return None
        return float(qualified.max() if take_max else qualified.min())

    return _outermost(highs, True), _outermost(lows, False)


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
    # ATR quarantine: a non-finite or non-positive ATR would make the band
    # masks silently all-False (NaN comparisons) and the depth cap meaningless
    # — refuse event-typing outright; the strict path already handled the pair.
    if atr_val is None or not np.isfinite(atr_val) or atr_val <= 0:
        return None
    closes = eq_df["Close"].values.astype(float)
    lows = eq_df["Low"].values.astype(float)
    highs = eq_df["High"].values.astype(float)
    buf = _band_buffer(atr_val)
    # Point 8 of the final method (step 7, dark, DEPTH_CAPS_GRADED_ENABLED): no
    # depth number refuses a below-rail event; the depth stays a fact.
    max_depth = (None if settings.DEPTH_CAPS_GRADED_ENABLED
                 else settings.BAND_EVENT_MAX_DEPTH_ATR * float(atr_val))
    read = _qualify_band(closes, lows, highs, S_val, R_val, buf, max_depth=max_depth)
    if read is None:
        return None
    # A terminal shakeout ends a MATURED cause: the judged (post-excision)
    # window must be a full worked base at TWICE the bare minimum — the pool's
    # extra grants (class width, event excision) are earned by extra cause.
    # (SPCB negative-corpus regression at the 2026-07-16 flip: a 34-bar
    # high-flag — the box's left half was the +35% rally leg itself — scraped
    # every gate on 30 judged churn bars and elected tier A.)
    if int(read["judged"].sum()) < 2 * settings.MIN_BASE_DAYS:
        return None
    deep = [e for e in read["excursions"]
            if e["kind"] == "below"
            and (e["end"] - e["start"]) >= settings.BAND_EVENT_MIN_BARS
            and e["extreme"] < S_val - 2.0 * buf]
    if not deep:
        return None
    # The qualifying deep events ride along: the Phase-C feed types the LAST
    # one as the box's terminal shakeout (phase_features._terminal_shakeout).
    read["deep"] = deep
    return read
