"""Watchlist event-ledger logic: server-resolved pins, snapshots, weekly review
grouping, and replay verdicts (Finviz plan Tasks 6-7).

The router stays thin; everything that decides lives here. Three conventions
carry the design:

- EC-37 — a stored pin is copied VERBATIM from the displayed artifact's
  ``scan_identity``, never derived from any clock. A Saturday save pins
  Friday's scan because Friday's scan is what is on screen.
- EC-26 — the snapshot is resolved server-side from the on-disk artifact; a
  client-authored chart payload is never accepted into permanent history.
- EC-28 — review/replay rows cross the wire as resolved verdicts extracted
  from the STORED payload; the frontend renders, it never re-derives.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from archive_models import SetupArchive
from services import screener_data

log = logging.getLogger("chrollo.watchlist")

SNAPSHOT_VERSION = 1
# Mirrors ck_watchlist_snapshot in models.py — SQLite length() counts
# characters on TEXT, so the pre-check does too.
SNAPSHOT_MAX_CHARS = 262_144

# EC-33: the closed replay-verdict vocabularies. Every value has a producing
# test (EC-22) and every refusing leg a distinguishable assertion (EC-27).
SNAPSHOT_STATUSES = ("ok", "missing")
ARCHIVE_STATUSES = ("matched", "rewritten", "purged", "never_archived", "no_pin")

# The archive LEFT-JOIN is enrichment ONLY (forward-return outcomes) — never
# the render source. Closed set so the wire cannot quietly grow render inputs.
_ENRICHMENT_FIELDS = (
    "ret_to_date", "mfe_to_date", "mae_to_date", "bars_to_date",
    "win_barrier", "r_multiple_20d", "days_to_trigger",
)


def _utc_now() -> datetime:
    """Naive-UTC stamp, matching how SQLAlchemy's sqlite DATETIME stores it."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def resolve_pin_and_snapshot(
    ticker: str, universe_key: str, displayed_scan_date: str | None
) -> tuple[dict | None, str | None, str]:
    """Copy the pin quadruple + snapshot from the server's own artifact.

    Returns ``(pin, snapshot_json, reason)``. ``pin`` is the full quadruple or
    None (the honest "starred without a setup" state — the half-pin CHECK makes
    anything in between impossible). Reasons: 'pinned' | 'not_in_scan' |
    'stale_display' | 'no_identity'. ``displayed_scan_date`` is what the card
    showed; if the on-disk artifact has moved past it we cannot snapshot what
    the operator was actually looking at, so the save degrades to unpinned
    rather than pinning a chart they never saw.

    Raises ValueError on an unknown universe key (closed registry).
    """
    from core.pipeline.universe import resolve_universe

    payload = screener_data.read_screener_data(
        resolve_universe(universe_key).artifact_path()
    )
    identity = payload.get("scan_identity") or {}
    # Staleness first: once the artifact has moved past the displayed scan, it
    # can say NOTHING about what the operator saw — 'not_in_scan' would blame
    # the name for a page that is simply old (review finding 2026-08-12).
    if displayed_scan_date and identity.get("scan_date") != displayed_scan_date:
        return None, None, "stale_display"
    entry = (payload.get("chart_data") or {}).get(ticker)
    if entry is None:
        return None, None, "not_in_scan"

    pin = {
        "pin_scan_date": identity.get("scan_date"),
        "pin_universe_type": identity.get("universe_type"),
        "pin_setup_type": entry.get("setup"),
        "pin_engine_config_version": identity.get("engine_config_version"),
    }
    if not all(pin.values()):
        # Pre-scan_identity artifact or an entry without a setup label: the
        # full-pin CHECK forbids a half-pin, so degrade to the unpinned state.
        return None, None, "no_identity"

    # Byte-faithful copy of the displayed entry (key-absence preserved), minus
    # election_trace: an unbounded debug structure no chart surface renders.
    snapshot_entry = {k: v for k, v in entry.items() if k != "election_trace"}
    envelope = {
        "snapshot_version": SNAPSHOT_VERSION,
        "scan_identity": identity,
        "entry": snapshot_entry,
    }
    encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > SNAPSHOT_MAX_CHARS:
        log.warning(
            "watchlist snapshot for %s exceeds %d chars (%d) — pin kept, "
            "snapshot dropped", ticker, SNAPSHOT_MAX_CHARS, len(encoded))
        return pin, None, "pinned"
    return pin, encoded, "pinned"


