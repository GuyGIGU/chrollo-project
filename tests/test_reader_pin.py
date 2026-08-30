"""Plumbing for the reader-vocabulary pin (tools.reader_pin).

The full pin is a named gate (`python -m tools.reader_pin --check`, ~5s over 88
fixture charts) run beside the marks-corpus ratchet, NOT inside the default
suite (Beck: gate cadence is a budget). These tests keep the cheap invariants
in pytest: the instrument imports, the committed baseline parses and covers
the three populations, the diff logic goes RED on drift (proven with literal
values, not fixture runs), and the position grid's stated-literal expectations
hold against the live function.
"""
import json
import os

from tools import reader_pin


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
    # Chart counts pinned: the sealed marks corpus (33), the negative corpus
    # (18), the shadow fixture (37, including its 5 rejecting tickers - the
    # population every other guard is blind to).
    assert len(pops["marks"]) == 33
    assert len(pops["junk"]) == 18
    assert len(pops["shadow"]) == 37
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
