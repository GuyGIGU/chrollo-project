"""Calibration router behavioral tests (Calibration at Scale, Tasks 3-5).

Real handlers against a real throwaway SQLite database — never a mocked
session, never the live trading_journal.db, never a booted app (hard-safety
line). What round-trips here is operator ground truth, so field-level
fidelity beats status codes. Deviation from the plan's ideal noted: httpx is
not a project dependency, so these call the route functions directly instead
of going through a TestClient; the HTTP layer itself is FastAPI's machinery.
Response-model fidelity is covered explicitly via MarkOut.model_validate, and
the same-app write guard's WIRING is pinned by route inspection.
"""
import sys
from datetime import datetime

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from models import CalibrationMark, CalibrationMarkEvent  # noqa: E402
from domains.calibration import router as calibration  # noqa: E402
from domains.calibration.router import (  # noqa: E402
    MarkIn,
    MarkOut,
    calibration_chart,
    calibration_fired,
    calibration_frame_thumb,
    calibration_trigger_grade,
    create_mark,
    delete_mark,
    list_marks,
    require_same_app,
    update_mark,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


def _bound_frame(close=11.02):
    idx = pd.to_datetime(["2026-04-13", "2026-04-14", "2026-04-15"])
    return pd.DataFrame({"Open": [close] * 3, "High": [close + 1] * 3,
                         "Low": [close - 1] * 3, "Close": [close] * 3,
                         "Volume": [1_000_000.0] * 3}, index=idx)


@pytest.fixture()
def digest(tmp_path, monkeypatch):
    """Freeze a frame for every identity the tests save under, in a tmp store
    (BOTH module instances patched), and hand back the shared digest —
    the write path now refuses marks that don't bind to a frozen frame."""
    import frame_store
    import webapp.backend.frame_store as wb_frame_store
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(wb_frame_store, "FRAMES_DIR", str(tmp_path))
    d = None
    for ticker, as_of in (("BODI", "2026-04-15"), ("BODI", "2026-04-14"),
                          ("KLAC", "2025-09-11")):
        d, _ = frame_store.freeze_frame(ticker, as_of, _bound_frame())
    return d


def _payload(digest, **overrides):
    fields = dict(
        ticker="BODI",
        as_of_date="2026-04-15",
        verdict="box",
        resistance=12.40,
        support=10.15,
        box_start_date="2025-12-12",
        box_end_date="2026-04-15",
        data_regime="as_traded",
        engine_config_version="test-config",
        anchor_close=11.02,
        frame_digest=digest,
        events=[{"event_type": "phase_c", "start_date": "2026-02-10",
                 "end_date": "2026-03-20", "tip_date": "2026-03-02",
                 "tip_price": 6.77, "source": "extraction"}],
    )
    fields.update(overrides)
    return MarkIn(**fields)


# ── Marks CRUD round-trips ───────────────────────────────────────────


def test_create_round_trips_every_field(db, digest):
    saved = MarkOut.model_validate(create_mark(_payload(
        digest, ticker="bodi", r_anchor_date="2025-12-12",
        s_anchor_date="2026-01-20", first_rail="resistance"), db))
    assert saved.ticker == "BODI"  # normalized at the boundary
    assert (saved.verdict, saved.revision, saved.label) == ("box", 1, "")
    assert (saved.resistance, saved.support) == (12.40, 10.15)
    assert (saved.box_start_date, saved.box_end_date) == ("2025-12-12", "2026-04-15")
    # Rail anchors + the first-marked rail persist and echo (root-swing intent).
    assert (saved.r_anchor_date, saved.s_anchor_date, saved.first_rail) == (
        "2025-12-12", "2026-01-20", "resistance")
    assert (saved.data_regime, saved.engine_config_version) == ("as_traded", "test-config")
    assert saved.anchor_close == 11.02
    assert saved.frame_digest == digest
    assert saved.created_at is not None and saved.updated_at is not None
    e = saved.events[0]
    assert (e.event_type, e.tip_date, e.tip_price, e.source) == (
        "phase_c", "2026-03-02", 6.77, "extraction")


def test_negative_verdict_saves_without_geometry(db, digest):
    saved = MarkOut.model_validate(create_mark(_payload(
        digest, verdict="no_structure", resistance=None, support=None,
        box_start_date=None, box_end_date=None, events=[],
        note="chop, no worked equilibrium"), db))
    assert saved.verdict == "no_structure" and saved.resistance is None


def test_label_is_an_identity_and_normalized(db, digest):
    saved = MarkOut.model_validate(create_mark(_payload(
        digest, label="  LPS "), db))
    assert saved.label == "lps"  # trimmed + case-folded: ONE identity
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(digest, label="lps"), db)  # same identity now
    assert err.value.detail["class"] == "duplicate_mark"


def test_invalid_payload_rejected_and_db_untouched(db, digest):
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(digest, resistance=9.0, support=12.0), db)
    assert err.value.status_code == 422
    assert err.value.detail["class"] == "invalid_mark"
    assert any("not above support" in p for p in err.value.detail["problems"])
    assert db.query(CalibrationMark).count() == 0


def test_unbound_mark_is_refused(db, digest):
    # No frozen frame for the session → the mark could never be replayed.
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(digest, as_of_date="2026-04-12",
                             box_end_date="2026-04-12"), db)
    assert (err.value.status_code, err.value.detail["class"]) == (422, "unbound_mark")
    # Right session, fabricated digest → equally unbound.
    with pytest.raises(HTTPException) as err:
        create_mark(_payload("0" * 64), db)
    assert err.value.detail["class"] == "unbound_mark"
    assert db.query(CalibrationMark).count() == 0


