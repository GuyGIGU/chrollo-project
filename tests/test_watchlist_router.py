"""Watchlist ledger router + service (Finviz plan Tasks 6-7), EC-22 mold:
real handlers against a throwaway in-memory SQLite — never a mocked session,
never the live DB, never a booted app. The artifact read is monkeypatched at
the service's own reference (domains.screener.data.read_screener_data); the
universe registry runs for real so the closed-registry refusal is genuine.

Pins: EC-37 (pin copied VERBATIM from the artifact, never a clock), EC-26
(snapshot resolved server-side), EC-28 (review rows quote the stored bytes),
EC-22 (every replay verdict value produced), EC-27 (every refusing leg
distinguishable), and the v1 snapshot fixture round-trip that keeps old saves
rendering through future shape changes."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import models  # noqa: E402
from domains.watchlist import router as watchlist  # noqa: E402
from domains.calibration.router import require_same_app  # noqa: E402
from domains.watchlist import ledger as watchlist_ledger  # noqa: E402

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "watchlist_snapshot_v1.json"
FIXTURE_TEXT = FIXTURE_PATH.read_text(encoding="utf-8")
FIXTURE = json.loads(FIXTURE_TEXT)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


def _artifact(scan_date="2026-08-11", tickers=("NVDA",), identity=True):
    """A payload shaped like output/screener_data.json, entries cloned from
    the immutable v1 fixture so save->replay equality is byte-meaningful."""
    payload = {
        "chart_data": {t: dict(FIXTURE["entry"]) for t in tickers},
        "ordered_tickers": list(tickers),
    }
    if identity:
        payload["scan_identity"] = {
            "scan_date": scan_date,
            "universe_type": "us_equities",
            "engine_config_version": "manifest-abc",
        }
    return payload


@pytest.fixture()
def artifact(monkeypatch):
    """Patch the artifact read at the service's own module reference — the one
    name the code under test actually calls."""
    payload = _artifact()

    def set_payload(p):
        payload.clear()
        payload.update(p)

    monkeypatch.setattr(
        watchlist_ledger.screener_data, "read_screener_data", lambda path: payload)
    return set_payload


def _watch(db, ticker="NVDA", save_date="2026-08-12", saved_at=None,
           unstarred_at=None, pin=None, snapshot_json=None, origin="user"):
    pin = pin or {}
    row = models.Watchlist(
        ticker=ticker, save_date=save_date,
        saved_at=saved_at or datetime(2026, 8, 12, 6, 0, 0),
        unstarred_at=unstarred_at, origin=origin,
        pin_scan_date=pin.get("scan_date"),
        pin_universe_type=pin.get("universe_type"),
        pin_setup_type=pin.get("setup_type"),
        pin_engine_config_version=pin.get("engine_config_version"),
        snapshot_json=snapshot_json,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


FULL_PIN = {"scan_date": "2026-08-11", "universe_type": "us_equities",
            "setup_type": "LPS", "engine_config_version": "manifest-abc"}


def _archive_row(db, ticker="NVDA", scan_date="2026-08-11",
                 universe_type="us_equities", ecv="manifest-abc", **extra):
    row = archive_models.SetupArchive(
        ticker=ticker, scan_date=scan_date, universe_type=universe_type,
        setup_type="LPS", tier="S", score=61.5,
        engine_config_version=ecv, **extra)
    db.add(row)
    db.commit()
    return row


# ── Save flow: server-resolved pin + snapshot (Task 6) ───────────────────────


def test_post_pins_verbatim_from_the_artifact(db, artifact):
    item = watchlist.add_to_watchlist("NVDA", watchlist.SaveIn(
        universe="us_stocks", scan_date="2026-08-11"), db)
    assert item.ticker == "NVDA"
    assert item.pinned is True
    assert item.pin_scan_date == "2026-08-11"

    row = db.query(models.Watchlist).one()
    # EC-37: the quadruple is the artifact's own identity, byte for byte.
    assert row.pin_scan_date == "2026-08-11"
    assert row.pin_universe_type == "us_equities"
    assert row.pin_setup_type == "LPS"
    assert row.pin_engine_config_version == "manifest-abc"
    # EC-26: the snapshot is the server's artifact entry, never client input.
    envelope = json.loads(row.snapshot_json)
    assert envelope["snapshot_version"] == 1
    assert envelope["scan_identity"]["scan_date"] == "2026-08-11"
    assert envelope["entry"] == FIXTURE["entry"]


def test_post_lowercases_and_dates_the_save(db, artifact):
    item = watchlist.add_to_watchlist("nvda", None, db)
    assert item.ticker == "NVDA"
    today = datetime.now(timezone.utc).date().isoformat()
    assert item.save_date == today
    assert item.created_at is not None  # the audit stamp rides the old field


def test_post_not_in_scan_saves_the_honest_unpinned_state(db, artifact):
    item = watchlist.add_to_watchlist("ZZZT", None, db)
    assert item.pinned is False
    row = db.query(models.Watchlist).one()
    assert (row.pin_scan_date, row.pin_universe_type, row.pin_setup_type,
            row.pin_engine_config_version) == (None, None, None, None)
    assert row.snapshot_json is None


def test_resolver_legs_are_distinguishable(artifact):
    """EC-27: the three unpinned outcomes carry distinct reasons — a stale
    display must never be mistaken for a name that simply didn't fire."""
    pin, snap, reason = watchlist_ledger.resolve_pin_and_snapshot(
        "NVDA", "us_stocks", "2026-08-11")
    assert reason == "pinned" and pin is not None and snap is not None

    _, _, reason = watchlist_ledger.resolve_pin_and_snapshot(
        "ZZZT", "us_stocks", "2026-08-11")
    assert reason == "not_in_scan"

    _, _, reason = watchlist_ledger.resolve_pin_and_snapshot(
        "NVDA", "us_stocks", "2026-08-08")  # page shows an older scan
    assert reason == "stale_display"

    # Staleness trumps absence: a ticker missing from a NEWER artifact says
    # nothing about the page the operator saw (review finding 2026-08-12).
    _, _, reason = watchlist_ledger.resolve_pin_and_snapshot(
        "ZZZT", "us_stocks", "2026-08-08")
    assert reason == "stale_display"

    artifact(_artifact(identity=False))
    _, _, reason = watchlist_ledger.resolve_pin_and_snapshot(
        "NVDA", "us_stocks", None)
    assert reason == "no_identity"


