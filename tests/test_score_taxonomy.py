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

from config import settings
from core.scoring import taxonomy
from core.archive.analyze import SUB_SCORES


def test_registry_columns_match_analyze_sub_scores():
    # The persisted columns the registry declares must equal the set analyze.py
    # correlates over — the archive/analysis coupling.
    assert set(taxonomy.archive_columns()) == set(SUB_SCORES)
    assert len(taxonomy.archive_columns()) == len(SUB_SCORES)   # no dupes


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
