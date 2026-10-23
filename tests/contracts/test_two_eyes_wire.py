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
def _read(*, grade=True, width_frac=None, mini=True, score=92.3, letter="S", spring_day=None):
    from engine_alpha.two_eyes import record

    d = dt.date
    events = () if spring_day is None else (record.Event(kind=record.SPRING, day=spring_day, price=89.0),)
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
    the_grade = record.Grade(score=score, letter=letter, empty_days=2, base_days=41, holds=True) if grade else None
    return record.Read(ticker="TWOEYES", as_of=d(2026, 3, 6), boxes=tuple(boxes), lps=lps, state="fired",
                       close=97.1, grade=the_grade, events=events)


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
         "opened": "2026-01-05", "end": None, "ranges_tall": 5.0},
        {"role": "mini", "r": 98.0, "r_day": "2026-02-10", "s": 94.0, "s_day": "2026-02-12",
         "opened": "2026-02-10", "end": None, "ranges_tall": pytest.approx(4.0 / 1.5)},
    ]
    assert block["lps"] == {"against": "mini", "how": "on", "start": "2026-03-02", "end": "2026-03-06",
                            "trigger": 98.4}
    assert block["state"] == "fired" and block["state_days"] is None
    assert block["grade"] == {"score": 92.3, "letter": "S", "empty_days": 2, "base_days": 41, "holds": True}
    assert block["events"] == [], "a read that named nothing carries an empty story, never a missing one"
    json.dumps(block, allow_nan=False)              # the wire's own test: days as text, plain numbers


def test_the_block_carries_the_story_the_reader_named():
    """The grade panel tells the story left to right (Tue 13/10/2026): each word with its day, its price, its
    swing's first and last day, its size in daily ranges and whether it has settled, oldest first."""
    from engine_alpha.two_eyes import record
    from engine_alpha.two_eyes_adapter import to_result

    d = dt.date
    events = (
        record.Event(kind=record.SPRING, day=d(2026, 2, 10), price=89.0, first_day=d(2026, 2, 6),
                     last_day=d(2026, 2, 13), size=0.75, committed=True, known_day=d(2026, 2, 13)),
        record.Event(kind=record.SOS, day=d(2026, 2, 24), price=101.5, first_day=d(2026, 2, 17),
                     last_day=d(2026, 2, 24), size=3.2, committed=False, note="no LPS follows it yet"),
        record.Event(kind=record.PHASE_D, day=d(2026, 2, 17), price=93.0, committed=True, note="SOS"),
    )
    read = _read()
    read = record.Read(ticker=read.ticker, as_of=read.as_of, boxes=read.boxes, lps=read.lps, state=read.state,
                       close=read.close, grade=read.grade, events=events)
    block = to_result(read)["_wire_two_eyes"]
    assert block["events"] == [
        {"kind": "spring", "day": "2026-02-10", "price": 89.0, "first": "2026-02-06", "last": "2026-02-13",
         "size": 0.75, "committed": True, "note": None},
        {"kind": "SOS", "day": "2026-02-24", "price": 101.5, "first": "2026-02-17", "last": "2026-02-24",
         "size": 3.2, "committed": False, "note": "no LPS follows it yet"},
        {"kind": "Phase D", "day": "2026-02-17", "price": 93.0, "first": None, "last": None,
         "size": None, "committed": True, "note": "SOS"},
    ]
    json.dumps(block, allow_nan=False)


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


def _payload(monkeypatch, row: dict, frame=None) -> dict:
    from core.pipeline.screening import dashboard

    monkeypatch.setattr(dashboard, "_sector_etf_for_ticker", lambda *_a: None)
    chart_data = dashboard._extract_chart_data(_frame() if frame is None else frame, pd.DataFrame([row]),
                                               [row["Ticker"]])
    assert row["Ticker"] in chart_data, "the chart was dropped"
    return chart_data[row["Ticker"]]


