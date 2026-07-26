"""The near-miss lane's inline recorder (near-miss lane Task 7).

A bounded, numbers-only recorder attached at ONE seam: the outer Phase-B
consultation (``bricks.validate_equilibrium`` → the enforce-traversal
election; never the inner-box calls to the same enumeration, never the
diagnostic mirror). At each gate refusal it records the raw-numbers tuple
the gate already had in hand — no strings, no dicts, no trace
materialization — into a per-evaluation hash map keyed on the framing
identity (Task 2), O(1) per refusal, first record canonical (one framing has
ONE judged window per evaluation, so a re-observation across consultations
carries identical numbers; it bumps a counter, never a record).

The recorder is constructed ONLY under ``settings.NEAR_MISS_LANE_ENABLED``
(read lazily at evaluation entry — AP-3) and imported ONLY there (EC-8:
flag-off is byte-identical and compute-free; every seam below receives
``None`` and skips on an ``is not None`` check exactly like the trace).
Everything downstream of the map — the bounded full-vector completion, the
ruled-cohort cut, persistence — is the DEFERRED phase (Tasks 8/9), never
pair-loop work.

MEASURE-ONLY: records refusals; moves no rail, gates nothing, scores
nothing. Zero logging on the engine path — counters only.
"""
from __future__ import annotations

from typing import NamedTuple

from config import settings
from engine_alpha.election_identity import framing_window_key
from engine_alpha.structure.box_gates import leg_threshold
from engine_alpha.structure.gate_margins import (
    NEAR_MISS_RULESET,
    coarse_failing_legs,
    complete_leg_vector,
    outside_allowed,
    ruled_near_miss,
)

__all__ = ["Refusal", "NearMissRecorder", "deferred_rows"]


class Refusal(NamedTuple):
    """One refused framing's kill-site record, positions df-ABSOLUTE (the
    recorder adds the consultation offset; window-relative bars never leave
    the seam). ``a``/``b``/``c`` are the kill-site numbers the gate had in
    hand, leg-specific:

      width           a=box_width      b=width cap        c=—
      window          a=window bars    b=floor            c=—
      respect_share   a=outside bars   b=window bars      c=max consec run
      respect_run     a=outside bars   b=window bars      c=max consec run
      crash           —                                     (eq voided; the
                                                            completion fills)
      occupancy       —                                     (family verdict
                                                            only; completion
                                                            itemizes)
      traversal_count a=full trips     b=swings           c=—
      traversal_density a=full trips   b=swings           c=—
    """
    leg: str
    pool: str            # strict | rescued | band (story stage is policy, never recorded)
    r_anchor: int
    s_anchor: int
    cand_start: int
    R: float
    S: float
    judged_len: int
    a: float = float("nan")
    b: float = float("nan")
    c: float = float("nan")


class NearMissRecorder:
    """Per-evaluation refusal map + counters. One instance per evaluated
    ticker; consultations rebase their window-relative bars through
    ``begin_consultation(offset, frame, atr)``. The frame/ATR REFERENCES
    (never copies) are the deferred phase's basis: judged windows
    re-materialize as slices of the enumeration frame, so rescued trims and
    band masks stay reconstructible after the election settles."""

    __slots__ = ("_offset", "frame", "atr", "records",
                 "n_refusals", "n_repeats")

    def __init__(self) -> None:
        self._offset = 0
        self.frame = None
        self.atr = None
        self.records: dict = {}
        self.n_refusals = 0
        self.n_repeats = 0

    def begin_consultation(self, offset: int, frame=None, atr=None) -> None:
        self._offset = int(offset)
        if frame is not None:
            self.frame = frame          # the enumeration frame (eval_df); one
            self.atr = atr              # per evaluation, identical each call

    def refusal(self, leg, pool, r_anchor_bar, s_anchor_bar, cand_start,
                R, S, judged_len, a=float("nan"), b=float("nan"),
                c=float("nan")) -> None:
        off = self._offset
        key = framing_window_key(off + r_anchor_bar, off + s_anchor_bar,
                                 off + cand_start)
        self.n_refusals += 1
        if key in self.records:
            self.n_repeats += 1
            return
        self.records[key] = Refusal(
            leg, pool, key[0], key[1], key[2], float(R), float(S),
            int(judged_len), float(a), float(b), float(c))


# ---------------------------------------------------------------------------
# The deferred phase (Task 8): bounded completion, cheapest evidence first.
# Runs ONCE per evaluation after the election settles — never in the pair
# loop. Everything below is pure compute over the recorder's map; errors
# surface (no blanket catch — Task 9's one narrow catch wraps the DB flush,
# nothing else).
# ---------------------------------------------------------------------------

