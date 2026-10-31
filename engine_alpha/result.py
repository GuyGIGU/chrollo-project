"""The alpha reader's ``Read`` as the scan's result row, the archive columns and the screen block: a fire is a whole
result dict, a chart without a setup is ``None``, a failed read is ``EVAL_ERROR`` and never a chart with no lines.
"""
from __future__ import annotations

import json
from dataclasses import replace

from typing import Optional

from config import settings
from engine_alpha.gate import EVAL_ERROR
from engine_alpha.record import STATE_WORDS as WATCH_WIRE_STATES
from engine_alpha.record import NO_LINES, READ_FAILED, SPRING, Read, Step
from engine_alpha.archive import SCREEN_KEY, alpha_archive_values, alpha_screen_boxes, volume_vs_50d

#: Keys downstream indexes with square brackets (the terminal and dashboard writers, the payload, the seed path):
#: a fire row is whole in these or it is not a row.
REQUIRED_KEYS = (
    "Ticker", "Tier", "Setup", "Score", "Current Price",
    "Base Len", "Box Width", "Touches", "ATR Ratio", "LPS Length",
    "Breach Days", "_R", "_S", "_trigger_price",
    "_phase_b_start_date", "_lps_zone_end_date",
    "_base_len", "_lps_len", "_lps_offset", "_r_anchor_bar", "_s_anchor_bar",
    "_r_touches", "_s_touches", "_vol_contraction", "_tightness_ratio",
    "_ta_grade", "_ta_grade_raw",
)

#: Keys downstream reads with ``.get()``: the archive's sector-RS enrichment goes silently empty without them.
SILENTLY_LOST_KEYS = ("_base_date_start", "_base_date_end")

#: Columns that are whole numbers WHEN MEASURED; an unmeasured one is None, never 0.
WHOLE_NUMBER_KEYS = ("Base Len", "Touches", "LPS Length", "Breach Days",
                     "_base_len", "_lps_len", "_lps_offset",
                     "_r_anchor_bar", "_s_anchor_bar",
                     "_r_touches", "_s_touches")

#: The screen's vocabulary: his ten words, borrowed from the record, never copied.
STATE_WORDS = WATCH_WIRE_STATES


def to_state(read: Read) -> str:
    """The one word the screen shows for this read; a crashed read's own word is not on his table and never crosses."""
    if read.failed:
        return READ_FAILED
    if read.state not in STATE_WORDS:
        raise ValueError(
            f"the two-eyes reader answered {read.state!r}, which is not one of "
            f"his ten words: {STATE_WORDS}")
    return read.state


def stock_trend(frame) -> dict:
    """The stock's trend template, not the box's: the frame the door admitted, cut to the daily window, under the
    archive's ``_stage2_*`` names."""
    from engine_alpha.chart import _trim_to_period
    from engine_alpha.stock import distance_to_52w_high_pct, trend_template

    daily = _trim_to_period(frame, settings.DAILY_STRUCTURE_PERIOD)
    if daily.empty:
        return {}
    trend = trend_template(daily, dist_52w_high_pct=distance_to_52w_high_pct(daily["High"], daily["Close"].iloc[-1]))
    return {f"_{key}": value for key, value in trend.items()}


def stock_adr(frame) -> dict:
    """The stock's ADR% over ``ADR_WINDOW`` days of the daily window, under ``_adr_pct``: carried, never graded."""
    from engine_alpha.chart import _trim_to_period
    from engine_alpha.stock import adr_pct

    daily = _trim_to_period(frame, settings.DAILY_STRUCTURE_PERIOD)
    return {"_adr_pct": adr_pct(daily, settings.ADR_WINDOW)}


def stock_stage(frame) -> dict:
    """The stock's weekly stage and the week its advance began, read on the WHOLE frame (a stage runs for years), under
    the archive's names."""
    from engine_alpha.stock import read_stage

    return {f"_{key}": value for key, value in read_stage(frame).items()}


def _spring_day(read: Read) -> Optional[str]:
    """The day of the reader's own spring (its tip), or None; the screen reads the volume at that key point."""
    return next((event.day.isoformat() for event in read.events if event.kind == SPRING), None)


