"""Clarity changes judgment, never chart geometry or setup admission."""
import datetime as dt
from types import SimpleNamespace as NS

import pytest

from engine_alpha.scoring.clarity import compose_grade
from engine_alpha.two_eyes.clarity import measure
from engine_alpha.two_eyes.record import Event, Grade, SPRING


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


def test_missing_facts_are_unknown_and_integrity_remains_the_ceiling(monkeypatch):
    from config import settings

    old = Grade(40, 'B', 9, 30, True)
    unknown = {'main_swing_share': None, 'rail_alignment_error': None}
    assert compose_grade(old, unknown).score == 40
    perfect = {'main_swing_share': 1., 'rail_alignment_error': 0.}
    assert compose_grade(old, perfect).score == 40
    broken = Grade(0, 'C', 0, 30, False)
    assert compose_grade(broken, perfect).score == 0
    monkeypatch.setattr(settings, 'SCORE_CLARITY_SWINGS', 0)
    monkeypatch.setattr(settings, 'SCORE_CLARITY_RAILS', 0)
    assert compose_grade(old, perfect).score == old.score


def test_the_adapter_composes_once_and_archives_the_same_breakdown_without_moving_the_setup():
    import json
    from engine_alpha.two_eyes.record import Box, Line, Lps, Read, Step
    from engine_alpha.two_eyes_adapter import graded_read, to_result
    from engine_alpha.two_eyes_archive import SCREEN_KEY, two_eyes_archive_values

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
    row = to_result(read)
    assert row['Score'] == row['_ta_grade'] == row[SCREEN_KEY]['grade']['score']
    assert row['Tier'] == scored.grade.letter == row[SCREEN_KEY]['grade']['letter']
    archived = two_eyes_archive_values(row.get, prefixed=True)
    assert json.loads(archived['two_eyes_clarity_json']) == scored.grade.clarity


def test_each_scoring_control_rotates_the_engine_identity(monkeypatch):
    from config import settings
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    for name in ['SCORE_CLARITY_SWINGS', 'SCORE_CLARITY_RAILS', 'CLARITY_SWING_FULL_SHARE',
                 'CLARITY_RAIL_FULL_ERROR', 'CLARITY_RAIL_ZERO_ERROR']:
        with monkeypatch.context() as patch:
            patch.setattr(settings, name, getattr(settings, name) + .01)
            assert manifest_hash() != before