def _kill_leg_screen(rec: Refusal):
    """``(possibly_ruled, cap_rank)`` — the kill leg's own narrowness, an
    EXACT necessary condition of ``ruled_near_miss``: the kill leg fails in
    every completion of this refusal (same window, same numbers), and the
    ruled form requires every failing leg narrow — so a kill leg beyond its
    band proves non-membership without completing the vector. Unknown kill
    sites (occupancy family verdict, crash) always pass with rank +inf: they
    are exactly the EGBN class the lane exists for. ``cap_rank`` orders the
    TOP-K cap only (higher = nearer); it is a bounding heuristic, never
    evidence — the report ranks within legs by native margin (Task 11)."""
    s = settings
    leg = rec.leg
    if leg == "width":
        deficit = rec.a - rec.b
        return deficit <= s.NEAR_MISS_WIDTH_DEFICIT_MAX, -deficit
    if leg == "window":
        margin = rec.a - rec.b
        return margin >= -s.NEAR_MISS_MAX_QUANTA, margin
    if leg == "respect_share":
        margin = outside_allowed(leg_threshold("respect_share"),
                                 int(rec.b)) - int(rec.a)
        return margin >= -s.NEAR_MISS_MAX_QUANTA, margin
    if leg == "respect_run":
        margin = int(leg_threshold("respect_run")) - int(rec.c)
        return margin >= -s.NEAR_MISS_MAX_QUANTA, margin
    if leg == "traversal_count":
        margin = int(rec.a) - int(leg_threshold("traversal_count"))
        return margin >= -s.NEAR_MISS_MAX_QUANTA, margin
    if leg == "traversal_density":
        density = (rec.a / rec.b) if rec.b > 0 else 0.0
        deficit = leg_threshold("traversal_density") - density
        return deficit <= s.NEAR_MISS_DENSITY_DEFICIT_MAX, -deficit
    # occupancy / crash: numbers were deliberately not computed at the kill
    # site — always finalists, completed first.
    return True, float("inf")


def deferred_rows(recorder: NearMissRecorder, *, fired: bool,
                  scan_close: float):
    """Complete the full leg vector for the deduped finalists and cut the
    RULED cohort (delegating to ``gate_margins.ruled_near_miss`` — EC-18).
    Returns ``(rows, stats)``: plain picklable dicts (they cross the worker
    pool boundary) and the no-silent-caps counters. Evidence by cost:
    margins first, the episode sentence next (one O(n) read per surviving
    row); the would-be score/tier ships NULL-until-measured (the plan's
    stated fallback — a refused framing has no election context to score)."""
    stats = {"records": int(len(recorder.records)),
             "refusals": int(recorder.n_refusals),
             "repeats": int(recorder.n_repeats),
             "screened_out": 0, "cap_dropped": 0, "completion_refused": 0,
             "kill_mismatch": 0, "not_ruled": 0, "ruled": 0}
    frame, atr = recorder.frame, recorder.atr
    if frame is None or not recorder.records:
        return [], stats

    finalists = []
    for rec in recorder.records.values():
        possible, rank = _kill_leg_screen(rec)
        if not possible:
            stats["screened_out"] += 1
            continue
        finalists.append((rank, rec))
    finalists.sort(key=lambda t: -t[0])
    k = settings.NEAR_MISS_TOP_K
    if len(finalists) > k:
        stats["cap_dropped"] = len(finalists) - k
        finalists = finalists[:k]

    from engine_alpha.structure.event_map import (
        episode_sequence_stats, read_rail_episodes_arrays)

    idx = frame.index
    rows = []
    for _rank, rec in finalists:
        if rec.pool == "band":
            from engine_alpha.structure.rail_qualification import qualify_pair_events
            read = qualify_pair_events(frame.iloc[rec.cand_start:], rec.S,
                                       rec.R, atr)
            window = (None if read is None
                      else frame.iloc[rec.cand_start:][read["judged"]])
        else:
            window = frame.iloc[rec.cand_start:rec.cand_start + rec.judged_len]
        if window is None or len(window) < 2:
            stats["completion_refused"] += 1
            continue
        vector = complete_leg_vector(window, rec.R, rec.S, atr)
        if vector is None:
            stats["completion_refused"] += 1
            continue
        if not ruled_near_miss(vector):
            stats["not_ruled"] += 1
            continue
        (failing_leg,) = coarse_failing_legs(vector)
        if rec.leg not in ("occupancy", "crash") and failing_leg != rec.leg:
            # The cascade's kill must be the vector's one failing concept on
            # the same window — a divergence is basis drift, counted loudly.
            stats["kill_mismatch"] += 1
            continue
        highs = window["High"].to_numpy(dtype=float)
        lows = window["Low"].to_numpy(dtype=float)
        closes = window["Close"].to_numpy(dtype=float)
        ep = episode_sequence_stats(
            read_rail_episodes_arrays(highs, lows, closes, rec.R, rec.S, atr),
            as_of_bar=len(window) - 1)
        stats["ruled"] += 1
        rows.append({
            "r_level": round(rec.R, 4),
            "s_level": round(rec.S, 4),
            "r_anchor_date": idx[rec.r_anchor].strftime("%Y-%m-%d"),
            "s_anchor_date": idx[rec.s_anchor].strftime("%Y-%m-%d"),
            "window_start_date": window.index[0].strftime("%Y-%m-%d"),
            "window_end_date": window.index[-1].strftime("%Y-%m-%d"),
            "pool": rec.pool,
            "kill_stage": rec.leg,
            "failing_leg": failing_leg,
            "judged_n": int(len(window)),
            "fired_night": 1 if fired else 0,
            "episode_profile": ep["profile"] or "",
            "margins": {leg: row["margin"] for leg, row in vector.items()},
            "would_be_trigger": round(rec.R, 4),   # breakout over the refused box's R
            "scan_close": float(scan_close),
            "lane_ruleset": NEAR_MISS_RULESET,
        })
    return rows, stats
