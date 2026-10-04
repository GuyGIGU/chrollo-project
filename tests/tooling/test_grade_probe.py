"""The grade probe (task 14): its statistics on numbers whose answer is known, its measures pinned on one of his
drawings and one junk chart, and its measures and directions held to the hypotheses written down before it ran
(the decisions row of Mon 05/10/2026), so the numbers he is shown are the ones that row promised."""
from __future__ import annotations

import numpy as np
import pytest


def test_the_rank_separation_counts_the_junk_reading_worse_in_the_stated_direction_ties_half():
    from tools.calibration.grade_probe import auc

    junk = np.array([False, False, True, True])
    assert auc(np.array([1.0, 2.0, 3.0, 4.0]), junk, +1) == 1.0
    assert auc(np.array([1.0, 2.0, 3.0, 4.0]), junk, -1) == 0.0
    assert auc(np.array([1.0, 1.0, 1.0, 1.0]), junk, +1) == 0.5
    assert auc(np.array([1.0, 3.0, 2.0, 4.0]), junk, +1) == 0.75


def test_leave_one_chart_out_judges_each_chart_by_a_cut_placed_without_it():
    from tools.calibration.grade_probe import best_cut, loco

    junk = np.array([False] * 4 + [True] * 4)
    apart = np.array([1.0, 2.0, 3.0, 4.0, 11.0, 12.0, 13.0, 14.0])
    assert loco(apart, junk, +1) == 1.0
    assert loco(apart, junk, -1) <= 0.5, "the wrong direction cannot read as a separation"
    assert best_cut(apart, junk) == pytest.approx(7.5), "half way between the last of his and the first junk"
    # one of his reads like the junk: left out, the others place the cut under it, and it is called junk
    mixed = np.array([1.0, 2.0, 3.0, 12.5, 11.0, 12.0, 13.0, 14.0])
    assert loco(mixed, junk, +1) == pytest.approx(0.5 * (1.0 + 3 / 4))
    # a junk chart right by his: placed with it, the cut sits under it (all eight right); placed WITHOUT it, the
    # cut sits half way to the next junk and it is called his — the score a cut earns on charts it never saw
    near = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 11.0, 12.0, 13.0])
    assert best_cut(near, junk) == pytest.approx(4.5)
    assert loco(near, junk, +1) == pytest.approx(0.5 * (3 / 4 + 1.0))


def test_the_measures_and_their_directions_are_the_ones_written_down_before_the_probe_ran():
    from tools.calibration import grade_probe

    assert grade_probe.MEASURES == (("H", +1), ("S1", +1), ("S2", -1), ("S3", +1), ("V", +1), ("E", -1))
    assert grade_probe.CONTROL == ("S0", +1)
    assert (grade_probe.SHUFFLES, grade_probe.TOGETHER, grade_probe.KEEP) == (2000, 0.7, 3)
    assert grade_probe.LETTERS == ((75.0, "S"), (50.0, "A"), (25.0, "B"))
    assert grade_probe.BAR == ("BMRN", "FRPH", "COLM")


def test_the_grade_ramps_from_his_median_to_the_junk_median_and_the_letter_follows():
    from tools.calibration.grade_probe import grade, letter, ramps

    junk = np.array([False, False, False, True, True, True])
    table = {"S1": np.array([0.1, 0.2, 0.3, 0.5, 0.6, 0.7])}
    ends = ramps(table, junk, ["S1"])
    assert ends == {"S1": (pytest.approx(0.2), pytest.approx(0.6))}
    assert grade({"S1": 0.1}, ends) == 100.0 and grade({"S1": 0.9}, ends) == 0.0
    assert grade({"S1": 0.4}, ends) == pytest.approx(50.0)
    assert [letter(g) for g in (100.0, 75.0, 74.9, 50.0, 25.0, 24.9)] == ["S", "S", "A", "A", "B", "C"]


@pytest.fixture(scope="module")
def unf_and_frph() -> tuple:
    from tools.calibration import core_board
    from tools.regression import negative_corpus
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture

    frames, _ = load_sealed_fixture()
    unf = next(s for s in load_corpus() if setup_key(s) == "UNF:2026-07-10")
    his = core_board.score_setup(unf, fixture_frame(frames, "UNF:2026-07-10", "UNF"))["on_last"]
    junk_frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c.get("key", c["ticker"]) == "FRPH")
    frph = core_board.junk_row(case, junk_frames["FRPH"])["fires"][0]
    return his, frph


def test_on_the_readers_own_box_his_unf_has_bars_as_tall_as_the_box_like_the_junk_frph(unf_and_frph):
    """The probe's finding in one pair: measured as his "answer a." reads (bars almost as tall as the gap between
    the lines), his own UNF and the junk FRPH look alike."""
    from tools.calibration.grade_probe import measures

    unf, frph = (measures(row) for row in unf_and_frph)
    assert (unf["box"], unf["days"], frph["box"], frph["days"]) == ("parent", 35, "parent", 115)
    assert unf["S0"] == pytest.approx(0.89, abs=0.005) and frph["S0"] == pytest.approx(0.85, abs=0.005)
    assert unf["S1"] == pytest.approx(0.69, abs=0.005) and frph["S1"] == pytest.approx(0.65, abs=0.005)
    assert unf["H"] == pytest.approx(1.25, abs=0.005) and frph["H"] == pytest.approx(1.19, abs=0.005)
    assert (unf["E"], frph["E"]) == (4, 5)
