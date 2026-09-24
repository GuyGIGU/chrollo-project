"""Per-mark FIRED-in-window grade for the calibration ledger (the sharper
"Engine" chip). The operator's real satisfaction bar (doctrine 2026-07-11):
would this pick have popped up on the nightly screener in real trading time?
That runs the FULL scoring pipeline (`domains.calibration.grading.fired_one` ->
`_evaluate_ticker`) over the mark's fair window — ~1s/session, up to ~10s for a
no-fire mark — so it CANNOT compute inside a request (the backend rule forbids
blocking on long work).

Architecture: a single background worker (never blocks the request thread), a
process-memo cache keyed per (mark id, created_at, revision, manifest_hash,
fired-policy sig), and a `computing` flag the frontend polls until it settles.
`created_at` is in the key for the same reason as the agreement cache (SQLite
recycles rowids). One worker means fired computes never run concurrently with
each other; the engine read path carries no shared mutable state and baseline
`flag_capture` mutates nothing, so a fired compute is safe alongside the
synchronous agreement read (a second worker OR variant/flag-mutating support
would need a global engine lock — noted, not needed for baseline).

Chip vocabulary: green **fired** (`fired · <tier> · Δ<rail>`), red **missed**
(`missed · <stage>` — the structure-reject stage that killed the box at his
rails, e.g. "respect", from a read-only traced structure read), neutral
**untested** (a negative, or an unassessable basis/eval). Read-only + degrade-
never-500 by construction. Heavy imports stay function-local so importing this
module (or `main`) starts no worker and pulls no pandas.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("chrollo.calibration")

# Process-memo (cold after restart, recomputed lazily) + the queued/in-flight
# set, both guarded by _LOCK. Single worker: serialize the expensive computes.
_FIRED: dict = {}
_PENDING: set = set()
_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="calib-fired")


def reset_fired_cache() -> None:
    """Test seam — a fresh process starts empty; tests want that on demand."""
    with _LOCK:
        _FIRED.clear()
        _PENDING.clear()


def _fired_sig() -> str:
    """The fired-policy signature in the cache key — a window/tolerance change
    invalidates stale chips. Carries HARNESS_POLICY_VERSION so a grading-
    SEMANTICS change (Family-7: event-window anchoring, fire-session rails)
    invalidates chips even when every numeric constant is unchanged and the
    engine hash never rotates."""
    from engine_alpha.election_identity import DEFAULT_RAIL_TOL_BOX_FRAC  # noqa: PLC0415
    from domains.calibration.grading import (  # noqa: PLC0415
        FIRED_WINDOW_SESSIONS,
        HARNESS_POLICY_VERSION,
    )
    return (f"v{HARNESS_POLICY_VERSION}:win{FIRED_WINDOW_SESSIONS}"
            f":rail{DEFAULT_RAIL_TOL_BOX_FRAC}")


# ── miss reason (why the box at his rails was rejected) ───────────────

def _nearest_reject(trace, mark_r, mark_s) -> dict | None:
    """Across every root's box_cascade, the REJECTED candidate whose rails are
    nearest the operator's box — 'why HIS box was rejected'. Returns
    {stage, detail} or None. Pure over the trace the engine already built."""
    rejects = [c for rec in (trace or []) for c in (rec.get("box_cascade") or [])
               if c.get("verdict") == "rejected" and c.get("stage")]
    if not rejects:
        return None
    if mark_r is None or mark_s is None or mark_r <= mark_s:
        last = rejects[-1]  # no geometry to match -> the terminal reject stage
        return {"stage": last.get("stage"), "detail": last.get("detail")}
    height = abs(mark_r - mark_s) or 1.0
    best, best_dist = None, None
    for c in rejects:
        R, S = c.get("R"), c.get("S")
        if R is None or S is None:
            continue
        dist = (abs(mark_r - R) + abs(mark_s - S)) / height
        if best_dist is None or dist < best_dist:
            best, best_dist = c, dist
    if best is None:
        return None
    return {"stage": best.get("stage"), "detail": best.get("detail"),
            "rail_dist": round(best_dist, 3)}


def _miss_reason(mark_dict, *, frame_loader=None) -> dict | None:
    """Read-only traced structure read at the mark's as-of -> why the box at his
    rails was rejected. None when the frame/prep is unavailable (degrade to a
    reasonless 'missed'). Consumes the engine's EXISTING trace — no engine edit."""
    from engine_alpha.structure.narrative import read_structure  # noqa: PLC0415
    from core.calibration import replay  # noqa: PLC0415 — pandas/scipy-heavy chain
    from webapp.backend import frame_store  # noqa: PLC0415
    loader = frame_loader or frame_store.load_frame
    frozen = loader(mark_dict["ticker"], mark_dict["as_of_date"],
                    digest=mark_dict.get("frame_digest"))
    if frozen is None:
        return None
    prep = replay.prepared_frame(frozen, mark_dict["as_of_date"])
    if prep is None:
        return None
    df, atr = prep
    trace: list = []
    read_structure(df, atr, trace=trace)  # baseline; no flag mutation needed
    return _nearest_reject(trace, mark_dict.get("resistance"),
                           mark_dict.get("support"))


