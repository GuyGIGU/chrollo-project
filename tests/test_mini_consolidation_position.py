"""The mini-consolidation POSITION attribute (story-chain program Task 4).

The 2026-08-23 unification ruling: the ceiling shelf and the inner
mini-consolidation are ONE event; position is a measured attribute with a
stated banding convention (inclusive ties, ceiling evaluated first). These
tests pin the convention so a boundary-sitting structure can never band
differently between runs or between the live reader and the diagnostic
mirror (both stamp at the ONE select_inner_box point).
"""
import math

import pandas as pd

from config import settings
from engine_alpha.structure.bricks import EquilibriumBox, find_inner_box
from engine_alpha.structure.inner_box import (
    mini_consolidation_position,
    select_inner_box,
)


def _ohlc_from_closes(closes, *, band=1.0, volume=1000.0):
    return pd.DataFrame({
        "Open": list(closes),
        "High": [c + band for c in closes],
        "Low": [c - band for c in closes],
        "Close": list(closes),
        "Volume": [volume] * len(closes),
    })


def _parent_box(**overrides):
    values = dict(S=100.0, R=110.0, start_bar=0, base_len=30, box_width=0.1,
                  quality=1.0, r_touches=3, s_touches=3, breach_days=0,
                  r_anchor_bar=0, s_anchor_bar=0, n_full_traversals=2,
                  traversal_density=0.5)
    values.update(overrides)
    return EquilibriumBox(**values)


# --- the pure banding convention (parent R=110, S=100, ATR=2 -> tol=2) ------

def test_ceiling_band_is_inclusive_at_the_tolerance_edge():
    assert mini_consolidation_position(109.0, 104.0, 110.0, 100.0, 2.0) == "at_ceiling"
    # exactly parent_r - tol: the tie lands IN the band (stated convention)
    assert mini_consolidation_position(108.0, 104.0, 110.0, 100.0, 2.0) == "at_ceiling"
    # one cent below the band edge: no longer the ceiling
    assert mini_consolidation_position(107.99, 104.0, 110.0, 100.0, 2.0) != "at_ceiling"


def test_support_band_is_inclusive_and_mid_range_is_the_remainder():
    assert mini_consolidation_position(106.0, 101.0, 110.0, 100.0, 2.0) == "on_support"
    assert mini_consolidation_position(106.0, 102.0, 110.0, 100.0, 2.0) == "on_support"
    assert mini_consolidation_position(106.0, 102.01, 110.0, 100.0, 2.0) == "mid_range"


def test_degenerate_parent_lands_at_the_ceiling_deterministically():
    # tol=5 on a 4-point parent: BOTH bands hold; the ruled higher-quality
    # position (ceiling first) wins, every run.
    assert mini_consolidation_position(100.0, 100.5, 104.0, 100.0, 5.0) == "at_ceiling"


def test_unusable_inputs_refuse_to_none_never_fabricate():
    assert mini_consolidation_position(None, 104.0, 110.0, 100.0, 2.0) is None
    assert mini_consolidation_position(109.0, 104.0, None, 100.0, 2.0) is None
    assert mini_consolidation_position(109.0, 104.0, 110.0, 100.0, 0.0) is None
    assert mini_consolidation_position(109.0, 104.0, 110.0, 100.0, math.nan) is None


# --- the ONE stamping point ---------------------------------------------------

_WIDE_TIGHT = ([100, 106, 112, 118, 116, 110, 104, 102] * 5
               + [101, 103, 105, 107, 109, 107, 105, 103] * 5)


def test_live_reader_stamps_position_from_the_parent_rails():
    df = _ohlc_from_closes(_WIDE_TIGHT)
    parent = _parent_box(start_bar=0, base_len=len(df), box_width=0.18,
                         R=110.0, S=100.0)
    inner = find_inner_box(df, parent, 1.0)
    assert inner is not None
    # The tight sub-range tops ~110 on a ~2-point candidate ATR: the ceiling.
    assert inner.position == "at_ceiling"
    assert inner.detection.get("position") == inner.position


def test_select_without_parent_rails_stamps_none_not_a_guess():
    df = _ohlc_from_closes(_WIDE_TIGHT)
    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    selected = select_inner_box(eval_df, 0, len(df), 0.18, len(df))
    assert selected is not None
    assert selected["position"] is None