def graded_read(read: Read, frame=None, stage=None) -> Read:
    """Compose the trait grade once: the letter the integrity grade's, the score placed within it by his traits, the weekly
    stage given as ``stage`` or read off ``frame``. A grade never costs a fire: if composing fails, the integrity grade stands."""
    grade = read.grade
    if grade is None or not grade.clarity or grade.clarity.get("method"):
        return read
    from engine_alpha.grade import compose_grade

    if stage is None and frame is not None:
        try:
            stage = stock_stage(frame).get("_cycle_stage")
        except Exception:                        # the stage row stays unmeasured; the other traits read
            stage = None
    try:
        composed = compose_grade(grade, grade.clarity["facts"], stage=stage)
    except Exception as exc:
        step = Step("grade", f"the clarity grade could not be composed ({type(exc).__name__}: {exc}); "
                             "the integrity grade stands")
        return replace(read, grade=replace(grade, clarity=None), trail=read.trail + (step,))
    trail = tuple(replace(step, saying=(
        f"the technical grade: {composed.letter} ({composed.score:.0f}); {composed.clarity['summary']}; "
        f"under it, {step.saying}"
    )) if step.stage == "grade" else step for step in read.trail)
    return replace(read, grade=composed, trail=trail)


def to_result(read: Read, frame=None):
    """A ``Read`` as the scan's three answers: ``EVAL_ERROR`` for a failed read, ``None`` for no setup, a whole result
    dict for a fire; with ``frame`` (the chart the door admitted) the fire carries the stock's trend, ADR and stage too."""
    if read.failed:
        return EVAL_ERROR
    if not read.fired:
        return None

    # The stock's own reads, once; the stage is one of the grade's traits.
    stock = {} if frame is None else {**stock_trend(frame), **stock_adr(frame), **stock_stage(frame)}
    read = graded_read(read, stage=stock.get("_cycle_stage"))
    box, lps, grade = read.parent, read.lps, read.grade
    # Rounded ONCE to the wire's grade precision: the score, _ta_grade and the block carry this one number.
    score = round(float(grade.score), 1) if grade is not None else None
    base_end = box.end_day or read.as_of
    result = {
        "Ticker": read.ticker,
        # The grade's letter; "" when grading fell over (the screen charts lettered tiers only).
        "Tier": grade.letter if grade is not None else "",
        # The setup TYPE, not the screen's state word: a box and its last receding run is an LPS setup.
        "Setup": "LPS",
        "Score": score if score is not None else 0.0,
        # The read day's real close; the forward-returns backfill scales every trigger by it.
        "Current Price": round(float(read.close), 2) if read.close is not None else None,
        # The old columns this reader does not measure stay EMPTY, never zero: downstream indexes the keys.
        "Base Len": None,
        # The box's height as a fraction of its support, the column's own definition: measured.
        "Box Width": float((box.resistance.price - box.support.price)
                           / box.support.price),
        "Touches": None,
        # The ten-over-fifty-day range squeeze, not the box's height in ranges.
        "ATR Ratio": None,
        "LPS Length": None,
        "Breach Days": None,
        "_R": float(box.resistance.price),
        "_S": float(box.support.price),
        "_trigger_price": float(lps.trigger_price),
        "_phase_b_start_date": box.opened_day.isoformat(),
        "_lps_zone_end_date": lps.end_day.isoformat(),
        # The base window for the archive's sector-RS enrichment, read with .get(): absent, it would void silently.
        "_base_date_start": box.opened_day.isoformat(),
        "_base_date_end": base_end.isoformat() if base_end else None,
        # The seed path re-keys these into the archive's own columns, so the keys must exist.
        "_base_len": None,
        "_lps_len": None,
        "_lps_offset": None,
        "_r_anchor_bar": None,        # bar offsets die with the window; the
        "_s_anchor_bar": None,        # family carries the anchor DAYS instead
        "_r_touches": None,
        "_s_touches": None,
        "_vol_contraction": None,
        "_tightness_ratio": None,
        # The 0-100 score the screen shows and the scan sorts by: None when the grade fell over, but the KEY must exist.
        "_ta_grade": score,
        "_ta_grade_raw": None,
        # The reader's own facts under the archive family's OWN names, so they survive the crossing.
        **_box_family("parent", box),
        **_box_family("mini", read.mini),
        "_two_eyes_lps_read_against": lps.read_against,
        # The reader LOOKED: 1 or 0, never empty (empty is a row written by a reader that never looked).
        "_two_eyes_has_mini": read.mini is not None,
        "_two_eyes_clarity_json": json.dumps(grade.clarity, allow_nan=False) if grade and grade.clarity else None,
        # The screen's volume at key points reads the spring on this day; no archive column reads it.
        "_spring_date": _spring_day(read),
        # The LPS pullback's volume against the 50-day average on the block's own days: an archive fact.
        "_two_eyes_lps_volume_ratio": None if frame is None else volume_vs_50d(
            frame, lps.end_day.isoformat(), first_day=lps.start_day.isoformat()),
        **stock,
    }
    for key in WHOLE_NUMBER_KEYS:
        if result[key] is not None:        # whole when measured, empty when not
            result[key] = int(result[key])
    missing = [k for k in REQUIRED_KEYS + SILENTLY_LOST_KEYS if k not in result]
    if missing:                         # a fire row is whole or it is not a row
        raise KeyError(f"the two-eyes adapter built a fire row missing {missing}")
    result[SCREEN_KEY] = _wire_block(read, result)
    return result


