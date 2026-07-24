"""Shared replay layer guards (Calibration at Scale, Task 6).

The layer's safety properties, pinned: the flag capture ALWAYS restores (a
leaked flag mid-batch poisons every later measurement), unknown flags are
refused loudly, and the corpus gate's fixture names still resolve to the one
shared implementation (the fold is real, not a copy).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from tools import marks_corpus, replay


def test_flag_capture_restores_on_success_and_crash():
    prior = settings.BAND_RAILS_ENABLED
    with replay.flag_capture(BAND_RAILS_ENABLED=not prior):
        assert settings.BAND_RAILS_ENABLED is (not prior)
    assert settings.BAND_RAILS_ENABLED is prior

    with pytest.raises(RuntimeError):
        with replay.flag_capture(BAND_RAILS_ENABLED=not prior):
            raise RuntimeError("mid-capture crash")
    assert settings.BAND_RAILS_ENABLED is prior


def test_flag_capture_refuses_unknown_flags():
    with pytest.raises(AttributeError):
        with replay.flag_capture(NO_SUCH_FLAG_EVER=True):
            pass


def test_flag_capture_multi_flag_typo_flips_nothing():
    # A typo in the SECOND name must not leave the first flag set with the
    # restoring finally never entered (Council finding 7): validate all
    # names before touching any flag.
    prior = settings.BAND_RAILS_ENABLED
    with pytest.raises(AttributeError):
        with replay.flag_capture(BAND_RAILS_ENABLED=not prior,
                                 NO_SUCH_FLAG_EVER=True):
            pass
    assert settings.BAND_RAILS_ENABLED is prior


def test_corpus_gate_aliases_the_shared_layer(monkeypatch):
    # The gate and the instruments must load the SAME fixture from the SAME
    # paths — the Task-6 fold moved the implementation down, not copied it.
    assert marks_corpus._FIXTURE_PARQUET == replay.SEALED_FIXTURE_PARQUET
    assert marks_corpus._BASELINE_JSON == replay.SEALED_BASELINE_JSON
    # Delegation pinned BEHAVIORALLY (not by source text): the gate's loader
    # yields whatever the shared loader yields.
    sentinel = ({"XYZ": "frame"}, {"sealed": True})
    monkeypatch.setattr(marks_corpus, "load_sealed_fixture", lambda: sentinel)
    assert marks_corpus._load_fixture() == sentinel


def test_fixture_frame_never_borrows_a_sibling_basis():
    # A digest-graduated setup (no ticker fallback passed) whose keyed frame
    # is missing must surface as MISSING — never silently receive a
    # same-ticker legacy frame (Council review 2026-07-24: wrong-basis grade).
    frames = {"ORMP": "legacy-frame", "ORMP:2026-05-08": "drawn-basis"}
    assert replay.fixture_frame(frames, "ORMP:2026-05-08") == "drawn-basis"
    assert replay.fixture_frame(frames, "ORMP:2026-02-02") is None
    # Legacy setups opt into the bare-ticker fallback explicitly.
    assert replay.fixture_frame(frames, "ORMP:legacy", "ORMP") == "legacy-frame"


# ── The frozen day-snap policy (Council finding 13: it had no coverage) ──


def _raw_frame(n=12):
    import pandas as pd
    idx = pd.bdate_range("2026-03-02", periods=n)
    return pd.DataFrame({"Close": [10.0] * n}, index=idx)


def test_snapped_election_walk(monkeypatch):
    raw = _raw_frame()
    sessions = list(raw.index)
    monkeypatch.setattr(replay, "prepared_frame",
                        lambda r, ts: (r.loc[:ts], 1.0))

    def elect_on(day):
        return lambda df, atr, v: "S" if df.index[-1] == day else None

    # Elects on the requested day -> snapped_k == 0.
    monkeypatch.setattr(replay, "read_structure_under", elect_on(sessions[-1]))
    (df, _atr, reads), ts, k = replay.snapped_election(raw, sessions[-1], [{}])
    assert (ts, k, reads) == (sessions[-1], 0, ["S"])

    # Elects two sessions back -> snapped_k == 2, the read's frame ends there.
    monkeypatch.setattr(replay, "read_structure_under", elect_on(sessions[-3]))
    (df, _atr, reads), ts, k = replay.snapped_election(raw, sessions[-1], [{}])
    assert (ts, k, reads[0]) == (sessions[-3], 2, "S")
    assert df.index[-1] == sessions[-3]

    # Elects only BEYOND the snap window -> the requested-day no-election
    # fallback (snapped_k 0, all-None reads), never a farther silent snap.
    monkeypatch.setattr(replay, "read_structure_under", elect_on(sessions[-8]))
    (df, _atr, reads), ts, k = replay.snapped_election(raw, sessions[-1], [{}])
    assert (ts, k, reads) == (sessions[-1], 0, [None])

    # snap_back=0 grades the requested session ONLY (the negative-mark policy).
    monkeypatch.setattr(replay, "read_structure_under", elect_on(sessions[-2]))
    (df, _atr, reads), ts, k = replay.snapped_election(
        raw, sessions[-1], [{}], snap_back=0)
    assert (ts, k, reads) == (sessions[-1], 0, [None])


def test_snapped_election_none_when_prep_refuses_everywhere(monkeypatch):
    raw = _raw_frame()
    monkeypatch.setattr(replay, "prepared_frame", lambda r, ts: None)
    assert replay.snapped_election(raw, raw.index[-1], [{}]) is None
