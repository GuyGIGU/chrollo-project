"""The new reader's record, spoken in the old engine's shape.

Task 5 of the two-eyes-reader build. The new reader answers a ``Read``; the
archive row, the wire, the board and the screen all speak the old result dict.
This is the ONE place those two vocabularies meet, so that when stages 1 to 7
fill the record in, nothing downstream changes shape again.

It deliberately sits OUTSIDE ``engine_alpha/two_eyes/``: that package is a leaf
and a test proves it imports nothing from the old chart reader. This file is
allowed to know both, and it is the only one.

**Three answers, exactly as the old reader has always given them**, because the
scan, the seed and the gates all branch on which of the three they got:

* a ``dict`` — a fire, whole in every key anybody indexes by hand;
* ``None`` — read, understood, not a setup (the skeleton's answer for every
  chart in the world today);
* ``EVAL_ERROR`` — the read fell over. This is the counted failure, and it is
  why a crash may never come back as "no lines": that sentence belongs to a
  chart that genuinely has none, and the night has to be able to tell a quiet
  refusal from a broken read.
"""
from __future__ import annotations

from typing import Optional

from engine_alpha.evaluation import EVAL_ERROR, WATCH_WIRE_STATES
from engine_alpha.two_eyes.record import NO_LINES, READ_FAILED, Read
from engine_alpha.two_eyes_archive import SCREEN_KEY, two_eyes_archive_values, two_eyes_screen_boxes

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


def to_result(read: Read):
    """A ``Read`` as the old engine's three answers.

    Returns ``EVAL_ERROR`` for a failed read, ``None`` for no setup, or a whole
    result dict for a fire.
    """
    if read.failed:
        return EVAL_ERROR
    if not read.fired:
        return None

    box, lps, grade = read.parent, read.lps, read.grade
    base_end = box.end_day or read.as_of
    result = {
        "Ticker": read.ticker,
        # EMPTY, not zero, for everything this reader does not measure yet —
        # and empty, not a different quantity, for a column whose meaning on
        # every old-reader row this reader does not share. A number stored in
        # either shape is indistinguishable from a measured one forever after.
        #
        # The tier and the score are the grade's (stage 7, task 14; build
        # task 15): its letter, and its 0-100 score. The old engine's tier
        # ladder — its 15%-of-price S ceiling among it — never runs here, so
        # nothing but the grade decides the letter. One placeholder survives:
        # a read whose grade fell over (a grade never costs a fire) keeps the
        # empty tier and the score 0.0, because the score column cannot be
        # empty. That IS a made-up number, recognisable by its empty tier;
        # the screen charts lettered tiers only. Recorded in docs/decisions.md
        # (2026-09-21, and the task-15 row) as the builder's default.
        "Tier": grade.letter if grade is not None else "",
        # The SETUP TYPE — LPS / REBOUND on every old-reader row — not the
        # screen's state word, which is a different vocabulary and rides the
        # watch sink to the screen. A fire of this reader is a box and its
        # last receding run: an LPS setup.
        "Setup": "LPS",
        "Score": float(grade.score) if grade is not None else 0.0,
        # The read day's real close. The resistance line stood in here once,
        # and the forward-returns backfill scales every trigger by this price.
        "Current Price": round(float(read.close), 2) if read.close is not None else None,
        # Trading bars on every old-reader row; this reader has not ruled how
        # a box's life is counted yet (stage 5), and calendar days would be a
        # second meaning in the same column.
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
        # sorts by: the new grade's score (the grade session's note for task
        # 15), on the same 0-100 scale; the engine version tells the two
        # readers' rows apart. None when the grade fell over — "not
        # measured", stored empty — but the KEY must exist, because the scan
        # sorts its results by this column. The old grade's raw sum and its
        # chapters are not this reader's: empty, never the score again.
        "_ta_grade": float(grade.score) if grade is not None else None,
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
    """The screen's block for a two-eyes fire (build task 15): days and resolved prices, nothing for the browser to
    work out. The boxes are the archive family's own, through its one shaper, so the scan's card and the archive's
    chart of the same row draw the same lines; the LPS, the state word and the grade are the record's."""
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
            "score": float(grade.score), "letter": grade.letter,
            "empty_days": int(grade.empty_days), "base_days": int(grade.base_days), "holds": bool(grade.holds)},
    }


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
