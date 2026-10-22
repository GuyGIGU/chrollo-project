"""Adapt the two-eyes ``Read`` to the scan, archive and screen result contract.

This adapter stays outside the reader's leaf package so that it can know the
legacy result shape. A fire returns a complete result dict, a chart without
a setup returns ``None``, and a failed read returns ``EVAL_ERROR``. A failure
must never appear as a chart with no lines.
"""
from __future__ import annotations

import json
from dataclasses import replace

from typing import Optional

from config import settings
from engine_alpha.evaluation import EVAL_ERROR, WATCH_WIRE_STATES
from engine_alpha.two_eyes.record import NO_LINES, READ_FAILED, SPRING, Read
from engine_alpha.two_eyes_archive import SCREEN_KEY, two_eyes_archive_values, two_eyes_screen_boxes, volume_vs_50d

#: Keys downstream reads with square brackets — a missing one is a KeyError in
#: the middle of a night's write, not a None in a column. A fire row is whole
#: in these or it is not a row. Surveyed, not guessed: the display names are
#: indexed by `core/pipeline/screening/terminal.py` and `core/pipeline/screening/dashboard.py`, the underscored
#: ones by the dashboard payload, the harness and the yardstick, and the seed
#: path re-keys `_base_len`, `_lps_len`, `_r_anchor_bar` and `_s_anchor_bar`
#: into the archive's own column names.
REQUIRED_KEYS = (
    "Ticker", "Tier", "Setup", "Score", "Current Price",
    "Base Len", "Box Width", "Touches", "ATR Ratio", "LPS Length",
    "Breach Days", "_R", "_S", "_trigger_price",
    "_phase_b_start_date", "_lps_zone_end_date",
    "_base_len", "_lps_len", "_lps_offset", "_r_anchor_bar", "_s_anchor_bar",
    "_r_touches", "_s_touches", "_vol_contraction", "_tightness_ratio",
    "_ta_grade", "_ta_grade_raw",
)

#: Keys downstream reads with ``.get()``. Their absence is not a crash — it is
#: worse, because nothing says anything: a computation quietly produces
#: nothing at all. The archive's sector-RS enrichment reads the base window
#: this way (`core/archive/writer.py`), so a fire row without these dates is
#: written with its RS-vs-sector column silently empty. The box knows its own
#: days, so it can say them.
SILENTLY_LOST_KEYS = ("_base_date_start", "_base_date_end")

#: Columns that are whole numbers by contract WHEN MEASURED. A float here is
#: stored and then compared against an int forever after; an unmeasured one is
#: None, never 0.
WHOLE_NUMBER_KEYS = ("Base Len", "Touches", "LPS Length", "Breach Days",
                     "_base_len", "_lps_len", "_lps_offset",
                     "_r_anchor_bar", "_s_anchor_bar",
                     "_r_touches", "_s_touches")

#: The screen's vocabulary — HIS ten words, borrowed from the one place that
#: owns them rather than copied. A second copy of a closed set is how two
#: parts of a system come to disagree about what a word means, and the
#: publisher raises on anything off the table.
STATE_WORDS = WATCH_WIRE_STATES


def to_state(read: Read) -> str:
    """The one word the screen shows for this read.

    A crashed read's own word (`READ_FAILED`) is NOT on his ten-word table and
    must never cross: the publisher raises on an unknown word. It does not
    need to, because a crashed read leaves here as the counted-failure
    sentinel long before a word is asked for — this only guards the seam.
    """
    if read.failed:
        return READ_FAILED
    if read.state not in STATE_WORDS:
        raise ValueError(
            f"the two-eyes reader answered {read.state!r}, which is not one of "
            f"his ten words: {STATE_WORDS}")
    return read.state


def stock_trend(frame) -> dict:
    """The stock's trend template, measured by the shared legacy functions.

    Not the setup's: it reads the stock, not the box, so a fire carries it whichever reader fired. Read by the old
    chain's OWN functions on the old chain's OWN frame (EC-3): ``frame`` is what the universe door admitted, cut to
    the daily window as ``evaluation._prepare_eval_frame_with_reason`` cuts it, the 52-week-high distance taken at
    its last close, then ``trend_template``. Under the archive's names (``_stage2_*``), exactly the old row's keys.
    """
    from engine_alpha.frames import _trim_to_period
    from engine_alpha.structure.metrics.indicators import distance_to_52w_high_pct, trend_template

    daily = _trim_to_period(frame, settings.DAILY_STRUCTURE_PERIOD)
    if daily.empty:
        return {}
    trend = trend_template(daily, dist_52w_high_pct=distance_to_52w_high_pct(daily["High"], daily["Close"].iloc[-1]))
    return {f"_{key}": value for key, value in trend.items()}


