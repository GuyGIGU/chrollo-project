"""Universe-level ADVISORY context for one scan (Lane E wiring).

Two null-safe helpers the screener calls ONCE per run, after the per-ticker
evaluation pass:

  * ``attach_rs_ratings`` — the in-house RS rating, LIVE and display-only
    (operator go-ahead 2026-10-02, the leadership read). Each firing setup gets
    ``_rs_rating``: the percentile (0..100) of its twelve-month strength among
    EVERY stock the scan read that has a year of history and trades at or above
    the entry filter's price floor. Twelve-month strength is IBD-style: four
    quarter returns, the latest counted double. Leadership is only meaningful
    RELATIVE to the market, so it cannot be computed per-ticker. A fire with
    under a year of history gets no rating (never a penalty).

  * ``compute_scan_sector_ranking`` — ranks the SPDR sector ETFs once per scan
    (``core.regime.sector_ranking``) and returns a ``{etf: composite_pct}`` map
    plus the ordered ``ranked`` list, so each setup can be tagged with its
    sector's relative strength. Gated under ``SECTOR_RANKING_ENABLED``, a no-op
    returning ``{}`` while the flag is off.

ADVISORY CONTRACT: metadata only — never gates a setup, never changes Score/Tier.
Settings read lazily.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence


def _flag(name: str, default=False):
    try:
        from config import settings

        return getattr(settings, name, default)
    except Exception:  # pragma: no cover - settings import guard
        return default


def year_strength(df) -> Optional[float]:
    """IBD-style twelve-month strength of one daily frame: the four quarter
    returns ending at its last close, the latest counted double. A year is
    ``RS_RATING_LOOKBACK`` trading days, a quarter a fourth of it. ``None``
    when the frame holds less than a year plus one day."""
    from core.fundamentals.advisory import _trailing_return

    quarter = int(_flag("RS_RATING_LOOKBACK", 252) or 252) // 4
    returns = [_trailing_return(df.iloc[:len(df) - quarter * k], quarter)
               for k in range(4)]
    if any(r is None for r in returns):
        return None
    return 2.0 * returns[0] + sum(returns[1:])


def attach_rs_ratings(results: Sequence[dict],
                      ticker_frames: Mapping[str, object]) -> None:
    """Write ``_rs_rating`` onto each firing result IN PLACE.

    The rank population is every frame in ``ticker_frames`` (the whole scan
    universe, not the firing set) with a year of history and a last close at or
    above ``MIN_PRICE``. A result whose ticker is not in that population gets no
    key — absent means "not rated", never a low rating."""
    if not results:
        return
    from core.regime.percentile import percentile_rank

    min_price = float(_flag("MIN_PRICE", 3.0) or 0.0)
    strength = {}
    for ticker, df in ticker_frames.items():
        # A frame with no readable close is left out (no rating), never raised.
        if df is None or "Close" not in getattr(df, "columns", ()) or len(df) == 0:
            continue
        if float(df["Close"].iloc[-1]) < min_price:
            continue
        value = year_strength(df)
        if value is not None:
            strength[ticker] = value
    ranks = percentile_rank(strength)
    for r in results:
        rank = ranks.get(r.get("Ticker"))
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