def _wire_block(read: Read, result: dict) -> dict:
    """The screen's block for a fire: days and resolved prices, nothing for the browser to work out; the boxes through
    the archive family's one shaper, so the scan's card and the archive's chart draw the same lines."""
    lps, grade = read.lps, read.grade
    return {
        "boxes": alpha_screen_boxes(alpha_archive_values(result.get, prefixed=True)),
        "lps": {"against": lps.read_against, "how": lps.how,
                "start": lps.start_day.isoformat(), "end": lps.end_day.isoformat(),
                "trigger": float(lps.trigger_price)},
        "state": read.state,
        # The number that rides beside a word that counts days ("forming N of 15": N), never written into it.
        "state_days": read.state_days,
        "grade": None if grade is None else {
            "score": result["_ta_grade"], "letter": grade.letter,
            **({"clarity": grade.clarity} if grade.clarity is not None else {}),
            "empty_days": int(grade.empty_days), "base_days": int(grade.base_days), "holds": bool(grade.holds)},
        # Every word the reader named on the box shown, oldest first; scan-only, the archive keeps no event.
        "events": [_wire_event(event) for event in read.events],
    }


def _wire_event(event) -> dict:
    """One word of the story as the screen reads it: the word, its day and price, its swing's days, its size, settled or not, the note."""
    def day(value):
        return None if value is None else value.isoformat()
    return {"kind": event.kind, "day": event.day.isoformat(), "price": float(event.price),
            "first": day(event.first_day), "last": day(event.last_day),
            "size": None if event.size is None else float(event.size),
            "committed": bool(event.committed), "note": event.note or None}


def _box_family(role: str, box) -> dict:
    """One box as the archive family's ``_two_eyes_<role>_<part>`` keys; no box, no keys (that half is stored empty)."""
    if box is None:
        return {}
    return {
        f"_two_eyes_{role}_r_price": float(box.resistance.price),
        f"_two_eyes_{role}_r_anchor_date": box.resistance.anchor_day.isoformat(),
        f"_two_eyes_{role}_s_price": float(box.support.price),
        f"_two_eyes_{role}_s_anchor_date": box.support.anchor_day.isoformat(),
        f"_two_eyes_{role}_opened_date": box.opened_day.isoformat(),
        f"_two_eyes_{role}_end_date": box.end_day.isoformat() if box.end_day else None,
        f"_two_eyes_{role}_daily_range": box.daily_range,
    }


def fill_watch(read: Read, watch: Optional[dict]) -> None:
    """Put the read into the watch sink the screen reads: the chart-state page types its state word off this one read."""
    if watch is None:
        return
    watch["alpha"] = True
    # The record itself, for a page that wants the lines of a read that did not fire.
    watch["read"] = read
    if read.failed:
        # A crashed read leaves no word: its own is not on his table, and a bare why would read as "no lines".
        watch["failed"] = True
        watch["refusal"] = read.refusal
        return
    # Only a word from his table may go in here: the publisher raises on an unknown one.
    if read.state in STATE_WORDS:
        watch["state"] = read.state
