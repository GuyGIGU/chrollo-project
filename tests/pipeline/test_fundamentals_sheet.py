"""The fundamentals sheet, the fundamental grade and the SEC fill (2026-10-12).

His list (Mon 12/10/2026): the last four quarters of EPS and sales growth, margin
trends, beats and misses, estimate revisions, the catalyst's proof, earnings
quality. What is pinned: nothing is read before it was public (a quarter on its
report day, an SEC fact on its filing day, an estimate never from the future), the
year-on-year lines compare the same quarter a year apart, the market's verdict is
read on the day that first traded on the report, each grade check passes, fails or
says "not known", and a missing line never counts against a stock.
"""
import json

import numpy as np
import pandas as pd
import pytest

AT_4 = dict(abs=1e-4)

from core.fundamentals import grade, post_pass, sec, sheet


# ------------------------------------------------------------------ builders
def _earnings(rows):
    """rows: (report datetime 'YYYY-MM-DD HH:MM', reported, estimate, surprise %),
    returned most-recent-first and US/Eastern like yfinance."""
    idx = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows]).tz_localize("America/New_York")
    frame = pd.DataFrame({"EPS Estimate": [r[2] for r in rows], "Reported EPS": [r[1] for r in rows],
                          "Surprise(%)": [r[3] for r in rows]}, index=idx)
    return frame.sort_index(ascending=False)


def _stmt(ends, rows):
    """rows: {line item: [values oldest-first]} -> yfinance layout (columns most-recent-first)."""
    frame = pd.DataFrame(rows, index=pd.to_datetime(ends)).T
    return frame[frame.columns[::-1]]


EIGHT_REPORTS = [
    ("2024-08-01 16:05", 0.50, 0.45, 11.1), ("2024-11-01 16:05", 0.55, 0.50, 10.0),
    ("2025-02-01 16:05", 0.60, 0.55, 9.1), ("2025-05-01 16:05", 0.65, 0.60, 8.3),
    ("2025-08-01 16:05", 0.70, 0.65, 7.7), ("2025-11-01 16:05", 0.80, 0.70, 14.3),
    ("2026-02-01 16:05", 0.90, 0.95, -5.3), ("2026-05-01 08:00", 1.10, 1.00, 10.0),
]


# ------------------------------------------------------------------ EPS lines
def test_reports_keep_only_what_was_reported_by_the_day():
    rows = EIGHT_REPORTS + [("2026-08-01 16:05", None, 1.2, None)]          # the next, not yet reported
    reps = sheet.reports(_earnings(rows), "2026-04-30")
    assert [str(r["day"].date()) for r in reps][-1] == "2026-02-01"        # 2026-05-01 was after the read day
    assert len(reps) == 7


def test_a_repeated_report_day_keeps_the_row_with_a_number():
    rows = EIGHT_REPORTS + [("2026-05-01 09:00", None, 1.0, None)]
    reps = sheet.reports(_earnings(rows), "2026-06-01")
    may = [r for r in reps if str(r["day"].date()) == "2026-05-01"]
    assert len(may) == 1 and may[0]["eps"] == pytest.approx(1.10, **AT_4)


def test_eps_growth_compares_each_report_with_the_one_four_earlier():
    lines = sheet.eps_lines(sheet.reports(_earnings(EIGHT_REPORTS), "2026-06-01"), 4)
    assert [l["day"] for l in lines] == ["2025-08-01", "2025-11-01", "2026-02-01", "2026-05-01"]
    assert lines[0]["yoy"] == pytest.approx(0.70 / 0.50 - 1, **AT_4)
    assert lines[-1]["yoy"] == pytest.approx(1.10 / 0.65 - 1, **AT_4)
    assert lines[2]["surprise"] == pytest.approx(-0.053, **AT_4)