#: What a two-eyes row carries to the screen: the candles (the frame's own), the verdicts every row carries, the
#: sector, the advisory facts the scan attaches to any row, the leadership read and the volume at key points (go-live
#: plan task 3: the stock's read, as an old fire carries it), the stock's ADR (Tue 13/10/2026: the grid's ADR cell
#: showed a dash on every new-reader chart), the grade's number, and THE block. Exact on purpose: a key added or
#: dropped here is a deliberate edit, never drift.
TWO_EYES_WIRE_KEYS = (
    "R", "S",
    "adr_pct",
    "base_len",
    "candles",
    "days_to_earnings",
    "dollar_volume_50d",
    "fund_earnings_surprise", "fund_eps_growth_accel", "fund_eps_growth_yoy", "fund_grade", "fund_grade_score",
    "fund_quarter_end", "fund_sales_growth_yoy", "fund_sheet",
    "lps_volume_ratio",
    "market_cap",
    "monthly_box", "monthly_candles", "monthly_volumes",
    "price",
    "rs_line_latest", "rs_line_new_high", "rs_rating",
    "score",
    "sector_etf", "sector_name",
    "setup",
    "spring_volume_ratio",
    "stage2_52w_low_pct", "stage2_ma200_slope_1m_pct", "stage2_trend_pass_count",
    "ta_grade",
    "tier",
    "trigger",
    "two_eyes",
    "volumes",
    "weekly_box", "weekly_candles", "weekly_volumes",
)

#: The leadership read on the card (the RS rating, the trend template and its two stage measures, the dollar volume):
#: the STOCK, which does not depend on the reader, so a new-reader fire carries it exactly as an old one does.
LEADERSHIP_KEYS = ("rs_rating", "stage2_trend_pass_count", "stage2_52w_low_pct", "stage2_ma200_slope_1m_pct",
                   "dollar_volume_50d")


def test_a_two_eyes_fire_keeps_its_chart_and_carries_the_one_block(monkeypatch):
    """The old payload cast the old engine's bar counts with int(), which a two-eyes row leaves empty: the chart was
    dropped by its own try, silently, the moment the row had a tier (the build log's note of task 6)."""
    from engine_alpha.two_eyes_adapter import to_result

    result = to_result(_read())
    chart = _payload(monkeypatch, result)
    assert chart["two_eyes"] == result["_wire_two_eyes"]
    assert (chart["tier"], chart["score"], chart["ta_grade"]) == ("S", pytest.approx(92.3), 92.3)
    assert (chart["R"], chart["S"], chart["trigger"], chart["price"]) == (100.0, 90.0, 98.4, 97.1)


def test_every_surface_shows_one_grade_number(monkeypatch):
    """One row, ONE number: the list's chip and the glance read ``ta_grade``, the story panel reads the block's grade,
    the archive keeps the score. A grade rounded at the wire beside its unrounded twin split the real night of Thu
    08/10/2026 (NVEC, 500/11: 46 on the card, 45 in the panel), as it would any score whose fraction sits in
    [.45, .5) (the task-15 blind check's P1)."""
    from engine_alpha.two_eyes_adapter import to_result

    result = to_result(_read(score=500 / 11, letter="B"))
    chart = _payload(monkeypatch, result)
    assert chart["ta_grade"] == chart["score"] == chart["two_eyes"]["grade"]["score"] == 45.5
    assert result["Score"] == result["_ta_grade"] == 45.5


def test_parent_length_counts_real_sessions_even_when_the_grade_window_ends_earlier(monkeypatch):
    from core.pipeline.screening.dashboard import _two_eyes_base_length
    from engine_alpha.two_eyes_adapter import to_result

    frame = _frame()
    read = _read()
    block = to_result(read)['_wire_two_eyes']
    block['boxes'][0]['opened'] = '2026-01-05'
    block['boxes'][0]['end'] = '2026-02-10'
    expected = len(frame.loc['2026-01-05':'2026-02-10'])
    assert _two_eyes_base_length(block, frame) == expected
    assert expected != read.grade.base_days
    block['boxes'][0]['opened'] = '2025-12-01'
    assert _two_eyes_base_length(block, frame) is None, 'partial history is not a measured length'


