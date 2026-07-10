"""Election-stability EC-8 battery (Calibration at Scale, Task 14).

Flag-off must be compute-free, not merely value-identical: an equal-output
check would pass even if the k backward re-reads ran and burned the scan
budget, so the inert proof is NEVER-CONSULTED (the probe raises if touched).
Hermetic: everything replays the committed marks-corpus fixture.
"""
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline import stability
from core.pipeline.screener import _evaluate_ticker
from tools.replay import flag_capture, load_sealed_fixture


def _fire_frame():
    """A pinned corpus hit sliced to its frozen first-fire session."""
    frames, baseline = load_sealed_fixture()
    hit = next(s for s in baseline["setups"] if s["status"] == "hit")
    import pandas as pd
    df = frames[hit["ticker"]].loc[:pd.Timestamp(hit["first_fire"])]
    return hit["ticker"], df, float(hit["spy_6m_return"])


def test_flag_off_probe_is_never_consulted(monkeypatch):
    ticker, df, spy = _fire_frame()
    monkeypatch.setattr(stability, "election_stability",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError(
                            "stability probe consulted while the flag is off")))
    assert settings.ELECTION_STABILITY_ENABLED is False  # shipped default
    result = _evaluate_ticker(ticker, df, spy, 0.5)
    assert result is not None
    assert not any(k.startswith("_stability") for k in result)


def test_flag_on_consults_and_emits_raw_diagnostics():
    ticker, df, spy = _fire_frame()
    with flag_capture(ELECTION_STABILITY_ENABLED=True):
        t0 = time.perf_counter()
        result = _evaluate_ticker(ticker, df, spy, 0.5)
        elapsed_ms = (time.perf_counter() - t0) * 1000
    assert result is not None
    frac = result["_stability_same_frac"]
    assert frac is None or 0.0 <= frac <= 1.0
    assert 0 <= result["_stability_streak"] <= result["_stability_probes"]
    assert result["_stability_probes"] <= settings.ELECTION_STABILITY_LOOKBACK
    # Not a gate — just visibility while the cost bound is being recorded.
    assert elapsed_ms < 30_000


def test_probe_is_deterministic():
    ticker, df, spy = _fire_frame()
    with flag_capture(ELECTION_STABILITY_ENABLED=True):
        a = _evaluate_ticker(ticker, df, spy, 0.5)
        b = _evaluate_ticker(ticker, df, spy, 0.5)
    keys = ("_stability_same_frac", "_stability_streak", "_stability_probes")
    assert [a[k] for k in keys] == [b[k] for k in keys]