# ------------------------------------------------------------------ quarters
ENDS = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"]
STMT = _stmt(ENDS, {"Total Revenue": [100.0, 110.0, 120.0, 135.0, 150.0],
                    "Gross Profit": [60.0, 66.0, 73.0, 83.0, 93.0],
                    "Operating Income": [10.0, 12.0, 15.0, 20.0, 27.0],
                    "Net Income": [8.0, 9.0, 12.0, 16.0, 22.0]})
REPORT_DAYS = [pd.Timestamp(d) for d in ("2025-05-01", "2025-08-01", "2025-11-01", "2026-02-01", "2026-05-01")]


def test_a_quarter_is_visible_from_its_report_day_not_before():
    lines, visible = sheet.quarter_lines(STMT, REPORT_DAYS, "2026-04-30", 4)
    assert lines[-1]["end"] == "2025-12-31"                    # March 2026 reported 01/05
    lines, _ = sheet.quarter_lines(STMT, REPORT_DAYS, "2026-05-01", 4)
    assert lines[-1]["end"] == "2026-03-31"


def test_without_a_matching_report_the_filing_lag_decides():
    lines, _ = sheet.quarter_lines(STMT, [], "2026-05-01", 4)
    assert lines[-1]["end"] == "2025-12-31"                    # 2026-03-31 + 75 days is mid-June
    lines, _ = sheet.quarter_lines(STMT, [], "2026-06-15", 4)
    assert lines[-1]["end"] == "2026-03-31"


def test_sales_year_on_year_needs_the_same_quarter_a_year_earlier():
    lines, _ = sheet.quarter_lines(STMT, REPORT_DAYS, "2026-06-01", 4)
    assert [l["sales_yoy"] for l in lines] == [None, None, None, pytest.approx(0.5, **AT_4)]
    assert lines[-1]["sales_yoy_source"] == "yahoo"
    assert lines[-1]["sales_qoq"] == pytest.approx(150 / 135 - 1, **AT_4)
    assert lines[-1]["operating_margin"] == pytest.approx(27 / 150, **AT_4)
    assert lines[-1]["operating_margin_year_ago"] == pytest.approx(10 / 100, **AT_4)


def test_the_sec_fills_the_year_ago_quarters_and_says_so():
    sec_sales = {"2024-06-30": 88.0, "2024-09-30": 96.0, "2024-12-31": 112.5}
    lines, _ = sheet.quarter_lines(STMT, REPORT_DAYS, "2026-06-01", 4, sec_sales=sec_sales)
    assert [l["sales_yoy_source"] for l in lines] == ["sec", "sec", "sec", "yahoo"]
    assert lines[0]["sales_yoy"] == pytest.approx(110 / 88 - 1, **AT_4)
    assert lines[2]["sales_yoy"] == pytest.approx(135 / 112.5 - 1, **AT_4)


def test_quality_sums_cash_against_income_and_stock_pay_against_sales():
    cash = _stmt(ENDS, {"Operating Cash Flow": [5.0, 6.0, 7.0, 8.0, 9.0],
                        "Stock Based Compensation": [20.0, 22.0, 24.0, 27.0, 30.0]})
    _, visible = sheet.quarter_lines(STMT, REPORT_DAYS, "2026-06-01", 4)
    q = sheet.quality(STMT, cash, visible, 4)
    assert q["operating_cash_flow"] == 30 and q["net_income"] == 59
    assert q["sbc_share_of_sales"] == pytest.approx(103 / 515, abs=1e-4)
    assert q["flags"] == ["profits not backed by cash"] and q["flags_known"] is True