def test_missing_digest_is_invalid(db, digest):
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(None), db)
    assert err.value.detail["class"] == "invalid_mark"
    assert any("frame_digest" in p for p in err.value.detail["problems"])


def test_duplicate_identity_names_THE_RIGHT_existing_row(db, digest):
    # A create that collides on identity is a correction, not a dead-end: the
    # 409 carries the existing row's id so the client offers a one-click,
    # EXPLICIT overwrite. A decoy row under the SAME frame but a different
    # label must not be the one named — the id must resolve on the full
    # (ticker, as_of, label) grain, not just "some row on this frame".
    decoy = create_mark(_payload(digest, label=""), db)          # (BODI, 04-15, '')
    target = create_mark(_payload(digest, label="lps"), db)      # (BODI, 04-15, 'lps')
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(digest, label="lps"), db)           # collide on 'lps'
    assert err.value.status_code == 409
    assert err.value.detail["class"] == "duplicate_mark"
    assert err.value.detail["existing_id"] == target.id != decoy.id
    assert db.query(CalibrationMark).count() == 2
    # Recovery: PUT the named id lands the correction on the RIGHT row only.
    updated = update_mark(err.value.detail["existing_id"],
                          _payload(digest, label="lps", support=10.30), db)
    assert updated.support == 10.30
    assert db.query(CalibrationMark).count() == 2


def test_label_normalization_shares_one_identity(db, digest):
    # 'lps', 'LPS ' and ' lps ' are ONE identity — a near-duplicate label
    # must collide (and name the same row), never slip past the unique key.
    first = create_mark(_payload(digest, label="lps"), db)
    # A same-frame empty-label decoy must not be the row named for the 'lps'
    # collision (guards the label filter in _mark_by_identity).
    create_mark(_payload(digest, label=""), db)
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(digest, label="  LPS "), db)
    assert err.value.detail["existing_id"] == first.id


def test_update_bumps_revision_and_replaces_events(db, digest):
    saved = create_mark(_payload(digest), db)
    updated = MarkOut.model_validate(update_mark(saved.id, _payload(
        digest, support=10.30,
        events=[{"event_type": "lps", "start_date": "2026-04-09",
                 "end_date": "2026-04-15"}]), db))
    assert (updated.support, updated.revision) == (10.30, 2)
    assert [e.event_type for e in updated.events] == ["lps"]
    assert db.query(CalibrationMarkEvent).count() == 1  # replaced, not appended


def test_update_collision_and_unknown_are_named(db, digest):
    # A collision on update is a SAME-FRAME label clash (never a cross-frame
    # re-stamp — that path is refused outright, see below): two marks on the
    # one frame, then re-label one onto the other's identity.
    a = create_mark(_payload(digest, label=""), db)      # (BODI, 04-15, '')
    b = create_mark(_payload(digest, label="lps"), db)   # (BODI, 04-15, 'lps')
    with pytest.raises(HTTPException) as err:
        update_mark(b.id, _payload(digest, label=""), db)  # re-label onto a
    assert err.value.status_code == 409
    assert err.value.detail["class"] == "duplicate_mark"
    assert err.value.detail["existing_id"] == a.id
    with pytest.raises(HTTPException) as err:
        update_mark(9999, _payload(digest), db)
    assert err.value.status_code == 404


def test_cross_frame_update_is_rejected(db, digest):
    # A mark's frame binding is IMMUTABLE (Council Review 2026-07-12, P1): the
    # ledger spans every session, so editing a mark while a DIFFERENT frame is
    # loaded must never silently move its replay basis. The backend refuses it
    # loudly and leaves the mark's original binding untouched.
    mark = create_mark(_payload(digest, as_of_date="2026-04-14",
                                box_end_date="2026-04-14"), db)
    with pytest.raises(HTTPException) as err:
        update_mark(mark.id, _payload(digest), db)  # payload names the 04-15 frame
    assert err.value.status_code == 409
    assert err.value.detail["class"] == "frame_rebind_rejected"
    kept = db.query(CalibrationMark).filter(CalibrationMark.id == mark.id).first()
    assert (kept.as_of_date, kept.revision) == ("2026-04-14", 1)  # unmoved, unrevised


def test_delete_is_hard_and_cascades(db, digest):
    saved = create_mark(_payload(digest), db)
    delete_mark(saved.id, db)
    assert db.query(CalibrationMark).count() == 0
    assert db.query(CalibrationMarkEvent).count() == 0
    with pytest.raises(HTTPException):
        delete_mark(saved.id, db)


def test_list_filters_by_ticker(db, digest):
    create_mark(_payload(digest), db)
    create_mark(_payload(digest, ticker="KLAC", as_of_date="2025-09-11",
                         box_start_date="2025-07-18", box_end_date="2025-09-11",
                         resistance=95.0, support=87.74, events=[]), db)
    assert len(list_marks(None, db)) == 2
    assert [m.ticker for m in list_marks("klac", db)] == ["KLAC"]


# ── Trigger (the buy) on the write path ──────────────────────────────


