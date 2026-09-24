"""Story-pool guard net (Event Map program Task 9) — Beck.

"Consulted only when every prior pool is empty" is a design claim until it is
a behavioral test. These guards convert it:

1. **Per-identity election stability** — every Guided List HIT, replayed at
   its pinned first-fire session, is byte-identical on the canonical fields
   (rails, box, score, tier) with ``STORY_POOL_ENABLED`` forced ON vs OFF.
   Asserted per identity, never as an aggregate count — the bar-dwell
   campaign proved "converts the target" and "moves ten elections" coexist
   invisibly behind aggregates. Since the 2026-07-26 flip + reseal (26 -> 28)
   the two ruled story conversions are pinned BY NAME as the only hits whose
   flag-off leg is legally silent (story-caused fires); any third off-silent
   hit fails loudly.
2. **Whole-shadow-panel identity flag-ON** — the panel-scale dark-flag leak
   tripwire: canonical fields + ranking match the committed flag-off
   baseline (a NEW fire would surface as NEW in the diff, never silently).

The flag-ON negative-bench replay lives in test_negative_corpus.py (its
home, the two-form precedent). Red-step proof: with the last-resort guard
(`not pool`) deliberately removed and the story pool merged into the
ordinary pools, guard 1 goes RED (election drift on hits) — run during
Task-9 development, recorded in the implementation log.

Fully OFFLINE: committed marks-corpus + shadow fixtures only.
"""
from __future__ import annotations

import json
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.screening.screener import _evaluate_ticker
from tools.regression import shadow_diff
from tools.regression.marks_corpus import _FROZEN_BREADTH
from tools.regression.marks_corpus import _load_fixture as _load_marks_fixture
from core.calibration.replay import fixture_frame

pytestmark = pytest.mark.regression


# Hits that fire ONLY through the story pool — silent with the flag off.
#
# ANRO:2026-08-12 joined on 2026-09-08, and the distinction matters: it is one of
# the five marks the operator had DRAWN but which the sealed standard had never
# tested, so its story-causation is a DISCOVERY about a new chart, not an
# ordinary pool regressing into silence. That is exactly the difference this
# guard exists to police, and it is checkable: ANRO was absent from the previous
# baseline entirely, so there was no prior election of it to regress from.
#
# A future addition here must clear the same bar. If a mark that was ALREADY in
# the standard turns up off-silent, an ordinary pool HAS regressed and the fix is
# in the engine, never in this list.
_STORY_CAUSED_HITS = ["ANRO:2026-08-12", "NKTR:2026-04-10", "YPF:2026-05-18"]


def test_story_flag_on_keeps_every_hit_election_identical(monkeypatch):
    frames, baseline = _load_marks_fixture()
    hits = [e for e in baseline["setups"] if e["status"] == "hit"]
    # NOT a hard-coded floor. The Guided List follows the operator's drawings
    # (his 2026-09-08 ruling), so a literal here breaks this guard every time he
    # draws a chart, for a reason that has nothing to do with what it tests. The
    # floor itself is pinned once, in the committed baseline, by
    # tests/regression/test_marks_corpus.py. What THIS guard must never do is silently
    # compare nothing.
    assert len(hits) >= 20, (
        f"only {len(hits)} pinned hits to compare — the fixture is thin or empty "
        "and this guard would pass without exercising an election")

    story_only = []
    for e in hits:
        ticker = e["ticker"]
        sliced = fixture_frame(frames, e["key"], ticker).loc[
            :pd.Timestamp(e["first_fire"])]
        spy = float(e["spy_6m_return"])

        monkeypatch.setattr(settings, "STORY_POOL_ENABLED", False)
        off = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
        monkeypatch.setattr(settings, "STORY_POOL_ENABLED", True)
        on = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)

        assert isinstance(on, dict), (
            f"{e['key']}: pinned hit did not fire at {e['first_fire']}")
        if isinstance(off, dict):
            assert shadow_diff.canonical_fields(off) == shadow_diff.canonical_fields(on), (
                f"{e['key']}: canonical/election drift with the story pool ON — "
                "the last-resort construction has broken")
        else:
            assert on["_elected_pool"] == "story", (
                f"{e['key']}: off-silent hit elected via "
                f"{on['_elected_pool']!r} — only a story-caused fire may be "
                "silent with the flag off")
            story_only.append(e["key"])
    assert sorted(story_only) == _STORY_CAUSED_HITS, (
        f"story-caused hit set moved: {sorted(story_only)} — a new off-silent "
        "hit means an ordinary pool regressed OR a new story conversion "
        "landed unruled; re-pin deliberately")


