"""The fundamentals sheet: is the business improving, quarter after quarter?

Operator, Mon 12/10/2026: *"the last four quarters of EPS and sales growth, margin
trends, earnings beats/misses, estimate revisions, the growth catalyst, and any
earnings-quality concerns. That would show whether the business is improving -- not
just whether its latest quarter looks impressive."* This module builds that sheet
from the frames the provider already serves; it fetches nothing itself, so every
piece is a pure function of its inputs (``core.fundamentals.post_pass`` fetches).

Where each line comes from:

  * **EPS, beats and misses** -- the earnings-history frame (``get_earnings_dates``):
    each report's reported EPS against the estimate, dated by the REPORT day, about
    twenty reports deep, so all four year-on-year growths can be read (each report
    against the one four reports earlier). This is the adjusted EPS the estimates
    are made for, not the income statement's diluted EPS.
  * **Sales and margins** -- the quarterly income statement (five or six quarters).
    A quarter becomes visible on the day it was REPORTED (the first earnings report
    after its period end), or, when no report day matches, after the filing lag
    (``FUNDAMENTALS_FILING_LAG_DAYS``). Year-on-year sales need the same quarter a
    year earlier; when the statement no longer holds it, the SEC filings fill it
    (``core.fundamentals.sec``, US filers only, when ``SEC_CONTACT`` is set).
  * **Earnings quality** -- the quarterly cash-flow statement: operating cash flow
    against net income over the shown quarters, and stock-based pay against sales.
  * **Estimate revisions** -- the analysts' estimate trend as it stands on the scan
    night (a current snapshot, so the night's own fact; it has no history behind it).
  * **The catalyst** -- what is new in the business is reading, not data: it stays
    his read. What can be measured is its proof: sales speeding up, estimates going
    up, and the market's verdict on report day (``reactions``: the move and the
    volume of the trading day that first traded on each report).

Every number is null-safe (missing data -> ``None``, never an exception) and the
sheet is JSON-ready: dates as ISO text, growths and margins as signed fractions.
"""
from __future__ import annotations

import math
import re
from typing import Optional

import pandas as pd

from core.fundamentals.metrics import _filing_lag_days, _finite, _naive_index, _signed_growth

_REVENUE_ROWS = ("Total Revenue", "Operating Revenue")
_GROSS_ROWS = ("Gross Profit",)
_OPERATING_ROWS = ("Operating Income",)
_NET_ROWS = ("Net Income", "Net Income Common Stockholders")
_CASH_ROWS = ("Operating Cash Flow",)
_SBC_ROWS = ("Stock Based Compensation",)
_GAAP_EPS_ROWS = ("Diluted EPS",)
_UNUSUAL_ROWS = ("Total Unusual Items",)
_SHARES_ROWS = ("Diluted Average Shares",)
_ACQUISITION_ROWS = ("Purchase Of Business", "Net Business Purchase And Sale")
#: A full stop after these is not the end of a sentence ("Snowflake Inc. provides ...").
_ABBREVIATIONS = {"inc", "co", "corp", "ltd", "llc", "plc", "lp", "n.v", "s.a", "u.s", "ag", "se", "nv",
                  "sa", "bv", "no", "st", "dr", "jr", "sr", "vs", "e.g", "i.e", "etc", "holdings", "hldgs"}
LOSS_TO_PROFIT, LOSS_NARROWED, LOSS_WIDENED = "loss → profit", "loss narrowed", "loss widened"
#: A quarter's report lands within this many days of its period end (10-K deadline plus margin).
_REPORT_WINDOW_DAYS = 120
#: A report announced before noon (US/Eastern) trades the same day; later, the next trading day.
_BEFORE_OPEN_HOUR = 12
#: The same quarter a year earlier sits this close to 365 days back.
_YEAR_SLACK_DAYS = 20


def _round(value, digits=4) -> Optional[float]:
    f = _finite(value)
    return None if f is None else round(f, digits)


