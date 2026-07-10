"""Calibration frame store guards (Calibration at Scale, Task 7).

The digest is the mark's basis assertion: it must be deterministic for
identical data, move for ANY changed cell, and survive the parquet round trip
byte-for-byte — otherwise save-time and verify-time digests of the same frame
disagree and every mark grades basis_mismatch vacuously.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import frame_store  # noqa: E402


def _frame(closes=(10.0, 10.5, 10.25)):
    idx = pd.to_datetime(["2026-04-13", "2026-04-14", "2026-04-15"][:len(closes)])
    closes = list(closes)
    return pd.DataFrame({
        "Open": closes, "High": [c + 0.5 for c in closes],
        "Low": [c - 0.5 for c in closes], "Close": closes,
        "Volume": [1_000_000.0] * len(closes),
    }, index=idx)


@pytest.fixture()
def frames_dir(tmp_path, monkeypatch):
    # The file is importable under two names (bare from the backend cwd,
    # webapp.backend.frame_store from tools) — two module INSTANCES with
    # separate globals. Patch both so writes and reads meet in tmp_path.
    import webapp.backend.frame_store as wb_frame_store
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(wb_frame_store, "FRAMES_DIR", str(tmp_path))
    return tmp_path


def test_digest_is_deterministic_and_data_sensitive():
    a, b = frame_store.ohlcv_digest(_frame()), frame_store.ohlcv_digest(_frame())
    assert a == b and len(a) == 64
    changed = _frame()
    changed.iloc[1, changed.columns.get_loc("Close")] = 10.51  # one cell, one tick
    assert frame_store.ohlcv_digest(changed) != a


def test_freeze_round_trips_through_parquet(frames_dir):
    current, stored = frame_store.freeze_frame("BODI", "2026-04-15", _frame())
    assert current == stored  # in-memory digest == parquet round-trip digest
    loaded = frame_store.load_frame("BODI", "2026-04-15")
    assert frame_store.ohlcv_digest(loaded) == stored


def test_freeze_never_overwrites_and_surfaces_divergence(frames_dir):
    frame_store.freeze_frame("BODI", "2026-04-15", _frame())
    restated = _frame(closes=(10.0, 10.5, 10.30))  # vendor restated the last bar
    current, stored = frame_store.freeze_frame("BODI", "2026-04-15", restated)
    assert current != stored  # divergence surfaced, first freeze preserved
    kept = frame_store.load_frame("BODI", "2026-04-15")
    assert float(kept["Close"].iloc[-1]) == 10.25


def test_load_missing_frame_is_none(frames_dir):
    assert frame_store.load_frame("ZZZZ", "2026-01-01") is None


def test_replay_layer_prefers_the_calibration_frame(frames_dir):
    from tools import replay
    frame_store.freeze_frame("BODI", "2026-04-15", _frame())
    raw, src = replay.resolve_frame("BODI", sealed={}, as_of="2026-04-15")
    assert src == "calibration frame"
    assert frame_store.ohlcv_digest(raw) == frame_store.ohlcv_digest(_frame())