def test_oversize_snapshot_drops_snapshot_keeps_pin(artifact):
    huge = _artifact()
    huge["chart_data"]["NVDA"]["pad"] = "x" * watchlist_ledger.SNAPSHOT_MAX_CHARS
    artifact(huge)
    pin, snap, reason = watchlist_ledger.resolve_pin_and_snapshot(
        "NVDA", "us_stocks", None)
    assert reason == "pinned"
    assert pin is not None
    assert snap is None  # the cap refuses the payload, never the save


def test_snapshot_strips_election_trace_only(artifact):
    traced = _artifact()
    traced["chart_data"]["NVDA"]["election_trace"] = {"huge": "debug"}
    artifact(traced)
    _, snap, _ = watchlist_ledger.resolve_pin_and_snapshot(
        "NVDA", "us_stocks", None)
    entry = json.loads(snap)["entry"]
    assert "election_trace" not in entry
    assert entry == FIXTURE["entry"]  # nothing else touched


def test_post_is_idempotent_while_active(db, artifact):
    first = watchlist.add_to_watchlist("NVDA", None, db)
    second = watchlist.add_to_watchlist("NVDA", None, db)
    assert db.query(models.Watchlist).count() == 1
    assert first.save_date == second.save_date


def test_same_day_restar_reactivates_the_existing_row(db, artifact):
    watchlist.add_to_watchlist("NVDA", None, db)
    watchlist.remove_from_watchlist("NVDA", db)
    row = db.query(models.Watchlist).one()
    assert row.unstarred_at is not None

    original_pin = row.pin_engine_config_version
    watchlist.add_to_watchlist("NVDA", None, db)
    assert db.query(models.Watchlist).count() == 1  # reactivated, not duplicated
    db.refresh(row)
    assert row.unstarred_at is None
    assert row.pin_engine_config_version == original_pin  # first save's pin kept