def stock_adr(frame) -> dict:
    """The stock's ADR%, its average daily range: the archive's volatility column (the edge reads split fires into
    ADR thirds) and the ADR cell of the big chart's leadership grid.

    The stock's, not the setup's, read as :func:`stock_trend` reads the trend: the old chain's OWN ``adr_pct`` over
    ``ADR_WINDOW`` days of the old chain's OWN frame (EC-3, one formula), so a chart both readers fire carries one
    ADR, under the old row's key (``_adr_pct``). Carried, never graded: the new reader's grade reads no ADR.
    """
    from engine_alpha.frames import _trim_to_period
    from engine_alpha.structure.metrics.indicators import adr_pct

    daily = _trim_to_period(frame, settings.DAILY_STRUCTURE_PERIOD)
    return {"_adr_pct": adr_pct(daily, settings.ADR_WINDOW)}


def _spring_day(read: Read) -> Optional[str]:
    """The day of the new reader's own spring (its tip), or None: the screen reads the volume at that key point on
    it. Its story names one spring at most."""
    return next((event.day.isoformat() for event in read.events if event.kind == SPRING), None)


def graded_read(read: Read) -> Read:
    """Compose the measured clarity once, outside the chart-reading leaf."""
    grade = read.grade
    if grade is None or not grade.clarity or grade.clarity.get("method"):
        return read
    from engine_alpha.scoring.clarity import compose_grade

    composed = compose_grade(grade, grade.clarity["facts"])
    trail = tuple(replace(step, saying=(
        f"the technical grade: {composed.letter} ({composed.score:.0f}); {composed.clarity['summary']}"
    )) if step.stage == "grade" else step for step in read.trail)
    return replace(read, grade=composed, trail=trail)