def _row(frame, labels) -> Optional[pd.Series]:
    """One line item as a Series indexed by naive period-end Timestamp, oldest first."""
    if frame is None or getattr(frame, "empty", True):
        return None
    for label in labels:
        if label in frame.index:
            series = frame.loc[label].copy()
            series.index = _naive_index(series.index)
            series = series[series.index.notna()]
            return series.sort_index()
    return None


def _cell(series: Optional[pd.Series], day) -> Optional[float]:
    if series is None or day not in series.index:
        return None
    return _finite(series[day])


def _knob(name: str):
    from config import settings

    return getattr(settings, name)


def eps_change(now, year_ago) -> tuple:
    """``(growth, words)``: the growth on the year as a signed fraction, or, when the
    year-ago figure was a loss (or zero), no percentage at all but the words -- a
    percentage off a loss misleads ("loss -> profit", "loss narrowed", "loss widened")."""
    n, b = _finite(now), _finite(year_ago)
    if n is None or b is None:
        return None, None
    if b > 0:
        return _signed_growth(n, b), None
    if n > 0:
        return None, LOSS_TO_PROFIT
    return None, LOSS_NARROWED if n > b else LOSS_WIDENED


def trend(values: list) -> Optional[str]:
    """``accelerating`` / ``slowing`` / ``mixed`` over the last three values, all
    known; None with fewer (never guessed from two)."""
    tail = list(values)[-3:]
    if len(tail) < 3 or any(v is None for v in tail):
        return None
    if tail[0] < tail[1] < tail[2]:
        return "accelerating"
    if tail[0] > tail[1] > tail[2]:
        return "slowing"
    return "mixed"


# ---------------------------------------------------------------- EPS reports
def reports(earnings: pd.DataFrame, as_of) -> list[dict]:
    """Every report with a reported EPS on or before ``as_of``, OLDEST first:
    ``{"day", "before_open", "eps", "estimate", "surprise"}``. Two rows for one
    day (the vendor sometimes repeats a report) keep the one that has a number."""
    if earnings is None or getattr(earnings, "empty", True) or "Reported EPS" not in earnings.columns:
        return []
    raw = pd.to_datetime(earnings.index, errors="coerce", utc=True)
    eastern = raw.tz_convert("America/New_York")
    cutoff = pd.Timestamp(as_of).normalize()
    out: dict = {}
    for i, stamp in enumerate(eastern):
        if pd.isna(stamp):
            continue
        eps = _finite(earnings["Reported EPS"].iloc[i])
        day = pd.Timestamp(stamp.date())
        if eps is None or day > cutoff:
            continue
        estimate = _finite(earnings["EPS Estimate"].iloc[i]) if "EPS Estimate" in earnings.columns else None
        surprise = _finite(earnings["Surprise(%)"].iloc[i]) if "Surprise(%)" in earnings.columns else None
        surprise = surprise / 100.0 if surprise is not None else _signed_growth(eps, estimate)
        out[day] = {"day": day, "before_open": stamp.hour < _BEFORE_OPEN_HOUR, "eps": eps,
                    "estimate": estimate, "surprise": surprise}
    return [out[day] for day in sorted(out)]


def eps_lines(all_reports: list[dict], n: int) -> list[dict]:
    """The last ``n`` reports, each with its EPS growth against the report four
    earlier (the same quarter a year before), oldest first."""
    lines = []
    for i in range(max(0, len(all_reports) - n), len(all_reports)):
        r = all_reports[i]
        year_ago = all_reports[i - 4]["eps"] if i >= 4 else None
        growth, words = eps_change(r["eps"], year_ago)
        lines.append({"day": str(r["day"].date()), "eps": _round(r["eps"]), "estimate": _round(r["estimate"]),
                      "surprise": _round(r["surprise"]), "yoy": _round(growth), "turn": words})
    return lines


# ---------------------------------------------------------------- quarters
def visible_day(period_end: pd.Timestamp, report_days: list) -> pd.Timestamp:
    """The day a quarter became public: its earnings report (the first report
    within the report window after its period end), else the filing lag."""
    for day in report_days:
        if period_end < day <= period_end + pd.Timedelta(days=_REPORT_WINDOW_DAYS):
            return day
    return period_end + pd.Timedelta(days=_filing_lag_days(None))


