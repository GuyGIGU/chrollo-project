"""Read-only engine-edge summary for the Home command-center pulse.

Wraps the pure ``core.backtest.edge_report`` over the read-only archive load
(``core.backtest.loader`` opens the DB ``mode=ro`` — the production archive cannot
be mutated here). The headline is BIAS-SAFE by construction: it is computed on the
``screener`` basis and the seed/manual hand-picked-winner rows are excluded and
flagged, never averaged in. The per-tier slices are likewise computed on the
unbiased basis only.

Cached with a short TTL so the index route does not re-read the whole archive on
every Home load. The TTL (vs. a scan-cadence signature) is the deliberately lean
choice for a single-user local app: it also picks up overnight forward-return
maturation within one TTL window, which a ``(max_id, row_count)`` signature would
miss because forward returns update in place.
"""
from __future__ import annotations

import math
import threading
import time

from core.backtest.edge_report import UNBIASED_SOURCE, headline_edge, slice_by
from core.backtest.loader import load_episodes

_TTL_SECONDS = 300.0
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "value": None}


def _finite(x):
    """Coerce to a finite float, or None — NaN/inf must never reach the JSON layer."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    return xf if math.isfinite(xf) else None


def _tier_view(block: dict) -> dict:
    """Project an edge_block down to the few fields the pulse tile renders."""
    barrier = block.get("barrier", {}) or {}
    return {
        "n": int(block.get("n", 0)),
        "mfe_median": _finite(block.get("headline_mfe_median")),
        "mfe_n": int(block.get("headline_mfe_n", 0)),
        "win_rate": _finite(barrier.get("win_rate")),
        "n_labelled": int(barrier.get("n_labelled", 0)),
    }


def _empty() -> dict:
    return {
        "unbiased": True,
        "contaminated_input": False,
        "n_unbiased": 0,
        "headline_mfe_col": "mfe_to_date",
        "headline_mfe_median": None,
        "headline_mfe_n": 0,
        "abnormal_median": None,
        "by_tier": {},
    }


def _compute() -> dict:
    try:
        df_all = load_episodes()  # all sources, read-only, collapsed to episodes
    except FileNotFoundError:
        return _empty()
    if df_all is None or getattr(df_all, "empty", True):
        return _empty()

    # Headline is bias-safe by construction: filters to the screener basis and
    # flags contamination if any seed/manual rows were present in the input.
    headline = headline_edge(df_all, source_basis=UNBIASED_SOURCE)

    # Per-tier slices on the UNBIASED basis ONLY — never the seed/manual gallery.
    if "source" in df_all.columns:
        df_basis = df_all[df_all["source"] == UNBIASED_SOURCE]
    else:
        df_basis = df_all
    by_tier = {tier: _tier_view(block) for tier, block in slice_by(df_basis, "tier").items()}

    abnormal = headline.get("abnormal") or {}
    return {
        "unbiased": bool(headline.get("unbiased", True)),
        "contaminated_input": bool(headline.get("contaminated_input", False)),
        "n_unbiased": int(headline.get("n_unbiased", 0)),
        "headline_mfe_col": headline.get("headline_mfe_col", "mfe_to_date"),
        "headline_mfe_median": _finite(headline.get("headline_mfe_median")),
        "headline_mfe_n": int(headline.get("headline_mfe_n", 0)),
        "abnormal_median": _finite(abnormal.get("median")),
        "by_tier": by_tier,
    }


def engine_edge(force: bool = False) -> dict:
    """Return the cached engine-edge summary, recomputing past the TTL."""
    now = time.monotonic()
    with _lock:
        cached = _cache["value"]
        if not force and cached is not None and (now - _cache["at"]) < _TTL_SECONDS:
            return cached
    value = _compute()  # compute outside the lock — a rare cold double-compute is harmless
    with _lock:
        _cache["value"] = value
        _cache["at"] = time.monotonic()
    return value
