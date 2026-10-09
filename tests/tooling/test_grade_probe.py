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


def test_the_rank_correlation_shares_tied_ranks_like_spearman():
    from tools.calibration.grade_probe import rank_corr

    a = np.array([1.0, 2.0, 2.0, 3.0, 5.0])
    assert rank_corr(a, a) == pytest.approx(1.0)
    assert rank_corr(a, -a) == pytest.approx(-1.0)
    # scipy.stats.spearmanr on the same pair, ties averaged in both: 0.78947 (= 15/19)
    assert rank_corr(a, np.array([2.0, 1.0, 3.0, 4.0, 4.0])) == pytest.approx(15 / 19, abs=1e-9)


def test_a_measure_survives_only_on_both_counts_at_most_three_and_never_two_that_move_together(monkeypatch):
    from tools.calibration import grade_probe

    junk = np.array([False] * 6 + [True] * 6)
    up = np.array([1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16], dtype=float)       # junk higher, each group rising
    turned = np.array([6, 5, 4, 3, 2, 1, 16, 15, 14, 13, 12, 11], dtype=float)  # junk higher, each group falling
    # Every one but E separates perfectly. Turned to its own direction, S1 and S3 rise with H (rank correlation
    # 1); S2, read junk-LOWER, is `turned` once turned, and so is V; `up` and `turned` correlate at 0.51.
    table = {"H": up, "S1": up * 2 + 0.5, "S2": -turned, "S3": up + 0.25, "V": turned, "E": np.ones(12)}
    scored, kept, dropped = grade_probe.survivors(table, junk, bar_auc=0.7, bar_loco=0.7)
    assert kept == ["H", "S2"]
    assert dropped == [("S1", "H"), ("S3", "H"), ("V", "S2")]
    assert scored["E"] == (0.5, 0.5), "a measure that cannot tell them apart never passes"
    # no twins at all: the first three are kept and the rest are dropped as surplus
    monkeypatch.setattr(grade_probe, "TOGETHER", 1.01)
    kept, dropped = grade_probe.survivors(table, junk, bar_auc=0.7, bar_loco=0.7)[1:]
    assert (kept, dropped) == (["H", "S1", "S2"], [("S3", None), ("V", None)])
    # one count is not enough: a bar no left-out score reaches keeps nothing, nor one no separation reaches
    assert grade_probe.survivors(table, junk, bar_auc=0.7, bar_loco=1.01)[1] == []
    assert grade_probe.survivors(table, junk, bar_auc=1.01, bar_loco=0.7)[1] == []
    # "move together" is read as graded: two measures that BOTH read the junk higher (each 0.58 apart) but order
    # the charts opposite ways (rank correlation -0.97) are not twins, and both stay
    monkeypatch.setattr(grade_probe, "TOGETHER", 0.7)
    a = np.array([1, 3, 5, 7, 9, 11, 2, 4, 6, 8, 10, 12], dtype=float)
    opposite = {"H": a, "S1": np.concatenate((12 - a[:6], 14 - a[6:])), "S2": np.ones(12), "S3": np.ones(12),
                "V": np.ones(12), "E": np.ones(12)}
    assert grade_probe.rank_corr(opposite["H"], opposite["S1"]) < -0.9
    assert grade_probe.survivors(opposite, junk, bar_auc=0.55, bar_loco=0.0)[1] == ["H", "S1"]
    # the second probe judges its own family, the dead days alone
    assert grade_probe.survivors({"D": up}, junk, bar_auc=0.7, bar_loco=0.7, family=grade_probe.SECOND)[1] == ["D"]


def test_the_chance_baseline_repeats_with_its_seed_and_rises_with_the_family():
    from tools.calibration.grade_probe import MEASURES, chance

    rng = np.random.default_rng(7)
    junk = np.array([False] * 20 + [True] * 8)
    table = {m: rng.normal(size=28) for m, _ in MEASURES}
    first = chance(table, junk, shuffles=200)
    assert chance(table, junk, shuffles=200) == first, "the same seed, the same baseline"
    alone = chance({m: (table[m] if m == "H" else np.ones(28)) for m, _ in MEASURES}, junk, shuffles=200)
    assert 0.5 < alone[0] < first[0] < 1.0, "the best of six is harder to beat than one measure alone"
    assert alone[1] < first[1]
    # the second probe's family is its one measure: its bar is that measure's own, not the best of six
    assert chance(table, junk, shuffles=200, family=MEASURES) == first
    one = chance(table, junk, shuffles=200, family=(("H", +1),))
    assert one[0] < first[0] and one[1] <= first[1]