def _grading_frame(close=11.02):
    # The <= 2026-04-15 slice must reproduce _bound_frame()'s digest exactly, so
    # its first three rows mirror it; two forward bars carry the Trigger window.
    idx = pd.to_datetime(["2026-04-13", "2026-04-14", "2026-04-15",
                          "2026-04-16", "2026-04-17"])
    return pd.DataFrame({"Open": [close] * 5, "High": [close + 1] * 5,
                         "Low": [close - 1] * 5, "Close": [close] * 5,
                         "Volume": [1_000_000.0] * 5}, index=idx)


@pytest.fixture()
def trigger_digest(tmp_path, monkeypatch):
    """Freeze BOTH the <= as-of base frame and the forward grading frame for
    (BODI, 2026-04-15), returning the shared base digest — a Trigger save needs
    the forward frame on disk (the write-boundary frame check)."""
    import frame_store
    import webapp.backend.frame_store as wb_frame_store
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(wb_frame_store, "FRAMES_DIR", str(tmp_path))
    d, _ = frame_store.freeze_frame("BODI", "2026-04-15", _bound_frame())
    frame_store.freeze_grading_frame("BODI", "2026-04-15", _grading_frame(), d)
    return d


# A trigger requires an LPS; this one ends 2026-04-14 (<= as-of) so a buy on
# 2026-04-16 lands strictly after it and at/after as-of.
_LPS_EVENT = [{"event_type": "lps", "start_date": "2026-04-09",
               "end_date": "2026-04-14"}]


def test_trigger_round_trips_through_create_and_out(db, trigger_digest):
    saved = MarkOut.model_validate(create_mark(_payload(
        trigger_digest, events=_LPS_EVENT,
        trigger_date="2026-04-16", trigger_price=12.55), db))
    assert saved.trigger_date == "2026-04-16"
    assert saved.trigger_price == 12.55


def test_markout_presents_a_missing_trigger_as_explicit_null(db, trigger_digest):
    saved = MarkOut.model_validate(create_mark(_payload(
        trigger_digest, events=_LPS_EVENT), db))
    dumped = saved.model_dump()
    # present in the schema, null — the client never guesses "omitted vs no buy".
    assert "trigger_date" in dumped and dumped["trigger_date"] is None
    assert "trigger_price" in dumped and dumped["trigger_price"] is None


def test_trigger_without_a_frozen_forward_frame_is_refused(db, digest):
    # `digest` freezes only the <= as-of base frame, not the grading frame — a
    # Trigger save must be refused loudly (it could never replay frozen-only).
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(digest, events=_LPS_EVENT,
                             trigger_date="2026-04-16", trigger_price=12.55), db)
    assert (err.value.status_code, err.value.detail["class"]) == (422, "unframed_trigger")
    assert db.query(CalibrationMark).count() == 0


def test_trigger_date_must_be_a_real_forward_session(db, trigger_digest):
    # 2026-04-18 is past the frozen frame_end (04-17) — not a real session.
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(trigger_digest, events=_LPS_EVENT,
                             trigger_date="2026-04-18", trigger_price=12.55), db)
    assert err.value.detail["class"] == "trigger_not_a_session"


def test_trigger_survives_an_edit_and_can_be_cleared(db, trigger_digest):
    saved = create_mark(_payload(trigger_digest, events=_LPS_EVENT,
                                 trigger_date="2026-04-16", trigger_price=12.55), db)
    updated = MarkOut.model_validate(update_mark(saved.id, _payload(
        trigger_digest, events=_LPS_EVENT,
        trigger_date="2026-04-16", trigger_price=12.60), db))
    assert (updated.trigger_price, updated.revision) == (12.60, 2)
    # Clearing it is a valid state — the LPS box stands without a buy.
    cleared = MarkOut.model_validate(update_mark(saved.id, _payload(
        trigger_digest, events=_LPS_EVENT), db))
    assert cleared.trigger_date is None and cleared.revision == 3


# ── Same-app write guard ─────────────────────────────────────────────


def test_same_app_guard_rejects_foreign_and_missing_header():
    for bad in ("", "not-ours"):
        with pytest.raises(HTTPException) as err:
            require_same_app(bad)
        assert err.value.status_code == 403
        assert err.value.detail["class"] == "cross_app_write"
    require_same_app("chrollo-dashboard")  # no raise


def test_every_side_effectful_route_declares_the_guard():
    # Every mutating route AND the expensive GETs: /chart spends the vendor
    # bucket and freezes frames (Council finding 11); /fired and /trigger-grade
    # run the full read per mark. Guarded, drive-by pages excluded.
    guarded_gets = {"/calibration/chart", "/calibration/frame-thumb",
                    "/calibration/fired", "/calibration/trigger-grade"}
    seen = {route.path for route in calibration.router.routes}
    assert guarded_gets <= seen  # the pin covers routes that actually exist
    # The old engine's two reads of a frame are gone with it (retire-old-engine,
    # Phase 2b): the overlay of its box election and the per-mark concordance chip.
    assert not {"/calibration/engine-read", "/calibration/agreement"} & seen
    for route in calibration.router.routes:
        methods = getattr(route, "methods", set()) or set()
        side_effectful = bool(methods & {"POST", "PUT", "DELETE", "PATCH"})
        if route.path in guarded_gets:
            side_effectful = True
        if side_effectful:
            deps = [d.call for d in route.dependant.dependencies]
            assert require_same_app in deps, route.path


# ── Chart endpoint: offline degraded-outcome list ────────────────────


