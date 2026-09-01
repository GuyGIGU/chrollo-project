"""Hermetic plumbing pins for tools.doctrine_audit (consolidation-method
Task 13 — Beck).

The doctrine gate is deliberately NOT in pytest's default cascade (it needs
the live payload + cache), which is exactly how it went silently dark once:
a spy pinning an old signature broke every read, and nothing red said so
until the next manual sitting (the 2026-08 arity trap). This leg pins ONLY
the gate's PLUMBING, payload-free, so a breaking engine change turns the
default pytest run red the same day:

* the polarity spy stays signature-TRANSPARENT and delegates verbatim;
* the abstention vocabulary matches the outcomes ``read_structure``
  actually emits (a renamed trace outcome must fail here, never silently
  convert vetoes into false refusals);
* the whole ``_audit_setup`` check table runs over TWO synthetic structures
  — a plain one, and one carrying a spring, an inner box and an LPS resting
  above resistance — so every conditional row of the table applies at least
  once and an attribute or signature drift anywhere in it raises here; a
  reachability leg pins that "anywhere" against the table's own rows;
* the D8 ceiling-rest invariant is inert while the flag is dark and binds
  (with the razor named) the day the exception goes live.

The judgments themselves are NOT re-tested here — the manual run over the
live payload stays mandatory after any engine-signature or election-path
change (the run-slot rule, AGENTS.md).
"""
from __future__ import annotations

import inspect
import re
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.structure import bricks
from engine_alpha.structure.narrative import read_structure
from tools import doctrine_audit


# ── the spied seam ──────────────────────────────────────────────────────────

def test_the_cause_spy_is_signature_transparent_and_delegates(monkeypatch):
    calls = []

    def fake_cause(*a, **k):
        calls.append((a, k))
        return True

    monkeypatch.setattr(bricks, "_cause_is_up", fake_cause)
    seen = {"up": None}
    spy = doctrine_audit._make_cause_spy(seen)
    kinds = {p.kind for p in inspect.signature(spy).parameters.values()}
    assert inspect.Parameter.VAR_POSITIONAL in kinds, (
        "the spy must accept any positional arity — pinning a spied "
        "signature broke the whole gate once (250/250 TypeError)")
    assert inspect.Parameter.VAR_KEYWORD in kinds
    assert spy(1, 2, key=3) is True
    assert calls == [((1, 2), {"key": 3})], "the spy must delegate verbatim"
    assert seen["up"] is True, "the spy must record the engine's own answer"


# ── the abstention vocabulary vs the walk's real outcomes ───────────────────

class _CompleteBricks:
    """A scripted walk that completes: one root, a box, no spring, an LPS."""

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar > 2:
            return None
        return SimpleNamespace(climax_bar=2, ar_bar=4, R=110.0, S=100.0)

    def validate_equilibrium(self, df, root, atr, trace=None, forms=None):
        return SimpleNamespace(S=100.0, R=110.0, start_bar=5, box_width=0.10)

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = SimpleNamespace(start_bar=20)
        return (lps, Counter()) if diagnose else lps

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=True, bridge_validated=True,
                               pre_box_trend="", box_trend="",
                               lps_tightness_ratio=0.0)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar


class _VetoBricks(_CompleteBricks):
    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=False, bridge_validated=False,
                               pre_box_trend="up", box_trend="up",
                               lps_tightness_ratio=0.99)


class _FloorBlockedBricks(_CompleteBricks):
    """A spring whose chronology floor blocks the only LPS: the floored call
    refuses, the unfloored diagnostic completes — the walk narrates
    ``lps_before_spring``."""

    def find_spring(self, df, box, atr):
        return SimpleNamespace(tip_bar=50, recovery_bar=53)

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = (None if start_floor_bar is not None
               else SimpleNamespace(start_bar=20))
        if diagnose:
            return lps, (Counter({"floored": 1}) if lps is None else Counter())
        return lps


