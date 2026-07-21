"""Forward-inclusive grading frame — the Trigger replay basis (Task 2).

Unit tests for frame_store.freeze_grading_frame / load_grading_frame against a
tmp FRAMES_DIR. No network, no booted app: the forward basis a Trigger grade
replays (sessions AFTER as-of) is captured and verified here in isolation, kept
distinct from the mark's <= as-of frame_digest basis.
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


def _full_frame(rows):
    idx = pd.to_datetime([d for d, _ in rows])
    vals = [c for _, c in rows]
    return pd.DataFrame({"Open": vals, "High": [v + 1 for v in vals],
                         "Low": [v - 1 for v in vals], "Close": vals,
                         "Volume": [1_000_000.0] * len(vals)}, index=idx)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    return tmp_path


def test_grading_frame_round_trips_and_le_slice_reproduces_base_digest(store):
    as_of = "2025-09-10"
    full = _full_frame([("2025-09-08", 100.0), ("2025-09-09", 101.0),
                        ("2025-09-10", 102.0),                       # as-of
                        ("2025-09-11", 103.0), ("2025-09-12", 104.0)])  # forward
    base = full[full.index <= pd.Timestamp(as_of)]
    base_digest, _ = frame_store.freeze_frame("KLAC", as_of, base)

    frame_store.freeze_grading_frame("KLAC", as_of, full, base_digest)
    loaded = frame_store.load_grading_frame("KLAC", as_of, base_digest)

    assert loaded is not None
    # It carries the forward bars the deadline comparison needs...
    assert loaded.index.max() == pd.Timestamp("2025-09-12")
    # ...and its <= as-of slice reproduces the base frame's digest exactly, so the
    # engine sees the identical <= as-of bars whether from base or grading frame.
    le = loaded[loaded.index <= pd.Timestamp(as_of)]
    assert frame_store.ohlcv_digest(le) == base_digest


def test_load_grading_frame_is_none_for_unknown_or_missing_digest(store):
    assert frame_store.load_grading_frame("KLAC", "2025-09-10", "deadbeef" * 8) is None
    assert frame_store.load_grading_frame("KLAC", "2025-09-10", "") is None


def test_load_grading_frame_rejects_a_digest_mismatch(store):
    # A grading file whose <= as-of slice does not reproduce the addressed digest
    # is treated as unbound — never silently graded on the wrong bars.
    as_of = "2025-09-10"
    full = _full_frame([("2025-09-09", 101.0), ("2025-09-10", 102.0),
                        ("2025-09-11", 103.0)])
    base = full[full.index <= pd.Timestamp(as_of)]
    base_digest, _ = frame_store.freeze_frame("KLAC", as_of, base)
    frame_store.freeze_grading_frame("KLAC", as_of, full, base_digest)

    # Ask for a DIFFERENT digest than the one the file is addressed by.
    other = frame_store.ohlcv_digest(_full_frame([("2025-09-10", 500.0)]))
    assert frame_store.load_grading_frame("KLAC", as_of, other) is None


def test_freeze_grading_frame_is_idempotent_never_overwrites(store):
    as_of = "2025-09-10"
    full = _full_frame([("2025-09-09", 101.0), ("2025-09-10", 102.0),
                        ("2025-09-11", 103.0)])
    base = full[full.index <= pd.Timestamp(as_of)]
    base_digest, _ = frame_store.freeze_frame("KLAC", as_of, base)
    frame_store.freeze_grading_frame("KLAC", as_of, full, base_digest)

    # A second capture with a DIFFERENT forward tail (same base, same digest/path)
    # must not overwrite the first — the point-in-time forward basis is immutable.
    tampered = _full_frame([("2025-09-09", 101.0), ("2025-09-10", 102.0),
                            ("2025-09-11", 999.0)])
    frame_store.freeze_grading_frame("KLAC", as_of, tampered, base_digest)
    loaded = frame_store.load_grading_frame("KLAC", as_of, base_digest)
    assert loaded.loc[pd.Timestamp("2025-09-11"), "Close"] == 103.0