def test_the_new_reader_chart_carries_its_parent_session_count(monkeypatch):
    from engine_alpha.two_eyes_adapter import to_result

    row = to_result(_read())
    chart = _payload(monkeypatch, row)
    assert chart['base_len'] == len(_frame().loc['2026-01-05':])


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
# The leadership read and the volume at key points (go-live plan task 3)      #
# --------------------------------------------------------------------------- #
_OLD_ROW = {"Ticker": "TWOEYES", "Tier": "A", "Score": 100, "Setup": "LPS", "Current Price": 97.1,
            "_trigger_price": 98.4, "_R": 100.0, "_S": 90.0, "_base_len": 8, "_lps_len": 2, "_lps_offset": 0,
            "_r_anchor_bar": 2, "_s_anchor_bar": 3}
#: What the scan attaches to a fire (the RS rating, after the read) and what the old chain measures on the stock (the
#: trend template): the same on both rows, as on one chart read by either reader.
_STOCK = {"_rs_rating": 84.21, "_stage2_trend_pass_count": 6, "_stage2_52w_low_pct": 0.8412,
          "_stage2_ma200_slope_1m_pct": -1.25}


def test_a_two_eyes_fire_carries_the_leadership_read_exactly_as_an_old_fire_does(monkeypatch):
    """Today a new-reader fire skipped the whole leadership block on the live screen (the old shape's `continue`).
    The stock's read does not depend on the reader: the same row facts and the same frame give the same cells."""
    from engine_alpha.two_eyes_adapter import to_result

    old = _payload(monkeypatch, {**_OLD_ROW, **_STOCK})
    new = _payload(monkeypatch, {**to_result(_read()), **_STOCK})
    assert {k: new[k] for k in LEADERSHIP_KEYS} == {k: old[k] for k in LEADERSHIP_KEYS}
    assert new["stage2_trend_pass_count"] == 6 and new["rs_rating"] == 84.21
    assert new["dollar_volume_50d"] is not None, "the 50-day dollar volume is read off the frame, for either reader"


def test_a_two_eyes_fire_carries_the_adr_an_old_fire_of_the_same_frame_carries(monkeypatch):
    """Since the flip a new-reader fire carried no ADR: the archive stored `adr_pct` empty on every such row (the edge
    reads split fires into ADR thirds, and an empty row falls out of them silently) and the leadership grid's ADR cell
    showed a dash. The ADR is the stock's, not the setup's: his ALB, read by each reader through the one door on Tue
    07/04/2026 (a day both fire), carries ONE number on the row the archive writes and on the card, the old chain's
    own formula and window (4.99%), never a second one."""
    from core.calibration.replay import load_sealed_fixture
    from engine_alpha import reader

    frames, _ = load_sealed_fixture()
    alb = frames["ALB:2026-04-13"].loc[:pd.Timestamp("2026-04-07")]
    assert reader.which_reader() == reader.READER_NEW, "the switch is off: this test reads the new reader"
    new = reader.evaluate_ticker("ALB", alb)
    with reader.the_old_reader_answers():
        old = reader.evaluate_ticker("ALB", alb)
    assert isinstance(old, dict) and isinstance(new, dict), "each reader fires on his ALB that day"
    assert "_wire_two_eyes" in new and "_wire_two_eyes" not in old, "each fire is its own reader's"
    assert round(old["_adr_pct"], 2) == 4.99
    assert new.get("_adr_pct") == old["_adr_pct"], "the row the archive writes: the old fire's ADR, to the last digit"

    old_card, new_card = _payload(monkeypatch, old, alb), _payload(monkeypatch, new, alb)
    assert "two_eyes" in new_card and "two_eyes" not in old_card
    assert new_card.get("adr_pct") == old_card["adr_pct"] == old["_adr_pct"], "the card: the same number, unrounded"