def test_next_day_restar_writes_a_new_event(db, artifact):
    _watch(db, save_date="2026-08-10", unstarred_at=datetime(2026, 8, 10, 18, 0))
    watchlist.add_to_watchlist("NVDA", None, db)
    rows = db.query(models.Watchlist).order_by(models.Watchlist.save_date).all()
    assert len(rows) == 2  # history preserved, new dated event appended
    assert rows[0].unstarred_at is not None
    assert rows[1].unstarred_at is None


def test_delete_deactivates_keeping_history(db, artifact):
    watchlist.add_to_watchlist("NVDA", None, db)
    out = watchlist.remove_from_watchlist("NVDA", db)
    assert out == {"status": "removed", "ticker": "NVDA"}
    assert db.query(models.Watchlist).count() == 1  # the row survives

    with pytest.raises(HTTPException) as err:
        watchlist.remove_from_watchlist("NVDA", db)  # nothing active anymore
    assert err.value.status_code == 404
    assert err.value.detail["class"] == "not_on_watchlist"


def test_get_lists_active_only_newest_first(db, artifact):
    _watch(db, ticker="OLD", save_date="2026-08-01",
           saved_at=datetime(2026, 8, 1, 6, 0),
           unstarred_at=datetime(2026, 8, 2, 6, 0))
    _watch(db, ticker="AAA", save_date="2026-08-10",
           saved_at=datetime(2026, 8, 10, 6, 0))
    _watch(db, ticker="BBB", save_date="2026-08-12",
           saved_at=datetime(2026, 8, 12, 6, 0))
    items = watchlist.list_watchlist(db)
    assert [i.ticker for i in items] == ["BBB", "AAA"]  # unstarred OLD absent


def test_get_carries_the_active_save_id_for_a_one_hop_replay(db, artifact):
    """The active row IS the ticker's most recent save (save_watch returns it
    before creating anything, and the partial unique index allows only one), so
    a surface wanting that save's stored chart can go straight to
    /watchlist/{id}/replay instead of paging the weekly review to find it."""
    _watch(db, ticker="OLD", save_date="2026-08-01",
           saved_at=datetime(2026, 8, 1, 6, 0),
           unstarred_at=datetime(2026, 8, 2, 6, 0))
    row = _watch(db, ticker="AAA", save_date="2026-08-10",
                 saved_at=datetime(2026, 8, 10, 6, 0))

    (item,) = watchlist.list_watchlist(db)
    assert item.ticker == "AAA"
    assert item.id == row.id

    # And that id addresses the replay route for real, not just by shape.
    replay = watchlist.watchlist_replay(item.id, db)
    assert replay.watch.ticker == "AAA"


def test_bad_ticker_refused_with_named_class(db, artifact):
    for bad in ("", "  ", "BAD!!", "TOO-LONG-TICKER-NAME"):
        with pytest.raises(HTTPException) as err:
            watchlist.add_to_watchlist(bad, None, db)
        assert err.value.status_code == 400
        assert err.value.detail["class"] == "bad_ticker"
    assert db.query(models.Watchlist).count() == 0


def test_bad_universe_refused_with_named_class(db, artifact):
    with pytest.raises(HTTPException) as err:
        watchlist.add_to_watchlist("NVDA", watchlist.SaveIn(universe="narnia"), db)
    assert err.value.status_code == 422
    assert err.value.detail["class"] == "bad_universe"


def test_calendar_impossible_scan_date_refused(db, artifact):
    """Shape-valid but calendar-impossible dates are refused at the boundary —
    they would otherwise silently degrade every save to unpinned."""
    with pytest.raises(HTTPException) as err:
        watchlist.add_to_watchlist("NVDA", watchlist.SaveIn(
            universe="us_stocks", scan_date="2026-02-31"), db)
    assert err.value.status_code == 400
    assert err.value.detail["class"] == "bad_date"
    assert db.query(models.Watchlist).count() == 0


