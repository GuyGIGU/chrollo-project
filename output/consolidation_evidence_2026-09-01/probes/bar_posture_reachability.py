"""Bar-posture rescue REACHABILITY — the twelve-name disclosure sheet, re-derived.

The 2026-08-31 census (`output/consolidation_evidence_2026-08-31/`) answered a
different question than the flip sheet quotes it for. It measured a WHOLESALE
in-memory basis swap at the 2026-08-27 cache edge and found twelve names the
swap would add; `probes/twelve_scope.py` then asked whether the SHIPPED lane
(the full-refusal escalation) could reach them, and called every name whose
public read returned nothing a "full refusal, second-look reachable". Three
defects in that instrument, all fixed here (council review 2026-09-01,
finding 9):

* **The public wrapper is not a verdict.** ``read_structure`` returns ``None``
  for BOTH a full refusal AND a cause-before-effect abstention, and an
  abstention is doctrinal and FINAL — the escalation returns before it arms a
  single form (``narrative.read_structure`` step 2), so a vetoed name can
  never be rescued. This probe classifies on the walk's OWN terminal verdict:
  the ``_CAUSE_VETOED`` sentinel ``_walk_structure`` returns, which is the
  identical object step 2 tests. That sentinel is the ONE declaration of
  finality in the engine, so the predicate can never drift from the policy
  (EC-3) — and, unlike a vocabulary of outcome strings, it cannot be widened
  by accident. It is NOT
  ``tools.doctrine_audit._VETO_OUTCOMES``: that frozenset answers a different
  question (which non-elections the coverage census EXCUSES rather than
  counts as a hole) and it holds ``lps_before_spring`` too, which is not
  final at all — the chronology floor ends one root's attempt and the walk
  continues to the next (``narrative.py:643-647``), so a floored name reaches
  the armed re-walk like any other refusal. Reading it as finality would have
  told the operator a rescuable name was "never reachable" and skipped its
  conversion leg (council review round two, 2026-09-01). ``_self_check``
  pins both halves against the engine on every run. FOUR verdicts, never one:
    - ``fails_prepare``        — the universe gate refuses the frame; the
                                 chart is never read, so the lane never runs.
    - ``elects_at_baseline``   — the baseline walk elects a structure; the
                                 escalation is scoped to full refusals, so
                                 the lane cannot touch this name at all.
    - ``cause_vetoed``         — a cause-before-effect abstention; doctrinally
                                 final, never reachable by any rescue.
    - ``full_refusal_reachable`` — the walk ended empty without abstaining
                                 (every root refused, chronology-floored roots
                                 included); the armed lane gets its one
                                 re-walk here.
  Reachable names are then run through the REAL armed lane (the shipped flag,
  scoped by ``tools.replay.flag_capture``) so the sheet says whether each one
  actually CONVERTS, not merely that it could be attempted.

* **Ambient-blind** (round three, 2026-09-01). The record mandates re-running
  this probe on the MORNING OF the flip sitting, when the machine may have the
  sibling contraction lane or the species preset already live. Round two read
  every leg at ambient and pinned the guard against the escalation's pass
  STAMP — so with the contraction lane live the guard aborted with "a
  chronology-floored name IS reachable — the walk continues", which is the
  opposite of what had happened (the re-walk HAD run; the senior lane simply
  named it). Now every flag that decides the escalation composition is pinned
  for both the measurement and the guard, the guard proves the policy across
  all five lane compositions by trace LENGTH rather than by stamp, and the
  stamp block carries the ambient state AND the pin side by side.

* **The pin was a hand-list, and it was short** (round four, 2026-09-01 — the
  one risk the review would not merge past). Round three pinned five flags by
  name, stamped seven, and computed ``ambient_matches_pin`` by iterating the
  FIVE, so any flag outside them was invisible to both halves. A full ambient
  sweep of all 28 flags in the engine's identity roster (2026-09-01, this
  cache, this population) found THREE that move a count through that hole,
  every one of them writing ``ambient_matches_pin: true`` over a moved sheet:

  - ``LPS_CEILING_REST_ENABLED`` — KFY stops being a full refusal and elects
    at BASELINE through that lane: the operator's headline goes from
    4-reachable / 4-converting to 3 / 3. This lane's flip sits on the SAME
    asks page as the bar-posture flip, so it may well be live on the morning
    of the sitting. (The finding the review named.)
  - ``STORY_POOL_ENABLED`` — off, the whole sheet inverts: 6 reachable, 3
    electing, and **zero** conversions. Round three STAMPED this flag and did
    not compare it, which is the two-sets defect in one line: the sidecar
    would have shown the operator ``STORY_POOL_ENABLED: false`` and told him
    on the next line that his basis was pinned.
  - ``SMA50_DIP_EXCEPTION_ENABLED`` — the universe gate softens and all three
    ``fails_prepare`` names (ICLR, MSGS, VTR) enter the read: 0 refusals at
    the gate, 5 reachable, 7 electing. It is a UNIVERSE flag, not a lane
    flag — which is exactly why a hand-list of lane names never contained it.

  The fix is therefore not a longer hand-list (the same instrument with a
  later expiry date): the pinned SET is DERIVED from the engine's own
  declaration of what decides a reading, and the stamped set IS the pinned
  set, so the two can no longer drift apart. See ``_PIN_VALUES`` /
  ``_measurement_pin`` / ``_ambient_deltas``.

* **The sheet still did not WITNESS its own conditions** (round five,
  2026-09-01). Three claims the sheet printed had nothing behind them:

  - the pin's SIZE was never asserted. The derivation was
    ``k in _PIN_VALUES or isinstance(getattr(settings, k), bool)`` checked to
    be a SUBSET of the declaration; the equality with the engine's roster
    lived entirely in that second disjunct, which reads as redundant. Delete
    it as a tidy-up and dropping a flag from the declaration shrinks the pin
    with every guard green, under a printed claim that the basis "cannot
    drift from the policy". The pin is now BUILT from the engine's set and
    asserted EQUAL to it, size included (``_measurement_pin``).
  - the honesty valve had every guard on the HELPER and none on the report
    path, so ``run`` could stamp one read of the machine and publish an empty
    delta list with nothing turning red. The ambient read is now hoisted into
    one named value the report path consumes (``_ambient_witness``) and the
    relation is re-stated over the report's own fields (``_audit_stamp``).
  - nothing witnessed that the printed counts were measured under the pin at
    all: the "measured under" identity was re-derived AFTER the loop, so the
    sheet would have printed the same words with no pin anywhere. There is
    now ONE pin site — a single ``flag_capture(**_MEASURE_PIN)`` around the
    whole ticker loop in ``run`` — the stamp records the flag state and the
    engine identity OBSERVED INSIDE it, and every measurement site refuses if
    it finds itself outside it (``_require_pinned_scope``).

* **Every census row's rails were null.** The row builder read ``Resistance``
  / ``Support``; the result dict carries ``_R`` / ``_S``. The operator's
  eyeball IS a boundary-respect judgment, so a sheet without rails asks him
  to rule on a chart it declined to describe. Rails are filled here from the
  elected structure (baseline or armed-lane) and, where nothing elects, from
  the deepest box the walk actually attempted — each row naming WHICH.

* **No stamp.** Unlike the miss-lane census this evidence carried no engine
  or population identity, so nothing distinguished a fresh read from a stale
  one. The report stamps the engine manifest hash, the cache edge it read,
  the exact population, and the exact flag state of the run (EC-13/EC-46).

Read-only: the parquet cache and twelve tickers. No archive write, no scan,
no backend. Both program flags stay DARK for the classification; the only
armed read is the scoped conversion leg, named in the stamp.

Usage (ChrolloDashboard venv python, from anywhere):
    python "output/consolidation_evidence_2026-09-01/probes/bar_posture_reachability.py"
    ... [--json OUT]     # a later sitting writes its own dated sidecar
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import pandas as pd

# The probe lives three levels under the repo root (output/<dated>/probes/);
# anchor on __file__ so a run from any cwd imports the repo packages, never a
# shadowing sibling (the documented config-shadow trap).
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools._bootstrap import configure_path, refuse_sealed_output  # noqa: E402

configure_path()

from config import settings  # noqa: E402
from engine_alpha import evaluation  # noqa: E402
from engine_alpha.freeze.manifest import (  # noqa: E402
    ENGINE_SETTINGS_KEYS,
    manifest_hash,
)
from engine_alpha.structure.narrative import (  # noqa: E402
    _CAUSE_VETOED,
    _walk_structure,
    read_structure,
)
from tools.replay import flag_capture  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_CENSUS = os.path.join(_PROJECT_ROOT, "output",
                       "consolidation_evidence_2026-08-31",
                       "bar_posture_census.json")
_DEFAULT_JSON = os.path.normpath(
    os.path.join(_HERE, "..", "bar_posture_reachability.json"))
_CACHE = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)

# Frozen replay scalars (scoring-only inputs), the replay seam's convention —
# the same pair the 08-31 census and the miss-lane census froze.
_BREADTH = 0.5
_SPY_6M = 0.0

_PLAIN = {
    "full_refusal_reachable": "full refusal - the armed lane can reach it",
    "cause_vetoed": "cause-before-effect abstention - never reachable",
    "elects_at_baseline": "elects at baseline - the lane cannot touch it",
    "fails_prepare": "fails the universe filters - the chart is never read",
}

# ── the ambient-proofing pins ───────────────────────────────────────────────
# The record mandates re-running this probe on the MORNING OF the flip
# sitting, and by then the machine may be in any flag state — the sibling
# contraction lane flipped, the ceiling-rest lane flipped, the species preset
# flipped, or any combination. Two things then have to hold, and round two got
# neither, round three got the second one only:
#
#   * the measurement must still mean what the sheet says it means. The sheet
#     claims "what the BAR-POSTURE lane buys". Read under an ambiently live
#     contraction lane, the conversion leg would arm BOTH forms and the
#     column would silently become "what the two lanes buy together"; read
#     under an ambiently live species preset, the BASELINE roster itself
#     moves and the reachability line moves with it; read under an ambiently
#     live ceiling-rest lane, a name that is a full refusal here elects at
#     baseline instead and drops out of the sheet's headline entirely.
#   * the self-check must be right in every one of those states, not abort.
#
# ROUND FOUR — the pin was a hand-list of five, and the sheet's honesty valve
# iterated that same five. Anything outside them was invisible twice over.
# Measured on this cache, 2026-09-01: `LPS_CEILING_REST_ENABLED=True` ambient
# takes KFY out of full_refusal_reachable (4 -> 3) and out of
# reachable_converting (4 -> 3), and the sidecar still wrote
# `ambient_matches_pin: true`. The operator's 4-of-12 morning sheet becomes a
# 3-of-12 sheet claiming a pinned basis it did not have.
#
# So the pinned SET is no longer named by hand. It is DERIVED from
# `manifest.ENGINE_SETTINGS_KEYS` — the engine's OWN declaration of every
# constant that decides a reading — whose completeness over the eval path is
# itself proven, not assumed: `tests/test_invariants.py::
# test_every_scoring_settings_symbol_is_in_manifest` scans every
# `settings.NAME` read by evaluation + scoring + screener + ALL of
# engine_alpha/structure/ and admits exactly three ops exclusions, none of
# them boolean. A boolean in that roster is therefore a flag that can move
# these counts, and every one of them is pinned (EC-3: the instrument's rule
# cannot drift from the engine's policy, because it IS the engine's roster).
#
# The VALUES stay declared literals below: `config.settings` is the thing that
# may have moved, so it cannot also be the reference. They are the shipped
# values of this changeset — which is the basis the 2026-08-31 census was
# measured against and the basis this sheet's reachability line is a line
# ABOUT: both program lanes dark, the sibling rescue lanes dark, the species
# story-form off, the doctrinal pair live.
_PIN_VALUES = {
    "AR_FIRST_REACTION_ENABLED": False,
    "BAND_RAILS_ENABLED": True,
    "BAR_POSTURE_RESCUE_ENABLED": False,
    "BOTTOMING_BASE_LANE_ENABLED": False,
    "CAUSE_BEFORE_EFFECT_VETO_ENABLED": True,
    "CONTRACTION_RESCUE_ENABLED": False,
    "DATA_DIVIDEND_ADJUSTED": False,
    "ELECTION_DETHRONE_ENABLED": True,
    "ELECTION_STABILITY_ENABLED": False,
    "ELECTION_TRACE_EXPORT_ENABLED": False,
    "EVENT_MAP_ENABLED": True,
    "FUNDAMENTALS_ENABLED": False,
    "HTF_CONTEXT_ENABLED": True,
    "LPS_AFTER_SPRING_ENABLED": True,
    # The measured mover round three left ambient — see the block above.
    "LPS_CEILING_REST_ENABLED": False,
    "LPS_HOLDING_SHELF_ENABLED": True,
    "LPS_OVERSHOOT_WINDOW_ATR_ENABLED": True,
    "LPS_SPREAD_MUST_DECLINE": True,
    "NEAR_MISS_LANE_ENABLED": True,
    "POWER_PLAY_PRESET_ENABLED": True,
    "POWER_PLAY_STORY_FORM_ENABLED": False,
    "RS_LINE_ENABLED": False,
    "SECTOR_RANKING_ENABLED": False,
    "SENTENCE_ARCHIVE_ENABLED": False,
    "SMA50_DIP_EXCEPTION_ENABLED": False,
    "STORY_POOL_ENABLED": True,
    "STRATEGY_READ_ENABLED": False,
    "TIGHTNESS_ADR_AWARE": True,
}
# Used by `_escalation_appended` to isolate the escalation's OWN records: the
# identical read with the two rescue lanes held dark is the subtrahend.
_LANES_DARK = {
    "BAR_POSTURE_RESCUE_ENABLED": False,
    "CONTRACTION_RESCUE_ENABLED": False,
}


def _engine_boolean_roster():
    """Every boolean in the engine's OWN declaration of what decides a reading.

    ONE derivation, named once, so the set this sheet pins and the set the
    engine declares are two NAMED sets compared with each other — never one
    set checked against itself. ``ENGINE_SETTINGS_KEYS`` is proven complete
    over the eval path by ``tests/test_invariants.py::
    test_every_scoring_settings_symbol_is_in_manifest``, so a boolean in it is
    a flag that can move these counts.
    """
    return sorted(k for k in ENGINE_SETTINGS_KEYS
                  if isinstance(getattr(settings, k, None), bool))


def _measurement_pin():
    """The declared pin, asserted EQUAL to the engine's boolean roster.

    Round five, 2026-09-01. The previous form derived the pinned set as
    ``k in _PIN_VALUES or isinstance(getattr(settings, k), bool)`` and then
    asserted that derivation was a SUBSET of the declaration. The equality
    survived only through the second disjunct — which reads as redundant
    belt-and-braces. Delete it as a tidy-up and the roster collapses to
    ``ENGINE_SETTINGS_KEYS & _PIN_VALUES``: from then on, dropping a flag from
    the declaration shrinks the pin with every guard still green, while the
    sheet keeps printing its claim that the basis "cannot drift from the
    policy". So the pinned dict is now BUILT from the ENGINE's set — a short
    declaration raises ``KeyError`` rather than quietly narrowing the pin —
    and the equality, SIZE included, is asserted over what is returned.

    Four ways this can rot, each fatal to the sheet and each caught HERE —
    where the set is stamped — rather than at the operator's desk (EC-55):
    a new engine flag lands and nobody pins it (round three's exact defect,
    which is the reason the set is derived rather than typed); a pinned name
    stops being part of the hashed engine identity; a pinned name stops being
    a flag at all; the derivation quietly stops covering the engine's set. An
    instrument that cannot state its own basis must refuse, never print
    unguarded counts.
    """
    engine_flags = _engine_boolean_roster()
    undeclared = [k for k in engine_flags if k not in _PIN_VALUES]
    assert not undeclared, (
        "the engine's identity roster (ENGINE_SETTINGS_KEYS) carries flag(s) "
        f"this sheet does not pin: {undeclared}. A flag left ambient moves "
        "these counts in silence - LPS_CEILING_REST_ENABLED did exactly that "
        "on 2026-09-01 - so declare the value it is measured at in "
        "_PIN_VALUES before this sheet is read again")
    stale = sorted(set(_PIN_VALUES) - set(ENGINE_SETTINGS_KEYS))
    assert not stale, (
        f"pinned name(s) {stale} are no longer in the engine's identity "
        "roster: either they were renamed (the pin is measuring nothing) or "
        "they stopped deciding a reading (the pin is stale). Re-derive both.")
    mistyped = sorted(k for k in _PIN_VALUES
                      if not isinstance(getattr(settings, k, None), bool))
    assert not mistyped, (
        f"pinned name(s) {mistyped} are no longer boolean flags in settings; "
        "a pin that forces a knob to True/False measures a broken engine")
    pin = {k: _PIN_VALUES[k] for k in engine_flags}
    assert sorted(pin) == engine_flags == sorted(_PIN_VALUES), (
        "the measured pin is not EQUAL to the engine's boolean roster - "
        f"declared-only {sorted(set(_PIN_VALUES) - set(engine_flags))}, "
        f"engine-only {sorted(set(engine_flags) - set(_PIN_VALUES))}. Equal, "
        "never merely contained: a pin narrower than the engine's own "
        "declaration is a basis this sheet has no right to claim")
    assert len(pin) == len(engine_flags) == len(_PIN_VALUES) > 0, (
        f"the pin holds {len(pin)} flag(s) where the engine declares "
        f"{len(engine_flags)} and this sheet declares {len(_PIN_VALUES)}. A "
        "pin that has silently shrunk still prints counts, and every one of "
        "them would then be measured under whatever the machine happened to "
        "be in")
    return pin


# The baseline read the classification is taken under.
_MEASURE_PIN = _measurement_pin()
# The conversion leg: the SAME pin with exactly one lane armed — the shipped
# bar-posture flag, alone, so the column measures one lane and names it.
_CONVERSION_PIN = dict(_MEASURE_PIN, BAR_POSTURE_RESCUE_ENABLED=True)


def _ambient_deltas(ambient, pin):
    """Every PINNED flag whose ambient value differs from the measured basis.

    Iterates the WHOLE pin — and the ambient dict the report stamps is built
    from this same pin's keys, so the stamped set and the compared set are ONE
    set by construction. Round three had two sets: it stamped seven flags and
    compared five, so an eighth flag moving under it was doubly invisible and
    `ambient_matches_pin` came out true while the headline counts had moved.
    Returning the deltas (not a bool) is deliberate: a mismatch has to NAME
    what moved, or the operator is told his sheet is wrong without being told
    which lane made it wrong.
    """
    return {name: {"ambient": ambient.get(name), "pinned": pin[name]}
            for name in sorted(pin) if ambient.get(name) != pin[name]}


def _ambient_witness():
    """ONE read of the machine's flag state, and the deltas taken FROM it.

    The report path consumes this pair and re-derives neither half, so the
    state the sheet STAMPS is by construction the state the deltas were taken
    from. Round four's guards all sat on ``_ambient_deltas``: the helper was
    right in isolation, and ``run`` was still free to stamp one read and
    compute (or skip) the deltas some other way with every guard green — the
    valve could be silenced and nothing turned red. ``_audit_stamp`` then
    re-states the relation over the report's own fields before a byte of the
    sheet is written.
    """
    ambient = {name: getattr(settings, name) for name in sorted(_MEASURE_PIN)}
    return ambient, _ambient_deltas(ambient, _MEASURE_PIN)


def _require_pinned_scope(what):
    """Refuse to measure anything outside ``run``'s ONE pinned scope.

    Every count on this sheet means "measured with every engine flag at this
    changeset's shipped value". Before round five each measurement re-entered
    the pin for itself and the stamp re-derived the identity afterwards, so
    moving or dropping a pin site left the sheet printing the same "measured
    under" line over numbers taken at whatever the machine happened to be in.
    The scope is opened once, in ``run``; every measurement site refuses if it
    finds itself outside it.
    """
    off_pin = {name: {"in scope": getattr(settings, name), "pinned": value}
               for name, value in sorted(_MEASURE_PIN.items())
               if getattr(settings, name) != value}
    assert not off_pin, (
        f"{what} was measured OUTSIDE the pinned basis this sheet claims - "
        f"{off_pin}. These counts are counts about the plain baseline roster "
        "at this changeset's shipped flag values; a name read under the "
        "machine's ambient state is a different measurement wearing this "
        "sheet's headline")

# The escalation-policy table `_self_check` proves, one row per lane
# composition the machine can really be in. ``rewalk`` = whether the
# full-refusal escalation should run at all; ``note`` = which lane names the
# records it appends, or WHY it stood down (the two stand-downs are different
# clauses of the policy and the guard must not blur them). The last row is not
# a duplicate of the third: with the species preset live the contraction form
# is already in the BASELINE roster, so ``escalation -= roster`` empties and
# there is no second walk at all (``narrative.py:474-480``) — the row that
# made round two's guard pass for the wrong reason.
_LANE_STATES = (
    ("both lanes dark",
     {"BAR_POSTURE_RESCUE_ENABLED": False, "CONTRACTION_RESCUE_ENABLED": False,
      "POWER_PLAY_STORY_FORM_ENABLED": False}, False,
     "stands down - no lane is armed (narrative.py:463-465)"),
    ("bar-posture lane armed",
     {"BAR_POSTURE_RESCUE_ENABLED": True, "CONTRACTION_RESCUE_ENABLED": False,
      "POWER_PLAY_STORY_FORM_ENABLED": False}, True, "bar_posture_rescue"),
    ("contraction lane armed",
     {"BAR_POSTURE_RESCUE_ENABLED": False, "CONTRACTION_RESCUE_ENABLED": True,
      "POWER_PLAY_STORY_FORM_ENABLED": False}, True, "contraction_rescue"),
    ("both lanes armed",
     {"BAR_POSTURE_RESCUE_ENABLED": True, "CONTRACTION_RESCUE_ENABLED": True,
      "POWER_PLAY_STORY_FORM_ENABLED": False}, True, "contraction_rescue"),
    ("contraction lane armed but already in the baseline roster (species preset)",
     {"BAR_POSTURE_RESCUE_ENABLED": False, "CONTRACTION_RESCUE_ENABLED": True,
      "POWER_PLAY_STORY_FORM_ENABLED": True}, False,
     "stands down - every armed form is already in the baseline roster "
     "(narrative.py:474-480)"),
)


def _num(value):
    """JSON-native float (the gate reasons carry numpy scalars)."""
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return str(value)


def _fire_row(result):
    """The operator-facing fire row, with the rails the census dropped."""
    return {
        "tier": result.get("Tier"),
        "score": round(float(result.get("Score", 0.0)), 1),
        "elected_pool": result.get("_elected_pool"),
        "story_profile": result.get("_story_admission_profile"),
        "R": _num(result.get("_R")),
        "S": _num(result.get("_S")),
        "inner_R": _num(result.get("_inner_R")),
        "inner_S": _num(result.get("_inner_S")),
        "trigger": _num(result.get("_trigger_price")),
    }


def _attempted_box(trace):
    """Rails from the deepest box the walk actually elected, or None.

    A refused or vetoed name has no Structure, but the walk usually DID elect
    an equilibrium before the story failed downstream — those are the rails
    the operator would see drawn. The last traced root carrying a box is the
    walk's deepest attempt; the row names its index and terminal outcome so
    the sheet never presents an attempt as an election.
    """
    for rec in reversed(trace):
        if rec.get("box"):
            return {"R": _num(rec["box"]["R"]), "S": _num(rec["box"]["S"]),
                    "root_index": rec.get("root_index"),
                    "outcome": rec.get("outcome")}
    return None


def _walk_verdict(daily, atr, trace, *, bricks=None):
    """One baseline walk, classified by the engine's OWN terminal verdict.

    ``cause_vetoed`` means exactly what ``read_structure`` step 2 means and
    nothing wider: the walk returned the cause-before-effect sentinel, so the
    escalation returns before it arms a single form. EVERY other empty read is
    a full refusal that the armed lane re-walks — including a root that hit
    the LPS chronology floor, which ends that ROOT's attempt and continues
    (``narrative.py:643-647``). The trace is filled as a side effect for the
    rails and the outcome disclosure; it is never the predicate.
    """
    walked = _walk_structure(daily, atr, bricks=bricks, trace=trace)
    return ("cause_vetoed" if walked is _CAUSE_VETOED
            else "full_refusal_reachable")


def _escalation_appended(make_bricks, overrides):
    """The trace records the full-refusal escalation APPENDED, or ``[]``.

    Measured by trace LENGTH against the identical read with both lanes dark
    — never by the pass stamp. That distinction is the whole of round three's
    T3 finding: the escalation stamps its records with the name of the SENIOR
    armed lane (``narrative.py:499-505``), so under an ambiently live
    contraction lane a bar-posture run's re-walk is stamped
    ``contraction_rescue``. Round two asserted the stamp string, so the
    instrument ABORTED whenever the sibling lane was live — with a message
    ("a chronology-floored name IS reachable — the walk continues") asserting
    the exact opposite of what had just happened: the re-walk HAD happened.
    Length is the fact; the stamp is a label on the fact, and is checked
    separately against what the lane composition predicts.
    """
    dark: list = []
    with flag_capture(**dict(overrides, **_LANES_DARK)):
        read_structure(None, 1.0, bricks=make_bricks(), trace=dark)
    lit: list = []
    with flag_capture(**overrides):
        read_structure(None, 1.0, bricks=make_bricks(), trace=lit)
    return lit[len(dark):]


def _self_check():
    """Prove the finality predicate against the ENGINE before any number, in
    EVERY lane state the machine can be in on the morning of a flip sitting.

    This instrument is built to be re-run at every flip sitting, so a
    predicate that has silently drifted from the escalation policy is a
    landmine with a date on it — the round-one build read the doctrine gate's
    abstention VOCABULARY as finality and would have reported a rescuable
    name as "never reachable". Both halves are driven through the same
    scripted bricks pytest pins the walk's outcomes with
    (``tests/test_doctrine_audit_plumbing.py``) rather than a local twin
    (EC-3), and each half asserts the OBSERVABLE consequence — whether the
    escalation appended a second walk's records — not the pass stamp.

    Every flag the escalation composition depends on is PINNED per row, so
    the guard's answer is a property of the ENGINE and not of the ambient
    process: it returns the same lines whether the machine's lanes are dark,
    half lit, or fully lit.

    Round four adds the two legs that guard the INSTRUMENT's own bookkeeping,
    because that is where round three's defect lived — not in the engine, but
    in a pin that named five flags and an honesty valve that iterated the same
    five. Both are proved the way the engine legs are: by property, over a
    synthetic ambient where the flag asserted reported would otherwise be
    unreported. The wiring between them — the sheet stamping one flag set and
    comparing another — is checked in ``run`` on the report itself, because a
    helper that is right in isolation is exactly what round three had.

    Raises ``AssertionError`` (or ``ImportError`` if those fixtures move):
    an instrument that cannot prove its own predicate must refuse, never
    print unguarded counts.
    """
    from tests.test_doctrine_audit_plumbing import (  # noqa: PLC0415
        _FloorBlockedBricks, _VetoBricks)

    checks = []

    # ── leg 0a: the pin covers the engine, and the valve reports the pin ─────
    # `_measurement_pin()` already refused at import if the engine's roster
    # carries a flag this sheet does not pin. What is proved here is the other
    # half — that `ambient_matches_pin` is computed over the WHOLE pin. The
    # property is exhaustive: flipping ANY ONE pinned flag in a synthetic
    # ambient must be reported, and reported alone. A valve that iterates a
    # subset (round three iterated five) fails on the first flag outside it.
    pin = _MEASURE_PIN
    # The pin must BE the engine's boolean roster — equal, size included, not
    # merely contained in the declaration. `_measurement_pin` refuses at
    # import if it is not; the equality is re-stated HERE, where the sheet
    # writes its guard lines, so the claim the operator reads is a claim
    # something checked. The loop below iterates the pin, so a pin that had
    # silently shrunk would pass it vacuously — this is the leg that makes
    # that impossible.
    engine_flags = _engine_boolean_roster()
    assert sorted(pin) == engine_flags, (
        "the measurement pin is not the engine's boolean roster - pin-only "
        f"{sorted(set(pin) - set(engine_flags))}, engine-only "
        f"{sorted(set(engine_flags) - set(pin))}. A pin narrower than the "
        "engine's own declaration leaves flags ambient that move these counts")
    assert len(pin) == len(engine_flags) > 1, (
        f"the pin holds {len(pin)} flag(s) against the engine's "
        f"{len(engine_flags)} - a shrunken pin still prints counts, and every "
        "leg below would pass over it")
    # The three flags MEASURED to move this sheet through round three's hole
    # (2026-09-01 ambient sweep) are named here as well as derived, so a future
    # narrowing of the roster cannot quietly drop a known mover.
    for measured_mover in ("LPS_CEILING_REST_ENABLED", "STORY_POOL_ENABLED",
                           "SMA50_DIP_EXCEPTION_ENABLED"):
        assert measured_mover in pin, (
            f"{measured_mover} is MEASURED to move this sheet's counts on "
            "this very population (2026-09-01) and it is not pinned - the "
            "operator would be handed a moved sheet under a pinned claim")
    for name in pin:
        synthetic = dict(pin)
        synthetic[name] = not pin[name]
        seen = _ambient_deltas(synthetic, pin)
        assert list(seen) == [name], (
            f"an ambient {name} moved away from the measured basis and the "
            f"honesty valve reported {sorted(seen)} - a flag the sheet does "
            "not report is a flag that changes the operator's counts in "
            "silence, which is the whole class this guard exists to close")
    # The negative control. Stated honestly: this does NOT catch a class the
    # loop above misses — an inverted comparison turns both red (measured
    # 2026-09-01). It is here because `ambient_matches_pin: true` is a claim
    # the sheet makes, and a claim nothing proves the valve can ever make is a
    # claim worth nothing. The loop is the leg that closes round three's hole.
    assert not _ambient_deltas(dict(pin), pin), (
        "the honesty valve reports a delta on an ambient state that IS the "
        "pin - it can never say 'matches', so its 'moved' means nothing")
    checks.append(
        f"the measurement pin IS the engine's boolean roster - all {len(pin)} "
        "of them, size asserted, not a subset (ENGINE_SETTINGS_KEYS, itself "
        "proven complete over the eval path by tests/test_invariants.py) - "
        "and a move of ANY ONE of them is named by ambient_matches_pin")

    # ── leg 0b: the stamped engine identity is a live witness of the basis ───
    # Every pinned flag is in the hashed roster, so entering the pin with one
    # flag flipped MUST move the manifest hash. That makes the stamp an
    # INDEPENDENT check on the valve above (they share no code): an unmoved
    # hash cannot coexist with a real flag delta.
    with flag_capture(**pin):
        pinned_hash = manifest_hash()
    flipped = dict(pin)
    flipped["LPS_CEILING_REST_ENABLED"] = not pin["LPS_CEILING_REST_ENABLED"]
    with flag_capture(**flipped):
        moved_hash = manifest_hash()
    assert moved_hash != pinned_hash, (
        "the engine manifest hash did not move when a pinned flag moved - the "
        "stamped identity is not a witness of the measured basis, so the "
        "chair would be sealing a hash that does not describe these numbers")
    checks.append(
        "the engine manifest hash moves when a pinned flag moves, so the "
        "stamped identity independently witnesses the basis these numbers "
        "were measured under")

    for label, lanes, rewalk_expected, note in _LANE_STATES:
        pin = dict(_MEASURE_PIN, **lanes)

        # Half one — a cause-before-effect abstention is FINAL. Under every
        # lane composition, including both armed: `read_structure` returns at
        # step 2, so the escalation appends nothing at all.
        trace: list = []
        with flag_capture(**pin):
            verdict = _walk_verdict(None, 1.0, trace, bricks=_VetoBricks())
        assert verdict == "cause_vetoed", (label, verdict)
        assert {r.get("outcome") for r in trace} == {"cause_absent"}, (
            f"{label}: the veto fixture must narrate cause_absent, not "
            f"{sorted({r.get('outcome') for r in trace})}")
        appended = _escalation_appended(_VetoBricks, pin)
        assert not appended, (
            f"{label}: a cause-before-effect abstention must never reach the "
            f"escalation, but the walk appended {len(appended)} record(s) "
            f"stamped {sorted({r.get('pass') for r in appended})}")

        # Half two — the LPS chronology floor is NOT final: it ends one root's
        # attempt and the walk continues, so the name is a full refusal the
        # escalation re-walks whenever a lane arms a form the baseline roster
        # lacks. The stamp is checked as a LABEL, after the fact of the
        # re-walk has already been established by length.
        trace = []
        with flag_capture(**pin):
            verdict = _walk_verdict(None, 1.0, trace,
                                    bricks=_FloorBlockedBricks())
        assert verdict == "full_refusal_reachable", (label, verdict)
        assert {r.get("outcome") for r in trace} == {"lps_before_spring"}, (
            f"{label}: the floor fixture must narrate lps_before_spring, not "
            f"{sorted({r.get('outcome') for r in trace})}")
        appended = _escalation_appended(_FloorBlockedBricks, pin)
        assert bool(appended) is rewalk_expected, (
            f"{label}: expected the escalation to "
            f"{'re-walk' if rewalk_expected else 'stand down'}, but it "
            f"appended {len(appended)} record(s)")
        stamps = sorted({r.get("pass") for r in appended})
        expected_stamps = [note] if rewalk_expected else []
        assert stamps == expected_stamps, (
            f"{label}: the re-walk happened, but the lane naming its records "
            f"is {stamps}, not {expected_stamps}")

        checks.append(
            f"{label}: cause_absent -> cause_vetoed, escalation never runs; "
            "lps_before_spring -> full_refusal_reachable, escalation "
            + (f"re-walks and the senior lane stamps its records {note}"
               if rewalk_expected else note))
    return checks


def _classify(ticker, raw):
    """The four-way verdict for one name, plus its rails and conversion.

    Called from INSIDE ``run``'s one pinned scope and refuses otherwise: the
    baseline read here is the plain S-test roster at this changeset's shipped
    flag values, which is what the sheet's reachability line is a line ABOUT.
    """
    _require_pinned_scope(f"ticker {ticker}")
    row = {"ticker": ticker, "last_session": str(raw.index[-1])[:10],
           "verdict": None, "verdict_plain": None, "refusal_gate": None,
           "walk_outcomes": None, "hit_chronology_floor": None,
           "R": None, "S": None, "rails_from": None,
           "elected_pool": None, "story_profile": None,
           "fires_at_baseline": None, "converts_with_lane_armed": None,
           "fire": None}

    prep, reason = evaluation._prepare_eval_frame_with_reason(raw)
    if prep is None:
        row["verdict"] = "fails_prepare"
        row["verdict_plain"] = _PLAIN[row["verdict"]]
        row["refusal_gate"] = reason[0] if reason else None
        row["refusal_samples"] = {k: _num(v) for k, v in (reason[1] or {}).items()} \
            if reason else None
        return row

    daily = prep["df"]
    atr = float(evaluation.structure_atr_row(daily)["ATR_10"])

    # The baseline read exactly as the live chain takes it (traceless), then —
    # only when it comes back empty — ONE traced re-run to read the engine's
    # own terminal outcome. This is the doctrine gate's own sequence: the
    # veto predicate is never re-evaluated, only the walk's report of it.
    # No capture here: the caller's pinned scope IS the basis, checked on the
    # way in. A pin re-entered per measurement is a pin no stamp can witness.
    base = read_structure(daily, atr)
    baseline_fire = evaluation._evaluate_ticker(ticker, raw, _SPY_6M, _BREADTH)
    row["fires_at_baseline"] = isinstance(baseline_fire, dict)

    if base is not None:
        row["verdict"] = "elects_at_baseline"
        row["verdict_plain"] = _PLAIN[row["verdict"]]
        row["R"], row["S"] = _num(base.R), _num(base.S)
        row["rails_from"] = "baseline election"
        row["elected_pool"] = str(base.box.elected_pool)
        row["story_profile"] = base.box.story_admission_profile
        if row["fires_at_baseline"]:
            row["fire"] = _fire_row(baseline_fire)
        return row

    trace: list = []
    verdict = _walk_verdict(daily, atr, trace)
    outcomes = sorted({r.get("outcome") for r in trace if r.get("outcome")})
    row["walk_outcomes"] = outcomes
    # Disclosed, never decisive: a floored root is evidence out of order, and
    # the operator should see it — but the walk moved on, so the name is
    # reachable and its conversion leg runs like any other refusal.
    row["hit_chronology_floor"] = "lps_before_spring" in outcomes
    attempted = _attempted_box(trace)

    row["verdict"] = verdict
    row["verdict_plain"] = _PLAIN[verdict]
    if verdict == "cause_vetoed":
        if attempted:
            row["R"], row["S"] = attempted["R"], attempted["S"]
            row["rails_from"] = (f"attempted box (walk root {attempted['root_index']}"
                                 f", {attempted['outcome']})")
        return row

    # The REAL armed lane — the shipped flag through the one scoped override,
    # never a patched predicate. This is the read a flip would actually buy.
    # ONE lane armed: the sibling contraction lane is pinned dark even if the
    # machine has since flipped it, or this column would silently become
    # "what the two lanes buy together" under the bar-posture lane's name.
    with flag_capture(**_CONVERSION_PIN):
        armed_structure = read_structure(daily, atr)
        armed = evaluation._evaluate_ticker(ticker, raw, _SPY_6M, _BREADTH)
    row["converts_with_lane_armed"] = isinstance(armed, dict)
    if isinstance(armed, dict):
        row["fire"] = _fire_row(armed)
        row["R"], row["S"] = row["fire"]["R"], row["fire"]["S"]
        row["rails_from"] = "armed-lane election"
        row["elected_pool"] = armed.get("_elected_pool")
        row["story_profile"] = armed.get("_story_admission_profile")
    elif armed_structure is not None:
        row["R"], row["S"] = _num(armed_structure.R), _num(armed_structure.S)
        row["rails_from"] = "armed-lane election (dies downstream of the walk)"
        row["elected_pool"] = str(armed_structure.box.elected_pool)
        row["story_profile"] = armed_structure.box.story_admission_profile
    elif attempted:
        row["R"], row["S"] = attempted["R"], attempted["S"]
        row["rails_from"] = (f"attempted box (walk root {attempted['root_index']}"
                             f", {attempted['outcome']})")
    return row


_AUDIT_LEGS = ("flag-set identity", "honesty valve",
               "measurement witness", "engine-identity cross-check")


def _audit_stamp(report):
    """Refuse the sheet unless its OWN fields witness its own conditions.

    Every leg is stated over the report — never over the helper that filled
    the field — and the report path consumes the return value, so a leg can
    only be skipped by deleting the call. Round three's helpers were each
    defensible in isolation and the sheet was still wrong, because nothing
    checked the wiring between them; round four moved the wiring check onto
    two of the four claims and left the honesty valve and the measurement
    scope with no check on the report path at all.

    Returns the audited report.
    """
    flags = report["measurement_flags"]
    pin = flags["classification"]

    # (1) The set of flags the sheet STAMPS and the set it MEASURES against
    #     must be ONE set. Round three stamped seven and compared five.
    stamped = set(report["flag_state"])
    compared = set(pin)
    assert stamped == compared, (
        "the sheet stamps a different flag set than it measures against - "
        f"stamped only: {sorted(stamped - compared)}; measured only: "
        f"{sorted(compared - stamped)}. A flag in one set and not the other "
        "is a flag that can move these counts without the sidecar saying so")

    # (2) The honesty valve, re-derived FROM THE SHEET's own stamped state.
    #     Round four proved `_ambient_deltas` exhaustively and never once
    #     required `run` to publish what it returned, so the valve could be
    #     silenced — deltas emptied, `ambient_matches_pin` left true over a
    #     moved machine — with every guard green. The relation is a property
    #     of the printed fields: a flag stamped away from its pinned value
    #     MUST appear in the deltas, named, with both values.
    moved = {name for name, value in report["flag_state"].items()
             if value != pin[name]}
    assert set(flags["ambient_deltas"]) == moved, (
        "the sheet's stamped flag state and its ambient_deltas disagree - "
        f"stamped as moved: {sorted(moved)}; reported as moved: "
        f"{sorted(flags['ambient_deltas'])}. A moved flag the valve does not "
        "name is a lane that changed these counts in silence, which is the "
        "whole class this sheet exists to make impossible")
    for name, delta in flags["ambient_deltas"].items():
        assert delta == {"ambient": report["flag_state"][name],
                         "pinned": pin[name]}, (
            f"the delta reported for {name} ({delta}) is not the pair the "
            f"sheet stamps (machine {report['flag_state'][name]}, pinned "
            f"{pin[name]}) - the operator would be told the wrong lane moved")
    assert flags["ambient_matches_pin"] is (not flags["ambient_deltas"]), (
        "the sheet's headline honesty line "
        f"(ambient_matches_pin={flags['ambient_matches_pin']}) contradicts "
        f"its own delta list ({sorted(flags['ambient_deltas'])})")

    # (3) The measurement WITNESS: what the flags actually were inside the one
    #     scope the twelve names were evaluated in. Not a re-derivation — the
    #     values were read in there. If the pin site is moved or dropped, this
    #     is the ambient state and it disagrees with the pin, loudly, naming
    #     every flag the sheet was really measured under.
    observed = flags["observed_inside_measurement_scope"]
    unwitnessed = {name: {"observed": observed.get(name), "pinned": value}
                   for name, value in sorted(pin.items())
                   if observed.get(name) != value}
    assert not unwitnessed, (
        "the flags observed INSIDE the measurement scope are not the pinned "
        f"basis this sheet claims: {unwitnessed}. Either the pin site around "
        "the ticker loop was moved or dropped, or something re-based the "
        "engine mid-run - either way these counts were not measured under "
        "the conditions printed above them, and the sheet must not be read")

    # (4) The engine's own identity is an INDEPENDENT witness: every pinned
    #     flag is in the hashed roster, so an unmoved hash cannot coexist with
    #     a moved flag. Two instruments sharing no code have to agree before
    #     the operator is handed a number.
    assert not (report["measurement_identity_matches_machine"]
                and flags["ambient_deltas"]), (
        "the machine's engine identity equals the measured identity, yet the "
        f"pin reports moved flags {sorted(flags['ambient_deltas'])} - every "
        "pinned flag is in the hashed roster, so one of the two instruments "
        "is lying and this sheet must not be read")

    # The audit leaves its own mark. Every leg above is individually pinned,
    # but nothing proved `run` still CALLS this function - which is round
    # four's defect ("the guards sat on the helper, none on the report path")
    # transposed one level up. So the audit witnesses itself: the legs it ran
    # are stamped into the sheet the operator reads, and the print/write path
    # refuses a report that does not carry them. Deleting the call now empties
    # a visible field AND stops the sheet being written at all.
    report["audited"] = list(_AUDIT_LEGS)
    return report


def _refuse_unaudited(report):
    """The write path's own check: an unaudited sheet is never published.

    Named rather than inline so the wiring itself is testable - the whole
    point of the mark above.
    """
    if list(report.get("audited") or ()) != list(_AUDIT_LEGS):
        raise AssertionError(
            "this sheet was never audited - it carries "
            f"{report.get('audited')!r} where the four legs "
            f"{list(_AUDIT_LEGS)} are required. Nothing may be printed or "
            "written: an unaudited sheet has not witnessed the conditions "
            "its own counts were measured under")
    return report


def run(json_out=None):
    json_out = json_out or _DEFAULT_JSON
    refuse_sealed_output(json_out)

    # The predicate is proven against the engine BEFORE a single count is
    # printed; a drifted finality rule must abort the sheet, not colour it.
    guard = _self_check()
    for line in guard:
        print(f"  predicate guard OK: {line}", flush=True)

    with open(_CENSUS, "r", encoding="utf-8") as fh:
        census = json.load(fh)
    tickers = sorted(r["ticker"] for r in census["new_fires"])
    claimed = {r["ticker"]: r for r in census["new_fires"]}
    fingerprint = hashlib.sha256(
        json.dumps(tickers, sort_keys=True).encode("utf-8")).hexdigest()

    data = pd.read_parquet(_CACHE, engine=settings.PARQUET_ENGINE)
    rows, edge = [], None
    # ── THE one pin site ────────────────────────────────────────────────────
    # Every ticker on this sheet is evaluated inside THIS scope, and the two
    # things the stamp claims about the measurement are read INSIDE it: the
    # engine identity, and the flag state actually in force. Round four
    # re-derived both afterwards, which made the sheet's "measured under" line
    # a claim about a scope it had already left — it would have printed the
    # identical words with no pin at all. Read here, they are a WITNESS: what
    # these counts were measured under, observed where they were measured.
    with flag_capture(**_MEASURE_PIN):
        engine_at_pin = manifest_hash()
        observed_at_pin = {name: getattr(settings, name)
                           for name in sorted(_MEASURE_PIN)}
        for ticker in tickers:
            raw = data[ticker].dropna()
            if edge is None or raw.index[-1] > edge:
                edge = raw.index[-1]
            row = _classify(ticker, raw)
            row["census_2026_08_31"] = {
                "tier": claimed[ticker]["tier"],
                "score": claimed[ticker]["score"],
                "profile": claimed[ticker]["profile"],
            }
            rows.append(row)
            print(f"  {ticker:<6} {row['verdict_plain']}", flush=True)

    counts = {"population": len(rows)}
    for verdict in ("full_refusal_reachable", "cause_vetoed",
                    "elects_at_baseline", "fails_prepare"):
        counts[verdict] = sum(r["verdict"] == verdict for r in rows)
    counts["reachable_converting"] = sum(
        r["converts_with_lane_armed"] is True for r in rows)
    counts["reachable_not_converting"] = sum(
        r["converts_with_lane_armed"] is False for r in rows)
    # Disclosure, not a verdict: how many refusals had a root whose last point
    # of support opened before its own spring. Round one classified these as
    # "never reachable"; the walk continues past them, so they are counted in
    # full_refusal_reachable above and their conversion leg ran.
    counts["reachable_with_chronology_floor"] = sum(
        r["hit_chronology_floor"] is True for r in rows)

    # ONE set, and ONE read of it: the ambient state the sheet stamps IS the
    # read the deltas were taken from (`_ambient_witness`), over the pin's own
    # keys, so "what the sheet reports" and "what the sheet compares" cannot be
    # two different sets again — nor two different reads of one set.
    ambient, deltas = _ambient_witness()
    ambient_matches_pin = not deltas

    # The machine's own engine identity, read FRESH and OUTSIDE the pinned
    # scope; its twin above was read INSIDE it. Flags live in the hashed
    # roster, so equal hashes cannot coexist with a flag delta — an
    # independent check on the valve. Unequal hashes are BROADER than the flag
    # answer: they also catch a moved threshold, which no flag pin can see.
    engine_ambient = manifest_hash()
    identity_matches = engine_ambient == engine_at_pin

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        # EC-13 stamp: WHAT was scored, on WHICH data, by WHICH engine, under
        # WHICH flags. The 08-31 census carried none of these.
        "population": ("the 12 new fires of the 2026-08-31 wholesale-swap "
                       "census (cache edge 2026-08-27)"),
        "population_source": os.path.relpath(_CENSUS, _PROJECT_ROOT).replace("\\", "/"),
        "population_tickers": tickers,
        # sha256 of the exact ticker list scored (this population is a ticker
        # set, not a marks set - no marks loader is involved).
        "population_fingerprint": fingerprint,
        "cache_last_session": str(edge)[:10] if edge is not None else None,
        "source_census_session": census.get("session"),
        # Read FRESH at run time, never cached at import: another agent may be
        # rotating the engine identity while this probe runs, and a stale hash
        # would stamp the sheet with an engine it did not read.
        "engine_manifest": engine_ambient,
        # The identity the NUMBERS were measured under. Equal to the above
        # whenever the machine sits at the pinned basis; different the moment
        # anything hashed has moved — including a threshold, which no flag pin
        # can see. This is the pair the chair's seal should agree with.
        # Read INSIDE the one scope the tickers were evaluated in, never
        # re-derived after it closed — so this hash is a witness of the
        # measurement, not a re-statement of the intention.
        "engine_manifest_at_measurement_pin": engine_at_pin,
        "measurement_identity_matches_machine": identity_matches,
        # The AMBIENT process state this run found, over EVERY pinned flag
        # (EC-13/EC-46) ...
        "flag_state": ambient,
        # ... and what the measurement actually ran at. They are the same
        # today; they need not be on the morning of a flip sitting, which is
        # exactly when this probe is mandated to be re-run.
        "measurement_flags": {
            "classification": dict(_MEASURE_PIN),
            "conversion_leg": dict(_CONVERSION_PIN),
            "ambient_matches_pin": ambient_matches_pin,
            "ambient_deltas": deltas,
            # The WITNESS (round five): every pinned flag as it actually stood
            # INSIDE the single scope the twelve names were evaluated in. The
            # two lines above describe the machine; this one describes the
            # measurement. If a future edit moves or drops that scope, this is
            # the field that disagrees — and `_audit_stamp` refuses the sheet.
            "observed_inside_measurement_scope": observed_at_pin,
            "pin_source": ("every boolean in engine_alpha.freeze.manifest."
                           "ENGINE_SETTINGS_KEYS - the engine's own roster of "
                           "constants that decide a reading, proven complete "
                           "over the eval path by tests/test_invariants.py::"
                           "test_every_scoring_settings_symbol_is_in_manifest"
                           " - pinned at this changeset's shipped values"),
            "why": ("EVERY flag the engine says can move a reading is pinned "
                    "for the measurement, not just the ones that name a lane: "
                    "the sheet's reachability line is a line about the plain "
                    "baseline roster, and its conversion column is a line "
                    "about ONE lane. Any ambient flag can move both without "
                    "changing a word of the sheet, so ambient_matches_pin is "
                    "computed over the whole pin and names what moved"),
            "measured_consequence": (
                "not cosmetic - all measured 2026-09-01 on this cache and "
                "this population. Through the hole round three left (a flag "
                "outside its five-name pin), THREE flags move a count while "
                "the sidecar writes ambient_matches_pin: true. "
                "LPS_CEILING_REST_ENABLED=True: KFY stops being a full "
                "refusal and elects at BASELINE through the ceiling-rest "
                "lane, so the headline moves full_refusal_reachable 4 -> 3 "
                "and reachable_converting 4 -> 3 (this is the one the review "
                "named). STORY_POOL_ENABLED=False: the sheet inverts - 6 "
                "reachable, 3 electing, ZERO conversions; round three stamped "
                "this flag without comparing it, so the sidecar would have "
                "shown its moved value and claimed a pinned basis on the next "
                "line. SMA50_DIP_EXCEPTION_ENABLED=True: the universe gate "
                "softens and all three fails_prepare names (ICLR, MSGS, VTR) "
                "enter the read - 0 / 5 / 7. Two more were already known and "
                "pinned by round three, so they cannot leak: "
                "CONTRACTION_RESCUE_ENABLED=True takes all four reachable "
                "names at baseline via the SIBLING lane with 'contracting at "
                "resistance' profiles (0 reachable / 0 converting, that "
                "lane's conversions credited to the bar-posture lane), and "
                "POWER_PLAY_STORY_FORM_ENABLED=True moves the same four plus "
                "CCEP (A 108.7 -> no fire), RCUS (A 106.2 strict -> B 82.0 "
                "story) and GEO's profile"),
            "flags_measured_inert_on_this_population": (
                "the full sweep flipped each of the 28 ambiently and "
                "re-measured under round three's five-flag pin (2026-09-01). "
                "Those five could not leak by construction; of the other 24, "
                "the three named above moved a count and 21 were inert. They "
                "are all pinned anyway: inert on twelve names at one cache "
                "edge is not a property of the flag, and a sheet's basis must "
                "be STATED, not inferred from a null result"),
        },
        "armed_leg": ("classification runs under the pinned baseline - EVERY "
                      "boolean in the engine's identity roster held at this "
                      "changeset's shipped value, so both program flags are "
                      "dark, both rescue lanes are dark and the species "
                      "story-form is off; the conversion leg re-reads each "
                      "reachable name with BAR_POSTURE_RESCUE_ENABLED=True "
                      "and every other flag unchanged - the shipped lane "
                      "through the one scoped override "
                      "(tools.replay.flag_capture), self-restoring"),
        # The finality rule this run classified by, and the engine-driven
        # checks that proved it before the sheet was built.
        "finality_rule": ("cause_vetoed = the walk returned narrative's "
                          "_CAUSE_VETOED sentinel (read_structure step 2, the "
                          "cause-before-effect abstention). An LPS chronology "
                          "floor is NOT final: it ends one root's attempt and "
                          "the walk continues, so such a name is a full "
                          "refusal the armed lane re-walks"),
        "predicate_guard": guard,
        "counts": counts,
        "names": rows,
    }

    # Nothing below is printed or written until the sheet's own fields have
    # witnessed the sheet's own claims.
    report = _refuse_unaudited(_audit_stamp(report))

    print("=" * 72)
    print("  BAR-POSTURE RESCUE REACHABILITY - the twelve-name sheet, re-derived")
    print("=" * 72)
    print(f"cache edge {report['cache_last_session']}   "
          f"(census read at {report['source_census_session']})")
    print(f"engine {report['engine_manifest']}  (machine)")
    print(f"engine {report['engine_manifest_at_measurement_pin']}  "
          "(the basis these numbers were measured under)")
    print(f"measurement scope: one pinned scope wraps the whole ticker loop; "
          f"all {len(observed_at_pin)} flags were OBSERVED at the pin inside "
          "it, and the two lines above were read on either side of it")
    print(f"population {len(tickers)} tickers   "
          f"fingerprint {fingerprint[:16]}...")
    # The WHOLE pinned set is printed, never a readable subset of it: a flag
    # the sheet does not show is a flag whose move the reader cannot check.
    print(f"flags: {len(ambient)} engine flags pinned and stamped; ambient ON "
          "= " + (", ".join(n for n, v in sorted(ambient.items()) if v)
                  or "(none)"))
    print("       ambient OFF = "
          + (", ".join(n for n, v in sorted(ambient.items()) if not v)
             or "(none)"))
    if ambient_matches_pin:
        print("measured at the pinned baseline - the machine's own state "
              "already matches it on every one of those flags")
    else:
        print("!! the machine's flag state has MOVED away from the basis this "
              "sheet measures:")
        for name, moved in deltas.items():
            print(f"!!   {name}: machine {moved['ambient']}, "
                  f"measured at {moved['pinned']}")
        print("!! the numbers below are still the PINNED read (every engine "
              "flag at this changeset's shipped value, both rescue lanes dark, "
              "species story-form off), so they stay comparable to the "
              "2026-08-31 census - but they are no longer what this machine "
              "does live")
        print("!! measured 2026-09-01 on this population, what each move "
              "would have done to the sheet you are holding: CEILING-REST "
              "live -> KFY elects at baseline through THAT lane, headline "
              "drops to 3 reachable / 3 converting. STORY POOL off -> 6 "
              "reachable, 3 electing, ZERO conversions. SMA50 DIP EXCEPTION "
              "live -> ICLR, MSGS and VTR stop failing the universe gate and "
              "enter the read (0 / 5 / 7). CONTRACTION lane live -> all four "
              "reachable names are taken by that lane and read as baseline "
              "elections with 'contracting at resistance' profiles, so the "
              "sheet would credit a sibling lane's conversions to the "
              "bar-posture lane. Rule the bar-posture flip against the "
              "PINNED sheet, and rule what the flip still BUYS against the "
              "sibling lane's own sheet")
    if not identity_matches:
        print("!! the machine's engine identity differs from the measured "
              "one, so something hashed has moved. Flags are named above; if "
              "nothing is named above, a THRESHOLD moved and no flag pin can "
              "see it - re-derive the sheet before quoting it")
    print()
    for key, value in counts.items():
        print(f"  {key:>31}: {value}")
    print()
    print(f"{'ticker':<7}{'verdict':<24}{'R':>10}{'S':>10}  rails from")
    print("-" * 72)
    for row in rows:
        print(f"{row['ticker']:<7}{row['verdict']:<24}"
              f"{(row['R'] if row['R'] is not None else '-'):>10}"
              f"{(row['S'] if row['S'] is not None else '-'):>10}  "
              f"{row['rails_from'] or '-'}")
    print()
    for row in rows:
        if row["verdict"] != "full_refusal_reachable":
            continue
        verb = "CONVERTS" if row["converts_with_lane_armed"] else "no fire"
        fire = row["fire"] or {}
        print(f"  {row['ticker']:<6} armed lane -> {verb}"
              + (f"  tier {fire.get('tier')} score {fire.get('score')} "
                 f"pool {fire.get('elected_pool')} "
                 f"| {fire.get('story_profile')}" if fire else ""))
        if row["hit_chronology_floor"]:
            print("         (one root's last point of support opened before "
                  "its own spring - evidence out of order; the walk moved on, "
                  "so the lane still reaches this name)")
    for row in rows:
        if row["verdict"] == "elects_at_baseline":
            state = ("already FIRES at baseline" if row["fires_at_baseline"]
                     else "elects but does not fire at baseline")
            print(f"  {row['ticker']:<6} {state}  (pool {row['elected_pool']})")
        if row["verdict"] == "fails_prepare":
            print(f"  {row['ticker']:<6} universe filter refused: "
                  f"{row['refusal_gate']} {row.get('refusal_samples')}")
        if row["verdict"] == "cause_vetoed":
            print(f"  {row['ticker']:<6} walk outcomes: {row['walk_outcomes']}")

    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print(f"\nwrote {json_out}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Bar-posture rescue reachability over the 12-name sheet.")
    parser.add_argument("--json", default=None,
                        help="sidecar report path (default: beside this probe)")
    run(parser.parse_args().json)


if __name__ == "__main__":
    main()
