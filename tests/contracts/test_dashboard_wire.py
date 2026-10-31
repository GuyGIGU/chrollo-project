"""The WIRE boundary of a fire's chart (core/pipeline/screening/dashboard._extract_chart_data).

Drives the REAL payload builder on a hand-built fire (the reader's record through its
adapter, the established pattern of tests/contracts/test_two_eyes_wire.py, which pins the
exact key set) over a synthetic frame — never a booted server. The sector-ETF lookup is the
one monkeypatched boundary (external lookup + a disk cache write).

What this file pins: the facts every fired row carries on top of the reader's block (the
leadership read, the group facts, the fundamentals, the market cap), the weekly and monthly
panes' box (decision A of the retirement, Fri 30/10/2026: the parent box's own rails), the
two volume measures, and the archive's grade filters.
"""
import datetime as dt
import os
import sys
import tempfile

import numpy as np
import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

from core.pipeline.screening import dashboard as dashboard_module


def _read(*, spring_day=None):
    """A fire as the reader hands it over: a parent, a mini, an LPS read against the mini, a grade."""
    from engine_alpha import record

    d = dt.date
    events = () if spring_day is None else (record.Event(kind=record.SPRING, day=spring_day, price=89.0),)
    boxes = (record.Box(resistance=record.Line(100.0, d(2026, 1, 12)), support=record.Line(90.0, d(2026, 1, 7)),
                        opened_day=d(2026, 1, 5), daily_range=2.0, role=record.ROLE_PARENT),
             record.Box(resistance=record.Line(98.0, d(2026, 2, 10)), support=record.Line(94.0, d(2026, 2, 12)),
                        opened_day=d(2026, 2, 10), daily_range=1.5, role=record.ROLE_MINI))
    lps = record.Lps(d(2026, 3, 2), d(2026, 3, 6), record.ROLE_MINI, trigger_price=98.4, how="on")
    grade = record.Grade(score=92.3, letter="S", empty_days=2, base_days=41, holds=True)
    return record.Read(ticker="AAA", as_of=d(2026, 3, 6), boxes=boxes, lps=lps, state="fired",
                       close=97.1, grade=grade, events=events)


def _frame(periods=60):
    dates = pd.date_range("2026-01-01", periods=periods, freq="B", name="Date")
    return pd.DataFrame({
        "Open": np.linspace(90, 99, len(dates)), "High": np.linspace(91, 100, len(dates)),
        "Low": np.linspace(89, 98, len(dates)), "Close": np.linspace(90, 99, len(dates)),
        "Volume": np.linspace(1000, 1100, len(dates)),
    }, index=dates)


def _payload(monkeypatch, *, overlay=None, frame=None) -> dict:
    """The per-ticker payload exactly as a scan would serialize it; an optional
    overlay injects the facts the scan attaches to a fire after the read."""
    from engine_alpha.result import to_result

    row = to_result(_read())
    row.update(overlay or {})
    results = pd.DataFrame([row])
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker",
                        lambda *_args: None)
    # the group facts (2026-10-23): no archive, a throwaway cache
    from core.fundamentals import industry
    monkeypatch.setattr(dashboard_module, "_industry_cache_path",
                        lambda: os.path.join(tempfile.mkdtemp(), "industry_cache.json"))
    monkeypatch.setattr(industry, "recent_fires", lambda *_a, **_k: {})
    chart_data = dashboard_module._extract_chart_data(_frame() if frame is None else frame, results, ["AAA"])
    assert "AAA" in chart_data, "the chart was dropped"
    return chart_data["AAA"]


# ── decision A (Fri 30/10/2026): the weekly and monthly panes carry the parent box ───────────

def test_the_weekly_and_monthly_panes_carry_the_parent_boxs_own_rails(monkeypatch):
    """A box is a price pair; it holds on every timeframe. The panes get the parent's R and S in
    the dict they read: the rails, where they start (the day the box opened), the anchor days that
    set them (the grey limb) and the LPS days (gold)."""
    chart = _payload(monkeypatch)
    expected = {"r": 100.0, "s": 90.0, "start_date": "2026-01-05",
                "limb_start_date": "2026-01-05", "limb_end_date": "2026-01-12",
                "lps_start_date": "2026-03-02", "lps_end_date": "2026-03-06"}
    assert chart["weekly_box"] == expected
    assert chart["monthly_box"] == expected
    assert (chart["R"], chart["S"]) == (100.0, 90.0), "the daily rails are the same pair"


def test_the_panes_box_is_the_parent_never_the_mini():
    block = {"boxes": [{"role": "mini", "r": 98.0, "s": 94.0, "r_day": "2026-02-10", "s_day": "2026-02-12",
                        "opened": "2026-02-10", "end": None}],
             "lps": {"start": "2026-03-02", "end": "2026-03-06"}}
    assert dashboard_module._timeframe_box(block) is None, "no parent, no box on the panes"
    block["boxes"].append({"role": "parent", "r": 100.0, "s": 90.0, "r_day": "2026-01-12",
                           "s_day": "2026-01-07", "opened": "2026-01-05", "end": "2026-02-27"})
    box = dashboard_module._timeframe_box(block)
    assert (box["r"], box["s"], box["start_date"]) == (100.0, 90.0, "2026-01-05")