def _quiet_frame():
    """130 trading days at 100 shares a day, his LPS pullback (Mon 02/03 to Fri 06/03/2026) at 50 and the spring
    (Tue 10/02/2026) at 300: so the 50 days ending on the LPS's last day hold 44 days at 100, the five LPS days and the
    spring, an average of 99, and the 50 ending on the spring average (49 x 100 + 300) / 50 = 104."""
    dates = pd.bdate_range("2025-10-01", periods=130, name="Date")
    volume = pd.Series(100.0, index=dates)
    volume[pd.Timestamp("2026-02-10")] = 300.0
    volume[pd.Timestamp("2026-03-02"):pd.Timestamp("2026-03-06")] = 50.0
    price = np.linspace(80, 99, len(dates))
    return pd.DataFrame({"Open": price, "High": price + 1, "Low": price - 1, "Close": price,
                         "Volume": volume.values}, index=dates)


def test_volume_at_key_points_is_read_on_the_new_readers_own_lps_and_spring_days(monkeypatch):
    """The LPS pullback: its five days' average (50) against the 50-day average ending on its last day (99) = 0.51x.
    The spring: its day (300) against the 50 days ending on it (104) = 2.88x. The old reader's own facts riding on
    the row (a dry-up of 0.9 and a spring on another day) are never read for a new-reader fire."""
    from engine_alpha.two_eyes_adapter import to_result

    row = {**to_result(_read(spring_day=dt.date(2026, 2, 10))),
           "_vol_contraction": 0.9, "_bin_c_event_date": "2026-01-15"}
    chart = _payload(monkeypatch, row, _quiet_frame())
    assert chart["lps_volume_ratio"] == 0.51
    assert chart["spring_volume_ratio"] == 2.88


def test_a_new_reader_fire_with_no_spring_shows_a_dash_never_the_old_readers_spring(monkeypatch):
    from engine_alpha.two_eyes_adapter import to_result

    row = {**to_result(_read()), "_bin_c_event_date": "2026-02-10"}
    chart = _payload(monkeypatch, row, _quiet_frame())
    assert chart["spring_volume_ratio"] is None, "no spring of its own: empty, which the card shows as a dash"
    assert chart["lps_volume_ratio"] == 0.51


def test_the_lps_window_and_the_spring_day_share_one_measure():
    """EC-3: one function reads the volume at a key point, a day or a run of days, against the 50 days ending on its
    last day; the old reader's spring day reads exactly what it always read."""
    from core.pipeline.screening import dashboard

    frame = _quiet_frame()
    assert dashboard._volume_vs_50d(frame, "2026-02-10") == 2.88
    assert dashboard._volume_vs_50d(frame, "2026-03-06", first_day="2026-03-02") == 0.51
    assert dashboard._volume_vs_50d(frame, "2026-03-06", first_day="2026-03-09") is None, "a window that ends first"
    assert dashboard._volume_vs_50d(frame, "2026-03-06", first_day="2024-01-02") is None, "a day not in the frame"


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
         "opened": "2026-01-05", "end": None, "ranges_tall": 5.0},
        {"role": "mini", "r": 196.0, "r_day": "2026-02-10", "s": 188.0, "s_day": "2026-02-12",
         "opened": "2026-02-10", "end": None, "ranges_tall": pytest.approx(4.0 / 1.5)},
    ], "the height in daily ranges is a ratio: the rescale onto today's candles leaves it as stored"
    assert block["lps"] == {"against": "mini"}
    assert block["grade"] == {"score": 92.3, "letter": "S"}
    assert "events" not in block, "the archive keeps no story: absent, so the panel says so, never an empty one"
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
