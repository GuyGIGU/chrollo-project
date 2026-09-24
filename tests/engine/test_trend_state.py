"""The daily trend-state classification (program Task 11): a PURE read over
segment_trends' own segment dicts — never a third trend reader — with one
hand-reasoned case per behavioral variant. Provisional rules; the operator's
trend-end labels calibrate them (marks enter baselines only after graduation,
so every expectation here is synthetic and reasoned from the rule text)."""
import pytest

from config import settings
from engine_alpha.structure.events.market_structure import (
    TREND_STATES,
    classify_trend_state,
)


def _seg(direction, start, terminal, end):
    return {"direction": direction, "start_bar": start,
            "terminal_bar": terminal, "end_bar": end,
            "terminal_price": 100.0}


def test_running_up_segment_is_trending():
    segs = [_seg(1, 10, 190, None)]
    assert classify_trend_state(segs, 200) == "trending"


def test_running_down_segment_is_correcting():
    segs = [_seg(1, 10, 120, 130), _seg(-1, 120, 195, None)]
    assert classify_trend_state(segs, 200) == "correcting"


def test_fresh_up_terminal_is_the_transition_zone_correcting():
    # The operator's transition zone: the uptrend just topped (terminal 5
    # bars from the edge, inside the reading clock) — the reaction is still
    # forming, not yet a base.
    segs = [_seg(1, 10, 195, 198)]
    assert classify_trend_state(segs, 200) == "correcting"


def test_fresh_down_terminal_opens_a_consolidation():
    segs = [_seg(-1, 10, 195, 198)]
    assert classify_trend_state(segs, 200) == "consolidating"


def test_an_aged_terminal_is_consolidating():
    edge_gap = int(settings.MIN_BASE_DAYS) + 5
    segs = [_seg(1, 10, 200 - edge_gap, 200 - edge_gap + 2)]
    assert classify_trend_state(segs, 200) == "consolidating"


def test_an_aged_down_terminal_is_also_consolidating():
    # The fourth transition cell, VALUE-pinned (2026-08-17 review, Beck: it
    # only appeared in the closed-set sweep, which any legal label passes) —
    # an aged bottom is a consolidation in progress, same as an aged top.
    edge_gap = int(settings.MIN_BASE_DAYS) + 5
    segs = [_seg(-1, 10, 200 - edge_gap, 200 - edge_gap + 2)]
    assert classify_trend_state(segs, 200) == "consolidating"


def test_no_structure_is_choppy():
    assert classify_trend_state([], 200) == "choppy"
    assert classify_trend_state(None, 200) == "choppy"


def test_the_latest_running_segment_wins():
    # A confirmed old uptrend plus a RUNNING downtrend at the edge — the MAN
    # shape's mirror. The edge state is the running segment's.
    segs = [_seg(1, 10, 150, 160), _seg(-1, 150, 190, None)]
    assert classify_trend_state(segs, 200) == "correcting"


def test_every_output_is_in_the_closed_set():
    cases = [[], [_seg(1, 0, 190, None)], [_seg(-1, 0, 190, None)],
             [_seg(1, 0, 195, 198)], [_seg(-1, 0, 100, 110)]]
    for segs in cases:
        assert classify_trend_state(segs, 200) in TREND_STATES
