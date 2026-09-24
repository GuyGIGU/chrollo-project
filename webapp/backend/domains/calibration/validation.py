"""The ONE mark-validity judgment (Calibration at Scale, Task 2).

Pure, import-anywhere: the marks CRUD router calls it at save time and the
agreement harness calls it at load time (EC-3 — write-side and read-side
validation must never drift). Returns a list of plain-English problems; empty
means valid. Callers decide the consequence (API → reject the request; harness
→ abort the batch naming the offender — a silently skipped mark shrinks every
agreement denominator).

The closed sets here are the AUTHORITATIVE, evolvable layer. The CHECK
constraints in ``models.py`` repeat them as frozen defence-in-depth DDL (an
existing SQLite table's CHECK does not change when this module does);
``tests/contracts/test_marks_validity.py`` pins the two layers against drift.
"""
from __future__ import annotations

import math
import re
from datetime import datetime

# Strict ticker grammar (security P1): bounded, uppercase alphabet, rejected —
# never sanitized. Shared by the candle endpoint, the CRUD boundary, and the
# harness; a ticker that failed this rule must never become an identity key or
# any part of a file path.
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

MARK_VERDICTS = ("box", "no_structure", "engine_wrong")
# The drawn-event vocabulary. sos + mini_consolidation + last_supper all added
# 2026-08-26 (the operator draws the piece he wants measured — decisions.md
# ground-truth ruling).
EVENT_TYPES = ("phase_c", "lps", "spring_test", "sos", "mini_consolidation",
               "last_supper")

# A mini-consolidation is a small BOX, so it alone carries a price band.
_BAND_TYPES = ("mini_consolidation",)
SOURCES = ("operator", "extraction")

_GEOMETRY_FIELDS = ("resistance", "support", "box_start_date", "box_end_date",
                    "r_anchor_date", "s_anchor_date", "first_rail")

FIRST_RAILS = ("resistance", "support")

# A mark's frame_digest is sha256-hex of the frozen frame it was drawn on —
# required provenance (the harness can replay nothing without it).
_DIGEST_SHAPE = re.compile(r"^[0-9a-f]{64}$")

_LABEL_MAX = 40
_NOTE_MAX = 500   # the operator's reason line — bounded so a stray paste can't bloat the ground-truth DB


_ISO_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_iso_date(value) -> datetime | None:
    """Strict single-format date: exactly YYYY-MM-DD, else None. The shape
    pre-check matters — strptime itself accepts unpadded months/days."""
    if not (isinstance(value, str) and _ISO_SHAPE.match(value)):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _positive_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def validate_mark(mark: dict) -> list[str]:
    """Judge one mark payload (model-shaped dict; events under ``events``)."""
    problems: list[str] = []
    get = mark.get

    ticker = get("ticker")
    if not (isinstance(ticker, str) and TICKER_RE.match(ticker)):
        problems.append(f"ticker {ticker!r} fails the strict grammar")

    as_of = parse_iso_date(get("as_of_date"))
    if as_of is None:
        problems.append(f"as_of_date {get('as_of_date')!r} is not YYYY-MM-DD")

    verdict = get("verdict")
    if verdict not in MARK_VERDICTS:
        problems.append(f"verdict {verdict!r} not in {MARK_VERDICTS}")

    if get("rails_source", "operator") not in SOURCES:
        problems.append(f"rails_source {get('rails_source')!r} not in {SOURCES}")

    # Point-in-time provenance is required, never backfilled. frame_digest
    # included: a mark without its frame's digest can never be replayed, so
    # it must be refused at birth, not silently excluded from every report.
    for field in ("data_regime", "engine_config_version"):
        if not (isinstance(get(field), str) and get(field).strip()):
            problems.append(f"{field} is missing")
    if not (isinstance(get("frame_digest"), str)
            and _DIGEST_SHAPE.match(get("frame_digest"))):
        problems.append(f"frame_digest {get('frame_digest')!r} is not a sha256 hex digest")
    if not _positive_number(get("anchor_close")):
        problems.append(f"anchor_close {get('anchor_close')!r} is not a positive number")

    # Label is an identity component (part of the unique key): bounded, and
    # already normalized (stripped, lowercased) by the write boundary.
    label = get("label", "")
    if not isinstance(label, str) or len(label) > _LABEL_MAX:
        problems.append(f"label must be a string of at most {_LABEL_MAX} chars")
    elif label != label.strip():
        problems.append("label carries leading/trailing whitespace")

    # Note is free operator text — bound it (same-app input still gets a ceiling)
    # so a stray large paste can't silently bloat the ground-truth DB + backups.
    note = get("note")
    if note is not None and (not isinstance(note, str) or len(note) > _NOTE_MAX):
        problems.append(f"note must be a string of at most {_NOTE_MAX} chars")

    knowable = get("knowable_from_date")
    if knowable is not None:
        kd = parse_iso_date(knowable)
        if kd is None:
            problems.append(f"knowable_from_date {knowable!r} is not YYYY-MM-DD")
        elif as_of is not None and kd > as_of:
            problems.append("knowable_from_date is after as_of_date")

    events = get("events") or []
    if verdict == "box":
        problems += _validate_box_geometry(mark, as_of)
        for i, event in enumerate(events):
            problems += _validate_event(event, i, as_of)
        problems += _validate_trigger(mark, as_of, events)
    elif verdict in MARK_VERDICTS:
        # A negative verdict is a typed row with NO geometry — a rail on a
        # "no_structure" row is an ambiguous mark, not extra information.
        for field in _GEOMETRY_FIELDS:
            if get(field) is not None:
                problems.append(f"negative verdict carries geometry ({field})")
        if events:
            problems.append("negative verdict carries event marks")
        if get("trigger_date") is not None or get("trigger_price") is not None:
            problems.append("negative verdict carries a trigger")
    return problems


