"""Near-miss collector guard net (near-miss lane Task 7) — Beck.

The collector sits on the exact seam where the bar-dwell campaign proved
aggregate guards go blind, so the acceptance is per-identity, not a count:

1. **Per-identity election stability** — every Guided List HIT replayed at
   its pinned first-fire, ``NEAR_MISS_LANE_ENABLED`` forced ON vs OFF: both
   legs fire and the canonical fields are identical PER IDENTITY. The
   recorder observes refusals; it may never perturb an election.
2. **Whole-shadow-panel flag-ON** — canonical fields + ranking equal the
   committed flag-off baseline (the panel-scale leak tripwire).
3. **Flag-ON negative-corpus replay** — every junk case stays refused, and
   refused identically, with the collector running.
4. **EC-8 inert leg** — flag-off constructs nothing: the recorder class is
   boobytrapped and the evaluation must never touch it.
5. **Recorder mechanics** — offset rebase, keep-first dedup, counters; plus
   a real-frame collection smoke (legs speak the registry vocabulary).

Fully OFFLINE: committed marks-corpus / shadow / negative fixtures only.
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
from engine_alpha.structure import near_miss as near_miss_mod
from engine_alpha.structure.box_gates import GATE_LEG_INDEX
from engine_alpha.structure.narrative import read_structure
from tools import negative_corpus, shadow_diff
from tools.marks_corpus import _FROZEN_BREADTH
from tools.marks_corpus import _load_fixture as _load_marks_fixture
from tools.replay import fixture_frame, prepared_frame

pytestmark = pytest.mark.regression


def test_lane_flag_on_keeps_every_hit_election_identical(monkeypatch):
    frames, baseline = _load_marks_fixture()
    hits = [e for e in baseline["setups"] if e["status"] == "hit"]
    assert len(hits) == 28, "the Guided List ratchet floor moved under this guard"

    for e in hits:
        ticker = e["ticker"]
        sliced = fixture_frame(frames, e["key"], ticker).loc[
            :pd.Timestamp(e["first_fire"])]
        spy = float(e["spy_6m_return"])

        monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", False)
        off = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
        monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
        on = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)

        assert isinstance(off, dict) and isinstance(on, dict), (
            f"{e['key']}: pinned hit did not fire on both legs "
            f"(off={type(off).__name__}, on={type(on).__name__})")
        assert shadow_diff.canonical_fields(off) == \
            shadow_diff.canonical_fields(on), (
                f"{e['key']}: canonical/election drift with the collector ON "
                "— a measure-only recorder moved an election")


def test_lane_flag_on_shadow_panel_is_identical(monkeypatch):
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)

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
    assert ok, ("collector-ON canonical drift vs committed baseline:\n"
                + "\n".join(lines))


def test_lane_flag_on_negative_corpus_stays_refused(monkeypatch):
    frames, meta = negative_corpus._load_fixture()
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        raw = frames.get(key)
        assert raw is not None and not raw.empty, f"fixture frame missing: {key}"
        sliced = raw.loc[:pd.Timestamp(case["as_of"])]

        monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", False)
        off = _evaluate_ticker(case["ticker"], sliced, 0.0, _FROZEN_BREADTH)
        monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
        on = _evaluate_ticker(case["ticker"], sliced, 0.0, _FROZEN_BREADTH)

        assert not isinstance(on, dict), (
            f"negative case {key} FIRED with the collector on")
        assert type(on) is type(off), (
            f"negative case {key}: outcome class drifted flag-on "
            f"({type(off).__name__} -> {type(on).__name__})")


def test_flag_off_is_construction_free(monkeypatch):
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["status"] == "hit")
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]

    def _boom(*a, **k):
        raise AssertionError("NearMissRecorder constructed with the flag OFF")
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", False)
    monkeypatch.setattr(near_miss_mod, "NearMissRecorder", _boom)
    result = _evaluate_ticker(e["ticker"], sliced,
                              float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert isinstance(result, dict)   # the hit still fires, untouched


def test_recorder_mechanics_and_real_frame_collection():
    rec = near_miss_mod.NearMissRecorder()
    rec.begin_consultation(10)
    rec.refusal("width", "strict", 4, 8, 4, 110.0, 100.0, 30, 0.21, 0.18)
    rec.begin_consultation(0)
    rec.refusal("width", "strict", 14, 18, 14, 110.0, 100.0, 30, 0.21, 0.18)
    # Same physical pair seen from two consultations -> ONE record (keep-first).
    assert rec.n_refusals == 2 and rec.n_repeats == 1
    (key, row), = rec.records.items()
    assert key == (14, 18, 14)                      # df-absolute identity
    assert row.leg == "width" and row.pool == "strict"
    assert row.r_anchor == 14 and row.judged_len == 30

    # Real-frame smoke: a busy fixture evaluation collects a non-trivial map
    # speaking the registry vocabulary.
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    raw = fixture_frame(frames, e["key"], e["ticker"])
    prep = prepared_frame(raw, e["key"].split(":", 1)[1])
    assert prep is not None
    df, atr = prep
    live = near_miss_mod.NearMissRecorder()
    read_structure(df, atr, near_miss=live)
    assert live.records, "a busy frame recorded zero refusals"
    legal_extra = {"occupancy"}                     # the family verdict label
    for row in live.records.values():
        assert row.leg in GATE_LEG_INDEX or row.leg in legal_extra, row.leg
        assert row.pool in ("strict", "rescued", "band")
        assert row.judged_len > 0
