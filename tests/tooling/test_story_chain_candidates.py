"""The story-chain candidate miner's battery (program Task 2).

The miner is a HEURISTIC candidate feed for the operator's keep/junk sheet —
not an engine read — so the battery is deliberately small: each detector fires
on a constructed chain shape, both stay silent on a plain trend, and the
sidecar path refuses the sealed set. The operator's sheet verdicts are the
real adjudication; a miner miss costs a sheet row, never a cohort.
"""
import numpy as np
import pandas as pd
import pytest

from tools.story_chain_candidates import (
    mine,
    scan_base_on_base,
    scan_shakeout_recovery,
)


def _frame(closes, spread=1.0):
    """Bars with a fixed daily range so ATR20 is ~``spread``."""
    idx = pd.bdate_range("2025-01-02", periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": c, "High": c + spread / 2,
                         "Low": c - spread / 2, "Close": c,
                         "Volume": np.full(len(c), 1e6)}, index=idx)


def _range_bars(n, lo=100.0, hi=108.0):
    """A worked oscillation between two levels."""
    return [lo + (hi - lo) * (0.5 + 0.45 * np.sin(i / 2.5)) for i in range(n)]


def test_base_on_base_fires_on_the_constructed_shape():
    closes = (_range_bars(70)                       # the parent box
              + list(np.linspace(112, 130, 12))     # breakout + run
              + [129.0 + 0.4 * np.sin(i) for i in range(20)]   # separated child
              + [129.0] * 5)
    cands = scan_base_on_base("SYN", _frame(closes, spread=2.0))
    assert cands, "the constructed base-on-base shape must surface"
    c = cands[0]
    assert c["chain"] == "base_on_base"
    assert c["separation_atr"] > 0           # child low ABOVE the old ceiling
    assert c["child_range_atr"] <= 4.0


def test_shakeout_recovery_fires_and_stamps_a_position():
    closes = (_range_bars(70)                       # the box
              + [99.0, 96.0, 95.0]                  # the violent undercut
              + list(np.linspace(96, 105, 10))      # the recovery
              + [103.5 + 0.3 * np.sin(i) for i in range(14)]   # holding pullback
              + [103.5] * 5)
    cands = scan_shakeout_recovery("SYN", _frame(closes, spread=2.0))
    assert cands, "the constructed after-shakeout shape must surface"
    c = cands[0]
    assert c["chain"] == "shakeout_recovery"
    assert c["position"] in ("above_floor", "tactical_band")
    assert c["undercut_atr"] >= 0.75

def test_plain_trend_is_silent_for_both_detectors():
    closes = list(np.linspace(50, 180, 240))         # relentless markup, no box
    df = _frame(closes, spread=1.5)
    assert scan_base_on_base("TRND", df) == []
    assert scan_shakeout_recovery("TRND", df) == []


def test_mine_keeps_one_candidate_per_ticker_per_chain():
    closes = (_range_bars(70) + list(np.linspace(112, 130, 12))
              + [129.0 + 0.4 * np.sin(i) for i in range(20)] + [129.0] * 5)
    frames = {"SYN": _frame(closes, spread=2.0)}
    ranked = mine(frames, top=5)
    assert set(ranked) == {"base_on_base", "shakeout_recovery"}
    assert len(ranked["base_on_base"]) <= 1          # best-per-ticker dedupe


def test_out_path_refuses_the_sealed_set(tmp_path, monkeypatch):
    from tools import story_chain_candidates as mod
    import os
    from _paths import REPO_ROOT
    root = str(REPO_ROOT)
    with pytest.raises(ValueError):
        mod.main(["--out", os.path.join(root, "docs", "marks", "cands.json")])
    with pytest.raises(ValueError):
        mod.main(["--out", os.path.join(root, "docs", "decisions.md")])