def _year_ago(series: Optional[pd.Series], end: pd.Timestamp) -> Optional[float]:
    if series is None:
        return None
    for day, value in series.items():
        if abs((end - day).days - 365) <= _YEAR_SLACK_DAYS:
            return _finite(value)
    return None


def _sec_year_ago(sec_sales: Optional[dict], end: pd.Timestamp) -> Optional[float]:
    if not sec_sales:
        return None
    for iso, value in sec_sales.items():
        if abs((end - pd.Timestamp(iso)).days - 365) <= _YEAR_SLACK_DAYS:
            return _finite(value)
    return None


def _margin(part, sales) -> Optional[float]:
    p, s = _finite(part), _finite(sales)
    return None if p is None or s is None or s == 0 else p / s


def quarter_lines(stmt: pd.DataFrame, report_days: list, as_of, n: int,
                  sec_sales: Optional[dict] = None) -> tuple[list[dict], list]:
    """The last ``n`` quarters public on ``as_of``, oldest first, and the period
    ends of every visible quarter (the cash-flow lines read the same ones)."""
    sales = _row(stmt, _REVENUE_ROWS)
    if sales is None:
        return [], []
    gross, operating, net = _row(stmt, _GROSS_ROWS), _row(stmt, _OPERATING_ROWS), _row(stmt, _NET_ROWS)
    gaap = _row(stmt, _GAAP_EPS_ROWS)
    cutoff = pd.Timestamp(as_of).normalize()
    visible = [end for end in sales.index
               if _finite(sales[end]) is not None and visible_day(end, report_days) <= cutoff]
    lines = []
    for i, end in enumerate(visible):
        if i < len(visible) - n:
            continue
        value = _finite(sales[end])
        yahoo_year_ago = _year_ago(sales[sales.index.isin(visible)], end)
        sec_year_ago = None if yahoo_year_ago is not None else _sec_year_ago(sec_sales, end)
        year_ago = yahoo_year_ago if yahoo_year_ago is not None else sec_year_ago
        before = _finite(sales[visible[i - 1]]) if i >= 1 else None
        op_year_ago = _year_ago(operating, end)
        gaap_growth, gaap_words = eps_change(_cell(gaap, end), _year_ago(gaap, end))
        lines.append({
            "end": str(end.date()),
            "sales": _round(value, 0),
            "sales_yoy": _round(_signed_growth(value, year_ago)),
            "sales_yoy_source": None if year_ago is None else ("yahoo" if yahoo_year_ago is not None else "sec"),
            "sales_qoq": _round(_signed_growth(value, before)) if before is not None else None,
            "gross_margin": _round(_margin(_cell(gross, end), value)),
            "operating_margin": _round(_margin(_cell(operating, end), value)),
            "operating_margin_year_ago": _round(_margin(op_year_ago, _year_ago(sales, end))),
            "net_margin": _round(_margin(_cell(net, end), value)),
            "eps_gaap": _round(_cell(gaap, end)),
            "eps_gaap_yoy": _round(gaap_growth),
            "eps_gaap_turn": gaap_words,
        })
    return lines, visible


