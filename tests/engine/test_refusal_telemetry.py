"""Named universe-prep refusal telemetry (gap-breach Task 7) — hermetic spine.

Move 4's contract: refusal stays an expected operational outcome delivered by
return value (never an exception, never a sentinel), the reasonless wrappers
DERIVE from the one reasoned implementation (no reasoned twin can drift from
the live gate), and the replay seam can name WHICH gate refused WHICH session.
One behavioral test per risk surface; no per-slug string unit tests (they
earn nothing — Beck P4).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.evaluation import (
    _prepare_eval_frame,
    _prepare_eval_frame_with_reason,
)
from core.calibration.replay import prepared_frame, prepared_frame_with_reason, refusal_scan

pytestmark = pytest.mark.regression


def _healthy_frame(n: int = 300) -> pd.DataFrame:
    """A frame that passes every baseline gate: rising, liquid, priced."""
    idx = pd.bdate_range("2025-01-02", periods=n)
    lo = max(float(settings.MIN_PRICE) * 4, 40.0)
    close = np.linspace(lo, lo * 1.6, n)          # monotonic up: SMA + YoY pass
    vol = np.full(n, float(settings.MIN_VOLUME_50D) * 3)
    return pd.DataFrame({"Open": close, "High": close * 1.01,
                         "Low": close * 0.99, "Close": close,
                         "Volume": vol}, index=idx)


def test_reasonless_wrapper_derives_from_the_reasoned_prep():
    df = _healthy_frame()
    prep_r, reason = _prepare_eval_frame_with_reason(df)
    assert reason is None and prep_r is not None
    prep = _prepare_eval_frame(df)
    assert prep is not None
    # Same verdict, same content: the wrapper may not re-derive anything.
    assert prep["yearly_return"] == prep_r["yearly_return"]
    pd.testing.assert_frame_equal(prep["df"], prep_r["df"])


def test_refusals_are_named_by_the_first_failing_gate():
    short = _healthy_frame(120)                    # < 200 bars
    prep, reason = _prepare_eval_frame_with_reason(short)
    assert prep is None and reason[0] == "bars"

    illiquid = _healthy_frame()
    illiquid["Volume"] = float(settings.MIN_VOLUME_50D) * 0.01
    prep, reason = _prepare_eval_frame_with_reason(illiquid)
    assert prep is None
    gate, samples = reason
    assert gate == "vol50"
    assert "vol_50" in samples                     # sampled values ride along


def test_first_fail_precedence_holds_across_the_whole_gate_order():
    """A frame failing SEVERAL gates at once must name the EARLIEST in the
    documented order (price -> vol50 -> sma50 -> sma200 -> yoy) — the
    REFUSED(universe) console lines are only trustworthy if a reorder of the
    checks cannot silently relabel a refusal."""
    # Declining + illiquid: below SMA50, below SMA200, negative YoY AND
    # illiquid — vol50 must be the one named (earliest failing gate).
    multi = _healthy_frame()
    multi["Close"] = multi["Close"].iloc[::-1].to_numpy()   # monotonic DOWN
    multi["Open"] = multi["Close"]
    multi["High"] = multi["Close"] * 1.01
    multi["Low"] = multi["Close"] * 0.99
    multi["Volume"] = float(settings.MIN_VOLUME_50D) * 0.01
    prep, reason = _prepare_eval_frame_with_reason(multi)
    assert prep is None and reason[0] == "vol50"

    # Same declining frame, liquid: sma50 outranks sma200 and yoy.
    declining = multi.copy()
    declining["Volume"] = float(settings.MIN_VOLUME_50D) * 3
    prep, reason = _prepare_eval_frame_with_reason(declining)
    assert prep is None and reason[0] == "sma50"

    # Sub-price floor outranks everything after bars (a penny stock that is
    # also illiquid and declining still names "price").
    penny = multi.copy()
    penny[["Open", "High", "Low", "Close"]] *= (
        float(settings.MIN_PRICE) * 0.1 / float(penny["Close"].iloc[-1]))
    prep, reason = _prepare_eval_frame_with_reason(penny)
    assert prep is None and reason[0] == "price"


def test_replay_seam_scan_names_refused_sessions_and_stays_quiet_on_pass():
    healthy = _healthy_frame()
    tail = healthy.index[-3:]
    assert refusal_scan(healthy, tail) == []
    # The reasonless replay prep still passes (derivation, not divergence).
    assert prepared_frame(healthy, tail[-1]) is not None

    illiquid = _healthy_frame()
    illiquid["Volume"] = float(settings.MIN_VOLUME_50D) * 0.01
    refused = refusal_scan(illiquid, illiquid.index[-3:])
    assert len(refused) == 3
    assert all(slug == "vol50" for _, slug in refused)
    assert refused[0][0] == illiquid.index[-3].strftime("%Y-%m-%d")
    prep, reason = prepared_frame_with_reason(illiquid, illiquid.index[-1])
    assert prep is None and reason[0] == "vol50"