def _frame(dates, close=100.0):
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    n = len(idx)
    return pd.DataFrame({"Open": [close] * n, "High": [close + 1] * n,
                         "Low": [close - 1] * n, "Close": [close] * n,
                         "Volume": [1_000_000] * n}, index=idx)


def _chart(monkeypatch, frame, tmp_path, ticker="KLAC", as_of="2025-09-11"):
    import frame_store
    import domains.market_data.service as market_data
    import webapp.backend.frame_store as wb_frame_store
    from core.pipeline.market_data import rate_limit
    from domains.market_data import candle_cache
    monkeypatch.setattr(market_data, "daily_candle_frame",
                        lambda *a, **k: frame)
    # WP-0: the endpoint fetches through the session candle cache. Give each case
    # a clean cache, no retry sleep, and a clear cooldown so the classic chart
    # assertions stay hermetic (rate-limit behaviour is tested in test_candle_cache).
    monkeypatch.setattr(candle_cache, "_CACHE", {})
    monkeypatch.setattr(candle_cache, "_TRANSIENT_RETRY_WAIT_S", 0.0)
    monkeypatch.setattr(rate_limit, "in_cooldown", lambda: False)
    # Both module instances — never the live store, whichever import form
    # a future change routes through.
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(wb_frame_store, "FRAMES_DIR", str(tmp_path))
    return calibration_chart(ticker=ticker, as_of=as_of)


def test_chart_validation_refusals(monkeypatch):
    # The vendor must be unreachable here: if a validation rule regresses,
    # this test fails loud and OFFLINE, never with a live network call.
    import domains.market_data.service as market_data
    monkeypatch.setattr(market_data, "daily_candle_frame",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("refusal must fire before any fetch")))
    cases = [("../etc", "2026-04-15", "bad_ticker"),
             ("BODI", "04/15/2026", "bad_date"),
             ("BODI", "2026-4-15", "bad_date"),
             ("BODI", "1999-01-01", "bad_date"),
             ("BODI", "2999-01-01", "future_date")]
    for ticker, as_of, expected in cases:
        with pytest.raises(HTTPException) as err:
            calibration_chart(ticker=ticker, as_of=as_of)
        assert (err.value.status_code, err.value.detail["class"]) == (400, expected)


def test_chart_empty_frame_is_no_data(monkeypatch, tmp_path):
    with pytest.raises(HTTPException) as err:
        _chart(monkeypatch, _frame([]), tmp_path)
    assert (err.value.status_code, err.value.detail["class"]) == (404, "no_data")


def test_chart_history_starting_after_as_of(monkeypatch, tmp_path):
    with pytest.raises(HTTPException) as err:
        _chart(monkeypatch, _frame(["2025-10-01", "2025-10-02"]), tmp_path)
    assert err.value.detail["class"] == "no_bars_at_date"
    assert "starts 2025-10-01" in err.value.detail["message"]


def test_chart_nonfinite_anchor_close_is_no_data(monkeypatch, tmp_path):
    # A NaN close on the anchor bar must degrade to 404 no_data, never leak a
    # NaN anchor_close into a saved mark's provenance (Beck, Review 2026-07-12).
    frame = _frame(["2025-09-09", "2025-09-10"])
    frame.iloc[-1, frame.columns.get_loc("Close")] = float("nan")
    with pytest.raises(HTTPException) as err:
        _chart(monkeypatch, frame, tmp_path, as_of="2025-09-10")
    assert (err.value.status_code, err.value.detail["class"]) == (404, "no_data")


def test_chart_freeze_failure_degrades_to_named_503(monkeypatch, tmp_path):
    # A freeze I/O failure surfaces as the named 503 'freeze_failed' refusal
    # (EC-6 degrade-never-500), never a bare 500 that hides it (Beck, Review
    # 2026-07-12) — every sibling refusal class is pinned; this one wasn't.
    import frame_store

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(frame_store, "freeze_frame", boom)
    with pytest.raises(HTTPException) as err:
        _chart(monkeypatch, _frame(["2025-09-09", "2025-09-10"]), tmp_path,
               as_of="2025-09-10")
    assert (err.value.status_code, err.value.detail["class"]) == (503, "freeze_failed")


def test_chart_happy_path_provenance_and_resolution(monkeypatch, tmp_path):
    frame = _frame(["2025-09-09", "2025-09-10", "2025-09-12", "2025-09-15"])
    out = _chart(monkeypatch, frame, tmp_path, as_of="2025-09-11")  # not a session
    assert out["as_of_session"] == "2025-09-10"
    # Server-named adjacent SESSIONS (the scrub steps these, never guessed
    # calendar days): prev is the bar before, next skips the non-session gap.
    assert (out["prev_session"], out["next_session"]) == ("2025-09-09", "2025-09-12")
    assert out["anchor_close"] == 100.0
    assert (out["bar_count"], out["forward_bars"]) == (2, 2)
    assert (out["frame_start"], out["frame_end"]) == ("2025-09-09", "2025-09-15")
    assert out["data_regime"] in ("as_traded", "div_adjusted")
    assert len(out["engine_config_version"]) == 64  # sha256 hex
    assert len(out["frame_digest"]) == 64  # the mark's basis, frozen at fetch
    assert any("resolved to 2025-09-10" in w for w in out["warnings"])
    assert any("short history" in w for w in out["warnings"])
    assert len(out["candles"]) == 4 and len(out["volumes"]) == 4


