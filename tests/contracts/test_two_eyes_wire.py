"""The screen block (task 15 of the two-eyes-reader build): what a two-eyes fire carries to the screen.

The plan's Done-when: *"the wire carries dates and resolved prices and the browser only locates and draws; old
families the new reader leaves empty read "not carried", never as an old-era row"*. So a two-eyes row reaches the
screen as ONE dated block (its boxes with their roles, the LPS and the box it was read against, the state word,
the grade) beside the verdicts every row carries (the lines, the tier, the score, the trigger), and NOTHING of the
old engine's families: a key the new reader does not fill is absent, never a null that a panel reads as "this row
predates the read", never a zero that reads as measured.

The scan's wire and the archive's chart are two producers of the same block; one shaper builds the boxes for both
from the archive family's own values, so they cannot drift apart.

And the adapter's score and tier are the grade's now (task 14 built it; the grade session's note for this task):
the dark placeholder stays only where the grade could not be read.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
for _p in (str(ROOT), str(ROOT / "webapp" / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --------------------------------------------------------------------------- #
# A two-eyes fire, built by hand: a parent, a mini, an LPS read against the mini, a grade                          #
# --------------------------------------------------------------------------- #
def _read(*, grade=True, width_frac=None, mini=True):
    from engine_alpha.two_eyes import record

    d = dt.date
    R, S = 100.0, 90.0
    if width_frac is not None:                       # a box this many times its support tall
        R = S * (1.0 + width_frac)
    boxes = [record.Box(resistance=record.Line(R, d(2026, 1, 5)), support=record.Line(S, d(2026, 1, 7)),
                        opened_day=d(2026, 1, 5), daily_range=2.0, role=record.ROLE_PARENT)]
    if mini:
        boxes.append(record.Box(resistance=record.Line(98.0, d(2026, 2, 10)), support=record.Line(94.0, d(2026, 2, 12)),
                                opened_day=d(2026, 2, 10), daily_range=1.5, role=record.ROLE_MINI))
    lps = record.Lps(d(2026, 3, 2), d(2026, 3, 6), record.ROLE_MINI if mini else record.ROLE_PARENT,
                     trigger_price=98.4, how="on" if mini else None)
    the_grade = record.Grade(score=92.3, letter="S", empty_days=2, base_days=41, holds=True) if grade else None
    return record.Read(ticker="TWOEYES", as_of=d(2026, 3, 6), boxes=tuple(boxes), lps=lps, state="fired",
                       close=97.1, grade=the_grade)


# --------------------------------------------------------------------------- #
# The adapter: the score and the tier are the grade's                          #
# --------------------------------------------------------------------------- #
def test_the_score_and_the_tier_are_the_grades():
    from engine_alpha.two_eyes_adapter import to_result

    result = to_result(_read())
    assert result["Score"] == pytest.approx(92.3) and result["Tier"] == "S"
    # The 0-100 grade the screen shows beside the letter and sorts by (the grade session's note for this task).
    assert result["_ta_grade"] == pytest.approx(92.3)
    # The old grade's raw sum is not this reader's: empty, never the new score a second time.
    assert result["_ta_grade_raw"] is None


def test_a_read_whose_grade_fell_over_keeps_the_dark_placeholder():
    """A grade never costs a fire: the read stands with no grade, and the score column cannot be empty."""
    from engine_alpha.two_eyes_adapter import to_result

    result = to_result(_read(grade=False))
    assert (result["Score"], result["Tier"], result["_ta_grade"]) == (0.0, "", None)
    assert result["_wire_two_eyes"]["grade"] is None


def test_the_old_engines_price_ceiling_never_touches_the_new_letter():
    """The OLD engine caps S at a box 15% of its price tall (it alone held SIMO at A on Fri 02/10/2026). The new
    reader's letter is its grade's, whatever the box's height."""
    from engine_alpha.two_eyes_adapter import to_result

    result = to_result(_read(width_frac=0.30))
    assert result["Box Width"] == pytest.approx(0.30)
    assert result["Tier"] == "S"


