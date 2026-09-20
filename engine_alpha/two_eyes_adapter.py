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

#: Keys downstream reads with square brackets — a missing one is a KeyError in
#: the middle of a night's write, not a None in a column. A fire row is whole
#: in these or it is not a row. Surveyed, not guessed: the display names are
#: indexed by `output/terminal.py` and `output/dashboard.py`, the underscored
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

#: Columns that are whole numbers by contract. A float here is stored and then
#: compared against an int forever after.
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

    box, lps = read.parent, read.lps
    unit = box.daily_range or 0.0
    width = float(box.resistance.price - box.support.price)
    base_end = box.end_day or read.as_of
    result = {
        "Ticker": read.ticker,
        "Tier": "",              # stage 7 grades; an empty grade is not a made-up one
        "Setup": read.state,
        "Score": 0.0,
        "Current Price": round(float(box.resistance.price), 2),
        "Base Len": _days(box.opened_day, base_end),
        "Box Width": width,
        "Touches": 0,
        "ATR Ratio": (width / unit) if unit else 0.0,
        "LPS Length": _days(lps.start_day, lps.end_day),
        "Breach Days": 0,
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
        "_base_len": _days(box.opened_day, base_end),
        "_lps_len": _days(lps.start_day, lps.end_day),
        "_lps_offset": 0,
        "_r_anchor_bar": 0,
        "_s_anchor_bar": 0,
        "_r_touches": 0,
        "_s_touches": 0,
        "_vol_contraction": 0.0,
        "_tightness_ratio": 0.0,
        # The grade is stage 7's. None is "not measured" — the archive stores
        # that as empty, never as a made-up number — but the KEY must exist,
        # because the scan sorts its results by this column.
        "_ta_grade": None,
        "_ta_grade_raw": None,
        # What the old engine has no word for, carried so the new reader's own
        # facts survive the crossing rather than being rebuilt from prices.
        "_two_eyes_r_anchor_date": box.resistance.anchor_day.isoformat(),
        "_two_eyes_s_anchor_date": box.support.anchor_day.isoformat(),
        "_two_eyes_box_end_date": box.end_day.isoformat() if box.end_day else None,
        "_two_eyes_daily_range": box.daily_range,
        "_two_eyes_lps_read_against": lps.read_against,
        "_two_eyes_has_mini": read.mini is not None,
    }
    for key in WHOLE_NUMBER_KEYS:
        result[key] = int(result[key])
    missing = [k for k in REQUIRED_KEYS + SILENTLY_LOST_KEYS if k not in result]
    if missing:                         # a fire row is whole or it is not a row
        raise KeyError(f"the two-eyes adapter built a fire row missing {missing}")
    return result


def _days(start, end) -> int:
    """Calendar days between two days, floored at zero — a placeholder count
    until stage 5 rules how a box's life is measured in trading days."""
    if start is None or end is None:
        return 0
    return max(0, (end - start).days)


def fill_watch(read: Read, watch: Optional[dict]) -> None:
    """Put the new reader's read into the watch sink the screen reads.

    The chart-state page types its state word off the ONE paying read rather
    than walking the chart a second time, so the sink has to carry the word.
    """
    if watch is None:
        return
    watch["two_eyes"] = True
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