_SKYT_DATES = ["2025-09-08", "2025-09-09", "2025-09-10", "2025-09-12", "2025-09-15"]


def test_chart_draws_the_preserved_copy_when_the_vendor_has_nothing(monkeypatch, tmp_path):
    # SKYT, 2026-08-28: the vendor stopped serving a ticker the operator had
    # already marked, and the chart refused although its bars sat frozen on disk.
    first = _chart(monkeypatch, _frame(_SKYT_DATES), tmp_path, as_of="2025-09-10")
    assert first["source"] == "vendor"

    gone = _chart(monkeypatch, _frame([]), tmp_path, as_of="2025-09-10")
    assert (gone["source"], gone["preserved_reason"]) == ("preserved", "no_data")
    assert first["preserved_reason"] is None
    assert gone["warnings"][0].startswith("preserved copy")
    # The same bars, the same basis: the whole frozen window (forward bars too).
    for key in ("as_of_session", "frame_digest", "bar_count", "forward_bars",
                "frame_start", "frame_end", "prev_session", "next_session",
                "anchor_close", "candles", "volumes"):
        assert gone[key] == first[key], key


def test_preserved_copy_answers_a_throttled_vendor_too(monkeypatch, tmp_path):
    from core.pipeline.market_data import rate_limit
    _chart(monkeypatch, _frame(_SKYT_DATES), tmp_path, as_of="2025-09-10")
    import domains.market_data.candle_cache as candle_cache
    monkeypatch.setattr(candle_cache, "_CACHE", {})
    monkeypatch.setattr(rate_limit, "in_cooldown", lambda: True)
    out = calibration_chart(ticker="KLAC", as_of="2025-09-10")
    assert (out["source"], out["preserved_reason"]) == ("preserved", "rate_limited")
    # A throttle is not a lost ticker: the words say so, and the page keeps such
    # a copy out of its sitting cache so the next lookup tries the vendor again.
    assert "throttling" in out["warnings"][0] and "no data" not in out["warnings"][0]


def test_preserved_copy_reaches_a_nearby_typed_date_but_not_another_chart(
        monkeypatch, tmp_path):
    # Frozen on Friday 2025-09-12; the frozen window runs on to Monday 09-15.
    _chart(monkeypatch, _frame(_SKYT_DATES), tmp_path, as_of="2025-09-12")
    # The weekend after it is not a session, so it still finds Friday...
    for weekend in ("2025-09-13", "2025-09-14"):
        near = _chart(monkeypatch, _frame([]), tmp_path, as_of=weekend)
        assert (near["source"], near["as_of_session"]) == ("preserved", "2025-09-12")
        assert any("resolved to 2025-09-12" in w for w in near["warnings"])
        assert near["forward_bars"] == 1  # Monday, counted the same as the vendor path
    # ...but Monday is a REAL session of its own (it is in the frozen window as a
    # forward bar), so drawing Friday's chart and calling Monday "not a session"
    # would be a lie: refused, naming the date that IS loadable (review 2026-10-02).
    for other_chart in ("2025-09-15", "2025-10-15"):
        with pytest.raises(HTTPException) as err:
            _chart(monkeypatch, _frame([]), tmp_path, as_of=other_chart)
        assert err.value.detail["class"] == "no_data"
        assert "preserved copy exists for 2025-09-12" in err.value.detail["message"]


def test_a_vendor_crash_falls_back_too_and_never_500s(monkeypatch, tmp_path):
    import domains.market_data.service as market_data

    def boom(*a, **k):
        raise RuntimeError("vendor chain exploded")

    _chart(monkeypatch, _frame(_SKYT_DATES), tmp_path, as_of="2025-09-10")
    import domains.market_data.candle_cache as candle_cache
    monkeypatch.setattr(candle_cache, "_CACHE", {})
    monkeypatch.setattr(market_data, "daily_candle_frame", boom)
    assert calibration_chart(ticker="KLAC", as_of="2025-09-10")["source"] == "preserved"
    # With no frozen copy the crash is a named refusal, not a bare 500.
    with pytest.raises(HTTPException) as err:
        calibration_chart(ticker="NOPE", as_of="2025-09-10")
    assert (err.value.status_code, err.value.detail["class"]) == (503, "vendor_error")


def test_an_unreadable_preserved_copy_is_skipped_not_raised(monkeypatch, tmp_path):
    import frame_store
    _chart(monkeypatch, _frame(_SKYT_DATES), tmp_path, as_of="2025-09-10")

    def torn(*a, **k):
        raise OSError("torn parquet")

    monkeypatch.setattr(frame_store, "load_preserved_chart", torn)
    with pytest.raises(HTTPException) as err:
        _chart(monkeypatch, _frame([]), tmp_path, as_of="2025-09-10")
    assert err.value.detail["class"] == "no_data"
    # Never "a preserved copy exists for 2025-09-10 — load it" about the very
    # date that just failed to read.
    assert "copy for 2025-09-10 could not be read" in err.value.detail["message"]


