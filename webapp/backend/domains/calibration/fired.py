"""Per-mark FIRED-in-window grade for the calibration ledger (the "Engine"
chip). The operator's real satisfaction bar (doctrine 2026-07-11): would this
pick have popped up on the nightly screener in real trading time? That runs
the FULL pipeline (`domains.calibration.grading.fired_one` -> the door's
`evaluate_ticker`) over the mark's fair window — ~1s/session, up to ~10s for a
no-fire mark — so it CANNOT compute inside a request (the backend rule forbids
blocking on long work).

Architecture: a single background worker (never blocks the request thread), a
process-memo cache keyed per (mark id, created_at, revision, manifest_hash,
fired-policy sig), and a `computing` flag the frontend polls until it settles.
`created_at` is in the key because SQLite recycles rowids. One worker means
fired computes never run concurrently with each other; the reader carries no
shared mutable state and the baseline walk mutates no setting, so one worker
is enough (a second worker OR a flag-mutating variant would need a global
engine lock — noted, not needed for baseline).

Chip vocabulary: green **fired** (`fired · <tier> · Δ<rail>`), red **missed**
(`missed · <state word>` — the reader's own state word on his day, with its
box and the reason from its own trail in the detail), neutral **untested** (a
negative, or an unassessable basis/eval). Read-only + degrade-never-500 by
construction. Heavy imports stay function-local so importing this module (or
`main`) starts no worker and pulls no pandas.
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
    from core.calibration.agreement import DEFAULT_RAIL_TOL_BOX_FRAC  # noqa: PLC0415
    from domains.calibration.grading import (  # noqa: PLC0415
        FIRED_WINDOW_SESSIONS,
        HARNESS_POLICY_VERSION,
    )
    return (f"v{HARNESS_POLICY_VERSION}:win{FIRED_WINDOW_SESSIONS}"
            f":rail{DEFAULT_RAIL_TOL_BOX_FRAC}")


# ── miss reason (why the reader passed on his mark) ───────────────────

def _new_reader_reason(ticker, chart) -> dict:
    """Why the reader passed on his mark, in its own words (go-live plan,
    task 5): its state word as the stage, and its box and the reason from its
    own trail as the detail — the box step, then every LPS step, said as the
    reader said them. Never "no box" for a chart it never read: the universe
    door's refusal is "not scanned", a refused read "the read failed"."""
    from engine_alpha import gate  # noqa: PLC0415 - the ONE reader door

    watch: dict = {}
    read = gate.read_record(ticker, chart, watch=watch)
    if read is None:
        return {"stage": "not scanned",
                "detail": "the new reader never read this chart: the universe door "
                          f"refused it ({watch.get('why')})"}
    if read.failed:
        return {"stage": "the read failed",
                "detail": f"the new reader could not read this chart: {read.refusal}"}
    said = [s.saying for s in read.trail if s.stage in ("box", "LPS")]
    if read.parent is None:
        # No box: the walk's last word is the trend end it read, or nothing at all.
        ends = [s.saying for s in read.trail if s.stage == "trend end"]
        said = [f"{ends[-1]}; no pair of swing ends became a box after it" if ends
                else "it found no end of a trend to read a box from"]
    return {"stage": read.state, "detail": "the new reader: " + "; ".join(said)}


def _miss_reason(mark_dict, *, frame_loader=None) -> dict | None:
    """The reader's own record at the mark's as-of -> why it passed on his
    box (``_new_reader_reason``). None when the frame is unavailable (degrade
    to a reasonless 'missed')."""
    import pandas as pd  # noqa: PLC0415

    from webapp.backend import frame_store  # noqa: PLC0415
    loader = frame_loader or frame_store.load_frame
    frozen = loader(mark_dict["ticker"], mark_dict["as_of_date"],
                    digest=mark_dict.get("frame_digest"))
    if frozen is None:
        return None
    # The chart as the fired walk read it on his day: the frame cut there.
    return _new_reader_reason(mark_dict["ticker"],
                              frozen.loc[:pd.Timestamp(mark_dict["as_of_date"])])


# ── fired grade -> chip ──────────────────────────────────────────────

def _rail_delta(mark_dict, frag):
    """Max per-rail distance (box-height fraction) of the fired rails from the
    drawn rails."""
    from core.calibration.agreement import rail_distances  # noqa: PLC0415
    r, s = mark_dict.get("resistance"), mark_dict.get("support")
    read_r, read_s = frag.get("fire_R"), frag.get("fire_S")
    if r is None or s is None or r <= s or read_r is None or read_s is None:
        return None
    try:
        d = rail_distances(r, s, float(read_r), float(read_s))
    except (ValueError, TypeError):
        return None
    return round(max(d["r_frac"], d["s_frac"]), 3)


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
                "rails_within_tol": bool(frag.get("fire_rails_within_tol"))}
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
    from engine_alpha.stamp import manifest_hash  # noqa: PLC0415
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
