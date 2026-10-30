"""The stage read: where a stock is in its life cycle, read on its weekly chart (built Fri 16/10/2026).

The STOCK's read, never the setup's (docs/strategy_alpha.md, "Two reads, kept apart" and "The life cycle: the four
stages"): Minervini's four stages after Weinstein, 1 neglect, 2 advance, 3 top, 4 decline, and the week the current
stage-2 advance began. It is measure-only: shown and archived on a fire, never a gate, a score or a tier, and no
reader reads it. The weekly chart is where he and the book read the stage (*"minnervini lists his "stage" traits
from weekly charts"*, 2026-10-03).

The rules, as the book states its real-time checks and the base-count rule written from his five counts on
12/10/2026 (that rule and these forms are ours):

* The bars are weeks ending Friday, and only COMPLETED weeks: read mid-week, the stage stands on last week's close;
  read on the week's last trading session, that week counts. A stage that moved with every day's close would
  move back and forth inside one week.
* The average is the 40-week average of the weekly closes (Minervini's 200-day); it is rising when it stands
  above where it stood four weeks earlier (the template's month), falling when below.
* An ADVANCE week closes above a rising average and at least 30% over the 52-week low (the book waits for a rally
  of 25 to 30% off the 52-week low before it calls stage 2; the trend template's own 30%). A DECLINE week closes
  below a falling average.
* The stage is 2 on an advance week, and after one while the average still rises; 3 once the average stops
  rising after an advance; 4 on a decline week; 1 after a decline week until the next advance week, and with
  neither in view.
  So a close under a still-rising average is a pullback inside stage 2, and a rally over a still-falling average
  after a decline is the turn, stage 1 (his stage 1 to 2 transition, AMGN and FFIV, 2026-10-03), never stage 4.
* The advance began the week after the last weekly close under a 40-week average that is not rising (week over
  week): the start of the base-count rule written from his counts on 12/10/2026 (ours; the count it starts matched
  three of his five). It is said only in stage 2: in a top the average flattens and the closes under it restart
  the count week after week. When no such close sits in the frame read, the advance is older than the
  frame and its start is not said.

What it does NOT see, measured on the book's tops (2026-10-16): a top that comes before the average stops rising.
On all seven (Vicor, AMGN, Stryker, Bank of America, Crocs, DECK, Chipotle) the read goes from 2 straight to 4, the
average turning down only with the price already under it, so Vicor's climax top and Chipotle's topping base read 2
on every day the reader fired inside them; his topping-base signature (late, wider than the bases before it, the
sellers winning) is not read here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine_alpha import two_eyes_numbers as M
from engine_alpha.market_sessions import NYSE_BUSINESS_DAY

#: The facts this read gives, under the archive's names, each empty when not measured.
STAGE_FACTS = ("cycle_stage", "advance_start", "advance_weeks")

_WEEK = "W-FRI"


def _empty() -> dict:
    return {key: None for key in STAGE_FACTS}


def completed_weeks(daily: pd.DataFrame) -> pd.DataFrame:
    """The daily frame's weekly bars (weeks ending Friday: the week's high, low and last close), the forming week
    left out. The frame's last row is the read day; its week is complete when the next trading session falls in
    a later week, so a week whose Friday is a holiday is complete on its Thursday."""
    index = pd.DatetimeIndex(daily.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    bars = pd.DataFrame({"High": daily["High"].to_numpy(float), "Low": daily["Low"].to_numpy(float),
                         "Close": daily["Close"].to_numpy(float)}, index=index)
    weeks = bars.resample(_WEEK).agg({"High": "max", "Low": "min", "Close": "last"})
    weeks = weeks.dropna(subset=["High", "Low", "Close"])
    if len(weeks):
        read_day = index[-1].normalize()
        next_session = read_day + NYSE_BUSINESS_DAY
        if next_session.to_period(_WEEK) == read_day.to_period(_WEEK):
            weeks = weeks.iloc[:-1]
    return weeks


def stages(weeks: pd.DataFrame) -> list:
    """The stage of every completed week (1 to 4), None where the average or its month-back value is not there
    yet. A week's stage reads that week and the last advance or decline week before it, never a later week."""
    span, slope = int(M.STAGE_MA_WEEKS), int(M.STAGE_SLOPE_WEEKS)
    close = weeks["Close"].to_numpy(float)
    average = weeks["Close"].rolling(span).mean().to_numpy(float)
    low_52 = weeks["Low"].rolling(int(M.STAGE_LOW_WEEKS), min_periods=1).min().to_numpy(float)
    off_low = 1.0 + float(M.STAGE_OFF_LOW_MIN)
    out, last = [None] * len(weeks), None
    for i in range(slope, len(weeks)):
        now, before = average[i], average[i - slope]
        if not (np.isfinite(now) and np.isfinite(before)):
            continue
        rising, falling = now > before, now < before
        if close[i] > now and rising and close[i] >= off_low * low_52[i]:
            last = "advance"
        elif close[i] < now and falling:
            last = "decline"
            out[i] = 4
            continue
        if last == "advance":
            out[i] = 2 if rising else 3
        else:
            out[i] = 1
    return out


def advance_start(weeks: pd.DataFrame, upto: int):
    """The position of the week the advance began, as of the completed week ``upto``: the week after the last
    weekly close under a 40-week average that is not rising (the count rule of 12/10/2026). None when no such
    close sits in the weeks read; ``upto + 1`` when the week read itself closed under one (no advance yet)."""
    close = weeks["Close"].to_numpy(float)
    average = weeks["Close"].rolling(int(M.STAGE_MA_WEEKS)).mean().to_numpy(float)
    start = None
    for i in range(1, upto + 1):
        if np.isfinite(average[i]) and np.isfinite(average[i - 1]) \
                and close[i] < average[i] and average[i] <= average[i - 1]:
            start = i + 1
    return start


def read_stage(daily: pd.DataFrame) -> dict:
    """The stage read of one stock as of its frame's last day: ``cycle_stage`` (1 to 4), ``advance_start`` (the
    Friday of the week the current stage-2 advance began, ISO) and ``advance_weeks`` (completed weeks from that week
    to the week read, both counted), each None when not measured; the advance only in stage 2. Read the whole frame
    the scan holds (five years), never the reader's two-year window: a stage and an advance run for years. Never
    raises: a stock fact never costs a fire."""
    out = _empty()
    try:
        weeks = completed_weeks(daily)
        if len(weeks) <= int(M.STAGE_MA_WEEKS):
            return out
        stage = stages(weeks)[-1]
        out["cycle_stage"] = stage
        if stage == 2:
            last = len(weeks) - 1
            start = advance_start(weeks, last)
            if start is not None and start <= last:
                out["advance_start"] = weeks.index[start].date().isoformat()
                out["advance_weeks"] = last - start + 1
    except (KeyError, TypeError, ValueError, IndexError):
        return _empty()
    return out
