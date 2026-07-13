"""Per-mark engine agreement for the calibration ledger (v2 Add-1).

The ledger's "Engine" chip answers the operator's HEADLINE calibration
question — did the engine SURFACE a setup at my pick? (concordance, not rail
replication; operator doctrine 2026-07-11). That is exactly the harness's
election grade (``tools.agreement`` over ``tools.replay.snapped_election``),
so this reuses ``grade_one`` — the SAME function the CLI reports score, so the
chip can never drift from ``python -m tools.calibration_harness``. It is NOT
the sharper fired-in-window criterion (that replays the FULL scoring pipeline
per mark, ~1s/session, and needs a background worker — a deliberate next
layer, not this one).

Read-only + frozen-or-refuse by construction: ``grade_one`` loads frozen
frames only (never a vendor fetch), never commits. Every box mark's chip is
memoized per (mark id, birth stamp, revision, live ``manifest_hash``, tolerance
signature): a correction (revision++) or an engine change (manifest) recomputes;
a re-render never does (the review's "cached, never replay on render" mandate).
The ``created_at`` birth stamp is in the key because SQLite reuses freed rowids
and every create starts at revision 1 — without it, a mark created after a
delete could alias the deleted mark's cached (wrong) chip.
Degrade-never-500 (EC-6): one mark that throws becomes an 'error' chip, never
a failed ledger.

Heavy imports (pandas/scipy via the harness) stay function-local so importing
this module — or ``main`` for a route-registration check — is light.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("chrollo.calibration")

# Process-memo, cold after restart, recomputed lazily — the _ENGINE_READS
# precedent. Keyed on (mark_id, created_at, revision, manifest_hash, tol_sig);
# created_at makes a reused rowid a distinct key (see the module docstring).
_AGREEMENTS: dict = {}


def reset_agreement_cache() -> None:
    """Test seam: a fresh process starts empty; tests want that on demand."""
    _AGREEMENTS.clear()


def _tol_sig() -> str:
    """The tolerance/policy signature baked into the grade — part of the cache
    key so a future tolerance change invalidates stale chips (review mandate)."""
    from core.pipeline.election_identity import DEFAULT_RAIL_TOL_BOX_FRAC  # noqa: PLC0415
    from tools import replay  # noqa: PLC0415 — pandas/scipy-heavy chain
    from tools.agreement import DEFAULT_SPAN_OVERLAP_MIN  # noqa: PLC0415
    return (f"rail{DEFAULT_RAIL_TOL_BOX_FRAC}"
            f":span{DEFAULT_SPAN_OVERLAP_MIN}"
            f":snap{replay.SNAP_BACK_SESSIONS}")


def _live_grade(mark) -> dict:
    """Grade ONE mark through the harness's own election lens (baseline
    variant) -> the agreement fragment {outcome, rail_distances?, ...}."""
    from tools.calibration_harness import _mark_dict, grade_one  # noqa: PLC0415
    return grade_one(_mark_dict(mark), [{}])[0]


def _chip_from_fragment(frag: dict) -> dict:
    """Map an agreement fragment -> the ledger chip vocabulary.

    Concordance semantics (the operator's headline): 'surfaced' = the engine
    elects a box at the pick = match OR disagree -> green ``.ok`` (the label +
    rail Δ carry whether the geometry ALSO matches). 'no read' = the engine
    elects nothing there -> red ``.miss`` (the real calibration miss). Anything
    the engine cannot fairly see (span off the frame's left edge, frozen basis
    lost) is neutral 'untested' — never a red miss it didn't earn.
    """
    outcome = frag.get("outcome")
    if outcome in ("match", "disagree"):
        dist = frag.get("rail_distances") or {}
        delta = max(dist.get("r_frac", 0.0), dist.get("s_frac", 0.0))
        return {"state": "ok",
                "kind": "match" if outcome == "match" else "differs",
                "rail_delta": round(delta, 3),
                "span_overlap": frag.get("span_overlap"),
                "outcome": outcome}
    if outcome == "engine_no_read":
        return {"state": "miss", "kind": "no_read", "outcome": outcome}
    if outcome == "edge_uncertain":
        return {"state": "untested", "kind": "edge",
                "outcome": outcome, "detail": frag.get("detail")}
    if outcome == "basis_mismatch":
        return {"state": "untested", "kind": "no_frame",
                "outcome": outcome, "detail": frag.get("detail")}
    # Any other taxonomy row reaching here (a negative graded by a caller that
    # didn't short-circuit it) — neutral, named, never a miss.
    return {"state": "untested", "kind": "other", "outcome": outcome}


def agreement_for_marks(marks, *, grade=None) -> dict:
    """{mark_id: chip} for a ticker's marks.

    Non-box marks are 'untested' (the chip asks about a box the mark doesn't
    have) and cost NO engine compute. Box marks grade through the memoized
    election lens. ``grade`` injects a per-mark grader in tests; when injected
    the process cache is bypassed so a fake result never pollutes the live path.
    """
    use_cache = grade is None
    grader = grade or _live_grade
    from core.freeze.manifest import manifest_hash  # noqa: PLC0415
    mh = manifest_hash()
    sig = _tol_sig()
    return {mark.id: _resolve(mark, mh, sig, grader, use_cache) for mark in marks}


def _resolve(mark, mh, sig, grader, use_cache) -> dict:
    if mark.verdict != "box":
        chip = {"state": "untested", "kind": "negative"}
    else:
        # created_at is birth-unique + immutable: a rowid reused after a delete
        # (SQLite recycles freed ids, and every create starts at revision 1) gets
        # a fresh stamp, so it can never be served the deleted mark's chip.
        key = (mark.id, mark.created_at, mark.revision, mh, sig)
        chip = _AGREEMENTS.get(key) if use_cache else None
        if chip is None:
            chip = _compute(mark, grader)
            if use_cache:
                _AGREEMENTS[key] = chip
    # Whether the engine has moved since the mark was stamped — a caveat shown
    # to the operator, not a recompute trigger (the chip already reflects the
    # CURRENT engine; the key carries mh, so a moved engine already recomputed).
    stale = bool(mark.engine_config_version) and mark.engine_config_version != mh
    return {**chip, "revision": mark.revision, "stale": stale}


def _compute(mark, grader) -> dict:
    try:
        frag = grader(mark)
    except Exception:  # EC-6: one bad mark degrades to a named chip, never a 500
        logger.exception("agreement compute failed for mark id=%s", mark.id)
        return {"state": "untested", "kind": "error", "outcome": "engine_error"}
    return _chip_from_fragment(frag)
