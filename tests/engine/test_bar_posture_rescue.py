"""The bar-posture rescue lane (consolidation-method Task 7,
``BAR_POSTURE_RESCUE_ENABLED``, dark) — the S-test form's ceiling leg in the
operator's unit (the bar's HIGH engages the rail zone), armed ONLY by the
full-refusal escalation's explicit roster.

The scope IS the design, exactly as the contraction rescue's: it can only
ever ADD a read where the whole walk elected nothing, so the fleet census's
QTTB loss (a wholesale-swap artifact: an older root story-admits a wider
frame and first-complete-wins ends the walk early) is unreachable by
construction, while all 12 census new fires — verified full refusals at
baseline — stay reachable. These guards pin:

* both escalation flags off + full refusal  -> ONE walk (live path);
* the bar lane alone re-walks a full refusal with the variant in the roster,
  stamped ``bar_posture_rescue``;
* an electing frame is never re-walked; a cause-before-effect veto is final;
* the variant is NEVER in the baseline roster (the paying read is blind to
  it — the species preset cannot arm it either);
* end-to-end on the corpus: EGBN converts on the banked A/B's exact date and
  tier through the story pool with the self-naming record. The A/B converted
  two operator-ruled names; the second, PKE:2026-02-24, left when he deleted
  that drawing and redrew the setup at 2026-04-07, which fires at baseline
  (2026-09-08).

The junk-defense leg (flag forced on over the must-NOT-fire corpus) lives in
test_negative_corpus.py, its home.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.screening.screener import _evaluate_ticker
from engine_alpha.structure.events.event_map import (
    ADMISSION_FORM_RESISTANCE_CONTRACTION,
    ADMISSION_FORM_S_TEST_BAR_POSTURE,
    baseline_admission_roster,
)
from engine_alpha.structure.narrative import Structure, read_structure
from tools.regression import shadow_diff
from tools.regression.marks_corpus import _FROZEN_BREADTH
from tools.regression.marks_corpus import _load_fixture as _load_marks_fixture
from core.calibration.replay import fixture_frame

pytestmark = pytest.mark.regression


class _RefusingBricks:
    """Every walk refuses immediately; ``walks`` counts how many walks ran."""

    def __init__(self):
        self.walks = 0

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar == 0:
            self.walks += 1
        return None


class _BarFormSensitiveBricks(_RefusingBricks):
    """Full refusal on the baseline roster; a complete story once the
    bar-posture variant arrives in the walk's explicit roster."""

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar == 0:
            self.walks += 1
        if search_from_bar > 10:
            return None
        return SimpleNamespace(climax_bar=10, ar_bar=20, R=110.0, S=100.0)

    def validate_equilibrium(self, df, root, atr, trace=None, forms=None):
        if forms is None or ADMISSION_FORM_S_TEST_BAR_POSTURE not in forms:
            return None
        return SimpleNamespace(S=100.0, R=110.0, start_bar=20, box_width=0.10)

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = SimpleNamespace(start_bar=85)
        return (lps, None) if diagnose else lps

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=True, bridge_validated=True,
                               pre_box_trend="", box_trend="",
                               lps_tightness_ratio=0.0)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar


class _AlwaysElectingBricks(_BarFormSensitiveBricks):
    def validate_equilibrium(self, df, root, atr, trace=None, forms=None):
        return SimpleNamespace(S=100.0, R=110.0, start_bar=20, box_width=0.10)


class _VetoedBricks(_AlwaysElectingBricks):
    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=False, bridge_validated=False,
                               pre_box_trend="up", box_trend="up",
                               lps_tightness_ratio=0.99)


def test_flag_defaults_dark_and_never_in_the_baseline_roster():
    assert settings.BAR_POSTURE_RESCUE_ENABLED is False
    assert ADMISSION_FORM_S_TEST_BAR_POSTURE not in baseline_admission_roster()
    # Even the species preset's arming cannot pull the variant into the
    # baseline — it is an escalation-only form by design.
    from engine_alpha.structure.context.htf import window_override
    with window_override({"POWER_PLAY_STORY_FORM_ENABLED": True}):
        assert ADMISSION_FORM_S_TEST_BAR_POSTURE not in \
            baseline_admission_roster()


