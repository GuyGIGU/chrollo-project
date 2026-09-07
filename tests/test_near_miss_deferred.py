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
    """The census headline as a living test AND the EC-17 happy path: the
    real cascade at production flag values, only the lane flag forced on —
    EGBN's refusal at as_of is a one-quantum occupancy near-miss the lane
    must SEE, with render-complete evidence, and the ticker fires in
    NEITHER flag state (recording is never a gate move)."""
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    raw = fixture_frame(frames, e["key"], e["ticker"])
    sliced = raw.loc[:pd.Timestamp("2026-01-15")]

    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", False)
    off, off_rows, off_stats = evaluate_ticker_with_near_miss(
        e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert not isinstance(off, dict) and off_rows == [] and off_stats == {}

    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
    result, rows, stats = evaluate_ticker_with_near_miss(
        e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert not isinstance(result, dict)      # fires in NEITHER state
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
    # The FULL vector rides every row (fourteen legs; window unconsulted at
    # the outer seam), and the evidence is render-complete: dates, never bar
    # indices, none of them past the evaluation day (as-of discipline).
    assert len(row["margins"]) == 14 and "window" not in row["margins"]
    for key in ("r_anchor_date", "s_anchor_date", "window_start_date",
                "window_end_date"):
        assert len(row[key]) == 10 and row[key].count("-") == 2
        assert row[key] <= "2026-01-15"


def test_truncation_sweep_keeps_every_row_as_of(monkeypatch):
    """As-of honesty: at every cut the emitted evidence uses only bars at or
    before that cut (dates are ISO, so string order IS date order)."""
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    raw = fixture_frame(frames, e["key"], e["ticker"])
    for cut in ("2026-01-08", "2026-01-12", "2026-01-15"):
        sliced = raw.loc[:pd.Timestamp(cut)]
        _result, rows, _stats = evaluate_ticker_with_near_miss(
            e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
        for row in rows:
            assert row["scan_date"] <= cut
            for key in ("r_anchor_date", "s_anchor_date",
                        "window_start_date", "window_end_date"):
                assert row[key] <= cut, (cut, key, row[key])


def test_kill_leg_screen_is_a_necessary_condition_of_the_ruling():
    """Every pool form included: band refusals rebuild their masked basis +
    pool laws exactly as deferred_rows does (review 2026-07-26 findings 1/8
    — the sweep used to skip band, leaving the screen unproven on the class
    the deep-event pool exists to observe)."""
    from engine_alpha.structure.rail_qualification import qualify_pair_events
    rec, _e, _frames = _egbn_recorder()
    assert rec.records
    frame, atr = rec.frame, rec.atr
    checked = 0
    for r in rec.records.values():
        possible, _rank = _kill_leg_screen(r)
        if possible or checked >= 40:
            continue
        completion_kw = {}
        if r.pool == "band":
            read = qualify_pair_events(frame.iloc[r.cand_start:], r.S, r.R, atr)
            window = (None if read is None
                      else frame.iloc[r.cand_start:][read["judged"]])
            if window is None or len(window) != r.judged_len:
                continue
            completion_kw = {
                "width_max": settings.BAND_MAX_BOX_WIDTH,
                "traversal_df": frame.iloc[
                    r.cand_start:r.cand_start + r.judged_len],
                "judged_mask": read["judged"]}
        else:
            window = frame.iloc[r.cand_start:r.cand_start + r.judged_len]
        if window is None or len(window) < 2:
            continue
        vector = complete_leg_vector(window, r.R, r.S, atr, **completion_kw)
        if vector is None:
            continue
        checked += 1
        assert not ruled_near_miss(vector), (
            f"screen rejected a refusal whose completion IS ruled — the "
            f"necessary condition is broken on leg {r.leg} (pool {r.pool})")
    assert checked >= 10, "too few screened-out refusals exercised"


def test_pool_precedence_keeps_one_row_per_framing():
    """The grain ruling (review 2026-07-26 finding 1, operator-delegated):
    per-pool records, pool-less archive identity — when one framing rules
    under two judging laws, the primary law wins and the shadowed row is
    COUNTED. Proven through deferred_rows on the real EGBN map with the
    ruled strict record cloned into a rescued-form sibling (same framing,
    same judged window — the strict/rescued reconstruction coincides)."""
    rec, _e, _frames = _egbn_recorder()
    base_rows, base_stats = deferred_rows(rec, fired=False, scan_close=25.0)
    assert base_rows, "the EGBN frame produced no ruled row"
    strict_ruled = {(r["r_level"], r["s_level"]) for r in base_rows
                    if r["pool"] == "strict"}
    assert strict_ruled, "no strict ruled row to clone"

    # Clone one ruled strict record into its rescued form (same framing,
    # same judged window — the strict/rescued reconstruction coincides).
    (win, _pool), ruled_rec = next(
        (k, v) for k, v in rec.records.items()
        if k[1] == "strict"
        and (round(v.R, 4), round(v.S, 4)) in strict_ruled)
    rec.records[(win, "rescued")] = ruled_rec._replace(pool="rescued")

    idx = rec.frame.index
    framing = (round(ruled_rec.R, 4), round(ruled_rec.S, 4),
               idx[ruled_rec.r_anchor].strftime("%Y-%m-%d"),
               idx[ruled_rec.s_anchor].strftime("%Y-%m-%d"))
    rows, stats = deferred_rows(rec, fired=False, scan_close=25.0)
    assert stats["pool_shadowed"] == base_stats["pool_shadowed"] + 1
    kept = [r for r in rows if (r["r_level"], r["s_level"], r["r_anchor_date"],
                                r["s_anchor_date"]) == framing]
    assert len(kept) == 1 and kept[0]["pool"] == "strict"


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
    # "Degrades to the plain evaluation" pinned as canonical-field EQUALITY,
    # not just firing (review 2026-07-26 finding 10): a drifted degrade
    # branch must red here, not in a live scan whose flag flipped mid-run.
    from core.pipeline.screener import _evaluate_ticker
    from tools import shadow_diff
    plain = _evaluate_ticker(e["ticker"], sliced,
                             float(e["spy_6m_return"]), _FROZEN_BREADTH)
    assert shadow_diff.canonical_fields(result) == \
        shadow_diff.canonical_fields(plain)


def test_fired_night_flag_rides_every_row_of_a_firing_ticker(monkeypatch):
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
    frames, baseline = _load_marks_fixture()
    flagged = 0
    for e in (x for x in baseline["setups"] if x["status"] == "hit"):
        sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
            :pd.Timestamp(e["first_fire"])]
        result, rows, _stats = evaluate_ticker_with_near_miss(
            e["ticker"], sliced, float(e["spy_6m_return"]), _FROZEN_BREADTH)
        assert isinstance(result, dict)
        assert all(r["fired_night"] == 1 for r in rows)
        flagged += len(rows)
        if flagged:
            break
    # The guard must never pass vacuously (review 2026-07-26 finding 10): at
    # least one firing ticker demonstrably records ruled refusals — if a
    # reseal dries every hit, this reds so the guard gets re-pointed
    # consciously instead of asserting nothing forever.
    assert flagged > 0, "no firing ticker produced a ruled refusal row"