# ── fired grade -> chip ──────────────────────────────────────────────

def _rail_delta(mark_dict, frag):
    """Max per-rail distance (box-height fraction) of the fired rails from the
    drawn rails — the closer of the parent/inner framing the fire matched."""
    from core.calibration.agreement import rail_distances  # noqa: PLC0415
    r, s = mark_dict.get("resistance"), mark_dict.get("support")
    if r is None or s is None or r <= s:
        return None

    def _d(read_r, read_s):
        if read_r is None or read_s is None:
            return None
        try:
            d = rail_distances(r, s, float(read_r), float(read_s))
        except (ValueError, TypeError):
            return None
        return max(d["r_frac"], d["s_frac"])

    candidates = [x for x in (_d(frag.get("fire_R"), frag.get("fire_S")),
                              _d(frag.get("fire_inner_R"), frag.get("fire_inner_S")))
                  if x is not None]
    return round(min(candidates), 3) if candidates else None


def _chip_from_fired(mark_dict, frag) -> dict:
    """Map a fired_one fragment -> the ledger chip vocabulary."""
    if frag is None:  # non-box (short-circuited upstream; defensive)
        return {"state": "untested", "kind": "negative"}
    fired = frag.get("fired")
    if fired is True:
        return {"state": "ok", "kind": "fired",
                "tier": frag.get("fire_tier"),
                "rail_delta": _rail_delta(mark_dict, frag),
                "fire_date": frag.get("fire_date"),
                "rails_within_tol": bool(frag.get("fire_rails_within_tol")),
                # binding-gate margin telemetry (nullable; older results omit)
                "gate_margin": frag.get("fire_gate_margin")}
    if fired is False:
        reason = _miss_reason(mark_dict) or {}
        return {"state": "miss", "kind": "missed",
                "stage": reason.get("stage"), "detail": reason.get("detail"),
                "window": frag.get("fired_window")}
    # fired is None -> unassessable (basis / EVAL_ERROR / thin fair window)
    return {"state": "untested", "kind": "unassessable",
            "detail": frag.get("fired_detail")}


def _live_fired(mark_dict) -> dict:
    from domains.calibration.grading import fired_one  # noqa: PLC0415
    frag = fired_one(mark_dict, [{}])[0]
    return _chip_from_fired(mark_dict, frag)


def _compute_and_store(key, mark_dict, grader) -> None:
    """Worker body: grade one mark, always store SOMETHING + clear pending (so
    the `computing` flag can never hang) — EC-6 degrade-never-crash."""
    chip = {"state": "untested", "kind": "error", "outcome": "engine_error"}
    try:
        chip = grader(mark_dict)
    except Exception:  # noqa: BLE001 — one bad mark degrades to a named chip
        logger.exception("fired compute failed for mark %s@%s",
                         mark_dict.get("ticker"), mark_dict.get("as_of_date"))
    with _LOCK:
        _FIRED[key] = chip
        _PENDING.discard(key)


def fired_for_marks(marks, *, compute=None, background=True) -> dict:
    """{marks: {id: chip|pending}, computing: bool} for a ticker's marks.

    Non-box marks are 'untested' (no box to fire) and cost no compute. Box marks
    grade through the memoized fired lens; a cache miss is ENQUEUED to the
    background worker (returns 'pending' immediately) so the request never
    blocks. ``compute`` injects a grader and ``background=False`` runs it inline
    — both for tests. mark dicts are extracted here (session live) so the worker
    never touches a detached ORM row.
    """
    from engine_alpha.freeze.manifest import manifest_hash  # noqa: PLC0415
    from domains.calibration.grading import _mark_dict  # noqa: PLC0415
    grader = compute or _live_fired
    mh = manifest_hash()
    sig = _fired_sig()
    out = {}
    computing = False
    for mark in marks:
        base = {"revision": mark.revision,
                "stale": bool(mark.engine_config_version)
                and mark.engine_config_version != mh}
        if mark.verdict != "box":
            out[mark.id] = {"state": "untested", "kind": "negative", **base}
            continue
        key = (mark.id, mark.created_at, mark.revision, mh, sig)
        with _LOCK:
            chip = _FIRED.get(key)
            claim = chip is None and key not in _PENDING
            if claim:
                _PENDING.add(key)  # claim under the lock so two marks can't double-enqueue
        if claim:
            # Extract the plain dict here (session live), OUTSIDE the lock, and
            # only on a real miss — a cache hit never touches the ORM row.
            md = _mark_dict(mark)
            if background:
                _POOL.submit(_compute_and_store, key, md, grader)
            else:
                _compute_and_store(key, md, grader)  # synchronous (tests)
                with _LOCK:
                    chip = _FIRED.get(key)
        if chip is None:
            computing = True
            out[mark.id] = {"state": "pending", **base}
        else:
            out[mark.id] = {**chip, **base}
    # The policy token rides in the response so the CLIENT cache can key on it
    # too — a dashboard tab left open across a service restart must never keep
    # serving chips graded under a previous policy (Dodds, plan task 1).
    return {"marks": out, "computing": computing, "policy": f"{mh[:16]}:{sig}"}