def test_the_abstention_vocabulary_matches_the_walks_real_outcomes(monkeypatch):
    assert doctrine_audit._VETO_OUTCOMES == {"cause_absent",
                                             "lps_before_spring"}
    monkeypatch.setattr(settings, "CAUSE_BEFORE_EFFECT_VETO_ENABLED", True)
    trace: list = []
    assert read_structure(None, 1.0, bricks=_VetoBricks(), trace=trace) is None
    assert ({r.get("outcome") for r in trace}
            & doctrine_audit._VETO_OUTCOMES) == {"cause_absent"}

    assert settings.LPS_AFTER_SPRING_ENABLED is True
    trace = []
    assert read_structure(None, 1.0, bricks=_FloorBlockedBricks(),
                          trace=trace) is None
    assert ({r.get("outcome") for r in trace}
            & doctrine_audit._VETO_OUTCOMES) == {"lps_before_spring"}


# ── the check table over two synthetic structures ───────────────────────────

def _synthetic_frame(n=30, spring=None):
    H = np.full(n, 105.0)
    L = np.full(n, 101.0)
    C = np.full(n, 103.0)
    H[10] = 110.0                      # the R anchor's own high IS the rail
    L[15] = 100.0                      # the S anchor's own low IS the rail
    if spring is not None:
        L[spring.tip_bar] = 98.0       # the penetration under S that C1 reads
    idx = pd.bdate_range("2026-01-02", periods=n)
    return pd.DataFrame({"High": H, "Low": L, "Close": C}, index=idx)


def _synthetic_structure(zone="INSIDE", low=101.0, ext_box=0.0, ext_atr=0.0):
    box = SimpleNamespace(R=110.0, S=100.0, start_bar=5, r_anchor_bar=10,
                          s_anchor_bar=15, box_width=0.10)
    lps = SimpleNamespace(start_bar=20, end_bar=25, low_bar=24, low=low,
                          high=max(104.0, low + 0.5), zone_type=zone,
                          high_extension_box=ext_box,
                          high_extension_atr=ext_atr)
    return SimpleNamespace(climax_bar=2, ar_bar=4, phase_b_start_bar=5,
                           phase_b_end_bar=20, R=110.0, S=100.0, box=box,
                           inner=None, spring=None, lps=lps,
                           lps_in_inner=False, terminator="lps")


def _spring_synthetic_structure():
    """The sibling that carries what the plain one structurally cannot: a
    spring (C1-C6), an inner box (E1-E2) and an LPS resting above resistance
    (D5) — and, keyed on a cause the engine actually resolved, the A3
    terminality row. Phase B ends at the spring tip, so this is also the only
    synthetic that walks D6's spring branch. The zone is OVERSHOOT_R, which
    keeps D8 (INSIDE-only) out of the way of its own flag test below."""
    s = _synthetic_structure(zone="OVERSHOOT_R", low=110.5)
    s.spring = SimpleNamespace(tip_bar=12, recovery_bar=13,
                               spring_type="SPRING", undercut_atr=0.4)
    s.inner = SimpleNamespace(start_bar=8, R=108.0, S=102.0)
    s.phase_b_end_bar = 12             # the spring is what ends Phase B here
    s.terminator = "spring"
    return s


def _run_audit_setup(s, atr=1.0, cause_up=None):
    counts: Counter = Counter()
    violations: list = []

    def check(inv, tk, ok, detail=""):
        counts[inv] += 1
        if not ok:
            violations.append((inv, tk, detail))

    doctrine_audit._audit_setup("SYN", _synthetic_frame(spring=s.spring), atr,
                                s, cause_up,
                                {"R": 110.0, "S": 100.0, "base_len": 25},
                                check)
    return counts, violations


def test_audit_setup_check_table_runs_hermetically_and_holds():
    counts, violations = _run_audit_setup(_synthetic_structure())
    assert violations == []
    assert set(counts) == {
        "A1 climax<=ar", "A2 ar<=box_start", "B1 S<R", "B2 High[r_anchor]==R",
        "B3 Low[s_anchor]==S", "B4 anchors-in-box", "B5 box.start==pbs",
        "B6 payload-immobility", "D1 lps-exists", "D2 lps-window-order",
        "D3 lps-in-box", "D4 lps-price-order", "D6 terminator",
        "D7 A-B-spine"}, (
        "the applied-invariant set drifted — a renamed or vanished check is "
        "a silent coverage change; adjust THIS literal deliberately")


