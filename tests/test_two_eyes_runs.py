"""The run reader copy's own pure tests: COPIED from tests/test_final_method_step10.py (two-eyes-reader task 7), re-pointed at the
new reader's copy. Verbatim but for the imports. None of them reads a number the copy takes from `method_numbers`;
those values are pinned in tests/test_two_eyes_copies_equal_originals.py. The originals' tests stay where
they are, frozen with the old engine; these move with the copy and change when it changes.

Copied: the run reader's own tests. Left with the originals (they test the old engine, not the piece): the root-election, flag and integration tests.
"""
from __future__ import annotations

from engine_alpha.two_eyes.runs import runs_on_the_line


# A rise of two higher highs and two higher lows, ended by a lower high on day 20; the reaction after the
# climax (118 on day 12) makes a lower low on day 24 before the first higher low on day 32.
LINE_UP = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 104), (12, "peak", 118), (16, "valley", 108),
           (20, "peak", 114), (24, "valley", 106), (28, "peak", 112), (32, "valley", 109), (36, "peak", 113)]


def _turns(spec, forming_last=False):
    out = [(b, k, float(p), b + 1) for b, k, p in spec]
    if forming_last:
        b, k, p, _ = out[-1]
        out[-1] = (b, k, p, None)
    return out


def test_a_run_ends_at_the_first_swing_that_fails_it_and_the_reaction_low_precedes_the_first_higher_low():
    runs = runs_on_the_line(_turns(LINE_UP))
    assert len(runs) == 1
    r = runs[0]
    assert (r["kind"], r["climax_bar"], r["climax_price"]) == ("BC", 12, 118.0)
    assert (r["ar_bar"], r["ar_price"]) == (24, 106.0), "the lowest low of the reaction before the first higher low"
    assert (r["launch_bar"], r["end_bar"]) == (0, 20), "launched on day 0, ended by the lower high on day 20"


def test_a_run_ended_by_a_lower_low_reacts_from_that_low():
    spec = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 104), (12, "peak", 118), (16, "valley", 102),
            (20, "peak", 109), (24, "valley", 105)]
    r = runs_on_the_line(_turns(spec))[0]
    assert (r["climax_bar"], r["ar_bar"], r["end_bar"]) == (12, 16, 16), "the lower low both ends the run and opens the reaction"


def test_a_selling_climax_is_the_mirror():
    spec = [(0, "peak", 120), (4, "valley", 110), (8, "peak", 116), (12, "valley", 100), (16, "peak", 108),
            (20, "valley", 104), (24, "peak", 111), (28, "valley", 106), (32, "peak", 109)]
    r = runs_on_the_line(_turns(spec))[0]
    assert (r["kind"], r["climax_bar"], r["climax_price"]) == ("SC", 12, 100.0)
    assert (r["ar_bar"], r["ar_price"]) == (24, 111.0), "the highest high of the reaction before the first lower high"


def test_no_higher_low_yet_means_no_reaction_and_no_root():
    assert runs_on_the_line(_turns(LINE_UP[:8])) == [], "the reaction is still running: the climax is not proven"
    assert runs_on_the_line(_turns(LINE_UP[:9], forming_last=True)) == [], "a forming turn never anchors"


def test_a_lower_low_before_the_higher_high_is_not_part_of_the_rise():
    spec = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 96), (12, "peak", 118), (16, "valley", 108),
            (20, "peak", 114), (24, "valley", 104), (28, "peak", 112), (32, "valley", 107)]
    r = runs_on_the_line(_turns(spec))[0]
    assert (r["launch_bar"], r["climax_bar"], r["ar_bar"]) == (8, 12, 24),         "the rise needs a higher low AND a higher high: it launches from the day-8 low, not day 0"


def test_a_single_leg_or_an_equal_top_is_not_a_run():
    assert runs_on_the_line(_turns([(0, "valley", 100), (4, "peak", 110), (8, "valley", 104)])) == []
    flat = [(0, "valley", 100), (4, "peak", 110), (8, "valley", 104), (12, "peak", 110), (16, "valley", 106)]
    assert runs_on_the_line(_turns(flat)) == [], "an equal top does not continue a rise"


# ---- NEW with the copy (task 7): an equal high ends a run, visibly -----------------------------------------
def test_an_equal_high_ends_the_run_and_the_run_is_returned():
    """The copied equal-top test is vacuous: its run is still open at the right edge and is dropped whether an
    equal high ends it or continues it. Here the run's reaction is decided, so it IS returned, and the equal
    high at bar 10 is what ended it — the climax is the peak before it (bar 6), not the equal one. If an equal
    high continued the run, the climax would move to bar 10 and 49 of the 88 fixture lines would change."""
    line = [(0, "valley", 100.0, 1), (2, "peak", 110.0, 3), (4, "valley", 104.0, 5), (6, "peak", 118.0, 7),
            (8, "valley", 108.0, 9), (10, "peak", 118.0, 11), (12, "valley", 106.0, 13), (14, "peak", 112.0, 15),
            (16, "valley", 109.0, 17), (18, "peak", 115.0, None)]
    (run,) = runs_on_the_line(line)
    assert (run["climax_bar"], run["end_bar"], run["ar_bar"]) == (6, 10, 12)