def test_preserved_copy_draws_the_rendering_the_marks_are_bound_to(monkeypatch, tmp_path):
    # A vendor restatement froze a second rendering beside the first; the saved
    # marks sit on the second. The preserved chart must draw THAT one, or the
    # operator's next edit would be refused as a rebind (409).
    first = _chart(monkeypatch, _frame(_SKYT_DATES, close=100.0), tmp_path, as_of="2025-09-10")
    restated = _chart(monkeypatch, _frame(_SKYT_DATES, close=90.0), tmp_path, as_of="2025-09-10")
    assert restated["frame_digest"] != first["frame_digest"]

    monkeypatch.setattr(calibration, "_bound_digest", lambda *a: restated["frame_digest"])
    out = _chart(monkeypatch, _frame([]), tmp_path, as_of="2025-09-10")
    assert out["frame_digest"] == restated["frame_digest"]
    assert out["anchor_close"] == 90.0 and out["forward_bars"] == restated["forward_bars"]

    monkeypatch.setattr(calibration, "_bound_digest", lambda *a: None)
    unbound = _chart(monkeypatch, _frame([]), tmp_path, as_of="2025-09-10")
    assert unbound["frame_digest"] == first["frame_digest"]  # no marks: the first freeze


def test_a_mark_saved_on_the_preserved_copy_binds(monkeypatch, tmp_path, db):
    _chart(monkeypatch, _frame(_SKYT_DATES), tmp_path, as_of="2025-09-10")
    out = _chart(monkeypatch, _frame([]), tmp_path, as_of="2025-09-10")
    saved = create_mark(_payload(out["frame_digest"], ticker="KLAC",
                                 as_of_date="2025-09-10", box_start_date="2025-09-08",
                                 box_end_date="2025-09-10", events=[]), db)
    assert saved.frame_digest == out["frame_digest"]


def test_chart_freezes_a_loadable_forward_grading_frame(monkeypatch, tmp_path):
    # A chart load must also freeze the forward-inclusive grading frame (Task 2),
    # so a later Trigger grade — a buy AFTER as-of — can replay frozen-only.
    import frame_store
    frame = _frame(["2025-09-09", "2025-09-10", "2025-09-12", "2025-09-15"])
    out = _chart(monkeypatch, frame, tmp_path, as_of="2025-09-11")
    gf = frame_store.load_grading_frame(out["ticker"], out["as_of_session"],
                                        out["frame_digest"])
    assert gf is not None
    # It carries bars AFTER as-of (the Trigger's forward window)...
    assert gf.index.max() > pd.Timestamp(out["as_of_session"])
    # ...and its <= as-of slice reproduces the mark's frozen basis exactly.
    le = gf[gf.index <= pd.Timestamp(out["as_of_session"])]
    assert frame_store.ohlcv_digest(le) == out["frame_digest"]


def _add_mark(db, **overrides):
    from datetime import datetime, timezone
    fields = dict(
        ticker="BODI", as_of_date="2026-04-15", label="", verdict="box",
        resistance=12.40, support=10.15, box_start_date="2025-12-12",
        box_end_date="2026-04-15", data_regime="as_traded",
        engine_config_version="cfg", anchor_close=11.02, frame_digest="d0",
        revision=1,
    )
    fields.update(overrides)
    now = datetime.now(timezone.utc)
    mark = CalibrationMark(created_at=now, updated_at=now, **fields)
    db.add(mark)
    db.commit()
    db.refresh(mark)
    return mark


# ── Frame thumbnail (v2 ledger mini-chart) ───────────────────────────


def test_frame_thumb_serves_a_downsampled_series(digest, monkeypatch):
    monkeypatch.setattr(calibration, "_FRAME_PREVIEWS", {})
    body = calibration_frame_thumb(ticker="BODI", as_of="2026-04-15",
                                   frame_digest=digest)
    assert body["ticker"] == "BODI"
    assert body["frame_digest"] == digest
    assert body["n"] == 3 and len(body["series"]) == 3
    assert body["lo"] < body["hi"]
    assert all("t" in p and "c" in p for p in body["series"])


def test_frame_thumb_refuses_an_unfrozen_digest(digest, monkeypatch):
    monkeypatch.setattr(calibration, "_FRAME_PREVIEWS", {})
    with pytest.raises(HTTPException) as err:
        calibration_frame_thumb(ticker="BODI", as_of="2026-04-15",
                                frame_digest="f" * 64)  # never frozen
    assert err.value.status_code == 404
    assert err.value.detail["class"] == "unbound_frame"


def test_frame_thumb_rejects_a_missing_digest():
    with pytest.raises(HTTPException) as err:
        calibration_frame_thumb(ticker="BODI", as_of="2026-04-15", frame_digest="")
    assert err.value.status_code == 400
    assert err.value.detail["class"] == "bad_digest"


def test_frame_thumb_caches_by_digest_never_re_reads(digest, monkeypatch):
    store = {}
    monkeypatch.setattr(calibration, "_FRAME_PREVIEWS", store)
    calibration_frame_thumb(ticker="BODI", as_of="2026-04-15", frame_digest=digest)
    assert digest in store  # computed once, cached under the content digest

    import frame_store
    def boom(*_a, **_k):
        raise AssertionError("a cache HIT must not re-read the parquet")
    monkeypatch.setattr(frame_store, "load_frame", boom)
    body = calibration_frame_thumb(ticker="BODI", as_of="2026-04-15",
                                   frame_digest=digest)
    assert body["n"] == 3  # served from cache


# ── Fired-in-window grade (the sharper "Engine" chip) ────────────────
import threading  # noqa: E402

import domains.calibration.fired as fired_service  # noqa: E402
from domains.calibration.fired import (  # noqa: E402
    _chip_from_fired,
    fired_for_marks,
    reset_fired_cache,
)


