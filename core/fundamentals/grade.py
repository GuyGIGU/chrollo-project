"""The fundamental grade: the business, graded apart from the chart.

Operator, Mon 12/10/2026: *"the split between technical and fundamental is correct.
Technical grade is reserved for matching the visual chart pattern which can also
include some dry stats like ADR and Trend template"*; the fundamental grade reads his
list (``core.fundamentals.sheet``). It is display and archive only: it never gates a
fire and never moves the setup grade or the tier.

Nine checks, each passed, failed or not known (no data). The letter is the share of
the KNOWN checks passed (``FUND_GRADE_LETTERS``), so a missing line never counts
against a stock; fewer known checks than ``FUND_GRADE_MIN_CHECKS`` give no letter.
Every threshold is OUR default from the O'Neil / Minervini canon and lives in
``config/enrichment.py``, his to change; it is recalibrated against the archive later,
never at add time. The checks follow his words "whether the business is improving --
not just whether its latest quarter looks impressive": growth, its speed, its
steadiness, margins, beats, estimates, the market's verdict, and the quality of the
earnings.
"""
from __future__ import annotations

from typing import Optional


def _knob(name: str):
    """A grade threshold, read lazily (the backend's cwd can shadow the repo's
    ``config`` package at import time)."""
    from config import settings

    return getattr(settings, name)


#: The checks in the order the sheet shows them: (key, the plain words).
CHECKS = (
    ("eps_growth", "EPS up 25%+ on the year"),
    ("eps_accel", "EPS growth speeding up"),
    ("eps_steady", "EPS up on the year in each of the last four reports"),
    ("sales_growth", "Sales up 25%+ on the year, or sales growth speeding up"),
    ("margins", "Operating margin above a year earlier"),
    ("beats", "Beat the estimate in 3 of the last 4 reports, the latest included"),
    ("estimates", "Analysts raising this year's EPS estimate"),
    ("reaction", "A report the market bought: 2+ daily ranges up on 2x volume"),
    ("quality", "No earnings-quality concern"),
)


def _pct(x: float) -> str:
    return f"{x * 100:+.0f}%"


def _eps_growth(sheet):
    yoy = [e.get("yoy") for e in sheet.get("eps", [])]
    if not yoy or yoy[-1] is None:
        return None, "no year-ago report to compare"
    floor = _knob("FUND_GRADE_EPS_GROWTH_MIN")
    return yoy[-1] >= floor, f"latest report {_pct(yoy[-1])}"


def _eps_accel(sheet):
    yoy = [e.get("yoy") for e in sheet.get("eps", [])]
    if len(yoy) < 2 or yoy[-1] is None or yoy[-2] is None:
        return None, "needs two year-on-year growths"
    return yoy[-1] > yoy[-2], f"{_pct(yoy[-2])} then {_pct(yoy[-1])}"


def _eps_steady(sheet):
    yoy = [e.get("yoy") for e in sheet.get("eps", [])]
    n = _knob("FUND_SHEET_QUARTERS")
    if len(yoy) < n or any(v is None for v in yoy):
        return None, f"needs {n} year-on-year growths"
    return all(v > 0 for v in yoy), ", ".join(_pct(v) for v in yoy)


def _sales_growth(sheet):
    quarters = sheet.get("quarters", [])
    if not quarters:
        return None, "no quarters"
    yoy = quarters[-1].get("sales_yoy")
    qoq = [q.get("sales_qoq") for q in quarters[-3:]]
    speeding = len(qoq) == 3 and None not in qoq and qoq[0] < qoq[1] < qoq[2]
    if yoy is not None and yoy >= _knob("FUND_GRADE_SALES_GROWTH_MIN"):
        return True, f"latest quarter {_pct(yoy)} on the year"
    if speeding:
        return True, "quarter-on-quarter growth " + ", ".join(_pct(v) for v in qoq)
    if yoy is None and (len(qoq) < 3 or None in qoq):
        return None, "no year-ago quarter and too few quarters"
    said = f"latest quarter {_pct(yoy)} on the year" if yoy is not None else "no year-ago quarter"
    return False, said + ", growth not speeding up"


def _margins(sheet):
    quarters = sheet.get("quarters", [])
    if not quarters or quarters[-1].get("operating_margin") is None:
        return None, "no operating margin"
    now = quarters[-1]["operating_margin"]
    before = quarters[-1].get("operating_margin_year_ago")
    if before is None:
        return None, "no year-ago quarter"
    return now > before, f"{before * 100:.1f}% a year earlier, {now * 100:.1f}% now"


def _beats(sheet):
    surprises = [e.get("surprise") for e in sheet.get("eps", [])]
    known = [s for s in surprises if s is not None]
    if len(known) < 3 or surprises[-1] is None:
        return None, "too few estimates to compare"
    beats = sum(1 for s in known if s > 0)
    passed = beats >= _knob("FUND_GRADE_BEATS_MIN") and surprises[-1] > 0
    return passed, f"{beats} of {len(known)} beaten, the latest {_pct(surprises[-1])}"