def test_a_row_without_the_readers_block_draws_no_chart(monkeypatch, capsys):
    """Every fire carries the block; a row without it is said and skipped, never a crash of the night's charts."""
    from engine_alpha.result import to_result
    from engine_alpha.archive import SCREEN_KEY

    row = to_result(_read())
    del row[SCREEN_KEY]
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker", lambda *_args: None)
    monkeypatch.setattr(dashboard_module, "_group_facts", lambda *_a, **_k: {})
    assert dashboard_module._extract_chart_data(_frame(), pd.DataFrame([row]), ["AAA"]) == {}
    assert "carries no _wire_two_eyes block" in capsys.readouterr().out


def test_wire_carries_the_leadership_read(monkeypatch):
    chart = _payload(monkeypatch, overlay={
        "_rs_rating": 84.21, "_stage2_trend_pass_count": 7,
        "_stage2_52w_low_pct": 0.8412, "_stage2_ma200_slope_1m_pct": -1.25,
        "_cycle_stage": 2, "_advance_start": "2026-05-29", "_advance_weeks": 20})
    assert chart["rs_rating"] == 84.21
    assert chart["stage2_trend_pass_count"] == 7
    assert chart["stage2_52w_low_pct"] == 0.8412
    assert chart["stage2_ma200_slope_1m_pct"] == -1.25
    assert (chart["cycle_stage"], chart["advance_start"], chart["advance_weeks"]) == (2, "2026-05-29", 20)
    bare = _payload(monkeypatch)
    assert bare["cycle_stage"] is None and bare["advance_start"] is None and bare["advance_weeks"] is None

def test_wire_carries_the_group_facts(monkeypatch):
    """The industry and the group counts ride every fired row, resolved here (EC-28); a row whose sheet
    names no industry carries None, never a count."""
    sheet = {"snapshot": {"industry": "Steel", "sector": "Basic Materials"}}
    chart = _payload(monkeypatch, overlay={"_fund_sheet": sheet})
    assert chart["group"] == {"industry": "Steel", "fired_tonight": 1, "fired_10d": 1, "members": 1}
    assert _payload(monkeypatch)["group"] is None


def test_a_group_facts_fault_blanks_the_group_and_keeps_the_chart(monkeypatch):
    """The group read is display only: a fault in it costs the group cell, never the night's charts."""
    def broken(*args, **kwargs):
        raise RuntimeError("the industry cache fell over")

    monkeypatch.setattr(dashboard_module._industry, "group_counts", broken)
    sheet = {"snapshot": {"industry": "Steel", "sector": "Basic Materials"}}
    chart = _payload(monkeypatch, overlay={"_fund_sheet": sheet})
    assert chart["group"] is None and chart["tier"] == "S"


def test_wire_carries_the_fundamentals_and_market_cap(monkeypatch):
    chart = _payload(monkeypatch, overlay={
        "_fund_eps_growth_yoy": 0.45, "_fund_quarter_end": "2026-06-30",
        "_market_cap": 1.25e9})
    assert chart["fund_eps_growth_yoy"] == 0.45
    assert chart["fund_quarter_end"] == "2026-06-30"
    assert chart["market_cap"] == 1.25e9


def test_wire_carries_the_fundamentals_sheet_and_grade(monkeypatch):
    sheet = {"eps": [{"day": "2026-09-02", "yoy": 0.77}], "grade": {"letter": "A", "passed": 8, "known": 9}}
    chart = _payload(monkeypatch, overlay={
        "_fund_sheet": sheet, "_fund_grade": "A", "_fund_grade_score": 0.8889})
    assert chart["fund_sheet"] == sheet
    assert chart["fund_grade"] == "A" and chart["fund_grade_score"] == 0.8889
    bare = _payload(monkeypatch)
    assert bare["fund_sheet"] is None and bare["fund_grade"] is None


def test_spring_volume_is_read_against_the_50_days_ending_on_it():
    # 70 days: ten loud ones (10,000), then 59 at 100 and the spring at 250. The
    # 50 days ending on the spring average (49 x 100 + 250) / 50 = 103, so the
    # spring is 2.43x; a window reaching back to the loud days would read ~0.24x.
    dates = pd.date_range("2026-01-01", periods=70, freq="B")
    frame = pd.DataFrame({"Volume": [10_000.0] * 10 + [100.0] * 59 + [250.0]}, index=dates)
    assert dashboard_module._volume_vs_50d(frame, str(dates[-1].date())) == 2.43
    assert dashboard_module._volume_vs_50d(frame, "2025-01-01") is None   # not in the frame
    assert dashboard_module._volume_vs_50d(frame, None) is None


