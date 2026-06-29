"""Universe-level ADVISORY context for one scan (Lane E wiring).

Two flag-gated, null-safe helpers the screener calls ONCE per run, after the
per-ticker evaluation pass:

  * ``attach_rs_ratings`` — turns each firing setup's trailing return
    (``_rs_trailing_return``, emitted by ``core.fundamentals.advisory``) into a
    universe-relative ``_rs_rating`` percentile (0..100) via
    ``core.regime.percentile``. This is the in-house RS rating: leadership is
    only meaningful RELATIVE to the rest of the scan, so it cannot be computed
    per-ticker. Gated under ``FUNDAMENTALS_ENABLED`` (it feeds the fundamentals
    chip set). Missing trailing return -> no rating (never a penalty).

  * ``compute_scan_sector_ranking`` — ranks the SPDR sector ETFs once per scan
    (``core.regime.sector_ranking``) and returns a ``{etf: composite_pct}`` map
    plus the ordered ``ranked`` list, so each setup can be tagged with its
    sector's relative strength. Gated under ``SECTOR_RANKING_ENABLED``.

ADVISORY CONTRACT: metadata only — never gates a setup, never changes Score/Tier.
Both helpers are no-ops (return input unchanged / ``{}``) when their flag is OFF,
so flags-OFF output is byte-identical (shadow guard). Flags read lazily.
"""
from __future__ import annotations

from typing import Optional, Sequence


def _flag(name: str, default=False):
    try:
        from config import settings

        return getattr(settings, name, default)
    except Exception:  # pragma: no cover - settings import guard
        return default


def attach_rs_ratings(results: Sequence[dict]) -> None:
    """Compute the universe RS-rating percentile across ``results`` IN PLACE.

    Reads each result's ``_rs_trailing_return`` (set by the per-ticker advisory
    layer) and writes ``_rs_rating`` = its percentile rank (0..100) within the
    firing set. No-op when ``FUNDAMENTALS_ENABLED`` is OFF or no result carries a
    trailing return. A result without a trailing return simply gets no rating."""
    if not _flag("FUNDAMENTALS_ENABLED"):
        return
    if not results:
        return
    from core.regime.percentile import percentile_rank

    by_ticker = {}
    for r in results:
        tr = r.get("_rs_trailing_return")
        if tr is not None:
            by_ticker[id(r)] = tr
    if not by_ticker:
        return
    ranks = percentile_rank(by_ticker)
    for r in results:
        rank = ranks.get(id(r))
        if rank is not None:
            r["_rs_rating"] = rank


def compute_scan_sector_ranking(*, provider=None) -> dict:
    """Rank the SPDR sector ETFs once for this scan.

    Returns ``{'composite': {etf: pct|None}, 'ranked': [etf, ...]}`` (the subset
    the chip layer needs), or ``{}`` when ``SECTOR_RANKING_ENABLED`` is OFF or the
    rank could not be built. Null-safe — any vendor miss degrades to ``{}``."""
    if not _flag("SECTOR_RANKING_ENABLED"):
        return {}
    try:
        from core.regime.sector_ranking import compute_sector_ranking

        ranking = compute_sector_ranking(provider=provider)
    except Exception:
        return {}
    if not ranking or not ranking.get("ranked"):
        return {}
    return {"composite": ranking.get("composite", {}), "ranked": ranking.get("ranked", [])}


def sector_rank_fields(sector_etf: Optional[str], sector_ranking: dict) -> dict:
    """Per-setup sector-rank advisory fields from the scan-wide ranking.

    Given a setup's resolved SPDR ``sector_etf`` and the scan ``sector_ranking``
    (from ``compute_scan_sector_ranking``), returns
    ``{'_sector_rank_pct': float, '_sector_rank_pos': int}`` when the ETF is in the
    ranking, else ``{}`` (missing -> no chip, never a penalty)."""
    if not sector_etf or not sector_ranking:
        return {}
    composite = sector_ranking.get("composite") or {}
    ranked = sector_ranking.get("ranked") or []
    out: dict = {}
    pct = composite.get(sector_etf)
    if pct is not None:
        out["_sector_rank_pct"] = float(pct)
    if sector_etf in ranked:
        out["_sector_rank_pos"] = int(ranked.index(sector_etf)) + 1  # 1-based, strongest=1
    return out