def test_the_measures_and_their_directions_are_the_ones_written_down_before_the_probe_ran():
    from tools.calibration import grade_probe

    assert grade_probe.MEASURES == (("H", +1), ("S1", +1), ("S2", -1), ("S3", +1), ("V", +1), ("E", -1))
    assert grade_probe.CONTROL == ("S0", +1)
    assert (grade_probe.SHUFFLES, grade_probe.TOGETHER, grade_probe.KEEP) == (2000, 0.7, 3)
    assert grade_probe.LETTERS == ((75.0, "S"), (50.0, "A"), (25.0, "B"))
    assert grade_probe.BAR == ("BMRN", "FRPH", "COLM")
    # the second probe (the decisions row of Mon 05/10/2026, his dead space): one measure, the junk higher
    assert grade_probe.SECOND == (("D", +1),)
    # beside the grade, never in its place (ours, after the board): the same measure read on the parent
    assert grade_probe.PARENT == ("Dp", +1)


def test_the_grade_ramps_from_his_median_to_the_junk_median_and_the_letter_follows():
    from tools.calibration.grade_probe import grade, letter, ramps

    junk = np.array([False, False, False, True, True, True])
    table = {"S1": np.array([0.1, 0.2, 0.3, 0.5, 0.6, 0.7])}
    ends = ramps(table, junk, ["S1"])
    assert ends == {"S1": (pytest.approx(0.2), pytest.approx(0.6))}
    assert grade({"S1": 0.1}, ends) == 100.0 and grade({"S1": 0.9}, ends) == 0.0
    assert grade({"S1": 0.4}, ends) == pytest.approx(50.0)
    assert [letter(g) for g in (100.0, 75.0, 74.9, 50.0, 25.0, 24.9)] == ["S", "S", "A", "A", "B", "C"]


def test_the_base_ends_the_day_before_the_soss_push_when_that_push_begins_after_the_box_opened():
    """The dead days are counted over the base: from THE SOS's push on is the right side, never dead space."""
    import types
    import pandas as pd
    from engine_alpha.two_eyes import record
    from tools.calibration.grade_probe import base_end

    days = pd.bdate_range("2026-01-05", periods=30)
    prepared = pd.DataFrame(index=days)

    def row(*events):
        return {"read": types.SimpleNamespace(events=events), "prepared": prepared}

    def sos(push_bar):
        return record.Event(kind=record.SOS, day=days[push_bar + 3].date(), price=10.0,
                            first_day=days[push_bar].date())

    assert base_end(row(), 5, 29) == 29, "no SOS: to the read day"
    assert base_end(row(sos(20)), 5, 29) == 19, "the day before the push begins"
    assert base_end(row(sos(5)), 5, 29) == 29, "a push from the box's opening day ends no base"
    assert base_end(row(sos(3)), 5, 29) == 29, "nor one that began before the box opened"
    spring = record.Event(kind=record.SPRING, day=days[10].date(), price=9.0, first_day=days[8].date())
    assert base_end(row(spring), 5, 29) == 29, "only THE SOS ends the base"


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


def test_his_frph_box_is_mostly_dead_space_and_his_unf_box_is_not(unf_and_frph):
    """His word (Mon 05/10/2026): *"FRPH is total junk because the box is mostly dead space"*, while a box about as
    tall as its bars, like his UNF, *"is completely fine"*. Over the base (the box's days before THE SOS's push),
    FRPH's bars miss its box on more than half the days, and UNF's on fewer than half."""
    from tools.calibration.grade_probe import measures

    unf, frph = (measures(row) for row in unf_and_frph)
    assert frph["D"] > 0.5, "mostly dead space"
    assert unf["D"] < 0.5, "a box as tall as its bars is no dead space"
    # pinned once measured: FRPH's base runs 103 of its 115 days (THE SOS's push ends it), 73 of them with no bar in
    # the box; UNF's 29 of 35, 3 of them; over the whole days to the read day the right side would count too
    assert (frph["base_days"], frph["D"], frph["D_all"]) == (103, pytest.approx(73 / 103), pytest.approx(82 / 115))
    assert (unf["base_days"], unf["D"], unf["D_all"]) == (29, pytest.approx(3 / 29), pytest.approx(8 / 35))
    assert (frph["Dp"], unf["Dp"]) == (frph["D"], unf["D"]), "both read on the parent already"