def test_dollar_volume_averages_the_last_50_trading_days():
    # Ten loud days, then 25 days at 100 shares and 25 at 300, all at $10:
    # the last 50 days trade $2,000 a day. A 60-day window would pull in the
    # loud days; a 20-day one would read only the 300s ($3,000).
    volume = [1_000_000.0] * 10 + [100.0] * 25 + [300.0] * 25
    frame = pd.DataFrame({"Close": [10.0] * 60, "Volume": volume})
    assert dashboard_module._dollar_volume_50d(frame) == 2000
    unreadable = pd.DataFrame({"Close": [np.nan] * 3, "Volume": [1.0] * 3})
    assert dashboard_module._dollar_volume_50d(unreadable) is None


def test_min_ta_grade_filter_excludes_ungraded_rows():
    """The grade's OWN filter: min_score keeps raw-sum semantics forever; a
    ta_grade floor excludes graded-below AND pre-v2 NULL rows (three-valued
    logic, deliberately — an ungraded row can never satisfy a grade floor)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    from archive_models import SetupArchive
    from domains.archive.queries import _apply_setup_filters

    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()

    def _row(ticker, grade):
        return SetupArchive(
            ticker=ticker, scan_date="2026-08-01", setup_type="LPS",
            tier="B", score=90.0, current_price=10.0, r_level=11.0,
            s_level=9.5, trigger_price=11.1, base_length=30, box_width=0.1,
            touches=4, atr_ratio=0.5, lps_length=3, breach_days=0,
            vol_contraction=0.4, tightness_ratio=0.4, ta_grade=grade)

    session.add_all([_row("HIGRD", 71.0), _row("LOGRD", 40.0),
                     _row("PREV2", None)])
    session.commit()
    got = {r.ticker for r in _apply_setup_filters(
        session.query(SetupArchive), min_ta_grade=50.0).all()}
    assert got == {"HIGRD"}
    unfiltered = {r.ticker for r in _apply_setup_filters(
        session.query(SetupArchive)).all()}
    assert unfiltered == {"HIGRD", "LOGRD", "PREV2"}


def test_episode_grade_floor_is_the_current_grade_and_keeps_the_anchor():
    """The episode view's ruled semantics (2026-08-08, operator-delegated):
    min_ta_grade floors on the episode's LATEST member's grade — a
    flip-straddling episode keeps its TRUE first-seen anchor, scan count,
    and saw-and-passed marker (the row-level filter re-anchored all three),
    and an episode whose grade decayed below the floor drops even though an
    older scan once passed. latest_ta_grade is served either way."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    from archive_models import SetupArchive
    import models
    from domains.archive.browse import list_episodes

    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()

    def _row(ticker, scan_date, grade):
        return SetupArchive(
            ticker=ticker, scan_date=scan_date, setup_type="LPS",
            tier="B", score=90.0, current_price=10.0, r_level=11.0,
            s_level=9.5, trigger_price=11.1, base_length=30, box_width=0.1,
            touches=4, atr_ratio=0.5, lps_length=3, breach_days=0,
            vol_contraction=0.4, tightness_ratio=0.4, ta_grade=grade)

    session.add_all([
        # STRAD: pre-flip NULL scan, then graded — one episode across the seam.
        _row("STRAD", "2026-08-03", None),
        _row("STRAD", "2026-08-04", 80.0),
        _row("STRAD", "2026-08-05", 75.0),
        # DECAY: once above the floor, latest below it.
        _row("DECAY", "2026-08-04", 90.0),
        _row("DECAY", "2026-08-05", 60.0),
        # PREV2: never graded.
        _row("PREV2", "2026-08-05", None),
    ])
    # The marker is keyed on the TRUE first_seen — it must survive the filter.
    session.add(models.SetupReview(ticker="STRAD", scan_date="2026-08-03",
                                   verdict="passed", note="looked, skipped"))
    session.commit()

    def _episodes(min_grade):
        # Plain-function route call: every Query default passed explicitly.
        return list_episodes(
            skip=0, limit=200, tier=None, setup_type=None, source=None,
            quality_label=None, min_score=None, min_ta_grade=min_grade,
            date_from=None, date_to=None, universe_type="us_equities",
            sort_by="first_seen", sort_dir="desc", db=session)

    eps = _episodes(70.0)
    assert [e.ticker for e in eps] == ["STRAD"]
    strad = eps[0]
    assert strad.first_seen == "2026-08-03"      # the true anchor, not 08-04
    assert strad.scan_count == 3                 # the NULL scan still counts
    assert strad.latest_ta_grade == 75.0         # the value the floor judged
    assert strad.ta_grade is None                # canonical row: honest NULL
    assert strad.passed is True                  # the marker did not detach

    lower = _episodes(50.0)
    assert {e.ticker for e in lower} == {"STRAD", "DECAY"}
    unfiltered = _episodes(None)
    assert {e.ticker for e in unfiltered} == {"STRAD", "DECAY", "PREV2"}
    by_ticker = {e.ticker: e for e in unfiltered}
    assert by_ticker["DECAY"].latest_ta_grade == 60.0   # served unfiltered too
    assert by_ticker["PREV2"].latest_ta_grade is None