def test_story_flag_on_shadow_panel_is_identical(monkeypatch):
    monkeypatch.setattr(settings, "STORY_POOL_ENABLED", True)

    frames, scalars = shadow_diff._load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    fields, scored = {}, []
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = _evaluate_ticker(ticker, df, spy_6m, breadth)
        if result is None or not isinstance(result, dict):
            continue
        fields[ticker] = shadow_diff.canonical_fields(result)
        scored.append((ticker, float(result["Score"])))

    ranking = [t for t, _ in sorted(scored, key=lambda x: (-x[1], x[0]))]
    # The baseline records each ticker's LAST fire in the fired window (build
    # step 1, 2026-09-13); this twin replays the frozen day alone, so it
    # compares against the baseline's frozen-day view.
    with open(shadow_diff._BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = shadow_diff.frozen_day_view(json.load(f), frames)
    ok, lines = shadow_diff.diff_against_baseline(
        {"fields": fields, "ranking": ranking}, baseline)
    assert ok, ("story-pool-ON canonical drift vs committed baseline:\n"
                + "\n".join(lines))


def test_story_pool_elects_the_ab_conversions_end_to_end(monkeypatch):
    """The feature's HAPPY PATH through the REAL cascade at production flag
    values (BAND_RAILS live, its pool naturally empty; only the story flag
    forced on): the two Task-14 fire-A/B conversions elect, carry the
    'story' pool label AND the exact admitting sentence into the evaluation
    result fields. A regression that couples the rung to the band flag,
    breaks the ruled admission, or drops the sentence reddens HERE — and
    the flag-off leg pins that these fires are story-CAUSED."""
    frames, baseline = _load_marks_fixture()
    by_key = {e["key"]: e for e in baseline["setups"]}
    # NKTR's final S-test is identity-UNFIXED on fire day (merge horizon
    # open at the edge -> '~', excluded from the as-of counts): admission
    # passed on the two knowable completed tests. The A/B record (2026-07-25)
    # predates the '~' rendering; semantics identical, marks refined.
    for key, fire_day, sentence in [
        ("NKTR:2026-04-10", "2026-04-09", "R+ S+ R+ S+ R+ S+~ R^"),
        ("YPF:2026-05-18", "2026-05-06", "S+ R+ S+ R^"),
    ]:
        e = by_key[key]
        sliced = fixture_frame(frames, key, e["ticker"]).loc[
            :pd.Timestamp(fire_day)]
        spy = float(e["spy_6m_return"])

        monkeypatch.setattr(settings, "STORY_POOL_ENABLED", False)
        off = _evaluate_ticker(e["ticker"], sliced, spy, _FROZEN_BREADTH)
        assert not isinstance(off, dict), (
            f"{key}: fires WITHOUT the story pool — no longer a story "
            "conversion; re-pin this guard deliberately")

        monkeypatch.setattr(settings, "STORY_POOL_ENABLED", True)
        on = _evaluate_ticker(e["ticker"], sliced, spy, _FROZEN_BREADTH)
        assert isinstance(on, dict), (
            f"{key}: the A/B story conversion no longer fires at {fire_day}")
        assert on["_elected_pool"] == "story", (
            f"{key}: elected via {on['_elected_pool']!r}, not the story pool")
        assert on["_story_admission_profile"] == sentence, (
            f"{key}: admitting sentence moved — "
            f"{on['_story_admission_profile']!r}")


def test_pool_label_stamping_point_refuses_unknown_labels():
    """The archive's electing-pool column is a CLOSED set enforced at the
    single stamping point — a future rung that mislabels (or leaves the
    Candidate slot unset) fails loudly instead of persisting 'None' and
    silently forking the rescued cohort."""
    from engine_alpha.structure.narrative.bricks import _pool_label

    for ok in ("strict", "rescued", "band", "story"):
        assert _pool_label(ok) == ok
    for bad in (None, "typo", "", "Strict"):
        with pytest.raises(ValueError, match="closed"):
            _pool_label(bad)


def test_archive_check_closes_the_elected_pool_set(tmp_path):
    """Fresh-DB DDL enforcement — the universe_type precedent applied to
    elected_pool: create_all carries a CHECK, so an illegal label cannot
    even be inserted around the stamping point on a new database."""
    import archive_models
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    eng = create_engine(f"sqlite:///{tmp_path / 'arch.db'}")
    archive_models.SetupArchive.__table__.create(bind=eng)
    db = sessionmaker(bind=eng)()

    def _row(ticker, pool):
        return archive_models.SetupArchive(
            ticker=ticker, scan_date="2026-07-26", setup_type="LPS",
            tier="A", score=1.0, s_level=90.0, trigger_price=0.0,
            source="screener", universe_type="us_equities",
            elected_pool=pool)

    for i, ok in enumerate(("strict", "rescued", "band", "story", None)):
        db.add(_row(f"OK{i}", ok))
    db.commit()

    db.add(_row("BAD", "typo"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_fires_carry_elected_pool_provenance():
    """Task 11: every fire archives its electing pool (closed set). The
    shadow fixture's ordinary fires must all read 'strict' — the label is
    unconditional (no flag), so a NULL here is a threading defect."""
    frames, scalars = shadow_diff._load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    seen = 0
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = _evaluate_ticker(ticker, df, spy_6m, breadth)
        if result is None or not isinstance(result, dict):
            continue
        seen += 1
        assert result.get("_elected_pool") in {"strict", "rescued", "band"}, (
            f"{ticker}: _elected_pool={result.get('_elected_pool')!r}")
    assert seen > 0, "no shadow fire evaluated — fixture problem"
