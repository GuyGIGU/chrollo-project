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
    fractions = row["_ta_grade_chapter_fractions"]
    assert tuple(fractions) == taxonomy.CHAPTER_ORDER
    assert all(0.0 <= v <= 1.0 for v in fractions.values())
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

    # 1b. The grade is tied to the row's OWN inputs (2026-08-08 review,
    #     finding 3 — mutation-proven: an input-blind compose fed an empty
    #     dict at this seam passed every bound/coherence assertion above;
    #     this sum cross-check is what makes that mutation die). The raw is
    #     the affine sum of the fired row's ta-layer term points — the v1
    #     sub-scores plus the flag-promoted points, breadth excluded.
    expected_raw = sum(
        (row["_sub_scores"].get(t.key) or 0.0)
        for t in taxonomy.ta_layer_terms() if t.present_when is None
    ) + sum(
        (row["_" + t.column] or 0.0)
        for t in taxonomy.ta_layer_terms() if t.present_when is not None
    )
    assert row["_ta_grade_raw"] == pytest.approx(expected_raw, abs=1e-9)
    assert row["_ta_grade_raw"] > 0.0, (
        "a real fire always carries structural points — an all-zero grade "
        "means the composite stopped reading its inputs")

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
    assert subs_live["score_setup_quality"] == row["_sub_scores"]["setup_quality"]

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
    assert kwargs["setup_completeness"] == fam_live["setup_completeness"]

    # 6. The wire leg (task 9): the REAL payload builder serializes the v2
    #    block from the same fired row — resolved, display-rounded verdicts
    #    (EC-28), the archive keeping full precision.
    import pandas as pd
    from output import dashboard as dashboard_module
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker",
                        lambda *_a: None)
    monkeypatch.setattr(settings, "DASHBOARD_CHART_TIERS", [row["Tier"]],
                        raising=False)
    frames, _ = shadow_diff._load_fixture()
    chart = dashboard_module._extract_chart_data(
        {ticker: frames[ticker]}, pd.DataFrame([row]), [ticker, "_pad"])[ticker]
    assert chart["ta_grade"] == round(row["_ta_grade"], 1)
    assert chart["ta_grade_raw"] == round(row["_ta_grade_raw"], 2)
    assert tuple(chart["ta_grade_chapters"]) == taxonomy.CHAPTER_ORDER
    assert chart["trend_base_count"] == row["_trend_base_count"]
    assert set(chart["sub_scores"]) >= set(
        t.key for t in taxonomy.REGISTRY if t.present_when is None)

    # 7. The fired_tags leg (task 10): verdicts resolved on the real fire,
    #    every id inside the closed set, identical on the wire, JSON in the
    #    archive cell.
    assert isinstance(row["_fired_tags"], list)
    assert {e["id"] for e in row["_fired_tags"]} <= taxonomy.TAG_IDS
    assert chart["fired_tags"] == row["_fired_tags"]
    import json as _json
    archived = ta_grade_archive_values(row.get, prefixed=True)["fired_tags"]
    assert _json.loads(archived) == row["_fired_tags"]


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
    # The vocabulary-derived leak check (2026-08-08 review, finding 4): the
    # old two-prefix filter was blind to _fired_tags and the five charter
    # fields — six families the writers' unconditional splat would have
    # LANDED in dark-epoch rows on a one-edit regression.
    v2_names = {"_" + n for n in taxonomy.V2_ROW_FIELDS}
    v2_fields = [k for k in fired
                 if k.startswith("_ta_grade") or k.startswith("_score_")
                 or k in v2_names]
    assert not v2_fields, f"v2 field(s) {v2_fields} leaked from the flag-off cascade"
    # The writers' own view — every FLAG-GATED column the archive family
    # extraction would stamp must read None on the flag-off row (the family
    # also carries the three always-on setup grades — narrative outputs,
    # legitimately non-NULL flag-off). The gated subset derives from the
    # vocabulary + the score_ prefix, so a leak lands red at the exact
    # boundary the writers splat.
    fam = ta_grade_archive_values(fired.get, prefixed=True)
    gated = {c for c in fam
             if c in taxonomy.V2_ROW_FIELDS or c.startswith("score_")}
    leaked = {k: fam[k] for k in gated if fam[k] is not None}
    assert not leaked, (
        f"flag-off row carries non-NULL family cell(s) {leaked} — these "
        "would land in dark-epoch archive rows and destroy the "
        "NULL-means-pre-v2 epoch contract")
    # Coverage tripwire: every flag-gated field the eval block stamps must be
    # in the vocabulary this test derives from (a new charter measurement
    # that skips V2_ROW_FIELDS re-opens the blind spot).
    extraction_cols = set(fam)
    for name in ("lps_shrink_frac", "lps_window_classification",
                 "story_richness_rate", "trend_base_count",
                 "inter_base_width_ratio", "fired_tags"):
        assert name in extraction_cols and name in taxonomy.V2_ROW_FIELDS