def _ns_mark(**overrides):
    # A complete stand-in: fired_for_marks builds _mark_dict(mark) on a miss,
    # which reads the full model shape (incl. events), so the fake carries it all.
    from datetime import datetime, timezone
    from types import SimpleNamespace
    base = dict(
        id=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), revision=1,
        ticker="BODI", as_of_date="2026-04-15", label="", verdict="box",
        resistance=12.4, support=10.15, box_start_date="2025-12-12",
        box_end_date="2026-04-15", r_anchor_date=None, s_anchor_date=None,
        first_rail=None, rails_source="operator", knowable_from_date=None,
        note=None, data_regime="as_traded", engine_config_version="cfg",
        anchor_close=11.02, frame_digest="d0",
        trigger_date=None, trigger_price=None, events=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_fired_chip_maps_fired_missed_and_unassessable(monkeypatch):
    # isolate the mapping from the real traced read
    monkeypatch.setattr(fired_service, "_miss_reason",
                        lambda md, **k: {"stage": "respect", "detail": "respect 0.71 < 0.80"})
    md = {"resistance": 12.4, "support": 10.15}
    ok = _chip_from_fired(md, {"fired": True, "fire_tier": "S",
                               "fire_R": 12.4, "fire_S": 10.15,
                               "fire_rails_within_tol": True})
    assert ok["state"] == "ok" and ok["kind"] == "fired" and ok["tier"] == "S"
    assert ok["rail_delta"] == 0.0  # fired at his exact rails
    miss = _chip_from_fired(md, {"fired": False, "fired_window": ["2026-04-01", "2026-04-15"]})
    assert miss["state"] == "miss" and miss["kind"] == "missed"
    assert miss["stage"] == "respect" and "0.71" in miss["detail"]  # the gate that killed it
    none = _chip_from_fired(md, {"fired": None, "fired_detail": "EVAL_ERROR"})
    assert none["state"] == "untested" and none["kind"] == "unassessable"
    assert _chip_from_fired(md, None)["kind"] == "negative"


def test_miss_reason_degrades_to_none_when_the_frame_is_gone():
    from domains.calibration.fired import _miss_reason
    reason = _miss_reason(
        {"ticker": "ZZZZ", "as_of_date": "2020-01-01", "resistance": 1.0, "support": 0.0},
        frame_loader=lambda *_a, **_k: None)
    assert reason is None  # no frozen frame -> reasonless 'missed', never a crash


def test_fired_non_box_is_untested_without_compute():
    reset_fired_cache()

    def forbidden(_md):
        raise AssertionError("a negative must not run the fired pipeline")

    out = fired_for_marks([_ns_mark(verdict="no_structure", resistance=None, support=None)],
                          compute=forbidden, background=False)
    assert out["computing"] is False
    assert out["marks"][1]["state"] == "untested" and out["marks"][1]["kind"] == "negative"


def test_fired_sync_grades_and_caches(monkeypatch):
    reset_fired_cache()
    monkeypatch.setattr("engine_alpha.stamp.manifest_hash", lambda: "LIVE")
    calls = []

    def grader(md):
        calls.append(1)
        return {"state": "ok", "kind": "fired", "tier": "A", "rail_delta": 0.1}

    mark = _ns_mark(engine_config_version="LIVE")
    first = fired_for_marks([mark], compute=grader, background=False)
    assert first["computing"] is False
    assert first["marks"][1]["state"] == "ok" and first["marks"][1]["stale"] is False
    fired_for_marks([mark], compute=grader, background=False)  # second call
    assert calls == [1]  # served from cache, grader not re-run


def test_fired_degrades_a_throwing_grade(monkeypatch):
    reset_fired_cache()
    monkeypatch.setattr("engine_alpha.stamp.manifest_hash", lambda: "LIVE")

    def boom(_md):
        raise RuntimeError("pipeline exploded")

    out = fired_for_marks([_ns_mark()], compute=boom, background=False)
    assert out["marks"][1]["state"] == "untested" and out["marks"][1]["kind"] == "error"


def test_fired_cache_keys_on_birth_stamp(monkeypatch):
    from datetime import datetime, timezone
    reset_fired_cache()
    monkeypatch.setattr("engine_alpha.stamp.manifest_hash", lambda: "LIVE")
    calls = []

    def grader(_md):
        calls.append(1)
        return {"state": "ok", "kind": "fired"}

    common = dict(id=5, revision=1, engine_config_version="LIVE")
    old = _ns_mark(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), **common)
    reborn = _ns_mark(created_at=datetime(2026, 2, 2, tzinfo=timezone.utc), **common)
    fired_for_marks([old], compute=grader, background=False)
    fired_for_marks([reborn], compute=grader, background=False)
    assert calls == [1, 1]  # a reused rowid with a fresh birth stamp re-grades


def test_fired_pool_returns_pending_then_settles(monkeypatch):
    import time
    reset_fired_cache()
    monkeypatch.setattr("engine_alpha.stamp.manifest_hash", lambda: "LIVE")
    gate = threading.Event()

    def slow(_md):
        gate.wait(3)
        return {"state": "ok", "kind": "fired", "tier": "S", "rail_delta": 0.1}

    mark = _ns_mark(engine_config_version="LIVE")
    first = fired_for_marks([mark], compute=slow, background=True)
    assert first["computing"] is True                 # non-blocking
    assert first["marks"][1]["state"] == "pending"
    gate.set()
    settled = None
    for _ in range(60):                               # bounded poll
        settled = fired_for_marks([mark], compute=slow, background=True)
        if not settled["computing"]:
            break
        time.sleep(0.05)
    assert settled["computing"] is False
    assert settled["marks"][1]["state"] == "ok"       # worker filled the cache


