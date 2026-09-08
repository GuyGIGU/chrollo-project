"""The reader-vocabulary pin (tools.reader_pin), run for real plus its plumbing.

The pin used to be a DARK gate: `python -m tools.reader_pin --check` was named
in AGENTS.md and wired into nothing, so its coverage depended on a human
remembering to type it — and it is the ONLY guard that can see a change to what
the rail readers SAY on a chart whose canonical output fields never move
(council review 2026-09-07, finding 11). The real check now runs here, over the
88 committed fixture charts, and as an explicit step in .github/workflows/
quality.yml beside the marks-corpus ratchet (the same belt-and-braces the
shadow-output guard already gets). It is hermetic — committed parquet + baseline
only, no network, no DB — and costs ~6s.

The remaining tests keep the cheap invariants: the instrument imports, the
committed baseline parses and covers the three populations, the diff logic goes
RED on drift (proven with literal values, not fixture runs), and the position
grid's stated-literal expectations hold against the live function.
"""
import json
import os

import pytest

from tools import reader_pin


@pytest.mark.regression
def test_reader_pin_reports_no_reading_drift():
    """Run the REAL gate: every reader, every fixture chart, against the
    committed baseline.

    `check_baseline()` returns True iff every pinned reader surface on all 88
    charts (33 marks + 18 junk + 37 shadow, including the 5 rejecting tickers
    every other guard is blind to) matches the baseline exactly, and the
    position grid still holds its stated literals.
    """
    assert reader_pin.check_baseline() is True, (
        "reader-vocabulary drift: a rail reader says something different about "
        "a fixture chart. Re-run `python -m tools.reader_pin --check` to see the "
        "population/chart/field, then fix the regression - or, ONLY at a ruled "
        "vocabulary seam (EC-29), re-capture with --capture in that same commit."
    )


def _baseline():
    assert os.path.exists(reader_pin._BASELINE_PATH), (
        "reader_pin baseline missing - run `python -m tools.reader_pin --capture` "
        "at a clean seam commit (EC-29)")
    with open(reader_pin._BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_baseline_parses_and_covers_all_three_populations():
    baseline = _baseline()
    pops = baseline["populations"]
    assert set(pops) == {"marks", "junk", "shadow"}
    # The junk corpus (18) and the shadow fixture (37, including its 5 rejecting
    # tickers - the population every other guard is blind to) are FIXED
    # populations, so their counts stay pinned here.
    assert len(pops["junk"]) == 18
    assert len(pops["shadow"]) == 37
    # The marks population is NOT fixed: it follows the operator's drawings by
    # his 2026-09-08 ruling, so a literal here would break this guard every time
    # he draws a chart. Bind it to the corpus it is supposed to cover instead —
    # which is the stronger check anyway: the old literal would have passed with
    # the pin covering 33 charts that were not the 33 in the corpus.
    from tools.marks_corpus import load_corpus, setup_key
    corpus_keys = {setup_key(s) for s in load_corpus()}
    assert set(pops["marks"]) == corpus_keys, (
        "the reader pin does not cover exactly the current marks corpus — "
        "re-capture at the seam that moved the population (EC-29)")
    assert baseline["pin_window_bars"] == reader_pin.PIN_WINDOW_BARS
    assert baseline["engine_config_version"]
    # Every chart derived a basis and a reading - no silent underivable holes.
    for pop, charts in pops.items():
        for key, chart in charts.items():
            assert chart.get("reading") is not None, f"{pop}/{key}: no reading"
            assert chart.get("window_digest"), f"{pop}/{key}: no window digest"


def test_diff_goes_red_on_reading_drift_and_names_it():
    base = {"populations": {"marks": {"ALB": {"window_digest": "d1",
                                              "reading": {"episode_stats": {"profile": "S+ R^"}}}}},
            "position_grid": []}
    drifted = {"populations": {"marks": {"ALB": {"window_digest": "d1",
                                                 "reading": {"episode_stats": {"profile": "S+ R+"}}}}},
               "position_grid": []}
    ok, lines = reader_pin.diff_readings(drifted, base)
    assert not ok
    assert any("marks/ALB" in ln and "profile" in ln for ln in lines)


def test_diff_names_basis_drift_separately_from_reading_drift():
    base = {"populations": {"junk": {"ENIC": {"window_digest": "d1", "reading": {"x": 1}}}},
            "position_grid": []}
    moved = {"populations": {"junk": {"ENIC": {"window_digest": "d2", "reading": {"x": 1}}}},
             "position_grid": []}
    ok, lines = reader_pin.diff_readings(moved, base)
    assert not ok
    # Exactly ONE line, and it is the basis line - the per-field reading walk
    # must not run on a chart whose bars moved (the repairs differ).
    assert len(lines) == 1 and "BASIS DRIFT" in lines[0]


def test_diff_passes_on_identical_snapshots():
    snap = {"populations": {"shadow": {"ABEV": {"window_digest": "d1",
                                                "reading": {"episodes": []}}}},
            "position_grid": [{"inputs": {}, "position": "at_ceiling"}]}
    ok, lines = reader_pin.diff_readings(json.loads(json.dumps(snap)), snap)
    assert ok
    assert lines == []


def test_position_grid_literal_expectations_hold():
    # The stated-in-advance values (reasoned from inner_box.py's documented
    # conventions, never copied from a run). The refusal rows must NEVER move;
    # the band rows move only at the ruled Task-6 tolerance seam (EC-29).
    assert reader_pin._verify_position_grid() == []
