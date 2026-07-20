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
from engine_alpha import stability
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
    assert frac is not None and 0.0 <= frac <= 1.0  # ample frame: k real probes
    assert result["_stability_probes"] == settings.ELECTION_STABILITY_LOOKBACK
    assert 0 <= result["_stability_streak"] <= result["_stability_probes"]
    assert 0 <= result["_stability_refused"] <= result["_stability_probes"]
    # Executable cost bound tied to the ledger's flip evidence (~2.75s/ticker
    # at k=3): 15s is ~5x headroom for machine noise, but a probe that starts
    # re-running LPS/bins/scoring per shift (10x-class regression) fails here
    # instead of silently going stale in the ledger.
    assert elapsed_ms < 15_000


def test_probe_is_deterministic():
    ticker, df, spy = _fire_frame()
    with flag_capture(ELECTION_STABILITY_ENABLED=True):
        a = _evaluate_ticker(ticker, df, spy, 0.5)
        b = _evaluate_ticker(ticker, df, spy, 0.5)
    keys = ("_stability_same_frac", "_stability_streak", "_stability_probes",
            "_stability_refused")
    assert [a[k] for k in keys] == [b[k] for k in keys]


# ── Loop-logic pins on hand-reasoned fakes (Council finding 8: without
# these, a constant-returning stub passes the whole battery) ─────────────


def _stub(R=12.0, S=10.0, start_bar=0):
    class _S:
        pass
    s = _S()
    s.R, s.S = R, S
    s.box = type("B", (), {"start_bar": start_bar})()
    return s


def _probe_env(monkeypatch, raw_len, reads_by_len, refuse_lens=()):
    """Fake the probe's two seams. Slices signal their shift via LENGTH:
    raw of raw_len -> shift j hands prep a slice of raw_len - j. The ATR
    sample offset is pinned to 1 so even the shortest synthetic slice can be
    sampled (the real prep never returns frames under 200 bars)."""
    import pandas as pd

    import engine_alpha.evaluation as evaluation
    import engine_alpha.structure.narrative as narrative

    monkeypatch.setattr(settings, "STRUCTURE_ATR_SAMPLE_OFFSET", 1)

    ref_df = pd.DataFrame({"ATR_10": [1.0] * raw_len, "Close": [11.0] * raw_len},
                          index=pd.bdate_range("2026-01-05", periods=raw_len))
    raw_df = ref_df[["Close"]]

    def fake_prep(sliced):
        if len(sliced) in refuse_lens:
            return None
        return {"df": ref_df.iloc[:len(sliced)]}

    monkeypatch.setattr(evaluation, "_prepare_eval_frame", fake_prep)
    monkeypatch.setattr(narrative, "read_structure",
                        lambda df, atr: reads_by_len.get(len(df)))
    return raw_df, _stub(), ref_df


def test_probe_persistent_election_counts_every_shift(monkeypatch):
    same = _stub()
    raw, ref, ref_df = _probe_env(monkeypatch, 10, {9: same, 8: same, 7: same})
    out = stability.election_stability(raw, ref, ref_df)
    assert out == {"same_frac": 1.0, "streak": 3, "probes": 3, "refused": 0}


def test_probe_flicker_breaks_the_streak_midwalk(monkeypatch):
    same, different = _stub(), _stub(R=15.0)  # 3.0 off >> 0.2 tolerance
    raw, ref, ref_df = _probe_env(monkeypatch, 10,
                                  {9: same, 8: different, 7: same})
    out = stability.election_stability(raw, ref, ref_df)
    assert (out["same_frac"], out["streak"]) == (2 / 3, 1)
    assert (out["probes"], out["refused"]) == (3, 0)


def test_probe_prep_refusal_is_not_same_and_counted_apart(monkeypatch):
    same = _stub()
    raw, ref, ref_df = _probe_env(monkeypatch, 10, {8: same, 7: same},
                                  refuse_lens={9})
    out = stability.election_stability(raw, ref, ref_df)
    assert (out["same_frac"], out["streak"]) == (2 / 3, 0)  # D-1 refused
    assert out["refused"] == 1


def test_probe_short_frame_reports_the_probes_it_could_run(monkeypatch):
    same = _stub()
    raw, ref, ref_df = _probe_env(monkeypatch, 2, {1: same})
    out = stability.election_stability(raw, ref, ref_df)
    assert (out["probes"], out["same_frac"]) == (1, 1.0)
