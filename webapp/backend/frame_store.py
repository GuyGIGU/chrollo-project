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
import uuid

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


_PREVIEW_POINTS = 48  # downsample target for the ledger frame thumbnail


def preview_series(frame: pd.DataFrame, points: int = _PREVIEW_POINTS) -> dict:
    """Downsample a frozen frame to a small close line + price envelope for the
    ledger thumbnail — the review's "precompute a downsampled series, never a
    per-row read on render" feed (v2 Add-2). Pure: no I/O, no engine, over the
    VISIBLE (finite) bars only, so it moves only when the drawn data moves.

    Returns ``{series: [{t, c}], lo, hi, n}``: a close path (each point dated so
    the operator's box maps to x by session, not by calendar guesswork) plus the
    frame's low/high envelope (the y-range the client expands to include the
    drawn rails). Bucketed by position — the first and last bars are always
    kept, so the line spans the full width and ends on the as-of close.
    """
    visible = finite_frame(frame)
    n = int(len(visible))
    if n == 0 or "Close" not in visible.columns:
        return {"series": [], "lo": None, "hi": None, "n": 0}
    closes = visible["Close"].astype(float)
    highs = visible["High"].astype(float) if "High" in visible.columns else closes
    lows = visible["Low"].astype(float) if "Low" in visible.columns else closes
    if n <= points:
        idxs = range(n)
    else:
        # last row of each positional bucket, plus the first bar (full-width line)
        idxs = sorted({0} | {min(int((i + 1) * n / points) - 1, n - 1)
                             for i in range(points)})
    series = [{"t": visible.index[i].strftime("%Y-%m-%d"),
               "c": float(closes.iloc[i])} for i in idxs]
    return {"series": series, "lo": float(lows.min()), "hi": float(highs.max()),
            "n": n}


def frame_path(ticker: str, as_of: str) -> str:
    # Callers validate ticker against the strict grammar BEFORE it reaches a
    # path (security rule); as_of is strict YYYY-MM-DD.
    return os.path.join(FRAMES_DIR, f"{ticker}_{as_of}.parquet")


def _versioned_path(ticker: str, as_of: str, digest: str) -> str:
    return os.path.join(FRAMES_DIR, f"{ticker}_{as_of}.{digest[:12]}.parquet")


def _atomic_write(frame: pd.DataFrame, path: str) -> None:
    # Per-write unique temp: the /chart freeze runs in FastAPI's sync-def
    # threadpool (many threads, one PID), so a PID-only temp name would let two
    # concurrent same-target freezes stage to and rename the SAME file. A uuid
    # suffix gives every writer its own temp before the atomic rename.
    tmp = f"{path}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
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


# ── Forward-inclusive grading frame (Trigger replay basis) ───────────
#
# A Trigger (the operator's buy) sits AFTER as-of, so grading "did the engine
# fire at/before the buy?" must replay sessions in ``(as_of, trigger_date]`` —
# and to do so frozen-only (no vendor fetch, no lookahead) it needs those
# forward bars persisted. This is a SEPARATE basis from the ``<= as_of`` frame:
# the mark's ``frame_digest`` still binds to what the operator LOOKED AT (the
# ``<= as_of`` frame, unchanged above), while the grading frame is the same
# rendering extended through ``frame_end``, addressed by that base digest so the
# two always pair. Its ``<= as_of`` slice reproduces the base digest by
# construction (finite-filtering is per-row, so slicing and filtering commute),
# which ``load_grading_frame`` verifies — a mismatch is treated as unbound, never
# silently graded on the wrong bars.


def _grading_path(ticker: str, as_of: str, base_digest: str) -> str:
    return os.path.join(FRAMES_DIR, f"{ticker}_{as_of}.{base_digest[:12]}.grade.parquet")


def freeze_grading_frame(ticker: str, as_of: str, full_frame: pd.DataFrame,
                         base_digest: str) -> None:
    """Freeze the forward-inclusive (``<= frame_end``) finite frame for a mark's
    basis, addressed by its ``<= as_of`` ``base_digest``.

    Idempotent: the first capture is the honest point-in-time forward basis and
    is never overwritten (a later vendor restatement of the forward bars must
    not move the ground a saved Trigger was graded on). ``full_frame`` is the
    whole fetched window (``<= frame_end``); only its finite (visible) bars are
    stored, so the ``<= as_of`` slice matches the base frozen frame exactly.
    """
    if not base_digest:
        return
    os.makedirs(FRAMES_DIR, exist_ok=True)
    path = _grading_path(ticker, as_of, base_digest)
    if os.path.exists(path):
        return
    _atomic_write(finite_frame(full_frame), path)


def load_grading_frame(ticker: str, as_of: str, base_digest: str):
    """The forward-inclusive frozen frame for ``(ticker, as_of, base_digest)``,
    or None if never frozen or its ``<= as_of`` slice does not reproduce
    ``base_digest`` (a corrupt / mismatched forward basis is never graded on).

    The grader replays the whole ``[frame_start, trigger_date]`` window from this
    one file: its ``<= as_of`` portion IS the base frame, and the bars after
    as-of are the frozen forward context the deadline comparison needs.
    """
    if not base_digest:
        return None
    frame = _read_frame(_grading_path(ticker, as_of, base_digest))
    if frame is None:
        return None
    le = frame[frame.index <= pd.Timestamp(as_of)]
    if ohlcv_digest(le) != base_digest:
        return None
    return frame
