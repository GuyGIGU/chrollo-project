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
from engine_alpha.scoring import taxonomy
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


def test_puzzle_quality_always_emitted():
    # The puzzle term is unconditional (folded 2026-07-18; formerly gated by
    # PUZZLE_SCORE_ENABLED via TermSpec.present_when) — all 15 terms emit.
    keys = taxonomy.emitted_keys()
    assert "puzzle_quality" in keys and len(keys) == 15


def test_only_breadth_is_regime_layer():
    # Locks the taxonomy decision: market-breadth is the ONLY scored term that
    # leaves the TA Score for the regime label (spy_trend is never a scored term).
    regime = [t.key for t in taxonomy.REGISTRY if t.layer == "regime"]
    assert regime == ["breadth_bonus"]


def test_layers_are_only_ta_or_regime():
    assert {t.layer for t in taxonomy.REGISTRY} == {"ta", "regime"}


def test_chapter_taxonomy_is_the_ruled_story_partition():
    # Operator-ruled 2026-08-06 (docs/decisions.md): the grade's breakdown reads
    # left→right like the chart — Cause → Work → Turn → Finish → Trend context.
    # This order is a RULING; changing it is a re-chaptering seam, not a tidy-up.
    assert taxonomy.CHAPTER_ORDER == (
        "cause", "work", "turn", "finish", "trend_context")
    for t in taxonomy.REGISTRY:
        if t.layer == "ta":
            assert t.chapter in taxonomy.CHAPTER_ORDER, (
                f"ta-layer term {t.key!r} declares no chapter — every graded "
                "term belongs to exactly one story chapter")
        else:
            assert t.chapter is None, (
                f"regime term {t.key!r} carries a chapter — the regime layer "
                "is outside the grade and has no story membership")
    # No orphan chapters: every ruled chapter has at least one term (an empty
    # chapter would render an empty breakdown segment).
    populated = {t.chapter for t in taxonomy.REGISTRY if t.chapter is not None}
    assert populated == set(taxonomy.CHAPTER_ORDER)


def test_chapter_map_covers_exactly_the_ta_layer():
    cm = taxonomy.chapter_map()
    assert set(cm) == {t.key for t in taxonomy.REGISTRY if t.layer == "ta"}
    assert all(ch in taxonomy.CHAPTER_ORDER for ch in cm.values())


def test_manifest_hashes_the_chapter_taxonomy():
    # Chapter membership is engine identity: the frozen-config manifest must
    # carry the taxonomy's own projection (one registry, no second map), so a
    # re-chaptering rotates engine_config_version like any weight. The batched
    # v2 settings names ride the same registration seam.
    from engine_alpha.freeze.manifest import collect_manifest
    m = collect_manifest()
    assert m["TA_GRADE_CHAPTER_ORDER"] == list(taxonomy.CHAPTER_ORDER)
    assert m["TA_GRADE_CHAPTER_MAP"] == {t.key: t.chapter for t in taxonomy.REGISTRY}
    for name in ("SCORE_SPRING", "TOUCH_POINT_RATE",
                 "LPS_TIGHTNESS_SLOPE", "VOL_CONTRACTION_SLOPE"):
        assert name in m, f"batched v2 setting {name} missing from the manifest"