def test_concurrent_double_post_converges_via_integrity_error(db, artifact, monkeypatch):
    """The uniqueness-violation = idempotent-success branch, actually driven
    (EC-22): a competing writer lands between the ladder queries and the
    INSERT; save_watch must converge on the winner, never 500."""
    real = watchlist_ledger.resolve_pin_and_snapshot

    def racing(ticker, universe_key, displayed):
        _watch(db, ticker=ticker,
               save_date=datetime.now(timezone.utc).date().isoformat(),
               saved_at=datetime(2026, 8, 12, 5, 0))
        return real(ticker, universe_key, displayed)

    monkeypatch.setattr(watchlist_ledger, "resolve_pin_and_snapshot", racing)
    row, outcome = watchlist_ledger.save_watch(db, "NVDA", "us_stocks", None)
    assert outcome == "already_active"
    assert row is not None
    assert db.query(models.Watchlist).count() == 1


def test_write_routes_declare_the_cross_app_guard():
    """Hunt's containment: every mutating watchlist route carries
    require_same_app (CORS stays a read-gate; the allowlist is not widened)."""
    for route in watchlist.router.routes:
        if route.methods & {"POST", "PUT", "DELETE", "PATCH"}:
            deps = [d.call for d in route.dependant.dependencies]
            assert require_same_app in deps, route.path


# ── Weekly review (Task 7) ───────────────────────────────────────────────────


def test_iso_week_monday_is_the_grouping_key():
    assert watchlist_ledger.iso_week_monday("2026-08-11") == "2026-08-10"  # Tue
    assert watchlist_ledger.iso_week_monday("2026-08-10") == "2026-08-10"  # Mon
    assert watchlist_ledger.iso_week_monday("2026-08-16") == "2026-08-10"  # Sun
    with pytest.raises(ValueError):
        watchlist_ledger.iso_week_monday("2026-8-11")  # unpadded is refused


def test_review_groups_by_pinned_scan_date_not_save_date(db, artifact):
    # Saved Wednesday, pinned to Tuesday's scan: the pin decides the week.
    _watch(db, ticker="AAA", save_date="2026-08-12", pin=FULL_PIN,
           snapshot_json=FIXTURE_TEXT)
    # Pinned to the PREVIOUS ISO week; un-starred — history stays visible.
    _watch(db, ticker="BBB", save_date="2026-08-12",
           unstarred_at=datetime(2026, 8, 12, 9, 0),
           pin={**FULL_PIN, "scan_date": "2026-08-04"})
    # Unpinned: falls back to its own save_date week.
    _watch(db, ticker="CCC", save_date="2026-08-05")

    resp = watchlist.watchlist_review(limit_weeks=12, db=db)
    assert [w.week_start for w in resp.weeks] == ["2026-08-10", "2026-08-03"]

    this_week = resp.weeks[0].saves
    assert [s.ticker for s in this_week] == ["AAA"]
    # EC-28: the review row quotes the STORED snapshot, not a live lookup.
    # ta_grade is the producer's NUMERIC grade — a string here would mean the
    # fixture certifies a payload shape the dashboard never writes (the P1
    # this guard exists for, review 2026-08-12).
    assert this_week[0].tier == "S"
    assert this_week[0].score == 61.5
    assert this_week[0].setup == "LPS"
    assert this_week[0].ta_grade == 74.1
    assert this_week[0].active is True
    assert this_week[0].pin_universe_key == "us_stocks"

    last_week = resp.weeks[1].saves
    assert [s.ticker for s in last_week] == ["CCC", "BBB"]  # newest day first
    assert last_week[1].active is False       # un-starred shown in place
    assert last_week[1].tier is None          # no snapshot -> honest nulls
    assert last_week[1].has_snapshot is False


def test_review_limit_weeks(db, artifact):
    _watch(db, ticker="AAA", save_date="2026-08-12", pin=FULL_PIN)
    _watch(db, ticker="BBB", save_date="2026-08-05",
           pin={**FULL_PIN, "scan_date": "2026-08-04"})
    resp = watchlist.watchlist_review(limit_weeks=1, db=db)
    assert [w.week_start for w in resp.weeks] == ["2026-08-10"]


