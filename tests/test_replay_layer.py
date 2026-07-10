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


def test_corpus_gate_aliases_the_shared_layer():
    # The gate and the instruments must load the SAME fixture from the SAME
    # paths — the Task-6 fold moved the implementation down, not copied it.
    assert marks_corpus._FIXTURE_PARQUET == replay.SEALED_FIXTURE_PARQUET
    assert marks_corpus._BASELINE_JSON == replay.SEALED_BASELINE_JSON
    assert marks_corpus._load_fixture.__module__ == "tools.marks_corpus"
    import inspect
    assert "load_sealed_fixture()" in inspect.getsource(marks_corpus._load_fixture)


def test_resolve_frame_names_its_source(monkeypatch):
    import pandas as pd
    fake = pd.DataFrame({"Close": [1.0]})
    raw, src = replay.resolve_frame("XYZ", sealed={"XYZ": fake})
    assert src == "corpus fixture" and raw is fake

    monkeypatch.setattr(replay, "_LIVE_PANEL",
                        pd.DataFrame(columns=pd.MultiIndex.from_tuples(
                            [("ABC", "Close")])))
    raw, src = replay.resolve_frame("XYZ", sealed={})
    assert raw is None and "not in corpus fixture nor cache" in src
