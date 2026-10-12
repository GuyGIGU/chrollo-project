"""Quarterly sales as first filed with the SEC: the year-ago quarters yfinance drops.

yfinance keeps five or six quarters of the income statement, so year-on-year sales
growth can be read for one or two of the last four quarters only (each needs the
same quarter a year earlier). The SEC's XBRL "company facts" (data.sec.gov, free)
hold every quarter a US filer has reported, each fact stamped with the day it was
FILED -- a genuine point-in-time record: a value is used only when it was filed on
or before the scan day, and of several filings of one period the FIRST is kept
(as reported then, never a later restatement).

Off unless ``SEC_CONTACT`` is set: the SEC's fair-access policy refuses requests
without a contact in the User-Agent header (tested 12/10/2026: 403 Forbidden), and
naming one is the operator's call. Foreign filers (20-F / 6-K) carry no quarterly
XBRL facts and get nothing here. Every miss degrades to ``None``, never a raise.

Fourth quarters are usually filed only inside the annual report (10-K), as the
whole year; the quarter is the year minus its first three quarters when all three
are on file.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Optional

import pandas as pd

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
#: The revenue concepts companies file under, the commonest first.
REVENUE_CONCEPTS = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                    "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax")
_QUARTER_DAYS = (80, 100)
_YEAR_DAYS = (350, 380)
_TIMEOUT_S = 20
_PAUSE_S = 0.15            # well under the SEC's ten requests a second
_TICKER_MAP_MAX_AGE_S = 7 * 24 * 3600


def _get_json(url: str, contact: str) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": contact, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as response:
            data = json.load(response)
        time.sleep(_PAUSE_S)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def ticker_ciks(contact: str, cache_path: str) -> dict:
    """``{TICKER: cik}``, from the SEC's ticker list, kept on disk for a week."""
    try:
        if time.time() - os.path.getmtime(cache_path) < _TICKER_MAP_MAX_AGE_S:
            with open(cache_path, encoding="utf-8") as fh:
                cached = json.load(fh)
            if isinstance(cached, dict) and cached:
                return cached
    except (OSError, json.JSONDecodeError):
        pass
    data = _get_json(TICKERS_URL, contact)
    if not data:
        return {}
    ciks = {str(row.get("ticker", "")).upper(): int(row["cik_str"])
            for row in data.values() if isinstance(row, dict) and "cik_str" in row}
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(ciks, fh)
    except OSError:
        pass
    return ciks


def _first_filed(facts: list, as_of: pd.Timestamp) -> dict:
    """``{(start, end): value}`` of the facts filed on or before ``as_of``, each
    period at its FIRST filing."""
    best: dict = {}
    for fact in facts:
        try:
            start, end = pd.Timestamp(fact["start"]), pd.Timestamp(fact["end"])
            filed, value = pd.Timestamp(fact["filed"]), float(fact["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if filed > as_of:
            continue
        key = (start, end)
        if key not in best or filed < best[key][0]:
            best[key] = (filed, value)
    return {key: value for key, (_, value) in best.items()}


def quarterly_sales(facts: Optional[dict], as_of) -> dict:
    """``{period end ISO: sales}`` for every quarter on file by ``as_of``. The
    first concept that holds a period wins it; fourth quarters are derived from the
    year when the three quarters before it are on file."""
    if not facts:
        return {}
    gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    cutoff = pd.Timestamp(as_of).normalize()
    out: dict = {}
    for concept in REVENUE_CONCEPTS:
        units = ((gaap.get(concept) or {}).get("units") or {}).get("USD") or []
        periods = _first_filed(units, cutoff)
        quarters = {k: v for k, v in periods.items() if _QUARTER_DAYS[0] <= (k[1] - k[0]).days <= _QUARTER_DAYS[1]}
        for (start, end), value in quarters.items():
            out.setdefault(str(end.date()), value)
        for (start, end), value in periods.items():
            if not _YEAR_DAYS[0] <= (end - start).days <= _YEAR_DAYS[1] or str(end.date()) in out:
                continue
            inside = [v for (s, e), v in quarters.items() if s >= start - pd.Timedelta(days=7) and e < end - pd.Timedelta(days=30)]
            if len(inside) == 3:
                out[str(end.date())] = value - sum(inside)
    return dict(sorted(out.items()))


def sales_for(ticker: str, as_of, contact: str, cache_dir: str) -> Optional[dict]:
    """The ticker's quarterly sales as first filed by ``as_of``, or None (no
    contact, not a US filer, or the SEC unreachable)."""
    if not contact:
        return None
    cik = ticker_ciks(contact, os.path.join(cache_dir, "sec_tickers.json")).get(ticker.upper())
    if cik is None:
        return None
    sales = quarterly_sales(_get_json(FACTS_URL.format(cik=cik), contact), as_of)
    return sales or None
