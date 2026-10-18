"""The box fix's one judgment (his "fix the box", Fri 17/10/2026): what a saved correction must be, stated
once and read by the write route. Pure: no database, no frame."""
from __future__ import annotations

import datetime as dt

__all__ = ["FIELDS", "EVENT_FIELDS", "EVENT_KINDS", "EVENT_NAMES", "normalize", "problems", "normalize_events",
           "event_problems", "summary"]

#: The columns a fix carries, in the order the write copies them.
FIELDS = ("ticker", "scan_day", "resistance", "r_day", "support", "s_day", "reader_resistance", "reader_r_day",
          "reader_support", "reader_s_day", "reader_opened_day", "ruleset", "note")

#: The events he may place on a fixed box (Sat 18/10/2026), in his words. A spring and an upthrust point at ONE day
#: (the tip, the top); the SOS, an LPS, a former LPS and a span are a stretch of days; the mini is a small box with
#: its own two lines. `former_lps` is the entry that already happened before the reader's LPS; `span` is a stretch
#: he wants to name as one thing, with his label and no question asked.
EVENT_KINDS = ("spring", "upthrust", "sos", "lps", "former_lps", "span", "mini")
EVENT_NAMES = {"spring": "spring", "upthrust": "upthrust", "sos": "SOS", "lps": "LPS", "former_lps": "former LPS",
               "span": "span", "mini": "mini"}
#: The columns an event carries, in the order the write copies them.
EVENT_FIELDS = ("kind", "first_day", "last_day", "price", "band_high", "band_low", "label")


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


def normalize_events(events: list) -> list:
    """Each event as it is saved: the kind stripped and lower-cased, the days ordered (a click in either order), the
    label stripped or None, the band ordered high over low."""
    out = []
    for raw in events or []:
        event = dict(raw)
        event["kind"] = (event.get("kind") or "").strip().lower()
        first, last = event.get("first_day"), event.get("last_day") or event.get("first_day")
        if first is not None and last is not None and str(last) < str(first):
            first, last = last, first
        event["first_day"], event["last_day"] = first, last
        hi, lo = event.get("band_high"), event.get("band_low")
        if hi is not None and lo is not None and float(hi) < float(lo):
            hi, lo = lo, hi
        event["band_high"], event["band_low"] = hi, lo
        label = (event.get("label") or "").strip()
        event["label"] = label or None
        out.append({name: event.get(name) for name in EVENT_FIELDS})
    return out


def event_problems(events: list, scan_day) -> list:
    """Every reason these events cannot be saved on a fix, in plain words; empty when they can. An event is one of
    his kinds, on trading days at or before the scan day; a mini has two lines, the higher over the lower."""
    out = []
    for n, event in enumerate(events or [], start=1):
        who = f"event {n}"
        if event.get("kind") not in EVENT_KINDS:
            out.append(f"{who}: {event.get('kind')!r} is not one of {', '.join(EVENT_KINDS)}")
        for name in ("first_day", "last_day"):
            if not _day(event.get(name)):
                out.append(f"{who}: {name} must be an ISO day")
        if _day(event.get("last_day")) and _day(scan_day) and str(event["last_day"]) > str(scan_day):
            out.append(f"{who}: last_day must be at or before the scan day")
        if event.get("kind") == "mini":
            hi, lo = event.get("band_high"), event.get("band_low")
            if hi is None or lo is None or not (float(hi) > float(lo)):
                out.append(f"{who}: a mini needs its two lines, the higher over the lower")
        for name in ("price", "band_high", "band_low"):
            value = event.get(name)
            if value is not None and float(value) <= 0:
                out.append(f"{who}: {name} must be a price over zero")
    return out


def _rails_moved(fix: dict) -> bool:
    """Whether his two lines differ from the pair the reader showed, to the cent (no reader pair: they do)."""
    r, s = fix.get("reader_resistance"), fix.get("reader_support")
    if r is None or s is None:
        return True
    return abs(float(fix["resistance"]) - float(r)) >= 0.005 or abs(float(fix["support"]) - float(s)) >= 0.005


def summary(fix: dict, events: list) -> str:
    """ONE sentence the lens shows for a fixed box (EC-28: the judgment crosses the wire resolved; the frontend
    only draws it): when it was fixed and what — the rails, the events by name in the order they happened, or
    both; a fix that kept the reader's pair and placed no event says so."""
    when = fix.get("updated_at") or fix.get("created_at")
    if isinstance(when, (dt.datetime, dt.date)):
        when = when.strftime("%d/%m/%Y")
    else:
        try:
            when = dt.date.fromisoformat(str(when)[:10]).strftime("%d/%m/%Y")
        except ValueError:
            when = str(when or "")
    parts = ["rails"] if _rails_moved(fix) else []
    if events:
        names = []
        for event in sorted(events, key=lambda e: (str(e.get("first_day")), str(e.get("kind")))):
            name = EVENT_NAMES.get(event.get("kind"), str(event.get("kind")))
            if event.get("kind") == "span" and event.get("label"):
                name = f'span "{event["label"]}"'
            names.append(name)
        parts.append(f"{len(events)} event{'' if len(events) == 1 else 's'}: {', '.join(names)}")
    what = " + ".join(parts) if parts else "the box as the reader drew it"
    return f"fixed {when}: {what}"
