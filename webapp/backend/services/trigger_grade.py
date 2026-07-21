"""Trigger grade — did the engine surface the pick at or before the operator's
buy? (Calibration Workbench, Task 11).

The Trigger is the operator's entry (the LPS-high breakout). Grading it asks a
no-lookahead question — at each session the engine reads only bars <= that
session — and resolves to THREE honest outcomes: fired at/before the Trigger,
fired after, never fired. "Never fired" is its OWN outcome, never collapsed into
"late": branding a setup the engine never elected as a late buy would be a lie.

This is a THIN layer over the existing FIRED replay (``services.calibration_fired``
-> ``tools.calibration_harness.fired_one``), NOT a second engine path: ``fire_date``
is the session the engine would have surfaced the pick — computed once inside the
one replay seam that already enforces no-lookahead per session and matches
``--fired`` — and the Trigger adds only a date COMPARISON on top. One replay feeds
both the fired chip and this grade (the Trigger is a comparison, not a second
~1s pass).

Agreement is reported in the operator's PRIORITY ORDER — (1) Box and its
Resistance/Support, (2) the LPS, (3) the Trigger timing — so a gap at the top is
never masked by a matched lower one.

Pure + import-anywhere: ``classify_fire_timing`` is the load-bearing decision and
carries no engine/pandas dependency; the coordinator reuses the memoized fired
seam and never touches the engine directly.
"""
from __future__ import annotations


def classify_fire_timing(fire_date, trigger_date) -> str:
    """The no-lookahead timing decision. ``fire_date`` is the engine's surface
    session (``None`` = never elected); ``trigger_date`` is the operator's buy.
    ISO ``YYYY-MM-DD`` strings compare chronologically.

    An absent read is ``never`` — NEVER ``after`` — so a setup the engine did not
    elect is never branded a late buy. The buy can land on the as-of bar itself,
    so an on-Trigger fire is ``at_or_before``.
    """
    if fire_date is None or trigger_date is None:
        return "never"
    return "at_or_before" if fire_date <= trigger_date else "after"


def _lps_marked(mark) -> bool:
    return any(getattr(e, "event_type", None) == "lps" for e in (mark.events or []))


def grade_one(mark, chip) -> dict:
    """Priority-ordered Trigger grade for one box mark from its FIRED ``chip``.
    Returns a graded dict, or a ``{'kind': ...}`` sentinel for the non-gradeable
    states (no Trigger marked / the fired replay still computing)."""
    if mark.verdict != "box" or mark.trigger_date is None:
        return {"kind": "no_trigger"}
    if chip is None or chip.get("state") == "pending":
        return {"kind": "pending"}
    elected = chip.get("state") == "ok"
    fire_date = chip.get("fire_date")  # present only when the engine fired
    return {
        "kind": "graded",
        # (1) HIGHEST priority — does the engine elect a box at his rails, and how
        # far off are they (box-height fraction, from the fired lens)?
        "box": {"elected": elected, "rail_delta": chip.get("rail_delta")},
        # (2) the LPS the operator marked. The engine's elected box is the LPS's
        # container; a precise engine-LPS match is a measure-first follow-up, so
        # this reports the operator's mark + whether a box was elected around it.
        "lps": {"operator_marked": _lps_marked(mark),
                "engine_box_elected": elected},
        # (3) LOWEST priority — the fired-at/before/after-Trigger timing, grounded
        # in the real fire session (never "no read" collapsed into "late").
        "timing": {"outcome": classify_fire_timing(fire_date, mark.trigger_date),
                   "fire_date": fire_date, "trigger_date": mark.trigger_date},
    }


def trigger_grade_for_marks(marks, *, fired=None) -> dict:
    """``{marks: {id: grade}, computing}`` for a ticker's marks. Reuses the
    memoized FIRED replay (only for marks that actually carry a Trigger, so a
    setup with no buy costs no compute); ``fired`` is injectable for tests. A
    cache miss streams as ``pending`` exactly like ``/fired`` — the client polls."""
    triggered = [m for m in marks
                 if m.verdict == "box" and m.trigger_date is not None]
    if fired is None:
        if triggered:
            from services.calibration_fired import fired_for_marks  # noqa: PLC0415
            fired = fired_for_marks(triggered)
        else:
            fired = {"marks": {}, "computing": False}
    chips = fired.get("marks", {})
    out = {m.id: grade_one(m, chips.get(m.id)) for m in marks}
    return {"marks": out, "computing": bool(fired.get("computing"))}