def test_quality_flags_one_time_items_buybacks_and_acquisitions():
    stmt = _stmt(ENDS, {"Total Revenue": [100.0, 110.0, 120.0, 135.0, 150.0],
                        "Net Income": [8.0, 9.0, 12.0, 16.0, 20.0],
                        "Total Unusual Items": [0.0, 0.0, 0.0, 0.0, 6.0],          # 30% of the latest net income
                        "Diluted Average Shares": [100.0, 99.0, 98.0, 97.0, 95.0]})  # down 5% on the year
    cash = _stmt(ENDS, {"Operating Cash Flow": [9.0, 10.0, 13.0, 17.0, 22.0],
                        "Stock Based Compensation": [1.0, 1.0, 1.0, 1.0, 1.0],
                        "Purchase Of Business": [0.0, 0.0, -60.0, 0.0, 0.0]})      # 60 of 515 sales
    _, visible = sheet.quarter_lines(stmt, REPORT_DAYS, "2026-06-01", 4)
    flags = sheet.quality(stmt, cash, visible, 4)["flags"]
    assert flags == ["one-time items 30% of the latest net income",
                     "share count down 5% on the year (buybacks lift EPS)", "acquisitions 12% of sales"]
    clean = sheet.quality(STMT, _stmt(ENDS, {"Operating Cash Flow": [9.0, 10.0, 13.0, 17.0, 23.0]}), visible, 4)
    assert clean["flags"] == [] and clean["flags_known"] is True


# ------------------------------------------------------------------ losses, GAAP, trends
@pytest.mark.parametrize("now, before, out", [
    (1.2, 1.0, (pytest.approx(0.2), None)), (0.3, -0.2, (None, "loss → profit")),
    (-0.1, -0.4, (None, "loss narrowed")), (-0.5, -0.4, (None, "loss widened")),
    (0.3, 0.0, (None, "loss → profit")), (None, 1.0, (None, None))])
def test_growth_off_a_loss_is_said_in_words_never_a_percentage(now, before, out):
    assert sheet.eps_change(now, before) == out


def test_gaap_eps_rides_beside_the_quarter_with_its_own_year_on_year():
    stmt = _stmt(ENDS, {"Total Revenue": [100.0, 110.0, 120.0, 135.0, 150.0],
                        "Diluted EPS": [-0.10, 0.02, 0.05, 0.08, 0.12]})
    lines, _ = sheet.quarter_lines(stmt, REPORT_DAYS, "2026-06-01", 4)
    assert lines[-1]["eps_gaap"] == pytest.approx(0.12) and lines[-1]["eps_gaap_yoy"] is None
    assert lines[-1]["eps_gaap_turn"] == sheet.LOSS_TO_PROFIT


@pytest.mark.parametrize("values, word", [([0.1, 0.2, 0.3], "accelerating"), ([0.3, 0.2, 0.1], "slowing"),
                                          ([0.1, 0.3, 0.2], "mixed"), ([0.5, 0.1, 0.2, 0.3], "accelerating"),
                                          ([0.2, 0.3], None), ([None, 0.2, 0.3], None)])
def test_a_trend_needs_three_known_quarters(values, word):
    assert sheet.trend(values) == word


# ------------------------------------------------------------------ snapshot and next report
def test_the_snapshot_is_the_first_sentence_of_the_business():
    snap = sheet.snapshot({"longName": "Snow Co.", "sector": "Technology", "industry": "Software",
                           "longBusinessSummary": "Snow Co. sells a data platform. It was founded in 2012."})
    assert snap == {"name": "Snow Co.", "sector": "Technology", "industry": "Software",
                    "summary": "Snow Co. sells a data platform."}
    inc = sheet.snapshot({"longBusinessSummary": "Snowflake Inc. provides a data platform in the U.S. and abroad. More."})
    assert inc["summary"] == "Snowflake Inc. provides a data platform in the U.S. and abroad."
    capital = sheet.snapshot({"longBusinessSummary": "Acme Corp. Global sells widgets. It began in 1990."})
    assert capital["summary"] == "Acme Corp. Global sells widgets."
    assert sheet.snapshot(None)["summary"] is None


def test_the_next_report_says_whether_it_is_confirmed():
    day = pd.Timestamp("2026-12-02 16:00", tz="America/New_York").timestamp()
    nxt = sheet.next_earnings({"earningsTimestampStart": day, "isEarningsDateEstimate": True}, "2026-10-12")
    assert nxt == {"day": "2026-12-02", "confirmed": False}
    assert sheet.next_earnings({"earningsTimestampStart": day}, "2026-10-12")["confirmed"] is None
    assert sheet.next_earnings({"earningsTimestampStart": day}, "2026-12-03") is None


