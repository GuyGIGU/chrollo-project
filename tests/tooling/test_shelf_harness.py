"""Shelf-harness plumbing spine (gap-breach Task 5) — hermetic.

The full instrument reads the operator's marks DB + frozen frames (offline but
machine-local); this spine keeps the probe honest on every pytest run without
either: a synthetic drawn basis must yield a PASS verdict on a clean pullback
shelf, the exact-window isolation must name a reject on a broken one, and the
out-of-range length guard must speak before the detector is ever consulted.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from tools.shelf_harness import probe_shelf

pytestmark = pytest.mark.regression


def _frame(n: int = 260) -> pd.DataFrame:
    """A worked 100..110 range with a clean terminal 3-bar pullback shelf.

    Deterministic, no RNG: an oscillating base (rail-to-rail traversal), a
    final reaction that descends into support and RESTS on its terminal low
    with drying volume — the detector's pullback-and-rest happy path.
    """
    idx = pd.bdate_range("2025-06-02", periods=n)
    base = np.full(n, 105.0)
    osc = 5.0 * np.sin(np.arange(n) / 3.0)
    close = base + osc
    # Terminal shelf: three quiet bars descending onto support and resting.
    close[-3:] = [103.0, 101.6, 101.2]
    high = close + 0.8
    low = close - 0.8
    high[-3:] = [103.6, 102.2, 101.7]
    low[-3:] = [102.2, 101.0, 100.9]
    vol = np.full(n, 1_000_000.0)
    vol[-3:] = 400_000.0  # dry-up
    return pd.DataFrame({"Open": close, "High": high, "Low": low,
                         "Close": close, "Volume": vol}, index=idx)


def _mark_and_event(df: pd.DataFrame, shelf_bars: int):
    idx = df.index
    mark = SimpleNamespace(
        ticker="TEST", as_of_date=str(idx[-1].date()),
        resistance=110.0, support=100.0,
        box_start_date=str(idx[-120].date()),
        r_anchor_date=None, s_anchor_date=None,
        frame_digest="deadbeefdeadbeef",
    )
    ev = SimpleNamespace(start_date=str(idx[-shelf_bars].date()),
                         end_date=str(idx[-1].date()))
    return mark, ev


def test_clean_pullback_shelf_passes():
    df = _frame()
    mark, ev = _mark_and_event(df, 3)
    row = probe_shelf(df, mark, ev)
    assert row["verdict"] == "pass", row
    assert row["m"]["low_beyond_tol"] == "inside"
    assert row["m"]["low_descent_frac"] == 1.0
    # The printed pullback_profile is the DETECTOR's own gated statistic —
    # on a pass row, the blessed candidate's exact value (first-bar high −
    # support low over the profile unit), never the whole-window range.
    assert row["m"]["pullback_profile"] is not None
    assert row["m"]["pullback_profile"] <= settings.LPS_PULLBACK_PROFILE_MAX


def test_marked_window_reject_is_isolated_and_named():
    # Same base, but the marked shelf RISES into the rail (lows marching up
    # after an interior low) — the detector must reject the EXACT marked
    # window and the probe must surface a single named slug, not a verdict
    # borrowed from some other window length.
    df = _frame()
    df.iloc[-3:, df.columns.get_loc("Low")] = [101.0, 102.0, 103.0]
    df.iloc[-3:, df.columns.get_loc("High")] = [102.0, 103.0, 104.2]
    df.iloc[-3:, df.columns.get_loc("Close")] = [101.8, 102.8, 104.0]
    df.iloc[-3:, df.columns.get_loc("Open")] = [101.2, 102.1, 103.1]
    mark, ev = _mark_and_event(df, 3)
    row = probe_shelf(df, mark, ev)
    assert row["verdict"] == "reject", row
    # The SPECIFIC first-fail slug for this window (lows marching up = the
    # rest gate), not any non-empty string: this is what proves the
    # length-pinned isolation returns THIS window's own reject rather than a
    # verdict aggregated from other scanned lengths.
    assert row["reject"] == "does not rest on its low", row


def test_out_of_range_length_named_before_detector():
    df = _frame()
    too_long = settings.LPS_LENGTH_MAX + 3
    mark, ev = _mark_and_event(df, too_long)
    row = probe_shelf(df, mark, ev)
    assert row["verdict"] == "length-outside-range"
    assert str(settings.LPS_LENGTH_MAX) in row["reject"]
