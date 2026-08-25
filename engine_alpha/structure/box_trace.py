"""Trace plumbing for the box election cascade.

The election narrates itself into an optional ``trace`` list — every examined
R/S pair gets a verdict record, and the traversal gate annotates the record it
judged. Both the gate layer and the election layer write through these two
helpers, so they live in a leaf module below both (no cycles, one shape).

Split out of ``box_primitives`` 2026-07-18 (Purity task 8) as a pure
structural move — both functions verbatim.
"""
from __future__ import annotations

from engine_alpha.election_identity import framing_window_key

__all__ = ["CASCADE_STAGES", "_trace_pair", "_trace_find"]

# The cascade's closed stage vocabulary, in kill-DEPTH order — how far a
# candidate got before dying. The pair gates run width → … → traversal;
# "story" is the last-resort pool's own admission judgment; "rescue_unused"
# and "dethroned" are POLICY kills of framings that had already PASSED every
# pair gate (a strict election discards the rescued pool; the dethrone rule
# drops a stale rescue-propped pair), so they rank deeper than any gate
# death; "selection" annotates only the elected winner and never appears on
# a rejected record. This tuple is the ONE owning declaration — trace_export
# derives its depth ranking from it (council review 2026-08-05, finding 9: a
# hand-typed subset over there shipped already drifted, ranking the two
# policy kills below a width death).
CASCADE_STAGES = ("width", "window", "respect", "occupancy", "traversal",
                  "story", "rescue_unused", "dethroned", "selection")

# Identity slots of the Candidate tuple (``box_primitives.Candidate`` owns
# the ORDER; this leaf cannot import it without a cycle). Named here so the
# framing-identity read below is loud instead of bare magic indices, and
# PINNED against ``Candidate._fields`` in tests/test_framing_identity.py —
# a slot insertion over there goes RED here instead of silently skewing
# every trace annotation (2026-08-25 sweep; the recorded arity-trap class).
_CAND_R_ANCHOR_BAR = 7
_CAND_S_ANCHOR_BAR = 8
_CAND_START = 9


def _trace_pair(trace, verdict, stage, detail, R_val, S_val, box_width,
                r_anchor_bar, s_anchor_bar, cand_start, rescued=False,
                legs=None):
    """Record one pair-cascade entry (the election narrating itself).

    No-op when ``trace`` is None — the live path never pays for it. Bars are
    window-relative here; ``validate_equilibrium`` rebases them df-positional.

    ``legs``: optional list of structured leg records
    (``box_gates._leg_record`` — leg id + measured statistic + threshold as
    NUMBERS) for a rejection; the ``detail`` sentence is derived from the same
    numbers, so downstream instruments read the records and never re-parse
    prose (near-miss lane Task 1 seam contract).
    """
    if trace is None:
        return
    trace.append({
        "r_anchor_bar": int(r_anchor_bar),
        "s_anchor_bar": int(s_anchor_bar),
        "cand_start": int(cand_start),
        "R": round(float(R_val), 4),
        "S": round(float(S_val), 4),
        "box_width": round(float(box_width), 4),
        "verdict": verdict,        # "rejected" | "valid" | "elected"
        "stage": stage,            # one of CASCADE_STAGES (None on a valid record)
        "detail": detail,
        "rescued": bool(rescued),
        "traversal": None,
        "legs": legs,
    })


def _trace_find(trace, cand):
    """The 'valid' cascade record belonging to candidate tuple ``cand`` —
    matched on the ONE in-window framing identity (Task 2: anchors + start;
    window-relative, so only valid against records from the same call)."""
    key = framing_window_key(cand[_CAND_R_ANCHOR_BAR],
                             cand[_CAND_S_ANCHOR_BAR],
                             cand[_CAND_START])
    for rec in trace:
        if rec["verdict"] == "valid" \
                and framing_window_key(rec["r_anchor_bar"], rec["s_anchor_bar"],
                                       rec["cand_start"]) == key:
            return rec
    return None