# --------------------------------------------------------------------------- #
# The adapter: the ONE dated block the screen reads                             #
# --------------------------------------------------------------------------- #
def test_the_block_carries_dates_and_prices_and_nothing_to_work_out():
    from engine_alpha.two_eyes_adapter import to_result

    block = to_result(_read())["_wire_two_eyes"]
    assert block["boxes"] == [
        {"role": "parent", "r": 100.0, "r_day": "2026-01-05", "s": 90.0, "s_day": "2026-01-07",
         "opened": "2026-01-05", "end": None},
        {"role": "mini", "r": 98.0, "r_day": "2026-02-10", "s": 94.0, "s_day": "2026-02-12",
         "opened": "2026-02-10", "end": None},
    ]
    assert block["lps"] == {"against": "mini", "how": "on", "start": "2026-03-02", "end": "2026-03-06",
                            "trigger": 98.4}
    assert block["state"] == "fired" and block["state_days"] is None
    assert block["grade"] == {"score": 92.3, "letter": "S", "empty_days": 2, "base_days": 41, "holds": True}
    json.dumps(block, allow_nan=False)              # the wire's own test: days as text, plain numbers


def test_the_screens_boxes_are_the_archive_familys_own():
    """One shaper, one family: the boxes on the scan's wire are the boxes the archive stores, shaped by the same
    function the archive's chart uses."""
    from engine_alpha.two_eyes_adapter import to_result
    from engine_alpha.two_eyes_archive import two_eyes_archive_values, two_eyes_screen_boxes

    result = to_result(_read())
    assert result["_wire_two_eyes"]["boxes"] == two_eyes_screen_boxes(
        two_eyes_archive_values(result.get, prefixed=True))


def test_the_screen_draws_no_earlier_box():
    """Ours (task 15): an earlier box is each night's own telling (the known limit) and the archive keeps none."""
    from engine_alpha.two_eyes import record
    from engine_alpha.two_eyes_adapter import to_result

    read = _read(mini=False)
    earlier = record.Box(resistance=record.Line(120.0, dt.date(2025, 9, 1)), support=record.Line(110.0, dt.date(2025, 9, 3)),
                         opened_day=dt.date(2025, 9, 1), end_day=dt.date(2025, 12, 1), daily_range=3.0,
                         role=record.ROLE_EARLIER)
    read = record.Read(ticker=read.ticker, as_of=read.as_of, boxes=(earlier,) + read.boxes, lps=read.lps,
                       state=read.state, close=read.close, grade=read.grade)
    assert [b["role"] for b in to_result(read)["_wire_two_eyes"]["boxes"]] == ["parent"]


# --------------------------------------------------------------------------- #
# The scan's wire: one additive block, the chart kept, the old families not carried                              #
# --------------------------------------------------------------------------- #
def _frame():
    dates = pd.date_range("2026-01-01", periods=60, freq="B", name="Date")
    return pd.DataFrame({
        "Open": np.linspace(90, 99, len(dates)), "High": np.linspace(91, 100, len(dates)),
        "Low": np.linspace(89, 98, len(dates)), "Close": np.linspace(90, 99, len(dates)),
        "Volume": np.linspace(1000, 1100, len(dates)),
    }, index=dates)


def _payload(monkeypatch, row: dict) -> dict:
    from core.pipeline.screening import dashboard

    monkeypatch.setattr(dashboard, "_sector_etf_for_ticker", lambda *_a: None)
    chart_data = dashboard._extract_chart_data(_frame(), pd.DataFrame([row]), [row["Ticker"]])
    assert row["Ticker"] in chart_data, "the chart was dropped"
    return chart_data[row["Ticker"]]


#: What a two-eyes row carries to the screen: the candles (the frame's own), the verdicts every row carries, the
#: sector, the advisory facts the scan attaches to any row, the grade's number, and THE block. Exact on purpose: a
#: key added or dropped here is a deliberate edit, never drift.
TWO_EYES_WIRE_KEYS = (
    "R", "S",
    "candles",
    "days_to_earnings",
    "fund_earnings_surprise", "fund_eps_growth_accel", "fund_eps_growth_yoy", "fund_sales_growth_yoy",
    "monthly_box", "monthly_candles", "monthly_volumes",
    "price",
    "rs_line_latest", "rs_line_new_high", "rs_rating",
    "score",
    "sector_etf", "sector_name",
    "setup",
    "ta_grade",
    "tier",
    "trigger",
    "two_eyes",
    "volumes",
    "weekly_box", "weekly_candles", "weekly_volumes",
)


def test_a_two_eyes_fire_keeps_its_chart_and_carries_the_one_block(monkeypatch):
    """The old payload cast the old engine's bar counts with int(), which a two-eyes row leaves empty: the chart was
    dropped by its own try, silently, the moment the row had a tier (the build log's note of task 6)."""
    from engine_alpha.two_eyes_adapter import to_result

    result = to_result(_read())
    chart = _payload(monkeypatch, result)
    assert chart["two_eyes"] == result["_wire_two_eyes"]
    assert (chart["tier"], chart["score"], chart["ta_grade"]) == ("S", pytest.approx(92.3), 92.3)
    assert (chart["R"], chart["S"], chart["trigger"], chart["price"]) == (100.0, 90.0, 98.4, 97.1)