def test_the_spring_synthetic_runs_the_rows_the_plain_one_cannot_reach():
    counts, violations = _run_audit_setup(_spring_synthetic_structure(),
                                          cause_up=True)
    assert violations == []
    assert set(counts) == {
        "A1 climax<=ar", "A2 ar<=box_start", "A3 terminality", "B1 S<R",
        "B2 High[r_anchor]==R", "B3 Low[s_anchor]==S", "B4 anchors-in-box",
        "B5 box.start==pbs", "B6 payload-immobility", "C1 spring-low<S",
        "C2 reclaim-window", "C3 spring-reclaim>=S", "C4 spring-in-box",
        "C5 undercut>0", "C6 spring<=lps", "D1 lps-exists",
        "D2 lps-window-order", "D3 lps-in-box", "D4 lps-price-order",
        "D5 lps-above-R", "D6 terminator", "D7 A-B-spine",
        "E1 inner-starts-in-parent", "E2 inner-rails-ordered"}, (
        "the applied-invariant set drifted — a renamed or vanished check is "
        "a silent coverage change; adjust THIS literal deliberately")

    # A3 reads the frame twice over: highs for an up-cause, lows for a
    # down-cause ("down-causes mirror every climax check on LOWS"). The mirror
    # is a second attribute path and gets its own pass over the same structure.
    counts, violations = _run_audit_setup(_spring_synthetic_structure(),
                                          cause_up=False)
    assert counts["A3 terminality"] == 1 and violations == []


def test_d8_is_inert_dark_and_binds_on_the_live_flag(monkeypatch):
    launched = dict(zone="INSIDE", ext_box=0.5, ext_atr=1.0)  # above both caps
    assert 0.5 > settings.LPS_INSIDE_HIGH_EXTENSION_BOX_MAX
    assert 1.0 > settings.LPS_INSIDE_HIGH_EXTENSION_ATR_MAX

    # Dark: the invariant is never applied (the exception cannot have
    # sanctioned anything).
    monkeypatch.setattr(settings, "LPS_CEILING_REST_ENABLED", False)
    counts, _ = _run_audit_setup(_synthetic_structure(low=109.0, **launched))
    assert "D8 ceiling-rest-on-rail" not in counts

    # Live: a sanctioned rest ON the ceiling holds; a deep rest violates.
    monkeypatch.setattr(settings, "LPS_CEILING_REST_ENABLED", True)
    razor = settings.LPS_CEILING_REST_MAX_BELOW_R_ATR * 1.0
    on_rail = 110.0 - razor + 0.05
    too_deep = 110.0 - razor - 0.65
    counts, violations = _run_audit_setup(
        _synthetic_structure(low=on_rail, **launched))
    assert counts["D8 ceiling-rest-on-rail"] == 1 and violations == []
    counts, violations = _run_audit_setup(
        _synthetic_structure(low=too_deep, **launched))
    assert [v[0] for v in violations] == ["D8 ceiling-rest-on-rail"]


# ── the table's own rows vs the rows the synthetics reach ───────────────────

def test_every_row_of_the_check_table_is_reachable_hermetically():
    """The docstring's promise — drift ANYWHERE in the table raises here — only
    holds while every declared row is actually reached. Derived from
    ``_audit_setup``'s own source and compared against what the synthetics ran,
    so a NEW conditional row that no synthetic reaches turns pytest red the day
    it lands instead of sitting dark until the next manual sitting (the two
    literal sets above catch a renamed or vanished row; only this catches an
    added one)."""
    declared = set(re.findall(r'check\("([^"]+)"',
                              inspect.getsource(doctrine_audit._audit_setup)))
    plain, _ = _run_audit_setup(_synthetic_structure())
    springy, _ = _run_audit_setup(_spring_synthetic_structure(), cause_up=True)
    assert declared - set(plain) - set(springy) == {"D8 ceiling-rest-on-rail"}, (
        "a check-table row no synthetic reaches — it is dark until the next "
        "manual doctrine run; give it a synthetic (D8 is the one exception: "
        "it is flag-guarded and has its own inert/binding test above)")
