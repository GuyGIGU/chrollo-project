"""The box fix's one judgment (his "fix the box", Fri 17/10/2026): what a saved correction must be, stated
once and read by the write route. Pure: no database, no frame."""
from __future__ import annotations

import datetime as dt

__all__ = ["FIELDS", "normalize", "problems"]

#: The columns a fix carries, in the order the write copies them.
FIELDS = ("ticker", "scan_day", "resistance", "r_day", "support", "s_day", "reader_resistance", "reader_r_day",
          "reader_support", "reader_s_day", "reader_opened_day", "ruleset", "note")


def _day(value) -> bool:
    try:
        dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def normalize(data: dict) -> dict:
    """The identity as the row is saved under: the ticker upper-cased and stripped, the note stripped or None."""
    out = dict(data)
    out["ticker"] = (out.get("ticker") or "").strip().upper()
    note = (out.get("note") or "").strip()
    out["note"] = note or None
    out["ruleset"] = out.get("ruleset") or ""
    return out


def problems(data: dict) -> list:
    """Every reason this fix cannot be saved, in plain words; empty when it can. His two lines are a box the
    rule of the pair could read: resistance over support, each on a trading day at or before the scan day."""
    out = []
    if not data.get("ticker"):
        out.append("a fix needs a ticker")
    for name in ("scan_day", "r_day", "s_day"):
        if not _day(data.get(name)):
            out.append(f"{name} must be an ISO day")
    r, s = data.get("resistance"), data.get("support")
    if r is None or s is None or not (float(r) > float(s)):
        out.append("resistance must sit over support")
    elif float(s) <= 0:
        out.append("support must be a price over zero")
    if not out:
        scan = data["scan_day"]
        for name in ("r_day", "s_day"):
            if data[name] > scan:
                out.append(f"{name} must be at or before the scan day")
    for name in ("reader_r_day", "reader_s_day", "reader_opened_day"):
        if data.get(name) is not None and not _day(data[name]):
            out.append(f"{name} must be an ISO day or absent")
    return out
