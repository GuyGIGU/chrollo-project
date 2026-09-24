"""Calibration frame store guards (Task 7; lifecycle per Council Review
2026-07-11 findings 1/4/5).

The digest is the mark's basis assertion: it must be deterministic for
identical data, move for ANY changed cell (prices AND dates), survive the
parquet round trip byte-for-byte, and cover ONLY the bars a chart renders.
The store must never lose a basis: restatements version, crashes quarantine,
and loads resolve by the mark's own digest.
"""
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import frame_store  # noqa: E402


def _frame(closes=(10.0, 10.5, 10.25),
           dates=("2026-04-13", "2026-04-14", "2026-04-15")):
    idx = pd.to_datetime(list(dates)[:len(closes)])
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


def test_digest_moves_when_only_a_date_moves():
    # A restatement that shifts a bar's DATE with identical prices (split /
    # holiday-repair artifact) must still move the basis.
    a = frame_store.ohlcv_digest(_frame())
    shifted = frame_store.ohlcv_digest(
        _frame(dates=("2026-04-13", "2026-04-14", "2026-04-16")))
    assert shifted != a


def test_digest_missing_column_uses_placeholder():
    frame = _frame().drop(columns=["Volume"])
    d = frame_store.ohlcv_digest(frame)
    assert len(d) == 64
    assert d != frame_store.ohlcv_digest(_frame())  # '-' cell ≠ real volume


def test_digest_and_freeze_cover_only_visible_bars(frames_dir):
    # The chart renders finite rows only; a vendor NaN-row flicker must not
    # read as a restatement (Council finding 5).
    clean = _frame()
    nan_row = pd.DataFrame({"Open": [float("nan")], "High": [10.5],
                            "Low": [9.5], "Close": [10.0],
                            "Volume": [1_000_000.0]},
                           index=pd.to_datetime(["2026-04-10"]))
    with_nan_row = pd.concat([nan_row, clean])
    assert frame_store.ohlcv_digest(frame_store.finite_frame(with_nan_row)) == \
        frame_store.ohlcv_digest(clean)
    current, stored = frame_store.freeze_frame("BODI", "2026-04-15", with_nan_row)
    assert current == stored == frame_store.ohlcv_digest(clean)
    assert len(frame_store.load_frame("BODI", "2026-04-15")) == len(clean)


def test_freeze_round_trips_through_parquet(frames_dir):
    current, stored = frame_store.freeze_frame("BODI", "2026-04-15", _frame())
    assert current == stored  # in-memory digest == parquet round-trip digest
    loaded = frame_store.load_frame("BODI", "2026-04-15")
    assert frame_store.ohlcv_digest(loaded) == stored


def test_restatement_versions_and_both_bases_resolve_by_digest(frames_dir):
    first, _ = frame_store.freeze_frame("BODI", "2026-04-15", _frame())
    restated = _frame(closes=(10.0, 10.5, 10.30))  # vendor restated the last bar
    current, stored = frame_store.freeze_frame("BODI", "2026-04-15", restated)
    assert current != stored and stored == first  # divergence surfaced, base kept
    # A pre-restatement mark (digest = first) and a post-restatement mark
    # (digest = current) BOTH keep a replayable basis (Council finding 1).
    old_basis = frame_store.load_frame("BODI", "2026-04-15", digest=first)
    new_basis = frame_store.load_frame("BODI", "2026-04-15", digest=current)
    assert float(old_basis["Close"].iloc[-1]) == 10.25
    assert float(new_basis["Close"].iloc[-1]) == 10.30
    assert frame_store.load_frame("BODI", "2026-04-15", digest="0" * 64) is None
    # Refreezing the same restatement is idempotent — one sibling, not many.
    frame_store.freeze_frame("BODI", "2026-04-15", restated)
    assert len(list(frames_dir.glob("BODI_2026-04-15*.parquet"))) == 2


def test_torn_base_file_is_quarantined_and_refrozen(frames_dir):
    # A crash mid-write leaves a torn parquet; the exists-check must not
    # protect it forever (Council finding 4).
    torn = frames_dir / "BODI_2026-04-15.parquet"
    torn.write_bytes(b"not a parquet file")
    assert frame_store.load_frame("BODI", "2026-04-15") is None  # pure read
    current, stored = frame_store.freeze_frame("BODI", "2026-04-15", _frame())
    assert current == stored
    assert frame_store.load_frame("BODI", "2026-04-15") is not None
    assert (frames_dir / "BODI_2026-04-15.parquet.corrupt").exists()


def test_freeze_leaves_no_temp_files(frames_dir):
    frame_store.freeze_frame("BODI", "2026-04-15", _frame())
    assert not list(frames_dir.glob("*.tmp-*"))


def test_load_missing_frame_is_none(frames_dir):
    assert frame_store.load_frame("ZZZZ", "2026-01-01") is None
    assert frame_store.load_frame("ZZZZ", "2026-01-01", digest="a" * 64) is None


# ── preview_series (v2 ledger thumbnail feed) ────────────────────────


def test_preview_series_small_frame_keeps_every_bar():
    frame = _frame(closes=(10.0, 10.5, 10.25))
    out = frame_store.preview_series(frame)
    assert out["n"] == 3
    assert [p["c"] for p in out["series"]] == [10.0, 10.5, 10.25]
    assert [p["t"] for p in out["series"]] == ["2026-04-13", "2026-04-14", "2026-04-15"]
    # envelope spans the frame's low..high (High = c+0.5, Low = c-0.5)
    assert out["lo"] == 9.5 and out["hi"] == 11.0


def test_preview_series_downsamples_but_keeps_first_and_last():
    import pandas as pd
    closes = [10.0 + i * 0.1 for i in range(300)]
    dates = pd.bdate_range("2025-01-01", periods=300)
    frame = pd.DataFrame({
        "Open": closes, "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes], "Close": closes,
        "Volume": [1.0] * 300,
    }, index=dates)
    out = frame_store.preview_series(frame, points=48)
    assert out["n"] == 300
    assert len(out["series"]) <= 49  # ~points, never the full 300
    assert out["series"][0]["c"] == closes[0]     # first bar kept -> full-width line
    assert out["series"][-1]["c"] == closes[-1]   # last bar kept -> ends on as-of close
    assert out["lo"] == closes[0] - 1 and out["hi"] == closes[-1] + 1


def test_preview_series_drops_non_finite_and_tolerates_empty():
    import numpy as np
    import pandas as pd
    frame = _frame(closes=(10.0, 10.5, 10.25))
    frame.loc[frame.index[1], "Close"] = np.nan  # a vendor NaN flicker
    out = frame_store.preview_series(frame)
    assert out["n"] == 2  # the NaN row is dropped, like the chart render
    empty = frame_store.preview_series(pd.DataFrame())
    assert empty == {"series": [], "lo": None, "hi": None, "n": 0}


def test_the_root_safe_import_survives_the_domain_move():
    """Tools import this as ``webapp.backend.frame_store`` with only the repo root
    on sys.path. The compatibility alias must not need the backend cwd: it once
    did, and every frame replay died with ``No module named 'domains'``."""
    import subprocess
    code = ("import sys; sys.path[:] = [p for p in sys.path if 'backend' not in p]; "
            "import webapp.backend.frame_store as f, webapp.backend.marks_validity as m; "
            "assert callable(f.ohlcv_digest) and callable(m.validate_mark)")
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