def test_fired_endpoint_filters_to_the_requested_ticker(db, monkeypatch):
    _add_mark(db, ticker="BODI")
    _add_mark(db, ticker="KLAC", as_of_date="2025-09-11", frame_digest="d2")
    seen = {}

    def fake(marks):
        seen["tickers"] = {m.ticker for m in marks}
        return {"marks": {m.id: {"state": "pending"} for m in marks}, "computing": True}

    monkeypatch.setattr(fired_service, "fired_for_marks", fake)
    body = calibration_fired(ticker="bodi", db=db)
    assert body["ticker"] == "BODI" and body["computing"] is True
    assert seen["tickers"] == {"BODI"}


def test_fired_endpoint_rejects_a_bad_ticker(db):
    with pytest.raises(HTTPException) as err:
        calibration_fired(ticker="!!", db=db)
    assert err.value.status_code == 400
    assert err.value.detail["class"] == "bad_ticker"


# ── Trigger grade ("did the engine fire by my buy?") ─────────────────
from domains.calibration.trigger_grade import (  # noqa: E402
    classify_fire_timing,
    trigger_grade_for_marks,
)


def test_classify_fire_timing_three_honest_outcomes():
    assert classify_fire_timing("2026-04-14", "2026-04-16") == "at_or_before"
    assert classify_fire_timing("2026-04-16", "2026-04-16") == "at_or_before"  # on-trigger
    assert classify_fire_timing("2026-04-20", "2026-04-16") == "after"
    assert classify_fire_timing(None, "2026-04-16") == "never"  # not "late"


def test_trigger_grade_layers_timing_over_the_fired_replay(db):
    m = _add_mark(db, trigger_date="2026-04-16", trigger_price=12.55)
    fired = {"marks": {m.id: {"state": "ok", "kind": "fired",
                              "fire_date": "2026-04-14", "rail_delta": 0.02}},
             "computing": False}
    grade = trigger_grade_for_marks([m], fired=fired)["marks"][m.id]
    assert grade["kind"] == "graded"
    assert grade["box"] == {"elected": True, "rail_delta": 0.02}  # top priority
    assert grade["timing"]["outcome"] == "at_or_before"
    assert grade["timing"]["fire_date"] == "2026-04-14"


def test_trigger_grade_fired_after_and_never_are_distinct(db):
    m = _add_mark(db, trigger_date="2026-04-16", trigger_price=12.55)
    after = trigger_grade_for_marks([m], fired={
        "marks": {m.id: {"state": "ok", "fire_date": "2026-04-20"}},
        "computing": False})["marks"][m.id]
    assert after["timing"]["outcome"] == "after"
    # A missed chip carries NO fire_date -> never, never silently "after/late".
    never = trigger_grade_for_marks([m], fired={
        "marks": {m.id: {"state": "miss", "kind": "missed"}},
        "computing": False})["marks"][m.id]
    assert never["timing"]["outcome"] == "never"
    assert never["box"]["elected"] is False


def test_trigger_grade_grades_a_box_without_a_trigger_on_the_top_tiers(db):
    # The north-star: Box/R/S evidence must show for EVERY setup, buy or not — a
    # top-priority gap is never hidden just because no Trigger is marked yet.
    m = _add_mark(db)  # a box, no buy marked
    fired = {"marks": {m.id: {"state": "ok", "fire_date": "2026-05-01",
                              "rail_delta": 0.05}}, "computing": False}
    grade = trigger_grade_for_marks([m], fired=fired)["marks"][m.id]
    assert grade["kind"] == "graded"
    assert grade["box"]["elected"] is True             # top tier still graded
    assert grade["timing"]["outcome"] == "no_trigger"  # timing waits for a buy


def test_trigger_grade_negative_has_no_box(db):
    m = _add_mark(db, verdict="no_structure", resistance=None, support=None,
                  box_start_date=None, box_end_date=None)
    out = trigger_grade_for_marks([m], fired={"marks": {}, "computing": False})
    assert out["marks"][m.id]["kind"] == "negative"


def test_trigger_grade_streams_pending_like_fired(db):
    m = _add_mark(db, trigger_date="2026-04-16", trigger_price=12.55)
    out = trigger_grade_for_marks([m], fired={
        "marks": {m.id: {"state": "pending"}}, "computing": True})
    assert out["computing"] is True
    assert out["marks"][m.id]["kind"] == "pending"


def test_trigger_grade_endpoint_filters_to_the_requested_ticker(db, monkeypatch):
    _add_mark(db, ticker="BODI", trigger_date="2026-04-16", trigger_price=12.55)
    _add_mark(db, ticker="KLAC", as_of_date="2025-09-11", frame_digest="d2")
    import domains.calibration.trigger_grade as tg
    seen = {}

    def fake(marks, **_k):
        seen["tickers"] = {m.ticker for m in marks}
        return {"marks": {m.id: {"kind": "no_trigger"} for m in marks}, "computing": False}

    monkeypatch.setattr(tg, "trigger_grade_for_marks", fake)
    body = calibration_trigger_grade(ticker="bodi", db=db)
    assert body["ticker"] == "BODI"
    assert seen["tickers"] == {"BODI"}  # never grades another ticker's marks