def test_the_parent_reading_takes_the_parents_dead_days_when_the_lps_was_read_against_the_mini():
    """His VIK: the LPS is read against the mini, whose days after THE SOS of the parent are the mini's own push and
    pullback; the parent reading (beside the grade) takes the parent's base, where 1 day of 15 has no bar in the box."""
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.calibration import core_board
    from tools.calibration.grade_probe import measures
    from tools.regression.marks_corpus import load_corpus, setup_key

    frames, _ = load_sealed_fixture()
    vik = next(s for s in load_corpus() if setup_key(s) == "VIK:2026-06-11")
    m = measures(core_board.score_setup(vik, fixture_frame(frames, "VIK:2026-06-11", "VIK"))["on_last"])
    assert (m["box"], m["base_days"], m["D"]) == ("mini", 16, pytest.approx(9 / 16))
    assert m["Dp"] == pytest.approx(1 / 15)


def test_the_grade_is_the_measure_written_down_and_the_parent_reading_only_stands_beside_it():
    """The row written before the probe ran says "If D survives, the grade is D alone"; the parent reading, chosen
    after the board, is printed beside the grade for his call (verify-14d, P1)."""
    from tools.calibration import grade_probe

    junk = np.array([False] * 6 + [True] * 6)
    apart = np.array([0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    charts = [{"ticker": f"T{i}", "junk": bool(j), "m": {"base_days": 20, "days": 25, "D_all": d}}
              for i, (j, d) in enumerate(zip(junk, apart))]
    out, kept, beside, _ = grade_probe.second_probe(charts, {"D": apart, "Dp": apart}, {"D": apart}, junk, 200)
    assert (kept, beside) == (["D"], ["Dp"])


def test_the_parent_reading_needs_the_written_down_d_to_survive_and_the_best_of_two_beaten():
    from tools.calibration import grade_probe

    junk = np.array([False] * 6 + [True] * 6)
    apart = np.array([1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16], dtype=float)
    flat = np.ones(12)
    assert grade_probe.parent_term({"D": apart, "Dp": apart}, junk, ["D"], shuffles=200)[0] == ["Dp"]
    assert grade_probe.parent_term({"D": apart, "Dp": flat}, junk, ["D"], shuffles=200)[0] == [], \
        "a parent reading that cannot tell them apart is no term"
    assert grade_probe.parent_term({"D": apart, "Dp": apart}, junk, [], shuffles=200)[0] == [], \
        "only when the measure written down first survived"
    # chosen after the board, so its bar is the best of the two under the same shuffles, not its own
    table = {"D": apart, "Dp": apart[::-1].copy()}
    assert grade_probe.parent_term(table, junk, ["D"], shuffles=200)[2] == \
        grade_probe.chance(table, junk, 200, family=(("D", +1), ("Dp", +1)))


# --------------------------------------------------------------------------- #
# The third reading (the decisions row of Fri 09/10/2026): his COLM word, "base dosen't hold and dosen't answer #
# for an LPS anywhere", and the study of his 40, written down before it was measured                           #
# --------------------------------------------------------------------------- #
def _bars(highs, lows, R, S, unit, opening, *events, turns=()):
    """A read made of bars, a story and the line's committed turns (bar numbers; none by default), for the parts of
    the third, fourth and fifth readings that need nothing else."""
    import types
    import pandas as pd

    days = pd.bdate_range("2026-01-05", periods=len(highs))
    prepared = pd.DataFrame({"High": highs, "Low": lows}, index=days)
    pair = types.SimpleNamespace(R=R, S=S, unit=unit, opening_bar=opening)
    line = types.SimpleNamespace(committed=tuple(types.SimpleNamespace(bar=b, day=days[b].date()) for b in turns))
    return {"read": types.SimpleNamespace(events=tuple(e(days) for e in events)), "prepared": prepared,
            "won": pair, "line": line}, [d.date() for d in days]


def _event(kind, first, last=None, day=None):
    from engine_alpha.two_eyes import record

    def make(days):
        swing = kind != record.PHASE_D
        return record.Event(kind=kind, day=days[first if day is None else day].date(), price=10.0,
                            first_day=days[first].date() if swing else None,
                            last_day=days[first if last is None else last].date() if swing else None)
    return make


def test_his_way_a_hair_beyond_a_line_is_respect_and_a_day_inside_a_named_swing_is_story():
    """His 30/08/2026 ruling (holding just below support, resting just above resistance, is respect) and his
    13/09/2026 ruling (*"a named event's swing is never docked, an unnamed lunge beyond a rail is"*): a day is empty
    only when its bar misses the box by more than the line's area, half a daily range, outside every named swing.
    Phase D is a day, not a swing: it pardons nothing."""
    from engine_alpha.two_eyes import record
    from tools.calibration.grade_probe import his_way

    inside = (10.8, 10.2)
    bars = [inside,
            (9.7, 9.4),     # wholly under the support, 0.3 under it: a hair, respect
            (9.4, 9.0),     # 0.6 under: beyond the area, empty
            (11.8, 11.4),   # 0.4 over the resistance: a hair, respect
            (12.0, 11.6),   # 0.6 over: empty
            (9.2, 8.8),     # 0.8 under, inside the named spring: story
            inside,
            (9.3, 9.0),     # 0.7 under, on Phase D's day: still empty
            inside, inside]
    row, days = _bars([h for h, _ in bars], [lo for _, lo in bars], 11.0, 10.0, 1.0, 0,
                      _event(record.SPRING, 5), _event(record.PHASE_D, 7))
    m = his_way(row)
    assert m["Dh_empty"] == [days[2], days[4], days[7]]
    assert (m["Dh"], m["Dh_days"]) == (pytest.approx(3 / 10), 10)


def test_the_hold_reads_the_lows_after_the_soss_top_against_the_supports_area_and_pardons_no_swing():
    """His COLM word (Thu 08/10/2026): *"base dosen't hold and dosen't answer for an LPS anywhere"*. After THE SOS's
    top, a low more than half a daily range under the support is the base not holding, a named last supper or not;
    a low a hair under it holds; the push's own days, before its top, are not read."""
    from engine_alpha.two_eyes import record
    from tools.calibration.grade_probe import his_way

    def read(right_lows, *events, push_low=10.4, opening=0):
        highs = [10.8] * 8 + [10.9, 11.5, 12.0] + [11.2] * len(right_lows)
        lows = [10.2] * 8 + [push_low, 10.8, 11.3] + list(right_lows)
        return his_way(_bars(highs, lows, 11.0, 10.0, 1.0, opening, *events)[0])

    sos = _event(record.SOS, 8, 10, day=10)               # the push from day 8, its top on day 10
    held = read([10.6, 9.6, 10.2], sos)
    assert held["holds"] and held["U"] == pytest.approx(0.4)
    broke = read([10.6, 9.4, 10.2], sos)
    assert not broke["holds"] and broke["U"] == pytest.approx(0.6)
    assert not read([10.6, 9.4, 10.2], sos, _event(record.LAST_SUPPER, 10, 12))["holds"], \
        "a named last supper that falls beyond the support is still the base not holding"
    assert read([10.6, 9.6, 10.2], sos, push_low=9.0)["holds"], "the push's days before its top are not read"
    assert read([10.6, 9.4, 10.2])["holds"], "no SOS ends the base: no right side yet"
    on_top = read([], sos)
    assert on_top["holds"] and on_top["U"] == 0.0, "the read day on the top itself: no right side yet"
    assert read([10.6, 9.4, 10.2], _event(record.SOS, 1, 10, day=10), opening=2)["holds"], \
        "a push that began before the box opened ends no base, so it opens no right side"


def test_the_third_grade_is_the_smaller_of_the_two_and_a_base_that_does_not_hold_grades_nothing():
    from tools.calibration.grade_probe import order_key, third_grade

    ends = {"Dh": (0.0, 0.2)}
    assert third_grade({"Dh": 0.0, "holds": True}, ends) == 100.0
    assert third_grade({"Dh": 0.05, "holds": True}, ends) == pytest.approx(75.0)
    assert third_grade({"Dh": 0.2, "holds": True}, ends) == 0.0
    assert third_grade({"Dh": 0.0, "holds": False}, ends) == 0.0, "the smaller, not the average (that would be 50)"
    # the grade's own order, label-free: every base that does not hold under every base that holds, then by Dh
    keys = [order_key({"Dh": d, "holds": h}) for d, h in ((0.0, True), (0.9, True), (0.0, False), (0.5, False))]
    assert keys == sorted(keys)


def test_the_third_reading_chosen_after_the_lists_must_beat_the_best_of_four_under_the_same_shuffles():
    from tools.calibration import grade_probe

    assert grade_probe.THIRD == (("D", +1), ("Dp", +1), ("Dh", +1), ("K", +1))
    assert grade_probe.STORY == ("spring", "spring test", "upthrust", "last supper", "SOS")
    junk = np.array([False] * 6 + [True] * 6)
    apart = np.array([1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16], dtype=float)
    flat = np.ones(12)
    rng = np.random.default_rng(3)
    table = {"D": rng.normal(size=12), "Dp": rng.normal(size=12), "Dh": rng.normal(size=12), "K": apart}
    passes, bar, scores = grade_probe.third_term(table, junk, shuffles=200)
    assert passes and scores == (1.0, 1.0)
    assert bar == grade_probe.chance(table, junk, 200, family=grade_probe.THIRD), "the best of the four, not its own"
    own = grade_probe.chance(table, junk, 200, family=(("K", +1),))
    assert bar[0] > own[0] and bar[1] > own[1], "the four together are harder to beat than K alone"
    assert not grade_probe.third_term({**table, "K": flat}, junk, shuffles=200)[0]


@pytest.fixture(scope="module")
def colm_fires() -> list:
    from tools.calibration import core_board
    from tools.regression import negative_corpus

    junk_frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c.get("key", c["ticker"]) == "COLM")
    return core_board.junk_row(case, junk_frames["COLM"])["fires"]


def test_his_colm_base_does_not_hold_on_either_fire_day_and_grades_nothing(colm_fires):
    """His picture (Thu 08/10/2026): after the reader's anchoring the price does not consolidate in the box, it
    reaches a lower level. On both fire days the fall after THE SOS's top (Wed 17/06/2026, low 63.59) lies 0.94
    daily ranges under the support 65.81, beyond its area; by Tue 23/06 the LPS's own low (63.24) is 1.08 under."""
    import datetime as dt
    from tools.calibration.grade_probe import measures, third_grade

    assert [f["day"] for f in colm_fires] == [dt.date(2026, 6, 22), dt.date(2026, 6, 23)]
    for fire, under in zip(colm_fires, (0.937, 1.084)):
        m = measures(fire)
        assert not m["holds"] and m["U"] == pytest.approx(under, abs=0.001)
        assert third_grade(m, {"Dh": (0.0, 0.2)}) == 0.0


def test_his_frph_stays_empty_counted_his_way_and_his_unf_grades_s(unf_and_frph):
    """His FRPH crosses (Mon 05/10/2026) are not hairs or story: counted his way, more than a third of its base is
    still empty. His UNF, a box as tall as its bars (*"completely fine"*), has no empty day left and holds."""
    from tools.calibration.grade_probe import measures, third_grade

    unf, frph = (measures(row) for row in unf_and_frph)
    assert frph["Dh"] > 1 / 3
    assert unf["Dh"] == 0.0 and unf["holds"]
    assert third_grade(unf, {"Dh": (0.0, 0.2)}) == 100.0


# --------------------------------------------------------------------------- #
# The fourth reading (the decisions row of Fri 09/10/2026, written down after the third's board): the fall must   #
# go under the whole base ("reaches a lower level"), and the ramp's ends come from his word "mostly"               #
# --------------------------------------------------------------------------- #
def test_the_fourth_hold_needs_the_fall_beyond_the_supports_area_and_under_the_bases_own_lowest_low():
    """His COLM word, *"reaches a lower level"*: a lower level than the base ever made. A dip beyond the support's
    area that stays over the spring's tip holds (his JAZZ, 13/09/2026: on the support rather than under it); a dip
    under the base's lowest low that stays inside the area holds; only a fall that is both does not."""
    from engine_alpha.two_eyes import record
    from tools.calibration.grade_probe import his_way

    def read(base_low, right_low):
        highs = [10.8] * 8 + [10.9, 11.5, 12.0, 11.2, 11.2]
        lows = [10.2, 10.2, base_low, 10.2, 10.2, 10.2, 10.2, 10.2] + [10.4, 10.8, 11.3, 10.6, right_low]
        return his_way(_bars(highs, lows, 11.0, 10.0, 1.0, 0, _event(record.SOS, 8, 10, day=10))[0])

    over_the_spring = read(9.0, 9.4)                  # 0.6 under the support, over the spring's tip 9.0
    assert not over_the_spring["holds"] and over_the_spring["holds4"], "the third reading's fault, mended"
    assert over_the_spring["floor"] == 9.0
    assert not read(9.0, 8.9)["holds4"], "beyond the area and under the whole base: the base does not hold"
    assert read(9.8, 9.7)["holds4"], "under the base's low by a hair, inside the support's area: it holds"


def test_the_fourth_grade_ramps_from_no_empty_day_to_mostly_empty_and_a_base_that_does_not_hold_grades_nothing():
    from tools.calibration.grade_probe import ENDS4, fourth_grade, letter

    assert ENDS4 == {"Dh": (0.0, 0.5)}, "1 at no empty day, 0 at one half: his 'mostly dead space'"
    assert letter(fourth_grade({"Dh": 1 / 60, "holds4": True})) == "S", "one empty day in sixty is S"
    assert fourth_grade({"Dh": 0.125, "holds4": True}) == pytest.approx(75.0)
    assert fourth_grade({"Dh": 0.25, "holds4": True}) == pytest.approx(50.0)
    assert fourth_grade({"Dh": 0.5, "holds4": True}) == 0.0
    assert fourth_grade({"Dh": 0.0, "holds4": False}) == 0.0


def test_the_fourth_reading_must_beat_the_best_of_five_under_the_same_shuffles():
    from tools.calibration import grade_probe

    assert grade_probe.FOURTH == grade_probe.THIRD + (("K4", +1),)
    junk = np.array([False] * 6 + [True] * 6)
    apart = np.array([1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16], dtype=float)
    flat = np.ones(12)
    rng = np.random.default_rng(3)
    table = {"D": rng.normal(size=12), "Dp": rng.normal(size=12), "Dh": rng.normal(size=12),
             "K": rng.normal(size=12), "K4": apart}
    passes, bar, scores = grade_probe.fourth_term(table, junk, shuffles=200)
    assert passes and scores == (1.0, 1.0)
    assert bar == grade_probe.chance(table, junk, 200, family=grade_probe.FOURTH), "the best of the five"
    own = grade_probe.chance(table, junk, 200, family=(("K4", +1),))
    assert bar[0] > own[0] and bar[1] > own[1], "the five together are harder to beat than K4 alone"
    assert not grade_probe.fourth_term({**table, "K4": flat}, junk, shuffles=200)[0]


def test_his_colm_falls_under_its_whole_base_and_his_jazz_drts_and_bodi_do_not(colm_fires):
    """COLM (his picture, Thu 08/10/2026) falls under its spring's tip (63.72) on both fire days; his JAZZ, whose own
    LPS pokes 0.54 daily ranges under the support (his ruling of 13/09/2026: on the support, not under it), and his
    DRTS and BODI, whose dips stay over their springs' tips, hold."""
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.calibration import core_board
    from tools.calibration.grade_probe import fourth_grade, letter, measures
    from tools.regression.marks_corpus import load_corpus, setup_key

    for fire in colm_fires:
        m = measures(fire)
        assert not m["holds4"] and m["floor"] == pytest.approx(63.72, abs=0.005)
        assert fourth_grade(m) == 0.0
    frames, _ = load_sealed_fixture()
    his = {setup_key(s): s for s in load_corpus()}
    for key in ("JAZZ:2026-02-24", "DRTS:2026-04-15", "BODI:2026-04-21"):
        s = his[key]
        m = measures(core_board.score_setup(s, fixture_frame(frames, key, s["ticker"]))["on_last"])
        assert not m["holds"] and m["holds4"], key
    jazz = his["JAZZ:2026-02-24"]
    m = measures(core_board.score_setup(jazz, fixture_frame(frames, "JAZZ:2026-02-24", "JAZZ"))["on_last"])
    assert letter(fourth_grade(m)) == "S"


# --------------------------------------------------------------------------- #
# The fifth reading (his ruling of Fri 09/10/2026): the story forgives an event's own swing only                  #
# --------------------------------------------------------------------------- #
def test_a_named_events_span_forgives_only_its_own_swing_on_the_line():
    """His ruling (Fri 09/10/2026): *"I'd forgive only that swing," correct*. The reader names a spring over ten days
    under the box; the line turns inside them. Only the days from the line's last turn before the spring's tip to its
    first turn after it are forgiven: the leg down to the low and back up."""
    from engine_alpha.two_eyes import record
    from tools.calibration.grade_probe import his_way

    inside, under = (10.8, 10.2), (9.3, 8.5)
    bars = [inside] * 5 + [under] * 10 + [inside] * 5
    row, days = _bars([h for h, _ in bars], [lo for _, lo in bars], 11.0, 10.0, 1.0, 0,
                      _event(record.SPRING, 5, 14, day=9), turns=(7, 8, 9, 11, 13))
    m = his_way(row)
    assert m["Dh"] == 0.0, "the span forgave all ten (the third and fourth readings)"
    assert m["Dw_empty"] == [days[i] for i in (5, 6, 7, 12, 13, 14)], "the swing forgives 8 to 11 only"
    assert m["Dw"] == pytest.approx(6 / 20)
    # no committed turn after the tip yet: its swing runs to the read day; none before it: from the first day
    row, days = _bars([h for h, _ in bars], [lo for _, lo in bars], 11.0, 10.0, 1.0, 0,
                      _event(record.SPRING, 5, 14, day=9), turns=(7,))
    assert his_way(row)["Dw_empty"] == [days[i] for i in (5, 6)]
    row, days = _bars([h for h, _ in bars], [lo for _, lo in bars], 11.0, 10.0, 1.0, 0,
                      _event(record.SPRING, 5, 14, day=9))
    assert his_way(row)["Dw_empty"] == [], "with no turn on the line, the swing is the whole span"
    # a one-day event (a spring test) forgives its own day only, as before
    row, days = _bars([h for h, _ in bars], [lo for _, lo in bars], 11.0, 10.0, 1.0, 0,
                      _event(record.SPRING_TEST, 9), turns=(7, 8, 9, 11, 13))
    assert len(his_way(row)["Dw_empty"]) == 9


def test_the_fifth_grade_reads_dw_with_his_ends_and_the_fourth_hold_and_beats_the_best_of_six():
    from tools.calibration import grade_probe
    from tools.calibration.grade_probe import ENDS5, fifth_grade, letter

    assert ENDS5 == {"Dw": (0.0, 0.5)}
    assert letter(fifth_grade({"Dw": 1 / 60, "holds4": True})) == "S"
    assert fifth_grade({"Dw": 0.25, "holds4": True}) == pytest.approx(50.0)
    assert fifth_grade({"Dw": 0.0, "holds4": False}) == 0.0
    assert grade_probe.FIFTH == grade_probe.FOURTH + (("K5", +1),)
    junk = np.array([False] * 6 + [True] * 6)
    apart = np.array([1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16], dtype=float)
    rng = np.random.default_rng(3)
    table = {m: rng.normal(size=12) for m in ("D", "Dp", "Dh", "K", "K4")}
    table["K5"] = apart
    passes, bar, scores = grade_probe.fifth_term(table, junk, shuffles=200)
    assert passes and scores == (1.0, 1.0)
    assert bar == grade_probe.chance(table, junk, 200, family=grade_probe.FIFTH), "the best of the six"
    own = grade_probe.chance(table, junk, 200, family=(("K5", +1),))
    assert bar[0] > own[0] and bar[1] > own[1]
    assert not grade_probe.fifth_term({**table, "K5": np.ones(12)}, junk, shuffles=200)[0]


@pytest.fixture(scope="module")
def frph_fires() -> list:
    from tools.calibration import core_board
    from tools.regression import negative_corpus

    junk_frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c.get("key", c["ticker"]) == "FRPH")
    return core_board.junk_row(case, junk_frames["FRPH"])["fires"]


