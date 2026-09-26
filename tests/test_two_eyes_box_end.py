"""The box-end reader copy's own pure tests: COPIED from tests/test_final_method_step11.py (two-eyes-reader task 7), re-pointed at the
new reader's copy. Verbatim but for the imports. None of them reads a number the copy takes from `method_numbers`;
those values are pinned in tests/test_two_eyes_copies_equal_originals.py. The originals' tests stay where
they are, frozen with the old engine; these move with the copy and change when it changes.

Copied: the box-end reader's own tests. Left with the originals (they test the old engine, not the piece): the walk, flag and integration tests.
"""
from __future__ import annotations

import numpy as np

from engine_alpha.two_eyes.box_end import _child_end, _leave_bar, box_end, election_bar


R, S, UNIT = 110.0, 100.0, 1.0          # a box of ten; the area is half a range


def _turns(spec, forming_last=False):
    out = [(b, k, float(p), b + 1) for b, k, p in spec]
    if forming_last:
        b, k, p, _ = out[-1]
        out[-1] = (b, k, p, None)
    return out


def _closes(n, level=105.0, **at):
    """Closes inside the box, with the days given (bar=price) overridden."""
    c = np.full(n, level, dtype=float)
    for bar, price in at.items():
        c[int(bar[1:])] = price
    return c


def test_the_election_commits_when_both_rails_are_answered():
    line = _turns([(0, "peak", 110), (4, "valley", 100), (8, "peak", 109.8), (12, "valley", 100.3), (16, "peak", 112)])
    assert election_bar(line, R, S, 4, 0.5) == 13, "the later of the two answering turns' commits (day 12 commits on 13)"
    assert election_bar(line[:3], R, S, 4, 0.5) is None, "S not answered yet"
    assert election_bar(_turns([(0, "peak", 110), (4, "valley", 100)]), R, S, 4, 0.5) is None


def test_the_breakout_day_is_the_first_close_over_r_by_the_margin():
    closes = _closes(30, b20=110.05, b22=110.2)
    assert _leave_bar(closes, R, 0.10, 4, True) == 22, "110.05 is inside the margin (0.10 ranges); 110.20 is not"
    assert _leave_bar(_closes(30), R, 0.10, 4, True) is None
    assert _leave_bar(_closes(30, b18=99.8, b24=99.95), S, 0.10, 4, False) == 18, "the mirror: the first close under S by the margin"


CHILD = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 111),
         (20, "valley", 104), (24, "peak", 118), (28, "valley", 110.2), (32, "peak", 118.3), (36, "valley", 110.4)]


def test_a_child_is_confirmed_when_both_its_anchors_are_answered():
    end, candidate = _child_end(_turns(CHILD), _closes(40, b22=112.0), R, 0.5, 0.10, 12, True)
    assert candidate is None and end is not None
    assert end["kind"] == "hand-over" and end["left_bar"] == 22
    assert (end["child"]["climax_bar"], end["child"]["ar_bar"]) == (24, 28), "the swing off the breakout run's top, holding in the R area"
    assert (end["end_bar"], end["known_bar"]) == (36, 37), "the later of the two answering turns, known on its commit"


