"""Calibration frame store — frozen replay frames, digest-bound to marks
(Calibration at Scale, Task 7).

A mark's rails are absolute prices tied to ONE rendering of the data. If the
harness later replays it against the rolled live cache, restatements/splits
silently shift the basis under the saved rails and "rule X matches N/M" moves
with zero engine change. So the frame the operator actually looked at is
FROZEN at fetch time (one parquet per ticker+as-of under
``calibration_frames/``, local data like the cache — never committed), its
digest rides the chart response into the saved mark, and the harness verifies
digest-before-scoring, refusing loudly on any mismatch.

Deliberately pure and root-safe (pandas/stdlib only, no ``config``/``database``
imports): the backend saves frames at chart-fetch time and the tools-side
harness loads them for replay — one implementation, two consumers (EC-3).
"""
from __future__ import annotations

import hashlib
import os

import pandas as pd

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", ".."))
FRAMES_DIR = os.path.join(_REPO_ROOT, "calibration_frames")

_FIELDS = ("Open", "High", "Low", "Close", "Volume")


def ohlcv_digest(frame: pd.DataFrame) -> str:
    """Deterministic sha256 over the bars a mark was drawn on.

    Canonical row serialization (ISO date + repr floats) rather than parquet
    bytes or pandas hashing — those move with library versions; this moves
    only when the DATA does, which is exactly the event it must detect.
    """
    lines = []
    for timestamp, row in frame.iterrows():
        cells = ",".join(repr(float(row[f])) if f in frame.columns else "-"
                         for f in _FIELDS)
        lines.append(f"{timestamp.strftime('%Y-%m-%d')},{cells}")
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def frame_path(ticker: str, as_of: str) -> str:
    # Callers validate ticker against the strict grammar BEFORE it reaches a
    # path (security rule); as_of is strict YYYY-MM-DD.
    return os.path.join(FRAMES_DIR, f"{ticker}_{as_of}.parquet")


def freeze_frame(ticker: str, as_of: str, frame: pd.DataFrame) -> tuple[str, str]:
    """Freeze the (<= as-of) frame a chart rendered; return
    ``(current_digest, stored_digest)``.

    An existing frozen frame is NEVER overwritten (marks already bound to it
    keep their basis). When the vendor has restated since the first freeze the
    two digests differ: the caller stamps the CURRENT digest into the new
    mark (it binds to what the operator is looking at) and surfaces the
    divergence — the harness then grades that mark ``basis_mismatch`` loudly
    instead of silently scoring against bars nobody drew on.
    """
    os.makedirs(FRAMES_DIR, exist_ok=True)
    path = frame_path(ticker, as_of)
    if not os.path.exists(path):
        frame.to_parquet(path)
    return ohlcv_digest(frame), ohlcv_digest(load_frame(ticker, as_of))


def load_frame(ticker: str, as_of: str):
    """The frozen frame for (ticker, as_of), or None if never frozen."""
    path = frame_path(ticker, as_of)
    if not os.path.exists(path):
        return None
    return pd.read_parquet(path)