# ------------------------------------------------------------------ reactions
def _prices(n=120, start="2026-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    close = np.full(n, 100.0)
    return pd.DataFrame({"Open": close, "High": close * 1.02, "Low": close / 1.02 * 1.0,
                         "Close": close.copy(), "Volume": np.full(n, 1000.0)}, index=idx)


def test_an_after_close_report_is_judged_on_the_next_trading_day():
    frame = _prices()
    day = frame.index[80]
    frame.loc[frame.index[81], ["Close", "Volume"]] = [110.0, 4000.0]
    out = sheet.reactions(frame, [{"day": day, "before_open": False}], 4)
    assert out[0]["day"] == str(frame.index[81].date())
    assert out[0]["change"] == pytest.approx(0.10, **AT_4)
    assert out[0]["volume_ratio"] == pytest.approx(4.0, **AT_4)
    assert out[0]["ranges"] == pytest.approx(0.10 / (1.02 / (1 / 1.02) - 1), abs=0.01)


def test_a_before_open_report_is_judged_the_same_day():
    frame = _prices()
    day = frame.index[80]
    out = sheet.reactions(frame, [{"day": day, "before_open": True}], 4)
    assert out[0]["day"] == str(day.date())


def test_a_frame_without_bars_reads_no_reaction():
    assert sheet.reactions(pd.DataFrame({"Close": [1.0] * 100}), [], 4) == []


# ------------------------------------------------------------------ revisions
def test_revisions_read_now_against_ninety_days_ago():
    trend = pd.DataFrame({"current": [2.2, 3.0], "90daysAgo": [2.0, 2.5]}, index=["0y", "+1y"])
    moves = pd.DataFrame({"upLast30days": [9], "downLast30days": [1]}, index=["0y"])
    r = sheet.revisions({"eps_trend": trend, "eps_revisions": moves})
    assert r["this_year_change_90d"] == pytest.approx(0.10, **AT_4)
    assert r["next_year_change_90d"] == pytest.approx(0.20, **AT_4)
    assert (r["up_30d"], r["down_30d"]) == (9, 1)
    assert sheet.revisions({})["this_year_change_90d"] is None


# ------------------------------------------------------------------ the grade
def _sheet(**over):
    base = {
        "eps": [{"yoy": 0.30, "surprise": 0.05}, {"yoy": 0.35, "surprise": 0.04},
                {"yoy": 0.40, "surprise": 0.06}, {"yoy": 0.50, "surprise": 0.10}],
        "quarters": [{"sales_yoy": 0.30, "sales_qoq": 0.05, "operating_margin": 0.10, "operating_margin_year_ago": 0.08},
                     {"sales_yoy": 0.31, "sales_qoq": 0.06, "operating_margin": 0.11, "operating_margin_year_ago": 0.08},
                     {"sales_yoy": 0.32, "sales_qoq": 0.07, "operating_margin": 0.12, "operating_margin_year_ago": 0.09},
                     {"sales_yoy": 0.35, "sales_qoq": 0.08, "operating_margin": 0.13, "operating_margin_year_ago": 0.09}],
        "revisions": {"this_year_change_90d": 0.05, "up_30d": 5, "down_30d": 1},
        "reactions": [{"day": "2026-05-02", "change": 0.12, "ranges": 3.0, "volume_ratio": 4.0}],
        "quality": {"flags": [], "flags_known": True},
        "trends": {"eps": "accelerating", "sales": "accelerating", "margin": "expanding"},
    }
    base.update(over)
    return base


def _check(result, key):
    return next(c for c in result["checks"] if c["key"] == key)["passed"]


def test_a_strong_improving_business_passes_every_check():
    g = grade.grade(_sheet())
    assert (g["letter"], g["passed"], g["known"]) == ("A", 9, 9)


def test_each_check_fails_on_its_own_fault():
    eps = _sheet()["eps"]
    assert _check(grade.grade(_sheet(eps=eps[:3] + [{"yoy": 0.20, "surprise": 0.1}])), "eps_growth") is False
    assert _check(grade.grade(_sheet(eps=eps[:3] + [{"yoy": 0.30, "surprise": 0.1}])), "eps_accel") is False
    assert _check(grade.grade(_sheet(eps=[{"yoy": -0.1, "surprise": 0.1}] + eps[1:])), "eps_steady") is False
    assert _check(grade.grade(_sheet(eps=eps[:3] + [{"yoy": 0.5, "surprise": -0.01}])), "beats") is False
    q = _sheet()["quarters"]
    slow = [dict(x, sales_yoy=0.10, sales_qoq=0.03) for x in q]
    assert _check(grade.grade(_sheet(quarters=slow)), "sales_growth") is False
    shrink = q[:3] + [dict(q[3], operating_margin=0.05)]
    assert _check(grade.grade(_sheet(quarters=shrink)), "margins") is False
    assert _check(grade.grade(_sheet(revisions={"this_year_change_90d": -0.02, "up_30d": 0, "down_30d": 3})), "estimates") is False
    assert _check(grade.grade(_sheet(reactions=[{"day": "d", "change": 0.03, "ranges": 1.0, "volume_ratio": 3.0}])), "reaction") is False
    assert _check(grade.grade(_sheet(quality={"flags": ["profits not backed by cash"], "flags_known": True})), "quality") is False


def test_sales_speeding_up_passes_without_a_year_ago_quarter():
    q = [dict(x, sales_yoy=None) for x in _sheet()["quarters"]]
    assert _check(grade.grade(_sheet(quarters=q)), "sales_growth") is True


def test_a_missing_line_is_not_known_and_never_counts_against():
    g = grade.grade(_sheet(reactions=[], quality={}))
    assert _check(g, "reaction") is None and _check(g, "quality") is None
    assert (g["passed"], g["known"], g["letter"]) == (7, 7, "A")


def test_too_few_known_checks_give_no_letter():
    g = grade.grade({"eps": [], "quarters": [], "revisions": {}, "reactions": [],
                     "quality": {"flags": [], "flags_known": True}})
    assert g["known"] == 1 and g["letter"] is None


def test_the_label_is_the_first_that_fits():
    assert grade.label(_sheet()) == grade.ACCELERATING
    steady = _sheet(trends={"eps": "mixed", "sales": "mixed"})
    assert grade.label(steady) == grade.STRONG
    turned = _sheet(trends={}, eps=[{"yoy": None, "turn": sheet.LOSS_TO_PROFIT}], quarters=[{"sales_yoy": 0.1}])
    assert grade.label(turned) == grade.TURNAROUND
    margin_turn = _sheet(trends={}, eps=[], quarters=[{"operating_margin": 0.05, "operating_margin_year_ago": -0.1}])
    assert grade.label(margin_turn) == grade.TURNAROUND
    assert grade.label({}) == grade.MIXED


def _q33(sales, margins):
    return [{"sales_yoy": s, "net_margin": m} for s, m in zip(sales, margins)]


def test_code_33_is_strict_three_quarters_of_all_three_and_unknown_without_history():
    eps = [{"yoy": 0.2}, {"yoy": 0.3}, {"yoy": 0.4}]
    met = grade.code33({"eps": eps, "quarters": _q33([0.1, 0.2, 0.3], [0.05, 0.06, 0.07])})
    assert met["met"] is True
    flat_margin = grade.code33({"eps": eps, "quarters": _q33([0.1, 0.2, 0.3], [0.05, 0.06, 0.06])})
    assert flat_margin["met"] is False and "net margin" in flat_margin["why"]
    two_good = grade.code33({"eps": eps[1:], "quarters": _q33([0.2, 0.3], [0.06, 0.07])})
    assert two_good["met"] is None
    no_sales_history = grade.code33({"eps": eps, "quarters": _q33([None, None, 0.3], [0.05, 0.06, 0.07])})
    assert no_sales_history["met"] is None and "sales growth" in no_sales_history["why"]


@pytest.mark.parametrize("share, letter", [(1.0, "A"), (0.85, "A"), (0.8, "B"), (0.7, "B"), (0.6, "C"), (0.5, "C"), (0.49, "D")])
def test_the_letter_is_the_share_of_known_checks_passed(share, letter):
    assert grade.letter_for(share) == letter


# ------------------------------------------------------------------ the SEC
def _fact(start, end, val, filed, form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


FACTS = {"facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
    _fact("2024-01-01", "2024-03-31", 100.0, "2024-05-01"),
    _fact("2024-01-01", "2024-03-31", 999.0, "2025-05-01"),              # a later restatement of the same quarter
    _fact("2024-04-01", "2024-06-30", 110.0, "2024-08-01"),
    _fact("2024-07-01", "2024-09-30", 120.0, "2024-11-01"),
    _fact("2024-01-01", "2024-12-31", 470.0, "2025-02-20", "10-K"),       # the year: Q4 = 470 - 330
    _fact("2025-01-01", "2025-03-31", 130.0, "2025-05-01"),
]}}}}}