def test_one_turn_at_one_anchor_is_the_parents_lps_above_r_not_a_child():
    one_turn = CHILD[:9] + [(36, "valley", 113.0), (40, "peak", 125.0)]
    end, candidate = _child_end(_turns(one_turn), _closes(44, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is None and (candidate["climax_bar"], candidate["ar_bar"]) == (24, 28), \
        "the top was answered, the low was not: the parent goes on (row 1 before row 4)"
    one_low = CHILD[:8] + [(32, "peak", 125.0), (36, "valley", 110.4), (40, "peak", 130.0)]
    end, candidate = _child_end(_turns(one_low), _closes(44, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is None and candidate["ar_bar"] == 28, "the low was answered, the top was not"


def test_a_run_that_comes_back_into_the_box_hands_nothing_over():
    spec = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 114),
            (20, "valley", 106), (24, "peak", 112), (28, "valley", 101), (32, "peak", 109)]
    end, candidate = _child_end(_turns(spec), _closes(36, b14=111.0), R, 0.5, 0.10, 12, True)
    assert end is None and candidate is None, "the first valley after the breakout sits under the R area: the box goes on"
    spec2 = spec + [(36, "valley", 103), (40, "peak", 120), (44, "valley", 112), (48, "peak", 120.2), (52, "valley", 112.3)]
    end, candidate = _child_end(_turns(spec2), _closes(56, b14=111.0, b38=113.0), R, 0.5, 0.10, 12, True)
    assert end is not None and end["left_bar"] == 38 and end["child"]["ar_bar"] == 44 and end["end_bar"] == 52


def test_candidates_accumulate_and_the_first_one_answered_ends_the_parent():
    spec = CHILD[:8] + [(32, "peak", 125), (36, "valley", 118.5), (40, "peak", 124.8), (44, "valley", 118.7)]
    end, candidate = _child_end(_turns(spec), _closes(48, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is not None and end["end_bar"] == 44, "the higher swing's two anchors were both revisited"
    assert (end["child"]["climax_bar"], end["child"]["ar_bar"]) == (32, 36)
    end, candidate = _child_end(_turns(spec[:11]), _closes(44, b22=112.0), R, 0.5, 0.10, 12, True)
    assert end is None and candidate["ar_bar"] == 28, "unconfirmed: the first candidate is the chart's state"


def test_no_breakout_means_no_hand_over_and_no_close_level_ends_a_box():
    spec = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 110.4)]
    end, candidate = _child_end(_turns(spec), _closes(20), R, 0.5, 0.10, 12, True)
    assert end is None and candidate is None


BELOW = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 108),
         (20, "valley", 92.0), (24, "peak", 99.6), (28, "valley", 91.8), (32, "peak", 99.4), (36, "valley", 92.2)]


def test_a_child_below_confirmed_by_its_answering_is_the_breakdown():
    end, _ = _child_end(_turns(BELOW), _closes(40, b18=99.8), S, 0.5, 0.10, 12, False)
    assert end is not None and end["kind"] == "breakdown" and end["left_bar"] == 18
    assert (end["child"]["climax_bar"], end["child"]["ar_bar"]) == (20, 24), "the swing off the decline's low, its peak in the S area"
    assert (end["end_bar"], end["known_bar"]) == (32, 33), "the second pair answers both anchors of the child below"
    end, candidate = box_end(_turns(BELOW), _closes(40, b18=99.8), R, S, 0, 4, UNIT)
    assert end["kind"] == "breakdown" and end["end_bar"] == 16, "the parent froze at its last turn before price left"


def test_a_dip_that_recovers_or_confirms_no_child_below_is_not_an_end():
    spring = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 108),
              (20, "valley", 98.0), (24, "peak", 104.0), (28, "valley", 101.0), (32, "peak", 109)]
    assert _child_end(_turns(spring), _closes(36, b18=99.8), S, 0.5, 0.10, 12, False) == (None, None), \
        "the first peak after the dip sits back inside the box: the run came back"
    open_dip = [(0, "peak", 110), (4, "valley", 100), (8, "peak", 110), (12, "valley", 100), (16, "peak", 108),
                (20, "valley", 92.0), (24, "peak", 99.0), (28, "valley", 90.0)]
    end, candidate = _child_end(_turns(open_dip), _closes(32, b18=99.8), S, 0.5, 0.10, 12, False)
    assert end is None and candidate["ar_bar"] == 24, "a candidate below, unanswered: under S, undetermined"


def test_the_earliest_known_end_wins():
    spec = BELOW + [(40, "peak", 118), (44, "valley", 110.5), (48, "peak", 118.2), (52, "valley", 110.6)]
    end, candidate = box_end(_turns(spec), _closes(56, b18=99.8, b38=112.0), R, S, 0, 4, UNIT)
    assert end["kind"] == "breakdown" and candidate is None