def to_result(read: Read, frame=None):
    """A ``Read`` as the old engine's three answers.

    Returns ``EVAL_ERROR`` for a failed read, ``None`` for no setup, or a whole
    result dict for a fire. ``frame``, when given, is the chart the universe
    door admitted: a fire then carries the stock's trend template
    (:func:`stock_trend`) and its ADR (:func:`stock_adr`), as an old-reader
    fire does.
    """
    if read.failed:
        return EVAL_ERROR
    if not read.fired:
        return None

    read = graded_read(read)
    box, lps, grade = read.parent, read.lps, read.grade
    # The grade's number, rounded ONCE to the wire's grade precision (one
    # decimal): the score, `_ta_grade` and the block all carry this one
    # number, so the list's chip, the story panel and the archive cannot
    # disagree.
    score = round(float(grade.score), 1) if grade is not None else None
    base_end = box.end_day or read.as_of
    result = {
        "Ticker": read.ticker,
        # EMPTY, not zero, for everything this reader does not measure yet —
        # and empty, not a different quantity, for a column whose meaning on
        # every old-reader row this reader does not share. A number stored in
        # either shape is indistinguishable from a measured one forever after.
        #
        # Only this reader's grade decides the tier and 0-100 score; the
        # legacy tier caps do not run here. If grading fails, the fire stays:
        # an empty tier identifies the 0.0 placeholder required by the score
        # column. The screen charts lettered tiers only.
        "Tier": grade.letter if grade is not None else "",
        # The SETUP TYPE — LPS / REBOUND on every old-reader row — not the
        # screen's state word, which is a different vocabulary and rides the
        # watch sink to the screen. A fire of this reader is a box and its
        # last receding run: an LPS setup.
        "Setup": "LPS",
        "Score": score if score is not None else 0.0,
        # The read day's real close. The resistance line stood in here once,
        # and the forward-returns backfill scales every trigger by this price.
        "Current Price": round(float(read.close), 2) if read.close is not None else None,
        # This column counts trading bars on legacy rows. Leave it empty
        # rather than substitute a calendar-day duration.
        "Base Len": None,
        # The box's height as a fraction of its support — the column's own
        # definition on every old-reader row — so this one IS measured.
        "Box Width": float((box.resistance.price - box.support.price)
                           / box.support.price),
        "Touches": None,
        # The ten-day over fifty-day range squeeze, which this reader does not
        # measure. The box's height in daily ranges is a different number,
        # and it lives in the family's own daily-range column.
        "ATR Ratio": None,
        "LPS Length": None,
        "Breach Days": None,
        "_R": float(box.resistance.price),
        "_S": float(box.support.price),
        "_trigger_price": float(lps.trigger_price),
        "_phase_b_start_date": box.opened_day.isoformat(),
        "_lps_zone_end_date": lps.end_day.isoformat(),
        # The base window, for the archive's sector-RS enrichment. It reads
        # these with `.get()`, so leaving them out costs no error and voids
        # the computation instead. Its other two inputs are the base's first
        # and last CLOSE, which this record does not carry — so RS-vs-sector
        # stays empty on a two-eyes row until it does. Said out loud rather
        # than filled with a zero, which would be a made-up price.
        "_base_date_start": box.opened_day.isoformat(),
        "_base_date_end": base_end.isoformat() if base_end else None,
        # The seed path re-keys these into the archive's own column names
        # (`_base_len` -> base_length, `_r_anchor_bar` -> r_anchor, …), so a
        # fire row without them writes NULLs into columns the scan fills.
        "_base_len": None,
        "_lps_len": None,
        "_lps_offset": None,
        "_r_anchor_bar": None,        # bar offsets die with the window; the
        "_s_anchor_bar": None,        # family carries the anchor DAYS instead
        "_r_touches": None,
        "_s_touches": None,
        "_vol_contraction": None,
        "_tightness_ratio": None,
        # The 0-100 grade the screen shows beside the letter and the scan
        # sorts by: the new grade's score on the same 0-100 scale; the engine
        # version tells the two readers' rows apart. None when the grade fell over — "not
        # measured", stored empty — but the KEY must exist, because the scan
        # sorts its results by this column. The old grade's raw sum and its
        # chapters are not this reader's: empty, never the score again.
        "_ta_grade": score,
        "_ta_grade_raw": None,
        # What the old engine has no word for, carried so the new reader's own
        # facts survive the crossing rather than being rebuilt from prices —
        # under the archive family's OWN names. A first version spoke names
        # of its own, so a real fire filled 2 of the family's 16 columns and
        # every producer-level test still passed.
        **_box_family("parent", box),
        **_box_family("mini", read.mini),
        "_two_eyes_lps_read_against": lps.read_against,
        # The new reader LOOKED, so this is 1 or 0 and never empty: empty is
        # kept for rows written by a reader that never looked.
        "_two_eyes_has_mini": read.mini is not None,
        "_two_eyes_clarity_json": json.dumps(grade.clarity, allow_nan=False) if grade and grade.clarity else None,
        # The screen's volume at key points reads the
        # LPS pullback on the block's own days and the spring on this one;
        # never the old reader's spring (`_bin_c_event_date`). No archive
        # column reads it: the archive family stores no event.
        "_spring_date": _spring_day(read),
        # The LPS pullback's volume against the 50-day average, on the block's
        # own days, by the panel's one measure: an archive fact (his word Mon
        # 12/10/2026, option A), empty when the frame is not there to read.
        "_two_eyes_lps_volume_ratio": None if frame is None else volume_vs_50d(
            frame, lps.end_day.isoformat(), first_day=lps.start_day.isoformat()),
        **({} if frame is None else {**stock_trend(frame), **stock_adr(frame)}),
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
    """The screen's block for a two-eyes fire: days and resolved prices, nothing for the browser to
    work out. The boxes are the archive family's own, through its one shaper, so the scan's card and the archive's
    chart of the same row draw the same lines; the LPS, the state word, the grade and the story are the record's."""
    lps, grade = read.lps, read.grade
    return {
        "boxes": two_eyes_screen_boxes(two_eyes_archive_values(result.get, prefixed=True)),
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
        # The story the grade panel tells left to right (Tue 13/10/2026, his "the Grade section ... is completely
        # broken"): every word the reader named on the box shown, oldest first. Scan-only: the archive keeps no
        # event, so the archive's chart of the same row says it has no story rather than an empty one.
        "events": [_wire_event(event) for event in read.events],
    }


def _wire_event(event) -> dict:
    """One word of the story as the screen reads it: the word, the day it points at and the price there, the first
    and last day of the swing that makes it, its size in the daily ranges the words are read in, whether it has
    settled, and the reader's own note (what opened the right side; an SOS no LPS follows yet)."""
    def day(value):
        return None if value is None else value.isoformat()
    return {"kind": event.kind, "day": event.day.isoformat(), "price": float(event.price),
            "first": day(event.first_day), "last": day(event.last_day),
            "size": None if event.size is None else float(event.size),
            "committed": bool(event.committed), "note": event.note or None}


def _box_family(role: str, box) -> dict:
    """One box as the archive family's keys (`engine_alpha/two_eyes_archive.py`
    reads them as ``_two_eyes_<role>_<part>``). No box, no keys — the family
    then stores that half as empty, which is the truth for a setup whose
    reader found no mini."""
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
    """Put the new reader's read into the watch sink the screen reads.

    The chart-state page types its state word off the ONE paying read rather
    than walking the chart a second time, so the sink has to carry the word.
    """
    if watch is None:
        return
    watch["two_eyes"] = True
    # The record itself, for a board or a page that wants the lines and the
    # LPS of a read that did not fire without reading the chart a second time.
    watch["read"] = read
    if read.failed:
        # A crashed read leaves NOTHING here. Its own word is not on his
        # table, and a bare `why` is worse than silence: the page's verdict
        # falls through to "no lines" and shows a broken read as a chart that
        # simply has none. The caller gets the sentinel instead.
        watch["failed"] = True
        watch["refusal"] = read.refusal
        return
    # Only a word from his table may go in here: the publisher raises on an
    # unknown one.
    if read.state in STATE_WORDS:
        watch["state"] = read.state