def save_watch(
    db: Session, ticker: str, universe_key: str, displayed_scan_date: str | None
) -> tuple[models.Watchlist, str]:
    """The dated save event. Returns ``(row, outcome)`` with outcome in
    'already_active' | 'reactivated' | 'created'.

    Idempotency ladder: an ACTIVE row anywhere wins untouched (starring a
    starred name is a no-op); a same-day unstarred row reactivates in place
    (its original pin stays — the ledger records what the FIRST save of the
    day saw); otherwise a new event row is written with the server-resolved
    pin + snapshot. A concurrent double-POST converges via the IntegrityError
    catch instead of surfacing a 500 (threadpool routers).
    """
    now = _utc_now()
    save_date = now.date().isoformat()

    active = (
        db.query(models.Watchlist)
        .filter(models.Watchlist.ticker == ticker,
                models.Watchlist.unstarred_at.is_(None))
        .first()
    )
    if active is not None:
        return active, "already_active"

    same_day = (
        db.query(models.Watchlist)
        .filter(models.Watchlist.ticker == ticker,
                models.Watchlist.save_date == save_date)
        .first()
    )
    if same_day is not None:
        same_day.unstarred_at = None
        db.commit()
        db.refresh(same_day)
        log.info("watchlist re-star %s reactivated the %s save", ticker, save_date)
        return same_day, "reactivated"

    pin, snapshot_json, reason = resolve_pin_and_snapshot(
        ticker, universe_key, displayed_scan_date)
    row = models.Watchlist(
        ticker=ticker,
        save_date=save_date,
        saved_at=now,
        unstarred_at=None,
        origin="user",
        snapshot_json=snapshot_json,
        **(pin or {
            "pin_scan_date": None, "pin_universe_type": None,
            "pin_setup_type": None, "pin_engine_config_version": None,
        }),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent double-POST of the same key: converge on the winner.
        db.rollback()
        existing = (
            db.query(models.Watchlist)
            .filter(models.Watchlist.ticker == ticker,
                    models.Watchlist.unstarred_at.is_(None))
            .first()
        ) or (
            db.query(models.Watchlist)
            .filter(models.Watchlist.ticker == ticker,
                    models.Watchlist.save_date == save_date)
            .first()
        )
        if existing is None:
            raise
        log.info("watchlist save %s converged on concurrent writer", ticker)
        return existing, "already_active"
    db.refresh(row)
    log.info("watchlist save %s %s (%s)", ticker, save_date, reason)
    return row, "created"


def unstar_watch(db: Session, ticker: str) -> models.Watchlist | None:
    """Deactivate the active row, keeping history. None when nothing is active."""
    active = (
        db.query(models.Watchlist)
        .filter(models.Watchlist.ticker == ticker,
                models.Watchlist.unstarred_at.is_(None))
        .first()
    )
    if active is None:
        return None
    active.unstarred_at = _utc_now()
    db.commit()
    return active


def active_watches(db: Session) -> list[models.Watchlist]:
    return (
        db.query(models.Watchlist)
        .filter(models.Watchlist.unstarred_at.is_(None))
        .order_by(models.Watchlist.saved_at.desc())
        .all()
    )


def iso_week_monday(date_str: str) -> str:
    """The Monday of ``date_str``'s ISO week — the weekly grouping key.

    String-in string-out over the pinned scan_date (Monday-based, DST-proof:
    pure calendar arithmetic on the date, no clocks involved). Strict shape
    via the canonical parser — bare strptime accepts unpadded dates.
    """
    from marks_validity import parse_iso_date

    parsed = parse_iso_date(date_str)
    if parsed is None:
        raise ValueError(f"not a YYYY-MM-DD date: {date_str!r}")
    d = parsed.date()
    return (d - timedelta(days=d.weekday())).isoformat()


def _coerce_str(value) -> str | None:
    return value if isinstance(value, str) else None


def _coerce_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN -> None


def _snapshot_display_fields(snapshot_json: str | None) -> dict:
    """Extract the review row's display fields from the STORED payload (EC-28:
    the row and its replay quote the same bytes, so they cannot disagree).
    Degrades to all-None on any parse surprise — never 500s a list. Each
    quoted value is COERCED per field: the wire models type-pin these, and
    one drifted stored value must degrade its own cell, never fail response
    validation for the whole review (council review 2026-08-17, sweep-i)."""
    fields = {"tier": None, "score": None, "setup": None, "ta_grade": None,
              "price": None}
    if not snapshot_json:
        return fields
    try:
        entry = json.loads(snapshot_json).get("entry") or {}
    except (ValueError, AttributeError) as exc:
        log.warning("unreadable watchlist snapshot skipped: %s", exc)
        return fields
    fields["tier"] = _coerce_str(entry.get("tier"))
    fields["setup"] = _coerce_str(entry.get("setup"))
    fields["score"] = _coerce_number(entry.get("score"))
    fields["ta_grade"] = _coerce_number(entry.get("ta_grade"))
    fields["price"] = _coerce_number(entry.get("price"))
    return fields


def weekly_review(db: Session, limit_weeks: int) -> list[dict]:
    """Save events grouped by the pinned scan_date's ISO week, newest first.

    Unpinned rows (starred without a setup / legacy) fall back to save_date so
    every save has a home; ``saved_at`` is audit-only and never a grouping key
    (EC-37). Includes un-starred history — that is the point of the ledger.
    """
    rows = db.query(models.Watchlist).all()

    def group_date(row: models.Watchlist) -> str:
        return row.pin_scan_date or row.save_date

    weeks: dict[str, list] = {}
    for row in rows:
        try:
            key = iso_week_monday(group_date(row))
        except ValueError:
            key = group_date(row)  # degrade: the raw string is its own bucket
        weeks.setdefault(key, []).append(row)

    out = []
    for week_start in sorted(weeks, reverse=True)[:limit_weeks]:
        members = sorted(weeks[week_start], key=lambda r: r.ticker)
        members.sort(key=group_date, reverse=True)  # newest day first, A-Z within
        out.append({
            "week_start": week_start,
            "saves": [_review_row(row) for row in members],
        })
    return out


def universe_key_for_type(universe_type: str | None) -> str | None:
    """The registry KEY for a stored universe TYPE ('us_equities' ->
    'us_stocks') — what a review re-star must POST back as its displayed
    universe; the type alone cannot drive resolve_universe. Public API: the
    watchlist router builds its wire item with this mapping."""
    if universe_type is None:
        return None
    from core.pipeline.universe import all_universes

    for u in all_universes():
        if u.universe_type == universe_type:
            return u.key
    return None


def _review_row(row: models.Watchlist) -> dict:
    display = _snapshot_display_fields(row.snapshot_json)
    return {
        "id": row.id,
        "ticker": row.ticker,
        "save_date": row.save_date,
        "saved_at": row.saved_at,
        "unstarred_at": row.unstarred_at,
        "active": row.unstarred_at is None,
        "origin": row.origin,
        "pinned": row.pin_scan_date is not None,
        "pin_scan_date": row.pin_scan_date,
        "pin_universe_type": row.pin_universe_type,
        "pin_universe_key": universe_key_for_type(row.pin_universe_type),
        "pin_setup_type": row.pin_setup_type,
        "pin_engine_config_version": row.pin_engine_config_version,
        "has_snapshot": row.snapshot_json is not None,
        **display,
    }


def replay(db: Session, row: models.Watchlist) -> dict:
    """The replay envelope: stored snapshot + per-leg verdicts.

    The snapshot is the ONLY render source; the archive join is enrichment
    (forward-return outcomes). Each leg degrades to a named verdict — never a
    500 — and the archive verdicts distinguish WHY the join came back empty:
    'purged' (the cohort still exists, this row is gone) vs 'never_archived'
    (no row of that scan ever landed) vs 'rewritten' (the row exists but under
    a different engine manifest than the operator saw).
    """
    snapshot = None
    snapshot_status = "missing"
    if row.snapshot_json:
        try:
            snapshot = json.loads(row.snapshot_json)
            snapshot_status = "ok"
        except ValueError as exc:  # CHECK-guarded; belt and suspenders
            log.warning("watchlist replay %d: unreadable snapshot: %s", row.id, exc)

    archive_status = "no_pin"
    enrichment = None
    if row.pin_scan_date is not None:
        match = (
            db.query(SetupArchive)
            .filter(SetupArchive.ticker == row.ticker,
                    SetupArchive.scan_date == row.pin_scan_date,
                    SetupArchive.universe_type == row.pin_universe_type)
            .first()
        )
        if match is not None:
            rewritten = (
                match.engine_config_version is not None
                and row.pin_engine_config_version is not None
                and match.engine_config_version != row.pin_engine_config_version
            )
            archive_status = "rewritten" if rewritten else "matched"
            enrichment = {f: getattr(match, f, None) for f in _ENRICHMENT_FIELDS}
        else:
            cohort = (
                db.query(SetupArchive.id)
                .filter(SetupArchive.scan_date == row.pin_scan_date,
                        SetupArchive.universe_type == row.pin_universe_type)
                .first()
            )
            archive_status = "purged" if cohort is not None else "never_archived"

    return {
        "watch": _review_row(row),
        "snapshot_status": snapshot_status,
        "archive_status": archive_status,
        "snapshot": snapshot,
        "archive": enrichment,
    }
