"""Canonical gate-leg registry + structured seam records (near-miss lane Task 1).

The gate legs' one machine-readable home (``box_gates.GATE_LEGS``) and the
recontracted cascade trace: a rejection record carries leg id + measured
statistic + threshold as NUMBERS with the sentence derived from the same
values, and the width/window narration sites do zero work when trace is None
(the argument-evaluation leak fix). Behavioral pins only — no per-leg string
unit tests beyond the derivation contract itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
import engine_alpha.structure.box_primitives as bp
from engine_alpha.structure.box_gates import (
    GATE_LEG_INDEX,
    GATE_LEGS,
    _occupancy_failures,
    _occupancy_leg_failures,
    leg_threshold,
)

pytestmark = pytest.mark.regression

_STAGES = {"width", "window", "respect", "occupancy", "traversal"}


def _frame(closes, lo_off=0.4, hi_off=0.4):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "High": closes + hi_off,
        "Low": closes - lo_off,
        "Close": closes,
    })


def _boxy_closes(n=40, lo=100.0, hi=110.0):
    out = []
    for i in range(n):
        cyc = i % 8
        out.append(lo + (hi - lo) * (cyc / 4 if cyc <= 4 else (8 - cyc) / 4))
    return out


def test_registry_binds_every_leg_to_a_live_threshold():
    # Unique ids, known stages, and every settings binding resolvable at call
    # time (AP-3 lazy reads) — a renamed knob must fail HERE, not in a lane
    # cohort three programs later.
    ids = [spec.leg for spec in GATE_LEGS]
    assert len(ids) == len(set(ids))
    assert set(GATE_LEG_INDEX) == set(ids)
    for spec in GATE_LEGS:
        assert spec.stage in _STAGES
        assert spec.op in (">=", "<=")
        if spec.setting:
            assert hasattr(settings, spec.setting), spec.leg
            assert leg_threshold(spec.leg) == getattr(settings, spec.setting)
    with pytest.raises(ValueError):
        leg_threshold("window")   # caller-bound: the floor arrives as an argument


def test_occupancy_prose_derives_from_the_structured_failures():
    # Build an eq dict failing a known subset relative to the LIVE thresholds,
    # so the pin survives recalibration.
    touches_min = settings.EQ_MIN_TOUCHES_PER_RAIL
    thirds_min = settings.EQ_MIN_TOUCH_THIRDS
    dwell_min = settings.EQ_MIN_HALF_DWELL
    eq = {
        "r_touch_thirds": thirds_min - 1,          # fails (clustered)
        "s_touch_thirds": thirds_min,              # passes
        "lower_dwell": round(dwell_min / 2, 4),    # fails (dead space low)
        "upper_dwell": dwell_min,                  # passes
        "mid_dwell": settings.EQ_MAX_MID_DWELL,    # passes (cap inclusive)
        "coverage": settings.EQ_MIN_COVERAGE,      # passes
    }
    failures = _occupancy_leg_failures(eq, touches_min - 1, touches_min)
    legs = [rec["leg"] for rec, _msg in failures]
    assert legs == ["r_touches", "r_touch_thirds", "lower_dwell"]
    for rec, msg in failures:
        # The sentence is derived from the record's own numbers.
        assert str(rec["measured"]) in msg
        assert str(rec["threshold"]) in msg
        assert rec["threshold"] == leg_threshold(rec["leg"])
    # The legacy prose surface is a pure projection of the structured one.
    assert _occupancy_failures(eq, touches_min - 1, touches_min) == \
        [msg for _rec, msg in failures]
    # An all-passing read yields nothing on either surface.
    ok_eq = dict(eq, r_touch_thirds=thirds_min,
                 lower_dwell=dwell_min)
    assert _occupancy_leg_failures(ok_eq, touches_min, touches_min) == []


def _assert_leg_contract(trace):
    rejected = [rec for rec in trace
                if rec["verdict"] == "rejected" and rec["stage"] in _STAGES]
    assert rejected, "fixture must exercise at least one gate rejection"
    for rec in rejected:
        assert rec["legs"], f"stage {rec['stage']} record carries no legs"
        for leg in rec["legs"]:
            assert leg["leg"] in GATE_LEG_INDEX
            assert isinstance(leg["threshold"], (int, float))
            # measured is a number wherever the gate had it in hand; only the
            # declared kill-site unknowns (crash min-low, respect run max) may
            # ride as None until the completion primitive fills them.
            if leg["measured"] is None:
                assert leg["leg"] in ("crash", "respect_run")
        if rec["stage"] == "width":
            (leg,) = rec["legs"]
            assert rec["detail"] == (
                f"box_width {leg['measured']:.3f} > "
                f"MAX_BOX_WIDTH {leg['threshold']}")
    return {rec["stage"] for rec in rejected}


def test_cascade_rejections_carry_structured_legs_with_derived_sentences():
    # (a) A worked range whose window ends on a 12-bar breakout shelf ABOVE the
    # rails: the outside share survives but the consecutive-run cap kills —
    # the respect_run leg rides with its numerators and measured=None.
    closes = _boxy_closes(60) + [125.0] * 12
    trace_a: list = []
    bp.collect_zigzag_candidates(_frame(closes), len(closes), atr_val=1.0,
                                 enforce_traversal=True, trace=trace_a)
    stages_a = _assert_leg_contract(trace_a)
    assert "respect" in stages_a
    run_legs = [leg for rec in trace_a if rec["stage"] == "respect"
                for leg in rec["legs"] if leg["leg"] == "respect_run"]
    assert run_legs, "the run-cap kill must be narrated as the respect_run leg"
    for leg in run_legs:
        assert leg["measured"] is None
        assert leg["outside"] >= 1 and leg["n"] > leg["outside"]

    # (b) A short worked stretch drowned in a mid-band plateau: respect passes,
    # the occupancy family kills (starved touches at minimum) — every failing
    # check rides as a structured leg.
    closes = _boxy_closes(16) + [105.0] * 24
    trace_b: list = []
    bp.collect_zigzag_candidates(_frame(closes), len(closes), atr_val=1.0,
                                 enforce_traversal=True, trace=trace_b)
    stages_b = _assert_leg_contract(trace_b)
    assert "occupancy" in stages_b


def test_width_rejections_are_narrated_and_forced(monkeypatch):
    # Force every pair through the width gate to pin that site's contract.
    monkeypatch.setattr(settings, "MAX_BOX_WIDTH", 1e-6)
    df = _frame(_boxy_closes())
    trace: list = []
    got = bp.collect_zigzag_candidates(df, len(df), atr_val=1.0,
                                       enforce_traversal=True, trace=trace)
    assert got == []
    stages = {rec["stage"] for rec in trace if rec["verdict"] == "rejected"}
    assert "width" in stages
    for rec in trace:
        if rec["stage"] == "width":
            (leg,) = rec["legs"]
            assert leg["leg"] == "width"
            assert leg["threshold"] == pytest.approx(1e-6)


def test_trace_none_narration_sites_do_no_work(monkeypatch):
    # The width/window sites must not even CALL the trace helper when trace is
    # None — the f-string argument evaluation was measured live-path work.
    def _boom(*a, **k):
        raise AssertionError("_trace_pair called on the trace=None path")
    monkeypatch.setattr(bp, "_trace_pair", _boom)
    monkeypatch.setattr(settings, "MAX_BOX_WIDTH", 1e-6)   # every pair width-rejects
    df = _frame(_boxy_closes())
    assert bp.collect_zigzag_candidates(df, len(df), atr_val=1.0,
                                        enforce_traversal=True, trace=None) == []
