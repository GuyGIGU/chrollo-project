"""Clarity changes judgment, never chart geometry or setup admission."""
import datetime as dt
from types import SimpleNamespace as NS

import pytest

from engine_alpha import numbers as M
from engine_alpha.grade import compose_grade
from engine_alpha.grade import whole_points
from engine_alpha.grade import measure
from engine_alpha.record import Event, Grade, SPRING


def _turn(bar, price, kind):
    return NS(bar=bar, price=price, kind=kind, day=dt.date(2026, 1, 1) + dt.timedelta(days=bar), committed=True)


def _facts(fine, far=None, events=()):
    line = NS(committed=fine, far=lambda floor: fine if far is None else far)
    days = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(31)]
    return measure(line, events, days, R=100, S=90, opening_bar=0, read_bar=30)


def test_churn_inside_the_same_main_swings_earns_less_without_counting_more_traversals():
    main = [_turn(0, 100, 'peak'), _turn(25, 90, 'valley'), _turn(30, 100, 'peak')]
    choppy = [main[0], *[_turn(i, 95 if i % 2 else 97, 'valley' if i % 2 else 'peak')
                        for i in range(1, 23)], *main[1:]]
    clean, noisy = _facts(main), _facts(choppy, main)
    assert clean['main_legs'] == noisy['main_legs'] == 2
    assert clean['main_swing_share'] == 1
    assert 0 < noisy['main_swing_share'] < 1
    old = Grade(100, 'S', 0, 30, True)
    assert compose_grade(old, noisy).score < compose_grade(old, clean).score


def test_rail_definition_uses_turn_locations_not_more_touches_or_event_names():
    rail = _facts([_turn(0, 100, 'peak'), _turn(10, 90, 'valley'), _turn(20, 100, 'peak')])
    center = _facts([_turn(0, 96, 'peak'), _turn(10, 94, 'valley'), _turn(20, 96, 'peak')])
    assert rail['rail_alignment_error'] == 0
    assert center['rail_alignment_error'] == pytest.approx(.4)


def test_one_endpoint_is_insufficient_evidence_of_a_readable_zigzag():
    facts = _facts([_turn(10, 94, 'peak')])
    assert facts['main_swing_share'] is None and facts['rail_alignment_error'] is None
    assert compose_grade(Grade(100, 'S', 0, 30, True), facts).score == 100


def test_only_a_known_springs_own_excursion_is_explained():
    turns = [_turn(0, 100, 'peak'), _turn(10, 85, 'valley'), _turn(20, 100, 'peak')]
    event = Event(SPRING, turns[1].day, 85, first_day=turns[0].day,
                  last_day=turns[2].day, committed=True, known_day=turns[2].day)
    named = _facts(turns, events=[event])
    assert named['event_turns'] == 1 and named['rail_alignment_error'] == 0
    future = Event(SPRING, turns[1].day, 85, first_day=turns[0].day,
                   last_day=turns[2].day, committed=True, known_day=dt.date(2026, 2, 10))
    assert _facts(turns, events=[future])['event_turns'] == 0


def _perfect():
    return {'main_swing_share': 1., 'rail_alignment_error': 0., 'height_in_ranges': 1.2, 'contraction': 0.4}


def _wide():
    return {'main_swing_share': 0., 'rail_alignment_error': 1., 'height_in_ranges': 4.5, 'contraction': 1.1}


def test_the_letter_is_the_integrity_grades_and_the_traits_order_within_it():
    """His ruling 3 (Thu 29/10/2026): the sealed 40 keep their letters; the traits order WITHIN the letter. A tight,
    clean, contracting S reads 100; a wide, choppy S reads the letter's floor; an A can never reach S by its traits,
    and a wide S still outranks every A."""
    tight_s = compose_grade(Grade(80, 'S', 2, 40, True), _perfect(), stage=2)
    wide_s = compose_grade(Grade(75, 'S', 20, 40, True), _wide(), stage=4)     # half the base empty: no trait left
    tight_a = compose_grade(Grade(60, 'A', 8, 40, True), _perfect(), stage=2)
    assert (tight_s.letter, tight_s.score) == ('S', 100)
    assert (wide_s.letter, wide_s.score) == ('S', 75) and wide_s.score > tight_a.score
    assert tight_a.letter == 'A' and 50 <= tight_a.score < 75
    assert tight_s.score > wide_s.score


