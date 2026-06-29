"""Universe percentile-rank utility (Lane C).

IBD-style self-normalizing rank: given one numeric value per ticker across a scan
universe, return each ticker's 0..100 percentile rank within that universe. The
RS rating (and any future "rank this metric across today's scan" need) builds on
this. Pure function — no IO, no settings, deterministic.

Design choices (the traps this guards against):

  * ``None`` / ``NaN`` inputs do NOT participate in the ranking and map to
    ``None`` in the output — they never silently become a 0th-percentile value
    (which would wrongly rank a missing-data ticker as the weakest in the
    universe). The denominator is the count of RANKABLE values only.
  * The rank is the share of OTHER rankable values strictly below, plus half the
    ties (midrank), scaled to 0..100 — so the strongest value is ~100, the
    weakest ~0, and equal values share an identical rank. Midrank ties keep the
    result order-independent (deterministic regardless of input dict ordering).
  * A single rankable value ranks 50.0 (no spread to normalize against).
"""
from __future__ import annotations

import math
from typing import Mapping, Optional


def _is_rankable(v) -> bool:
    if v is None:
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return not (math.isnan(f) or math.isinf(f))


def percentile_rank(
    values: Mapping[str, Optional[float]],
) -> dict[str, Optional[float]]:
    """Map ``{key: value}`` to ``{key: percentile_0_100 | None}``.

    Missing / NaN / inf values rank to ``None`` and are excluded from the
    denominator. Ties share an identical midrank. With ``n`` rankable values the
    result for a value ``x`` is ``100 * (below + 0.5 * equal) / n`` where
    ``below`` / ``equal`` count the rankable values strictly below / equal to
    ``x`` (the value itself included in ``equal``). One rankable value -> 50.0.
    """
    rankable = {k: float(v) for k, v in values.items() if _is_rankable(v)}
    out: dict[str, Optional[float]] = {k: None for k in values}

    n = len(rankable)
    if n == 0:
        return out

    ordered = sorted(rankable.values())
    for key, x in rankable.items():
        # Count strictly-below and equal via the sorted list. This inner pass is
        # O(n) per key -> O(n^2) overall; fine for the current small universes
        # (sector ETFs / today's call site). When wired to the full scan universe
        # (thousands of tickers, Wave 2), swap in np.searchsorted over `ordered`
        # for genuine O(n log n).
        below = sum(1 for v in ordered if v < x)
        equal = sum(1 for v in ordered if v == x)
        out[key] = round(100.0 * (below + 0.5 * equal) / n, 2)
    return out
