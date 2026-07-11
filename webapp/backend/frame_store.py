"""Calibration frame store — frozen replay frames, digest-bound to marks
(Calibration at Scale, Task 7; lifecycle hardened per Council Review
2026-07-11 findings 1/4/5).

A mark's rails are absolute prices tied to ONE rendering of the data. If the
harness later replays it against the rolled live cache, restatements/splits
silently shift the basis under the saved rails and "rule X matches N/M" moves
with zero engine change. So the frame the operator actually looked at is
FROZEN at fetch time (parquet files per ticker+as-of under
``calibration_frames/``), its digest rides the chart response into the saved
mark, and the harness verifies digest-before-scoring, refusing loudly on any
mismatch.

Lifecycle rules (each one is a review scar, not a nicety):

* **Visible bars only.** Rows with any non-finite O/H/L/C are dropped ONCE,
  before both freeze and digest — the chart renders only finite rows, so the
  digest must move only when VISIBLE data moves. A vendor NaN-row flicker is
  not a restatement.
* **Restatements are versioned, never lost.** The first freeze claims the
  base file and is never overwritten; when the vendor restates, the current
  rendering is frozen under a digest-qualified sibling. Every mark replays
  against the frame matching ITS OWN digest — old and new marks both keep a
  basis.
* **Writes are atomic** (temp + rename). A crash mid-freeze cannot leave a
  torn file posing as the frozen truth; an unreadable base found at freeze
  time is quarantined (``.corrupt``) and refrozen, never trusted. Loads stay
  pure reads — the harness never mutates the store.

NOTE: ``calibration_frames/`` is NOT a regenerable cache — once marks bind to
digests, deleting it destroys the replay basis of the whole calibration
corpus. Back it up with the same habit that covers the journal DB.

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
_PRICE_FIELDS = ("Open", "High", "Low", "Close")


def finite_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Only the bars a chart actually renders: drop rows with any non-finite
    O/H/L/C (the chart is shaped with require_finite=True)."""
    cols = [c for c in _PRICE_FIELDS if c in frame.columns]
    if not cols:
        return frame
    finite = frame[cols].apply(pd.to_numeric, errors="coerce")
    return frame[finite.notna().all(axis=1) & (finite.abs() != float("inf")).all(axis=1)]


def ohlcv_digest(frame: pd.DataFrame) -> str:
    """Deterministic sha256 over the bars a mark was drawn on.

    Canonical row serialization (ISO date + repr floats) rather than parquet
    bytes or pandas hashing — those move with library versions; this moves
    only when the DATA does, which is exactly the event it must detect.
    Callers pass the finite (visible) frame.
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


def _versioned_path(ticker: str, as_of: str, digest: str) -> str:
    return os.path.join(FRAMES_DIR, f"{ticker}_{as_of}.{digest[:12]}.parquet")


def _atomic_write(frame: pd.DataFrame, path: str) -> None:
    tmp = f"{path}.tmp-{os.getpid()}"
    frame.to_parquet(tmp)
    os.replace(tmp, path)


def _read_frame(path: str):
    """Pure read: None for missing OR unreadable (repair is freeze's job)."""
    if not os.path.exists(path):
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def freeze_frame(ticker: str, as_of: str, frame: pd.DataFrame) -> tuple[str, str]:
    """Freeze the visible (<= as-of) frame a chart rendered; return
    ``(current_digest, stored_digest)``.

    Equal digests: this rendering IS the frozen basis. Different digests:
    the vendor restated since the first freeze — the current rendering has
    been frozen under a digest-qualified sibling, so marks made on either
    rendering stay replayable (``load_frame`` resolves by digest).
    """
    os.makedirs(FRAMES_DIR, exist_ok=True)
    visible = finite_frame(frame)
    current = ohlcv_digest(visible)
    base = frame_path(ticker, as_of)
    stored_frame = _read_frame(base)
    if stored_frame is None:
        if os.path.exists(base):
            # Torn write from a crash — quarantine, never trust, refreeze.
            os.replace(base, f"{base}.corrupt")
        _atomic_write(visible, base)
        return current, current
    stored = ohlcv_digest(stored_frame)
    if current != stored:
        versioned = _versioned_path(ticker, as_of, current)
        if not os.path.exists(versioned):
            _atomic_write(visible, versioned)
    return current, stored


def load_frame(ticker: str, as_of: str, digest: str | None = None):
    """The frozen frame for (ticker, as_of), or None if never frozen.

    With a mark's ``digest``: whichever frozen version matches it — the base
    freeze first, then the digest-qualified sibling a restatement created.
    None means no frozen frame carries that basis (the mark grades
    basis_mismatch; it is never silently replayed on other bars).
    """
    base = _read_frame(frame_path(ticker, as_of))
    if digest is None:
        return base
    if base is not None and ohlcv_digest(base) == digest:
        return base
    versioned = _read_frame(_versioned_path(ticker, as_of, digest))
    if versioned is not None and ohlcv_digest(versioned) == digest:
        return versioned
    return None
