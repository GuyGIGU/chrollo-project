"""Deferred completion + ruled cohort cut (near-miss lane Task 8) — Beck.

The properties: the kill-leg screen is an EXACT necessary condition of the
ruled predicate (proven against completions on a real frame, not asserted),
the cap counts its drops (no silent truncation), the flagship EGBN class
survives end-to-end as a ruled row, and the flag-off twin degrades to the
plain evaluation. Fully OFFLINE (committed fixtures).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.evaluation import evaluate_ticker_with_near_miss
from engine_alpha.structure.gate_margins import (
    complete_leg_vector,
    ruled_near_miss,
)
from engine_alpha.structure.narrative import read_structure
from engine_alpha.structure.near_miss import (
    NearMissRecorder,
    _kill_leg_screen,
    deferred_rows,
)
from tools.marks_corpus import _FROZEN_BREADTH
from tools.marks_corpus import _load_fixture as _load_marks_fixture
from tools.replay import fixture_frame, prepared_frame

pytestmark = pytest.mark.regression


def _egbn_recorder():
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    raw = fixture_frame(frames, e["key"], e["ticker"])
    prep = prepared_frame(raw, "2026-01-15")
    assert prep is not None
    df, atr = prep
    rec = NearMissRecorder()
    read_structure(df, atr, near_miss=rec)
    return rec, e, frames


def test_flagship_egbn_is_a_ruled_row_end_to_end(monkeypatch):
    """The census headline as a living test: EGBN's refusal at as_of is a
    one-quantum occupancy near-miss — the lane must SEE it (Task 8's whole
    point), with the evidence fields render-complete."""
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    raw = fixture_frame(frames, e["key"], e["ticker"])
    sliced = raw.loc[:pd.Timestamp("2026-01-15")]

    result, rows, stats = evaluate_ticker_with_near_miss(
        e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert not isinstance(result, dict)      # EGBN stays a miss — no gate moved
    assert stats["ruled"] == len(rows) and rows, (
        f"EGBN produced no ruled near-miss rows (stats={stats})")
    flag = [r for r in rows if r["failing_leg"] == "occupancy"
            and r["margins"].get("lower_dwell") == -1]
    assert flag, f"the EGBN lower_dwell(-1) class is missing: {rows}"
    row = flag[0]
    assert row["ticker"] == "EGBN" and row["scan_date"] == "2026-01-15"
    assert row["pool"] in ("strict", "rescued", "band")
    assert row["lane_ruleset"] == "2026-07-26.A"
    assert row["fired_night"] == 0
    assert row["would_be_trigger"] == row["r_level"]
    assert row["scan_close"] > 0
    # Render-complete geometry: dates, never bar indices.
    for key in ("r_anchor_date", "s_anchor_date", "window_start_date",
                "window_end_date"):
        assert len(row[key]) == 10 and row[key].count("-") == 2


def test_kill_leg_screen_is_a_necessary_condition_of_the_ruling():
    rec, _e, _frames = _egbn_recorder()
    assert rec.records
    frame, atr = rec.frame, rec.atr
    checked = 0
    for r in rec.records.values():
        possible, _rank = _kill_leg_screen(r)
        if possible or r.pool == "band" or checked >= 40:
            continue
        window = frame.iloc[r.cand_start:r.cand_start + r.judged_len]
        if len(window) < 2:
            continue
        vector = complete_leg_vector(window, r.R, r.S, atr)
        if vector is None:
            continue
        checked += 1
        assert not ruled_near_miss(vector), (
            f"screen rejected a refusal whose completion IS ruled — the "
            f"necessary condition is broken on leg {r.leg}")
    assert checked >= 10, "too few screened-out refusals exercised"


def test_cap_drops_are_counted_never_silent(monkeypatch):
    rec, _e, _frames = _egbn_recorder()
    monkeypatch.setattr(settings, "NEAR_MISS_TOP_K", 1)
    rows, stats = deferred_rows(rec, fired=False, scan_close=25.0)
    assert stats["cap_dropped"] > 0
    assert len(rows) <= 1
    assert stats["records"] == len(rec.records)


def test_flag_off_twin_degrades_to_the_plain_evaluation(monkeypatch):
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", False)
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["status"] == "hit")
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]
    result, rows, stats = evaluate_ticker_with_near_miss(
        e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert isinstance(result, dict) and rows == [] and stats == {}


def test_fired_night_flag_rides_every_row_of_a_firing_ticker(monkeypatch):
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["status"] == "hit")
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]
    result, rows, _stats = evaluate_ticker_with_near_miss(
        e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert isinstance(result, dict)
    assert all(r["fired_night"] == 1 for r in rows)