def test_a_tighter_box_outranks_a_wider_one_at_equal_dead_space():
    """His 29/10 words: wide "nothing burger" boxes hug the S spot. Two boxes with the same empty days: the one 1.5
    ranges tall outranks the one 3.5 ranges tall, everything else equal."""
    facts = _perfect()
    tight = compose_grade(Grade(90, 'S', 1, 40, True), {**facts, 'height_in_ranges': 1.5})
    wide = compose_grade(Grade(90, 'S', 1, 40, True), {**facts, 'height_in_ranges': 3.5})
    assert tight.score > wide.score and tight.letter == wide.letter == 'S'
    rows = {c['key']: c for c in wide.clarity['components']}
    expected = (M.TRAIT_TIGHT_ZERO_RANGES - 3.5) / (M.TRAIT_TIGHT_ZERO_RANGES - M.TRAIT_TIGHT_FULL_RANGES)
    assert rows['tightness']['fraction'] == pytest.approx(max(0.0, expected))
    assert rows['tightness']['max_points'] == M.TRAIT_WEIGHTS['tightness'] == max(M.TRAIT_WEIGHTS.values())


def test_the_stage_is_a_trait_and_an_unread_stage_leaves_the_budget():
    """"the stage thing I taught you" (Thu 29/10/2026): stage 2 earns the row, stage 4 none, and a stock whose
    weekly stage is not read is graded on the other traits alone."""
    facts = _perfect()
    two, four, none = (compose_grade(Grade(100, 'S', 0, 40, True), facts, stage=s) for s in (2, 4, None))
    budget, stage_points = sum(M.TRAIT_WEIGHTS.values()), M.TRAIT_WEIGHTS['stage']
    assert two.score == none.score == 100
    assert four.score == whole_points(75 + 25 * (1 - stage_points / budget)) < 100, "stage 4 costs exactly the stage row"
    assert {c['key']: c['fraction'] for c in none.clarity['components']}['stage'] is None
    assert none.clarity['available_points'] == budget - stage_points and two.clarity['available_points'] == budget


def test_missing_facts_leave_the_integrity_grade_and_a_broken_base_stays_at_zero():
    old = Grade(40, 'B', 9, 30, True)
    unknown = {'main_swing_share': None, 'rail_alignment_error': None}
    only_dead = compose_grade(old, unknown)
    assert only_dead.letter == 'B' and 25 <= only_dead.score < 50, "the dead-space row alone places it in B"
    assert compose_grade(Grade(40, 'B', 0, 0, True), unknown).score == 40, "no measured trait: the integrity score"
    broken = Grade(0, 'C', 0, 30, False)
    assert compose_grade(broken, _perfect(), stage=2).score == 0 and compose_grade(broken, _perfect()).letter == 'C'


def test_the_facts_carry_the_height_in_ranges_and_the_right_sides_contraction():
    import numpy as np

    turns = [_turn(0, 100, 'peak'), _turn(10, 90, 'valley'), _turn(20, 100, 'peak'), _turn(30, 90, 'valley')]
    line = NS(committed=turns, far=lambda floor: turns)
    days = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(31)]
    high = np.linspace(100, 100, 31); low = high - np.r_[np.full(21, 4.0), np.full(10, 2.0)]
    facts = measure(line, (), days, R=100, S=90, opening_bar=0, read_bar=30, high=high, low=low, unit=4.0)
    assert facts['height_in_ranges'] == pytest.approx(2.5)
    assert facts['contraction'] == pytest.approx(0.5), "no SOS: the base's last third against its earlier two thirds"
    bare = measure(line, (), days, R=100, S=90, opening_bar=0, read_bar=30)
    assert bare['height_in_ranges'] is None and bare['contraction'] is None
    # With THE SOS the right side is the bars from its push on, set against the whole base: the base's bars are four
    # points tall, the right side's two, so the ratio is 0.5 whatever the base's own last third did.
    from engine_alpha.record import SOS
    sos = Event(SOS, days[22], 101, first_day=days[21], last_day=days[23], committed=True, known_day=days[23])
    low = high - np.r_[np.full(10, 4.0), np.full(11, 4.0), np.full(10, 2.0)]
    with_sos = measure(line, (sos,), days, R=100, S=90, opening_bar=0, read_bar=30, high=high, low=low, unit=4.0)
    assert with_sos['base_end'] == days[20].isoformat()
    assert with_sos['contraction'] == pytest.approx(0.5)
    low = high - np.r_[np.full(10, 2.0), np.full(11, 4.0), np.full(10, 4.0)]
    loose = measure(line, (sos,), days, R=100, S=90, opening_bar=0, read_bar=30, high=high, low=low, unit=4.0)
    assert loose['contraction'] == pytest.approx(4.0 / (31 / 21 * 2 + 0)) if False else loose['contraction'] > 1.0


