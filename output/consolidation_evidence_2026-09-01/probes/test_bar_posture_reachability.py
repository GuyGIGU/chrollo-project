"""The eyeball sheet must witness its own measurement conditions.

Three claims the bar-posture reachability sheet PRINTS, each of which had
nothing behind it before round five (2026-09-01), and one leg here per claim:

  (a) "the pinned set is derived from the engine's own roster, so it cannot
      drift from the policy" — the pin's SIZE was never asserted. The roster
      was derived as ``k in _PIN_VALUES or isinstance(getattr(settings, k),
      bool)`` and asserted to be a SUBSET of the declaration; the equality
      lived entirely in that second disjunct, which reads as redundant
      belt-and-braces. Remove it as a tidy-up and dropping a flag from the
      declaration shrinks the pin with every guard green.
  (b) "ambient_matches_pin" — every guard sat on the helper ``_ambient_deltas``
      and none on the report path, so the valve could be silenced with nothing
      turning red.
  (c) "the basis these numbers were measured under" — re-derived AFTER the
      ticker loop, so the sheet printed the identical line whether or not a
      pin had ever been entered.

Run: ``.venv\\Scripts\\python.exe -m pytest
"output/consolidation_evidence_2026-09-01/probes/test_bar_posture_reachability.py" -q``
(the repo's ``testpaths = tests`` means a default pytest run does NOT collect
this file — it is named explicitly, like the probe it guards).

Every leg here is stated over a fixture where the thing asserted would
otherwise be PRESENT: a silenced valve is proved over a report whose stamped
flag state really has a flag off-pin, and a dropped pin scope is proved with
the machine really moved away from the pin. Asserting an absence over a
fixture that has nothing to hide proves nothing.
"""
import copy
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_probe():
    """Import the probe by path — it lives in output/, not on the package path."""
    spec = importlib.util.spec_from_file_location(
        "bar_posture_reachability_probe",
        os.path.join(_HERE, "bar_posture_reachability.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = _load_probe()

from config import settings  # noqa: E402  (the probe bootstrapped sys.path)
from tools.replay import flag_capture  # noqa: E402

# The flag the 2026-09-01 sweep MEASURED to move the headline (4/4 -> 3/3) by
# electing KFY at baseline through the sibling ceiling-rest lane. Used as the
# "moved machine" throughout, so every negative leg is stated over the exact
# ambient that produced the defect these fixes close.
_MOVER = "LPS_CEILING_REST_ENABLED"
# A DIFFERENT flag for the drop legs, deliberately: the refusal message quotes
# `_MOVER` in its fixed prose, so a message-content assertion on that name
# would pass over an empty list. This one appears in the message only if the
# guard actually named it.
_DROPPED = "STORY_POOL_ENABLED"


# ── (a) the pin IS the engine's boolean roster, size included ────────────────

def test_pin_is_equal_to_the_engine_boolean_roster():
    """Not a subset — equal, and its size asserted."""
    engine_flags = probe._engine_boolean_roster()
    assert len(engine_flags) > 1, (
        "a roster of one name cannot distinguish 'named' from 'defaulted'")
    assert sorted(probe._MEASURE_PIN) == engine_flags
    assert len(probe._MEASURE_PIN) == len(engine_flags) == len(probe._PIN_VALUES)


def test_dropping_a_declared_flag_refuses_the_pin(monkeypatch):
    """The declaration may not silently shrink the measured basis.

    The fixture holds every engine flag, so naming the dropped one is a real
    discrimination and not a coin flip.
    """
    assert _DROPPED in probe._PIN_VALUES
    short = {k: v for k, v in probe._PIN_VALUES.items() if k != _DROPPED}
    monkeypatch.setattr(probe, "_PIN_VALUES", short)
    with pytest.raises(AssertionError) as excinfo:
        probe._measurement_pin()
    message = str(excinfo.value)
    assert _DROPPED in message
    # and it must name the dropped flag, not merely list the whole roster
    assert "TIGHTNESS_ADR_AWARE" not in message


def test_a_short_declaration_cannot_build_a_narrower_pin(monkeypatch):
    """Structural, not merely guarded: the pin is BUILT from the engine's set.

    Even with every assertion in ``_measurement_pin`` removed, keying the
    returned dict off the engine's roster makes a short declaration a
    ``KeyError`` rather than a quietly smaller pin.
    """
    short = {k: v for k, v in probe._PIN_VALUES.items() if k != _DROPPED}
    monkeypatch.setattr(probe, "_PIN_VALUES", short)
    with pytest.raises(KeyError) as excinfo:
        {k: probe._PIN_VALUES[k] for k in probe._engine_boolean_roster()}
    assert _DROPPED in str(excinfo.value)


def test_the_self_check_states_the_equality_in_its_stamped_lines():
    """The claim the operator reads is a claim something checked."""
    line = probe._self_check()[0]
    assert "IS the engine's boolean roster" in line
    assert f"all {len(probe._MEASURE_PIN)} of them" in line
    assert "size asserted, not a subset" in line


# ── (b) the honesty valve is witnessed on the REPORT path ────────────────────

def _report(*, moved=None, deltas=None, observed=None, identity_matches=True):
    """A report shaped exactly like the one ``run`` writes.

    ``moved`` flips one flag in the STAMPED machine state, which is the only
    state under which an empty delta list is a lie. Every other field is the
    honest one, so each leg fails for its own reason and no other.
    """
    flag_state = dict(probe._MEASURE_PIN)
    if moved:
        flag_state[moved] = not flag_state[moved]
    if deltas is None:
        deltas = {name: {"ambient": flag_state[name], "pinned": value}
                  for name, value in probe._MEASURE_PIN.items()
                  if flag_state[name] != value}
    return {
        "flag_state": flag_state,
        "measurement_identity_matches_machine": identity_matches,
        "measurement_flags": {
            "classification": dict(probe._MEASURE_PIN),
            "ambient_matches_pin": not deltas,
            "ambient_deltas": deltas,
            "observed_inside_measurement_scope":
                dict(probe._MEASURE_PIN) if observed is None else observed,
        },
    }


def test_an_honest_moved_machine_report_passes():
    """The positive control: a moved flag, named, is a sheet that may be read."""
    report = _report(moved=_MOVER, identity_matches=False)
    assert report["measurement_flags"]["ambient_deltas"], (
        "the fixture must actually have a delta to report, or the negative "
        "leg below proves nothing")
    assert probe._audit_stamp(report) is report


def test_report_path_refuses_a_silenced_valve():
    """A flag stamped off-pin and absent from the deltas must refuse the sheet.

    This is (b): the machine really has moved, so a valve that reports nothing
    is a valve that was silenced — and before round five the report path had
    no guard on it at all.
    """
    report = _report(moved=_MOVER, deltas={}, identity_matches=False)
    assert report["flag_state"][_MOVER] != probe._MEASURE_PIN[_MOVER]
    with pytest.raises(AssertionError) as excinfo:
        probe._audit_stamp(report)
    assert _MOVER in str(excinfo.value)


def test_report_path_refuses_a_delta_naming_the_wrong_lane():
    """The named delta must be the pair the sheet stamps, not any pair."""
    report = _report(moved=_MOVER, identity_matches=False)
    deltas = report["measurement_flags"]["ambient_deltas"]
    deltas[_MOVER] = {"ambient": probe._MEASURE_PIN[_MOVER],
                      "pinned": probe._MEASURE_PIN[_MOVER]}
    with pytest.raises(AssertionError) as excinfo:
        probe._audit_stamp(report)
    assert _MOVER in str(excinfo.value)


def test_report_path_refuses_a_headline_that_contradicts_its_delta_list():
    report = _report(moved=_MOVER, identity_matches=False)
    report["measurement_flags"]["ambient_matches_pin"] = True
    with pytest.raises(AssertionError) as excinfo:
        probe._audit_stamp(report)
    assert "ambient_matches_pin" in str(excinfo.value)


def test_report_path_refuses_a_stamped_set_that_is_not_the_measured_set():
    report = _report()
    report["flag_state"].pop(_MOVER)
    with pytest.raises(AssertionError) as excinfo:
        probe._audit_stamp(report)
    assert _MOVER in str(excinfo.value)


# ── (c) the counts were WITNESSED as measured under the pin ──────────────────

def test_report_path_refuses_an_unwitnessed_measurement_scope():
    """The flags observed INSIDE the loop's scope must be the pinned basis.

    Fixture: the witness carries the ambient value the machine would have
    supplied had the pin site been moved or dropped, so the absence being
    asserted is one that would otherwise be present.
    """
    observed = dict(probe._MEASURE_PIN)
    observed[_MOVER] = not observed[_MOVER]
    report = _report(observed=observed)
    with pytest.raises(AssertionError) as excinfo:
        probe._audit_stamp(report)
    message = str(excinfo.value)
    assert _MOVER in message
    assert "pin site" in message


def test_classify_refuses_a_name_measured_outside_the_pinned_scope():
    """Every measurement site refuses if it finds itself off the pin.

    Guarded before the frame is touched, so ``raw=None`` is enough: what is
    proved is that the refusal precedes the measurement, not that it survives
    one.
    """
    with flag_capture(**{_MOVER: not probe._MEASURE_PIN[_MOVER]}):
        with pytest.raises(AssertionError) as excinfo:
            probe._classify("KFY", None)
    message = str(excinfo.value)
    assert "KFY" in message and _MOVER in message


def test_classify_is_admitted_inside_the_pinned_scope():
    """The positive control for the refusal above: inside the scope it runs.

    A moved machine, the pin entered exactly as ``run`` enters it, and the
    guard lets the name through — so the refusal above is discriminating on
    the scope and not simply always raising.
    """
    with flag_capture(**{_MOVER: not probe._MEASURE_PIN[_MOVER]}):
        with flag_capture(**probe._MEASURE_PIN):
            probe._require_pinned_scope("ticker KFY")


@pytest.mark.slow
def test_run_on_a_moved_machine_still_measures_at_the_pin(tmp_path):
    """End to end: the machine moved, the sheet did not.

    The ambient is the flag MEASURED on 2026-09-01 to take KFY out of
    ``full_refusal_reachable`` (headline 4/4 -> 3/3) through the sibling
    ceiling-rest lane. With the pin site in place the counts must be the
    pinned ones, the witness must show the pinned value, and the sheet must
    say out loud that the machine has moved. Drop or move the pin site and
    every one of those three goes the other way.
    """
    out = tmp_path / "moved_ambient.json"
    with flag_capture(**{_MOVER: True}):
        assert getattr(settings, _MOVER) is True
        report = probe.run(str(out))

    flags = report["measurement_flags"]
    # the machine is stamped as moved, and the valve names the lane
    assert report["flag_state"][_MOVER] is True
    assert flags["ambient_matches_pin"] is False
    assert list(flags["ambient_deltas"]) == [_MOVER]
    # the WITNESS: inside the scope the twelve names were evaluated in, the
    # flag was at the pinned value, not the machine's
    assert flags["observed_inside_measurement_scope"][_MOVER] is False
    assert flags["observed_inside_measurement_scope"] == flags["classification"]
    # and therefore the counts are the pinned counts, not the moved machine's
    assert report["counts"]["full_refusal_reachable"] == 4
    assert report["counts"]["reachable_converting"] == 4
    assert "KFY" in [r["ticker"] for r in report["names"]
                     if r["verdict"] == "full_refusal_reachable"]
    # the two engine identities disagree, because the machine really has moved
    assert report["measurement_identity_matches_machine"] is False
    # the written sidecar is the audited object, not a second rendering
    assert json.loads(out.read_text(encoding="utf-8"))["counts"] == report["counts"]
    # and `run` really ran the audit: every leg above is pinned on its own, but
    # only this asserts the CALL still happens. Deleting it from `run` leaves
    # each leg green and publishes an unwitnessed sheet - the defect this
    # file's guards kept climbing one level to escape.
    assert report["audited"] == list(probe._AUDIT_LEGS)
    assert json.loads(out.read_text(encoding="utf-8"))["audited"] == \
        list(probe._AUDIT_LEGS)


def test_the_shipped_sidecar_carries_the_witness():
    """The artifact the operator eyeballs must contain all three claims."""
    path = os.path.join(_HERE, "..", "bar_posture_reachability.json")
    sheet = json.load(open(os.path.normpath(path), encoding="utf-8"))
    flags = sheet["measurement_flags"]
    assert flags["observed_inside_measurement_scope"] == flags["classification"]
    assert len(flags["classification"]) == len(probe._engine_boolean_roster())
    # and it must still survive its own audit
    assert probe._audit_stamp(copy.deepcopy(sheet)) is not None
    # the audit's own mark: every leg named, in the shipped artifact. Without
    # this the audit could be deleted from `run` and the sheet would look
    # identical - the defect this file's own guards kept moving one level up.
    assert sheet["audited"] == list(probe._AUDIT_LEGS)


def test_the_write_path_refuses_an_unaudited_sheet(monkeypatch):
    """Deleting the audit call must stop the sheet, not just weaken it.

    Every audit leg is pinned above, but a leg only runs if `run` still calls
    `_audit_stamp` - and nothing proved that. Here the audit is neutered to a
    pass-through (exactly what deleting the call leaves behind) and the write
    path must refuse before a byte is printed or written.
    """
    monkeypatch.setattr(probe, "_audit_stamp", lambda report: report)
    report = probe._audit_stamp(_report())      # the neutered pass-through
    assert "audited" not in report, (
        "the fixture must arrive unaudited, or the refusal below proves "
        "nothing about a deleted audit call")
    with pytest.raises(AssertionError, match="never audited"):
        probe._refuse_unaudited(report)


def test_the_refusal_names_a_partial_audit(monkeypatch):
    """A truncated leg list is as unread-able as no audit at all."""
    report = _report()
    report["audited"] = list(probe._AUDIT_LEGS)[:2]
    with pytest.raises(AssertionError, match="never audited"):
        probe._refuse_unaudited(report)
    report["audited"] = list(probe._AUDIT_LEGS)
    assert probe._refuse_unaudited(report) is report
