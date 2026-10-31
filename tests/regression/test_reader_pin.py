"""The reader pin (tools.regression.reader_pin), run for real plus its plumbing.

The pin is the fold acceptance for the alpha reader: what it SAYS about every committed fixture
chart (the boxes, the LPS, the state word, the events, the grade, the trail's stage words), read
with ``engine_alpha.reader.read`` and compared field by field against
``tests/baselines/reader_pin_baseline.json``. It is the only guard that can see a reading change
that keeps every fire and trigger. The real check runs here over the three committed populations
and as an explicit step in .github/workflows/quality.yml. It is hermetic - committed parquet +
baseline only, no network, no DB.

The remaining tests keep the cheap invariants: the committed baseline parses and covers the three
populations, the record shape is the one the baseline holds, the diff goes RED on drift and names
the chart (proven with literal values, not fixture runs), basis drift is named apart from reading
drift, and the three comparators (moved here from the retired fold_parity instrument) keep their
exactness.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import pytest

from tools.regression import reader_pin

pytestmark = pytest.mark.regression


def test_reader_pin_reports_no_reading_drift():
    """Run the REAL gate: every chart of every population, against the committed baseline.

    ``check_baseline()`` returns True iff the reader's record of every chart (the marks, the junk,
    the shadow fixture, including the charts that do not fire) matches the baseline exactly.
    """
    assert reader_pin.check_baseline() is True, (
        "reading drift: the alpha reader says something different about a fixture chart. Re-run "
        "`python -m tools.regression.reader_pin --check` to see the population/chart/field, then fix "
        "the regression - or, ONLY at a ruled reading seam (EC-29), re-capture with --capture in that "
        "same commit."
    )


def _baseline():
    assert os.path.exists(reader_pin._BASELINE_PATH), (
        "reader_pin baseline missing - run `python -m tools.regression.reader_pin --capture` "
        "at a clean seam commit (EC-29)")
    with open(reader_pin._BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_RECORD_KEYS = {"as_of", "failed", "refusal", "state", "state_days", "boxes", "lps", "events", "grade", "trail"}


def test_baseline_parses_and_covers_all_three_populations():
    baseline = _baseline()
    pops = baseline["populations"]
    assert set(pops) == {"marks", "junk", "shadow"}
    # The junk corpus (16: NVT left on the operator's Thu 10/09/2026 ruling, CHCT on his Sun
    # 13/09/2026 "The setups is valid" ruling) and the shadow fixture (37, including the tickers
    # that do not fire) are FIXED populations, so their counts stay pinned here.
    assert len(pops["junk"]) == 16
    assert len(pops["shadow"]) == 37
    # The marks population is NOT fixed: it follows the operator's drawings by his 2026-09-08
    # ruling, so it is bound to the corpus it is supposed to cover instead of a literal.
    from tools.regression.marks_corpus import load_corpus, setup_key
    corpus_keys = {setup_key(s) for s in load_corpus()}
    assert set(pops["marks"]) == corpus_keys, (
        "the reader pin does not cover exactly the current marks corpus - "
        "re-capture at the seam that moved the population (EC-29)")
    assert baseline["engine_config_version"] and baseline["ruleset"]
    # Every chart carries a basis digest and a whole record; no read crashed.
    for pop, charts in pops.items():
        for key, chart in charts.items():
            assert chart.get("digest"), f"{pop}/{key}: no basis digest"
            reading = chart.get("reading")
            assert reading is not None and set(reading) == _RECORD_KEYS, f"{pop}/{key}: record shape"
            assert reading["failed"] is False, f"{pop}/{key}: the read failed ({reading['refusal']})"
            assert isinstance(reading["trail"], list) and reading["trail"], f"{pop}/{key}: no trail"
    # The pin sees the fires too, and agrees with the junk gate on who fires on the frozen day:
    # the junk charts the reader reads as "fired" on their last day are exactly the cases whose
    # pinned fire days (tests/baselines/negative_corpus_baseline.json) include that day.
    from tools.regression.negative_corpus import load_known_fires
    pinned = load_known_fires()
    fired_junk = sorted(k for k, c in pops["junk"].items() if c["reading"]["state"] == "fired")
    last_day_pinned = sorted(k for k, c in pops["junk"].items() if c["reading"]["as_of"] in pinned.get(k, []))
    assert fired_junk == last_day_pinned and len(fired_junk) == 6, (fired_junk, last_day_pinned)


def test_the_record_rounds_prices_to_the_cent_and_keeps_stage_words_only():
    """The record is the reader's facts, prices to the cent, the trail as stage words (never the
    sentences): a reworded sentence is not a reading change, a moved cent is."""
    from engine_alpha.record import Box, Event, Grade, Line, Lps, Read, Step

    box = Box(Line(10.123456, dt.date(2026, 1, 5)), Line(9.0, dt.date(2026, 1, 7)), dt.date(2026, 1, 5))
    read = Read(ticker="AAA", as_of=dt.date(2026, 3, 2), boxes=(box,),
                lps=Lps(dt.date(2026, 2, 24), dt.date(2026, 2, 26), "parent", trigger_price=10.009),
                trail=(Step("box", "a long sentence"), Step("LPS", "another")), state="fired",
                events=(Event("SOS", dt.date(2026, 2, 10), 10.5049),),
                grade=Grade(score=61.234, letter="A", empty_days=2, base_days=30, holds=True))
    rec = reader_pin.chart_record(read)
    assert rec == {
        "as_of": "2026-03-02", "failed": False, "refusal": None, "state": "fired", "state_days": None,
        "boxes": [{"role": "parent", "R": 10.12, "S": 9.0, "opened": "2026-01-05", "end": None}],
        "lps": {"start": "2026-02-24", "end": "2026-02-26", "against": "parent", "trigger": 10.01, "how": None},
        "events": [{"kind": "SOS", "day": "2026-02-10", "price": 10.5}],
        "grade": {"letter": "A", "score": 61.23},
        "trail": ["box", "LPS"],
    }
    assert reader_pin.ticker_of("ALB:2026-04-13") == "ALB"
    assert reader_pin.ticker_of("BBVA@2026-06-05") == "BBVA"
    assert reader_pin.ticker_of("SWK") == "SWK"


def test_diff_goes_red_on_reading_drift_and_names_the_chart():
    base = {"populations": {"marks": {"ALB:2026-04-13": {"digest": "d1", "reading": {
        "state": "fired", "events": [{"kind": "SOS", "day": "2026-04-01", "price": 10.0}]}}}}}
    drifted = {"populations": {"marks": {"ALB:2026-04-13": {"digest": "d1", "reading": {
        "state": "crossed", "events": [{"kind": "SOS", "day": "2026-04-01", "price": 10.01}]}}}}}
    ok, lines = reader_pin.diff_readings(drifted, base)
    assert not ok
    assert lines == ["  marks/ALB:2026-04-13: events[0].price: 10.0 -> 10.01",
                     "  marks/ALB:2026-04-13: state: 'fired' -> 'crossed'"]


def test_diff_names_basis_drift_separately_from_reading_drift():
    base = {"populations": {"junk": {"ENIC": {"digest": "d1", "reading": {"x": 1}}}}}
    moved = {"populations": {"junk": {"ENIC": {"digest": "d2", "reading": {"x": 2}}}}}
    ok, lines = reader_pin.diff_readings(moved, base)
    assert not ok
    # Exactly ONE line, and it is the basis line - the per-field reading walk
    # must not run on a chart whose bars moved (the repairs differ).
    assert len(lines) == 1 and "BASIS DRIFT" in lines[0] and "junk/ENIC" in lines[0]


def test_diff_names_a_missing_and_a_new_chart():
    base = {"populations": {"shadow": {"ABEV": {"digest": "d1", "reading": {}}}}}
    cur = {"populations": {"shadow": {"SWK": {"digest": "d1", "reading": {}}}}}
    ok, lines = reader_pin.diff_readings(cur, base)
    assert not ok
    assert any("MISSING" in ln and "ABEV" in ln for ln in lines)
    assert any("NEW" in ln and "SWK" in ln for ln in lines)


def test_diff_passes_on_identical_snapshots():
    snap = {"populations": {"shadow": {"ABEV": {"digest": "d1", "reading": {"events": [], "grade": None}}}}}
    ok, lines = reader_pin.diff_readings(json.loads(json.dumps(snap)), snap)
    assert ok
    assert lines == []


def test_exact_equal_nan_and_exactness():
    assert reader_pin.exact_equal(float("nan"), float("nan"))
    assert reader_pin.exact_equal({"a": [1.0, float("nan")]}, {"a": [1.0, float("nan")]})
    assert not reader_pin.exact_equal(0.1234567, 0.1234568)
    assert not reader_pin.exact_equal({"a": 1}, {"a": 1.0})  # int vs float: dict path
    assert not reader_pin.exact_equal(1, 1.0)  # type-strict on scalars


def test_diff_paths_reports_asymmetric_keys():
    diffs = reader_pin.diff_paths({"a": 1, "gone": 2}, {"a": 1, "new": 3})
    joined = "\n".join(diffs)
    assert "gone" in joined and "ONLY IN BASELINE" in joined
    assert "new" in joined and "ONLY IN CURRENT" in joined
    assert not reader_pin.diff_paths({"a": {"b": [1.0, 2.0]}}, {"a": {"b": [1.0, 2.0]}})


def test_jsonable_unwraps_numpy_and_keeps_nan():
    import numpy as np

    out = reader_pin.jsonable({"a": np.float64(1.5), "b": np.int64(2), "c": np.bool_(True), "d": (1, 2),
                               "e": float("nan")})
    assert out["a"] == 1.5 and type(out["a"]) is float
    assert out["b"] == 2 and type(out["b"]) is int
    assert out["c"] is True and out["d"] == [1, 2]
    assert out["e"] != out["e"]
