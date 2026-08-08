"""EC-17: the dark grade's happy path through the REAL cascade (build task 6).

Drives a realistic full-featured setup — the frozen shadow fixture, the same
frames the byte-parity guard replays — through the REAL chain with production
values for every other flag and ONLY ``TA_SCORE_V2`` forced on: the shared
eval-twins scoring context, result assembly, and the archive row assembly on
all three writer bases. Builder-in-isolation tests do not satisfy EC-17; this
suite is what lets the dark feature's death show up red. It GROWS with each
wave: the serialized-payload leg joins at task 9 (wire contract), the
fired_tags leg at task 10.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

from config import settings
from engine_alpha.evaluation import EVAL_ERROR
from engine_alpha.scoring import taxonomy
from engine_alpha.scoring.scoring import (
    sub_score_archive_values,
    ta_grade_archive_values,
)
from tools import shadow_diff


def _first_fired_result(monkeypatch):
    """The first shadow-fixture ticker that fires, evaluated flag-ON through
    the real per-ticker pipeline (production values for every other flag)."""
    monkeypatch.setattr(settings, "TA_SCORE_V2", True)
    frames, scalars = shadow_diff._load_fixture()
    spy = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = shadow_diff._evaluate_ticker(ticker, df, spy, breadth)
        if result is not None and result is not EVAL_ERROR:
            return ticker, result
    pytest.fail("no shadow-fixture ticker fires — the fixture rotted")


def test_ec17_flag_on_happy_path_through_the_real_cascade(monkeypatch):
    ticker, row = _first_fired_result(monkeypatch)

    # 1. The grade family on the REAL result: bounded, chapter-coherent,
    #    every promoted term point emitted under its archive-ready name.
    assert 0.0 <= row["_ta_grade"] <= 100.0
    chapters = row["_ta_grade_chapters"]
    assert tuple(chapters) == taxonomy.CHAPTER_ORDER
    cap_sum = taxonomy.structural_cap_sum()
    assert sum(chapters.values()) == pytest.approx(
        row["_ta_grade_raw"] * 100.0 / cap_sum, abs=1e-9)
    assert isinstance(row["_ta_grade_warnings"], dict)
    for term in taxonomy.ta_layer_terms():
        if term.present_when == "TA_SCORE_V2":
            assert ("_" + term.column) in row, (
                f"promoted term {term.key!r} missing from the flag-on result")
    # Wave-1 charter measurements ride the same flag-on result (task 7) —
    # keys always present; a None VALUE is a legal ABSENT reading.
    for key in ("_lps_shrink_frac", "_lps_window_classification",
                "_story_richness_rate", "_trend_base_count",
                "_inter_base_width_ratio"):
        assert key in row, f"charter measurement {key!r} missing flag-on"

    # 2. The v1 face is intact — the flag adds, never mutates.
    assert "Score" in row and "Tier" in row and "_sub_scores" in row

    # 3. Live-writer basis: the two producers read the row as the scan
    #    writer does, value-faithful.
    fam_live = ta_grade_archive_values(row.get, prefixed=True)
    assert fam_live["ta_grade"] == row["_ta_grade"]
    assert fam_live["ta_grade_raw"] == row["_ta_grade_raw"]
    assert fam_live["score_spring"] == row["_score_spring"]
    subs_live = sub_score_archive_values(row.get("_sub_scores"))
    assert subs_live["score_box_tightness"] == row["_sub_scores"]["box_tightness"]
    assert subs_live["score_puzzle_quality"] == row["_sub_scores"]["puzzle_quality"]

    # 4. Seed-twin basis: the adapter strips prefixes; the SAME producers on
    #    the adapted result must be byte-identical to the live basis.
    from core.archive.result_adapter import seed_row_from_result
    seed_result = seed_row_from_result(row)
    assert ta_grade_archive_values(seed_result.get, prefixed=False) == fam_live
    assert sub_score_archive_values(seed_result.get("sub_scores")) == subs_live

    # 5. The mapper path assembles a REAL model row (no DB required) and the
    #    grade columns ride it end to end.
    from archive_models import SetupArchive
    from services.archive_queries import archive_row_from_result
    kwargs = archive_row_from_result(seed_result, overrides={
        "ticker": ticker,
        "scan_date": "2026-01-01",
        "universe_type": "us_equities",
        "source": "seed",
        "setup_type": seed_result.get("setup_type", "LPS"),
        "tier": seed_result.get("tier", "C"),
        "score": seed_result.get("score", 0.0),
        **sub_score_archive_values(seed_result.get("sub_scores")),
    })
    SetupArchive(**kwargs)  # model-compatible or TypeError
    assert kwargs["ta_grade"] == pytest.approx(row["_ta_grade"])
    assert kwargs["ta_grade_raw"] == pytest.approx(row["_ta_grade_raw"])
    assert kwargs["score_spring"] == pytest.approx(row["_score_spring"])
    assert kwargs["puzzle_completeness"] == fam_live["puzzle_completeness"]


def test_flag_off_cascade_emits_no_v2_fields(monkeypatch):
    """The same real cascade flag-OFF: not one v2 field on the result — the
    eval-chain boundary's own absence proof (the scorer and wire tripwires
    guard their boundaries; this guards the canonical result row)."""
    monkeypatch.setattr(settings, "TA_SCORE_V2", False)
    frames, scalars = shadow_diff._load_fixture()
    spy = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None
    fired = None
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = shadow_diff._evaluate_ticker(ticker, df, spy, breadth)
        if result is not None and result is not EVAL_ERROR:
            fired = result
            break
    assert fired is not None, "no shadow-fixture ticker fires — the fixture rotted"
    v2_fields = [k for k in fired
                 if k.startswith("_ta_grade") or k.startswith("_score_")]
    assert not v2_fields, f"v2 field(s) {v2_fields} leaked from the flag-off cascade"