def _fresh_archive_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    import archive_models  # noqa: F401 — register on Base before create_all
    import models          # noqa: F401

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_manual_writer_shape_commits_a_flag_on_row_to_a_real_db(monkeypatch):
    """2026-08-08 review, finding 1 (four seats independently; the crash
    reproduced): the manual writer shipped with only the sub-score splat, so
    the model pass bound resolve_fired_tags' Python LIST into the TEXT column
    — sqlite refused at commit, and the EC-19 closed-set refusals never ran
    on the third writer. Every prior guard stopped short of this cell: the
    parity test compares column NAMES, the row-assembly round-trip feeds
    string sentinels, and the cascade's mapper leg never flushed. This test
    drives the manual route's exact producer set on a REAL flag-on fire into
    a fresh create_all database and COMMITS — doubling as the legal-side
    crossing of the two closed-set CHECKs and the fired_tags JSON cell."""
    import json as _json

    from core.archive.result_adapter import seed_row_from_result
    from services.archive_queries import archive_row_from_result

    ticker, row = _first_fired_result(monkeypatch)
    seed_result = seed_row_from_result(row)
    kwargs = archive_row_from_result(seed_result, overrides={
        "ticker": ticker,
        "scan_date": "2026-01-01",
        "universe_type": "us_equities",
        "source": "manual",
        "setup_type": seed_result.get("setup_type", "LPS"),
        "tier": seed_result.get("tier", "C"),
        "score": seed_result.get("score", 0.0),
        # The manual route's two producers, same shapes as the route source
        # (pinned there by the parity AST guard requiring BOTH splats).
        **sub_score_archive_values(
            seed_result.get("sub_scores"),
            exclude=frozenset({"score_traversal_quality"})),
        **ta_grade_archive_values(seed_result.get, prefixed=False),
    })
    from archive_models import SetupArchive
    session = _fresh_archive_session()
    session.add(SetupArchive(**kwargs))
    session.commit()               # pre-fix: ProgrammingError fired exactly here
    stored = session.query(SetupArchive).one()
    assert _json.loads(stored.fired_tags) == row["_fired_tags"]
    assert stored.ta_grade == pytest.approx(row["_ta_grade"])
    assert stored.score_traversal_quality is None   # declared exclusion holds


def test_fresh_db_checks_refuse_illegal_closed_set_labels():
    """EC-19's DB leg for the two new label columns (2026-08-08 review, via
    Beck): a fresh create_all database must REFUSE an illegal label on a
    direct insert that bypasses the producer — the ReadVerdict/elected_pool
    precedent. (The producer-side refusal is pinned in test_scoring; the
    legal side commits through the real fire in the test above.)"""
    from sqlalchemy.exc import IntegrityError

    from archive_models import SetupArchive

    base = dict(ticker="AAA", scan_date="2026-01-01", setup_type="LPS",
                tier="B", score=90.0, current_price=10.0, r_level=11.0,
                s_level=9.5, trigger_price=11.1, base_length=30,
                box_width=0.1, touches=4, atr_ratio=0.5, lps_length=3,
                breach_days=0, vol_contraction=0.4, tightness_ratio=0.4,
                engine_config_version="hashX", source="screener")
    for col, bad in (("setup_chronology", "sideways"),
                     ("lps_window_classification", "diagonal_march")):
        session = _fresh_archive_session()
        session.add(SetupArchive(**base, **{col: bad}))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
