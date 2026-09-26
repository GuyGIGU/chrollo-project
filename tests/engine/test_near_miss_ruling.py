"""The RULED near-miss form — truth-table pin (near-miss lane Task 6; EC-18).

``gate_margins.ruled_near_miss`` is the ONE implementation of the operator
ruling (docs/near_miss_lane_2026-07.md §5, ruleset 2026-07-26.A): exactly one
T-COARSE-8 leg fails AND every failing fine leg is narrow (integer margins
within NEAR_MISS_MAX_QUANTA; float legs within the junk-calibrated decile
deficits). This table IS the ruling — an edit that moves any row is a
re-ruling (new ruleset + manifest rotation + census re-run), never a cleanup.
"""
from __future__ import annotations

import sys

import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.structure.box.gate_margins import (
    NEAR_MISS_RULESET,
    OCCUPANCY_FAMILY,
    coarse_failing_legs,
    ruled_near_miss,
)

pytestmark = pytest.mark.regression


def _vector(**margins):
    """A minimal leg vector: every named leg failing at the given margin,
    padded with a couple of passing legs so the shape is realistic."""
    vec = {
        "width": {"leg": "width", "measured": 0.10, "threshold": 0.18,
                  "margin": 0.08, "passed": True},
        "respect_share": {"leg": "respect_share", "measured": 2, "threshold": 5,
                          "margin": 3, "passed": True},
    }
    for leg, margin in margins.items():
        vec[leg] = {"leg": leg, "measured": None, "threshold": None,
                    "margin": margin, "passed": margin >= 0}
    return vec


def test_ruleset_identity():
    assert NEAR_MISS_RULESET == "2026-07-26.A"
    assert settings.NEAR_MISS_MAX_QUANTA == 1


def test_truth_table():
    cases = [
        # (description, vector, verdict)
        ("zero failing legs", _vector(), False),
        ("one int leg at -1 (EGBN's lower_dwell class)",
         _vector(lower_dwell=-1), True),
        ("one int leg at -2 — narrow it is not (N1)",
         _vector(lower_dwell=-2), False),
        ("TWO occupancy fine legs, both -1 = ONE ruled concept (the YPF pin)",
         _vector(lower_dwell=-1, mid_dwell=-1), True),
        ("occupancy -1 AND respect_share -1 = two coarse legs",
         _vector(lower_dwell=-1, respect_share=-1), False),
        ("occupancy concept with one member deep: -1 and -2 mix",
         _vector(lower_dwell=-1, mid_dwell=-2), False),
        ("respect_run alone at -1", _vector(respect_run=-1), True),
        ("respect_share alone at -1", _vector(respect_share=-1), True),
        ("respect pair co-failing = two coarse legs",
         _vector(respect_share=-1, respect_run=-1), False),
        ("window alone at -1 (self-resolving dynamics, still recorded)",
         _vector(window=-1), True),
        ("width within the junk decile", _vector(width=-0.005), True),
        ("width beyond the junk decile", _vector(width=-0.02), False),
        ("crash IN, within its decile", _vector(crash=-0.005), True),
        ("crash beyond its decile", _vector(crash=-0.02), False),
        ("traversal_density within its decile",
         _vector(traversal_density=-0.005), True),
        ("traversal_density beyond", _vector(traversal_density=-0.05), False),
        # Exactly AT each sealed decile: the boundary is IN, and the row is
        # sourced from the settings constant so a re-ruling moves it with the
        # ruleset (review 2026-07-26 finding 10 — a > vs >= rewrite must red).
        ("width exactly at its decile",
         _vector(width=-settings.NEAR_MISS_WIDTH_DEFICIT_MAX), True),
        ("crash exactly at its decile",
         _vector(crash=-settings.NEAR_MISS_CRASH_DEFICIT_MAX), True),
        ("traversal_density exactly at its decile",
         _vector(traversal_density=-settings.NEAR_MISS_DENSITY_DEFICIT_MAX),
         True),
        ("traversal pair co-failing = two coarse legs",
         _vector(traversal_count=-1, traversal_density=-0.005), False),
        ("None vector", None, False),
    ]
    for desc, vec, want in cases:
        assert ruled_near_miss(vec) is want, desc


def test_coarse_collapse_matches_the_family():
    vec = _vector(lower_dwell=-1, upper_dwell=-3, coverage=-2)
    assert coarse_failing_legs(vec) == ["occupancy"]
    vec2 = _vector(respect_run=-1, lower_dwell=-1)
    assert coarse_failing_legs(vec2) == ["respect_run", "occupancy"]
    assert set(OCCUPANCY_FAMILY) == {
        "r_touches", "s_touches", "r_touch_thirds", "s_touch_thirds",
        "lower_dwell", "upper_dwell", "mid_dwell", "coverage"}


def test_narrowness_reads_settings_lazily(monkeypatch):
    vec = _vector(lower_dwell=-2)
    assert ruled_near_miss(vec) is False
    monkeypatch.setattr(settings, "NEAR_MISS_MAX_QUANTA", 2)
    assert ruled_near_miss(vec) is True     # AP-3: call-time read, no cache