def _validate_box_geometry(mark: dict, as_of) -> list[str]:
    problems = []
    resistance, support = mark.get("resistance"), mark.get("support")
    if not _positive_number(resistance) or not _positive_number(support):
        problems.append("box verdict requires positive resistance and support rails")
    elif resistance <= support:
        problems.append(f"resistance {resistance} not above support {support}")
    start = parse_iso_date(mark.get("box_start_date"))
    end = parse_iso_date(mark.get("box_end_date"))
    if start is None or end is None:
        problems.append("box verdict requires an ISO box_start_date and box_end_date")
    else:
        if start > end:
            problems.append("box span is inverted")
        if as_of is not None and end > as_of:
            problems.append("box_end_date is after as_of_date")
    # Rail anchors (optional — pre-anchor marks have none): the swing bar
    # each rail was placed on, each an ISO session at/before the as-of.
    for field in ("r_anchor_date", "s_anchor_date"):
        anchor = mark.get(field)
        if anchor is None:
            continue
        ad = parse_iso_date(anchor)
        if ad is None:
            problems.append(f"{field} {anchor!r} is not YYYY-MM-DD")
        elif as_of is not None and ad > as_of:
            problems.append(f"{field} is after as_of_date")
    first = mark.get("first_rail")
    if first is not None and first not in FIRST_RAILS:
        problems.append(f"first_rail {first!r} not in {FIRST_RAILS}")
    return problems


def _validate_event(event: dict, index: int, as_of) -> list[str]:
    problems = []
    tag = f"event[{index}]"
    if event.get("event_type") not in EVENT_TYPES:
        problems.append(f"{tag} type {event.get('event_type')!r} not in {EVENT_TYPES}")
    if event.get("source", "operator") not in SOURCES:
        problems.append(f"{tag} source {event.get('source')!r} not in {SOURCES}")
    start = parse_iso_date(event.get("start_date"))
    end = parse_iso_date(event.get("end_date"))
    if start is None or end is None:
        problems.append(f"{tag} needs ISO start_date and end_date")
        return problems
    if start > end:
        problems.append(f"{tag} span is inverted")
    if as_of is not None and end > as_of:
        problems.append(f"{tag} ends after as_of_date")
    tip = event.get("tip_date")
    if tip is not None:
        td = parse_iso_date(tip)
        if td is None:
            problems.append(f"{tag} tip_date {tip!r} is not YYYY-MM-DD")
        elif not (start <= td <= end):
            problems.append(f"{tag} tip_date outside its span")
    if event.get("tip_price") is not None and not _positive_number(event.get("tip_price")):
        problems.append(f"{tag} tip_price {event.get('tip_price')!r} is not a positive number")
    problems.extend(_validate_event_band(event, tag))
    return problems


def _validate_event_band(event: dict, tag: str) -> list[str]:
    """The price band — required for a mini-consolidation (a box without a top
    and a bottom is not a box), absent-or-well-formed for every other type."""
    problems = []
    high, low = event.get("band_high"), event.get("band_low")
    if high is None and low is None:
        if event.get("event_type") in _BAND_TYPES:
            problems.append(f"{tag} {event.get('event_type')} needs a price band "
                            "(band_high and band_low)")
        return problems
    if high is None or low is None:
        problems.append(f"{tag} band needs BOTH band_high and band_low")
        return problems
    if not _positive_number(high) or not _positive_number(low):
        problems.append(f"{tag} band prices must be positive numbers")
    elif not high > low:
        problems.append(f"{tag} band_high must be above band_low")
    return problems


def _validate_trigger(mark: dict, as_of, events: list) -> list[str]:
    """The Trigger (the operator's BUY) is the breakout above the High of the
    LPS's final bar. Its ONLY placement rule is that it lands strictly AFTER the
    last LPS bar (and requires an LPS). It may sit before, on, or after the as-of
    (relaxed 2026-07-22): the operator marks the real breakout day, then locks the
    snapshot separately — so the buy is deliberately NOT constrained to as_of here
    (the grade compares the engine's fire date to the buy date, never to as_of).
    Absent trigger = a legitimate null state (no buy marked). `as_of` is accepted
    for signature symmetry with the other validators but no longer bounds the buy.

    The frame-dependent upper bound (trigger_date is a real session <= frame_end)
    is checked at the WRITE boundary, where the frozen grading frame is loadable —
    not here, so this one shared judgment (EC-3) stays pure and import-anywhere.
    """
    td = mark.get("trigger_date")
    tp = mark.get("trigger_price")
    if td is None and tp is None:
        return []
    problems: list[str] = []
    if (td is None) != (tp is None):
        problems.append("trigger_date and trigger_price must be set together")
    if tp is not None and not _positive_number(tp):
        problems.append(f"trigger_price {tp!r} is not a positive number")
    if td is None:
        return problems
    tdate = parse_iso_date(td)
    if tdate is None:
        problems.append(f"trigger_date {td!r} is not YYYY-MM-DD")
        return problems
    # It is the breakout above the last LPS bar's high, so it requires an LPS and
    # lands strictly after that LPS's final (end) bar. (No as_of floor — relaxed
    # 2026-07-22; the buy may precede the snapshot.)
    lps_ends = [parse_iso_date(e.get("end_date")) for e in events
                if e.get("event_type") == "lps"]
    lps_ends = [d for d in lps_ends if d is not None]
    if not lps_ends:
        problems.append("trigger requires an LPS event (the buy is the breakout "
                        "above the last LPS bar's high)")
    elif tdate <= max(lps_ends):
        problems.append("trigger_date must be after the last LPS bar")
    return problems