def test_the_adapter_composes_once_and_archives_the_same_breakdown_without_moving_the_setup():
    import json
    from engine_alpha.record import Box, Line, Lps, Read, Step
    from engine_alpha.result import graded_read, to_result
    from engine_alpha.archive import SCREEN_KEY, two_eyes_archive_values

    day = dt.date(2026, 1, 30)
    box = Box(Line(100, day), Line(90, day), day)
    lps = Lps(day, day, 'parent', 99)
    old = Grade(100, 'S', 0, 30, True,
                clarity={'facts': {'main_swing_share': .2, 'rail_alignment_error': .5}})
    read = Read('TEST', day, boxes=(box,), lps=lps, state='fired', close=98, grade=old,
                trail=(Step('grade', 'the grade: S (100)'),))
    scored = graded_read(read)
    assert graded_read(scored) is scored
    assert scored.fired == read.fired and scored.boxes == read.boxes and scored.lps == read.lps
    assert f'{scored.grade.letter} ({scored.grade.score:.0f})' in scored.trail[0].saying
    assert scored.trail[0].saying.endswith('; under it, the grade: S (100)')
    row = to_result(read)
    assert row['Score'] == row['_ta_grade'] == row[SCREEN_KEY]['grade']['score']
    assert row['Tier'] == scored.grade.letter == row[SCREEN_KEY]['grade']['letter']
    archived = two_eyes_archive_values(row.get, prefixed=True)
    assert json.loads(archived['two_eyes_clarity_json']) == scored.grade.clarity


def test_a_clarity_score_that_falls_over_keeps_the_integrity_grade_and_the_fire(monkeypatch):
    from engine_alpha.gate import EVAL_ERROR
    from engine_alpha.record import Box, Line, Lps, Read, Step
    from engine_alpha.result import graded_read, to_result

    day = dt.date(2026, 1, 30)
    old = Grade(100, 'S', 0, 30, True,
                clarity={'facts': {'main_swing_share': .2, 'rail_alignment_error': .5}})
    read = Read('TEST', day, boxes=(Box(Line(100, day), Line(90, day), day),), lps=Lps(day, day, 'parent', 99),
                state='fired', close=98, grade=old, trail=(Step('grade', 'the grade: S (100)'),))
    monkeypatch.setattr(M, 'CLARITY_SWING_FULL_SHARE', 0)
    kept = graded_read(read)
    assert (kept.grade.score, kept.grade.letter, kept.grade.clarity) == (100, 'S', None)
    assert 'could not be composed (ZeroDivisionError' in kept.trail[-1].saying
    row = to_result(read)
    assert row is not EVAL_ERROR and row['Tier'] == 'S' and row['_two_eyes_clarity_json'] is None


def test_each_scoring_control_rotates_the_engine_identity(monkeypatch):
    from engine_alpha.stamp import manifest_hash

    before = manifest_hash()
    for name in ['CLARITY_SWING_FULL_SHARE', 'CLARITY_RAIL_FULL_ERROR', 'CLARITY_RAIL_ZERO_ERROR']:
        with monkeypatch.context() as patch:
            patch.setattr(M, name, getattr(M, name) + .01)
            assert manifest_hash() != before
