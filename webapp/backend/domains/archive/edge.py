"""Read-only engine-edge summary for the Home command-center pulse.

Wraps the pure ``core.backtest.edge_report`` over the read-only archive load
(``core.backtest.loader`` opens the DB ``mode=ro`` — the production archive cannot
be mutated here). The headline is BIAS-SAFE by construction: it is computed on the
``screener`` basis and the seed/manual hand-picked-winner rows are excluded and
flagged, never averaged in. The per-tier slices are likewise computed on the
unbiased basis only.

ONE reader at a time (his word Mon 12/10/2026, option A): the headline and the tiers
measure the reader that wrote the latest scan, and the other reader's fires ride
under them as one baseline line, never pooled. The two readers' letters are
different verdicts, and the new reader's rows leave the old engine's measurement
columns empty, so a pooled tile would read neither.

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

from core.archive.calibration_outcomes import load_calibration_setups
from core.backtest.edge_report import UNBIASED_SOURCE, edge_block, headline_edge, slice_by
from core.backtest.loader import load_episodes_by_reader
from core.pipeline.universe import default_universe

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


def _tail_view(block: dict) -> dict:
    """Project a tail_rates block, coercing every rate through the finite guard."""
    tail = block.get("tail", {}) or {}
    return {
        "n": int(tail.get("n", 0)),
        "col": tail.get("col"),
        "bands": [
            {"threshold": _finite(b.get("threshold")), "rate": _finite(b.get("rate"))}
            for b in (tail.get("bands") or [])
        ],
    }


def _tier_view(block: dict) -> dict:
    """Project an edge_block down to the few fields the pulse tile renders."""
    barrier = block.get("barrier", {}) or {}
    return {
        "n": int(block.get("n", 0)),
        "mfe_median": _finite(block.get("headline_mfe_median")),
        "mfe_n": int(block.get("headline_mfe_n", 0)),
        "win_rate": _finite(barrier.get("win_rate")),
        "n_labelled": int(barrier.get("n_labelled", 0)),
        # The win rate is conditional on resolution and the resolution rate is
        # itself tier-dependent (62% for S, 16% for C) — it ships alongside so the
        # tile can never show one without the other.
        "resolution_rate": _finite(barrier.get("resolution_rate")),
        "tail": _tail_view(block),
    }


def _empty() -> dict:
    return {
        "reader": None,
        "reader_since": None,
        "baseline": None,
        "unbiased": True,
        "contaminated_input": False,
        "n_unbiased": 0,
        "headline_mfe_col": "mfe_to_date",
        "headline_mfe_median": None,
        "headline_mfe_n": 0,
        "abnormal_median": None,
        "tail": {"n": 0, "col": None, "bands": []},
        "by_tier": {},
        "calibration": None,
    }


def _calibration_view():
    """His calibration setups as their own group beside the fires (operator ruling
    2026-10-03: archived setups too), never pooled into the headline or a tier.
    None when there are none."""
    df = load_calibration_setups()
    return _tier_view(edge_block(df)) if not df.empty else None


def _scan_days(df):
    """The first and last scan day of a reader's fires on the unbiased basis."""
    if "source" in df.columns:
        df = df[df["source"] == UNBIASED_SOURCE]
    days = df["scan_date"].dropna().astype(str) if "scan_date" in df.columns else []
    return (min(days), max(days)) if len(days) else (None, None)


def _last_written(df):
    """A reader's latest unbiased fire as (scan day, row id), or None. The id
    breaks a tie of days: on the flip, both readers wrote rows for the same scan
    day (Fri 09/10/2026), and the reader that wrote last is the one running."""
    if "source" in df.columns:
        df = df[df["source"] == UNBIASED_SOURCE]
    if df.empty or "scan_date" not in df.columns:
        return None
    return str(df["scan_date"].max()), int(df["id"].max()) if "id" in df.columns else 0


def _current_and_baseline(by_reader: dict):
    """The reader that wrote the latest scan is the one the tile measures; the
    other is its baseline, one line, never pooled (his word Mon 12/10/2026,
    option A). Recency, not a name: switched back, the old engine is current."""
    last = {name: _last_written(df) for name, df in by_reader.items()}
    read = [name for name in last if last[name] is not None]
    if not read:
        return None, None
    current = max(read, key=lambda name: last[name])
    others = [name for name in read if name != current]
    return current, (others[0] if others else None)


def _baseline_view(df, reader: str) -> dict:
    """The other reader's fires as one line: the same figures as a tier, its name
    and the scan days it covers."""
    basis = df[df["source"] == UNBIASED_SOURCE] if "source" in df.columns else df
    first, last = _scan_days(df)
    return {**_tier_view(edge_block(basis)), "reader": reader, "first_scan": first, "last_scan": last}


def _compute() -> dict:
    try:
        # Stock universe only: the edge tile measures the US-equities screener, and
        # the ETF universes now archive under the same source='screener'. Pin the
        # universe_type via the descriptor (single source for the key<->universe_type
        # duality) so their setups stay out of this population.
        by_reader = load_episodes_by_reader(universe_type=default_universe().universe_type)
    except FileNotFoundError:
        return _empty()
    reader, baseline = _current_and_baseline(by_reader)
    if reader is None:
        return _empty()
    df_all = by_reader[reader]

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
        "reader": reader,
        "reader_since": _scan_days(df_all)[0],
        "baseline": None if baseline is None else _baseline_view(by_reader[baseline], baseline),
        "unbiased": bool(headline.get("unbiased", True)),
        "contaminated_input": bool(headline.get("contaminated_input", False)),
        "n_unbiased": int(headline.get("n_unbiased", 0)),
        "headline_mfe_col": headline.get("headline_mfe_col", "mfe_to_date"),
        "headline_mfe_median": _finite(headline.get("headline_mfe_median")),
        "headline_mfe_n": int(headline.get("headline_mfe_n", 0)),
        "abnormal_median": _finite(abnormal.get("median")),
        "tail": _tail_view(headline),
        "by_tier": by_tier,
        "calibration": _calibration_view(),
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
