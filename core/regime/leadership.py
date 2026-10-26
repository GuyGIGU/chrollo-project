"""Leading groups and leading sectors: display only (his ask, Mon 26/10/2026).

Minervini's money is made on the market leader and its top competitors: the
strongest stocks of the strongest groups. Three facts answer it for any name the
scan read, all from the one RS rating the scan already computes
(``scan_context.attach_rs_ratings``: the percentile of twelve-month strength
among every stock read):

- a GROUP's strength = the median RS rating of its stocks (the vendor's
  industry, from the industry cache), ranked among the groups;
- a SECTOR's strength = the same median over the sector's stocks, ranked among
  the sectors;
- a stock's PLACE = its rank by RS inside its own group (1 = the group's leader).

``leading`` marks the top quarter of a ranking. A group or sector with fewer
than three rated stocks is not ranked. Resolved here so the browser only prints
it (EC-28): it never changes a fire, Score or Tier, and gates nothing.
"""
from __future__ import annotations

import math
from statistics import median

#: The share of a ranking marked as leading (11 sectors -> 3, 143 groups -> 36).
LEADING_SHARE = 0.25
#: The fewest rated stocks a group or sector needs to be ranked.
MIN_MEMBERS = 3


def _rank(members: dict) -> dict:
    """name -> {rank, of, rs, members, leading}, strongest first; ties by name."""
    strength = {name: median(values) for name, values in members.items() if len(values) >= MIN_MEMBERS}
    order = sorted(strength, key=lambda name: (-strength[name], name))
    cut = math.ceil(len(order) * LEADING_SHARE)
    return {name: {"rank": i + 1, "of": len(order), "rs": round(strength[name], 1),
                   "members": len(members[name]), "leading": i < cut}
            for i, name in enumerate(order)}


def read_leadership(ratings: dict, cache: dict) -> dict:
    """The sector, group and place facts for every rated stock the cache names.

    ``ratings`` = ticker -> RS rating (0-100); ``cache`` = the industry cache
    (ticker -> {"sector", "industry"}). Returns ``{"sectors", "groups",
    "stocks"}`` (each group carries its sector; each stock its group, RS, and
    place in the group), or ``{}`` when nothing could be grouped.
    """
    by_group: dict = {}
    by_sector: dict = {}
    sector_of: dict = {}
    for ticker, rs in ratings.items():
        entry = cache.get(ticker)
        if not isinstance(entry, dict) or rs is None:
            continue
        industry, sector = entry.get("industry") or None, entry.get("sector") or None
        if industry:
            by_group.setdefault(industry, []).append((rs, ticker))
            if sector:
                sector_of.setdefault(industry, sector)
        if sector:
            by_sector.setdefault(sector, []).append(rs)
    groups = _rank({name: [rs for rs, _ in rows] for name, rows in by_group.items()})
    if not groups:
        return {}
    for name, facts in groups.items():
        facts["sector"] = sector_of.get(name)
    stocks = {}
    for name in groups:
        rows = sorted(by_group[name], key=lambda row: (-row[0], row[1]))
        for place, (rs, ticker) in enumerate(rows, start=1):
            stocks[ticker] = {"group": name, "rs": round(rs, 1), "place": place, "of": len(rows)}
    return {"sectors": _rank(by_sector), "groups": groups, "stocks": stocks}
