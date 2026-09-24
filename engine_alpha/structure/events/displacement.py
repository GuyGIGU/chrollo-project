"""The displacement seam — "a structure resolved; what may the engine read next."

Story-chain program Task 5 (PLAN task sequence; docs/story_chain_program_2026-08.md).
A DISPLACEMENT is a structure's resolution: a close beyond the ceiling
(breakout up) or a violent break under the floor (shakeout down). This module
owns the shared arithmetic BOTH chains and the species lane consume — the
resolved-structure question already had one calibrated, RULED implementation
(the Power-Play breakout wall with the 1.0×ATR10 departure yardstick, ruled
2026-08-18), so the chain consumes it BY EXTRACTION from the one owning
arithmetic, never a re-typed twin (EC-3/EC-18; strangler-fig — extracted
exactly as consumed, no speculative generality).

The as-of contract every consumer carries (EC-45; the census/first_legal_look
lessons, 2026-08-17/20):

* **The yardstick is the base's volatility, never the crossing bar's own** —
  ``atr10_before`` is shifted one bar so an explosive resolution bar cannot
  raise (or lower) its own wall.
* **Reference levels are RUNNING extremes as of the read bar** — a shakeout
  low deepens while the recovery is in progress; ``running_argmin`` /
  ``running_argmax`` give the per-bar prefix extreme so a walk reads what it
  could actually SEE. Consumers honor the edge-skip reserve (read the prefix
  at ``p - skip``, the ``first_legal_look`` discipline) — these primitives
  hand them the prefix state, they do not absolve them of the reserve.
* **NaN fails closed** — a NaN lift (frame head) compares False, so a cross
  is never declared on an unusable yardstick (unresolved, not resolved).

Pure measurement: indices in, indices out. No settings reads, no elections,
no scoring.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "atr10_before",
    "first_close_beyond",
    "first_close_below",
    "running_argmax",
    "running_argmin",
]


def atr10_before(highs, lows, closes) -> np.ndarray:
    """ATR10 shifted one bar — the departure-yardstick basis at each bar's
    CROSSING, computed over the ten bars before it (extracted verbatim from
    the species wall; the shift is the whole point)."""
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    tr = np.maximum(highs - lows,
                    np.maximum(np.abs(highs - prev), np.abs(lows - prev)))
    return pd.Series(tr).rolling(10).mean().shift(1).to_numpy()


def first_close_beyond(closes, level, start, lift=None):
    """The first position ``>= start`` whose close prints ABOVE
    ``level + lift`` — the resolution-up form (the species breakout wall;
    Chain A's parent breakout). ``lift`` is a per-bar array aligned to
    ``closes`` (or None for the bare level); a NaN lift compares False and
    fails closed. Returns None while unresolved."""
    closes = np.asarray(closes, dtype=float)
    if start >= len(closes):
        return None
    tail = closes[start:]
    if lift is not None:
        after = np.flatnonzero(tail > level + np.asarray(lift, dtype=float)[start:])
    else:
        after = np.flatnonzero(tail > level)
    return int(start + after[0]) if len(after) else None


def first_close_below(closes, level, start, lift=None):
    """The mirror: the first position ``>= start`` whose close prints BELOW
    ``level - lift`` — the resolution-down form (Chain B's violent break
    under the floor). Same NaN-fails-closed law."""
    closes = np.asarray(closes, dtype=float)
    if start >= len(closes):
        return None
    tail = closes[start:]
    if lift is not None:
        after = np.flatnonzero(tail < level - np.asarray(lift, dtype=float)[start:])
    else:
        after = np.flatnonzero(tail < level)
    return int(start + after[0]) if len(after) else None


def running_argmin(values) -> np.ndarray:
    """Per-bar prefix argmin: ``out[k]`` = the index of the lowest value in
    ``values[:k+1]`` — the running extreme a walk standing at bar k could
    see. Ties keep the EARLIEST index (a later equal low never moves the
    anchor), deterministically."""
    values = np.asarray(values, dtype=float)
    out = np.empty(len(values), dtype=int)
    best, best_i = np.inf, 0
    for k in range(len(values)):
        if values[k] < best:
            best, best_i = values[k], k
        out[k] = best_i
    return out


def running_argmax(values) -> np.ndarray:
    """The mirror prefix argmax (recovery highs, run peaks). Earliest-tie,
    same law."""
    values = np.asarray(values, dtype=float)
    out = np.empty(len(values), dtype=int)
    best, best_i = -np.inf, 0
    for k in range(len(values)):
        if values[k] > best:
            best, best_i = values[k], k
        out[k] = best_i
    return out
