"""The industry per ticker and the group facts: display only (his yes, Fri 23/10/2026).

The industry is the vendor's word on the fundamentals sheet (``sheet.snapshot``),
so every fired name that carries a sheet already names its group. What the
screen never said is the GROUP: how many of it fired tonight, how many in the
last 10 trading days, and how big it is. Those are resolved here, engine-side,
so the browser only prints them (conventions EC-28): no sort, no gate, no grade.

Measured first (2026-10-23, 5,949 archived episodes): "how many of the group
fired" pays nothing in the tail, and "the group already at its highs" is mostly
the stock's daily range. The counts are shown because the picture was missing,
not because they pay (decisions.md, 2026-10-23).

The industry cache (``output/industry_cache.json``, ticker -> sector / industry /
as_of) is filled from the sheets night by night and by the backfill tool
(``tools.maintenance.industry_backfill``) for the rest of the scanned universe,
so the group's size counts the universe, not only the names that fired.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from typing import Iterable, Optional

from core.archive.db_path import archive_db_path

CACHE_BASENAME = "industry_cache.json"
#: The archive rows the 10-day count reads: the screener's own fires (seed and
#: manual rows are a hand-picked gallery, never a night's picture).
FIRE_SOURCE = "screener"


def cache_path() -> str:
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    return os.path.join(root, "output", CACHE_BASENAME)


def load_cache(path: str) -> dict:
    """ticker -> {"sector", "industry", "as_of"}; an unreadable file reads as empty (regenerable)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def save_cache(cache: dict, path: str) -> None:
    """Best-effort; a failed write only costs tomorrow's count."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        pass


def industry_of_sheet(sheet) -> Optional[str]:
    """The vendor's industry on a fundamentals sheet, None when the sheet has none."""
    if not isinstance(sheet, dict):
        return None
    snapshot = sheet.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    return snapshot.get("industry") or None


def remember(cache: dict, ticker: str, sheet, as_of: str) -> None:
    """Write a sheet's industry into the cache; a sheet without one writes nothing."""
    industry = industry_of_sheet(sheet)
    if industry is None:
        return
    cache[ticker] = {"sector": sheet["snapshot"].get("sector"), "industry": industry, "as_of": as_of}


def remember_name(cache: dict, ticker: str, industry: Optional[str], as_of: str) -> None:
    """Write an industry known by name alone (an archived sheet's word) when the
    cache has no industry for the ticker; a fuller entry is never overwritten."""
    if industry and not industry_of(cache, ticker):
        cache[ticker] = {"sector": None, "industry": industry, "as_of": as_of}


def industry_of(cache: dict, ticker: str) -> Optional[str]:
    entry = cache.get(ticker)
    return entry.get("industry") if isinstance(entry, dict) else None


def members_of(universe: Iterable[str], cache: dict) -> dict:
    """industry -> how many of the scanned universe the cache places in it."""
    counts: Counter = Counter()
    for ticker in universe:
        industry = industry_of(cache, ticker)
        if industry:
            counts[industry] += 1
    return dict(counts)


def group_counts(tonight: dict, recent: dict, members: dict) -> dict:
    """industry -> {"fired_tonight", "fired_10d", "members"}.

    ``tonight`` and ``recent`` map ticker -> industry (None when unknown); a
    name is counted once however many nights it fired. The group's size is at
    least the names seen firing, so a group the cache has not counted yet never
    reads as "3 of 1".
    """
    by_industry: dict = {}
    for ticker, industry in tonight.items():
        if industry:
            by_industry.setdefault(industry, [set(), set()])[0].add(ticker)
    for ticker, industry in {**recent, **tonight}.items():
        if industry:
            by_industry.setdefault(industry, [set(), set()])[1].add(ticker)
    return {
        industry: {"fired_tonight": len(night), "fired_10d": len(window),
                   "members": max(int(members.get(industry, 0)), len(window))}
        for industry, (night, window) in by_industry.items()
    }


def recent_fires(since: str, before: str, universe_type: str, db_path: Optional[str] = None) -> dict:
    """ticker -> the industry its archived sheet names (None when the row has
    none) for the screener's fires with ``since <= scan_date < before``. Read-only;
    a missing archive or table reads as nothing fired."""
    path = db_path or archive_db_path()
    if not os.path.exists(path):
        return {}
    uri = f"file:{path.replace(os.sep, '/')}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        try:
            rows = con.execute(
                "SELECT ticker, fund_sheet_json FROM setup_archive "
                "WHERE scan_date >= ? AND scan_date < ? AND source = ? AND universe_type = ? "
                "ORDER BY scan_date",
                (since, before, FIRE_SOURCE, universe_type)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return {}
    out: dict = {}
    for ticker, sheet_json in rows:
        industry = None
        if sheet_json:
            try:
                industry = industry_of_sheet(json.loads(sheet_json))
            except (TypeError, ValueError):
                industry = None
        # the latest night with a sheet wins; a night without one never erases it
        if industry or ticker not in out:
            out[ticker] = industry
    return out