def test_the_sheet_cuts_each_letter_on_the_whole_point_it_prints():
    """verify-15c: the pack's grade sheet printed a reading `:.0f` beside a letter cut on the raw number, so a 74.55
    read "75 A" there while the screen read "75 S". Each reading the sheet prints is read to the whole point, and its
    letter is cut on that number, as the reader's own grade is."""
    from tools.calibration.grade_probe import fixed_ends_probe

    m = {"holds4": True, "Dh_days": 55, "Dw_empty": [0] * 7}
    charts = [{"key": "X", "junk": False, "m": m}, {"key": "J", "junk": True, "m": {**m, "holds4": False}}]
    out, _, _ = fixed_ends_probe(charts, {"K5": np.array([0.1, 0.9])}, np.array([False, True]), [], 1, "FIFTH", "",
                                 "", "5", lambda *args: (True, (0.5, 0.5), (0.6, 0.6)),
                                 lambda m, ends=None: 74.545 if m["holds4"] else 0.0, {"Dw": (0.0, 0.5)}, "Dw")
    assert (charts[0]["grade_5"], charts[0]["letter_5"]) == (75.0, "S")
    assert "  his under S on the fifth reading: 0" in out


def test_the_sheets_other_grades_are_read_to_the_whole_point_too():
    """The same for the grade the sheet prints beside it ("as written") and for the bar's lines on the board."""
    import datetime as dt

    from tools.calibration.grade_probe import format_grades, grade_all

    charts = [{"key": k, "junk": k.startswith("J"), "m": {"D": float(k.startswith("J"))}}
              for k in ("X1", "X2", "J1", "J2")]
    grade_all(charts, {"D": np.array([0.0, 0.0, 1.0, 1.0])}, np.array([False, False, True, True]), ["D"], "",
              grader=lambda m, ends: 74.545)
    assert [(c["grade"], c["letter"], c["loco_grade"]) for c in charts] == [(75.0, "S", 75.0)] * 4
    junk = [{"ticker": "COLM", "key": "COLM", "m": {"D": 1.0}, "every": [(dt.date(2026, 6, 22), {"D": 1.0})]}]
    assert "    COLM: 22/06 75 S" in format_grades([], junk, {"D": (0.0, 1.0)}, grader=lambda m, ends: 74.545)


