"""Coupling guards for the sub-score taxonomy registry (core/scoring/taxonomy.py).

These are the tripwires that make the registry the single source of truth: if a
sub-score is added / renamed / dropped without updating the registry, or a cap
setting disappears, or breadth stops being the only regime-layer term, one of
these fails. They assert the registry stays in lock-step with the archive columns
(analyze.SUB_SCORES) and config settings — WITHOUT changing any behavior.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

import pytest

from config import settings
from core.scoring import taxonomy
from core.archive.analyze import SUB_SCORES


def test_analyze_sub_scores_are_registry_sourced():
    # analyze.py now derives its list FROM the registry (not a re-typed literal),
    # so they are identical by construction — this pins that wiring stays in place.
    assert SUB_SCORES == taxonomy.archive_columns()
    assert len(SUB_SCORES) == len(set(SUB_SCORES))   # no dupes


def test_persisted_columns_follow_score_prefix_convention():
    # Every persisted column is 'score_' + its result key. Combined with the
    # engine anchor (test_taxonomy_emitted_keys_match_score_setup_output), this ties
    # the registry's columns back to real score_setup output, not just to itself.
    for term in taxonomy.REGISTRY:
        if term.column is not None:
            assert term.column == f"score_{term.key}"


def test_every_cap_setting_resolves_to_a_number():
    for term in taxonomy.REGISTRY:
        assert hasattr(settings, term.cap_setting), f"missing setting {term.cap_setting}"
        assert isinstance(term.cap(), float)


def test_emitted_keys_track_the_puzzle_flag(monkeypatch):
    monkeypatch.setattr(settings, "PUZZLE_SCORE_ENABLED", False)
    off = taxonomy.emitted_keys()
    assert "puzzle_quality" not in off and len(off) == 14
    monkeypatch.setattr(settings, "PUZZLE_SCORE_ENABLED", True)
    assert "puzzle_quality" in taxonomy.emitted_keys()


def test_only_breadth_is_regime_layer():
    # Locks the taxonomy decision: market-breadth is the ONLY scored term that
    # leaves the TA Score for the regime label (spy_trend is never a scored term).
    regime = [t.key for t in taxonomy.REGISTRY if t.layer == "regime"]
    assert regime == ["breadth_bonus"]


def test_layers_are_only_ta_or_regime():
    assert {t.layer for t in taxonomy.REGISTRY} == {"ta", "regime"}


def test_structural_cap_sum_is_all_ta_caps_excluding_breadth():
    # The 0-100 divisor sums every emitted TA-layer cap; breadth (regime) is the
    # only scored term excluded, and it must be a pure config function > 0.
    ta_keys = {t.key for t in taxonomy.ta_layer_terms()}
    assert "breadth_bonus" not in ta_keys
    assert taxonomy.structural_cap_sum() > 0
    caps = taxonomy.caps()  # default flags -> puzzle off, so also excluded
    expected = sum(c for k, c in caps.items()
                   if k not in ("breadth_bonus", "puzzle_quality"))
    assert taxonomy.structural_cap_sum() == pytest.approx(expected)
