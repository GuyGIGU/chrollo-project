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
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from models import CalibrationMark, CalibrationMarkEvent  # noqa: E402
from routers import calibration  # noqa: E402
from routers.calibration import (  # noqa: E402
    MarkIn,
    MarkOut,
    calibration_chart,
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
    saved = MarkOut.model_validate(create_mark(_payload(digest, ticker="bodi"), db))
    assert saved.ticker == "BODI"  # normalized at the boundary
    assert (saved.verdict, saved.revision, saved.label) == ("box", 1, "")
    assert (saved.resistance, saved.support) == (12.40, 10.15)
    assert (saved.box_start_date, saved.box_end_date) == ("2025-12-12", "2026-04-15")
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


def test_duplicate_identity_is_a_named_conflict(db, digest):
    create_mark(_payload(digest), db)
    with pytest.raises(HTTPException) as err:
        create_mark(_payload(digest), db)
    assert err.value.status_code == 409
    assert err.value.detail["class"] == "duplicate_mark"
    assert db.query(CalibrationMark).count() == 1


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
    create_mark(_payload(digest), db)
    other = create_mark(_payload(digest, as_of_date="2026-04-14",
                                 box_end_date="2026-04-14"), db)
    with pytest.raises(HTTPException) as err:
        update_mark(other.id, _payload(digest), db)  # would collide with the first
    assert err.value.detail["class"] == "duplicate_mark"
    with pytest.raises(HTTPException) as err:
        update_mark(9999, _payload(digest), db)
    assert err.value.status_code == 404


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


# ── Same-app write guard ─────────────────────────────────────────────


def test_same_app_guard_rejects_foreign_and_missing_header():
    for bad in ("", "not-ours"):
        with pytest.raises(HTTPException) as err:
            require_same_app(bad)
        assert err.value.status_code == 403
        assert err.value.detail["class"] == "cross_app_write"
    require_same_app("chrollo-dashboard")  # no raise


def test_every_side_effectful_route_declares_the_guard():
    # Every mutating route AND the chart GET (it spends the vendor bucket and
    # freezes frames — Council finding 11): guarded, drive-by pages excluded.
    for route in calibration.router.routes:
        methods = getattr(route, "methods", set()) or set()
        side_effectful = bool(methods & {"POST", "PUT", "DELETE", "PATCH"})
        if route.path.endswith("/chart"):
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
    import services.market_data as market_data
    import webapp.backend.frame_store as wb_frame_store
    monkeypatch.setattr(market_data, "daily_candle_frame",
                        lambda *a, **k: frame)
    # Both module instances — never the live store, whichever import form
    # a future change routes through.
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(wb_frame_store, "FRAMES_DIR", str(tmp_path))
    return calibration_chart(ticker=ticker, as_of=as_of)


def test_chart_validation_refusals(monkeypatch):
    # The vendor must be unreachable here: if a validation rule regresses,
    # this test fails loud and OFFLINE, never with a live network call.
    import services.market_data as market_data
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
