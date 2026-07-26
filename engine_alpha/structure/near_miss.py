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

from engine_alpha.election_identity import framing_window_key

__all__ = ["Refusal", "NearMissRecorder"]


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
    ``begin_consultation(offset)``."""

    __slots__ = ("_offset", "records", "n_refusals", "n_repeats")

    def __init__(self) -> None:
        self._offset = 0
        self.records: dict = {}
        self.n_refusals = 0
        self.n_repeats = 0

    def begin_consultation(self, offset: int) -> None:
        self._offset = int(offset)

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
