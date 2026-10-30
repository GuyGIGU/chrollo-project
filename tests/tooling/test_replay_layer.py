"""Shared replay layer guards (Calibration at Scale, Task 6).

The layer's safety properties, pinned: the flag capture ALWAYS restores (a
leaked flag mid-batch poisons every later measurement), unknown flags are
refused loudly, and the corpus gate's fixture names still resolve to the one
shared implementation (the fold is real, not a copy).
"""
import sys
from pathlib import Path

import pytest

from _paths import BASELINES_DIR, REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from tools.regression import marks_corpus
from core.calibration import replay


def test_flag_capture_restores_on_success_and_crash():
    prior = settings.ADR_WINDOW
    with replay.flag_capture(ADR_WINDOW=prior + 1):
        assert settings.ADR_WINDOW == prior + 1
    assert settings.ADR_WINDOW == prior

    with pytest.raises(RuntimeError):
        with replay.flag_capture(ADR_WINDOW=prior + 1):
            raise RuntimeError("mid-capture crash")
    assert settings.ADR_WINDOW == prior


def test_flag_capture_refuses_unknown_flags():
    with pytest.raises(AttributeError):
        with replay.flag_capture(NO_SUCH_FLAG_EVER=True):
            pass


def test_flag_capture_multi_flag_typo_flips_nothing():
    # A typo in the SECOND name must not leave the first flag set with the
    # restoring finally never entered (Council finding 7): validate all
    # names before touching any flag.
    prior = settings.ADR_WINDOW
    with pytest.raises(AttributeError):
        with replay.flag_capture(ADR_WINDOW=prior + 1,
                                 NO_SUCH_FLAG_EVER=True):
            pass
    assert settings.ADR_WINDOW == prior


def test_the_sealed_fixture_paths_are_the_committed_baselines():
    # The layer finds the repo root on its own; a root one folder off would
    # point every fixture consumer at files that do not exist.
    assert Path(replay.BASELINE_DIR).resolve() == BASELINES_DIR
    assert Path(replay.SEALED_FIXTURE_PARQUET).resolve() == BASELINES_DIR / "marks_corpus.parquet"
    assert Path(replay.SEALED_BASELINE_JSON).resolve() == BASELINES_DIR / "marks_corpus_baseline.json"


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
