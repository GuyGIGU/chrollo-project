"""The boards' shared measurements against his drawings — pure, so the right answer can be reasoned, not observed.

These came out of the yardstick (task 3 of the two-eyes-reader build, retired with the old engine on
31/10/2026). The boards that compare the reader with his drawings (``core_board``, ``walk_board``,
``listing_gate``) share them: his last receding day, whether a read fired on it at his trigger, whether two
lines sit in his rail area, and the FIRST place a read leaves his drawing.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

#: How far his day may shift before a hit stops being a near miss. Three
#: trading days: his own redraws move a buy by a day or two, never a week.
DEFAULT_SHIFT_SESSIONS = 3

#: His rail area, as he taught it: about half a daily range either side.
RAIL_TOLERANCE_RANGES = 0.5


def _date(value) -> Optional[dt.date]:
    if value is None or isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def his_last_lps_day(setup: dict) -> Optional[dt.date]:
    """The end of his LAST run of receding days — the day before his buy."""
    spans = [setup.get("lps"), setup.get("lps2")]
    ends = [_date(s[1]) for s in spans if s]
    return max(ends) if ends else None


def _trigger_matches(setup: dict, read: dict) -> bool:
    """The engine found HIS buy: the same last receding day, priced off it.

    Measured across all of his drawings, without exception: his BUY day is
    the very next trading day after his last receding day, and his trigger
    price is exactly the HIGH of that last receding day. So his ``trigger``
    field is the day he would buy, while the engine's is the day its own run
    of receding days ended — they are one session apart by construction and
    must never be compared to each other.

    What makes a match, then, is that the engine ended its run on the day he
    ended his, and priced the buy off the same bar.
    """
    his_price = setup.get("trigger_price")
    if setup.get("trigger") is None or his_price is None:
        return False        # he marked no buy; nothing can match it
    if read.get("lps_end") != his_last_lps_day(setup):
        return False
    got = read.get("trigger_price")
    return got is not None and abs(float(got) - float(his_price)) < 0.005


def strict_hit(setup: dict, reads: list) -> bool:
    """Fired, on his last receding day, at his trigger. All three."""
    day = his_last_lps_day(setup)
    for read in reads:
        if read.get("day") == day:
            return bool(read.get("fired")) and _trigger_matches(setup, read)
    return False            # never read on his day at all


def chance_hit(setup: dict, reads: list, highs: dict,
               shift: int = DEFAULT_SHIFT_SESSIONS) -> bool:
    """The same read, with HIS day shifted — a near miss, never the headline.

    Shifting his day is not the same as reading on a different day. If his
    last receding day had been a session earlier or later, his trigger would
    have been THAT day's high — his own law, measured on all his drawings. So
    the shifted question is asked with a shifted trigger too: on day X near
    his, did the engine end its own run on X and price the buy at X's high?

    Keeping his real trigger while sliding only the reading day asks nothing
    new — it answers exactly what the headline already answered, which is how
    the first version of this column came to agree with it on all 70 reads.
    """
    day = his_last_lps_day(setup)
    if day is None or setup.get("trigger") is None:
        return False
    for read in reads:
        got = read.get("day")
        if got is None or abs((got - day).days) > shift:
            continue
        if not read.get("fired") or read.get("lps_end") != got:
            continue
        high = highs.get(got)
        price = read.get("trigger_price")
        if high is not None and price is not None and abs(float(price) - float(high)) < 0.005:
            return True
    return False


def rails_close(his_r: float, his_s: float, got_r, got_s, atr: float) -> bool:
    """Both of the engine's lines inside half a daily range of his."""
    if not atr or atr <= 0:
        raise ValueError("rails_close needs the drawn box's own daily range")
    if got_r is None or got_s is None:
        return False
    tolerance = RAIL_TOLERANCE_RANGES * float(atr)
    return (abs(float(got_r) - float(his_r)) <= tolerance
            and abs(float(got_s) - float(his_s)) <= tolerance)


def first_difference(setup: dict, read: Optional[dict], atr: float) -> Optional[str]:
    """The FIRST stage where the engine's read leaves his drawing.

    In his order — the lines, the day the box opened, whether it fired at all,
    then the buy. A later difference is downstream of an earlier one and tells
    him nothing he can act on, so only the first is reported.

    "No frame" is its own answer and must never be folded into "lines". When
    the universe door refuses his own last receding day, the engine never sees
    a chart at all; calling that "it drew the wrong lines" puts the chart in
    the board's largest bucket accused of something it was never given the
    chance to do.
    """
    if read is None:
        return "no read"
    if read.get("error"):
        return "no frame" if read["error"] == "no frame" else "the read crashed"
    rails = setup["rails_drawn"]
    if not rails_close(rails["R"], rails["S"], read.get("R"), read.get("S"), atr):
        return "lines"
    his_open = _date((setup.get("box") or [None])[0])
    if his_open is not None and read.get("box_start") != his_open:
        return "opening day"
    if not read.get("fired"):
        return "no fire"
    if not _trigger_matches(setup, read):
        return "trigger"
    return None