def test_sec_sales_take_each_quarter_as_first_filed_and_derive_the_fourth():
    out = sec.quarterly_sales(FACTS, "2025-06-01")
    assert out["2024-03-31"] == 100.0                                    # not the 2025 restatement
    assert out["2024-12-31"] == pytest.approx(140.0, **AT_4)
    assert out["2025-03-31"] == 130.0


def test_sec_sales_never_read_a_fact_filed_after_the_day():
    out = sec.quarterly_sales(FACTS, "2024-12-31")
    assert set(out) == {"2024-03-31", "2024-06-30", "2024-09-30"}


def test_the_sec_is_never_asked_without_a_contact(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the SEC was called without a contact")
    monkeypatch.setattr(sec, "_get_json", boom)
    assert sec.sales_for("AAA", "2026-01-01", "", "unused") is None


# ------------------------------------------------------------------ the scan
class _Provider:
    def __init__(self):
        self.calls = []

    def get_income_stmt(self, ticker, quarterly=True):
        self.calls.append("stmt")
        return _stmt(["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"],
                     {"Total Revenue": [100.0, 110.0, 120.0, 130.0, 140.0],
                      "Operating Income": [10.0, 11.0, 13.0, 15.0, 18.0],
                      "Net Income": [8.0, 9.0, 10.0, 12.0, 14.0],
                      "Diluted EPS": [0.5, 0.55, 0.6, 0.65, 0.7]})

    def get_earnings_dates(self, ticker, limit=12):
        self.calls.append("earnings")
        return _earnings([("2025-08-01 16:05", 0.5, 0.45, 11.0), ("2025-11-01 16:05", 0.55, 0.5, 10.0),
                          ("2026-02-01 16:05", 0.6, 0.55, 9.0), ("2026-05-01 16:05", 0.65, 0.6, 8.0),
                          ("2026-08-01 16:05", 0.9, 0.7, 28.0)])

    def get_cashflow(self, ticker, quarterly=True):
        self.calls.append("cash")
        return pd.DataFrame()

    def get_analysis(self, ticker):
        self.calls.append("analysis")
        return {"eps_trend": pd.DataFrame({"current": [3.0], "90daysAgo": [2.5]}, index=["0y"])}

    def earnings_date(self, ticker):
        return "2026-11-01"

    def info(self, ticker):
        self.calls.append("info")
        return {"longName": "Triple A", "sector": "Technology", "industry": "Software",
                "earningsTimestampStart": pd.Timestamp("2026-11-01 16:00", tz="America/New_York").timestamp(),
                "isEarningsDateEstimate": False}


def _run(tmp_path, monkeypatch, provider, end="2026-09-01"):
    from config import settings
    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)
    monkeypatch.setattr(settings, "SEC_CONTACT", "", raising=False)
    row = {"Ticker": "AAA"}
    frame = _prices(n=200, start="2025-12-01")
    frame = frame.loc[:end]
    counts = post_pass.attach_fundamentals_post_pass([row], {"AAA": frame}, provider=provider,
                                                     cache_path=str(tmp_path / "cache.json"))
    return row, counts