# ── Replay verdicts (Task 7) — every legal value produced (EC-22) ────────────


def test_replay_matched_with_enrichment(db, artifact):
    row = _watch(db, pin=FULL_PIN, snapshot_json=FIXTURE_TEXT)
    _archive_row(db, ret_to_date=0.12, mfe_to_date=0.2, win_barrier="2.5R")
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.snapshot_status == "ok"
    assert resp.archive_status == "matched"
    assert resp.archive["ret_to_date"] == 0.12
    assert resp.archive["win_barrier"] == "2.5R"
    # The snapshot, not the archive, is the render source.
    assert resp.snapshot["entry"] == FIXTURE["entry"]


def test_replay_matched_when_archive_has_no_manifest(db, artifact):
    row = _watch(db, pin=FULL_PIN, snapshot_json=FIXTURE_TEXT)
    _archive_row(db, ecv=None)  # pre-manifest archive row: not provably rewritten
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.archive_status == "matched"


def test_replay_rewritten_under_a_different_manifest(db, artifact):
    row = _watch(db, pin=FULL_PIN, snapshot_json=FIXTURE_TEXT)
    _archive_row(db, ecv="manifest-xyz")
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.archive_status == "rewritten"
    assert resp.snapshot_status == "ok"  # the stored view still renders


def test_replay_purged_vs_never_archived_are_distinct_legs(db, artifact):
    """EC-27: cohort-present-but-row-gone is 'purged'; cohort absent entirely
    is 'never_archived' — two different operational stories."""
    row = _watch(db, pin=FULL_PIN, snapshot_json=FIXTURE_TEXT)
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.archive_status == "never_archived"

    _archive_row(db, ticker="OTHR")  # the cohort exists, our row does not
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.archive_status == "purged"
    assert resp.archive is None  # enrichment never fabricated


def test_replay_no_pin_and_missing_snapshot(db, artifact):
    row = _watch(db)  # legacy-style: no pin, no snapshot
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.snapshot_status == "missing"
    assert resp.archive_status == "no_pin"
    assert resp.snapshot is None
    assert resp.archive is None


def test_replay_unknown_id_refused(db, artifact):
    with pytest.raises(HTTPException) as err:
        watchlist.watchlist_replay(999, db)
    assert err.value.status_code == 404
    assert err.value.detail["class"] == "not_found"


def test_verdict_vocabularies_are_closed_registries():
    """EC-33: every status the routes can emit is a member of the one registry
    tuple; the frontend twin derives from the same lists."""
    assert set(watchlist_ledger.SNAPSHOT_STATUSES) == {"ok", "missing"}
    assert set(watchlist_ledger.ARCHIVE_STATUSES) == {
        "matched", "rewritten", "purged", "never_archived", "no_pin"}


# ── The v1 fixture round-trip guard ──────────────────────────────────────────


def test_snapshot_v1_fixture_round_trips_end_to_end(db, artifact):
    """The immutable v1 contract: an artifact shaped like the fixture, saved
    through the real POST, replays byte-equal to the fixture. Future shape
    changes must keep this green or old saves stop rendering."""
    watchlist.add_to_watchlist("NVDA", watchlist.SaveIn(
        universe="us_stocks", scan_date="2026-08-11"), db)
    row = db.query(models.Watchlist).one()
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.snapshot == FIXTURE  # identity, version, entry — all of it


def test_stored_v1_bytes_still_replay(db, artifact):
    """A row written by an OLDER build (the fixture's exact bytes) must keep
    replaying as-is — the versioned envelope is append-only."""
    row = _watch(db, pin=FULL_PIN, snapshot_json=FIXTURE_TEXT)
    resp = watchlist.watchlist_replay(row.id, db)
    assert resp.snapshot_status == "ok"
    assert resp.snapshot == FIXTURE
    assert resp.snapshot["snapshot_version"] == 1
    # The keys the chart surfaces render from — absence here means a v1 save
    # no longer draws.
    entry = resp.snapshot["entry"]
    for key in ("candles", "volumes", "R", "S", "tier", "score", "setup",
                "price", "trigger", "base_len"):
        assert key in entry, key