# ---------------------------------------------------------------- quality
def quality(stmt: pd.DataFrame, cashflow: pd.DataFrame, visible: list, n: int) -> dict:
    """Operating cash flow against net income, and stock-based pay against sales,
    summed over the last ``n`` visible quarters both statements hold."""
    ends = visible[-n:]
    cash, sbc = _row(cashflow, _CASH_ROWS), _row(cashflow, _SBC_ROWS)
    net, sales = _row(stmt, _NET_ROWS), _row(stmt, _REVENUE_ROWS)

    def total(series):
        values = [_cell(series, end) for end in ends]
        return sum(values) if ends and all(v is not None for v in values) else None

    cash_total, net_total, sbc_total, sales_total = total(cash), total(net), total(sbc), total(sales)
    sbc_share = None if sbc_total is None or not sales_total else sbc_total / sales_total
    flags, known = [], False
    if cash_total is not None and net_total is not None:
        known = True
        if net_total > 0 and cash_total < net_total:
            flags.append("profits not backed by cash")
    if sbc_share is not None:
        known = True
        if sbc_share > _knob("FUND_GRADE_SBC_MAX"):
            flags.append(f"stock pay {sbc_share * 100:.0f}% of sales")
    if ends:
        latest = ends[-1]
        unusual, latest_net = _cell(_row(stmt, _UNUSUAL_ROWS), latest), _cell(net, latest)
        if unusual is not None and latest_net is not None:
            known = True
            if latest_net > 0 and abs(unusual) >= _knob("FUND_FLAG_UNUSUAL_SHARE") * latest_net:
                flags.append(f"one-time items {abs(unusual) / latest_net * 100:.0f}% of the latest net income")
        shares = _row(stmt, _SHARES_ROWS)
        now, before = _cell(shares, latest), _year_ago(shares, latest)
        if now is not None and before:
            known = True
            drop = 1.0 - now / before
            if drop >= _knob("FUND_FLAG_SHARE_DROP"):
                flags.append(f"share count down {drop * 100:.0f}% on the year (buybacks lift EPS)")
        bought = total(_row(cashflow, _ACQUISITION_ROWS))
        if bought is not None and sales_total:
            known = True
            if -bought >= _knob("FUND_FLAG_ACQUISITION_SHARE") * sales_total:
                flags.append(f"acquisitions {-bought / sales_total * 100:.0f}% of sales")
    return {
        "quarters": len(ends),
        "operating_cash_flow": _round(cash_total, 0),
        "net_income": _round(net_total, 0),
        "sbc_share_of_sales": _round(sbc_share),
        "flags": flags,
        "flags_known": known,
    }


# ---------------------------------------------------------------- revisions
def revisions(analysis: Optional[dict]) -> dict:
    """This year's and next year's EPS estimate now against 90 days ago, and the
    analysts raising against cutting this year's over 30 days."""
    trend = (analysis or {}).get("eps_trend")
    moves = (analysis or {}).get("eps_revisions")

    def at(frame, row, col):
        try:
            return _finite(frame.loc[row, col])
        except (AttributeError, KeyError, TypeError):
            return None

    now, before = at(trend, "0y", "current"), at(trend, "0y", "90daysAgo")
    up, down = at(moves, "0y", "upLast30days"), at(moves, "0y", "downLast30days")
    return {
        "this_year_eps": _round(now),
        "this_year_eps_90d_ago": _round(before),
        "this_year_change_90d": _round(_signed_growth(now, before)),
        "next_year_change_90d": _round(_signed_growth(at(trend, "+1y", "current"), at(trend, "+1y", "90daysAgo"))),
        "up_30d": None if up is None else int(up),
        "down_30d": None if down is None else int(down),
    }


# ---------------------------------------------------------------- reactions
def reactions(frame: Optional[pd.DataFrame], all_reports: list[dict], n: int) -> list[dict]:
    """The market's verdict on each of the last ``n`` reports: the first trading
    day that traded on it (the next day for a report after the close), its close
    against the close before, that move in daily ranges (the 20-day ADR before it,
    the yardstick his charts are measured in), and its volume against the 50-day
    average before it."""
    if frame is None or len(frame) < 60 or not {"High", "Low", "Close", "Volume"} <= set(frame.columns):
        return []
    frame = frame.sort_index()
    days = frame.index
    high, low, close, volume = (frame[c].to_numpy(float) for c in ("High", "Low", "Close", "Volume"))
    out = []
    for r in all_reports[-n:]:
        side = "left" if r["before_open"] else "right"
        i = int(days.searchsorted(r["day"], side=side))
        if i < 50 or i >= len(days):
            continue
        change = close[i] / close[i - 1] - 1.0
        adr = float(pd.Series(high[i - 20:i] / low[i - 20:i] - 1.0).mean())
        avg_volume = float(pd.Series(volume[i - 50:i]).mean())
        out.append({
            "report_day": str(r["day"].date()),
            "day": str(days[i].date()),
            "change": _round(change),
            "ranges": _round(change / adr if adr > 0 and math.isfinite(adr) else None, 2),
            "volume_ratio": _round(volume[i] / avg_volume if avg_volume > 0 else None, 2),
        })
    return out