def test_the_scan_attaches_the_sheet_and_the_grade(tmp_path, monkeypatch):
    provider = _Provider()
    row, counts = _run(tmp_path, monkeypatch, provider)
    assert counts["sheet_populated"] == 1
    assert provider.calls.count("stmt") == 1 and provider.calls.count("earnings") == 1   # fetched once
    s = row["_fund_sheet"]
    assert s["eps"][-1]["day"] == "2026-08-01" and s["eps"][-1]["yoy"] == pytest.approx(0.8, **AT_4)
    assert s["quarters"][-1]["end"] == "2026-06-30" and s["quarters"][-1]["sales_yoy"] == pytest.approx(0.4, **AT_4)
    assert row["_fund_grade"] == s["grade"]["letter"]
    assert s["next_earnings"] == {"day": "2026-11-01", "confirmed": True}
    assert s["snapshot"]["industry"] == "Software" and s["grade"]["label"] in (
        grade.ACCELERATING, grade.STRONG, grade.TURNAROUND, grade.MIXED)
    assert "_fund_sheet_filed" not in row
    json.dumps(s)                                                    # wire- and archive-ready


def test_the_cached_sheet_replays_and_the_nightly_part_is_fresh(tmp_path, monkeypatch):
    provider = _Provider()
    _run(tmp_path, monkeypatch, provider)
    provider.calls.clear()
    row, counts = _run(tmp_path, monkeypatch, provider, end="2026-09-02")
    assert counts["cache_hits"] == 1
    assert provider.calls == ["analysis", "info"]                    # estimates and the next report: every night
    assert row["_fund_sheet"]["quarters"][-1]["end"] == "2026-06-30"


