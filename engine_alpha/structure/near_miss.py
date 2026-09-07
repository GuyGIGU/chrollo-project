"""The near-miss lane's inline recorder (near-miss lane Task 7).

A bounded, numbers-only recorder attached at ONE seam: the outer Phase-B
consultation (``bricks.validate_equilibrium`` → the enforce-traversal
election; never the inner-box calls to the same enumeration, never the
diagnostic mirror). At each gate refusal it records the raw-numbers tuple
the gate already had in hand — no strings, no dicts, no trace
materialization — into a per-evaluation hash map keyed on the framing
identity (Task 2) PLUS the judging pool form, O(1) per refusal, first record
canonical per (framing, pool). The pool belongs in the key because the
cascade legally re-judges one framing under different laws on different
windows (full/strict, SOS-trimmed/rescued, excision-masked/band) — a
pool-blind key silently discarded every rescued and band refusal as a
"repeat" (review 2026-07-26 finding 1). Within one pool form the judged
window IS unique per evaluation, so a same-pool re-observation carries
identical numbers and bumps a counter, never a record. The archive identity
stays pool-less: the deferred cut keeps ONE row per framing by pool
precedence (strict > rescued > band), every shadowed row counted.

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
from engine_alpha.structure.box_gates import GATE_LEG_INDEX, leg_threshold
from engine_alpha.structure.gate_margins import (
    _FLOAT_DEFICIT_SETTINGS,
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
        if leg not in GATE_LEG_INDEX and leg != "occupancy":
            # The registry (+ the documented family verdict label) is the ONLY
            # legal vocabulary — a free-typed leg id would ride invisibly past
            # the completion, the screen, and the archive CHECK (review
            # 2026-07-26 finding 9); mirror of box_gates._leg_record's guard.
            raise ValueError(f"unknown gate-leg id {leg!r} recorded at a "
                             f"kill site — not in GATE_LEGS")
        off = self._offset
        win = framing_window_key(off + r_anchor_bar, off + s_anchor_bar,
                                 off + cand_start)
        key = (win, str(pool))       # one record per framing PER POOL FORM
        self.n_refusals += 1
        if key in self.records:
            self.n_repeats += 1
            return
        self.records[key] = Refusal(
            leg, pool, win[0], win[1], win[2], float(R), float(S),
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
    evidence — the report ranks within legs by native margin (Task 11).

    Each arm computes the kill leg's SIGNED margin from the kill-site
    numbers; which narrowness band then applies is dispatched through the
    ruled mapping itself (``gate_margins._FLOAT_DEFICIT_SETTINGS`` for the
    float legs, ``NEAR_MISS_MAX_QUANTA`` otherwise) — one mapping, imported,
    so a re-ruling that moves a leg between families re-scores the screen
    automatically (review 2026-07-26 finding 8, EC-18)."""
    leg = rec.leg
    if leg == "width":
        margin = rec.b - rec.a               # cap - width (b = the electing
        #                                      pool's own cap at the kill site)
    elif leg == "window":
        margin = rec.a - rec.b
    elif leg == "respect_share":
        margin = outside_allowed(leg_threshold("respect_share"),
                                 int(rec.b)) - int(rec.a)
    elif leg == "respect_run":
        margin = int(leg_threshold("respect_run")) - int(rec.c)
    elif leg == "traversal_count":
        margin = int(rec.a) - int(leg_threshold("traversal_count"))
    elif leg == "traversal_density":
        density = (rec.a / rec.b) if rec.b > 0 else 0.0
        margin = density - leg_threshold("traversal_density")
    else:
        # occupancy / crash: numbers were deliberately not computed at the
        # kill site — always finalists, completed first.
        return True, float("inf")
    setting = _FLOAT_DEFICIT_SETTINGS.get(leg)
    if setting is not None:
        return -margin <= getattr(settings, setting), margin
    return margin >= -settings.NEAR_MISS_MAX_QUANTA, margin


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
             "kill_mismatch": 0, "not_ruled": 0, "ruled": 0,
             "pool_shadowed": 0}
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
        completion_kw = {}
        if rec.pool == "band":
            # The band pool's OWN laws (review 2026-07-26 findings 1/4):
            # build legs judge the excision-masked window, width measures
            # against the band class cap, and the traversal pair judges the
            # CONTIGUOUS cand_start..+judged_len slice — exactly the windows
            # the live cascade consulted (box_gates._apply_traversal_gate).
            # The excision mask itself threads in too, so the two adjacency
            # legs (respect run, touch thirds) mirror the gate's real-position
            # read (council review 2026-09-07, finding 6).
            from engine_alpha.structure.rail_qualification import qualify_pair_events
            read = qualify_pair_events(frame.iloc[rec.cand_start:], rec.S,
                                       rec.R, atr)
            window = (None if read is None
                      else frame.iloc[rec.cand_start:][read["judged"]])
            if window is not None and len(window) != rec.judged_len:
                # The re-derived mask no longer matches the judged basis the
                # gate killed on — basis drift, counted, never completed.
                stats["completion_refused"] += 1
                continue
            completion_kw = {
                "width_max": settings.BAND_MAX_BOX_WIDTH,
                "traversal_df": frame.iloc[
                    rec.cand_start:rec.cand_start + rec.judged_len],
                "judged_mask": None if read is None else read["judged"],
            }
        else:
            window = frame.iloc[rec.cand_start:rec.cand_start + rec.judged_len]
        if window is None or len(window) < 2:
            stats["completion_refused"] += 1
            continue
        vector = complete_leg_vector(window, rec.R, rec.S, atr,
                                     **completion_kw)
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

    # ONE row per framing: the archive identity is pool-less, so when the
    # same framing rules under more than one judging law the primary law
    # wins (strict > rescued > band) and every shadowed row is counted —
    # the grain ruling of review 2026-07-26 finding 1 (operator-delegated).
    precedence = {"strict": 0, "rescued": 1, "band": 2}
    best: dict = {}
    for row in rows:
        fkey = (row["r_level"], row["s_level"],
                row["r_anchor_date"], row["s_anchor_date"])
        cur = best.get(fkey)
        if cur is None:
            best[fkey] = row
            continue
        stats["pool_shadowed"] += 1
        if precedence.get(row["pool"], 9) < precedence.get(cur["pool"], 9):
            best[fkey] = row
    return list(best.values()), stats
