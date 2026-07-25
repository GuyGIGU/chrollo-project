"""Story-rescue last-resort pool — Task 8 flag-protocol guards (EC-8).

Pins the four laws of the rung:

1. **Flag-off is compute-free** — the story builder is never consulted
   (byte-identity follows: the dark branch is a plain short-circuit).
2. **Last resort, provably** — the rung runs only when the strict, rescued,
   AND band pools are all empty; a band candidate blocks it.
3. **The ruled form judges, the other gates stay** — the builder admits the
   operator-ruled sentence (>=2 completed support tests + terminal resistance
   posture + no drift, as-of), refuses without posture, and the respect gate
   still refuses BEFORE the story judgment runs.
4. **The traversal gate judges the story pool** — a story candidate is not
   exempt from the count/density floors (the measured census requirement).

Synthetic frames, deterministic, instant. The fleet-scale guards (26-identity
election stability + the named negative bench) are the Task-9 battery.
"""
from __future__ import annotations

import pandas as pd
import pytest

from config import settings
from engine_alpha.structure import box_primitives
from engine_alpha.structure.box_primitives import (
    _story_pool_candidates,
    collect_zigzag_candidates,
)

pytestmark = pytest.mark.regression

R, S, ATR = 14.0, 12.0, 1.0
ZZ = [(0, "peak", 14.0), (5, "valley", 12.0)]


def _frame(bars):
    return pd.DataFrame({"High": [b[0] for b in bars],
                         "Low": [b[1] for b in bars],
                         "Close": [b[2] for b in bars],
                         "Volume": [1_000_000.0] * len(bars)})


def _story_bars():
    """R=14 / S=12 (width 0.167), atr=1: two completed support tests
    ([3,5] and [10,12]) and a terminal resistance engagement closing above
    R — the ruled sentence. No bar leaves the buffered band."""
    bars = [
        (14.0, 13.2, 13.4),
        (13.4, 12.9, 13.1),
        (13.3, 12.8, 13.0),
        (13.0, 12.4, 12.7),
        (12.9, 12.2, 12.6),
        (12.8, 12.0, 12.5),
        (13.2, 12.6, 13.0),
        (13.3, 12.7, 13.1),
        (13.3, 12.7, 13.0),
        (13.4, 12.8, 13.1),
        (13.0, 12.4, 12.7),
        (12.9, 12.3, 12.6),
        (13.0, 12.2, 12.8),
        (13.3, 12.7, 13.1),
    ]
    bars += [(13.3, 12.7, 13.0)] * 11        # bars 14-24, quiet mid-range
    bars += [
        (13.6, 12.9, 13.3),
        (13.8, 13.1, 13.6),
        (14.0, 13.3, 13.8),
        (14.2, 13.5, 14.05),
        (14.4, 13.7, 14.2),                  # terminal close above R
    ]
    return bars


def _run_builder(bars, trace=None):
    df = _frame(bars)
    return _story_pool_candidates(df, df["High"].values, df["Low"].values,
                                  ZZ, ATR, 0, trace=trace)


def test_builder_admits_the_ruled_sentence_and_narrates():
    trace = []
    pool = _run_builder(_story_bars(), trace=trace)
    assert len(pool) == 1
    tup = pool[0]
    assert (tup[1], tup[2], tup[9], tup[10], tup[11]) == (R, S, 0, 30, "story")
    valid = [r for r in trace if r["verdict"] == "valid"]
    assert len(valid) == 1
    assert valid[0]["detail"].startswith("story-admitted")
    assert valid[0]["rescued"] is True


def test_builder_refuses_without_terminal_posture():
    """Two completed support tests alone are NOT the ruled form — the window
    must end engaging R in pre-breakout posture. A no-posture window dies at
    the O(1) prefilter, silently (like width): no episode read, no trace."""
    trace = []
    assert _run_builder(_story_bars()[:20], trace=trace) == []
    assert trace == []


def test_builder_narrates_a_story_stage_refusal():
    """Posture without the worked-support leg (one completed S-test only)
    reaches the episode read and is refused at the story stage, narrated."""
    bars = _story_bars()
    for i in (10, 11, 12):                   # flatten the second S-test
        bars[i] = (13.3, 12.7, 13.0)
    trace = []
    assert _run_builder(bars, trace=trace) == []
    assert {r["stage"] for r in trace} == {"story"}
    assert "ruled form not read" in trace[0]["detail"]


def test_builder_keeps_the_respect_gate():
    bars = _story_bars()
    for i in range(14, 22):                  # 8 outside days -> share < 0.80
        high, _low, close = bars[i]
        bars[i] = (high, 11.0, close)
    trace = []
    assert _run_builder(bars, trace=trace) == []
    # Died at respect, silently (the strict pass narrates respect for these
    # same pairs); the story judgment was never reached.
    assert all(r["stage"] != "story" for r in trace)


def test_flag_off_is_compute_free(monkeypatch):
    df = _frame(_story_bars())
    monkeypatch.setattr(box_primitives, "_build_candidate", lambda *a, **k: None)
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", False)
    monkeypatch.setattr(settings, "STORY_POOL_ENABLED", False)
    monkeypatch.setattr(
        box_primitives, "_story_pool_candidates",
        lambda *a, **k: pytest.fail("story pool consulted flag-off"))
    assert collect_zigzag_candidates(df, len(df), ATR,
                                     enforce_traversal=True) == []


def test_rung_is_last_resort_after_the_band_pool(monkeypatch):
    df = _frame(_story_bars())
    sentinel = [(0.5, R, S, 0.1667, 3, 3, 0, 0, 5, 0, len(df), "band")]
    monkeypatch.setattr(box_primitives, "_build_candidate", lambda *a, **k: None)
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", True)
    monkeypatch.setattr(settings, "STORY_POOL_ENABLED", True)
    monkeypatch.setattr(box_primitives, "_band_rail_candidates",
                        lambda *a, **k: list(sentinel))
    monkeypatch.setattr(
        box_primitives, "_story_pool_candidates",
        lambda *a, **k: pytest.fail(
            "story pool consulted while the band pool held candidates"))
    monkeypatch.setattr(box_primitives, "_apply_traversal_gate",
                        lambda eq_df, pool, *a, **k: pool)
    assert collect_zigzag_candidates(df, len(df), ATR,
                                     enforce_traversal=True) == sentinel


def test_traversal_gate_judges_the_story_pool(monkeypatch):
    df = _frame(_story_bars())
    tup = (0.5, R, S, 0.1667, 3, 3, 0, 0, 5, 0, len(df), "story")
    monkeypatch.setattr(box_primitives, "_build_candidate", lambda *a, **k: None)
    monkeypatch.setattr(settings, "BAND_RAILS_ENABLED", False)
    monkeypatch.setattr(settings, "STORY_POOL_ENABLED", True)
    monkeypatch.setattr(box_primitives, "_story_pool_candidates",
                        lambda *a, **k: [tup])
    monkeypatch.setattr(settings, "TRAVERSAL_MIN", 99)
    assert collect_zigzag_candidates(df, len(df), ATR,
                                     enforce_traversal=True) == []
