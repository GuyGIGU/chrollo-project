"""Candidate-framing identity, named once (near-miss lane Task 2).

One definition, two forms: the in-window integer key (per-evaluation dedup,
the cascade-trace match) and the date-anchored cross-night key (persistence,
census, the cohort store's UNIQUE constraint). The property that matters:
positions slide with the nightly 2y trim, dates do not — so only the
date-anchored form may ever be persisted or compared across frames.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from engine_alpha.election_identity import framing_date_key, framing_window_key
from engine_alpha.structure.box.box_trace import _trace_find, _trace_pair

pytestmark = pytest.mark.regression


def test_trace_identity_slots_match_the_candidate_contract():
    """The leaf module's named slot indices must track the Candidate tuple's
    real field order (it cannot import the producer without a cycle) — a
    slot insertion in box_primitives goes RED here instead of silently
    skewing every trace annotation (2026-08-25 sweep)."""
    from engine_alpha.structure.box import box_trace
    from engine_alpha.structure.box.box_primitives import Candidate

    fields = Candidate._fields
    assert fields.index("r_anchor_bar") == box_trace._CAND_R_ANCHOR_BAR
    assert fields.index("s_anchor_bar") == box_trace._CAND_S_ANCHOR_BAR
    assert fields.index("cand_start") == box_trace._CAND_START


def test_trace_find_derives_from_the_window_key():
    trace: list = []
    # Two records with the same anchors: one rejected, one valid — the match
    # must key on (anchors, start) AND the valid verdict, exactly as before.
    _trace_pair(trace, "rejected", "respect", "x", 110.0, 100.0, 0.10, 4, 8, 4)
    _trace_pair(trace, "valid", None, None, 110.0, 100.0, 0.10, 4, 8, 4)
    _trace_pair(trace, "valid", None, None, 112.0, 101.0, 0.11, 12, 16, 12)
    cand = (0.5, 110.0, 100.0, 0.10, 3, 3, 0, 4, 8, 4, 40, "strict", None)
    rec = _trace_find(trace, cand)
    assert rec is not None and rec["verdict"] == "valid"
    assert (rec["r_anchor_bar"], rec["s_anchor_bar"]) == (4, 8)
    assert framing_window_key(4, 8, 4) == (4, 8, 4)
    # No valid record for these anchors -> no match (never a fuzzy fallback).
    other = (0.5, 111.0, 99.0, 0.12, 3, 3, 0, 20, 24, 20, 40, "strict", None)
    assert _trace_find(trace, other) is None


def test_date_key_survives_the_nightly_trim_where_positions_do_not():
    idx_long = pd.bdate_range("2025-06-02", periods=120)
    closes = np.linspace(100.0, 110.0, 120)
    frame_long = pd.DataFrame({"Close": closes}, index=idx_long)
    # The same chart one trim later: 10 leading sessions gone, positions slide.
    frame_short = frame_long.iloc[10:]

    r_bar_long, s_bar_long = 50, 54
    r_bar_short, s_bar_short = 40, 44          # same sessions, shifted positions
    assert frame_long.index[r_bar_long] == frame_short.index[r_bar_short]

    key_long = framing_date_key("AAA", 110.123456, 100.0,
                                frame_long.index, r_bar_long, s_bar_long)
    key_short = framing_date_key("AAA", 110.123456, 100.0,
                                 frame_short.index, r_bar_short, s_bar_short)
    assert key_long == key_short                # dates anchor; positions don't
    assert key_long[1] == 110.1235              # 4dp rail convention
    assert key_long[3] == frame_long.index[r_bar_long].strftime("%Y-%m-%d")

    # A different anchor session is a DIFFERENT framing, same rails or not.
    moved = framing_date_key("AAA", 110.123456, 100.0,
                             frame_long.index, r_bar_long + 1, s_bar_long)
    assert moved != key_long
    # And the window form is explicitly frame-local: the same framing yields
    # different window keys across the two frames — the reason it must never
    # be persisted.
    assert framing_window_key(r_bar_long, s_bar_long, r_bar_long) != \
        framing_window_key(r_bar_short, s_bar_short, r_bar_short)