def test_both_lanes_off_full_refusal_is_one_walk():
    assert settings.CONTRACTION_RESCUE_ENABLED is False
    bricks = _RefusingBricks()
    assert read_structure(None, 1.0, bricks=bricks) is None
    assert bricks.walks == 1, "flags off must stay a single walk (live path)"


def test_bar_lane_rewalks_a_full_refusal_with_the_variant_armed(monkeypatch):
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    bricks = _BarFormSensitiveBricks()
    trace: list = []
    s = read_structure(None, 1.0, bricks=bricks, trace=trace)
    assert isinstance(s, Structure), "the escalated walk should have elected"
    assert bricks.walks == 2
    stamped = [r for r in trace if r.get("pass") == "bar_posture_rescue"]
    assert stamped and trace[-1]["outcome"] == "complete", (
        "a bar-posture-only escalation stamps its own pass name")


def test_both_lanes_arm_one_rewalk_with_the_contraction_stamp(monkeypatch):
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    bricks = _BarFormSensitiveBricks()
    trace: list = []
    s = read_structure(None, 1.0, bricks=bricks, trace=trace)
    assert isinstance(s, Structure)
    assert bricks.walks == 2, "two lanes armed is still ONE re-walk"
    assert all(r.get("pass") == "contraction_rescue"
               for r in trace if "pass" in r), (
        "with the contraction lane armed the frozen stamp stands")


def test_species_armed_baseline_still_escalates_the_bar_variant(monkeypatch):
    """The species preset arms the contraction in the BASELINE roster; the
    bar variant still escalates on top — one re-walk, its own stamp."""
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "POWER_PLAY_STORY_FORM_ENABLED", True)
    bricks = _BarFormSensitiveBricks()
    trace: list = []
    s = read_structure(None, 1.0, bricks=bricks, trace=trace)
    assert isinstance(s, Structure)
    assert bricks.walks == 2
    assert all(r.get("pass") == "bar_posture_rescue"
               for r in trace if "pass" in r), (
        "the contraction is already in the baseline, so the escalation set "
        "holds only the bar variant — the stamp says so")


def test_bar_lane_never_runs_when_a_structure_elects(monkeypatch):
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    bricks = _AlwaysElectingBricks()
    assert isinstance(read_structure(None, 1.0, bricks=bricks), Structure)
    assert bricks.walks == 1


def test_bar_lane_never_relitigates_a_cause_veto(monkeypatch):
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "CAUSE_BEFORE_EFFECT_VETO_ENABLED", True)
    bricks = _VetoedBricks()
    assert read_structure(None, 1.0, bricks=bricks) is None
    assert bricks.walks == 1