def _estimates(sheet):
    r = sheet.get("revisions") or {}
    change, up, down = r.get("this_year_change_90d"), r.get("up_30d"), r.get("down_30d")
    if change is None:
        return None, "no estimate history"
    raised = change > 0 and (up is None or down is None or up >= down)
    moves = "" if up is None or down is None else f"; {up} up / {down} down in 30 days"
    return raised, f"this year's estimate {_pct(change)} in 90 days{moves}"


def _reaction(sheet):
    moves = [m for m in sheet.get("reactions", []) if m.get("ranges") is not None and m.get("volume_ratio") is not None]
    if not moves:
        return None, "no report days in the price data"
    best = max(moves, key=lambda m: m["ranges"])
    bought = [m for m in moves if m["ranges"] >= _knob("FUND_GRADE_REACTION_RANGES")
              and m["volume_ratio"] >= _knob("FUND_GRADE_REACTION_VOLUME")]
    if bought:
        top = max(bought, key=lambda m: m["ranges"])
        return True, f"{top['day']}: {_pct(top['change'])} ({top['ranges']:.1f} ranges) on {top['volume_ratio']:.1f}x volume"
    return False, f"best {best['day']}: {_pct(best['change'])} ({best['ranges']:.1f} ranges) on {best['volume_ratio']:.1f}x volume"


def _quality(sheet):
    q = sheet.get("quality") or {}
    if not q.get("flags_known"):
        return None, "no cash-flow data"
    flags = q.get("flags") or []
    return not flags, "; ".join(flags) if flags else "none identified"


_READERS = {"eps_growth": _eps_growth, "eps_accel": _eps_accel, "eps_steady": _eps_steady,
            "sales_growth": _sales_growth, "margins": _margins, "beats": _beats,
            "estimates": _estimates, "reaction": _reaction, "quality": _quality}


#: The descriptive labels (proposed to him 12/10/2026 as Chrollo's own, not Minervini's categories), the
#: first that fits. "Catalyst-led" and "cyclical / event-driven" need a judgment of the story: his read.
ACCELERATING, STRONG, TURNAROUND, MIXED = ("Accelerating growth", "Strong growth", "Turnaround",
                                           "Mixed / insufficient data")


def label(sheet: dict) -> str:
    t = sheet.get("trends") or {}
    eps, quarters = sheet.get("eps") or [], sheet.get("quarters") or []
    if t.get("eps") == "accelerating" and "accelerating" in (t.get("sales"), t.get("sales_qoq")):
        return ACCELERATING
    last_eps = eps[-1] if eps else {}
    last_q = quarters[-1] if quarters else {}
    om, om_before = last_q.get("operating_margin"), last_q.get("operating_margin_year_ago")
    margins_held = om is None or om_before is None or om >= om_before
    if (last_eps.get("yoy") is not None and last_q.get("sales_yoy") is not None
            and last_eps["yoy"] >= _knob("FUND_GRADE_EPS_GROWTH_MIN")
            and last_q["sales_yoy"] >= _knob("FUND_GRADE_SALES_GROWTH_MIN") and margins_held):
        return STRONG
    if last_eps.get("turn") in ("loss → profit", "loss narrowed") or (
            om is not None and om_before is not None and om_before < 0 and om > om_before):
        return TURNAROUND
    return MIXED


def code33(sheet: dict) -> dict:
    """Minervini's Code 33, strict: EPS growth, sales growth and the profit margin
    each rising over three quarters in a row, every figure known. ``met`` is None
    when any of the nine figures is missing (never awarded on two good quarters)."""
    eps = [e.get("yoy") for e in sheet.get("eps", [])][-3:]
    sales = [q.get("sales_yoy") for q in sheet.get("quarters", [])][-3:]
    margin = [q.get("net_margin") for q in sheet.get("quarters", [])][-3:]
    series = {"EPS growth": eps, "sales growth": sales, "net margin": margin}
    missing = [name for name, values in series.items() if len(values) < 3 or None in values]
    if missing:
        return {"met": None, "why": "not enough comparable history: " + ", ".join(missing)}
    rising = {name: values[0] < values[1] < values[2] for name, values in series.items()}
    if all(rising.values()):
        return {"met": True, "why": "EPS growth, sales growth and net margin up three quarters running"}
    return {"met": False, "why": "not rising three quarters running: " + ", ".join(n for n, ok in rising.items() if not ok)}


def letter_for(share: float) -> str:
    for floor, letter in _knob("FUND_GRADE_LETTERS"):
        if share >= floor:
            return letter
    return "D"


def grade(sheet: dict) -> dict:
    """``{"letter", "passed", "known", "checks": [{"key", "label", "passed", "why"}]}``.
    ``letter`` is None with fewer known checks than ``FUND_GRADE_MIN_CHECKS``."""
    checks = []
    for key, words in CHECKS:
        passed, why = _READERS[key](sheet)
        checks.append({"key": key, "label": words, "passed": passed, "why": why})
    known = [c for c in checks if c["passed"] is not None]
    passed = sum(1 for c in known if c["passed"])
    letter: Optional[str] = None
    if len(known) >= _knob("FUND_GRADE_MIN_CHECKS"):
        letter = letter_for(passed / len(known))
    return {"letter": letter, "passed": passed, "known": len(known), "checks": checks,
            "label": label(sheet), "code33": code33(sheet)}