def test_the_old_families_are_not_carried_on_a_two_eyes_row(monkeypatch):
    """Absent, not null: a family the new reader does not fill says nothing about the row. A null here is what a
    panel reads as "this row predates the read"; the old sub-scores came over as zeros, measured-looking."""
    from engine_alpha.two_eyes_adapter import to_result

    chart = _payload(monkeypatch, to_result(_read()))
    assert tuple(sorted(chart)) == TWO_EYES_WIRE_KEYS


def test_an_old_reader_row_carries_no_block(monkeypatch):
    """Additive: the rows the old reader writes are the payload they always were."""
    row = {"Ticker": "AAA", "Tier": "A", "Score": 100, "Setup": "LPS", "Current Price": 11.2,
           "_trigger_price": 11.6, "_R": 11.5, "_S": 9.5, "_base_len": 8, "_lps_len": 2, "_lps_offset": 0,
           "_r_anchor_bar": 2, "_s_anchor_bar": 3}
    chart = _payload(monkeypatch, row)
    assert "two_eyes" not in chart and chart["base_len"] == 8


# --------------------------------------------------------------------------- #
# The archive's chart: the same block from the stored family                   #
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db():
    import archive_models
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _archive_row(db, **columns):
    import archive_models

    row = archive_models.SetupArchive(ticker="TWOEYES", scan_date="2026-03-06", setup_type="LPS", **columns)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _served_candles(monkeypatch):
    import domains.market_data.service as market_data

    index = pd.bdate_range(end=pd.Timestamp("2026-04-01"), periods=200)
    frame = pd.DataFrame({"Open": 95.0, "High": 96.0, "Low": 94.0, "Close": 95.0, "Volume": 1000.0}, index=index)
    monkeypatch.setattr(market_data, "daily_candle_frame", lambda *a, **k: frame)
    return frame


def test_the_archives_chart_draws_a_two_eyes_row_from_its_days(db, monkeypatch):
    """The stored prices are rescaled onto today's candles exactly as the old lines are; the days need nothing."""
    from domains.archive import browse

    _served_candles(monkeypatch)
    row = _archive_row(
        db, tier="S", score=92.3, current_price=47.5,           # the close 95.0 now reads 2x the stored one
        r_level=100.0, s_level=90.0, trigger_price=98.4,
        two_eyes_parent_r_price=100.0, two_eyes_parent_r_anchor_date="2026-01-05",
        two_eyes_parent_s_price=90.0, two_eyes_parent_s_anchor_date="2026-01-07",
        two_eyes_parent_opened_date="2026-01-05", two_eyes_parent_daily_range=2.0,
        two_eyes_mini_r_price=98.0, two_eyes_mini_r_anchor_date="2026-02-10",
        two_eyes_mini_s_price=94.0, two_eyes_mini_s_anchor_date="2026-02-12",
        two_eyes_mini_opened_date="2026-02-10", two_eyes_mini_daily_range=1.5,
        two_eyes_lps_read_against="mini", two_eyes_has_mini=1)
    chart = browse.get_setup_chart(row.id, db=db)
    block = chart["two_eyes"]
    assert block["boxes"] == [
        {"role": "parent", "r": 200.0, "r_day": "2026-01-05", "s": 180.0, "s_day": "2026-01-07",
         "opened": "2026-01-05", "end": None},
        {"role": "mini", "r": 196.0, "r_day": "2026-02-10", "s": 188.0, "s_day": "2026-02-12",
         "opened": "2026-02-10", "end": None},
    ]
    assert block["lps"] == {"against": "mini"}
    assert block["grade"] == {"score": 92.3, "letter": "S"}
    assert chart["R"] == pytest.approx(200.0), "the old lines and the block's are rescaled alike"


def test_an_old_archive_row_draws_as_it_always_has(db, monkeypatch):
    """The legacy path: a row the old reader wrote (its family NULL) carries no block."""
    from domains.archive import browse

    _served_candles(monkeypatch)
    row = _archive_row(db, tier="A", score=71.0, current_price=95.0, base_length=40, lps_length=6,
                       r_level=99.0, s_level=91.0, r_anchor=3, s_anchor=7)
    chart = browse.get_setup_chart(row.id, db=db)
    assert "two_eyes" not in chart
    assert (chart["base_len"], chart["r_anchor"], chart["s_anchor"]) == (40, 3, 7)