# ---------------------------------------------------------------- the sheet
def filed_part(stmt, earnings, cashflow, as_of, *, n: int, sec_sales: Optional[dict] = None) -> dict:
    """The part of the sheet that changes only when a new report lands (cacheable
    until the next one): EPS lines, quarters, earnings quality, the report days."""
    all_reports = reports(earnings, as_of)
    report_days = [r["day"] for r in all_reports]
    lines, visible = quarter_lines(stmt, report_days, as_of, n, sec_sales)
    return {
        "eps": eps_lines(all_reports, n),
        "quarters": lines,
        "quality": quality(stmt, cashflow, visible, n),
        "reports": [{"day": str(r["day"].date()), "before_open": bool(r["before_open"])} for r in all_reports[-n:]],
    }


def snapshot(info: Optional[dict]) -> dict:
    """The company in one sentence: its name, sector, industry, and the first
    sentence of the vendor's business summary (no judgment added)."""
    info = info or {}
    summary = str(info.get("longBusinessSummary") or "").strip()
    first = summary
    for stop in re.finditer(r"\.\s+(?=[A-Z])", summary):
        word = summary[:stop.start()].split()[-1].lower().strip(".,")
        if word not in _ABBREVIATIONS and len(word) > 1:
            first = summary[:stop.start() + 1]
            break
    first = first.strip()
    if first and not first.endswith("."):
        first += "."
    if len(first) > 220:
        first = first[:217].rstrip() + "…"
    return {"name": info.get("longName") or info.get("shortName"), "sector": info.get("sector"),
            "industry": info.get("industry"), "summary": first or None}


def next_earnings(info: Optional[dict], as_of) -> Optional[dict]:
    """The next report day and whether the company has CONFIRMED it (``False``: the
    vendor's estimate; ``None``: not said). None when no future day is known."""
    info = info or {}
    stamp = _finite(info.get("earningsTimestampStart") or info.get("earningsTimestamp"))
    if stamp is None:
        return None
    day = pd.Timestamp(stamp, unit="s", tz="UTC").tz_convert("America/New_York").normalize().tz_localize(None)
    if day < pd.Timestamp(as_of).normalize():
        return None
    estimate = info.get("isEarningsDateEstimate")
    return {"day": str(day.date()), "confirmed": None if estimate is None else not bool(estimate)}


def trends(filed: dict) -> dict:
    """Is growth speeding up, steady or slowing: EPS and sales on the year, sales on
    the quarter, and the operating margin, each over its last three quarters."""
    quarters = filed.get("quarters", [])
    margin = trend([q.get("operating_margin") for q in quarters])
    return {
        "eps": trend([e.get("yoy") for e in filed.get("eps", [])]),
        "sales": trend([q.get("sales_yoy") for q in quarters]),
        "sales_qoq": trend([q.get("sales_qoq") for q in quarters]),
        "margin": {"accelerating": "expanding", "slowing": "shrinking"}.get(margin, margin),
    }


def nightly_part(filed: dict, analysis: Optional[dict], frame, *, n: int,
                 info: Optional[dict] = None, as_of=None) -> dict:
    """The part read fresh every scan night: the estimate revisions as they stand,
    the report-day reactions off the night's own price frame, the company snapshot
    and the next report day."""
    as_reports = [{"day": pd.Timestamp(r["day"]), "before_open": r["before_open"]}
                  for r in filed.get("reports", [])]
    day = as_of if as_of is not None else (frame.index[-1] if frame is not None and len(frame) else pd.Timestamp.today())
    return {"revisions": revisions(analysis), "reactions": reactions(frame, as_reports, n),
            "trends": trends(filed), "snapshot": snapshot(info), "next_earnings": next_earnings(info, day)}