def test_bar_lane_converts_the_banked_ab_names_end_to_end(monkeypatch):
    """The banked A/B's acceptance evidence, reproduced at the SCOPED lane
    (battery.log 2026-08-31: the wholesale in-memory swap converted exactly
    EGBN and PKE, junk silent, shadow byte-identical): EGBN fires on the
    operator-ruled date and tier through the story pool, self-naming, with
    the contraction lane OFF — this is the bar variant's own road."""
    frames, baseline = _load_marks_fixture()
    by_key = {e["key"]: e for e in baseline["setups"]}
    # PKE:2026-02-24 was the A/B's second conversion. The operator DELETED that
    # drawing and redrew the setup at 2026-04-07, which the engine fires at
    # BASELINE, so it left the corpus on 2026-09-08 when the standard began
    # following his current drawings; this half of the guard retired with it
    # when this branch merged onto that standard (2026-09-24), exactly as the
    # contraction rescue's did (tests/engine/test_miss_program_lanes.py).
    # RECORDED, because it is a real loss: the flag is still dark awaiting his
    # ruling, and the banked A/B cited both names.
    for key, fire_day, tier in [("EGBN:2026-01-15", "2026-01-07", "A")]:
        e = by_key[key]
        assert e["status"] == "miss", (
            f"{key} is no longer a sealed expected-miss — this guard and the "
            "ratchet need a deliberate re-pin")
        sliced = fixture_frame(frames, key, e["ticker"]).loc[
            :pd.Timestamp(fire_day)]

        monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", False)
        off = _evaluate_ticker(e["ticker"], sliced, 0.0, _FROZEN_BREADTH)
        assert not isinstance(off, dict), (
            f"{key}: fires WITHOUT the lane — no longer a bar-posture "
            "conversion; re-pin this guard deliberately")

        monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
        on = _evaluate_ticker(e["ticker"], sliced, 0.0, _FROZEN_BREADTH)
        assert isinstance(on, dict), (
            f"{key}: the bar-posture conversion no longer fires at {fire_day}")
        assert on["_elected_pool"] == "story"
        assert on["_story_admission_profile"].startswith(
            "engaged at resistance"), (
            f"{key}: the record lost the behavior name — "
            f"{on['_story_admission_profile']!r}")
        assert on["Tier"] == tier


def test_bar_lane_keeps_an_ordinary_hit_byte_identical(monkeypatch):
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"]
             if x["status"] == "hit" and x["key"].startswith("VLO"))
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]
    spy = float(e["spy_6m_return"])
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", False)
    off = _evaluate_ticker(e["ticker"], sliced, spy, _FROZEN_BREADTH)
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    on = _evaluate_ticker(e["ticker"], sliced, spy, _FROZEN_BREADTH)
    assert isinstance(off, dict) and isinstance(on, dict)
    assert shadow_diff.canonical_fields(off) == shadow_diff.canonical_fields(on)


# ── the ruling-sourced truth table (consolidation-method Task 11, EC-27) ────

def _stats(**over):
    base = {"n_completed_s": 2, "terminal_r_engagement": True,
            "terminal_s_drift": False, "terminal_r_posture": False}
    base.update(over)
    return base


def test_bar_posture_truth_table_admits_and_refuses_each_leg():
    from engine_alpha.structure.events.event_map import story_admission_bar_posture

    # The admitting row: >=2 completed support tests + the bar engages the
    # ceiling + not bleeding on the floor. Posture (the close) is IGNORED —
    # that is the whole variant.
    assert story_admission_bar_posture(_stats()) is True
    assert story_admission_bar_posture(_stats(terminal_r_posture=True)) is True
    # Each refusing leg, one at a time (EC-27: the guard must say WHICH).
    assert story_admission_bar_posture(_stats(n_completed_s=1)) is False
    assert story_admission_bar_posture(
        _stats(terminal_r_engagement=False)) is False
    assert story_admission_bar_posture(
        _stats(terminal_s_drift=True)) is False


def test_bar_posture_is_a_strict_superset_of_the_s_test_form():
    from engine_alpha.structure.events.event_map import (
        story_admission, story_admission_bar_posture)

    # Posture implies engagement by the reader's construction, so every
    # close-form admission is a bar-form admission; the variant's whole gain
    # is the engaged-without-posture right edge (the EGBN class).
    close_admits = _stats(terminal_r_posture=True, terminal_r_engagement=True)
    assert story_admission(close_admits) is True
    assert story_admission_bar_posture(close_admits) is True
    egbn_class = _stats(terminal_r_posture=False, terminal_r_engagement=True)
    assert story_admission(egbn_class) is False
    assert story_admission_bar_posture(egbn_class) is True


def test_bar_posture_refuses_unreadable_silence():
    from engine_alpha.structure.events.event_map import story_admission_bar_posture

    # EC-54 at the judgment layer: a frame whose verdict bars were unreadable
    # produces zero COMPLETED tests (unreadable episodes never count), so the
    # form refuses — silence can never admit.
    assert story_admission_bar_posture(
        _stats(n_completed_s=0, terminal_r_engagement=True)) is False
