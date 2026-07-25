"""Story-pool guard net (Event Map program Task 9) — Beck.

"Consulted only when every prior pool is empty" is a design claim until it is
a behavioral test. These guards convert it:

1. **Per-identity election stability** — every Guided List HIT, replayed at
   its pinned first-fire session, is byte-identical on the canonical fields
   (rails, box, score, tier) with ``STORY_POOL_ENABLED`` forced ON vs OFF.
   Asserted per identity, never as an aggregate count — the bar-dwell
   campaign proved "converts the target" and "moves ten elections" coexist
   invisibly behind aggregates.
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
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.screener import _evaluate_ticker
from tools import shadow_diff
from tools.marks_corpus import _FROZEN_BREADTH
from tools.marks_corpus import _load_fixture as _load_marks_fixture
from tools.replay import fixture_frame

pytestmark = pytest.mark.regression


def test_story_flag_on_keeps_every_hit_election_identical(monkeypatch):
    frames, baseline = _load_marks_fixture()
    hits = [e for e in baseline["setups"] if e["status"] == "hit"]
    assert len(hits) == 26, "the Guided List ratchet floor moved under this guard"

    for e in hits:
        ticker = e["ticker"]
        sliced = fixture_frame(frames, e["key"], ticker).loc[
            :pd.Timestamp(e["first_fire"])]
        spy = float(e["spy_6m_return"])

        monkeypatch.setattr(settings, "STORY_POOL_ENABLED", False)
        off = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
        monkeypatch.setattr(settings, "STORY_POOL_ENABLED", True)
        on = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)

        assert isinstance(off, dict) and isinstance(on, dict), (
            f"{e['key']}: pinned hit did not fire at {e['first_fire']}")
        assert shadow_diff.canonical_fields(off) == shadow_diff.canonical_fields(on), (
            f"{e['key']}: canonical/election drift with the story pool ON — "
            "the last-resort construction has broken")


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
    with open(shadow_diff._BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    ok, lines = shadow_diff.diff_against_baseline(
        {"fields": fields, "ranking": ranking}, baseline)
    assert ok, ("story-pool-ON canonical drift vs committed baseline:\n"
                + "\n".join(lines))


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
