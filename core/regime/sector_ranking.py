"""SPDR sector ETF relative-strength ranking (Lane C).

Ranks the 11 SPDR sector ETFs (XLK, XLV, XLF, XLY, XLP, XLC, XLI, XLE, XLU, XLRE,
XLB) by their relative strength versus SPY over several trailing horizons (default
21 / 63 / 126 trading days ~ 1 / 3 / 6 months). The per-horizon RS measure is the
ratio momentum:  ``(etf/SPY)_today / (etf/SPY)_{today-N}`` — i.e. how the
sector-vs-market ratio has moved over the window. Sectors leading the market on
multiple horizons surface at the top; this is the sector-rotation context a later
scoring wave can use to favor setups in leading groups.

Pure core (``rank_sectors``) takes an already-fetched ``{symbol: close_series}``
panel and is fully unit-testable offline. ``compute_sector_ranking`` is the thin
fetch wrapper through ``get_provider()``. Both null-safe: a sector with too little
history scores ``None`` on that horizon and is simply unranked there, never
crashing the rank.

Lookahead note: each horizon reads the close ``N`` bars back from the LATEST bar
within the same series — a trailing window, never a future bar.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

import pandas as pd

from core.regime.percentile import percentile_rank
from core.regime.rs_line import rs_line


def _ratio_momentum(ratio: pd.Series, lookback: int) -> Optional[float]:
    """``ratio_today / ratio_{today-lookback}`` - 1, or ``None`` if the series is
    too short to span the window. Guards a zero/negative base."""
    if ratio is None or len(ratio) <= lookback or lookback <= 0:
        return None
    latest = float(ratio.iloc[-1])
    base = float(ratio.iloc[-1 - lookback])
    if base <= 0:
        return None
    return latest / base - 1.0


def rank_sectors(
    panel: Mapping[str, pd.Series],
    *,
    benchmark: str = "SPY",
    lookbacks: Sequence[int] = (21, 63, 126),
) -> dict:
    """Rank the sector ETFs in ``panel`` (a ``{symbol: close_series}`` map that
    MUST include ``benchmark``) by their RS-vs-benchmark momentum.

    Returns ``{'per_horizon': {lookback: {etf: momentum|None}},
    'percentile': {lookback: {etf: pct|None}},
    'composite': {etf: avg_pct|None}, 'ranked': [etf, ...]}`` where ``ranked`` is
    the sector list ordered strongest-first by the composite (None composites
    sort last). Missing benchmark or empty panel -> empty result.
    """
    empty = {"per_horizon": {}, "percentile": {}, "composite": {}, "ranked": []}
    if not panel or benchmark not in panel:
        return empty
    bench_close = panel[benchmark]
    if bench_close is None or len(bench_close) == 0:
        return empty

    etfs = [s for s in panel if s != benchmark]

    per_horizon: dict[int, dict[str, Optional[float]]] = {}
    pct_by_horizon: dict[int, dict[str, Optional[float]]] = {}
    for lb in lookbacks:
        moms: dict[str, Optional[float]] = {}
        for etf in etfs:
            ratio = rs_line(panel[etf], bench_close)
            moms[etf] = _ratio_momentum(ratio, lb) if not ratio.empty else None
        per_horizon[lb] = moms
        pct_by_horizon[lb] = percentile_rank(moms)

    # Composite = mean of the available per-horizon percentiles for each ETF.
    composite: dict[str, Optional[float]] = {}
    for etf in etfs:
        vals = [pct_by_horizon[lb][etf] for lb in lookbacks if pct_by_horizon[lb][etf] is not None]
        composite[etf] = round(sum(vals) / len(vals), 2) if vals else None

    ranked = sorted(
        etfs,
        key=lambda e: (composite[e] is not None, composite[e] if composite[e] is not None else 0.0),
        reverse=True,
    )
    return {
        "per_horizon": per_horizon,
        "percentile": pct_by_horizon,
        "composite": composite,
        "ranked": ranked,
    }


def compute_sector_ranking(
    *,
    etfs: Optional[Sequence[str]] = None,
    benchmark: str = "SPY",
    lookbacks: Optional[Sequence[int]] = None,
    days: int = 400,
    provider=None,
) -> dict:
    """Fetch wrapper: pull the SPDR sector ETFs + benchmark through the provider
    and rank them. ``etfs`` / ``lookbacks`` default lazily to the settings region.
    Any ETF that returns no candles is dropped from the panel (still null-safe in
    the rank). Returns the same shape as ``rank_sectors``.
    """
    if provider is None:
        from core.pipeline.market_data.providers import get_provider

        provider = get_provider()
    if etfs is None or lookbacks is None:
        from config import settings

        if etfs is None:
            etfs = getattr(
                settings, "SECTOR_RANKING_ETFS",
                ("XLK", "XLV", "XLF", "XLY", "XLP", "XLC", "XLI", "XLE", "XLU", "XLRE", "XLB"),
            )
        if lookbacks is None:
            lookbacks = getattr(settings, "SECTOR_RANKING_LOOKBACKS", (21, 63, 126))

    panel: dict[str, pd.Series] = {}
    for symbol in [benchmark, *etfs]:
        frame = provider.daily_candles(symbol, days)
        if frame is not None and not frame.empty and "Close" in frame.columns:
            panel[symbol] = frame["Close"]

    return rank_sectors(panel, benchmark=benchmark, lookbacks=lookbacks)