def test_the_readers_own_grade_is_the_probes_fifth_reading(colm_fires, frph_fires, unf_and_frph):
    """The grade entry in the reader (stage 7) is the reading measured here, not a re-typed cousin of it: on COLM's
    and FRPH's fire days and on his UNF, the record's grade is the probe's fifth reading read to the whole point, day
    for day."""
    from engine_alpha.two_eyes.grade import whole_points
    from tools.calibration.grade_probe import fifth_grade, measures

    for row in (*colm_fires, *frph_fires, *unf_and_frph):
        m, g = measures(row), row["read"].grade
        assert (g.score, g.holds, g.empty_days, g.base_days) == \
            (whole_points(fifth_grade(m)), m["holds4"], len(m["Dw_empty"]), m["Dh_days"]), row["day"]


def test_his_frph_box_failed_so_it_grades_under_a_on_every_fire_day_and_his_unf_and_jazz_stay_s(frph_fires,
                                                                                                 unf_and_frph):
    """His verdict (Fri 09/10/2026): FRPH's marked box failed long ago, and the reader's two-month spring under its
    moved box is no spring. Forgiving only its own swing, FRPH grades under A on all six fire days, Thu 18/06 to Thu
    02/07/2026. His UNF (a box as tall as its bars) and JAZZ (his LPS on the support) still grade S."""
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.calibration import core_board
    from tools.calibration.grade_probe import fifth_grade, letter, measures
    from tools.regression.marks_corpus import load_corpus, setup_key

    assert len(frph_fires) == 6
    for fire in frph_fires:
        assert letter(fifth_grade(measures(fire))) in ("B", "C"), fire["day"]
    frames, _ = load_sealed_fixture()
    jazz = next(s for s in load_corpus() if setup_key(s) == "JAZZ:2026-02-24")
    for row in (unf_and_frph[0], core_board.score_setup(jazz, fixture_frame(frames, "JAZZ:2026-02-24", "JAZZ"))["on_last"]):
        assert letter(fifth_grade(measures(row))) == "S", row["day"]