def test_a_cache_entry_from_before_the_sheet_is_fetched_again(tmp_path, monkeypatch):
    (tmp_path / "cache.json").write_text(json.dumps({"AAA": {
        "as_of": "2026-08-30", "next_earnings": "2026-11-01",
        "fund_fields": {"_fund_eps_growth_yoy": 0.1}}}), encoding="utf-8")
    provider = _Provider()
    row, counts = _run(tmp_path, monkeypatch, provider)
    assert counts["cache_hits"] == 0 and "stmt" in provider.calls
    assert "_fund_sheet" in row


def test_a_sheet_that_falls_over_costs_only_itself(tmp_path, monkeypatch):
    provider = _Provider()
    monkeypatch.setattr(sheet, "nightly_part", lambda *a, **k: 1 / 0)
    row, counts = _run(tmp_path, monkeypatch, provider)
    assert "_fund_sheet" not in row and counts["sheet_populated"] == 0
    assert row["_fund_earnings_surprise"] == pytest.approx(0.28)      # the four metrics stand


def test_no_test_reaches_the_sec_even_with_a_contact_in_the_live_config(tmp_path, monkeypatch):
    """tests/conftest.py blanks SEC_CONTACT for every test: the live config names the operator's contact, and a
    full provider would otherwise send the SEC a real request from the test run."""
    asked = []
    monkeypatch.setattr(sec, "sales_for", lambda ticker, as_of, contact, cache_dir: asked.append(contact) or None)
    from config import settings
    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)
    post_pass.attach_fundamentals_post_pass([{"Ticker": "AAA"}], {"AAA": _prices(n=200, start="2025-12-01")},
                                            provider=_Provider(), cache_path=str(tmp_path / "cache.json"))
    assert asked == [""]                                              # asked once, with no contact: no request
